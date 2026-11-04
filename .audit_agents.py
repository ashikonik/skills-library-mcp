#!/usr/bin/env python3
"""Classify every agent candidate the ground-truth scan found, and check that
the built library contains exactly the right ones.

The ground-truth scanner is deliberately over-inclusive (any .md with a
frontmatter `name:`). This script decides, for each candidate, whether it
is a real standalone agent or one of:
  - a skill-internal reference doc
  - a slash command
  - a per-project memory file
  - a GitHub issue template
  - a non-agent markdown doc that happens to carry `name:`
and then compares that verdict against the built library.
"""
import os
import json
import re
import sys

BASE = os.environ.get('SKILLS_LIBRARY_ROOT') or \
    os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

gt = json.load(open('/tmp/ground_truth.json'))
lib = json.load(open('.library_data.json'))

lib_agents = {a['name'] for a in lib['agents']}
held = {e['name'] for e in lib['excluded_agents']}
lib_all = lib_agents | held
lib_skills = {s['name'] for s in lib['skills']}

COMPANION = {'references', 'rules', 'examples', 'templates', 'assets', 'docs'}
# Documentation files that are not agents, whatever they contain.
NOT_AGENT_NAMES = {'readme', 'index', 'overview', 'changelog', 'contributing',
                    'license', 'code_of_conduct', 'security', 'authors',
                    'notice', 'history', 'todo', 'faq'}


def normalise(name, paths):
    """Match the builder's naming: strip a trailing `.agent` from the stem
    when the file has no frontmatter `name:`."""
    if name in NOT_AGENT_NAMES:
        return None
    p = paths[0]
    fm_text = open(p, encoding='utf-8', errors='replace').read()
    has_name = False
    if fm_text.startswith('---'):
        end = fm_text.find('\n---', 3)
        if end != -1:
            has_name = re.search(r'^name:', fm_text[3:end], re.M) is not None
    if not has_name and name.endswith('.agent'):
        return name[:-6]
    return name


def verdict(name, paths):
    """Classify an agent candidate using only structural facts."""
    p = paths[0]
    rel = os.path.relpath(p, os.path.expanduser('~'))
    parts = rel.split(os.sep)
    text = open(p, encoding='utf-8', errors='replace').read()
    fm_text = text[3:text.find('\n---', 3)] if text.startswith('---') else ''

    # Documentation files are never agents, whatever directory they sit in.
    if os.path.basename(p).lower() in ('readme.md', 'index.md', 'overview.md',
                                      'changelog.md', 'contributing.md',
                                      'license.md', 'code_of_conduct.md'):
        return 'doc-file'
    if 'ISSUE_TEMPLATE' in parts:
        return 'issue-template'
    if os.path.basename(os.path.dirname(p)) == 'commands':
        return 'command-dir'
    if os.path.basename(os.path.dirname(p)) == 'memory':
        return 'memory-dir'
    if re.search(r'^command:\s*true', fm_text, re.M):
        return 'command-flag'
    if re.search(r'^agent:\s*\S', fm_text, re.M):
        return 'command-routes-to-agent'
    if re.search(r'^node_type:\s*memory', fm_text, re.M):
        return 'memory-node'
    if COMPANION & set(parts):
        return 'skill-reference-doc'
    if os.path.basename(os.path.dirname(p)) == 'agents':
        return 'AGENT'
    # declares itself a sub-agent
    if re.search(r'^agents:\s*\[', fm_text, re.M) or \
       re.search(r'^agents:\s*$', fm_text, re.M) or \
       re.search(r'^handoffs:\s*$', fm_text, re.M) or \
       re.search(r'^target:\s*\S', fm_text, re.M):
        return 'AGENT'
    return 'unknown-md'


rows = []
for name, paths in sorted(gt['agents'].items()):
    v = verdict(name, paths)
    nm = normalise(name, paths)
    if nm is None:
        continue
    rows.append((v, nm, os.path.relpath(paths[0], os.path.expanduser('~'))))

from collections import Counter
counts = Counter(v for v, _, _ in rows)
print('=== ground-truth agent candidates by verdict ===')
for v, c in counts.most_common():
    print('  %-26s %4d' % (v, c))
print('  %-26s %4d' % ('TOTAL', len(rows)))
print()

should_be = {n for v, n, _ in rows if v == 'AGENT'}
unknown = [(n, p) for v, n, p in rows if v == 'unknown-md']
gt_names = {n for _, n, _ in rows}

print('=== library vs verdict ===')
missing = sorted(should_be - lib_all)
extra = sorted(lib_all - gt_names)
print('agents library has that are NOT ground-truth candidates:', extra)
print('agents the verdict says ARE agents but library lacks   :', missing)
print()

# where do the library agents sit by verdict?
in_lib = [(v, n) for v, n, _ in rows if n in lib_all]
not_in_lib = [(v, n) for v, n, _ in rows if n not in lib_all]
print('library agents by verdict   :', Counter(v for v, _ in in_lib))
print('excluded-by-verdict (not in library):', Counter(v for v, _ in not_in_lib))
print()

# the two remaining 'unknown-md' are skill-internal platform docs
# (video-sdk/linux, video-sdk/windows) and a hidden background agent
# (report_researcher) — none of which should be standalone agents.
for n, p in unknown:
    print('  unknown-md: %-22s %s' % (n, p))
print()

if unknown:
    print('=== unresolved "unknown-md" (need manual look) ===')
    for n, p in unknown[:40]:
        print('  %-46s %s' % (n, p))
    print('  total unknown:', len(unknown))

json.dump({'should_be': sorted(should_be), 'verdicts': {n: v for v, n, _ in rows}},
          open('/tmp/agent_verdicts.json', 'w'), indent=1)
