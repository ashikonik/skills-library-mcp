/**
 * The policy layer: what the server is allowed to do, and who says so.
 *
 * The rules live in `policy-rules.ts`; this file evaluates them.
 *
 * **Three verdicts.** `allow`, `deny`, `conditional`. A conditional
 * rule holds the operation until the caller supplies the evidence it
 * names -- and when it does, the verdict is still `conditional`, with
 * `satisfied: true`. A satisfied gate is not an allow: the caller
 * learns which gate opened, which is the thing worth knowing.
 *
 * **A deny outranks a satisfied conditional.** A deny is a wall; a
 * satisfied conditional is only the absence of one. So the passes are
 * ordered: the denies first, then the conditionals, then the allow.
 *
 * **An operation with no rule is refused**, as `SL-0`. A surface not
 * in the table is not an implicit yes.
 *
 * **A project may only tighten.** `<project>/.skills-library/policy.json`
 * lists rule ids to deny. There is no way to write "allow" in it, so
 * the file cannot loosen anything -- and a malformed file is an
 * error, not a silent fall back to the defaults. A policy file that
 * cannot be read must not silently become no policy.
 */
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { RULES, findRule, rulesFor, wallRules, type PolicyVerdict, type Rule } from './policy-rules.js';

export { RULES, findRule, POLICY_TTL_MS } from './policy-rules.js';
export type { PolicyVerdict, Rule } from './policy-rules.js';

/** Where the project's policy file lives, relative to the project root. */
export const POLICY_DIR = '.skills-library';
export const POLICY_FILE = 'policy.json';

/** The decision the evaluator reaches. */
export interface PolicyDecision {
  /** The rule that decided it. `SL-0` when no rule covers the operation. */
  rule: string;
  /** The operation that was asked about. */
  operation: string;
  /** The verdict. */
  verdict: PolicyVerdict;
  /** Why. This is the rule's own reason. */
  reason: string;
  /** For a conditional: whether the evidence was supplied. */
  satisfied?: boolean;
  /** What to tell the caller. */
  hint?: string;
}

/**
 * The facts a decision is made against.
 *
 * The named fields are the ones the rules read. `args` holds the
 * facts the server worked out for itself -- "the target is outside
 * the whitelist", "the file is not ours" -- so the rules stay a
 * statement of policy rather than a second implementation of the
 * checks.
 */
export interface PolicyContext {
  /** The caller asked for the write to happen. */
  apply?: boolean;
  /** The caller asked to replace what is there. */
  overwrite?: boolean;
  /** The server worked out these facts about the operation. */
  args?: Record<string, unknown>;
}

/** The policy in force: the built-in rules, plus any project overrides. */
export interface Policy {
  /** The effective verdict per rule id. Every rule is present. */
  rules: Map<string, { verdict: PolicyVerdict; reason?: string }>;
  /** The rule ids the project file tightened. */
  overrides: string[];
  /** Where the policy came from: `default` or `file`. */
  source: 'default' | 'file';
  /** The policy file's path, when there is one. */
  path: string | null;
}

/** The built-in policy: every rule, at its own verdict. */
export function defaultPolicy(): Policy {
  const rules = new Map<string, { verdict: PolicyVerdict; reason?: string }>();
  for (const rule of RULES) {
    rules.set(rule.id, { verdict: rule.verdict, reason: rule.reason });
  }
  return { rules, overrides: [], source: 'default', path: null };
}

/**
 * The effective verdict of a rule: the override if there is one, the
 * built-in otherwise.
 */
export function verdictOf(policy: Policy, rule: Rule): PolicyVerdict {
  return policy.rules.get(rule.id)?.verdict ?? rule.verdict;
}

/**
 * The facts a wall is decided by.
 *
 * A wall is a deny rule with an `appliesWhen`. The fact it names is
 * looked up in `ctx.args` under exactly that name, and it must be
 * literally `true`. Anything else -- absent, false, a truthy string --
 * means the wall does not apply.
 */
function wallApplies(rule: Rule, ctx: PolicyContext): boolean {
  if (rule.appliesWhen === undefined) return true;
  return ctx.args?.[rule.appliesWhen] === true;
}

/**
 * Is a conditional rule's evidence present?
 *
 * The evidence is a comma-separated list of fact names. Each is
 * looked up in `ctx.args` and then at the top level of the context,
 * and it must be exactly `true` -- the caller asked for the write,
 * not merely mentioned it.
 */
export function evidencePresent(rule: Rule, ctx: PolicyContext): boolean {
  if (rule.evidence === undefined) return true;
  for (const name of rule.evidence.split(',')) {
    const fact = name.trim();
    if (!fact) continue;
    const value = ctx.args?.[fact] ?? (ctx as Record<string, unknown>)[fact];
    if (value !== true) return false;
  }
  return true;
}

/**
 * Evaluate an operation against the policy.
 *
 * The passes are ordered: the denies, then the conditionals, then the
 * allow. A deny is reported as soon as one applies, so it outranks a
 * conditional that was satisfied.
 */
export function evaluate(
  operation: string,
  ctx: PolicyContext,
  policy: Policy = defaultPolicy(),
): PolicyDecision {
  const applicable = rulesFor(operation);
  const walls = wallRules();

  // Pass 1: the walls. A deny is a wall, and it outranks everything.
  //
  // A wall can also be *conditional*: it applies under a fact, and
  // then holds the operation until its evidence is supplied. SL-3 is
  // one -- it applies when the caller is about to overwrite
  // something, and holds until they say they meant to.
  let satisfiedWall: Rule | null = null;
  for (const rule of walls) {
    // A wall guards one operation. It is checked when that operation
    // is performed, not on every operation -- otherwise two walls
    // that share a fact (SL-5 and SL-10 both watch
    // `outside_whitelist`) would collide, and the one that happens to
    // come first in the table would fire for an operation it has
    // nothing to do with.
    if (rule.operation !== operation) continue;
    const verdict = verdictOf(policy, rule);
    if (verdict !== 'deny' && verdict !== 'conditional') continue;
    if (!wallApplies(rule, ctx)) continue;
    if (verdict === 'deny') {
      return {
        rule: rule.id,
        operation,
        verdict: 'deny',
        reason: policy.rules.get(rule.id)?.reason ?? rule.reason,
        hint: rule.hint,
      };
    }
    // A conditional wall: it holds unless its evidence is present.
    if (!evidencePresent(rule, ctx)) {
      return {
        rule: rule.id,
        operation,
        verdict: 'conditional',
        satisfied: false,
        reason: policy.rules.get(rule.id)?.reason ?? rule.reason,
        hint: rule.hint,
      };
    }
    if (!satisfiedWall) satisfiedWall = rule;
  }

  // Pass 2: the operation's own rules. An unsatisfied conditional
  // holds the operation.
  let satisfied: Rule | null = null;
  for (const rule of applicable) {
    const verdict = verdictOf(policy, rule);
    if (verdict === 'deny') {
      return {
        rule: rule.id,
        operation,
        verdict: 'deny',
        reason: policy.rules.get(rule.id)?.reason ?? rule.reason,
        hint: rule.hint,
      };
    }
    if (verdict !== 'conditional') continue;
    if (!evidencePresent(rule, ctx)) {
      return {
        rule: rule.id,
        operation,
        verdict: 'conditional',
        satisfied: false,
        reason: policy.rules.get(rule.id)?.reason ?? rule.reason,
        hint: rule.hint,
      };
    }
    if (!satisfied) satisfied = rule;
  }

  // Pass 3: the allow. A satisfied conditional wall is reported in
  // preference to the operation's own conditional, because it is the
  // more specific gate.
  if (satisfiedWall) satisfied = satisfiedWall;
  if (satisfied) {
    return {
      rule: satisfied.id,
      operation,
      verdict: 'conditional',
      satisfied: true,
      reason: policy.rules.get(satisfied.id)?.reason ?? satisfied.reason,
      hint: satisfied.hint,
    };
  }
  if (applicable.length > 0) {
    const first = applicable[0]!;
    return {
      rule: first.id,
      operation,
      verdict: 'allow',
      reason: policy.rules.get(first.id)?.reason ?? first.reason,
    };
  }

  // No rule covers the operation. That is a refusal, not an allow.
  return {
    rule: 'SL-0',
    operation,
    verdict: 'deny',
    reason:
      `the operation '${operation}' is not covered by the policy table. ` +
      'This is a bug in the server, not something the caller can work around.',
    hint: 'The operation should have a rule. Report it.',
  };
}

/**
 * The refusal an operation earns, or `null` when it may proceed.
 *
 * Every operation that touches the filesystem goes through this, so
 * a rule a project tightened is a rule the server honours -- and the
 * refusal names the rule that stopped it.
 */
export function permit(
  operation: string,
  ctx: PolicyContext,
  policy: Policy = defaultPolicy(),
): PolicyDecision | null {
  const decision = evaluate(operation, ctx, policy);
  if (decision.verdict === 'deny') return decision;
  if (decision.verdict === 'conditional' && decision.satisfied === false) {
    return decision;
  }
  return null;
}

/** The refusal fields, in the shape a tool result carries them. */
export function refusalFields(decision: PolicyDecision): Record<string, unknown> {
  return {
    applied: false,
    denied: decision.verdict === 'deny',
    gated: decision.verdict === 'conditional',
    rule: decision.rule,
    operation: decision.operation,
    reason: decision.reason,
    hint: decision.hint,
  };
}

/**
 * Can a project tighten this rule to `deny`?
 *
 * Only tightening is possible: `allow` may become `deny`, `deny` and
 * `conditional` may not become anything else.
 */
export function mayTighten(rule: Rule): boolean {
  return rule.verdict === 'allow';
}

/** The project policy file's shape. */
export interface PolicyFile {
  schema_version: number;
  /** The rule ids the project denies. */
  deny: string[];
}

/**
 * Read the project's policy file.
 *
 * A missing file is normal: the built-in policy applies. A malformed
 * one is an error -- the file was written to say something, and
 * ignoring it would make the server's behaviour depend on a typo.
 */
export function loadPolicy(projectRoot: string): Policy {
  const path = join(projectRoot, POLICY_DIR, POLICY_FILE);
  const base = defaultPolicy();
  if (!existsSync(path)) return base;

  let text: string;
  try {
    text = readFileSync(path, 'utf-8');
  } catch (e) {
    throw new Error(
      `cannot read ${path}: ${e instanceof Error ? e.message : String(e)}. ` +
        'Fix or move the file; the built-in defaults are not used, because a ' +
        'policy file that cannot be read must not silently become no policy.',
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (e) {
    throw new Error(
      `cannot parse ${path} as JSON: ${e instanceof Error ? e.message : String(e)}. ` +
        'Fix or move the file; the built-in defaults are not used, because a ' +
        'policy file that cannot be read must not silently become no policy.',
    );
  }

  const file = parsed as Partial<PolicyFile>;
  if (!file || typeof file !== 'object' || !Array.isArray(file.deny)) {
    throw new Error(
      `${path} is malformed: it must be a JSON object with a "deny" array of ` +
        'rule ids. Fix or move the file; the built-in defaults are not used, ' +
        'because a policy file that cannot be read must not silently become no policy.',
    );
  }

  const policy: Policy = { ...base, source: 'file', path, overrides: [] };
  for (const id of file.deny) {
    const rule = findRule(id);
    if (!rule) {
      throw new Error(
        `${path} denies unknown rule '${id}'. The known rule ids are: ` +
          RULES.map((r) => r.id).join(', '),
      );
    }
    // A project may tighten any rule to `deny`. It may not loosen one
    // that is already `deny` or `conditional` -- the built-in verdict
    // is the floor, not the ceiling.
    policy.rules.set(id, { verdict: 'deny', reason: rule.reason });
    policy.overrides.push(id);
  }
  return policy;
}

/**
 * The effective policy, as the caller sees it.
 *
 * Every rule is reported -- its id, its operation, its effective
 * verdict, why, and whether the project file tightened it -- so a
 * caller can reason about what the server will do before it does it.
 */
export function describePolicy(
  policy: Policy,
  error: string | null = null,
): Record<string, unknown> {
  return {
    policy_path: policy.path,
    source: policy.source,
    error,
    overrides: policy.overrides,
    rules: RULES.map((rule) => ({
      id: rule.id,
      operation: rule.operation,
      verdict: verdictOf(policy, rule),
      reason: policy.rules.get(rule.id)?.reason ?? rule.reason,
      evidence: rule.evidence,
      hint: rule.hint,
      overridden: policy.overrides.includes(rule.id),
    })),
  };
}

/** The project root a policy file is looked for under. */
export function projectRootOf(cwd: string): string {
  return resolve(cwd);
}

export { dirname, join, resolve };
