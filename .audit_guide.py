#!/usr/bin/env python3
"""Content-level audit of the guide and report.

Checks that are not just "does the path exist" but "is the claim true":
  - every skill in the library appears in the guide's catalogue
  - every agent in the library appears in the guide's catalogue
  - every held-aside agent appears in the held-aside table
  - the guide's headline counts match the library
  - the report's headline counts match the library
  - skill descriptions in the library are non-empty and sane
  - the guide's routing table points at skills whose SKILL.md exists
"""
import os
import re
import json
import sys

BASE = os.environ.get('SKILLS_LIBRARY_ROOT') or \
    os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

lib = json.load(open('.library_data.json'))
guide = open('ROUTING_GUIDE.md', encoding='utf-8').read()
report = open('SKILLS_AND_AGENTS_REPORT.md', encoding='utf-8').read()

problems = []

# --- headline counts ---------------------------------------------------
n_sk = len(lib['skills'])
n_ag = len(lib['agents'])
n_ex = len(lib['excluded_agents'])

for doc, name in ((guide, 'guide'), (report, 'report')):
    for val, label in ((n_sk, 'skills'), (n_ag, 'agents')):
        # accept either "<val> skills" phrasing or a table row pairing them
        pat = (r'\*\*%d\*\*[^\n]{0,60}\b%s\b' % (val, label) +
               r'|\b%s\b[^\n]{0,60}\*\*%d\*\*' % (label, val) +
               r'|\|\s*\*\*(?:\*\*)?%d(?:\*\*)?\s*\*\*[^\n]{0,80}\b%s\b' % (val, label) +
               r'|\|\s*\*\*(?:\*\*)?%s[^\n]{0,80}\*\*%d\*\*' % (label, val))
        if not re.search(pat, doc, re.I):
            problems.append('%s: no headline count %d for %s' % (name, val, label))

# --- catalogue coverage ------------------------------------------------
cat_start = guide.split('## 4. Skill Catalogue by Domain')[1].split('## 5. Agent Catalogue')[0]
cat_skills = set(re.findall(r'^\| `([^`]+)` \|', cat_start, re.M))
lib_skills = {s['name'] for s in lib['skills']}
missing_in_guide = sorted(lib_skills - cat_skills)
if missing_in_guide:
    problems.append('guide skill catalogue missing %d: %s'
                    % (len(missing_in_guide), missing_in_guide[:8]))
extra_in_guide = sorted(cat_skills - lib_skills)
if extra_in_guide:
    problems.append('guide skill catalogue has unknown: %s' % extra_in_guide[:8])

ag_start = guide.split('## 5. Agent Catalogue by Function')[1].split('## 6. Ensemble')[0]
ag_rows = set(re.findall(r'^\| `([^`]+)` \|', ag_start, re.M))
lib_agents = {a['name'] for a in lib['agents']}
missing_ag = sorted(lib_agents - ag_rows)
if missing_ag:
    problems.append('guide agent catalogue missing %d: %s'
                    % (len(missing_ag), missing_ag[:8]))
if {e['name'] for e in lib['excluded_agents']} - ag_rows:
    problems.append('guide held-aside table missing: %s'
                    % sorted({e['name'] for e in lib['excluded_agents']} - ag_rows))

# --- report coverage ---------------------------------------------------
rep_skills = set(re.findall(r'^\| `([^`]+)` \|', report, re.M))
if lib_skills - rep_skills:
    problems.append('report missing skills: %s'
                    % sorted(lib_skills - rep_skills)[:8])

# --- descriptions ------------------------------------------------------
no_desc_sk = [s['name'] for s in lib['skills'] if not s['desc'].strip()]
if no_desc_sk:
    problems.append('skills with empty description: %d %s'
                    % (len(no_desc_sk), no_desc_sk[:5]))
no_desc_ag = [a['name'] for a in lib['agents'] if not a['desc'].strip()]
if no_desc_ag:
    problems.append('agents with empty description: %d %s'
                    % (len(no_desc_ag), no_desc_ag[:5]))

# --- guide routing targets resolve ------------------------------------
for nm in re.findall(r'^\| `([^`]+)` \|', guide, re.M):
    if nm in lib_skills:
        if not os.path.isfile(os.path.join('skills', nm, 'SKILL.md')):
            problems.append('guide names skill with no SKILL.md: %s' % nm)
    elif nm in lib_agents:
        if not os.path.isfile(os.path.join('agents', nm + '.md')):
            problems.append('guide names agent with no file: %s' % nm)

# --- domain totals -----------------------------------------------------
dom = [int(x) for x in re.findall(r'^### 4\.\d+ .* — (\d+) skills?$', guide, re.M)]
if sum(dom) != n_sk:
    problems.append('guide domain counts sum to %d, expected %d' % (sum(dom), n_sk))

print('skills in library      : %d' % n_sk)
print('agents in library      : %d' % n_ag)
print('held aside             : %d' % n_ex)
print('guide catalogue skills : %d' % len(cat_skills))
print('guide catalogue agents : %d' % len(ag_rows))
print('domain count sum       : %d' % sum(dom))
print()
print('problems: %d' % len(problems))
for p in problems:
    print('   ', p)
sys.exit(1 if problems else 0)
