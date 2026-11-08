#!/usr/bin/env python3
"""The two implementations must sort strings the same way.

Both servers order their results with the same tie-break, and both
report a `matched_on` list. If the two sort by different rules, one
server returns the same query's results in a different order than the
other -- and the user sees a different answer depending on which
implementation happened to be installed.

The rule is: **compare by unicode code point**. Python's `str`
comparison already does this, so the Python side gets it for free. The
TypeScript side does not: JS's `<` compares UTF-16 code units, and
UTF-16 orders the surrogate range (U+D800-U+DFFF) *below* U+E000-U+FFFF,
so an astral character and a high BMP character compare the wrong way
round. `codepointCompare` in `mcp/src/search.ts` fixes that
explicitly.

The interesting pairs are the astral ones. Library names are ASCII
today and the tokenizer only ever emits `[a-z0-9]` tokens, so this
cannot arise from a real search -- but a tie-break that silently
changes its ordering rule is the kind of thing that gets discovered a
year later, in a diff nobody reads. This test pins the rule.

A skip is not a pass: when the TypeScript build is missing the gate
compares nothing, and it exits non-zero saying INCOMPLETE rather than
PASS.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
PYTHON = sys.executable

sys.path.insert(0, os.path.join(MCP, 'python'))

from search import codepoint_compare  # noqa: E402

TS_ENTRY = os.path.join(MCP, 'dist', 'index.js')

failures = []
skips = []

# The pairs both implementations are driven over.
#
# The first group is ordinary ASCII -- the everyday case.
# The second group is where UTF-16 and code-point orderings differ:
# an astral character (U+1F600) against a high BMP character (U+FFFF).
# Under UTF-16 order the astral character sorts FIRST (its lead
# surrogate is 0xD83D, below 0xFFFF); under code-point order it sorts
# LAST (0x1F600 is above 0xFFFF).
#
# The third group is a direct check that the two implementations
# agree on where an astral character sits relative to an ordinary one.
PAIRS = [
    # Ordinary ASCII.
    ('a', 'b'),
    ('b', 'a'),
    ('a', 'a'),
    ('', 'a'),
    ('a', ''),
    ('', ''),
    ('abc', 'abd'),
    ('ab', 'abc'),
    # The case that separates UTF-16 order from code-point order.
    ('\U0001f600', '￿'),
    ('￿', '\U0001f600'),
    # Astral characters against ordinary ones.
    ('\U0001f600', 'a'),
    ('a', '\U0001f600'),
    ('\U0001f600', 'é'),
    # Two astral characters.
    ('\U0001f600', '\U0001f601'),
    ('\U0001f601', '\U0001f600'),
    # Astral characters at the edge of the range.
    ('\U00010000', '\U0001f600'),
    ('\U0001ffff', '\U00010000'),
]


def fail(msg):
    failures.append(msg)
    sys.stderr.write('FAIL: %s\n' % msg)


def ok(msg):
    sys.stdout.write('ok   %s\n' % msg)


def skip(msg):
    skips.append(msg)
    sys.stderr.write('SKIP: %s\n' % msg)


def ts_verdicts():
    """What the TypeScript implementation says about each pair."""
    script = os.path.join(HERE, '_ts_sort.mjs')
    proc = subprocess.run(
        ['node', script, json.dumps([list(p) for p in PAIRS])],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError('the TypeScript comparator failed:\n%s' % proc.stderr)
    return json.loads(proc.stdout)


def main():
    if not os.path.isfile(TS_ENTRY):
        skip('the TypeScript build is missing (%s). Run `npm run build` '
             'in mcp/ first.' % TS_ENTRY)
        sys.stderr.write('\nSORT PARITY: INCOMPLETE — the check did not '
                         'run.\n')
        return 1

    py = [codepoint_compare(a, b) for a, b in PAIRS]
    try:
        ts = ts_verdicts()
    except RuntimeError as e:
        fail(str(e))
        return 1

    mismatched = 0
    for (a, b), p, t in zip(PAIRS, py, ts):
        if p != t:
            fail('%r vs %r: python says %d, typescript says %d'
                 % (a, b, p, t))
            mismatched += 1
    if mismatched == 0:
        ok('the two implementations agree on all %d pairs' % len(PAIRS))

    # The comparator must actually be doing something. A comparator
    # that always returns 0 would agree with everything, including
    # itself, and this test would pass while the tie-break silently
    # stopped ordering anything.
    astral = codepoint_compare('\U0001f600', '￿')
    if astral != 1:
        fail('the code-point order is wrong: U+1F600 should sort after '
             'U+FFFF, got %d' % astral)
        mismatched += 1
    else:
        ok('the astral case orders by code point, not by UTF-16 code unit')

    if mismatched == 0:
        ok('the comparator discriminates: it is not always 0')

    if failures:
        sys.stderr.write('\n%d FAILURE(S)\n' % len(failures))
        return 1
    sys.stdout.write('\nSORT PARITY: PASS — the two implementations order '
                     'strings the same way\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
