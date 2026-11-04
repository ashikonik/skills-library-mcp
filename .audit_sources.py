#!/usr/bin/env python3
"""Verify every library entry against its recorded source on disk.

For each skill: the recorded source dir still exists, still contains a
SKILL.md, and that SKILL.md's frontmatter name matches the library name.
For each agent: the recorded source file still exists and is byte-identical
to the copy in the library.
"""
import os
import re
import json
import hashlib
import sys

BASE = os.environ.get('SKILLS_LIBRARY_ROOT') or \
    os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

lib = json.load(open('.library_data.json'))


def sha(p):
    try:
        return hashlib.sha256(open(p, 'rb').read()).hexdigest()
    except OSError:
        return None


def fm_name(text):
    if not text.startswith('---'):
        return None
    end = text.find('\n---', 3)
    if end == -1:
        return None
    m = re.search(r'^name:\s*(.+)$', text[3:end], re.M)
    if not m:
        return None
    v = m.group(1).strip()
    if v.startswith(('"', "'")) and v.endswith(('"', "'")) and len(v) > 1:
        v = v[1:-1]
    return v


problems = []
n_skills = n_agents = 0

for s in lib['skills']:
    n_skills += 1
    src = s['source']
    sm = os.path.join(src, 'SKILL.md')
    if not os.path.isfile(sm):
        problems.append('SKILL source gone: %s -> %s' % (s['name'], src))
        continue
    text = open(sm, encoding='utf-8', errors='replace').read()
    nm = fm_name(text)
    if nm and nm != s['name']:
        problems.append('SKILL name drift: %s (source says %s)' % (s['name'], nm))
    # the copied SKILL.md must be byte-identical to the source
    cp = os.path.join(s['path'], 'SKILL.md')
    if not os.path.isfile(cp):
        problems.append('SKILL copy missing: %s' % s['path'])
    elif sha(cp) != sha(sm):
        problems.append('SKILL copy differs from source: %s' % s['path'])

for a in lib['agents'] + lib['excluded_agents']:
    n_agents += 1
    src = a['source']
    if not os.path.isfile(src):
        problems.append('AGENT source gone: %s -> %s' % (a['name'], src))
        continue
    cp = a['path']
    if not os.path.isfile(cp):
        problems.append('AGENT copy missing: %s' % cp)
    elif sha(cp) != sha(src):
        problems.append('AGENT copy differs from source: %s' % cp)

print('skills verified : %d' % n_skills)
print('agents verified : %d' % n_agents)
print('problems        : %d' % len(problems))
for p in problems[:40]:
    print('   ', p)
sys.exit(1 if problems else 0)
