#!/usr/bin/env python3
"""Verify the 6 top-level packs + humanizer.zip are intact and untouched.

Self-contained: does not depend on a prior snapshot. Checks structure,
content sanity, and that each pack is still mirrored under skills/.
"""
import os
import json
import hashlib
import zipfile
import sys

BASE = os.environ.get('SKILLS_LIBRARY_ROOT') or \
    os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

PACKS = {
    'caveman-mode': ('Forces all reasoning and replies into blunt caveman speech '
                     'for the whole conversation.', 1),
    'document-builder': ('Three layers — SPECIFY -> BUILD -> VERIFY. Produces '
                         '.docx/.pptx/.xlsx/PDF/markdown.', 100),
    'humanizer': ('Rewrites text so it reads as human, not AI. Built on '
                  'Wikipedia Signs of AI Writing.', 1),
    'latex-doctor': ('Diagnoses, fixes and writes LaTeX for any IDE or engine.', 1),
    'research-partner': ('Academic research support with a mandatory scope '
                         'interview and strict evidence discipline.', 1),
    'skill-creator-plus': ('Skill authoring with a real evaluation harness — '
                           '3 sub-agents, a blind A/B comparator, an HTML '
                           'review viewer, and an improvement loop.', 5),
}

problems = []


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


for name, (desc, min_files) in PACKS.items():
    if not os.path.isdir(name):
        problems.append('PACK MISSING: %s' % name)
        continue
    files = []
    for dp, dn, fn in os.walk(name):
        dn.sort()
        for f in sorted(fn):
            files.append(os.path.relpath(os.path.join(dp, f), name))
    has_skill = any(f.endswith('SKILL.md') for f in files)
    if not has_skill:
        problems.append('PACK %s has no SKILL.md' % name)
    if len(files) < min_files:
        problems.append('PACK %s has only %d files (expected >= %d)'
                        % (name, len(files), min_files))
    # mirrored under skills/?
    mirror = os.path.join('skills', name)
    if not os.path.isdir(mirror):
        problems.append('PACK %s not mirrored under skills/' % name)
    else:
        mfiles = []
        for dp, dn, fn in os.walk(mirror):
            for f in fn:
                mfiles.append(os.path.relpath(os.path.join(dp, f), mirror))
        if len(mfiles) != len(files):
            problems.append('PACK %s mirror differs: %d vs %d files'
                            % (name, len(mfiles), len(files)))
    print('PACK %-18s %4d files  SKILL.md:%s  mirrored:%s'
          % (name, len(files), 'yes' if has_skill else 'NO',
             'yes' if os.path.isdir(mirror) else 'NO'))

# --- humanizer.zip -----------------------------------------------------
if not os.path.isfile('humanizer.zip'):
    problems.append('humanizer.zip MISSING')
else:
    try:
        with zipfile.ZipFile('humanizer.zip') as z:
            names = z.namelist()
            bad = z.testzip()
        if bad:
            problems.append('humanizer.zip corrupt at %s' % bad)
        print('FILE humanizer.zip       %4d entries  integrity:ok' % len(names))
    except zipfile.BadZipFile as e:
        problems.append('humanizer.zip unreadable: %s' % e)

# --- side files --------------------------------------------------------
for f in ['README.md', 'ROUTING_GUIDE.md', 'SKILLS_AND_AGENTS_REPORT.md',
          '.library_data.json', '.build_library.py', '.build_guide.py',
          '.gen_report.py']:
    if not os.path.isfile(f):
        problems.append('SIDE FILE MISSING: %s' % f)
    elif os.path.getsize(f) == 0:
        problems.append('SIDE FILE EMPTY: %s' % f)

print()
print('problems: %d' % len(problems))
for p in problems:
    print('   ', p)
sys.exit(1 if problems else 0)
