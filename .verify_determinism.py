#!/usr/bin/env python3
"""Prove the generators are deterministic.

Runs every generator a second time and compares the output byte-for-byte
against the first run's output.

Why this exists
---------------
`skills/` and `agents/` are deleted and recreated on each build, which
changes the order the filesystem hands directories back. Any generator that
picks "the first copy it saw" therefore picks a *different* copy after a
rebuild — the generated documents silently change content between runs.

That bug was live: the report's canonical-path column flipped for every
agent that exists both as `agents/<name>.md` and nested inside a skill's
own `agents/` directory, and the report showed Japanese locale copies of
descriptions while claiming the English library path.

Two runs of the same input must produce the same bytes. This script is the
regression guard for that.
"""
import hashlib
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

GENERATORS = [
    ('build-library', [PY, '.build_library.py'],
     ['.library_data.json']),
    ('build-guide', [PY, '.build_guide.py'],
     ['ROUTING_GUIDE.md']),
    ('gen-report', [PY, '.gen_report.py'],
     ['SKILLS_AND_AGENTS_REPORT.md']),
]

# Fields that legitimately differ between two runs of the same input.
VOLATILE_KEYS = ('generated_at', 'built_at', 'scanned_at')


def sha256(path):
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def run(cmd):
    r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True)
    if r.returncode != 0:
        print('generator failed: %s' % ' '.join(cmd))
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        raise SystemExit(1)


def main():
    failures = []

    for name, cmd, outputs in GENERATORS:
        print('--- %s' % name)
        run(cmd)
        first = {rel: sha256(os.path.join(BASE, rel)) for rel in outputs}
        for rel, h in first.items():
            print('    pass 1  %-34s %s' % (rel, (h or 'MISSING')[:16]))

        run(cmd)
        second = {rel: sha256(os.path.join(BASE, rel)) for rel in outputs}
        for rel, h in second.items():
            same = first[rel] == h
            print('    pass 2  %-34s %s  %s' % (
                rel, (h or 'MISSING')[:16], 'same' if same else 'DIFFERENT'))
            if not same:
                failures.append('%s: %s is not reproducible' % (name, rel))

    print()
    if failures:
        print('DETERMINISM: FAIL')
        for f in failures:
            print('  %s' % f)
        return 1
    print('DETERMINISM: PASS — every generator is byte-reproducible')
    return 0


if __name__ == '__main__':
    sys.exit(main())
