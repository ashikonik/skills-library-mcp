/**
 * The policy rule table: the safety rules, as data.
 *
 * Every operation the server performs that touches the filesystem is
 * named here, with the verdict it gets and the reason for it. The
 * rules are *data* so that they can be read, reported and tested
 * without running anything.
 *
 * The verdicts are exactly three:
 *
 *   `allow`        the operation may proceed.
 *   `deny`         the operation may not proceed, ever.
 *   `conditional`  the operation may proceed if the caller supplies
 *                  the evidence the rule names.
 *
 * A rule's `evidence` is the fact that satisfies it -- `apply` for a
 * write that has not been asked for, `overwrite` for one that would
 * replace something. A rule with no evidence is always satisfied; a
 * conditional rule with evidence is satisfied only when the caller
 * supplies it.
 *
 * **An operation with no rule is refused**, as `SL-0`. A surface that
 * is not in the table is not an implicit yes: a rule added to the
 * server without a rule here would otherwise be a rule nobody can
 * see, and one nobody can tighten.
 *
 * The rule ids are stable. A refusal names the rule that stopped it,
 * so the ids appear in the server's output, in a project's policy
 * file, and in the tests. They never change meaning.
 */
export type PolicyVerdict = 'allow' | 'deny' | 'conditional';

export interface Rule {
  /** The rule's stable id. `SL-n`, or `SL-0` for the synthetic deny. */
  id: string;
  /** The operation the rule governs, dotted. */
  operation: string;
  /** What the rule says about the operation. */
  verdict: PolicyVerdict;
  /** Why. This is the text a refusal carries. */
  reason: string;
  /** The fact that satisfies a conditional rule. Comma-separated for several. */
  evidence?: string;
  /** The context fact that makes a deny apply. */
  appliesWhen?: string;
  /** What to tell the caller when the rule holds or refuses. */
  hint?: string;
}

/** How long a client may treat the policy report as fresh. */
export const POLICY_TTL_MS = 60_000;

/**
 * The rule table.
 *
 * The order matters: when two rules govern the same operation and
 * both apply, the earlier one is the one reported. The deny rules
 * come before the conditional ones for the same operation, so a
 * refusal names the wall rather than the gate.
 */
export const RULES: Rule[] = [
  {
    id: 'SL-0',
    operation: '*',
    verdict: 'deny',
    reason:
      "the operation is not covered by the policy table. This is a bug in " +
      'the server, not something the caller can work around.',
    hint: 'The operation should have a rule. Report it.',
  },

  // ------------------------------------------------------- the writes
  //
  // A *plan* and a *write* are different operations. A plan writes
  // nothing, so it needs no authorisation -- refusing it would make
  // the tool useless, since the plan is how a caller finds out what a
  // write would do. The write takes an explicit request.
  //
  // So each install and uninstall has two rules: the `.plan` is
  // allowed outright, and the write is conditional on `apply`.
  {
    id: 'SL-1',
    operation: 'install.skills',
    verdict: 'conditional',
    reason:
      'Installing a skill writes into the harness directory, so it takes ' +
      'an explicit request to apply.',
    evidence: 'apply',
    hint: 'Pass apply=true to write the files.',
  },
  {
    id: 'SL-2',
    operation: 'install.agents',
    verdict: 'conditional',
    reason:
      'Installing an agent writes into the harness directory, so it takes ' +
      'an explicit request to apply.',
    evidence: 'apply',
    hint: 'Pass apply=true to write the files.',
  },
  {
    id: 'SL-4',
    operation: 'uninstall.skills',
    verdict: 'conditional',
    reason:
      'Uninstalling removes files from the harness directory, so it takes ' +
      'an explicit request to apply.',
    evidence: 'apply',
    hint: 'Pass apply=true to remove the files.',
  },
  {
    id: 'SL-8',
    operation: 'uninstall.agents',
    verdict: 'conditional',
    reason:
      'Uninstalling removes files from the harness directory, so it takes ' +
      'an explicit request to apply.',
    evidence: 'apply',
    hint: 'Pass apply=true to remove the files.',
  },

  // ------------------------------------------------------- the plans
  //
  // A plan writes nothing, so it is allowed outright. The rules are
  // here rather than implied, because "an operation with no rule is
  // refused" means a plan needs a rule of its own.
  {
    id: 'SL-11',
    operation: 'install.skills.plan',
    verdict: 'allow',
    reason:
      'A dry run writes nothing, so it needs no authorisation. It is how a ' +
      'caller finds out what a write would do.',
  },
  {
    id: 'SL-12',
    operation: 'install.agents.plan',
    verdict: 'allow',
    reason:
      'A dry run writes nothing, so it needs no authorisation. It is how a ' +
      'caller finds out what a write would do.',
  },
  {
    id: 'SL-13',
    operation: 'uninstall.skills.plan',
    verdict: 'allow',
    reason:
      'A dry run removes nothing, so it needs no authorisation. It is how a ' +
      'caller finds out what a removal would do.',
  },
  {
    id: 'SL-14',
    operation: 'uninstall.agents.plan',
    verdict: 'allow',
    reason:
      'A dry run removes nothing, so it needs no authorisation. It is how a ' +
      'caller finds out what a removal would do.',
  },

  // ------------------------------------------------------- the walls
  //
  // A wall guards an operation. Its `operation` is the operation it
  // protects -- the one the server evaluates -- and its `appliesWhen`
  // is the fact that makes it bite. So a wall is reached by asking
  // about the operation it guards, with the fact set; it is not
  // reached by asking about the wall itself.
  //
  // The fact is named exactly as the server works it out: a target
  // outside the whitelist is `outside_whitelist`, a target inside a
  // harness-managed directory is `harness_managed`, and so on.
  //
  // A wall may be a deny (it refuses outright) or a conditional (it
  // holds the operation until its evidence is supplied). SL-3 is the
  // latter: it applies only when the caller is about to replace
  // something that is already there.
  {
    id: 'SL-3',
    operation: 'install.skills',
    verdict: 'conditional',
    reason:
      'Overwriting replaces something that is already there, so it takes ' +
      'an explicit request.',
    evidence: 'overwrite',
    appliesWhen: 'overwrite_requested',
    hint: 'Pass overwrite=true to replace what is there.',
  },
  {
    id: 'SL-5',
    operation: 'install.skills',
    verdict: 'deny',
    reason:
      'The target path is outside the harness directories, so the write ' +
      'is refused.',
    appliesWhen: 'outside_whitelist',
    hint:
      'Install into one of the harness directories, or use the ' +
      'agentsmd harness with a path inside the project.',
  },
  {
    id: 'SL-6',
    operation: 'install.skills',
    verdict: 'deny',
    reason:
      'The target path is inside a directory the harness manages itself, ' +
      'so the write is refused.',
    appliesWhen: 'harness_managed',
    hint: 'Pick a target the harness does not own.',
  },
  {
    id: 'SL-7',
    operation: 'install.skills',
    verdict: 'deny',
    reason:
      'The symlink would point outside the library, so the write is ' +
      'refused.',
    appliesWhen: 'symlink_outward',
    hint: 'Install in copy mode, or fix the library path.',
  },
  {
    id: 'SL-9',
    operation: 'uninstall.agents',
    verdict: 'deny',
    reason:
      'The target is not a symlink this server made, so removing it could ' +
      'destroy something else.',
    appliesWhen: 'not_ours',
    hint: 'Remove it yourself if you are sure.',
  },
  {
    id: 'SL-10',
    operation: 'uninstall.agents',
    verdict: 'deny',
    reason:
      'The target path is outside the harness directories, so the removal ' +
      'is refused.',
    appliesWhen: 'outside_whitelist',
    hint: 'Remove it yourself if you are sure.',
  },
];

/**
 * The rules that govern one operation.
 *
 * A rule with an `appliesWhen` is a *wall*: it is decided by a fact
 * about the operation, not by the operation's name alone, and it is
 * evaluated in the wall pass. So it is excluded here -- a wall that
 * was also an operation rule would be evaluated twice, and once
 * without its fact.
 */
export function rulesFor(operation: string): Rule[] {
  return RULES.filter((r) => r.operation === operation && r.appliesWhen === undefined);
}

/** Every rule that has an `appliesWhen` -- the walls. */
export function wallRules(): Rule[] {
  return RULES.filter((r) => r.appliesWhen !== undefined);
}

/** The rule with this id, or `undefined`. */
export function findRule(id: string): Rule | undefined {
  return RULES.find((r) => r.id === id);
}
