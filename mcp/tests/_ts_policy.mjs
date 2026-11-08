/**
 * The TypeScript policy layer, reported as JSON.
 *
 * The point of this script is parity: the Python implementation and
 * this one must agree about the rule table and about every decision
 * it reaches, because a client that talks to one server and then the
 * other must not see a different policy.
 */
import { RULES } from '../dist/policy-rules.js';
import { evaluate as evaluatePolicy, defaultPolicy, loadPolicy } from '../dist/policy.js';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const ids = RULES.map((r) => r.id);
const verdicts = {};
const evidence = {};
const walls = {};
for (const rule of RULES) {
  verdicts[rule.id] = rule.verdict;
  evidence[rule.id] = rule.evidence ?? null;
  if (rule.appliesWhen !== undefined) walls[rule.id] = rule.appliesWhen;
}

// The contexts to compare. Each is a real decision a caller can
// reach, so a divergence here is a divergence a client would see.
const CASES = [
  { operation: 'install.skills', context: {} },
  { operation: 'install.skills', context: { apply: true } },
  { operation: 'install.skills', context: { apply: 'yes' } },
  { operation: 'install.skills', context: { apply: true, overwrite: true } },
  {
    operation: 'install.skills',
    context: { apply: true, args: { outside_whitelist: true } },
  },
  {
    operation: 'install.skills',
    context: { apply: true, args: { harness_managed: true } },
  },
  {
    operation: 'install.skills',
    context: { apply: true, args: { symlink_outward: true } },
  },
  {
    operation: 'install.skills',
    context: { apply: true, args: { outside_whitelist: 'true' } },
  },
  // The overwrite gate: it holds until the caller says they meant to.
  {
    operation: 'install.skills',
    context: { apply: true, args: { overwrite_requested: true } },
  },
  {
    operation: 'install.skills',
    context: {
      apply: true,
      overwrite: true,
      args: { overwrite_requested: true },
    },
  },
  { operation: 'install.agents', context: {} },
  { operation: 'install.agents', context: { apply: true } },
  { operation: 'uninstall.skills', context: {} },
  { operation: 'uninstall.skills', context: { apply: true } },
  { operation: 'uninstall.agents', context: {} },
  { operation: 'uninstall.agents', context: { apply: true } },
  {
    operation: 'uninstall.agents',
    context: { apply: true, args: { not_ours: true } },
  },
  {
    operation: 'uninstall.agents',
    context: { apply: true, args: { outside_whitelist: true } },
  },
  { operation: 'an.operation.that.does.not.exist', context: {} },
  // The plans: a dry run writes nothing, so it is allowed outright.
  { operation: 'install.skills.plan', context: {} },
  { operation: 'install.agents.plan', context: {} },
  { operation: 'uninstall.skills.plan', context: {} },
  { operation: 'uninstall.agents.plan', context: {} },
];

const cases = CASES.map(({ operation, context }) => {
  const decision = evaluatePolicy(operation, context, defaultPolicy());
  return {
    operation,
    context,
    rule: decision.rule,
    verdict: decision.verdict,
    satisfied: decision.satisfied ?? null,
  };
});

// The project policy file, exercised against the TypeScript loader.
//
// The Python side of this is checked in `test_policy.py`. The two
// implementations must behave the same here too -- and the way to
// know that is to ask both of them, not to assume they agree.
//
// The file cases are reported as the *effect* of the file, not as the
// loader's internals: what matters is the verdict a caller would get,
// and whether the loader refused the file at all.
function withPolicyFile(contents, fn) {
  const root = mkdtempSync(join(tmpdir(), 'ts-policy-'));
  const dir = join(root, '.skills-library');
  mkdirSync(dir);
  if (contents !== null) {
    writeFileSync(join(dir, 'policy.json'), contents);
  }
  try {
    return fn(root);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

const fileCases = [];

// No file: the built-in policy applies.
fileCases.push({
  label: 'missing file',
  expect: 'ok',
  got: withPolicyFile(null, (root) => {
    const p = loadPolicy(root);
    return { source: p.source, overrides: p.overrides.length };
  }),
  want: { source: 'default', overrides: 0 },
});

// A deny tightens the rule.
fileCases.push({
  label: 'deny SL-1',
  expect: 'ok',
  got: withPolicyFile(JSON.stringify({ schema_version: 1, deny: ['SL-1'] }), (root) => {
    const p = loadPolicy(root);
    const d = evaluatePolicy('install.skills', { apply: true }, p);
    return { source: p.source, overrides: p.overrides, rule: d.rule, verdict: d.verdict };
  }),
  want: { source: 'file', overrides: ['SL-1'], rule: 'SL-1', verdict: 'deny' },
});

// A malformed file is an error, not a silent fall back.
//
// The error's *name* is recorded as well as its message: a loader that
// fell over on a `None` would raise a `TypeError`, which is a crash
// rather than a refusal, and the caller cannot act on a crash.
for (const [label, text] of [
  ['not JSON at all', 'this is not json'],
  ['JSON but not an object', '[1, 2, 3]'],
  ['an object without a deny array', '{"schema_version": 1}'],
  ['a deny that is not an array', '{"schema_version": 1, "deny": "SL-1"}'],
]) {
  fileCases.push({
    label: `malformed: ${label}`,
    expect: 'error',
    got: withPolicyFile(text, (root) => {
      try {
        loadPolicy(root);
        return { error: null, errorName: null };
      } catch (e) {
        return {
          error: e instanceof Error ? e.message : String(e),
          errorName: e instanceof Error ? e.name : typeof e,
        };
      }
    }),
    want: { error: 'raises' },
  });
}

// An unknown rule id is an error: the file was written to say
// something, and a typo must not be ignored.
fileCases.push({
  label: 'unknown rule id',
  expect: 'error',
  got: withPolicyFile(JSON.stringify({ schema_version: 1, deny: ['SL-999'] }), (root) => {
    try {
      loadPolicy(root);
      return { error: null, errorName: null };
    } catch (e) {
      return {
        error: e instanceof Error ? e.message : String(e),
        errorName: e instanceof Error ? e.name : typeof e,
      };
    }
  }),
  want: { error: 'raises' },
});

process.stdout.write(
  JSON.stringify({ ids, verdicts, evidence, walls, cases, fileCases }, null, 2),
);
