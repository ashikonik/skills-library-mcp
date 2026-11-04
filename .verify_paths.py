#!/usr/bin/env python3
"""Validate that every path referenced in the report and guide exists on disk."""
import re
import os
import sys

BASE = os.environ.get('SKILLS_LIBRARY_ROOT') or \
    os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

total_bad = 0
for fname in ('SKILLS_AND_AGENTS_REPORT.md', 'ROUTING_GUIDE.md', 'README.md'):
    if not os.path.isfile(fname):
        print('MISSING FILE', fname)
        total_bad += 1
        continue
    g = open(fname, encoding='utf-8').read()

    # Absolute paths in backticks. The home directory is whatever the
    # machine has, so it is matched by shape rather than by name -- a
    # published tree must not carry anyone's home directory, whoever
    # they are.
    home = os.path.expanduser('~').rstrip('/')
    abs_paths = set(re.findall(r'`(/%s[^`\n]+)`' % re.escape(home.lstrip('/')),
                               g))
    abs_paths |= set(re.findall(r'`(/Users/[^`\n]+)`', g))
    missing_abs = sorted(p for p in abs_paths
                          if not os.path.exists(p) and '…' not in p)

    rel_paths = set(re.findall(r'`(skills/[^`\n]+|agents/[^`\n]+)`', g))
    # drop placeholder patterns like `skills/<name>/`
    rel_paths = {p for p in rel_paths if '<' not in p and '…' not in p}
    missing_rel = sorted(p for p in rel_paths if not os.path.exists(p.rstrip('/')))

    print('== %s' % fname)
    print('   absolute refs: %-5d missing: %d' % (len(abs_paths), len(missing_abs)))
    print('   library refs : %-5d missing: %d' % (len(rel_paths), len(missing_rel)))
    for m in missing_abs[:15]:
        print('      MISSING ABS %s' % m)
    for m in missing_rel[:15]:
        print('      MISSING REL %s' % m)
    total_bad += len(missing_abs) + len(missing_rel)

print()
print('TOTAL BROKEN PATH REFERENCES:', total_bad)
sys.exit(1 if total_bad else 0)
