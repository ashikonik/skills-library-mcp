#!/usr/bin/env python3
"""Frontmatter correctness audit — the regression guard for the truncation bug.

The library's builders used a line-oriented regex parser for YAML
frontmatter. That parser reads one line per key, so a plain scalar that
continues on the next line is truncated. 17 skill descriptions lost their
activation triggers this way; `math-olympiad` lost 629 characters, including
every one of "IMO", "Putnam" and "competition math" — the exact queries the
skill exists to catch. The skill was unreachable by search.

This script re-derives every description from the *built* library using
PyYAML, independently of the builder, and asserts the stored description
matches. It is deliberately a second implementation, so it can disagree.

Checks
------
  1. every stored description equals the PyYAML description, whitespace
     normalised — except for the 2 agents whose frontmatter is not valid
     YAML, which must equal the regex fallback
  2. no stored description is shorter than the PyYAML one (a truncation)
  3. `math-olympiad` and `accessibility` carry their full descriptions
  4. the count of descriptions equals the count of entries in the tree
  5. the pipe count in the guide and report tables stays 0 — a `|` in a
     description would break the markdown tables
"""
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

# A published tree holds a filtered subset of the library, and has no
# machine behind it. The checks below are about the *tree*, so they
# hold for both; the ones that describe the machine are skipped.
PUBLISHED = (os.path.isfile(os.path.join(BASE, 'CREDITS.md')) and
             os.path.isfile(os.path.join(BASE, 'LICENSE')))

try:
    import yaml
except ImportError:
    print('PyYAML is required by this audit')
    sys.exit(2)

problems = []
notes = []

lib = json.load(open('.library_data.json', encoding='utf-8'))


def frontmatter(text):
    m = re.search(r'^---\s*\n(.*?)\n---', text, re.S)
    return m.group(1) if m else ''


def regex_fld(raw, key):
    """The builder's original line-oriented parser, for the fallback case."""
    m = re.search(r'^%s:\s*(.+)$' % key, raw, re.M)
    if not m:
        return ''
    v = m.group(1).strip()
    if v in ('>', '|', '>-', '|-'):
        lines = raw.split('\n')
        try:
            i = next(k for k, l in enumerate(lines) if l.startswith(key + ':'))
        except StopIteration:
            return ''
        buf = []
        for l in lines[i + 1:]:
            if l.strip() and not l.startswith(' '):
                break
            buf.append(l.strip())
        return ' '.join(x for x in buf if x).strip('"').strip("'").strip()
    return v.strip('"').strip("'").strip()


def norm(s):
    """Whitespace-normalised comparison form."""
    return ' '.join((s or '').split())


def yaml_desc(path):
    """(description, parse_ok, parse_error, has_frontmatter).

    `parse_ok` is False when the frontmatter could not be parsed as YAML —
    which is fine for the 2 agents with an unquoted ':' (the builder falls
    back to the regex parser there) and for files with no frontmatter at all
    (the builder falls back to a body summary).
    """
    try:
        text = open(path, encoding='utf-8', errors='replace').read()
    except OSError as e:
        return '', False, str(e), False
    raw = frontmatter(text)
    if not raw:
        return '', False, 'no frontmatter', False
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        # Not valid YAML. The builder falls back to the regex parser here;
        # the description must equal that fallback exactly.
        return regex_fld(raw, 'description'), False, str(e).split('\n')[0], True
    if not isinstance(data, dict):
        return '', False, 'frontmatter is not a mapping', True
    v = data.get('description')
    if v is None:
        return '', True, None, True
    if isinstance(v, (list, tuple)):
        v = ', '.join(str(x) for x in v)
    return str(v).strip(), True, None, True


def body_summary(content):
    """The builder's fallback for a file with no frontmatter description."""
    body = re.sub(r'^---.*?\n---\s*', '', content, count=1, flags=re.S)
    para = []
    for line in body.split('\n'):
        s = line.strip()
        if not s:
            if para:
                break
            continue
        if s.startswith(('#', '-', '*', '>', '|', '```')):
            if para:
                break
            continue
        para.append(s)
    return ' '.join(para)


# ---------------------------------------------------------------- skills
skill_paths = {}
for s in lib['skills']:
    # path is "skills/<name>/"; the file is SKILL.md inside it.
    skill_paths[s['name']] = os.path.join(BASE, s['path'].rstrip('/'), 'SKILL.md')

agent_paths = {}
for a in lib['agents']:
    agent_paths[a['name']] = os.path.join(BASE, a['path'])

yaml_broken = []
checked = 0
for name, rec in ((s['name'], s) for s in lib['skills']):
    path = skill_paths.get(name)
    if not path or not os.path.isfile(path):
        problems.append('skill %r: %s is missing' % (name, path))
        continue
    desc, ok, err, has_fm = yaml_desc(path)
    stored = rec.get('desc', '')
    if not has_fm:
        # No frontmatter at all: the builder falls back to a body summary.
        # Compare against that instead.
        text = open(path, encoding='utf-8', errors='replace').read()
        expect = body_summary(text)
        if norm(stored) != norm(expect):
            problems.append('skill %r: body-summary fallback differs' % name)
            problems.append('    stored: %s' % norm(stored)[:160])
            problems.append('    body  : %s' % norm(expect)[:160])
        continue
    if not ok:
        yaml_broken.append((name, err))
        problems.append('skill %r: frontmatter is not valid YAML (%s)' % (name, err))
        continue
    if not desc:
        # No frontmatter description: the builder falls back to a body
        # summary. Not comparable, but it must be non-empty.
        if not stored:
            problems.append('skill %r: no description anywhere' % name)
        continue
    checked += 1
    if norm(stored) != norm(desc):
        problems.append('skill %r: stored description != YAML description' % name)
        problems.append('    stored: %s' % norm(stored)[:160])
        problems.append('    yaml  : %s' % norm(desc)[:160])
    # The specific regression: a stored description shorter than the real one.
    if len(norm(stored)) < len(norm(desc)):
        problems.append('skill %r: stored description is SHORTER than YAML '
                        '(%d < %d) — truncation' % (name, len(norm(stored)),
                                                    len(norm(desc))))

# ---------------------------------------------------------------- agents
for a in lib['agents']:
    name = a['name']
    path = agent_paths.get(name)
    if not path or not os.path.isfile(path):
        problems.append('agent %r: %s is missing' % (name, path))
        continue
    desc, ok, err, has_fm = yaml_desc(path)
    stored = a.get('desc', '')
    if not has_fm:
        # A prose agent with no frontmatter: the builder falls back to a
        # body summary.
        text = open(path, encoding='utf-8', errors='replace').read()
        expect = body_summary(text)
        if norm(stored) != norm(expect):
            problems.append('agent %r: body-summary fallback differs' % name)
            problems.append('    stored: %s' % norm(stored)[:160])
            problems.append('    body  : %s' % norm(expect)[:160])
        continue
    if not ok:
        # Expected for the two agents with an unquoted ':' in a plain scalar.
        # The description must equal the regex fallback, byte for byte.
        yaml_broken.append((name, err))
        if norm(stored) != norm(desc):
            problems.append('agent %r: fallback description != regex fallback' % name)
            problems.append('    stored: %s' % norm(stored)[:160])
            problems.append('    regex: %s' % norm(desc)[:160])
        continue
    if not desc:
        continue
    if norm(stored) != norm(desc):
        problems.append('agent %r: stored description != YAML description' % name)
        problems.append('    stored: %s' % norm(stored)[:160])
        problems.append('    yaml  : %s' % norm(desc)[:160])

# ------------------------------------------------------- named regressions
NAMED = {
    'math-olympiad': ['IMO', 'Putnam'],
    'accessibility': ['WCAG 2.2 Level AA'],
}
by_name = {s['name']: s for s in lib['skills']}
for name, needles in NAMED.items():
    rec = by_name.get(name)
    if not rec:
        problems.append('%s is not in the library' % name)
        continue
    desc = rec.get('desc', '')
    for needle in needles:
        if needle not in desc:
            problems.append('%s: description is missing %r' % (name, needle))
    notes.append('%s: description is %d chars' % (name, len(desc)))

# ---------------------------------------------------------------- counts
# The counts are read from the tree, not asserted. The working library
# holds 976 skills and 102 agents; a *published* tree holds fewer,
# because the licence filter removes the entries whose licence does not
# permit redistribution. What must hold in both is that the number of
# descriptions equals the number of entries on disk -- a tree whose data
# and content disagree is broken, whatever the number is.
on_disk_skills = sum(
    1 for n in os.listdir(os.path.join(BASE, 'skills'))
    if os.path.isdir(os.path.join(BASE, 'skills', n)))
if len(lib['skills']) != on_disk_skills:
    problems.append('the library data holds %d skills but the tree holds %d'
                    % (len(lib['skills']), on_disk_skills))
on_disk_agents = sum(
    1 for n in os.listdir(os.path.join(BASE, 'agents'))
    if n.endswith('.md'))
if len(lib['agents']) != on_disk_agents:
    problems.append('the library data holds %d agents but the tree holds %d'
                    % (len(lib['agents']), on_disk_agents))

# ------------------------------------------------------- markdown safety
# A `|` inside a description would break the guide's and report's tables.
# Every table row must have the same number of cells as its table's header.
def check_tables(doc, text):
    header_cells = None
    for lineno, line in enumerate(text.split('\n'), 1):
        if not line.startswith('|'):
            header_cells = None
            continue
        cells = len(line.split('|')) - 2
        if set(line.replace('|', '').replace(' ', '')) <= set('-:'):
            # A separator row: `|---|---|`
            continue
        if header_cells is None:
            header_cells = cells
            continue
        if cells != header_cells:
            problems.append('%s:%d: row has %d cells, header has %d '
                            '(a description contains a pipe?): %s'
                            % (doc, lineno, cells, header_cells, line[:100]))


for doc in ('ROUTING_GUIDE.md', 'SKILLS_AND_AGENTS_REPORT.md'):
    p = os.path.join(BASE, doc)
    if not os.path.isfile(p):
        # The census report is a description of the *machine* the
        # library was scanned from. A published tree has no machine
        # behind it, and the report is not copied into one.
        if doc == 'SKILLS_AND_AGENTS_REPORT.md' and PUBLISHED:
            continue
        problems.append('%s is missing' % doc)
        continue
    check_tables(doc, open(p, encoding='utf-8').read())

# ---------------------------------------------------------------- report
print('frontmatter audit')
print('  skills checked against PyYAML : %d' % checked)
print('  agents checked against PyYAML : %d' % len(lib['agents']))
print('  frontmatter PyYAML could not parse (fallback expected): %d'
      % len(yaml_broken))
for n, e in yaml_broken:
    print('    %s: %s' % (n, e))
for n in notes:
    print('  %s' % n)
print('  problems: %d' % len(problems))
for p in problems:
    print('    %s' % p)

if problems:
    print()
    print('FRONTMATTER AUDIT: FAIL')
    sys.exit(1)
print()
print('FRONTMATTER AUDIT: PASS')
