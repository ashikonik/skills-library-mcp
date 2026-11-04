#!/usr/bin/env python3
"""Drift test: does the build correctly pick up a skill that appears later,
and correctly drop one that disappears — without needing a manual wipe?

Creates a temporary skill on the machine, runs the builder, checks it was
picked up; then removes it, runs the builder again, checks it was dropped.
"""
import os
import json
import shutil
import subprocess
import sys

BASE = os.environ.get('SKILLS_LIBRARY_ROOT') or \
    os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

PROBE_ROOT = os.path.join(os.path.expanduser('~'), '.puku-cli', 'drift-probe')
PROBE = os.path.join(PROBE_ROOT, 'skills', 'drift-probe-skill')
PROBE_NAME = 'drift-probe-skill'


def build():
    out = subprocess.run([sys.executable, '.build_library.py'],
                         capture_output=True, text=True, timeout=900)
    if out.returncode != 0:
        print(out.stdout[-2000:])
        print(out.stderr[-2000:])
        raise SystemExit('build failed')
    return json.load(open('.library_data.json'))


def names(data):
    return {s['name'] for s in data['skills']}


print('--- baseline ---')
base = build()
print('skills:', len(base['skills']))
print('probe present?', PROBE_NAME in names(base))

# ---- add a skill mid-flight -------------------------------------------
os.makedirs(PROBE, exist_ok=True)
with open(os.path.join(PROBE, 'SKILL.md'), 'w') as fh:
    fh.write('---\nname: %s\ndescription: Temporary probe skill for the '
             'drift test. Use to verify the builder picks up new skills.\n---\n\n'
             '# Drift probe\n\nTemporary.\n' % PROBE_NAME)
with open(os.path.join(PROBE, 'reference.md'), 'w') as fh:
    fh.write('# supporting file\n\nproves auxiliary files come along\n')

print()
print('--- probe added, rebuilding ---')
added = build()
in_lib = PROBE_NAME in names(added)
in_fs = os.path.isdir(os.path.join(BASE, 'skills', PROBE_NAME))
aux = os.path.isfile(os.path.join(BASE, 'skills', PROBE_NAME, 'reference.md'))
print('skills now      :', len(added['skills']))
print('probe in library :', in_lib)
print('probe dir exists :', in_fs)
print('supporting file  :', aux)

# ---- remove it again ---------------------------------------------------
shutil.rmtree(PROBE_ROOT, ignore_errors=True)
print()
print('--- probe removed, rebuilding ---')
removed = build()
print('skills now       :', len(removed['skills']))
print('probe gone       :', PROBE_NAME not in names(removed))
print('probe dir gone   :', not os.path.exists(os.path.join(BASE, 'skills', PROBE_NAME)))

ok = in_lib and in_fs and aux and (PROBE_NAME not in names(removed))
print()
print('DRIFT TEST:', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
