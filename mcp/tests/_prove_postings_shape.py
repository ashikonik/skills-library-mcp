#!/usr/bin/env python3
"""Prove the postings gate fails on the old (field-blind) postings shape.

The gate must reject an index whose `search.postings` is the old
`kind -> token -> ids` shape while `search.fields` advertises five
fields. This script builds such an index in a temporary tree and runs
the gate against it.

It writes only into a temporary directory and never touches the real
index.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)

REAL_INDEX = os.path.join(MCP, 'data', 'index.json')


def old_shape(data):
    """Rewrite the postings into the old, field-blind shape."""
    postings = {}
    for e in data['skills'] + data['agents']:
        bucket = postings.setdefault(e['kind'], {})
        for t in set(e['tokens']['name'] + e['tokens']['desc']):
            bucket.setdefault(t, []).append(e['id'])
    for kind in postings:
        for t in postings[kind]:
            postings[kind][t].sort()
    data['search']['postings'] = postings
    return data


def main():
    if not os.path.isfile(REAL_INDEX):
        sys.stderr.write('SKIP: %s not found.\n' % REAL_INDEX)
        return 0
    with open(REAL_INDEX, encoding='utf-8') as fh:
        data = json.load(fh)

    tmp = tempfile.mkdtemp(prefix='postings-proof-')
    try:
        os.makedirs(os.path.join(tmp, 'data'), exist_ok=True)
        with open(os.path.join(tmp, 'data', 'index.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump(old_shape(data), fh)

        # Run the gate against the temporary tree. The gate resolves the
        # index from `MCP/data/index.json`, so the temporary tree has to
        # carry the whole `mcp` layout the gate expects -- which it
        # does, because only `data/index.json` is read.
        shutil.copytree(os.path.join(MCP, 'python'),
                        os.path.join(tmp, 'python'), dirs_exist_ok=True)
        shutil.copytree(os.path.join(MCP, 'build'),
                        os.path.join(tmp, 'build'), dirs_exist_ok=True)
        os.makedirs(os.path.join(tmp, 'tests'), exist_ok=True)
        shutil.copy(os.path.join(HERE, 'test_postings.py'),
                    os.path.join(tmp, 'tests', 'test_postings.py'))

        r = subprocess.run(
            [sys.executable, os.path.join(tmp, 'tests', 'test_postings.py')],
            capture_output=True, text=True, timeout=300)
        sys.stdout.write(r.stdout)
        if r.stderr.strip():
            sys.stdout.write('--- stderr ---\n' + r.stderr[-2000:])
        if r.returncode == 0:
            sys.stdout.write(
                '\nPROOF: FAIL -- the gate passed on the old postings '
                'shape\n')
            return 1
        sys.stdout.write(
            '\nPROOF: PASS -- the gate rejected the old postings shape '
            '(exit %d)\n' % r.returncode)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
