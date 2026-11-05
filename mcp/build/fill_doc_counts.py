#!/usr/bin/env python3
"""Fill the counts in the documentation from the index.

The library and the published tree hold different numbers of entries: the
tree leaves the private project files and the test fixtures out. A count
written out by hand is therefore wrong in one of them, and wrong *silently*
-- the document still reads fine, it just describes a library that is not the
one in the directory.

So the documents carry a token instead of a number:

    This library holds **{n_skills} skills** and **{n_agents} agents**

and this script fills the tokens from the index. The same script fills the
public tree's copy, with the public tree's counts -- see
`assemble_public.py`, which calls `fill_doc_counts()` on the tree after it
copies the documentation.

The source files in git carry the tokens. That is deliberate: the token is
the source of truth, and a number committed alongside it would drift.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from assemble_public import fill_doc_counts  # noqa: E402


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else BASE
    fill_doc_counts(root)
