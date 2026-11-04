#!/usr/bin/env python3
"""Consolidate all non-agent-specific skills and agents into this folder.

Creates:
  skills/<name>/        one directory per skill (SKILL.md + all supporting files)
  agents/<name>.md      one file per generally-usable agent
  agents/_agent-specific/  pipeline-internal agents, kept but clearly separated

Writes .library_data.json for the guide builder. Idempotent — wipes and
rebuilds skills/ and agents/ on each run.

The scan root is the machine's home directory by default, because the
library is a consolidation of everything installed on it. Two things
change that:

  * `SKILLS_LIBRARY_SCAN_ROOT` overrides it, which is how a published
    tree rebuilds itself from its own contents rather than from the
    machine that published it.
  * when the scan root IS this directory, the tree is the source: the
    copy step is skipped, because the files are already here. A public
    clone has no other machine to scan.
"""
import os
import re
import json
import shutil
import collections

OUT = os.path.dirname(os.path.abspath(__file__))
# The scan root: the machine's home directory by default. Overridable so a
# published tree can rebuild from its own contents.
ROOT = os.environ.get('SKILLS_LIBRARY_SCAN_ROOT') or os.path.expanduser('~')
# When the scan root is this tree, the tree is the source and nothing is
# copied -- the files are already where they belong.
IN_PLACE = os.path.realpath(ROOT) == os.path.realpath(OUT)

# A *published* tree -- one that has been assembled for redistribution --
# has no machine behind it. Its content was copied in, filtered by
# licence, and it is the source of truth for itself. Without this, a
# published tree that ran the builder would scan the home directory and
# copy the machine's skills back in, including the ones the licence
# filter deliberately excluded.
#
# The marker is the presence of the published tree's own attribution:
# `CREDITS.md` and `LICENSE` are written by the assembler.
PUBLISHED = (os.path.isfile(os.path.join(OUT, 'CREDITS.md')) and
             os.path.isfile(os.path.join(OUT, 'LICENSE')))
if PUBLISHED and 'SKILLS_LIBRARY_SCAN_ROOT' not in os.environ:
    ROOT = OUT
    IN_PLACE = True
SKILLS_OUT = os.path.join(OUT, 'skills')
AGENTS_OUT = os.path.join(OUT, 'agents')
SPECIFIC_OUT = os.path.join(AGENTS_OUT, '_agent-specific')

SKIP = {'node_modules', '.git', 'venv', '.venv', 'site-packages', '__pycache__',
        '.npm', '.gradle', '.m2', 'dist', 'build', '.next', 'target',
        '.ruff_cache'}
# NOTE: `.cache` is deliberately NOT skipped — package caches (e.g. uv's
# archive-v0) can vendor real skills, such as Typer's `.agents/skills/typer`.
# NOTE: `vendor` is NOT skipped either — a skill's own `vendor/` directory
# holds the working files it ships (e.g. document-builder's docx/pptx/xlsx
# tooling). Dropping it makes the copied skill non-functional.
LOCALES = {'ja-JP', 'zh-CN', 'zh-TW', 'ko-KR', 'tr', 'es', 'pt-BR', 'fr', 'de', 'it', 'ru', 'pl'}

# ---------------------------------------------------------------------------
# Pipeline-internal agents: they exist only to be dispatched by an orchestrating
# agent and are documented as "not for direct invocation". Kept, but separated.
# ---------------------------------------------------------------------------
AGENT_SPECIFIC = {
    'scan-inventory': ('claude-security', 'scan pipeline — dispatched by the scan job'),
    'scan-loader': ('claude-security', 'scan pipeline — dispatched by the scan job'),
    'scan-researcher': ('claude-security', 'scan pipeline — dispatched by the scan job'),
    'scan-verifier': ('claude-security', 'scan pipeline — dispatched by the scan job'),
    'patch-generator': ('claude-security', 'fix job — dispatched by the fix job'),
    'patch-verifier': ('claude-security', 'fix job — dispatched by the fix job'),
    'explore': ('claude-security', 'dispatched by researcher/verifier/patch agents'),
    'report_researcher': ('Gemini Antigravity', 'hidden background sub-agent'),
    'analyzer': ('skill-creator-plus', 'eval loop — internal post-hoc analyzer'),
    'comparator': ('skill-creator-plus', 'eval loop — internal blind comparator'),
    'grader': ('skill-creator-plus', 'eval loop — internal grader'),
    'logs-reader': ('osmo-cli', 'spawned by the main OSMO agent'),
    'workflow-expert': ('osmo-cli', 'spawned by the main OSMO agent'),
    'documentation-writer': ('VS Code Python extension', 'extension-internal agent'),
}

# Agents that form a coordinated ensemble or act on the harness itself.
ENSEMBLE = {
    'gan-planner': 'GAN harness — planner -> generator -> evaluator',
    'gan-generator': 'GAN harness — planner -> generator -> evaluator',
    'gan-evaluator': 'GAN harness — planner -> generator -> evaluator',
    'observer': 'background session observer (continuous-learning loop)',
    'loop-operator': 'operates autonomous agent loops',
    'harness-optimizer': 'tunes the local agent harness itself',
    'agent-evaluator': 'scores agent output quality',
    'chief-of-staff': 'multi-channel communication triage',
    'ecc-coordinator': 'ECC pipeline — Plan -> TDD -> Verify -> Review -> Commit',
    'claude-security': 'orchestrates the scan and fix pipelines',
    'opensource-forker': 'open-source pipeline — fork -> sanitize -> package',
    'opensource-sanitizer': 'open-source pipeline — fork -> sanitize -> package',
    'opensource-packager': 'open-source pipeline — fork -> sanitize -> package',
    'agent-creator': 'authoring toolchain',
    'skill-reviewer': 'authoring toolchain',
    'plugin-validator': 'authoring toolchain',
}


def frontmatter(text):
    m = re.search(r'^---\s*\n(.*?)\n---', text, re.S)
    return m.group(1) if m else ''


def fld(fm, key):
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
# The regex parser above reads one line per key. That is enough for a plain
# scalar on one line, but it truncates a plain scalar that continues on the
# next line, and it mis-handles quoted multi-line scalars. 17 skill
# descriptions are truncated this way -- `math-olympiad` loses 629 characters,
# including every activation trigger ("IMO", "Putnam", "competition math"),
# which makes the skill unreachable by search for the exact queries it exists
# to catch.
#
# PyYAML is the reference parser. The regex parser stays alive as the
# fallback for the two agents whose frontmatter is not valid YAML
# (`Explore` and `silent-failure-hunter` carry an unquoted `:` in a plain
# scalar).
try:
    import yaml
    HAVE_YAML = True
except ImportError:          # pragma: no cover - PyYAML is present here
    HAVE_YAML = False


# Every key the original line-oriented parser knew about. The regex fallback
# is rebuilt over exactly this list so it stays behaviourally identical.
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
    """Parsed frontmatter as a mapping.

    PyYAML when it is available and the frontmatter is valid YAML; the
    original line-oriented parser otherwise. Both paths are kept so the
    adversarial verification scripts still have a genuinely different
    implementation to disagree with.
    """
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
    """One field of a whole document, YAML first, regex fallback.

    Lists join with ', ' so the existing string-typed call sites keep
    working unchanged.
    """
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
    next line. The routing guide and the report both collapse whitespace,
    so a description that keeps its newlines would make the two generated
    documents disagree with each other and with the library. Normalising
    here means every consumer sees the same single-line text.
    """
    return ' '.join(fld_of(content, 'description').split())


def body_summary(content):
    """First meaningful prose paragraph of a document, for frontmatter-less files."""
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


def walk(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP]
        # Never re-scan this library's own generated output — it is rebuilt
        # from scratch each run and would otherwise feed back into itself.
        dn[:] = [d for d in dn
                 if os.path.join(dp, d) not in (SKILLS_OUT, AGENTS_OUT)]
        # A *published* copy of this library is not an upstream source: it
        # holds the same skills, already consolidated. Scanning it would
        # double-count every entry and shift the copy counts. A tree is
        # recognised by its own `.library_data.json` — except this one,
        # which is the library being built.
        dn[:] = [d for d in dn
                 if not (os.path.join(dp, d) != OUT
                         and os.path.isfile(os.path.join(dp, d,
                                                        '.library_data.json')))]
        yield dp, dn, fn


def is_locale_path(p):
    rel = os.path.relpath(p, ROOT)
    return any(x in rel.split(os.sep) for x in LOCALES)


# --------------------------------------------------------------------- gather
skill_paths = collections.defaultdict(list)
for dp, dn, fn in walk(ROOT):
    if 'SKILL.md' not in set(fn):
        continue
    p = os.path.join(dp, 'SKILL.md')
    try:
        c = open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        continue
    nm = fld(frontmatter(c), 'name') or os.path.basename(dp)
    skill_paths[nm].append((dp, is_locale_path(p), c))

AGENT_SUFFIX = ('-reviewer', '-architect', '-resolver', '-planner', '-specialist',
                 '-optimizer', '-explorer', '-evaluator', '-updater', '-cleaner',
                 '-hunter', '-analyst', '-operator', '-harness', '-generator',
                 '-finder', '-packager', '-sanitizer', '-forker', '-troubleshooter',
                 '-staff', '-guide', '-coordinator', '-runner', '-lookup', '-creator',
                 '-verifier', '-auditor', '-critic', '-scorer', '-drafter', '-mapper',
                 '-miner', '-builder', '-researcher', '-loader')

agent_paths = collections.defaultdict(list)
for dp, dn, fn in walk(ROOT):
    in_agents_dir = os.path.basename(dp) == 'agents'
    parent_parts = os.path.relpath(dp, ROOT).split(os.sep)
    companion = bool({'references', 'rules', 'examples', 'templates', 'assets', 'docs'}
                     & set(parent_parts))
    for f in sorted(set(fn)):
        if not f.endswith('.md') or f == 'SKILL.md':
            continue
        if f.lower() in ('readme.md', 'index.md', 'overview.md'):
            continue
        p = os.path.join(dp, f)
        try:
            c = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        if len(c) < 200:
            continue
        fm = frontmatter(c)
        low = f.lower()
        stem = low[:-3] if low.endswith('.md') else low
        # Several tools omit `name:` and rely on the filename:
        #   - OpenCode agents use `mode: subagent`
        #   - VS Code uses `<name>.agent.md`
        #   - Figma/Zoom plugin agents are plain prose with no frontmatter
        named = fld(fm, 'name')
        opencode_style = 'mode: subagent' in fm
        vscode_style = stem.endswith('.agent')
        prose_style = not fm and in_agents_dir
        # Slash commands and per-project memory files declare `name:` but are
        # not agents. Exclude them by their markers.
        in_commands_dir = os.path.basename(dp) == 'commands'
        in_memory_dir = os.path.basename(dp) == 'memory'
        is_command = (
            in_commands_dir
            or in_memory_dir
            or 'command: true' in fm
            # `agent: <name>` routes a slash command to an agent; the agent
            # itself never carries this key (it uses `agents:` for sub-agents).
            or re.search(r'^agent:\s*\S', fm, re.M) is not None
            or re.search(r'^node_type:\s*memory', fm, re.M) is not None
        )
        if named:
            nm = named
        elif opencode_style or vscode_style or prose_style:
            nm = stem[:-6] if stem.endswith('.agent') else stem
        else:
            continue
        # A file that declares itself a sub-agent is one, whatever its
        # filename: e.g. VS Code's `Ask.agent.md` / `Plan.agent.md` /
        # `Explore.agent.md` (GitHub Copilot Chat) name themselves in
        # frontmatter and carry `agents:`/`handoffs:`. Requiring an
        # agent-shaped marker keeps skill-internal reference docs (which
        # also carry `name:`) out.
        declares_agent = (
            re.search(r'^agents:\s*\[', fm, re.M) is not None
            or re.search(r'^agents:\s*$', fm, re.M) is not None
            or re.search(r'^handoffs:\s*$', fm, re.M) is not None
            or re.search(r'^target:\s*\S', fm, re.M) is not None
        )
        looks = (in_agents_dir
                 or (not companion
                     and not is_command
                     and (stem.startswith(('agent', 'code-', 'build-', 'ecc-', 'tdd-'))
                          or stem.endswith(AGENT_SUFFIX)
                          or opencode_style or vscode_style
                          or declares_agent)))
        if not looks:
            continue
        agent_paths[nm].append((p, is_locale_path(p), c, fm))

print('unique skills: %d   unique agents: %d' % (len(skill_paths), len(agent_paths)))


def skill_rank(e):
    """Lower is better."""
    dp, loc, _ = e
    rel = os.path.relpath(dp, ROOT)
    parts = rel.split(os.sep)
    s = 0
    if loc:
        s += 100
    if '.tmp' in parts:
        s += 40
    if parts[:2] == ['Projects', 'ECC'] and 'skills' in parts:
        s -= 20
    elif parts[0] == 'Projects' and len(parts) > 1:
        s += 10
    if rel.startswith('Projects/Skills_n_Agents/'):
        s -= 15
    # Adapter surfaces that ship *generated* copies of a skill lose content:
    # Ponytail's `.openclaw/skills/<n>/SKILL.md` is a flattened copy with a
    # truncated description that drops the trigger phrases the routing guide
    # matches on ("yagni", "be lazy", "over-engineering"). Prefer the
    # canonical copy. Scoped to `.openclaw` on purpose — a general
    # "penalise dot-directories" rule would flip ~69 existing skills.
    if '/.openclaw/' in rel:
        s += 8
    return s


def agent_rank(e):
    """Lower is better."""
    p, loc, c, fm = e
    rel = os.path.relpath(p, ROOT)
    parts = rel.split(os.sep)
    s = 0
    if loc:
        s += 100
    if '.tmp' in parts:
        s += 40
    if 'plugins/marketplaces/claude-plugins-official' in rel:
        s -= 15
    if parts[:2] == ['Projects', 'ECC'] and 'agents' in parts:
        s -= 12
    if '/.kiro/agents/' in rel:
        s += 8
    if '/.opencode/agents/' in rel:
        s += 6
    return s


# --------------------------------------------------------------- copy skills
# When the tree IS the scan root, the content is already here and copying
# it onto itself would delete it. So the wipe and the copy are skipped,
# and only the index is rebuilt. That is the published tree's case.
if not IN_PLACE:
    if os.path.isdir(SKILLS_OUT):
        shutil.rmtree(SKILLS_OUT)
    os.makedirs(SKILLS_OUT)

skill_records = []
collisions = []
for name, entries in sorted(skill_paths.items()):
    # Tie-break on the path itself. `skill_rank` scores are frequently equal
    # for two copies of the same skill, and a stable sort would then keep
    # os.walk order — which is not stable across rebuilds (skills/ is deleted
    # and recreated, so the directory entry order changes). Without an
    # explicit tie-break the library content could differ between runs.
    entries = sorted(entries, key=lambda e: (skill_rank(e), e[0]))
    src = entries[0][0]
    dst = os.path.join(SKILLS_OUT, name)
    if os.path.exists(dst):
        collisions.append(name)
        continue
    if IN_PLACE:
        # The content is already at `dst`. The record still needs to be
        # built, so the copy is the only thing skipped.
        pass
    else:
        try:
            shutil.copytree(src, dst, symlinks=False, ignore=shutil.ignore_patterns(*SKIP))
        except (shutil.Error, OSError) as e:
            print('  !! copy failed %s: %s' % (name, e))
            continue
    content = entries[0][2]
    fm = frontmatter(content)
    body = content[content.index('---', 3) + 3:] if fm else content
    h1 = re.search(r'^#\s+(.+)$', body, re.M)
    skill_records.append({
        'name': name,
        # The description is the one field read through YAML. The regex
        # parser truncates a plain scalar that continues on the next line,
        # which cost 17 skills their activation triggers.
        'desc': desc_of(content) or body_summary(content),
        'desc_source': 'yaml' if fm_data(content).get('description') else 'body',
        'title': h1.group(1).strip() if h1 else name,
        'source': src,
        'copies': len(entries),
        'locale_only': all(e[1] for e in entries),
        'rescued_from_tmp': all('.tmp' in e[0].split(os.sep) for e in entries),
        'path': 'skills/%s/' % name,
    })

# --------------------------------------------------------------- copy agents
if os.path.isdir(AGENTS_OUT):
    shutil.rmtree(AGENTS_OUT)
os.makedirs(AGENTS_OUT)
os.makedirs(SPECIFIC_OUT)

agent_records = []
excluded = []
for name, entries in sorted(agent_paths.items()):
    # Same deterministic tie-break as skills: see the note above.
    entries = sorted(entries, key=lambda e: (agent_rank(e), e[0]))
    src, loc, content, fm = entries[0]
    # Flatten any path-ish name (e.g. "video-sdk/linux") so it stays a
    # single file inside agents/.
    flat = name.replace('/', '-').replace(os.sep, '-')
    if name in AGENT_SPECIFIC:
        orch, why = AGENT_SPECIFIC[name]
        shutil.copyfile(src, os.path.join(SPECIFIC_OUT, flat + '.md'))
        excluded.append({'name': name, 'orchestrator': orch, 'reason': why,
                         'source': src, 'path': 'agents/_agent-specific/%s.md' % flat})
        continue
    shutil.copyfile(src, os.path.join(AGENTS_OUT, flat + '.md'))
    agent_records.append({
        'name': name,
        # Description through YAML, like skills. `tools` deliberately stays on
        # the literal regex string: the index normalises it independently, and
        # leaving it alone keeps this a genuine bug repair rather than a
        # reformat of the whole file.
        'desc': desc_of(content) or body_summary(content),
        'desc_source': 'yaml' if fm_data(content).get('description') else 'body',
        'tools': fld(fm, 'tools'),
        'model': fld(fm, 'model'),
        'source': src,
        'copies': len(entries),
        'ensemble': ENSEMBLE.get(name, ''),
        'path': 'agents/%s.md' % flat,
    })

# README for the excluded set
w = []
w.append('# Pipeline-internal agents — not for direct invocation')
w.append('')
w.append('These %d definitions are **dispatch targets**, not standalone tools. Each one is' % len(excluded))
w.append('invoked by an orchestrating agent as part of a larger workflow, and several are')
w.append('explicitly marked *"not for direct invocation"* or *"restricted"* in their own')
w.append('description. Invoking one directly will fail or produce nonsense, because they expect')
w.append('parameters (a scan root, a workspace clone, a comparison result path) that only the')
w.append('parent workflow supplies.')
w.append('')
w.append('They are kept here rather than deleted so the pipelines remain reproducible.')
w.append('')
w.append('| Agent | Dispatched by | Why it is not standalone | Original source |')
w.append('|---|---|---|---|')
for e in sorted(excluded, key=lambda x: (x['orchestrator'], x['name'])):
    w.append('| `%s` | %s | %s | `%s` |' % (e['name'], e['orchestrator'], e['reason'], e['source']))
w.append('')
w.append('## How each pipeline works')
w.append('')
w.append('**claude-security** — `agents/claude-security.md` orchestrates the whole thing:')
w.append('')
w.append('```')
w.append('scan-inventory   -> partitions the repo into components, accounts for every top-level dir')
w.append('scan-loader      -> returns one candidates file from the run directory')
w.append('scan-researcher  -> researches one candidate vulnerability (read-only)')
w.append('scan-verifier    -> votes on one candidate finding (read-only)')
w.append('  ... repeat ...')
w.append('patch-generator  -> implements the fix in a scratch workspace clone')
w.append('patch-verifier   -> reviews the staged diff and runs the tests')
w.append('```')
w.append('')
w.append('**skill-creator-plus** — `scripts/run_loop.py` drives a blind A/B evaluation:')
w.append('`comparator` (judges A vs B without knowing which is which) -> `analyzer` (unblids the')
w.append('result, explains why the winner won) and `grader` (scores against expectations).')
w.append('')
w.append('**Gemini Antigravity** — `report_researcher` is a hidden background agent with a')
w.append('`send_message` tool, wired into that CLI\'s own session model.')
w.append('')
with open(os.path.join(SPECIFIC_OUT, 'README.md'), 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(w) + '\n')

print('copied skills: %d' % len(skill_records))
print('copied agents: %d' % len(agent_records))
print('excluded (agent-specific): %d' % len(excluded))
if collisions:
    print('!! name collisions (skipped):', collisions)

data = {'skills': skill_records, 'agents': agent_records,
        'excluded_agents': excluded}
with open(os.path.join(OUT, '.library_data.json'), 'w', encoding='utf-8') as fh:
    json.dump(data, fh, indent=1, ensure_ascii=False)
print('wrote .library_data.json')
