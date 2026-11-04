#!/usr/bin/env python3
"""Verify supporting files: every file in each skill's source dir must be
present in the library copy, byte-identical (modulo deliberately-skipped
directories). Catches a copytree that silently dropped content.
"""
import os
import json
import hashlib
import sys

BASE = os.environ.get('SKILLS_LIBRARY_ROOT') or \
    os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

lib = json.load(open('.library_data.json'))

# same skip set the builder uses for copytree
SKIP = {'node_modules', '.git', 'venv', '.venv', 'site-packages', '__pycache__',
        '.npm', '.gradle', '.m2', 'dist', 'build', '.next', 'target',
        '.ruff_cache'}


def sha(p):
    try:
        return hashlib.sha256(open(p, 'rb').read()).hexdigest()
    except OSError:
        return None


missing_total = 0
diff_total = 0
extra_total = 0
file_total = 0
skills_with_problems = []

for s in lib['skills']:
    src = s['source']
    dst = s['path']
    src_files = {}
    for dp, dn, fn in os.walk(src):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            fp = os.path.join(dp, f)
            src_files[os.path.relpath(fp, src)] = sha(fp)
    dst_files = {}
    for dp, dn, fn in os.walk(dst):
        for f in fn:
            fp = os.path.join(dp, f)
            dst_files[os.path.relpath(fp, dst)] = sha(fp)

    file_total += len(src_files)
    miss = sorted(set(src_files) - set(dst_files))
    diff = sorted(f for f in src_files if f in dst_files and src_files[f] != dst_files[f])
    extra = sorted(set(dst_files) - set(src_files))

    if miss or diff or extra:
        skills_with_problems.append(s['name'])
        missing_total += len(miss)
        diff_total += len(diff)
        extra_total += len(extra)
        if len(skills_with_problems) <= 12:
            print('%s:' % s['name'])
            for m in miss[:5]:
                print('   MISSING  %s' % m)
            for d in diff[:5]:
                print('   DIFFERS  %s' % d)
            for e in extra[:5]:
                print('   EXTRA    %s' % e)

print()
print('source files compared : %d' % file_total)
print('skills with problems  : %d' % len(skills_with_problems))
print('missing files         : %d' % missing_total)
print('differing files       : %d' % diff_total)
print('extra files in copy   : %d' % extra_total)
sys.exit(1 if (missing_total or diff_total) else 0)
