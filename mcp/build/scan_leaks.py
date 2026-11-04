#!/usr/bin/env python3
"""Scan a tree for paths that name the machine that built it.

A public repository must not carry the build machine's home directory:
`/home/someone/...` tells a reader whose machine produced it, and it
is useless to them. The public tree is assembled by copying, so such a
path can arrive from three places:

  * a generated artefact -- the index's `abs_path`, the provenance
    table's `source`, the run manifest's `library_root`;
  * a hand-written document -- a registration snippet with the
    author's absolute entrypoint;
  * a copied file -- a bundled note that mentions a path.

What is *not* a leak
--------------------
Third-party content legitimately contains example paths: a skill that
teaches cross-platform paths writes `/home/name/.venv/bin/python`, an
upstream author's own machine appears in their notes, and a test
fixture uses `/home/u/.claude/...`. Those are the upstream's words, and
rewriting them would corrupt the content being credited.

So the scanner flags exactly one thing: the *builder's* home directory.
It is passed in, so the same scanner works on any machine and in CI,
where the home is a temporary directory.

Usage:
    python3 mcp/build/scan_leaks.py [tree ...]

With no argument it scans the public tree -- the sibling directory the
assembler writes to -- so it can be a build step in its own right.

Exit code 0 when the tree is clean, 1 when a leak is found.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))

# Directories that hold no published content.
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.pytest_cache',
             '.ruff_cache', '.mypy_cache', 'dist'}

# File suffixes that are binary or are known to be noise.
SKIP_SUFFIX = {'.zip', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico',
               '.pdf', '.woff', '.woff2', '.ttf', '.otf', '.mp4', '.mp3',
               '.wav', '.so', '.dylib', '.dll', '.exe', '.gz', '.xz',
               '.bz2', '.jar', '.wasm', '.bin', '.pack', '.idx'}

# The maximum size of a file worth reading. Anything larger is a bundle
# of assets, not a document a reader would read.
MAX_BYTES = 4 * 1024 * 1024


def patterns_for(home):
    """The absolute prefixes that would leak the builder's machine."""
    home = home.rstrip('/')
    pats = [re.compile(re.escape(home) + r'(?![A-Za-z0-9._-])')]
    # The macOS equivalent, for a tree assembled on a Mac.
    user = os.path.basename(home)
    if home.startswith('/home/'):
        pats.append(re.compile(r'/Users/' + re.escape(user) + r'(?![A-Za-z0-9._-])'))
    return pats


def scan(root, pats):
    """Every (path, line-number, line) that names the builder's machine."""
    hits = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in sorted(fn):
            if os.path.splitext(f)[1].lower() in SKIP_SUFFIX:
                continue
            p = os.path.join(dp, f)
            try:
                if os.path.getsize(p) > MAX_BYTES:
                    continue
                with open(p, encoding='utf-8', errors='replace') as fh:
                    lines = fh.readlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                if any(pat.search(line) for pat in pats):
                    hits.append((p, i, line.strip()[:160]))
    return hits


def public_tree():
    """The tree the assembler writes to.

    It is a sibling of the library, because the library is a *working*
    directory and this is a *published* one -- the two are never the
    same tree.
    """
    return os.environ.get('PUBLIC_TREE') or os.path.join(
        os.path.dirname(BASE), 'skills-library-mcp-public')


def main():
    roots = sys.argv[1:] or [public_tree()]
    home = os.environ.get('SKILLS_LIBRARY_HOME') or os.path.expanduser('~')
    pats = patterns_for(home)
    print('scanning for %s' % home)

    total = 0
    for root in roots:
        hits = scan(root, pats)
        print('%-50s %s' % (root, 'clean' if not hits
                            else '%d leak(s)' % len(hits)))
        for p, i, line in hits:
            print('  %s:%d' % (os.path.relpath(p, root), i))
            print('    %s' % line)
        total += len(hits)
    if total:
        print()
        print('%d path(s) name the machine that built this tree. The public'
              ' tree must not carry them.' % total)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
