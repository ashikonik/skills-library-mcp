#!/usr/bin/env python3
"""The policy layer: what the server is allowed to do, and who says so.

This is the mirror of `mcp/src/policy.ts`. The two must agree exactly:
a client that talks to one server and then the other must not see a
different policy, and a rule id that means one thing in one
implementation must mean the same thing in the other.

The rules live in `policy_rules.py`; this file evaluates them.

**Three verdicts.** `allow`, `deny`, `conditional`. A conditional rule
holds the operation until the caller supplies the evidence it names --
and when it does, the verdict is still `conditional`, with
`satisfied: True`. A satisfied gate is not an allow: the caller learns
which gate opened, which is the thing worth knowing.

**A deny outranks a satisfied conditional.** A deny is a wall; a
satisfied conditional is only the absence of one. So the passes are
ordered: the denies first, then the conditionals, then the allow.

**An operation with no rule is refused**, as `SL-0`. A surface not in
the table is not an implicit yes.

**A project may only tighten.** `<project>/.skills-library/policy.json`
lists rule ids to deny. There is no way to write "allow" in it, so the
file cannot loosen anything -- and a malformed file is an error, not a
silent fall back to the defaults. A policy file that cannot be read
must not silently become no policy.
"""
import json
import os

from policy_rules import (ALLOW, CONDITIONAL, DENY, POLICY_DIR, POLICY_FILE,
                          POLICY_TTL_MS, RULES, find_rule, rules_for,
                          wall_rules)


def default_policy():
    """The built-in policy: every rule, at its own verdict."""
    return {
        'rules': {r['id']: {'verdict': r['verdict'], 'reason': r['reason']}
                  for r in RULES},
        'overrides': [],
        'source': 'default',
        'path': None,
    }


def verdict_of(policy, rule):
    """The effective verdict of a rule: the override, or the built-in."""
    entry = policy['rules'].get(rule['id'])
    return entry['verdict'] if entry else rule['verdict']


def _reason_of(policy, rule):
    entry = policy['rules'].get(rule['id'])
    if entry and entry.get('reason'):
        return entry['reason']
    return rule['reason']


def wall_applies(rule, ctx):
    """Does this wall apply to the operation?

    A wall is a deny rule with an `applies_when`. The fact it names is
    looked up in `ctx['args']` under exactly that name, and it must be
    literally `True`. Anything else -- absent, false, a truthy string
    -- means the wall does not apply.
    """
    if 'applies_when' not in rule:
        return True
    args = ctx.get('args') or {}
    return args.get(rule['applies_when']) is True


def evidence_present(rule, ctx):
    """Is a conditional rule's evidence present?

    The evidence is a comma-separated list of fact names. Each is
    looked up in `ctx['args']` and then at the top level of the
    context, and it must be exactly `True` -- the caller asked for the
    write, not merely mentioned it.
    """
    if 'evidence' not in rule:
        return True
    args = ctx.get('args') or {}
    for name in rule['evidence'].split(','):
        fact = name.strip()
        if not fact:
            continue
        value = args.get(fact, ctx.get(fact))
        if value is not True:
            return False
    return True


def evaluate(operation, ctx=None, policy=None):
    """Evaluate an operation against the policy.

    The passes are ordered: the walls, then the operation's own rules,
    then the allow. A deny is reported as soon as one applies, so it
    outranks a conditional that was satisfied.
    """
    ctx = ctx or {}
    policy = policy or default_policy()
    applicable = rules_for(operation)
    walls = wall_rules()

    # Pass 1: the walls. A deny is a wall, and it outranks everything.
    #
    # A wall can also be *conditional*: it applies under a fact, and
    # then holds the operation until its evidence is supplied. SL-3 is
    # one -- it applies when the caller is about to overwrite
    # something, and holds until they say they meant to.
    satisfied_wall = None
    for rule in walls:
        # A wall guards one operation. It is checked when that
        # operation is performed, not on every operation -- otherwise
        # two walls that share a fact (SL-5 and SL-10 both watch
        # `outside_whitelist`) would collide, and the one that happens
        # to come first in the table would fire for an operation it
        # has nothing to do with.
        if rule['operation'] != operation:
            continue
        verdict = verdict_of(policy, rule)
        if verdict not in (DENY, CONDITIONAL):
            continue
        if not wall_applies(rule, ctx):
            continue
        if verdict == DENY:
            return {
                'rule': rule['id'],
                'operation': operation,
                'verdict': DENY,
                'reason': _reason_of(policy, rule),
                'hint': rule.get('hint'),
            }
        # A conditional wall: it holds unless its evidence is present.
        if not evidence_present(rule, ctx):
            return {
                'rule': rule['id'],
                'operation': operation,
                'verdict': CONDITIONAL,
                'satisfied': False,
                'reason': _reason_of(policy, rule),
                'hint': rule.get('hint'),
            }
        if satisfied_wall is None:
            satisfied_wall = rule

    # Pass 2: the operation's own rules. An unsatisfied conditional
    # holds the operation.
    satisfied = None
    for rule in applicable:
        verdict = verdict_of(policy, rule)
        if verdict == DENY:
            return {
                'rule': rule['id'],
                'operation': operation,
                'verdict': DENY,
                'reason': _reason_of(policy, rule),
                'hint': rule.get('hint'),
            }
        if verdict != CONDITIONAL:
            continue
        if not evidence_present(rule, ctx):
            return {
                'rule': rule['id'],
                'operation': operation,
                'verdict': CONDITIONAL,
                'satisfied': False,
                'reason': _reason_of(policy, rule),
                'hint': rule.get('hint'),
            }
        if satisfied is None:
            satisfied = rule

    # Pass 3: the allow. A satisfied conditional wall is reported in
    # preference to the operation's own conditional, because it is the
    # more specific gate.
    if satisfied_wall is not None:
        satisfied = satisfied_wall
    if satisfied is not None:
        return {
            'rule': satisfied['id'],
            'operation': operation,
            'verdict': CONDITIONAL,
            'satisfied': True,
            'reason': _reason_of(policy, satisfied),
            'hint': satisfied.get('hint'),
        }
    if applicable:
        first = applicable[0]
        return {
            'rule': first['id'],
            'operation': operation,
            'verdict': ALLOW,
            'reason': _reason_of(policy, first),
        }

    # No rule covers the operation. That is a refusal, not an allow.
    return {
        'rule': 'SL-0',
        'operation': operation,
        'verdict': DENY,
        'reason': ("the operation '%s' is not covered by the policy table. This "
                   'is a bug in the server, not something the caller can work '
                   'around.' % operation),
        'hint': 'The operation should have a rule. Report it.',
    }


def permit(operation, ctx=None, policy=None):
    """The refusal an operation earns, or `None` when it may proceed.

    Every operation that touches the filesystem goes through this, so
    a rule a project tightened is a rule the server honours -- and the
    refusal names the rule that stopped it.
    """
    decision = evaluate(operation, ctx, policy)
    if decision['verdict'] == DENY:
        return decision
    if decision['verdict'] == CONDITIONAL and decision.get('satisfied') is False:
        return decision
    return None


def refusal_fields(decision):
    """The refusal fields, in the shape a tool result carries them."""
    return {
        'applied': False,
        'denied': decision['verdict'] == DENY,
        'gated': decision['verdict'] == CONDITIONAL,
        'rule': decision['rule'],
        'operation': decision['operation'],
        'reason': decision['reason'],
        'hint': decision.get('hint'),
    }


def may_tighten(rule):
    """Can a project tighten this rule to `deny`?

    Only tightening is possible: `allow` may become `deny`, `deny` and
    `conditional` may not become anything else.
    """
    return rule['verdict'] == ALLOW


def load_policy(project_root):
    """Read the project's policy file.

    A missing file is normal: the built-in policy applies. A malformed
    one is an error -- the file was written to say something, and
    ignoring it would make the server's behaviour depend on a typo.
    """
    path = os.path.join(project_root, POLICY_DIR, POLICY_FILE)
    base = default_policy()
    if not os.path.isfile(path):
        return base

    try:
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
    except OSError as e:
        raise ValueError(
            'cannot read %s: %s. Fix or move the file; the built-in defaults '
            'are not used, because a policy file that cannot be read must not '
            'silently become no policy.' % (path, e))

    try:
        parsed = json.loads(text)
    except ValueError as e:
        raise ValueError(
            'cannot parse %s as JSON: %s. Fix or move the file; the built-in '
            'defaults are not used, because a policy file that cannot be read '
            'must not silently become no policy.' % (path, e))

    if not isinstance(parsed, dict) or not isinstance(parsed.get('deny'), list):
        raise ValueError(
            '%s is malformed: it must be a JSON object with a "deny" array of '
            'rule ids. Fix or move the file; the built-in defaults are not '
            'used, because a policy file that cannot be read must not silently '
            'become no policy.' % path)

    policy = dict(base)
    policy['source'] = 'file'
    policy['path'] = path
    policy['overrides'] = []
    for rule_id in parsed['deny']:
        rule = find_rule(rule_id)
        if rule is None:
            raise ValueError(
                "%s denies unknown rule '%s'. The known rule ids are: %s"
                % (path, rule_id, ', '.join(r['id'] for r in RULES)))
        # A project may tighten any rule to `deny`. It may not loosen
        # one that is already `deny` or `conditional` -- the built-in
        # verdict is the floor, not the ceiling.
        policy['rules'][rule_id] = {'verdict': DENY, 'reason': rule['reason']}
        policy['overrides'].append(rule_id)
    return policy


def describe_policy(policy, error=None):
    """The effective policy, as the caller sees it.

    Every rule is reported -- its id, its operation, its effective
    verdict, why, and whether the project file tightened it -- so a
    caller can reason about what the server will do before it does it.
    """
    return {
        'policy_path': policy['path'],
        'source': policy['source'],
        'error': error,
        'overrides': list(policy['overrides']),
        'rules': [
            {
                'id': rule['id'],
                'operation': rule['operation'],
                'verdict': verdict_of(policy, rule),
                'reason': _reason_of(policy, rule),
                'evidence': rule.get('evidence'),
                'hint': rule.get('hint'),
                'overridden': rule['id'] in policy['overrides'],
            }
            for rule in RULES
        ],
    }
