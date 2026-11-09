#!/usr/bin/env python3
"""Run every verification in one go. Exits non-zero if anything fails.

  1. .audit_find.py     ground-truth re-scan of the machine (find + PyYAML)
  2. .audit_agents.py   classify agent candidates; diff against the library
  3. .audit_sources.py  every recorded source still exists; copies match
  4. .audit_contents.py every supporting file copied completely
  5. .audit_guide.py    guide/report catalogue coverage and counts
  6. .verify_paths.py   every path referenced in the docs exists
  7. .verify_packs.py   the 6 packs + humanizer.zip are intact
  8. .audit_drift.py    the build tracks skills appearing/disappearing
  9. .audit_frontmatter.py  descriptions match the real YAML frontmatter
 10. mcp/tests/test_mcp.py       the MCP server, its tools and its safety rules
 11. mcp/tests/test_agreement.py the Python and TypeScript servers agree
 12. mcp/tests/test_jsonrpc.py   the protocol, against both servers
 13. mcp/scripts/eval_search.py  the ranking, against a labelled query set
 14. mcp/tests/test_skills_extension.py  the Skills extension, and its parity
 15. mcp/tests/test_policy.py   the policy layer, and its parity
 16. mcp/tests/test_provenance.py  the licence and redistribution verdict
 17. mcp/tests/test_search_rules.py  the search rules, one by one
 18. mcp/tests/test_filter_validation.py  the search filters are checked
 19. mcp/tests/test_postings.py  the postings cover every advertised field
 20. mcp/tests/test_bm25.py  the BM25 arm, and its parity with TypeScript
 21. mcp/tests/test_properties.py  the invariants every response must hold
 22. mcp/tests/test_task_table.py  the task table, row by row
 23. mcp/scripts/break_check_policy.sh  the policy gate can actually fail
 24. mcp/scripts/break_check_skills.sh  the Skills gate can actually fail
 25. mcp/scripts/break_check_provenance.sh  the provenance gate can actually fail
 26. mcp/scripts/break_check_search.sh  the search gate can actually fail
 27. mcp/scripts/break_check_filters.sh  the filter gate can actually fail
 28. mcp/scripts/break_check_postings.sh  the postings gate can actually fail
 29. mcp/scripts/break_check_bm25.sh  the BM25 gate can actually fail
 30. mcp/scripts/break_check_properties.sh  the property gate can actually fail
 31. mcp/scripts/break_check_task_table.sh  the task-table gate can actually fail

And, in addition: the protocol revision parity -- the two
implementations of the revision, compared directly.

The last eighteen need the MCP index. If `mcp/data/index.json` is missing
they are skipped with a message rather than failed -- a fresh clone
without a built index should not report a false failure -- but the
skipped steps are named in the output, so a green run never hides them.

The break-checks prove that the gates above can fail. Each one
breaks the code a gate guards and requires the gate to notice; a gate
that passes on broken code is not a gate.

**A skip is not a pass.** The exit code distinguishes two kinds of
skip. The machine-scanning steps are skipped *by design* in a published
tree -- there is no machine behind it -- and that is an expected skip.
Any other skip means a gate did not run: the index is missing, or the
TypeScript build is missing, or a step reported its own skip. Those
make the run INCOMPLETE, and the script exits non-zero saying so. A
verification that did not check the thing it claims to check must not
report success.
"""
import os
import subprocess
import sys

BASE = os.environ.get('SKILLS_LIBRARY_ROOT') or \
    os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

# A *published* tree is not the machine's library. Its content was
# assembled by copying, filtered by licence, and it has no upstream
# sources to re-scan and no packs at the top level. The steps that
# compare the library against the machine are meaningless there -- and
# the drift test is worse than meaningless: it runs the builder, which
# would scan the home directory and copy every skill on the machine,
# including the ones the licence filter deliberately excluded.
#
# So the machine-scanning steps are skipped in a published tree, and the
# skip is stated in the output rather than hidden.
PUBLISHED = os.path.isfile(os.path.join(BASE, 'CREDITS.md')) and \
    os.path.isfile(os.path.join(BASE, 'LICENSE'))

STEPS = [
    ('ground-truth scan', '.audit_find.py'),
    ('agent classification', '.audit_agents.py'),
    ('source integrity', '.audit_sources.py'),
    ('supporting files', '.audit_contents.py'),
    ('guide + report content', '.audit_guide.py'),
    ('path references', '.verify_paths.py'),
    ('standalone packs', '.verify_packs.py'),
    ('drift test', '.audit_drift.py'),
    ('frontmatter correctness', '.audit_frontmatter.py'),
    ('MCP server and tools', 'mcp/tests/test_mcp.py'),
    ('MCP cross-implementation', 'mcp/tests/test_agreement.py'),
    ('MCP installer parity', 'mcp/tests/test_installer_parity.py'),
    ('MCP sort parity', 'mcp/tests/test_sort_parity.py'),
    ('documentation counts', 'mcp/tests/test_doc_counts.py'),
    ('MCP protocol', 'mcp/tests/test_jsonrpc.py'),
    ('MCP protocol parity', 'mcp/tests/test_protocol_parity.py'),
    ('MCP skills extension', 'mcp/tests/test_skills_extension.py'),
    ('MCP policy layer', 'mcp/tests/test_policy.py'),
    ('MCP provenance', 'mcp/tests/test_provenance.py'),
    ('search rules', 'mcp/tests/test_search_rules.py'),
    ('filter validation', 'mcp/tests/test_filter_validation.py'),
    ('postings fields', 'mcp/tests/test_postings.py'),
    ('BM25 arm', 'mcp/tests/test_bm25.py'),
    ('response properties', 'mcp/tests/test_properties.py'),
    ('task table', 'mcp/tests/test_task_table.py'),
    ('search ranking', 'mcp/scripts/eval_search.py'),
    ('policy gate can fail', 'mcp/scripts/break_check_policy.sh'),
    ('Skills gate can fail', 'mcp/scripts/break_check_skills.sh'),
    ('provenance gate can fail', 'mcp/scripts/break_check_provenance.sh'),
    ('search gate can fail', 'mcp/scripts/break_check_search.sh'),
    ('filter gate can fail', 'mcp/scripts/break_check_filters.sh'),
    ('postings gate can fail', 'mcp/scripts/break_check_postings.sh'),
    ('BM25 gate can fail', 'mcp/scripts/break_check_bm25.sh'),
    ('property gate can fail', 'mcp/scripts/break_check_properties.sh'),
    ('task-table gate can fail', 'mcp/scripts/break_check_task_table.sh'),
    ('published tree in sync', 'mcp/tests/test_published_tree.py'),
]

# The steps that compare the library against the machine it was scanned
# from. They only make sense in the working library.
MACHINE_ONLY = {
    '.audit_find.py',
    '.audit_agents.py',
    '.audit_sources.py',
    '.audit_contents.py',
    '.audit_guide.py',
    '.verify_paths.py',
    '.verify_packs.py',
    '.audit_drift.py',
}

# The MCP steps need the index. Without it they would fail for a
# reason that has nothing to do with what they check.
NEEDS_INDEX = {
    'mcp/tests/test_mcp.py',
    'mcp/tests/test_agreement.py',
    'mcp/tests/test_installer_parity.py',
    'mcp/tests/test_sort_parity.py',
    'mcp/tests/test_doc_counts.py',
    'mcp/tests/test_jsonrpc.py',
    'mcp/tests/test_protocol_parity.py',
    'mcp/tests/test_skills_extension.py',
    'mcp/tests/test_policy.py',
    'mcp/tests/test_provenance.py',
    'mcp/tests/test_search_rules.py',
    'mcp/tests/test_filter_validation.py',
    'mcp/tests/test_postings.py',
    'mcp/tests/test_bm25.py',
    'mcp/tests/test_properties.py',
    'mcp/tests/test_task_table.py',
    'mcp/scripts/eval_search.py',
    # The break-checks run the policy and Skills gates, and both of
    # those need the index.
    'mcp/scripts/break_check_policy.sh',
    'mcp/scripts/break_check_skills.sh',
    'mcp/scripts/break_check_provenance.sh',
    'mcp/scripts/break_check_search.sh',
    'mcp/scripts/break_check_filters.sh',
    'mcp/scripts/break_check_postings.sh',
    'mcp/scripts/break_check_bm25.sh',
    'mcp/scripts/break_check_properties.sh',
    'mcp/scripts/break_check_task_table.sh',
}
INDEX = os.path.join(BASE, 'mcp', 'data', 'index.json')

failures = []
skipped = []
unexpected_skips = []
for label, script in STEPS:
    print('=' * 70)
    print('== %s   (%s)' % (label, script))
    print('=' * 70)
    if PUBLISHED and script in MACHINE_ONLY:
        print('SKIPPED: this is a published tree. The step compares the')
        print('library against the machine it was scanned from, and a')
        print('published tree has no machine behind it -- running the')
        print('builder here would copy the machine\'s skills in, including')
        print('the ones the licence filter excluded.')
        skipped.append(label)
        print()
        continue
    if script in NEEDS_INDEX and not os.path.isfile(INDEX):
        print('SKIPPED: %s not found. Run scripts/rebuild.sh to build it.'
              % INDEX)
        skipped.append(label)
        unexpected_skips.append(label)
        print()
        continue
    # A `.sh` step is a shell script; everything else is Python.
    argv = ['bash', script] if script.endswith('.sh') else [sys.executable, script]
    r = subprocess.run(argv, capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.stderr.strip():
        sys.stdout.write('--- stderr ---\n' + r.stderr[-1500:])
    if r.returncode != 0:
        failures.append(label)
    elif 'SKIP' in r.stdout:
        # A step that prints its own SKIP line has skipped rather than
        # passed. The cross-implementation gate does this when the
        # TypeScript build is missing, and the published-tree check does
        # it when there is no published tree. Either way the gate did
        # not run, and the run is not a pass.
        unexpected_skips.append(label)
    print()

print('=' * 70)
if skipped:
    print('SKIPPED STEPS: %s' % ', '.join(skipped))
if failures:
    print('FAILED STEPS: %s' % ', '.join(failures))
    sys.exit(1)

# A skip is not a pass, and not every skip is an expected one.
#
# The machine-only steps are skipped *by design* in a published tree --
# there is no machine behind it. That is an expected skip and the run
# is still a pass.
#
# The index-dependent steps are skipped when the index is missing. That
# is NOT expected: it means the gate did not run, and a run that did
# not test the thing it claims to test must not report success. The
# same is true of the cross-implementation gate, which skips when the
# TypeScript build is missing.
#
# So the exit code distinguishes the two, and the summary line says
# which happened. A green run with a hidden skip is exactly the
# failure mode this project already has once.
if unexpected_skips:
    print('UNEXPECTED SKIPS: %s' % ', '.join(unexpected_skips))
    print()
    print('These steps did not run. The verification is INCOMPLETE:')
    print('the thing they check was not checked. Build the index and')
    print('the TypeScript server, then run this again.')
    sys.exit(1)

if skipped:
    print('ALL %d VERIFICATION STEPS PASSED (%d expected skip(s): %s)'
          % (len(STEPS), len(skipped), ', '.join(skipped)))
else:
    print('ALL %d VERIFICATION STEPS PASSED' % len(STEPS))
