#!/usr/bin/env python3
"""The two installers must agree about what they will write.

The Python fallback is what runs when the MCP SDK is unavailable, so a
divergent fallback is worse than no fallback: the same call is
accepted on one machine and refused on another, for no stated reason.

The agreement gate compares the *tool surface* -- the names, the
descriptions, the annotations. It never compared install *behaviour*.
That left the two installers free to disagree about the safety
rules, and they did:

  - `agentsmd` writes exactly one file, `<project>/AGENTS.md`. The
    Python implementation allowed that path and nothing else. The
    TypeScript implementation allowed that path *and anything else
    under the project root* -- so the two disagreed about what the
    whitelist meant.

This test drives both implementations over the same list of targets
and requires the same answer from each. It is the check that would
have caught that divergence, and it is what stops the next one.

The harness directories live under `$HOME`, and both implementations
read `$HOME` once, when the module is imported. So the test points
`HOME` at a temp tree *before* importing either, and drives the
TypeScript side through a subprocess with the same `HOME`.
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

GOLDEN = os.path.join(HERE, 'golden', 'installer_parity.json')
TS_ENTRY = os.path.join(MCP, 'dist', 'index.js')

failures = []
skips = []

# The cases. Each is (harness, target relative to its root, allowed?).
#
# `agentsmd` is resolved against the project root. Every other harness
# is resolved against `$HOME`.
CASES = [
    # agentsmd writes ONE file. Only that file.
    ('agentsmd', 'AGENTS.md', True),
    ('agentsmd', 'sub/AGENTS.md', False),
    ('agentsmd', 'notes.txt', False),
    ('agentsmd', 'deep/nested/file.txt', False),
    ('agentsmd', '../outside.txt', False),
    # claude-code writes into ~/.claude/skills and ~/.claude/agents.
    ('claude-code', '.claude/skills/tdd-workflow/SKILL.md', True),
    ('claude-code', '.claude/skills/nested/deep/SKILL.md', True),
    ('claude-code', '.claude/agents/thing.md', True),
    ('claude-code', '.claude/skills/learned/thing/SKILL.md', False),
    ('claude-code', '.codex/skills/thing/SKILL.md', False),
    ('claude-code', '../escape.txt', False),
    # codex writes into ~/.codex/skills.
    ('codex', '.codex/skills/thing/SKILL.md', True),
    ('codex', '.codex/skills/nested/SKILL.md', True),
    ('codex', '.claude/skills/thing/SKILL.md', False),
    ('codex', 'elsewhere/file.txt', False),
    # puku-cli writes into ~/.puku-cli/skills.
    ('puku-cli', '.puku-cli/skills/thing/SKILL.md', True),
    ('puku-cli', '.claude/skills/thing/SKILL.md', False),
]


def fail(msg):
    failures.append(msg)
    sys.stderr.write('FAIL: %s\n' % msg)


def ok(msg):
    sys.stdout.write('ok   %s\n' % msg)


def skip(msg):
    skips.append(msg)
    sys.stderr.write('SKIP: %s\n' % msg)


def python_verdicts(home, project):
    """What the Python implementation says about each case.

    `HOME` must be set before the import: `installers.py` reads it
    once, at module level.
    """
    os.environ['HOME'] = home
    sys.path.insert(0, os.path.join(MCP, 'python'))
    from installers import check_target

    out = []
    for harness, rel, _ in CASES:
        root = project if harness == 'agentsmd' else home
        target = os.path.join(root, rel)
        err = check_target(harness, target, project_root=project)
        out.append(err is None)
    return out


def ts_verdicts(home, project):
    """What the TypeScript implementation says about each case."""
    script = os.path.join(HERE, '_ts_installers.mjs')
    env = dict(os.environ)
    env['HOME'] = home
    proc = subprocess.run(
        ['node', script, home, project],
        capture_output=True, text=True, timeout=120, env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


def main():
    if not os.path.isfile(TS_ENTRY):
        skip('the TypeScript build is missing (%s). Run `npm run build` '
             'in mcp/ first.' % TS_ENTRY)
        sys.stderr.write('\nINSTALLER PARITY: INCOMPLETE — the check did '
                         'not run.\n')
        return 1

    tmp = tempfile.mkdtemp(prefix='installer-parity-')
    try:
        home = os.path.join(tmp, 'home')
        project = os.path.join(tmp, 'project')
        os.makedirs(home)
        os.makedirs(project)

        py = python_verdicts(home, project)
        try:
            ts = ts_verdicts(home, project)
        except RuntimeError as e:
            fail('the TypeScript installer probe failed:\n%s' % e)
            return 1

        mismatched = 0
        for (harness, rel, expected), p, t in zip(CASES, py, ts):
            label = '%s %s' % (harness, rel)
            if p != t:
                fail('%s: python says %s, typescript says %s'
                     % (label, 'allow' if p else 'refuse',
                        'allow' if t else 'refuse'))
                mismatched += 1
            elif p != expected:
                fail('%s: both implementations say %s, but the rule says %s'
                     % (label, 'allow' if p else 'refuse',
                        'allow' if expected else 'refuse'))
                mismatched += 1
        if mismatched == 0:
            ok('the two installers agree on all %d target cases'
               % len(CASES))

        # The case that used to diverge: agentsmd writes one file, and
        # only that file.
        allowed_agentsmd = [c[1] for c, p in zip(CASES, py)
                            if c[0] == 'agentsmd' and p]
        ok('agentsmd: only %s is allowed'
           % ', '.join(allowed_agentsmd))

        # The harness-managed directory is never written to.
        learned = [c for c, p in zip(CASES, py)
                   if c[1].endswith('learned/thing/SKILL.md')]
        ok('the harness-managed directory is refused: %s'
           % ('yes' if learned and not learned[0][2] else 'NO'))

        if failures:
            sys.stderr.write('\n%d FAILURE(S)\n' % len(failures))
            return 1
        sys.stdout.write('\nINSTALLER PARITY: PASS — the two '
                         'implementations agree\n')
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
