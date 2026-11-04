#!/usr/bin/env python3
"""Generate the Skills & Agents inventory report.

Re-runs the full filesystem scan and writes SKILLS_AND_AGENTS_REPORT.md
next to this script. Safe to re-run after new skills/agents are installed.

The scan root is the machine's home directory by default, because the
library is a consolidation of everything installed on it. A published
tree sets `SKILLS_LIBRARY_SCAN_ROOT` to its own directory, so the report
describes the tree that ships rather than the machine that published it.
"""
import os
import re
import json
import hashlib
import collections
import datetime

OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('SKILLS_LIBRARY_SCAN_ROOT') or os.path.expanduser('~')
# When the scan root is this tree, the report describes this tree -- so the
# machine-specific sections (which are about the *other* directories on the
# machine) are not written.
IN_PLACE = os.path.realpath(ROOT) == os.path.realpath(OUT)

# A published tree has no machine behind it: its content was copied in and
# filtered by licence. Scanning the home directory here would describe the
# machine, not this tree -- and would name every skill the licence filter
# excluded.
PUBLISHED = (os.path.isfile(os.path.join(OUT, 'CREDITS.md')) and
             os.path.isfile(os.path.join(OUT, 'LICENSE')))
if PUBLISHED and 'SKILLS_LIBRARY_SCAN_ROOT' not in os.environ:
    ROOT = OUT
    IN_PLACE = True

SKIP = {'node_modules', '.git', 'venv', '.venv', 'site-packages', '__pycache__',
        '.npm', '.gradle', '.m2', 'dist', 'build', '.next', 'vendor', 'target',
        '.ruff_cache', '.cache'}
LOCALES = {'ja-JP', 'zh-CN', 'zh-TW', 'ko-KR', 'tr', 'es', 'fr', 'de',
           'pt-BR', 'it', 'ru', 'pl'}

# Ponytail ships generated adapter copies of its skills under `.openclaw/`
# with truncated descriptions. Prefer the canonical `skills/` copy for both
# the description and the canonical path.
PONYTAIL_PREFIX = OUT + '/ponytail/'


def rank_path(p):
    """Lower is better. Scoped to Ponytail; every other path is unaffected.

    The final path component of the key is an explicit tie-break. Without it
    every non-Ponytail path scores identically, and a stable sort would then
    return whichever copy os.walk happened to see first — which changes
    between rebuilds. The path itself is the tie-break, so the result is
    reproducible.
    """
    if not p.startswith(PONYTAIL_PREFIX):
        return (0, 0, p)
    dot_dirs = sum(1 for x in p.split(os.sep)
                   if x.startswith('.') and x not in ('.', '..'))
    return (dot_dirs, len(p), p)


def path_rank(p):
    """Quality score for a copy of a skill or agent. Lower is better.

    The library's own assembled copies win: `skills/<name>/SKILL.md` and
    `agents/<name>.md` are byte-for-byte what `.build_library.py` copied in,
    so reporting them means the table shows the file that actually exists in
    this library — and its description is the one `.library_data.json` and
    `ROUTING_GUIDE.md` carry. Without this the report and the guide can
    describe different copies of the same skill.

    Beyond that: locale variants and scratch directories lose, the ECC source
    library wins, and adapter surfaces that ship flattened copies lose.

    The path is the final tie-break, which makes the choice deterministic —
    `os.walk` order is not stable across rebuilds, because `skills/` and
    `agents/` are deleted and recreated.
    """
    rel = os.path.relpath(p, ROOT)
    parts = rel.split(os.sep)
    s = 0
    # The library's own assembled copy.
    if rel.startswith('Projects/Skills_n_Agents/skills/'):
        s -= 30
    elif rel.startswith('Projects/Skills_n_Agents/agents/'):
        s -= 30
    elif rel.startswith('Projects/Skills_n_Agents/ponytail/'):
        s -= 25
    if any(x in parts for x in LOCALES):
        s += 100
    if '.tmp' in parts:
        s += 40
    if parts[:2] == ['Projects', 'ECC']:
        s -= 20
    elif parts[0] == 'Projects' and len(parts) > 1:
        s += 10
    if rel.startswith('Projects/Skills_n_Agents/'):
        s -= 15
    # Adapter surfaces ship generated, flattened copies that lose content.
    if '/.openclaw/' in rel:
        s += 8
    if p.startswith(PONYTAIL_PREFIX):
        dot_dirs = sum(1 for x in p.split(os.sep)
                       if x.startswith('.') and x not in ('.', '..'))
        s += dot_dirs * 10
    # A copy nested inside a skill's own agents/ directory is a duplicate of
    # the assembled library copy; prefer the flat, installed one.
    if '/skills/' in rel and '/agents/' in rel:
        s += 5
    return (s, len(p), p)

AGENT_SUFFIX = ('-reviewer', '-architect', '-resolver', '-planner', '-specialist',
                 '-optimizer', '-explorer', '-evaluator', '-updater', '-cleaner',
                 '-hunter', '-analyst', '-operator', '-harness', '-generator',
                 '-finder', '-packager', '-sanitizer', '-forker', '-troubleshooter',
                 '-staff', '-guide', '-coordinator', '-runner', '-lookup', '-creator',
                 '-verifier', '-auditor', '-critic', '-scorer', '-drafter', '-mapper',
                 '-miner', '-builder', '-researcher', '-loader')


def frontmatter(text):
    m = re.search(r'^---\s*\n(.*?)\n---', text, re.S)
    return m.group(1) if m else ''


def fld(fm, key):
    """Read a frontmatter field, resolving '>' folded block scalars."""
    m = re.search(r'^%s:\s*(.+)$' % key, fm, re.M)
    if not m:
        return ''
    v = m.group(1).strip()
    if v in ('>', '|', '>-', '|-'):
        lines = fm.split('\n')
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


# ------------------------------------------------------------------- YAML path
# `fld` above reads one line per key, so a plain scalar that continues on the
# next line is truncated -- which costs 17 skills their activation triggers.
# PyYAML is the reference parser; the regex parser stays alive as the
# fallback for the two agents whose frontmatter is not valid YAML
# (`Explore` and `silent-failure-hunter` carry an unquoted `:`).
#
# This script re-scans the machine independently and does NOT read
# `.library_data.json`, so it needs the same substitution the builder got --
# otherwise the report and the routing guide would describe different copies
# of the same skill.
try:
    import yaml
    HAVE_YAML = True
except ImportError:          # pragma: no cover - PyYAML is present here
    HAVE_YAML = False


FM_KEYS = (
    'name', 'description', 'tools', 'model', 'mode', 'permission', 'license',
    'version', 'compatibility', 'metadata', 'origin', 'allowed-tools',
    'disable-model-invocation', 'user-invocable', 'argument-hint', 'color',
    'effort', 'target', 'agents', 'handoffs', 'tier', 'category', 'tags',
)


def _regex_fm(raw):
    """The original line-oriented parser, expressed as a mapping."""
    out = {}
    for key in FM_KEYS:
        v = fld(raw, key)
        if v:
            out[key] = v
    return out


def fm_data(text):
    """Parsed frontmatter as a mapping. YAML first, regex fallback."""
    raw = frontmatter(text)
    if not raw:
        return {}
    if HAVE_YAML:
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError:
            data = None
        if isinstance(data, dict):
            return data
    return _regex_fm(raw)


def fld_of(content, key):
    """One field of a whole document. YAML first, regex fallback."""
    v = fm_data(content).get(key, '')
    if v is None:
        return ''
    if isinstance(v, (list, tuple)):
        return ', '.join(str(x) for x in v)
    if isinstance(v, bool):
        return 'true' if v else 'false'
    return str(v).strip()


def desc_of(content):
    """The description of a document, whitespace-normalised.

    YAML preserves the line breaks of a plain scalar that continues on the
    next line. The guide and the report both collapse whitespace, and the
    library does too — normalising here means the three never disagree.
    """
    return ' '.join(fld_of(content, 'description').split())


def walk(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP]
        # A *published* copy of this library is not an upstream source: it
        # holds the same skills, already consolidated. Scanning it would
        # double-count every entry. A tree is recognised by its own
        # `.library_data.json` -- except this one, which is the library
        # being reported on.
        dn[:] = [d for d in dn
                 if not (os.path.join(dp, d) != OUT
                         and os.path.isfile(os.path.join(dp, d,
                                                        '.library_data.json')))]
        yield dp, dn, fn


# ------------------------------------------------------------------ collect
skills = {}
agents = {}
raw_skill_files = 0
raw_agent_files = 0

for dp, dn, fn in walk(ROOT):
    files = set(fn)
    in_agents_dir = os.path.basename(dp) == 'agents'

    if 'SKILL.md' in files:
        p = os.path.join(dp, 'SKILL.md')
        raw_skill_files += 1
        try:
            c = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        fm = frontmatter(c)
        name = fld(fm, 'name') or os.path.basename(dp)
        # The description is the one field read through YAML. `name` stays on
        # the regex path on purpose: `.audit_find.py` parses names with real
        # PyYAML independently, and the two implementations must be able to
        # disagree.
        desc = desc_of(c)
        body = c[c.index('---', 3) + 3:] if fm else c
        h1 = re.search(r'^#\s+(.+)$', body, re.M)
        title = h1.group(1).strip() if h1 else name
        rel = os.path.relpath(p, ROOT)
        is_locale = any(x in rel.split(os.sep) for x in LOCALES)
        h = hashlib.md5(c.encode()).hexdigest()
        r = skills.setdefault(name, {'name': name, 'desc': desc, 'title': title,
                                     'hash': h, 'paths': [], 'copies': 0,
                                     'locale': False})
        r['paths'].append(p)
        r['copies'] += 1
        if is_locale:
            r['locale'] = True
        if not r['desc'] and desc:
            r['desc'] = desc
        # Remember each copy's own description so the canonical copy's text
        # can be chosen once the whole scan is done (see `resolve_descs`).
        r.setdefault('descs', {})[p] = desc

    for f in sorted(files):
        if not f.endswith('.md') or f == 'SKILL.md':
            continue
        low = f.lower()
        stem = low[:-3] if low.endswith('.md') else low
        # Companion docs inside a skill (references/, rules/, examples/, templates/) are
        # supporting material for that skill, not standalone agent definitions.
        parent_parts = os.path.relpath(dp, ROOT).split(os.sep)
        companion = bool({'references', 'rules', 'examples', 'templates', 'assets', 'docs'}
                         & set(parent_parts))
        looks = (in_agents_dir
                 or (not companion
                     and (stem.startswith(('agent', 'code-', 'build-', 'ecc-', 'tdd-'))
                          or stem.endswith(AGENT_SUFFIX))))
        if not looks:
            continue
        p = os.path.join(dp, f)
        try:
            c = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        if len(c) < 200:
            continue
        fm = frontmatter(c)
        name = fld(fm, 'name')
        if not name:
            continue
        raw_agent_files += 1
        h = hashlib.md5(c.encode()).hexdigest()
        r = agents.setdefault(name, {'name': name, 'desc': desc_of(c),
                                     'tools': fld(fm, 'tools'),
                                     'model': fld(fm, 'model'),
                                     'hash': h, 'paths': [], 'copies': 0})
        r['paths'].append(p)
        r['copies'] += 1
        # Remember every copy's fields so the canonical copy's values can be
        # chosen after the scan — the first copy seen is not necessarily the
        # canonical one, and os.walk order is not stable across rebuilds.
        r.setdefault('descs', {})[p] = desc_of(c)
        r.setdefault('tools_by_path', {})[p] = fld(fm, 'tools')
        r.setdefault('model_by_path', {})[p] = fld(fm, 'model')

# -------------------------------------------------------------- collections
# The source-collection priority list. The machine's own directories are
# only relevant when scanning the machine; a published tree is scanned
# from its own root, so the list is just the tree itself.
PRIO = [
    (OUT + '/ponytail/', 'Ponytail: lazy senior dev mode'),
    (OUT + '/', 'Standalone (in this folder)'),
]
if not IN_PLACE:
    PRIO += [
        (ROOT + '/Projects/HisabKora/', 'Project: HisabKora'),
        (ROOT + '/Projects/CSE412/MediCare/', 'Project: MediCare'),
        (ROOT + '/.codex/skills/', 'Codex: standalone skills'),
        (ROOT + '/.codex/.tmp/plugins/plugins/', 'Codex: plugin marketplace (180 plugins)'),
        (ROOT + '/.claude/plugins/marketplaces/claude-plugins-official/',
         'Claude: official plugin marketplace'),
        (ROOT + '/.config/opencode/skills/', 'OpenCode: standalone skills'),
        (ROOT + '/.config/ecc/skills/', 'ECC: core skill library'),
        (ROOT + '/.gemini/antigravity-cli/builtin/skills/', 'Gemini Antigravity: builtin skills'),
        (ROOT + '/.vscode/extensions/', 'VS Code: extension-bundled skills'),
    ]


def collection(paths):
    for pre, lab in PRIO:
        if any(p.startswith(pre) for p in paths):
            return lab
    for p in paths:
        if '/ECC/' in p or '/ecc/' in p:
            return 'ECC: core skill library'
    for p in paths:
        if '/plugins/' in p:
            return 'Codex: plugin marketplace (180 plugins)'
    return 'Other / uncategorised'


def canonical(paths):
    """The one path this entry is reported under.

    Uses the same ranking as `resolve_descs`, so the path in the table and
    the description in the table always describe the same file.

    Must be deterministic: the scan order of os.walk is not stable across
    rebuilds (skills/ and agents/ are deleted and recreated, which changes
    the directory entry order). The ranking is therefore total — it ends in
    the path itself — so the same input always yields the same canonical path.
    """
    return min(paths, key=path_rank)


def resolve_descs():
    """Pick each skill's description from its canonical copy.

    The scan keeps the *first* description it sees, which is whichever copy
    os.walk reached first — not necessarily the canonical one. Resolve the
    description from the same copy the entry is reported under, so the
    description and the path in the table always describe the same file.

    The ranking is total (it ends in the path), so this is deterministic.
    """
    for r in skills.values():
        descs = r.get('descs') or {}
        if not descs:
            continue
        pick = min(descs, key=path_rank)
        d = descs[pick]
        if d:
            r['desc'] = d

    # Same treatment for agents: description, tools and model must come from
    # the copy the entry is reported under.
    for r in agents.values():
        descs = r.get('descs') or {}
        if descs:
            pick = min(descs, key=path_rank)
            if descs[pick]:
                r['desc'] = descs[pick]
        tools = r.get('tools_by_path') or {}
        if tools:
            pick = min(tools, key=path_rank)
            if tools[pick]:
                r['tools'] = tools[pick]
        models = r.get('model_by_path') or {}
        if models:
            pick = min(models, key=path_rank)
            if models[pick]:
                r['model'] = models[pick]


resolve_descs()


skill_buckets = collections.defaultdict(list)
for s in skills.values():
    skill_buckets[collection(s['paths'])].append(s)

# How many on-disk SKILL.md files are ECC-derived (by frontmatter name match)?
ecc_names = set()
ecc_root = os.path.join(ROOT, 'Projects', 'ECC', 'skills')
try:
    for d in os.listdir(ecc_root):
        p = os.path.join(ecc_root, d, 'SKILL.md')
        if os.path.exists(p):
            try:
                c = open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            nm = fld(frontmatter(c), 'name')
            if nm:
                ecc_names.add(nm)
except OSError:
    pass

ecc_total = 0
for dp, dn, fn in walk(ROOT):
    if 'SKILL.md' not in set(fn):
        continue
    p = os.path.join(dp, 'SKILL.md')
    try:
        c = open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        continue
    nm = fld(frontmatter(c), 'name')
    if nm and nm in ecc_names:
        ecc_total += 1

agent_buckets = collections.defaultdict(list)
for a in agents.values():
    agent_buckets[collection(a['paths'])].append(a)

allc = sorted(set(list(skill_buckets) + list(agent_buckets)))
allc_sorted = sorted(allc, key=lambda c: (-len(skill_buckets.get(c, [])),
                                           -len(agent_buckets.get(c, [])), c))


def clip(text, n=240):
    d = ' '.join((text or '').split())
    if len(d) > n:
        d = d[:n - 3].rsplit(' ', 1)[0] + '...'
    return d.replace('|', '\\|')


# --------------------------------------------------------------------- write
L = []
w = L.append

w('# Skills & Agents Inventory Report')
w('')
if IN_PLACE:
    w('**Scan root:** this repository — every directory in the tree visited')
else:
    w('**Scan root:** `%s` — recursive, every directory visited' % ROOT)
w('**Report date:** %s' % datetime.date.today().isoformat())
w('**Generated by:** `.gen_report.py` (in this folder) — re-runnable after future installs')
w('')
w('---')
w('')

# --- 1
w('## 1. Executive Summary')
w('')
w('| Metric | Count |')
w('|---|---:|')
w('| Raw `SKILL.md` files physically on disk | %d |' % raw_skill_files)
w('| **Distinct skills** (deduplicated by frontmatter `name`) | **%d** |' % len(skills))
w('| Distinct skill content hashes (MD5) | %d |' % len({s['hash'] for s in skills.values()}))
w('| Raw agent definition files detected | %d |' % raw_agent_files)
w('| **Distinct agents** (deduplicated by frontmatter `name`) | **%d** |' % len(agents))
w('| Source collections | %d |' % len(allc))
w('')
w('### The duplication story — read this before using the counts')
w('')
if IN_PLACE:
    w('This tree is already deduplicated: it holds one copy of each published skill and agent,')
    w('so the counts below are the counts of the content itself.')
    w('')
    w('So a %d-file footprint is **%d genuinely distinct skills** and **%d distinct agents**.' % (
        raw_skill_files, len(skills), len(agents)))
    w('Every table below lists the deduplicated set with a canonical path, plus a copy count')
    w('showing how many times each definition appears on disk.')
    w('')
else:
    w('The headline number on disk is badly misleading. The tree contains **5 byte-identical copies of')
    w('the ECC ("Everything Claude Code") repository**:')
    w('')
    w('- `%s/Projects/ECC`' % ROOT)
    w('- `%s/Projects/CSE488/ECC`' % ROOT)
    w('- `%s/Projects/PRIoTP-main/ECC`' % ROOT)
    w('- `%s/Hackathon/ECC`' % ROOT)
    w('- `%s/Study Materials /EWU/Summer2026/CSE412/Project/ECC`' % ROOT)
    w('')
    w('Each copy mirrors the same skills across **4 tool surfaces** (`.agents/` 37, `.kiro/` 43,')
    w('`.cursor/` 10, `.claude/` 1) and ships a `docs/<locale>/` tree holding a translated copy of every')
    w('skill and command in 8 languages (ja-JP, zh-CN, zh-TW, ko-KR, tr, es, pt-BR, + English).')
    w('ECC is *additionally* installed as a Claude Code plugin marketplace, a pinned Claude Code plugin')
    w('cache (v2.0.0), an OpenCode config, a Codex config, and a Gemini Antigravity bundle.')
    w('')
    w('So a %d-file footprint collapses to **%d genuinely distinct skills** and **%d distinct agents**.' % (
        raw_skill_files, len(skills), len(agents)))
    w('Every table below lists the deduplicated set with a canonical path, plus a copy count showing')
    w('how many times each definition appears on disk.')
    w('')
    w('> **Attribution note.** A skill is attributed to the collection where it was *first* found,')
    w('> in the priority order used by the generator (this folder → HisabKora → MediCare → Codex →')
    w('> Claude → OpenCode → ECC → Gemini → VS Code). Because ECC is installed into many of those')
    w('> surfaces, a skill that is conceptually part of the ECC library may appear under "Codex" or')
    w('> "Claude" in the tables below. The ECC-derived skills are the largest coherent group in the')
    w('> collection either way — **%d of the %d skill files on disk are ECC-derived** (1,862 in the ECC'
      % (ecc_total, raw_skill_files))
    w('> tree itself, the rest installed into other surfaces and locale trees).')
    w('')

# --- 2
w('## 2. Source Collections')
w('')
w('Skills and agents grouped by origin. "Copies" in the detail tables is the number of on-disk')
w('instances (mirrored repos + tool surfaces + locale translations).')
w('')
w('| Collection | Skills | Agents |')
w('|---|---:|---:|')
for c in allc_sorted:
    w('| %s | %d | %d |' % (c, len(skill_buckets.get(c, [])), len(agent_buckets.get(c, []))))
w('| **TOTAL** | **%d** | **%d** |' % (len(skills), len(agents)))
w('')

# --- 3
w('## 3. Skills')
w('')
w('A *skill* is a `SKILL.md` file with YAML frontmatter (`name`, `description`) that teaches the')
w('model a procedure, a convention set, or a domain playbook. It activates when the situation it')
w('describes matches the request.')
w('')

sidx = 0
for c in allc_sorted:
    items = sorted(skill_buckets.get(c, []), key=lambda s: s['name'].lower())
    if not items:
        continue
    sidx += 1
    w('### 3.%d %s — %d skills' % (sidx, c, len(items)))
    w('')
    w('| Skill | What it does / expertises in | Copies | Canonical path |')
    w('|---|---|---:|---|')
    for s in items:
        d = clip(s['desc']) or '_(no description in frontmatter)_'
        w('| `%s` | %s | %d | `%s` |' % (s['name'], d, s['copies'], canonical(s['paths'])))
    w('')

# --- 4
w('## 4. Agents')
w('')
w('An *agent* is a specialised sub-agent definition (frontmatter `name`, `description`, usually')
w('`tools` and `model`) invoked for a bounded role — review, build-fixing, architecture, research,')
w('or a domain specialism — with its own tool allow-list.')
w('')

aidx = 0
for c in allc_sorted:
    items = sorted(agent_buckets.get(c, []), key=lambda a: a['name'].lower())
    if not items:
        continue
    aidx += 1
    w('### 4.%d %s — %d agents' % (aidx, c, len(items)))
    w('')
    w('| Agent | Role / expertise | Model | Tools | Copies | Canonical path |')
    w('|---|---|---|---|---:|---|')
    for a in items:
        d = clip(a['desc']) or '_(no description)_'
        w('| `%s` | %s | %s | %s | %d | `%s` |' % (
            a['name'], d, a['model'] or '—', a['tools'].replace('|', '\\|') or '—',
            a['copies'], canonical(a['paths'])))
    w('')

# --- 5
w('## 5. Capability Coverage by Domain')
w('')

DOMAINS = [
    ('Code Review & Quality', ['review', 'simplif', 'cleaner', 'comment-analyzer', 'refactor',
                               'silent-failure', 'type-design', 'pr-test', 'agent-eval', 'taste',
                               'code-tour', 'codebase-onboarding', 'repo-scan', 'health']),
    ('Build & Compilation Fixers', ['build-', '-build-resolver', 'build-fix']),
    ('Architecture & Design', ['architect', 'adr', 'hexagonal', 'design-system', 'blueprint',
                               'system-design', 'codebase-onboarding', 'legacy', 'moderniz',
                               'architecture', 'decision-record']),
    ('Language & Framework Patterns', ['python', 'typescript', 'react', 'vue', 'angular', 'django',
                                       'fastapi', 'springboot', 'laravel', 'quarkus', 'kotlin',
                                       'swift', 'golang', 'rust', 'cpp', 'csharp', 'php', 'perl',
                                       'nestjs', 'nuxt', 'dotnet', 'fsharp', 'dart', 'jpa',
                                       'exposed', 'ktor', 'nextjs', 'expo', 'prisma', 'mysql',
                                       'postgres', 'redis', 'clickhouse', 'django-', 'vercel',
                                       'netlify', 'render-', 'cloudflare', 'bun-', 'vite-',
                                       'turbopack', 'native', 'compose', 'electron', 'tauri']),
    ('Testing & QA', ['test', 'tdd', 'e2e', 'eval', 'benchmark', 'qa', 'coverage',
                       'verification', 'regression', 'playwright', 'browser-qa']),
    ('Security & Compliance', ['security', 'vuln', 'threat', 'owasp', 'hipaa', 'phi', 'gdpr',
                               'sanitiz', 'secret', 'cve', 'permissioned', 'supply-chain',
                               'compliance', 'customs-trade', 'exploit', 'attack-path',
                               'fix-finding', 'triage-finding', 'track-findings']),
    ('AI / LLM Engineering', ['ai-', 'agent', 'llm', 'claude', 'gpt', 'openai', 'anthropic',
                              'prompt', 'rag', 'mcp', 'transformer', 'foundation', 'huggingface',
                              'model', 'finetun', 'inference', 'context-budget', 'token-budget',
                              'cost-aware', 'sandbox', 'durable', 'chat-sdk', 'aiq-', 'vercel-agent']),
    ('Data & Databases', ['sql', 'database', 'schema', 'migration', 'query', 'etl', 'vector',
                          'embed', 'chunk', 'supabase', 'neon', 'data-', 'dashboard', 'pipeline']),
    ('DevOps & Infrastructure', ['deploy', 'ci-cd', 'cicd', 'kubernetes', 'docker', 'container',
                                 'terraform', 'observab', 'monitor', 'infra', 'provision',
                                 'release', 'config-gc', 'sre', 'uptime', 'cloudflare',
                                 'netlify', 'render-', 'vercel-', 'wrangler', 'worker']),
    ('Documentation & Writing', ['doc', 'readme', 'write', 'article', 'memo', 'brief', 'report',
                                 'citation', 'cite', 'humanizer', 'latex', 'markdown', 'summar',
                                 'translation', 'visa-doc', 'narrative', 'spec-to-backlog',
                                 'draft-', 'capture-tasks']),
    ('Research & Analysis', ['research', 'survey', 'study', 'analys', 'literature', 'scholar',
                             'pubmed', 'uspto', 'deep-research', 'scientific', 'taxonomy',
                             'experiment', 'findings', 'citation', 'paper']),
    ('Bioinformatics & Life Sciences', ['ngs-', 'biom', 'gene', 'genom', 'protein', 'pdb', 'clinvar',
                                       'ensembl', 'uniprot', 'reactome', 'kegg', 'pathway',
                                       'alphafold', 'boltz', 'scrna', 'microbiome', 'proteome',
                                       'ncbi-', 'chembl', 'bindingdb', 'pubchem', 'hmdb',
                                       'biorxiv', 'cellxgene', 'bgee', 'chebi', 'efo-',
                                       'gwas-', 'epigraph', 'eva-', 'metabolights', 'biostudies',
                                       'mgnify', 'gnomad', 'cbioportal', 'encode-', 'quickgo',
                                       'pride-', 'rhea-', 'ipd-', 'finngen', 'ukb-', 'tpmi',
                                       'rxcs-', 'gtex-', 'opentargets', 'civic-', 'gget']),
    ('Design, UI & Accessibility', ['design', 'frontend', 'ui-', 'a11y', 'accessib', 'visual',
                                    'animation', 'motion', 'blender', 'remotion', 'shadcn',
                                    'liquid-glass', 'interface', 'taste', 'geist']),
    ('Business, Finance & Product', ['revenue', 'sales', 'crm', 'hubspot', 'invoice', 'billing',
                                      'pricing', 'churn', 'market', 'competitive', 'investor',
                                      'capital', 'unit-economics', 'dcf', 'earn', 'bear',
                                      'valuation', 'lead', 'deal', 'pipeline', 'accounting',
                                      'working-capital', 'inventory', 'returns', 'logistics',
                                      'quality-nonconformance', 'tearsheet', 'bull-']),
    ('Sales, Outreach & Marketing', ['outreach', 'email', 'slack', 'teams', 'linkedin', 'social',
                                      'seo', 'content', 'ads', 'campaign', 'brand', 'copy',
                                      'newsletter', 'calendar', 'gmail', 'publisher', 'crosspost',
                                      'article-writing', 'lead-intelligence', 'canva']),
    ('Communication & Productivity', ['notion', 'sharepoint', 'linear', 'jira', 'asana', 'clickup',
                                       'zoom', 'calendar', 'email', 'slack', 'teams', 'todo',
                                       'task', 'meeting', 'minutes', 'gmail', 'drive', 'sheets',
                                       'docs', 'transcribe', 'superhuman', 'm5-', 'magicpath',
                                       'deepnote', 'microsoft-365', 'outlook']),
    ('Network & Infrastructure', ['network', 'bgp', 'vlan', 'wireguard', 'cisco', 'netmiko',
                                  'ssh', 'homelab', 'dns', 'pihole', 'routing', 'firewall',
                                  'neon-postgres-egress', 'connections-optimizer']),
    ('Education & Training', ['tutor', 'learn', 'course', 'teach', 'math', 'olympiad', 'mentor',
                              'paper', 'student', 'flashcard', 'quiz', 'cse412', 'language-review']),
]


def hit(name, keys):
    """Word-boundary keyword match on a normalised name.

    Naive substring matching produces false positives ('gene' inside 'generate',
    'ngs-' inside 'settings-precedence'), so keywords are matched on token
    boundaries with separators treated as whitespace.
    """
    norm = re.sub(r'[-_/]+', ' ', name.lower())
    norm = ' '.join(norm.split())
    for k in keys:
        kw = ' '.join(re.sub(r'[-_/]+', ' ', k.lower()).split())
        if not kw:
            continue
        pat = r'(?<![a-z0-9])' + r'\s+'.join(re.escape(w) for w in kw.split()) + r'(?![a-z0-9])'
        if re.search(pat, norm):
            return True
    return False


w('| Domain | Skills | Agents | Representative entries |')
w('|---|---:|---:|---|')
for dom, keys in DOMAINS:
    sk = [s for s in skills.values() if hit(s['name'], keys)]
    ag = [a for a in agents.values() if hit(a['name'], keys)]
    if not sk and not ag:
        continue
    ex = ', '.join('`%s`' % x['name'] for x in (sk + ag)[:6])
    w('| %s | %d | %d | %s |' % (dom, len(sk), len(ag), ex))
w('')
w('> Counts **overlap between domains** — `security-review`, for example, matches both')
w('> "Language & Framework Patterns" and "Security & Compliance". These are indicator-based')
w('> buckets, not a partition, so the columns deliberately do not sum to the totals.')
w('')

# --- 6
w('## 6. Notable Focused Collections')
w('')

w('### 6.1 Curated standalone packs in this folder')
w('')
w('`%s` holds 6 hand-authored packs. Unlike the plugin-marketplace' % OUT)
w('material, each is written to a spec — with explicit reference files and a stated workflow')
w('discipline — and these are the highest-quality originals in the collection.')
w('')
w('| Skill | Purpose |')
w('|---|---|')
w('| `caveman-mode` | Forces all thinking and replies into blunt, stripped-down caveman speech for the entire conversation. Short words, broken grammar, no filler or hedging — while keeping technical accuracy, code, numbers and file paths 100% exact. |')
w('| `document-builder` | Three-layer pipeline (SPECIFY → BUILD → VERIFY) for producing finished `.docx` / `.pptx` / `.xlsx` / PDF / markdown deliverables with diagrams and charts. Mandatory spec interview, strict source fidelity (no invented facts), drift control across long documents, sanity-check pass before delivery. Bundles its own vendored docx/pptx/xlsx/pdf/frontend-design skills under `vendor/` so it works standalone. |')
w('| `humanizer` | Rewrites text so it reads as genuinely human rather than AI. Built on Wikipedia *Signs of AI Writing* plus community-compiled word-frequency and structural pattern lists. Ships `references/banned-words.md` (exhaustive word/phrase ban list) and `references/pattern-details.md` (structural, grammatical and tonal patterns with severity ratings). |')
w('| `latex-doctor` | Diagnoses, fixes and writes LaTeX for any IDE or engine (Overleaf, TeXstudio, VS Code + LaTeX Workshop, Vim/Emacs, pdflatex/xelatex/lualatex). Covers compilation errors, missing packages, font issues, BibTeX/BibLaTeX, cross-references, overfull/underfull hbox, float placement, table formatting, math typesetting, and any document class (article, report, book, memoir, thesis). Reference files: `errors.md`, `packages.md`, `bibliography.md`, `math-and-symbols.md`. |')
w('| `research-partner` | Rigorous academic research support: a mandatory intake interview before any deliverable, a written scope contract requiring explicit approval, structured literature reviews, taxonomy construction, constructive critique of papers, multi-stance deep dives, and comparison tables. Enforces evidence discipline — never states an unverified finding, labels provenance (`[from the uploaded PDF]`, `[recalled — worth verifying]`, `[my inference]`), never invents a citation. |')
w('| `skill-creator-plus` | Skill authoring with a built-in evaluation harness. Ships 3 sub-agents (`analyzer.md`, `comparator.md`, `grader.md`), an HTML eval-review viewer under `assets/eval_review.html`, and scripts for the improvement loop (`run_loop.py`), description optimisation (`improve_description.py`) and packaging (`package_skill.py`). Reference files: `schemas.md`, `environments.md`, `authoring-checklist.md`, `description-optimization.md`. |')
w('')

w('### 6.2 Research & Life Sciences')
w('')
w('A large cluster covers biomedical databases and computational biology — the densest single-domain')
w('specialisation in the whole collection.')
w('')
w('**Sequence data / NGS** — `ngs-bcl-to-fastq`, `ngs-fastq-qc`, `ngs-bulk-rnaseq`,')
w('`ngs-bulk-rnaseq-counts-qc`, `ngs-bulk-rnaseq-differential-expression`, `ngs-atacseq-peaks-qc`,')
w('`ngs-chip-cutrun-peaks-qc`, `ngs-dna-variant-calling`, `ngs-dna-germline-variants`,')
w('`ngs-dna-somatic-variants`, `ngs-dna-umi-panel-variants`, `ngs-epigenomics-peaks`,')
w('`ngs-scrna-seq`, `ngs-shotgun-metagenomics`, `ngs-amplicon-microbiome`, `ngs-analysis-router`,')
w('`ngs-runtime-env`')
w('')
w('**Protein structure & design** — `alphafold-skill`, `boltz-protein-design`, `boltz-protein-screen`,')
w('`boltz-small-molecule-design`, `boltz-small-molecule-screen`, `boltz-small-molecule-adme`,')
w('`boltz-structure-and-binding`, `boltz-check-status`, `boltz-cli-setup`')
w('')
w('**Biomedical databases** — `pubchem-pug-skill`, `chembl-skill`, `bindingdb-skill`,')
w('`ncbi-blast-skill`, `ncbi-entrez-skill`, `ncbi-pmc-skill`, `ncbi-datasets-skill`,')
w('`ncbi-clinicaltables-skill`, `ensembl-skill`, `uniprot-skill`, `reactome-skill`, `hmdb-skill`,')
w('`civic-skill`, `openthargets-skill`, `gwas-catalog-skill`, `clinvar-variation-skill`,')
w('`epigraphdb-skill`, `eva-skill`, `metabolights-skill`, `biostudies-arrayexpress-skill`,')
w('`biorxiv-skill`, `proteomexchange-skill`, `mgnify-skill`, `gnomad-graphql-skill`,')
w('`cbioportal-skill`, `encode-skill`, `bgee-skill`, `chebi-skill`, `efo-ontology-skill`,')
w('`cellxgene-skill`, `quickgo-skill`, `rhea-skill`, `ipd-skill`, `finngen-phewas-skill`,')
w('`ukb-topmed-phewas-skill`, `tpmi-phewas-skill`, `rxcs-skill`, `gtex-eqtl-skill`')
w('')
w('**Literature & evaluation** — `literature-review`, `scholar-evaluation`, `pubmed-database`,')
w('`uspto-database`, `project-guidelines-example`, `gget`')
w('')

w('### 6.3 Vendor / SaaS API surface')
w('')
w('Two vendor clusters dominate the plugin marketplace by sheer volume:')
w('')
w('- **Twilio (~50 skills)** — account setup, IAM/auth, regulatory-compliance and HIPAA bundles,')
w('  SMS/MMS/WhatsApp/RCS/email send, SendGrid deliverability, email settings, inbound parse,')
w('  suppressions, engagement quality, voice/Twiml, TaskRouter routing, Conversations,')
w('  customer memory, notifications/alerts, debugging & observability, reliability patterns,')
w('  security hardening.')
w('- **Zoom (~45 skills)** — Meeting SDK across 9 platforms (web, windows, macos, linux, ios,')
w('  android, react-native, electron, unreal), Video SDK across 8, RTMS, virtual agents,')
w('  contact centre (web/ios/android), OAuth, webhooks, websockets, Apps SDK, Cobrowse SDK,')
w('  plus `choose-zoom-approach` and `debug-zoom` decision helpers.')
w('')
w('Also present, by size:')
w('')
w('| Vendor / Suite | Approx. skills | Coverage |')
w('|---|---:|---|')
w('| Render | 20 | deploy, cron, postgres, redis, disks, domains, env vars, workers, blueprints, scaling, monitor, networking, MCP, migrate-from-heroku |')
w('| Netlify | 12 | deploy, edge functions, blobs, caching, forms, identity, image CDN, frameworks, functions, config, CLI |')
w('| Vercel | 12 | agent, API, CLI, flags, functions, queues, sandbox, services, storage, firewall |')
w('| Figma | 12 | design-to-code, generate design/diagram/library/motion, code connect, SwiftUI, FigJam, Slides |')
w('| Microsoft 365 | 27 | SharePoint ×8, Outlook email ×8, Outlook calendar ×6, Teams ×7 |')
w('| Google Workspace | 12 | Drive, Docs, Sheets, Slides, Calendar ×5, Gmail, Meet |')
w('| Slack | 6 | digest, triage, reply drafting, channel summarisation, outgoing messages |')
w('| Shopify | 22 | Liquid, Functions, Hydrogen, Polaris extensions ×4, admin API, customer, payments apps, POS UI, Storefront GraphQL, onboarding ×2, partner, CLI |')
w('| CircleCI | 3 | CLI, config, builds |')
w('| HubSpot | 4 | CRM data hygiene, customer prep, pipeline health, core |')
w('| Notion | 4 | knowledge capture, meeting intelligence, research documentation, spec-to-implementation |')
w('| Twilio | ~50 | full platform |')
w('| Zoom | ~45 | full platform |')
w('| Airtable | 3 | CLI, filters, overview |')
w('| Canva | 4 | branded presentation, resize for social, translate design, base |')
w('')

w('### 6.4 Document & visualisation')
w('')
w('**Artifact templates (18)** — complete business deliverables as ready-to-fill templates:')
w('analytics dashboard, business review, design report, experiment analysis, financial budget,')
w('investment committee memo, legal memorandum, market trends report, minimal letterhead, operating')
w('calendar, operating review, project kickoff, project tracker, sales pipeline, simple dark mode,')
w('simple light mode, strategy memorandum, system design, team alignment, three-statement forecast.')
w('')
w('**Data visualisation (~15)** — `canvas2d-data-visualization`, `d3-data-visualization`,')
w('`grammar-of-graphics-and-declarative-visualization`, `geospatial-and-cartographic-visualization`,')
w('`gantt-chart-visualization`, `node-link-and-diagram-layout`,')
w('`statistical-and-uncertainty-visualization`, `scrollytelling-and-parallax-data-visualization`,')
w('`threejs-data-visualization`, `react-and-nextjs-data-visualization`,')
w('`typescript-data-visualization-engineering`, `dashboards-and-real-time-visualization`,')
w('`accessibility-and-inclusive-visualization`, `testing-data-visualizations`,')
w('`uml-and-software-architecture-visualization`.')
w('')

w('### 6.5 Agentic & autonomous systems')
w('')
w('A distinctive cluster covers building and running agent systems themselves — the most mature')
w('meta-level capability in the collection.')
w('')
w('**Harness & loop construction** — `agent-harness-construction`, `autonomous-agent-harness`,')
w('`autonomous-loops`, `continuous-agent-loop`, `continuous-learning`, `continuous-learning-v2`,')
w('`iterative-retrieval`, `context-budget`, `token-budget-advisor`, `cost-tracking`,')
w('`cost-aware-llm-pipeline`, `agentic-engineering`, `agentic-os`, `dynamic-workflow-mode`,')
w('`parallel-execution-optimizer`, `dmux-workflows`, `team-agent-orchestration`, `agent-sort`,')
w('`agent-introspection-debugging`, `agent-self-evaluation`, `agent-eval`, `eval-harness`,')
w('`skill-scout`, `skill-stocktake`, `gan-style-harness`, `ralphinho-rfc-pipeline`, `council`')
w('')
w('**Multi-agent GAN harness** — a three-role loop, all on Opus: `gan-planner` → `gan-generator` →')
w('`gan-evaluator` → back to the generator. Detailed in §7.')
w('')
w('**Security scanning pipeline** — `claude-security` orchestrates restricted sub-agents')
w('`scan-inventory` → `scan-loader` → `scan-researcher` → `scan-verifier`, then `patch-generator` →')
w('`patch-verifier` for the fix round.')
w('')
w('**Modernisation pipeline** — `legacy-analyst` → `business-rules-extractor` → `test-engineer`')
w('(characterization / contract / equivalence tests) → `scaffolder` → `uplift-migrator` →')
w('`version-delta-analyst`, reviewed by `architecture-critic`.')
w('')

# --- 7
w('## 7. Agent Roster by Function')
w('')

reviewers = sorted(a['name'] for a in agents.values() if a['name'].endswith('-reviewer'))
resolvers = sorted(a['name'] for a in agents.values() if 'build-resolver' in a['name'])

GROUPS = [
    ('Language & stack reviewers (%d)' % len(reviewers), reviewers,
     'Each is marked "MUST BE USED for <language> projects" and covers that language\'s idioms, '
     'security and performance.'),
    ('Build-error resolvers (%d)' % len(resolvers), resolvers,
     'Diagnose and fix compilation / build / dependency failures with minimal, surgical diffs. '
     'Explicitly forbidden from making architectural edits.'),
    ('Architecture & planning', ['architect', 'code-architect', 'ai-architect', 'network-architect',
                                 'a11y-architect', 'homelab-architect', 'planner',
                                 'architecture-critic', 'scaffolder', 'uplift-migrator',
                                 'version-delta-analyst', 'code-explorer', 'explore'],
     'System design, feature blueprints, modernisation planning and codebase mapping.'),
    ('Security', ['security-reviewer', 'security-auditor', 'claude-security', 'scan-inventory',
                  'scan-loader', 'scan-researcher', 'scan-verifier', 'patch-generator',
                  'patch-verifier', 'opensource-sanitizer', 'opensource-forker',
                  'opensource-packager'],
     'Vulnerability detection, adversarial review, orchestrated multi-agent scanning, and the '
     'three-stage open-source release pipeline.'),
    ('Quality & verification', ['code-reviewer', 'pr-test-analyzer', 'agent-evaluator',
                                'skill-reviewer', 'harness-optimizer', 'loop-operator',
                                'tdd-guide', 'e2e-runner', 'docs-lookup', 'doc-updater',
                                'code-simplifier', 'refactor-cleaner', 'silent-failure-hunter',
                                'comment-analyzer', 'conversation-analyzer',
                                'type-design-analyzer', 'spec-miner', 'test-engineer',
                                'business-rules-extractor'],
     'Review, scoring, cleanup, documentation and the guardrails that keep autonomous loops honest.'),
    ('Domain specialists', ['database-reviewer', 'performance-optimizer', 'healthcare-reviewer',
                            'mle-reviewer', 'seo-specialist', 'marketing-agent',
                            'chief-of-staff', 'ctf-flag-finder', 'network-config-reviewer',
                            'network-troubleshooter', 'harmonyos-app-resolver',
                            'maintainer', 'reviewer', 'agent-creator', 'plugin-validator',
                            'legacy-analyst', 'observer', 'report_researcher'],
     'Vertical expertise: databases, performance, clinical safety, ML systems, SEO, marketing, '
     'multi-channel comms, networks, CTF.'),
    ('Research, scoring & outreach', ['signal-scorer', 'enrichment-agent', 'mutual-mapper',
                                      'outreach-drafter', 'scan-researcher'],
     'Prospect discovery, enrichment, mutual-connection mapping and personalised outreach drafting.'),
]

for title, members, blurb in GROUPS:
    if isinstance(members, str):
        members = sorted([a['name'] for a in agents.values() if a['name'].endswith(members)])
    else:
        members = [m for m in members if m in agents]
    if not members:
        continue
    w('### %s' % title)
    w('')
    w('%s' % blurb)
    w('')
    w('%d agents: %s' % (len(members), ', '.join('`%s`' % m for m in members)))
    w('')

w('### The GAN harness — a three-role loop')
w('')
w('| Role | Model | What it does |')
w('|---|---|---|')
w('| `gan-planner` | opus | Expands a one-line prompt into a full product specification — features, sprints, evaluation criteria and design direction. |')
w('| `gan-generator` | opus | Implements features against the spec, reads evaluator feedback, iterates until the quality threshold is met. |')
w('| `gan-evaluator` | opus | Tests the live running application via Playwright, scores it against the rubric, and feeds actionable feedback back to the generator. |')
w('')

# --- 8
w('## 8. Directory Map')
w('')
w('| Path | What it holds |')
w('|---|---|')
if IN_PLACE:
    w('| `skills/` | The published skills — one directory per skill, each with its `SKILL.md` and any supporting files. |')
    w('| `agents/` | The published agent definitions, one markdown file per agent. |')
    w('| `agents/_agent-specific/` | The pipeline-internal agents — dispatch targets, not standalone tools. |')
    w('| `ponytail/` | **Ponytail** (upstream clone, MIT) — 6 skills in `skills/` plus generated adapter copies under `.openclaw/skills/`. A "lazy senior dev" mode: the 7-rung ladder (does it need to exist → already here → stdlib → native → dependency → one line → minimum that works). `AGENTS.md` is the compact always-on ruleset. |')
    w('| `mcp/` | The MCP server — the TypeScript implementation, the Python fallback, the shared index builder and the test suite. |')
    w('')
else:
    w('| `%s/Projects/ECC` | **Canonical ECC repo.** 271 skills in `skills/`, 67 agents in `agents/`, 92 slash commands in `commands/`, plus mirrored `.agents/` (37), `.kiro/` (43), `.cursor/` (10) surfaces and `docs/<locale>/` translations. |' % ROOT)
    w('| `%s/Projects/ECC/skills/` | The 271-skill core library — the single largest skill collection on the system. |' % ROOT)
    w('| `%s/Projects/ECC/agents/` | The 67-agent roster — the source of truth for agent definitions. |' % ROOT)
    w('| `%s/Projects/ECC/commands/` | 92 slash commands. |' % ROOT)
    w('| `%s/Projects/CSE488/ECC`, `%s/Projects/PRIoTP-main/ECC`, `%s/Hackathon/ECC`, `%s/Study Materials /EWU/Summer2026/CSE412/Project/ECC` | Byte-identical clones of the ECC repo — pure duplication. |' % (ROOT, ROOT, ROOT, ROOT))
    w('| `%s/.config/ecc/` | Installed ECC runtime config (skills, agents, commands, `.claude/`, `.opencode/`). |' % ROOT)
    w('| `%s/.claude/plugins/marketplaces/ecc/` | ECC installed as a Claude Code plugin marketplace. |' % ROOT)
    w('| `%s/.claude/plugins/cache/ecc/ecc/2.0.0/` | Pinned cached copy (v2.0.0). |' % ROOT)
    w('| `%s/.claude/plugins/marketplaces/claude-plugins-official/` | Official Anthropic plugin set — agent-sdk-dev, code-review, code-modernization, claude-security, feature-dev, hookify, and the LSP family. |' % ROOT)
    w('| `%s/.codex/.tmp/plugins/plugins/` | **180 Codex plugins** — the widest vendor surface (Twilio, Zoom, Shopify, Figma, Vercel, Netlify, Render, Slack, Canva, Notion, Airtable, CircleCI, HubSpot, Mixpanel, PostHog, Sentry, Neon, …). |' % ROOT)
    w('| `%s/.codex/skills/` | 22 standalone Codex skills — adds `continuous-learning`, `council`, `skill-scout`, `skill-stocktake`, `production-audit`, `code-tour`, `plankton-code-quality`, `iterative-retrieval`. |' % ROOT)
    w('| `%s/.config/opencode/skills/` | 15 OpenCode skills — adds `healthcare-phi-compliance`, `hipaa-compliance`, `postgres-patterns`, `search-first`, `error-handling`. |' % ROOT)
    w('| `%s/.config/opencode/agents/` | 26 OpenCode agent definitions. |' % ROOT)
    w('| `%s/.gemini/antigravity-cli/builtin/skills/` | 9 Gemini Antigravity builtin skills plus a `report_researcher` agent. |' % ROOT)
    w('| `%s/Projects/HisabKora/.agents/` | 19 project-local skills + 9 agents for the HisabKora app (Android clean architecture, Kotlin coroutines/flows, orch-* workflow skills, `hisabkora-context`). |' % ROOT)
    w('| `%s/Projects/CSE412/MediCare/.agents/` | 10 Prisma skills, mirrored into `.claude/` and `.windsurf/`. |' % ROOT)
    w('| `%s/agents/ctf-flag-finder.md` | Standalone CTF challenge solver agent. |' % ROOT)
    w('| `%s/.vscode/extensions/…` | Editor-bundled skills from the Python, Pylance and Java extensions (16 total) — `pylance-refactoring`, `python-manager-discovery`, `java-lsp-tools`, `cross-platform-paths`, `run-e2e-tests`. |' % ROOT)
    w('| `%s/` | **This folder** — 6 curated standalone packs (see §6.1). |' % OUT)
    w('| `%s/ponytail/` | **Ponytail** (upstream clone, MIT) — 6 skills in `skills/` plus generated adapter copies under `.openclaw/skills/`. A "lazy senior dev" mode: the 7-rung ladder (does it need to exist → already here → stdlib → native → dependency → one line → minimum that works). `AGENTS.md` is the compact always-on ruleset. |' % OUT)
    w('')

# --- 9
w('## 9. Findings & Recommendations')
w('')
if IN_PLACE:
    w('1. **The tree is already deduplicated.** %d `SKILL.md` files reduce to **%d distinct'
      % (raw_skill_files, len(skills)))
    w('   skills and %d distinct agents**, one copy each.' % len(agents))
    w('2. **Agent coverage is strongest on review and build-fixing.** %d language-specific reviewers and'
      % len(reviewers))
    w('   %d build resolvers, plus a specialist for nearly every major stack. This is the most' % len(resolvers))
    w('   developed axis of the whole collection.')
    w('3. **Gaps worth filling.** No dedicated database-migration-safety agent, no Kubernetes or')
    w('   Terraform agent, no API-contract agent, and no native mobile reviewer — the skills side')
    w('   covers SwiftUI and Jetpack Compose patterns, but the agent side stops at React and Flutter.')
    w('4. **Ponytail is the only upstream clone kept as its own collection.** It is MIT-licensed and')
    w('   carries its own `.git`, so it is kept whole at `ponytail/` rather than flattened into the')
    w('   library. Its 6 skills are the most opinionated in the set — one behaviour mode plus five')
    w('   one-shot reports — and they pair with the review agents in §7 rather than replacing them.')
    w('5. **The routing guide is the way in.** `ROUTING_GUIDE.md` maps a task to the skill or')
    w('   agent that handles it; the MCP server exposes the same mapping as a search.')
    w('')
else:
    w('1. **Massive redundancy.** %d files on disk reduce to **%d distinct skills and %d distinct'
      % (raw_skill_files, len(skills), len(agents)))
    w('   agents**. Five identical ECC clones × four tool surfaces × eight locale trees account for the')
    w('   overwhelming majority. Consolidating to a single ECC checkout — or symlinking the clones —')
    w('   would remove several thousand redundant files with no functional loss.')
    w('2. **Locale trees are storage, not capability.** Every skill exists in up to 8 languages under')
    w('   `docs/<locale>/`. These are valuable for localisation but must not be counted as separate')
    w('   skills; the tables above dedupe them.')
    w('3. **The standalone packs in this folder are the best original work here.** `caveman-mode`,')
    w('   `document-builder`, `humanizer`, `latex-doctor`, `research-partner` and `skill-creator-plus`')
    w('   are hand-authored with reference files and an enforced workflow — a spec interview before')
    w('   producing, or a verification pass before delivering. The marketplace skills generally lack')
    w('   that discipline; they are reference material.')
    w('4. **The 180-plugin Codex marketplace is breadth over depth.** Twilio (~50) and Zoom (~45) alone')
    w('   are ~90 skills of API-usage reference — valuable as lookups, rarely worth activating.')
    w('5. **Agent coverage is strongest on review and build-fixing.** %d language-specific reviewers and'
      % len(reviewers))
    w('   %d build resolvers, plus a specialist for nearly every major stack. This is the most' % len(resolvers))
    w('   developed axis of the whole collection.')
    w('6. **Gaps worth filling.** No dedicated database-migration-safety agent, no Kubernetes or')
    w('   Terraform agent, no API-contract agent, and no native mobile reviewer — the skills side')
    w('   covers SwiftUI and Jetpack Compose patterns, but the agent side stops at React and Flutter.')
    w('7. **Consider promoting the standalone packs.** `research-partner`, `document-builder` and')
    w('   `humanizer` are general-purpose and would work well under `~/.puku-cli/skills/` or')
    w('   `.puku-cli/skills/` in a project, rather than sitting loose in this folder.')
    w('8. **Ponytail is the only upstream clone kept as its own collection.** It is MIT-licensed and')
    w('   carries its own `.git`, so it is kept whole at `ponytail/` rather than flattened into the')
    w('   library. Its 6 skills are the most opinionated in the set — one behaviour mode plus five')
    w('   one-shot reports — and they pair with the review agents in §7 rather than replacing them.')
    w('')

# --- 10
w('## 10. Appendix — Methodology')
w('')
w('- **Walk:** `os.walk` over `%s`, visiting every directory. Pruned: `node_modules`,' % ROOT)
w('  `.git`, `venv`/`.venv`/`site-packages`, `dist`/`build`/`target`/`vendor`, `.next`,')
w('  `.npm`/`.gradle`/`.m2` caches, `__pycache__`, `.ruff_cache`, `.cache`.')
w('- **Skill detection:** any directory containing a `SKILL.md` with YAML frontmatter. `name` and')
w('  `description` read from the frontmatter, with `>`/`|` folded block scalars resolved into a')
w('  single line.')
w('- **Agent detection:** markdown files carrying frontmatter `name:` that either live in an')
w('  `agents/` directory or match an agent-like filename pattern (`*-reviewer.md`, `*-resolver.md`,')
w('  `*-architect.md`, `*-planner.md`, and ~25 more suffixes). `tools:` and `model:` are captured')
w('  from the same frontmatter block.')
w('- **Deduplication:** by frontmatter `name` (primary key). MD5 content hashes are reported')
w('  separately in §1 to show how many definitions are byte-identical replicas versus')
w('  same-named-but-different skills.')
w('- **Copy counts:** the number of on-disk instances of each definition, counting mirrored')
w('  repositories, alternate tool surfaces and locale translations.')
w('- **Collection assignment:** each entry is attributed to the highest-priority matching source path')
w('  (see the priority list in `.gen_report.py`), so an ECC skill mirrored into `.claude/` is')
w('  attributed to ECC rather than counted twice.')
w('- **Domain buckets (§5):** substring matching of the skill/agent name against a keyword list.')
w('  Deliberately overlapping — an entry can match several domains.')
w('')
w('---')
w('')
w('*Report generated by `.gen_report.py`. Re-run it to refresh after installing new plugins or')
w('skills.*')

path = os.path.join(OUT, 'SKILLS_AND_AGENTS_REPORT.md')
with open(path, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(L) + '\n')

print('Wrote:', path)
print('lines:', len(L))
print('skills:', len(skills), '| agents:', len(agents))
print('collections:', len(allc))
print('reviewers:', len(reviewers), '| build resolvers:', len(resolvers))
