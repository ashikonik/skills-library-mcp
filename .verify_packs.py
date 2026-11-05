#!/usr/bin/env python3
"""Verify the top-level packs + humanizer.zip are intact and untouched.

Self-contained: does not depend on a prior snapshot. Checks structure,
content sanity, and that each pack is still mirrored under skills/.

The pack list comes from `mcp/build/packs.json` -- the manifest that
names the library's own packs. It used to be a literal in this file, so
adding a pack meant editing the manifest, this file, the tiering module,
the provenance resolver, the guide builder and the report builder. Six
places, one of which was easy to forget, and a pack that no verifier
knew about was a pack nobody would notice breaking.
"""
import os
import json
import hashlib
import zipfile
import sys

BASE = os.environ.get('SKILLS_LIBRARY_ROOT') or \
    os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

sys.path.insert(0, os.path.join(BASE, 'mcp', 'build'))
from packs import packs as pack_records, licence_of  # noqa: E402

problems = []


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


for rec in pack_records():
    name = rec['name']
    min_files = rec.get('min_files', 1)
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
    print('PACK %-18s %4d files  SKILL.md:%s  mirrored:%s  licence:%s'
          % (name, len(files), 'yes' if has_skill else 'NO',
             'yes' if os.path.isdir(mirror) else 'NO', licence_of(name)))

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
