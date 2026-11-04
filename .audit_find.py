#!/usr/bin/env python3
"""Ground-truth re-scan, written independently of .build_library.py.

Differences from the builder, on purpose:
  - discovery via `find` (subprocess) rather than os.walk
  - frontmatter parsed with PyYAML (real YAML) rather than regex
  - agent detection keyed on `name:` plus directory context, with NO
    filename heuristics and NO suffix lists
  - reports every discrepancy candidate rather than pre-filtering

If this and .build_library.py agree, the agreement means something.

The scan root is the machine's home directory by default. A published
tree sets `SKILLS_LIBRARY_SCAN_ROOT` to its own directory, so the
ground truth is the tree that ships.
"""
import os
import re
import json
import subprocess
import sys

LIB = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('SKILLS_LIBRARY_SCAN_ROOT') or os.path.expanduser('~')
# When the scan root is this tree, the tree is the source: the library's
# own `skills/` and `agents/` output is NOT excluded, because it IS the
# content being checked.
IN_PLACE = os.path.realpath(ROOT) == os.path.realpath(LIB)

# A published tree has no machine behind it -- it was assembled by
# copying, and its content is what was copied. The ground truth for a
# published tree is the tree itself.
PUBLISHED = (os.path.isfile(os.path.join(LIB, 'CREDITS.md')) and
             os.path.isfile(os.path.join(LIB, 'LICENSE')))
if PUBLISHED and 'SKILLS_LIBRARY_SCAN_ROOT' not in os.environ:
    ROOT = LIB
    IN_PLACE = True

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


def _published_trees():
    """Published copies of this library, found by their `.library_data.json`.

    A published tree holds the same skills, already consolidated, so it
    is not an *upstream* source: scanning it would double-count every
    entry and shift the copy counts. This one is excluded by name,
    because it is the library being compared against.
    """
    out = []
    for parent in (os.path.join(ROOT, 'Projects'), ROOT):
        if not os.path.isdir(parent):
            continue
        try:
            names = sorted(os.listdir(parent))
        except OSError:
            continue
        for d in names:
            p = os.path.join(parent, d)
            if p == LIB or not os.path.isdir(p):
                continue
            if os.path.isfile(os.path.join(p, '.library_data.json')):
                out.append(p)
    return out


def _excludes():
    """Paths to exclude: the library's own output and packs."""
    ex = []
    if not IN_PLACE:
        # The library's own generated output is excluded, because the
        # scan is looking for *upstream* copies to compare against.
        for sub in ('skills', 'agents', 'document-builder', 'skill-creator-plus',
                    'research-partner', 'humanizer', 'latex-doctor', 'caveman-mode'):
            ex += ['-not', '-path', os.path.join(LIB, sub, '*')]
    for p in _published_trees():
        ex += ['-not', '-path', os.path.join(p, '*')]
    for junk in ('node_modules', '.git', 'venv', '.venv', 'site-packages',
                 '__pycache__'):
        ex += ['-not', '-path', '*/%s/*' % junk]
    return ex


def find_skills():
    """Every SKILL.md on the machine, via find(1)."""
    cmd = ['find', ROOT, '-name', 'SKILL.md'] + _excludes() + ['-print']
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return sorted(p for p in out.stdout.split('\n') if p)


def find_md():
    """Every markdown file, via find(1)."""
    cmd = ['find', ROOT, '-name', '*.md'] + _excludes() + ['-print']
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return sorted(p for p in out.stdout.split('\n') if p)


def parse_frontmatter(text):
    """Return (dict, body). Uses real YAML when available."""
    if not text.startswith('---'):
        return {}, text
    end = text.find('\n---', 3)
    if end == -1:
        return {}, text
    raw = text[3:end]
    body = text[end + 4:]
    if HAVE_YAML:
        try:
            data = yaml.safe_load(raw)
            if isinstance(data, dict):
                return data, body
        except Exception:
            pass
    # regex fallback
    data = {}
    for line in raw.split('\n'):
        m = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)$', line)
        if m:
            v = m.group(2).strip()
            if v.startswith(('"', "'")) and v.endswith(('"', "'")) and len(v) > 1:
                v = v[1:-1]
            data[m.group(1)] = v
    return data, body


def main():
    skill_files = find_skills()
    md_files = find_md()

    # ---- skills -------------------------------------------------------
    skills = {}
    for p in skill_files:
        d = os.path.dirname(p)
        try:
            text = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        fm, _ = parse_frontmatter(text)
        nm = fm.get('name')
        if not isinstance(nm, str) or not nm.strip():
            nm = os.path.basename(os.path.normpath(d))
        nm = nm.strip()
        skills.setdefault(nm, []).append(p)

    # ---- agents -------------------------------------------------------
    # Candidate = any .md with a frontmatter `name:` that is NOT a
    # SKILL.md, plus any .md sitting in a dir literally named "agents".
    agents = {}
    for p in md_files:
        if os.path.basename(p) == 'SKILL.md':
            continue
        try:
            text = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        if len(text.strip()) < 200:
            continue
        fm, _ = parse_frontmatter(text)
        nm = fm.get('name')
        in_agents_dir = os.path.basename(os.path.dirname(p)) == 'agents'
        if not isinstance(nm, str) or not nm.strip():
            if in_agents_dir:
                nm = os.path.basename(p)[:-3]
            else:
                continue
        agents.setdefault(nm.strip(), []).append(p)

    out = {
        'skills': {k: sorted(v) for k, v in skills.items()},
        'agents': {k: sorted(v) for k, v in agents.items()},
        'skill_md_count': len(skill_files),
        'md_count': len(md_files),
        'yaml': HAVE_YAML,
    }
    json.dump(out, open('/tmp/ground_truth.json', 'w'), indent=1)
    print('YAML parser available :', HAVE_YAML)
    print('SKILL.md files found   :', len(skill_files))
    print('total .md files found  :', len(md_files))
    print('unique skill names    :', len(skills))
    print('unique agent names    :', len(agents))


if __name__ == '__main__':
    main()
