#!/usr/bin/env python3
"""The documentation's numbers must match the library they describe.

The documents used to carry their own copies of the library's counts:
the task-table row count, the tier counts, the vocabulary size, the
ranking figures. They were prose, so nobody could tell they were
numbers, and they went stale -- the row count said 73 when the table
had 74, the vocabulary size was two hundred tokens out, and the
ranking figures were from a run before the corpus changed.

They are now filled in from the index when the documents are
rendered. This test is the other half of that: it checks that the
*rendered* documents agree with the library, so a stale number cannot
survive in the output even if the templates are edited by hand.

It also checks that the templates carry no leftover literal counts --
a number written directly into a template is a number that will go
stale, and it is the failure this whole arrangement exists to prevent.

The check is deliberately about *agreement*, not about specific
values. A test that asserted "the row count is 74" would itself go
stale the next time a row is added; a test that asserts "the row count
in the document equals the row count in the table" cannot.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
BASE = os.path.dirname(MCP)

sys.path.insert(0, os.path.join(MCP, 'build'))
sys.path.insert(0, os.path.join(MCP, 'python'))

from assemble_public import doc_counts  # noqa: E402

INDEX = os.path.join(MCP, 'data', 'index.json')

failures = []


def fail(msg):
    failures.append(msg)
    sys.stderr.write('FAIL: %s\n' % msg)


def ok(msg):
    sys.stdout.write('ok   %s\n' % msg)


# The rendered document and its template.
DOCS = [
    ('mcp/README.md', 'mcp/docs/templates/README.md.tpl'),
    ('mcp/docs/ARCHITECTURE.md', 'mcp/docs/templates/ARCHITECTURE.md.tpl'),
    ('mcp/docs/REGISTERING.md', 'mcp/docs/templates/REGISTERING.md.tpl'),
    ('mcp/docs/TOOL_REFERENCE.md', 'mcp/docs/templates/TOOL_REFERENCE.md.tpl'),
]

# The tokens the renderer fills in. A template that uses one of these
# gets the live value; a template that hardcodes a number instead is
# what this test exists to catch.
TOKENS = [
    '{n_skills}', '{n_agents}', '{n_total}', '{n_tier1}', '{n_tier2}',
    '{n_tier3}', '{n_skill_tier1}', '{n_skill_tier2}', '{n_skill_tier3}',
    '{n_tasks}', '{n_domains}', '{n_vocab}', '{n_noted_rows}',
    '{eval_rank1}', '{eval_top3}', '{eval_top10}', '{n_queries}',
]

# Literal counts in a template are the thing that goes stale. These
# are the shapes that mean "a number about the library".
#
# The patterns deliberately do NOT match every number: a template
# legitimately contains numbers that are not library facts -- a version
# number, a port number, a year, a percentage in an example payload.
# These match the specific shapes that were actually stale.
STALE_PATTERNS = [
    # "5,741 vocabulary tokens" / "all 5741 corpus"
    (r'\b\d{1,3},\d{3}\s+vocabulary tokens\b',
     'a hardcoded vocabulary size'),
    (r'\ball\s+\d{3,6}\s+corpus\b',
     'a hardcoded vocabulary size'),
    # "the 73-row task index", "73 rows"
    (r'\bthe\s+\d+-row\s+task(?:-type)?\s+index\b',
     'a hardcoded task-row count'),
    (r'\b\d+\s+rows\s+(?:of|list|name|named)\b',
     'a hardcoded task-row count'),
    (r'\b\d+\s+of\s+the\s+\d+\s+rows\b',
     'a hardcoded task-row count'),
    # "over 34 labelled queries"
    (r'\bover\s+\d+\s+labelled queries\b',
     'a hardcoded labelled-query count'),
    # "all 38 domains"
    (r'\ball\s+\d+\s+domains\b',
     'a hardcoded domain count'),
    # "rank 1    : 20 / 34"
    (r'rank\s*1\s*:\s*\d+\s*/\s*\d+',
     'a hardcoded ranking figure'),
    (r'rank\s*<=\s*3\s*:\s*\d+\s*/\s*\d+',
     'a hardcoded ranking figure'),
    (r'rank\s*<=\s*10\s*:\s*\d+\s*/\s*\d+',
     'a hardcoded ranking figure'),
]


def load_index():
    if not os.path.isfile(INDEX):
        return None
    with open(INDEX, encoding='utf-8') as fh:
        return json.load(fh)


def check_templates_have_no_literals():
    """A template must not carry a library count as a literal."""
    bad = 0
    for _rel, tpl_rel in DOCS:
        path = os.path.join(BASE, tpl_rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        for pattern, what in STALE_PATTERNS:
            for m in re.finditer(pattern, text):
                line = text.count('\n', 0, m.start()) + 1
                fail('%s:%d carries %s: %r\n'
                     '     Use the token instead -- the renderer fills it '
                     'from the index.' % (tpl_rel, line, what, m.group(0)))
                bad += 1
    if bad == 0:
        ok('no template carries a literal library count')


def check_templates_use_tokens():
    """Each template that quotes a count must use a token for it."""
    # Which token belongs to which fact, and a way to recognise the
    # fact in a rendered document.
    NEEDED = [
        ('{n_vocab}', r'\b\d{1,3}(?:,\d{3})?\s+vocabulary tokens\b'),
        ('{n_tasks}', r'\b\d+-row\s+task(?:-type)?\s+index\b'),
        ('{n_tasks}', r'\b\d+\s+of\s+the\s+\d+\s+rows\b'),
        ('{eval_rank1}', r'rank\s*1\s*:\s*\d+\s*/\s*\d+'),
    ]
    missing = 0
    for _rel, tpl_rel in DOCS:
        path = os.path.join(BASE, tpl_rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        for token, pattern in NEEDED:
            if token in text:
                continue
            # The token is not used here -- is the fact quoted at all?
            if re.search(pattern, text):
                fail('%s quotes a count but does not use %s'
                     % (tpl_rel, token))
                missing += 1
    if missing == 0:
        ok('every quoted count uses a token')


def check_rendered_matches(index):
    """The rendered documents must agree with the library."""
    subs = doc_counts(BASE)
    if subs is None:
        fail('the index is missing (%s); nothing could be checked'
             % INDEX)
        return
    if not subs:
        fail('no counts could be computed')
        return

    bad = 0
    for rel, tpl_rel in DOCS:
        path = os.path.join(BASE, rel)
        tpl_path = os.path.join(BASE, tpl_rel)
        if not os.path.isfile(path):
            continue
        if not os.path.isfile(tpl_path):
            continue
        with open(path, encoding='utf-8') as fh:
            rendered = fh.read()
        with open(tpl_path, encoding='utf-8') as fh:
            template = fh.read()

        # Render the template with the current counts, and require the
        # document to match. This is the whole check: if the document
        # on disk was not rendered from this template with these
        # counts, it is stale.
        expected = template
        for token, value in subs.items():
            expected = expected.replace(token, value)
        if rendered != expected:
            fail('%s does not match its template rendered with the '
                 'current counts.\n'
                 '     Run: python3 mcp/build/assemble_public.py'
                 % rel)
            bad += 1
    if bad == 0:
        ok('every rendered document matches the live counts')


def check_no_unfilled_tokens(index):
    """A rendered document must not still contain a token."""
    bad = 0
    for rel, _tpl_rel in DOCS:
        path = os.path.join(BASE, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        for token in TOKENS:
            if token in text:
                fail('%s still contains the unfilled token %s'
                     % (rel, token))
                bad += 1
    if bad == 0:
        ok('no rendered document contains an unfilled token')


def main():
    index = load_index()
    if index is None:
        fail('the index is missing (%s). Run scripts/rebuild.sh to build '
             'it.' % INDEX)
        return 1

    check_templates_have_no_literals()
    check_templates_use_tokens()
    check_rendered_matches(index)
    check_no_unfilled_tokens(index)

    if failures:
        sys.stderr.write('\n%d FAILURE(S)\n' % len(failures))
        return 1
    sys.stdout.write('\nDOC COUNTS: PASS — the documents quote the library, '
                     'not a memory of it\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
