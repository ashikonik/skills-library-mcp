#!/usr/bin/env python3
"""The policy layer must do what it claims, in both implementations.

A policy layer is only worth having if it actually stops things. This
test checks that it does, from four directions:

**The rules are data.** The table is read, and every rule has the
shape the evaluator assumes: an id, an operation, one of exactly three
verdicts, a reason, and either evidence or a wall.

**The verdicts are correct.** A deny refuses. A conditional holds
until the caller supplies the evidence it names. An allow proceeds.
And an operation with no rule is refused -- a surface not in the table
is not an implicit yes.

**A deny outranks a satisfied conditional.** This is the precedence
that matters: a conditional is only the absence of a deny, so a
satisfied gate cannot outrank a wall.

**A project may only tighten.** The policy file can deny a rule. It
cannot loosen one, it cannot invent a rule id, and a malformed file is
an error rather than a silent fall back to the defaults.

**Every rule is satisfiable.** This is the assertion that a refusal
test cannot make. A conditional rule whose evidence is never
recognised is off forever -- the operation is always held, and a test
that only checks "it refuses" cannot tell that gate from a broken
one. So every conditional rule is checked three ways: it is held by
an empty context, it opens when its evidence is supplied, and it is
reachable -- some operation actually exercises it.

The TypeScript implementation is checked against the same table, so a
rule that means one thing in one implementation and something else in
the other is caught.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
BASE = os.path.dirname(MCP)
PYTHON = sys.executable

TS_ENTRY = os.path.join(MCP, 'dist', 'index.js')

failures = []
skips = []
checks = []


def check(name, ok, detail=''):
    checks.append(name)
    if ok:
        sys.stdout.write('  ok   %s\n' % name)
    else:
        failures.append(name)
        sys.stdout.write('  FAIL %s\n' % name)
        if detail:
            sys.stdout.write('       %s\n' % detail)


def skip(msg):
    skips.append(msg)
    sys.stderr.write('SKIP: %s\n' % msg)


def load_python_modules():
    """Import the policy modules from the Python implementation."""
    sys.path.insert(0, os.path.join(MCP, 'python'))
    import policy
    import policy_rules
    return policy, policy_rules


# ---------------------------------------------------------------- the table

def test_rules_are_data(policy, rules):
    """Every rule has the shape the evaluator assumes."""
    check('the rule table is not empty', len(rules.RULES) > 0)

    allowed_verdicts = {rules.ALLOW, rules.DENY, rules.CONDITIONAL}
    ids = []
    for rule in rules.RULES:
        for field in ('id', 'operation', 'verdict', 'reason'):
            if not rule.get(field):
                check('rule %s has a %s' % (rule.get('id', '?'), field), False,
                      str(rule))
        check('rule %s has a known verdict' % rule.get('id'),
              rule.get('verdict') in allowed_verdicts,
              str(rule.get('verdict')))
        ids.append(rule.get('id'))

    check('every rule id is unique', len(ids) == len(set(ids)),
          '%d ids, %d unique' % (len(ids), len(set(ids))))

    # A rule is either gated on evidence, is a wall, or is an explicit
    # allow. A conditional with neither evidence nor a wall would be a
    # gate that could never open or close -- and the satisfiability
    # test below would catch it, but the table should say so here.
    for rule in rules.RULES:
        if rule['id'] == 'SL-0':
            continue
        if rule['verdict'] == rules.ALLOW:
            check('rule %s is an explicit allow with no evidence' % rule['id'],
                  not rule.get('evidence') and not rule.get('applies_when'),
                  str(rule))
            continue
        check('rule %s is gated or is a wall' % rule['id'],
              bool(rule.get('evidence')) or bool(rule.get('applies_when')),
              str(rule))

    # The walls are denies or conditionals -- both of them hold the
    # operation. A wall that was neither would be an allow that the
    # evaluator can never explain.
    for rule in rules.wall_rules():
        check('wall %s is a deny or a conditional' % rule['id'],
              rule['verdict'] in (rules.DENY, rules.CONDITIONAL), str(rule))


# -------------------------------------------------------------- the verdicts

def test_verdicts(policy, rules):
    """A deny refuses, a conditional holds, an allow proceeds."""
    # A deny. SL-0 covers an operation that is not in the table.
    decision = policy.evaluate('an.operation.that.does.not.exist', {})
    check('an operation with no rule is refused',
          decision['verdict'] == rules.DENY, str(decision))
    check('the refusal for an uncovered operation names SL-0',
          decision['rule'] == 'SL-0', str(decision))

    # A conditional, unsatisfied.
    decision = policy.evaluate('install.skills', {})
    check('a conditional is held without its evidence',
          decision['verdict'] == rules.CONDITIONAL, str(decision))
    check('an unsatisfied conditional says so',
          decision.get('satisfied') is False, str(decision))
    check('the held rule is SL-1',
          decision['rule'] == 'SL-1', str(decision))

    # The same conditional, satisfied. It is still a conditional: the
    # caller learns which gate opened, which is the thing worth knowing.
    decision = policy.evaluate('install.skills', {'apply': True})
    check('a satisfied conditional is still a conditional',
          decision['verdict'] == rules.CONDITIONAL, str(decision))
    check('a satisfied conditional says so',
          decision.get('satisfied') is True, str(decision))

    # `permit` is the gate the tools use: it returns the refusal, or
    # nothing.
    check('permit refuses a held operation',
          policy.permit('install.skills', {}) is not None)
    check('permit allows a satisfied operation',
          policy.permit('install.skills', {'apply': True}) is None)

    # The evidence must be *literally* true. A truthy string is not
    # the caller asking for the write.
    decision = policy.evaluate('install.skills', {'apply': 'yes'})
    check('a truthy-but-not-true evidence does not open the gate',
          decision.get('satisfied') is False, str(decision))


def test_precedence(policy, rules):
    """A deny outranks a satisfied conditional."""
    # SL-5 is a wall: it applies when the fact `outside_whitelist` is
    # true. SL-1 is a conditional on the same operation's family. Both
    # are present, the conditional is satisfied, and the wall still
    # wins.
    decision = policy.evaluate(
        'install.skills',
        {'apply': True, 'args': {'outside_whitelist': True}},
    )
    check('a deny outranks a satisfied conditional',
          decision['verdict'] == rules.DENY, str(decision))
    check('the wall is the rule that is reported',
          decision['rule'] == 'SL-5', str(decision))

    # The same context without the wall is a satisfied conditional.
    decision = policy.evaluate('install.skills', {'apply': True})
    check('without the wall the conditional opens',
          decision.get('satisfied') is True, str(decision))

    # A wall only applies when its fact is literally true.
    decision = policy.evaluate(
        'install.skills',
        {'apply': True, 'args': {'outside_whitelist': 'true'}},
    )
    check('a wall needs its fact to be literally true',
          decision.get('satisfied') is True, str(decision))


# ------------------------------------------------------- the policy file

def test_project_policy_file(policy, rules):
    """A project may tighten, and only tighten."""
    tmp = tempfile.mkdtemp(prefix='policy-file-')
    try:
        d = os.path.join(tmp, '.skills-library')
        os.makedirs(d)

        # No file: the built-in policy applies.
        p = policy.load_policy(tmp)
        check('a missing policy file is not an error',
              p['source'] == 'default' and not p['overrides'], str(p))

        # A deny. The rule becomes a deny.
        with open(os.path.join(d, 'policy.json'), 'w', encoding='utf-8') as fh:
            json.dump({'schema_version': 1, 'deny': ['SL-1']}, fh)
        p = policy.load_policy(tmp)
        check('a policy file is reported as the source',
              p['source'] == 'file', str(p['source']))
        check('the denied rule is an override',
              p['overrides'] == ['SL-1'], str(p['overrides']))
        decision = policy.evaluate('install.skills', {'apply': True}, p)
        check('a denied rule refuses even with its evidence',
              decision['verdict'] == rules.DENY, str(decision))
        check('the refusal names the denied rule',
              decision['rule'] == 'SL-1', str(decision))

        # A rule that is already a deny cannot be loosened. There is
        # no way to write "allow" in the file, so the file cannot
        # loosen anything.
        #
        # SL-5 is a *wall*: it refuses when its fact is present. A
        # project that denies it does not make the operation refuse
        # outright -- it makes the wall bite harder, which it already
        # did. So the wall still fires under its fact, and the
        # refusal still names it.
        with open(os.path.join(d, 'policy.json'), 'w', encoding='utf-8') as fh:
            json.dump({'schema_version': 1, 'deny': ['SL-5']}, fh)
        p = policy.load_policy(tmp)
        decision = policy.evaluate(
            'install.skills',
            {'apply': True, 'args': {'outside_whitelist': True}}, p)
        check('a wall denied by the project still refuses',
              decision['verdict'] == rules.DENY, str(decision))
        check('the refusal names the wall',
              decision['rule'] == 'SL-5', str(decision))
        check('the denied wall is reported as an override',
              p['overrides'] == ['SL-5'], str(p['overrides']))

        # An unknown rule id is an error: the file was written to say
        # something, and a typo must not be ignored.
        with open(os.path.join(d, 'policy.json'), 'w', encoding='utf-8') as fh:
            json.dump({'schema_version': 1, 'deny': ['SL-999']}, fh)
        try:
            policy.load_policy(tmp)
            check('an unknown rule id is an error', False, 'no error raised')
        except ValueError as e:
            check('an unknown rule id is an error', True)
            check('the error names the unknown rule', 'SL-999' in str(e), str(e))
        except Exception as e:
            # A crash is not the same thing as a refusal. The loader
            # must *say* what is wrong with the file, not fall over on
            # it -- a caller cannot act on a traceback.
            check('an unknown rule id is an error', False,
                  'raised %s, not a ValueError: %s' % (type(e).__name__, e))

        # A malformed file is an error, not a silent fall back.
        for label, text in [
            ('not JSON at all', 'this is not json'),
            ('JSON but not an object', '[1, 2, 3]'),
            ('an object without a deny array', '{"schema_version": 1}'),
            ('a deny that is not an array', '{"schema_version": 1, "deny": "SL-1"}'),
        ]:
            with open(os.path.join(d, 'policy.json'), 'w', encoding='utf-8') as fh:
                fh.write(text)
            try:
                policy.load_policy(tmp)
                check('a malformed policy file is an error (%s)' % label, False,
                      'no error raised')
            except ValueError as e:
                check('a malformed policy file is an error (%s)' % label, True)
                # The message has to say what is wrong. A loader that
                # raised for an unrelated reason -- a crash on a `None`
                # -- would satisfy "an error was raised" while telling
                # the caller nothing.
                check('the error explains the problem (%s)' % label,
                      ('malformed' in str(e) or 'parse' in str(e)
                       or 'cannot' in str(e)),
                      str(e))
            except Exception as e:
                check('a malformed policy file is an error (%s)' % label, False,
                      'raised %s, not a ValueError: %s' % (type(e).__name__, e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_describe(policy, rules):
    """The report says every rule, its verdict, and whether it was tightened."""
    p = policy.default_policy()
    report = policy.describe_policy(p)
    check('the report lists every rule',
          len(report['rules']) == len(rules.RULES),
          '%d listed, %d known' % (len(report['rules']), len(rules.RULES)))
    ids = [r['id'] for r in report['rules']]
    check('the report lists the rule ids',
          set(ids) == set(r['id'] for r in rules.RULES), str(ids))
    for entry in report['rules']:
        check('rule %s has a verdict in the report' % entry['id'],
              entry['verdict'] in (rules.ALLOW, rules.DENY, rules.CONDITIONAL),
              str(entry))
        check('rule %s has a reason in the report' % entry['id'],
              bool(entry['reason']), str(entry))
    check('the report says nothing was overridden',
          report['overrides'] == [], str(report['overrides']))


# ------------------------------------------------------- satisfiability

def test_satisfiable(policy, rules):
    """Every conditional rule must be reachable, holdable and openable.

    A conditional rule whose evidence is never recognised is off
    forever. A refusal test cannot tell that from a working gate --
    both refuse. So each conditional rule is checked three ways:

      1. It is *held* by a context that supplies none of its evidence.
      2. It *opens* when its evidence is supplied.
      3. It is *reachable*: some operation in the table actually
         exercises it, and the rule is the one that decides.
    """
    conditional_ops = [r['operation'] for r in rules.RULES
                       if r['verdict'] == rules.CONDITIONAL]
    check('there is at least one conditional rule',
          len(conditional_ops) > 0)

    for rule in rules.RULES:
        if rule['verdict'] != rules.CONDITIONAL:
            continue
        evidence = [f.strip() for f in rule['evidence'].split(',') if f.strip()]
        check('rule %s names its evidence' % rule['id'],
              len(evidence) > 0, str(rule))

        # A conditional *wall* only applies under its fact. The
        # evidence opens it once the fact is present.
        #
        # The context must also satisfy the operation's *own* gates --
        # an operation rule that is still held outranks a satisfied
        # wall, because the operation has not been allowed through yet.
        if 'applies_when' in rule:
            fact = rule['applies_when']
            ctx = {name: True for name in evidence}
            # Everything the operation's own rules ask for.
            for own in rules.rules_for(rule['operation']):
                if own['verdict'] != rules.CONDITIONAL:
                    continue
                for name in own['evidence'].split(','):
                    name = name.strip()
                    if name:
                        ctx[name] = True
            decision = policy.evaluate(rule['operation'],
                                       {'args': {fact: True}, **ctx})
            check('rule %s opens with its evidence' % rule['id'],
                  decision.get('satisfied') is True, str(decision))
            check('rule %s is the rule that opens it' % rule['id'],
                  decision['rule'] == rule['id'], str(decision))
            # Without its evidence, under the fact, it holds.
            decision = policy.evaluate(rule['operation'],
                                       {'args': {fact: True}})
            check('rule %s is held without its evidence' % rule['id'],
                  decision.get('satisfied') is False, str(decision))
            check('rule %s is the rule that holds it' % rule['id'],
                  decision['rule'] == rule['id'], str(decision))
            continue

        # 1. Held without the evidence.
        decision = policy.evaluate(rule['operation'], {})
        check('rule %s is held without its evidence' % rule['id'],
              decision.get('satisfied') is False, str(decision))
        check('rule %s is the rule that holds it' % rule['id'],
              decision['rule'] == rule['id'], str(decision))

        # 2. Opens with the evidence.
        ctx = {name: True for name in evidence}
        decision = policy.evaluate(rule['operation'], ctx)
        check('rule %s opens with its evidence' % rule['id'],
              decision.get('satisfied') is True, str(decision))
        check('rule %s is the rule that opens it' % rule['id'],
              decision['rule'] == rule['id'], str(decision))

        # 3. Reachable -- the rule is the one that decides, not a
        #    different rule that happens to fire first.
        check('rule %s is reachable' % rule['id'],
              decision['rule'] == rule['id'], str(decision))

    # Every operation that has a conditional rule must have one that
    # opens: otherwise the operation is permanently held, which is
    # not a gate but a wall wearing a gate's clothes.
    for op in sorted(set(conditional_ops)):
        opens = False
        for rule in rules.rules_for(op):
            if rule['verdict'] != rules.CONDITIONAL:
                continue
            evidence = [f.strip() for f in rule['evidence'].split(',') if f.strip()]
            ctx = {name: True for name in evidence}
            if 'applies_when' in rule:
                ctx = {**ctx, 'args': {rule['applies_when']: True}}
            decision = policy.evaluate(op, ctx)
            if decision.get('satisfied') is True and decision['rule'] == rule['id']:
                opens = True
        check('operation %s can be opened' % op, opens,
              'every conditional on it is unreachable')

    # A wall is a gate too: it must open once its evidence is there.
    for rule in rules.wall_rules():
        if rule['verdict'] != rules.CONDITIONAL:
            continue
        evidence = [f.strip() for f in rule.get('evidence', '').split(',')
                    if f.strip()]
        ctx = {name: True for name in evidence}
        for own in rules.rules_for(rule['operation']):
            if own['verdict'] != rules.CONDITIONAL:
                continue
            for name in own['evidence'].split(','):
                name = name.strip()
                if name:
                    ctx[name] = True
        decision = policy.evaluate(rule['operation'],
                                   {'args': {rule['applies_when']: True}, **ctx})
        check('wall %s can be opened' % rule['id'],
              decision.get('satisfied') is True
              and decision['rule'] == rule['id'], str(decision))


def test_walls_are_reachable(policy, rules):
    """Every wall must be triggerable by its fact.

    A wall guards an operation, so it is reached by asking about the
    operation it protects with the fact set -- not by asking about
    the wall itself.
    """
    for rule in rules.wall_rules():
        fact = rule['applies_when']
        evidence = [f.strip() for f in rule.get('evidence', '').split(',')
                    if f.strip()]
        ctx = {name: True for name in evidence}
        # The operation's own gates must be open too, or the operation
        # is held by them rather than by the wall.
        for own in rules.rules_for(rule['operation']):
            if own['verdict'] != rules.CONDITIONAL:
                continue
            for name in own['evidence'].split(','):
                name = name.strip()
                if name:
                    ctx[name] = True
        decision = policy.evaluate(
            rule['operation'], {'args': {fact: True}, **ctx})
        if rule['verdict'] == rules.DENY:
            check('wall %s fires when its fact is true' % rule['id'],
                  decision['verdict'] == rules.DENY
                  and decision['rule'] == rule['id'], str(decision))
        else:
            # A conditional wall holds until its evidence is present.
            decision = policy.evaluate(
                rule['operation'], {'args': {fact: True}})
            check('wall %s holds when its fact is true' % rule['id'],
                  decision['verdict'] == rules.CONDITIONAL
                  and decision.get('satisfied') is False, str(decision))
            decision = policy.evaluate(
                rule['operation'], {'args': {fact: True}, **ctx})
            check('wall %s opens with its evidence' % rule['id'],
                  decision.get('satisfied') is True, str(decision))
            check('wall %s is the rule that opens it' % rule['id'],
                  decision['rule'] == rule['id'], str(decision))

        # And it must not fire when the fact is absent.
        decision = policy.evaluate(rule['operation'], {'args': {}})
        check('wall %s does not fire without its fact' % rule['id'],
              decision['rule'] != rule['id'], str(decision))

        # The wall's operation must be one the server actually
        # evaluates -- a wall on an operation nothing performs is a
        # wall that can never protect anything.
        check('wall %s guards a real operation' % rule['id'],
              rule['operation'] in ('install.skills', 'install.agents',
                                     'uninstall.skills', 'uninstall.agents'),
              rule['operation'])


# ------------------------------------------------------- the tool surface

def test_tool_surface(policy, rules):
    """The tools refuse through the policy, and say which rule stopped them."""
    sys.path.insert(0, os.path.join(MCP, 'python'))
    import server as pyserver

    tmp = tempfile.mkdtemp(prefix='policy-tools-')
    try:
        os.environ['SKILLS_LIBRARY_PROJECT'] = tmp
        srv = pyserver.Server()

        # The policy report.
        report = srv.call_tool('policy_get', {})
        check('policy_get reports the rules',
              len(report['rules']) == len(rules.RULES), str(len(report['rules'])))
        check('policy_get reports the policy path',
              report['policy_path'] is None, str(report['policy_path']))

        # A dry run writes nothing, so it is allowed. Refusing it
        # would make the tool useless: the plan is how a caller finds
        # out what a write would do.
        result = srv.call_tool('install_skills', {'harness': 'puku-cli',
                                                  'ids': ['skill:does-not-exist']})
        check('a dry run is not held by the policy',
              result.get('gated') is not True, str(result)[:300])
        check('a dry run reports its targets',
              'targets' in result, str(result)[:300])

        # An uninstall dry run is allowed too.
        result = srv.call_tool('uninstall_skills', {'harness': 'puku-cli',
                                                    'names': ['x']})
        check('an uninstall dry run is not held by the policy',
              result.get('gated') is not True, str(result)[:300])

        # An agent uninstall dry run.
        result = srv.call_tool('uninstall_agents', {'harness': 'claude-code',
                                                     'names': ['x']})
        check('an agent uninstall dry run is not held by the policy',
              result.get('gated') is not True, str(result)[:300])

        # With apply, the operation proceeds and the *targets* are
        # refused by the walls instead.
        result = srv.call_tool('install_skills', {'harness': 'puku-cli',
                                                  'ids': ['skill:does-not-exist'],
                                                  'apply': True})
        check('an install with apply is not held',
              result.get('gated') is not True, str(result)[:300])

        # A project policy that denies SL-1 stops the *write*. The
        # plan is a different operation, so it still works -- which is
        # what a caller needs: to see what the write would do.
        d = os.path.join(tmp, '.skills-library')
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'policy.json'), 'w', encoding='utf-8') as fh:
            json.dump({'schema_version': 1, 'deny': ['SL-1']}, fh)
        srv2 = pyserver.Server()
        result = srv2.call_tool('install_skills', {'harness': 'puku-cli',
                                                   'ids': ['skill:does-not-exist'],
                                                   'apply': True})
        check('a project policy that denies SL-1 stops the write',
              result.get('denied') is True, str(result)[:300])
        check('the refusal names SL-1',
              result.get('rule') == 'SL-1', str(result)[:300])

        # The plan is still allowed.
        result = srv2.call_tool('install_skills', {'harness': 'puku-cli',
                                                   'ids': ['skill:does-not-exist']})
        check('a project policy that denies SL-1 does not stop the plan',
              result.get('denied') is not True, str(result)[:300])

        # The report says the rule was tightened.
        report = srv2.call_tool('policy_get', {})
        check('the report says SL-1 was tightened by the project',
              report['overrides'] == ['SL-1'], str(report['overrides']))
        entry = [r for r in report['rules'] if r['id'] == 'SL-1'][0]
        check('the tightened rule is reported as a deny',
              entry['verdict'] == 'deny', str(entry))
        check('the tightened rule is marked overridden',
              entry['overridden'] is True, str(entry))
    finally:
        os.environ.pop('SKILLS_LIBRARY_PROJECT', None)
        shutil.rmtree(tmp, ignore_errors=True)


def test_malformed_policy_file_is_reported():
    """A policy file that cannot be read is reported, not ignored."""
    sys.path.insert(0, os.path.join(MCP, 'python'))
    import server as pyserver

    tmp = tempfile.mkdtemp(prefix='policy-malformed-')
    try:
        d = os.path.join(tmp, '.skills-library')
        os.makedirs(d)
        with open(os.path.join(d, 'policy.json'), 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        os.environ['SKILLS_LIBRARY_PROJECT'] = tmp
        srv = pyserver.Server()
        report = srv.call_tool('policy_get', {})
        check('a malformed policy file is reported as an error',
              bool(report.get('error')), str(report.get('error'))[:200])
        check('the malformed policy file falls back to the defaults',
              report['source'] == 'default', str(report['source']))
    finally:
        os.environ.pop('SKILLS_LIBRARY_PROJECT', None)
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------ the manifest

def test_manifest():
    """The manifest records what was written, and only that."""
    sys.path.insert(0, os.path.join(MCP, 'python'))
    import manifest

    tmp = tempfile.mkdtemp(prefix='manifest-')
    try:
        records, error = manifest.load_manifest(tmp)
        check('a missing manifest reads as empty',
              records == [] and error is None, '%s %s' % (records, error))

        manifest.record_install(tmp, 'claude-code', 'agent', 'x',
                                '/tmp/x.md', 'write')
        records, error = manifest.load_manifest(tmp)
        check('a write is recorded',
              len(records) == 1 and records[0]['name'] == 'x',
              str(records))
        check('the record says where it went',
              records[0]['path'] == '/tmp/x.md', str(records[0]))

        # Writing the same path twice replaces the record rather than
        # duplicating it.
        manifest.record_install(tmp, 'claude-code', 'agent', 'x',
                                '/tmp/x.md', 'write')
        records, _ = manifest.load_manifest(tmp)
        check('the same path is recorded once',
              len(records) == 1, str(records))

        # The records are filtered by harness and kind.
        manifest.record_install(tmp, 'opencode', 'agent', 'y',
                                '/tmp/y.md', 'write')
        manifest.record_install(tmp, 'claude-code', 'skill', 'z',
                                '/tmp/z/SKILL.md', 'symlink')
        records, _ = manifest.records_for(tmp, 'claude-code', 'agent')
        check('the records are filtered by harness and kind',
              len(records) == 1 and records[0]['name'] == 'x', str(records))

        # A malformed manifest is reported, not silently read as empty.
        d = os.path.join(tmp, '.skills-library')
        with open(os.path.join(d, 'installs.json'), 'w', encoding='utf-8') as fh:
            fh.write('not json')
        records, error = manifest.load_manifest(tmp)
        check('a malformed manifest is reported',
              records == [] and bool(error), '%s %s' % (records, error))

        # A manifest without an installs array is malformed too.
        with open(os.path.join(d, 'installs.json'), 'w', encoding='utf-8') as fh:
            fh.write('{"schema_version": 1}')
        records, error = manifest.load_manifest(tmp)
        check('a manifest without an installs array is reported',
              records == [] and bool(error), '%s %s' % (records, error))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_uninstall_agents_refuses_foreign_files():
    """A file this server did not write is refused, not removed."""
    sys.path.insert(0, os.path.join(MCP, 'python'))
    import installers
    import manifest
    import server as pyserver

    tmp = tempfile.mkdtemp(prefix='uninstall-agents-')
    home = os.path.join(tmp, 'home')
    project = os.path.join(tmp, 'project')
    os.makedirs(os.path.join(home, '.claude', 'agents'))
    os.makedirs(project)
    try:
        # Point the installer at the temp home.
        original = dict(installers.TARGET_DIRS)
        installers.TARGET_DIRS['claude-code'] = [
            os.path.join(home, '.claude', 'skills'),
            os.path.join(home, '.claude', 'agents'),
        ]
        os.environ['SKILLS_LIBRARY_PROJECT'] = project
        srv = pyserver.Server()

        # A file this server did not write.
        foreign = os.path.join(home, '.claude', 'agents', 'someone-elses.md')
        with open(foreign, 'w', encoding='utf-8') as fh:
            fh.write('# not ours\n')

        result = srv.call_tool('uninstall_agents', {
            'harness': 'claude-code', 'names': ['someone-elses'], 'apply': True})
        check('a foreign file is refused',
              result['targets'][0]['status'] == 'error', str(result)[:300])
        check('the refusal names the not_ours wall',
              result['targets'][0].get('wall') == 'not_ours',
              str(result['targets'][0])[:300])
        check('the foreign file is still there',
              os.path.isfile(foreign))

        # A file the manifest says we wrote is removed.
        manifest.record_install(project, 'claude-code', 'agent', 'ours',
                                foreign, 'write')
        result = srv.call_tool('uninstall_agents', {
            'harness': 'claude-code', 'names': ['someone-elses'], 'apply': True})
        check('a file the manifest records is removed',
              result['targets'][0]['status'] == 'removed', str(result)[:300])
        check('the file is gone', not os.path.exists(foreign))
        records, _ = manifest.load_manifest(project)
        check('the manifest forgets the removed file',
              not any(r['path'] == foreign for r in records), str(records))
    finally:
        installers.TARGET_DIRS.clear()
        installers.TARGET_DIRS.update(original)
        os.environ.pop('SKILLS_LIBRARY_PROJECT', None)
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------- the TS mirror

def _python_policy_file_effects(policy, rules):
    """The Python loader's answer to the same policy-file cases.

    The labels match the ones `_ts_policy.mjs` reports, so the two
    can be compared case for case. The reported *effect* is what
    matters -- the verdict a caller would get, and whether the loader
    refused the file -- not the loader's internal shape.
    """
    tmp = tempfile.mkdtemp(prefix='policy-effect-')
    effects = {}
    try:
        d = os.path.join(tmp, '.skills-library')
        os.makedirs(d)
        path = os.path.join(d, 'policy.json')

        # No file: the built-in policy applies.
        p = policy.load_policy(tmp)
        effects['missing file'] = {'source': p['source'],
                                   'overrides': len(p['overrides'])}

        # A deny tightens the rule.
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'schema_version': 1, 'deny': ['SL-1']}, fh)
        p = policy.load_policy(tmp)
        decision = policy.evaluate('install.skills', {'apply': True}, p)
        effects['deny SL-1'] = {'source': p['source'],
                                'overrides': list(p['overrides']),
                                'rule': decision['rule'],
                                'verdict': decision['verdict']}

        # A malformed file is an error, not a silent fall back.
        for label, text in [
            ('not JSON at all', 'this is not json'),
            ('JSON but not an object', '[1, 2, 3]'),
            ('an object without a deny array', '{"schema_version": 1}'),
            ('a deny that is not an array', '{"schema_version": 1, "deny": "SL-1"}'),
        ]:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(text)
            try:
                policy.load_policy(tmp)
                effects['malformed: %s' % label] = {'error': None,
                                                     'errorName': None}
            except ValueError as e:
                effects['malformed: %s' % label] = {'error': str(e),
                                                     'errorName': 'ValueError'}
            except Exception as e:
                effects['malformed: %s' % label] = {
                    'error': str(e), 'errorName': type(e).__name__}

        # An unknown rule id is an error.
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'schema_version': 1, 'deny': ['SL-999']}, fh)
        try:
            policy.load_policy(tmp)
            effects['unknown rule id'] = {'error': None, 'errorName': None}
        except ValueError as e:
            effects['unknown rule id'] = {'error': str(e), 'errorName': 'ValueError'}
        except Exception as e:
            effects['unknown rule id'] = {'error': str(e),
                                          'errorName': type(e).__name__}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return effects


def test_typescript_agrees():
    """The TypeScript implementation must report the same table."""
    if not os.path.isfile(TS_ENTRY):
        skip('the TypeScript build is missing (%s). Run `npm run build` in '
             'mcp/ first.' % TS_ENTRY)
        return

    script = os.path.join(HERE, '_ts_policy.mjs')
    proc = subprocess.run(['node', script], capture_output=True, text=True,
                          timeout=120)
    if proc.returncode != 0:
        check('the TypeScript policy module runs', False, proc.stderr[-500:])
        return
    ts = json.loads(proc.stdout)

    policy, rules = load_python_modules()

    # The rule table must be the same, id for id.
    py_ids = [r['id'] for r in rules.RULES]
    check('the TypeScript rule table has the same ids',
          ts['ids'] == py_ids,
          'TS: %s\nPY: %s' % (ts['ids'], py_ids))

    py_verdicts = {r['id']: r['verdict'] for r in rules.RULES}
    check('the TypeScript verdicts match',
          ts['verdicts'] == py_verdicts,
          'TS: %s\nPY: %s' % (ts['verdicts'], py_verdicts))

    py_evidence = {r['id']: r.get('evidence') for r in rules.RULES}
    check('the TypeScript evidence matches',
          ts['evidence'] == py_evidence,
          'TS: %s\nPY: %s' % (ts['evidence'], py_evidence))

    py_walls = {r['id']: r.get('applies_when') for r in rules.RULES
                if r.get('applies_when')}
    check('the TypeScript walls match',
          ts['walls'] == py_walls,
          'TS: %s\nPY: %s' % (ts['walls'], py_walls))

    # The decisions must match, for a set of contexts.
    for case in ts['cases']:
        operation = case['operation']
        ctx = case['context']
        py_ctx = dict(ctx)
        py_args = py_ctx.pop('args', {})
        py_ctx['args'] = py_args
        decision = policy.evaluate(operation, py_ctx)
        check('the TypeScript decision matches for %s' % operation,
              case['verdict'] == decision['verdict']
              and case['rule'] == decision['rule']
              and case['satisfied'] == decision.get('satisfied', None),
              'TS: %s/%s (satisfied=%s)  PY: %s/%s (satisfied=%s)  ctx=%s'
              % (case['rule'], case['verdict'], case['satisfied'],
                 decision['rule'], decision['verdict'],
                 decision.get('satisfied'), json.dumps(ctx)))

    # The project policy file must behave the same in both
    # implementations: the same file must tighten the same rule, and
    # the same malformed file must be refused by both.
    #
    # The Python loader is exercised directly in
    # `test_project_policy_file`; this compares the two *effects*, so
    # a loader that quietly loosened a rule, or that ignored a
    # malformed file, would show up as a disagreement.
    py_file_effects = _python_policy_file_effects(policy, rules)
    for case in ts.get('fileCases', []):
        label = case['label']
        py = py_file_effects.get(label)
        check('the TypeScript reports the policy-file case %r' % label,
              py is not None, 'no Python counterpart')
        if py is None:
            continue
        if case['expect'] == 'error':
            check('the TypeScript refuses the policy file %r' % label,
                  case['got'].get('error') is not None, str(case['got']))
            check('the Python refuses the policy file %r' % label,
                  py.get('error') is not None, str(py))
            check('both refuse the policy file %r' % label,
                  (case['got'].get('error') is None) == (py.get('error') is None),
                  'TS: %s  PY: %s' % (case['got'], py))
            # A crash is not a refusal. The loader must say what is
            # wrong with the file; falling over on a `None` tells the
            # caller nothing, and the two implementations would then
            # "agree" only in that both fell over.
            check('the TypeScript refuses with an explanation, not a crash (%r)' % label,
                  case['got'].get('errorName') == 'Error',
                  'error name: %r  message: %r'
                  % (case['got'].get('errorName'), case['got'].get('error')))
            check('the Python refuses with an explanation, not a crash (%r)' % label,
                  py.get('errorName') == 'ValueError',
                  'error name: %r  message: %r'
                  % (py.get('errorName'), py.get('error')))
            # And the message has to say what is wrong.
            for side, got in (('TypeScript', case['got']), ('Python', py)):
                msg = (got.get('error') or '')
                check('the %s explains the problem (%r)' % (side, label),
                      ('malformed' in msg or 'parse' in msg
                       or 'cannot' in msg or 'unknown rule' in msg),
                      msg)
        else:
            check('the TypeScript and Python agree on the policy file %r' % label,
                  case['got'] == py,
                  'TS: %s\nPY: %s' % (json.dumps(case['got']), json.dumps(py)))


def main():
    if not os.path.isfile(os.path.join(MCP, 'data', 'index.json')):
        skip('the index is missing. Run `python3 build/build_index.py` first.')
        sys.stderr.write('\nPOLICY: INCOMPLETE — the check did not run.\n')
        return 1

    policy, rules = load_python_modules()

    print('the rule table')
    test_rules_are_data(policy, rules)

    print('\nthe verdicts')
    test_verdicts(policy, rules)

    print('\nprecedence')
    test_precedence(policy, rules)

    print('\nthe project policy file')
    test_project_policy_file(policy, rules)

    print('\nthe report')
    test_describe(policy, rules)

    print('\nsatisfiability')
    test_satisfiable(policy, rules)

    print('\nwall reachability')
    test_walls_are_reachable(policy, rules)

    print('\nthe tool surface')
    test_tool_surface(policy, rules)

    print('\na malformed policy file')
    test_malformed_policy_file_is_reported()

    print('\nthe manifest')
    test_manifest()

    print('\nuninstall_agents')
    test_uninstall_agents_refuses_foreign_files()

    print('\nthe TypeScript mirror')
    test_typescript_agrees()

    print('\n%d checks, %d failures, %d skips'
          % (len(checks), len(failures), len(skips)))
    if failures:
        sys.stderr.write('\nPOLICY: FAIL -- %d failing checks:\n' % len(failures))
        for f in failures:
            sys.stderr.write('  - %s\n' % f)
        return 1
    sys.stdout.write('\nPOLICY: PASS\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
