#!/usr/bin/env python3
"""Build `mcp/data/index.json` — the shared artifact both MCP servers read.

Why an index at all
-------------------
The library holds 976 skills and 102 agents: 8.4 MB of SKILL.md text and
66 MB of supporting files. Neither server may load that into memory, and no
model may be handed it. So the index carries *descriptions, tokens and
bundle manifests only* — roughly 2 MB — and the actual documents are read
lazily, one file at a time, when a tool is asked for them.

Why it is a derived artifact
----------------------------
The index is rebuilt from `.library_data.json` and the library tree. It is
not a new key in `.library_data.json`, so the library's own data file keeps
its shape, the MCP index can be rebuilt without re-scanning the machine, and
neither server ever depends on a machine scan.

Idempotency
-----------
Two runs over an unchanged library produce byte-identical output apart from
`generated_at`. The verifier compares the content with that field excluded.
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from domains import DOMAINS, assign                      # noqa: E402
from tiering import PACKS, CORE_DOMAINS, assign_tiers    # noqa: E402
from tasks import TASKS                                 # noqa: E402

OUT = os.path.join(BASE, 'mcp', 'data', 'index.json')

try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


# ------------------------------------------------------------------ helpers
def sha256_file(path):
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def frontmatter(text):
    m = re.search(r'^---\s*\n(.*?)\n---', text, re.S)
    return m.group(1) if m else ''


def yaml_frontmatter(path):
    """Parsed frontmatter of a file, plus whether it parsed.

    The two agents whose frontmatter is not valid YAML come back with
    `parse_ok` False and a `parse_error`; the server falls back to a
    regex reader for those and must agree with the Python fallback.

    When the YAML parse fails, the raw frontmatter text is still returned
    so the caller can recover individual fields with the regex reader --
    an agent whose `tools:` is readable should not lose it just because
    some *other* key in the same block is malformed.
    """
    try:
        text = open(path, encoding='utf-8', errors='replace').read()
    except OSError as e:
        return {}, False, str(e), text_or_empty(path), ''
    raw = frontmatter(text)
    if not raw:
        return {}, True, None, text, ''
    if not HAVE_YAML:
        return {}, False, 'PyYAML not available', text, raw
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        return {}, False, str(e).split('\n')[0], text, raw
    if not isinstance(data, dict):
        return {}, False, 'frontmatter is not a mapping', text, raw
    return data, True, None, text, raw


def regex_field(raw, key):
    """Read one field with the line-oriented parser (the YAML fallback).

    The builder uses the same parser, so an agent whose frontmatter is not
    valid YAML gets the same description the library recorded.
    """
    if not raw:
        return ''
    m = re.search(r'^%s:\s*(.+)$' % re.escape(key), raw, re.M)
    if not m:
        return ''
    v = m.group(1).strip()
    if v in ('>', '|', '>-', '|-'):
        lines = raw.split('\n')
        try:
            i = next(k for k, l in enumerate(lines)
                     if l.startswith(key + ':'))
        except StopIteration:
            return ''
        buf = []
        for l in lines[i + 1:]:
            if l.strip() and not l.startswith(' '):
                break
            buf.append(l.strip())
        return ' '.join(x for x in buf if x).strip('"').strip("'").strip()
    return v.strip('"').strip("'").strip()


def text_or_empty(path):
    try:
        return open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''


def norm_tools(v):
    """Normalise the `tools:` field to a JSON array.

    Three shapes are in use across the library: a YAML list, a comma string
    and a space-separated string. 73 agents differ between the regex parser
    (which yields the literal text `["Read", "Grep"]`) and YAML (which
    yields a real list). The index normalises once, here.
    """
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    if not s:
        return []
    if s.startswith('[') and s.endswith(']'):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except ValueError:
            pass
    if ',' in s:
        return [x.strip() for x in s.split(',') if x.strip()]
    return [x for x in s.split() if x]


def prompt_signals(metadata):
    """The curated activation phrases, normalised.

    `metadata.promptSignals` is a dict: `{phrases: [...], allOf: [[...]],
    anyOf: [...]}`. 18 skills carry it. These are hand-written activation
    phrases -- the corpus carries its own supervision, and an exact hit on
    one of them beats any fuzzy similarity.
    """
    if not isinstance(metadata, dict):
        return {'phrases': [], 'all_of': [], 'any_of': []}
    ps = metadata.get('promptSignals')
    if not isinstance(ps, dict):
        return {'phrases': [], 'all_of': [], 'any_of': []}
    phrases = [str(x).strip() for x in (ps.get('phrases') or []) if str(x).strip()]
    all_of = [[str(x).strip() for x in row if str(x).strip()]
              for row in (ps.get('allOf') or [])]
    any_of = [str(x).strip() for x in (ps.get('anyOf') or []) if str(x).strip()]
    return {'phrases': phrases, 'all_of': all_of, 'any_of': any_of}


# ------------------------------------------------------------------- bundle
# A "reference" is a backticked path in the SKILL.md that points at a file
# inside the skill's own directory.
REF_RE = re.compile(r'`([A-Za-z0-9_./-]+\.(?:md|py|sh|js|ts|json|yaml|yml|txt|csv))`')


def scan_bundle(skill_dir, skill_md_text):
    """The supporting files of a skill: what is there, and what is referenced.

    The bundle is a manifest, not the content. 114 references across the
    library already dangle — pre-existing, and recorded here rather than
    hidden, so a caller can tell a missing file from a missing mention.
    """
    files = []
    total = 0
    for root, dirs, names in os.walk(skill_dir):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
        for n in sorted(names):
            p = os.path.join(root, n)
            rel = os.path.relpath(p, skill_dir)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            files.append({'path': rel, 'bytes': size})
            total += size

    refs = []
    for target in REF_RE.findall(skill_md_text or ''):
        # Only count references that point inside the skill.
        if target.startswith('/') or '..' in target.split('/'):
            continue
        resolves = os.path.isfile(os.path.join(skill_dir, target))
        refs.append({'target': target, 'resolves': resolves})

    seen = set()
    unique_refs = []
    for r in refs:
        if r['target'] in seen:
            continue
        seen.add(r['target'])
        unique_refs.append(r)

    resolved = sum(1 for r in unique_refs if r['resolves'])
    return {
        'file_count': len(files),
        'total_bytes': total,
        'files': files,
        'refs': unique_refs,
        'refs_total': len(unique_refs),
        'refs_resolved': resolved,
        'refs_dangling': len(unique_refs) - resolved,
    }


# ------------------------------------------------------------------ tokens
# The tokenizer is defined once here and mirrored in the TypeScript server.
# The two must agree exactly; that is what the agreement test checks.
STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'been', 'being', 'but', 'by',
    'can', 'could', 'did', 'do', 'does', 'for', 'from', 'had', 'has', 'have',
    'he', 'her', 'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its',
    'me', 'my', 'of', 'on', 'or', 'our', 'out', 'she', 'so', 'such', 'than',
    'that', 'the', 'their', 'them', 'then', 'there', 'these', 'they', 'this',
    'those', 'to', 'too', 'up', 'us', 'was', 'we', 'were', 'what', 'when',
    'where', 'which', 'while', 'who', 'whom', 'why', 'will', 'with', 'would',
    'you', 'your',
}
# Deliberately NOT stopwords: test, write, fix, review, build, debug, run,
# create, update, generate, deploy. Those are this library's domain
# vocabulary, and stripping them made "write tests first" fail to surface
# `tdd-workflow` in an earlier prototype.

CAMEL_RE = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')
WORD_RE = re.compile(r'[^A-Za-z0-9]+')


def tokenize(text):
    """NFKC-ish normalise, split camelCase, drop function words."""
    if not text:
        return []
    out = []
    for word in WORD_RE.split(str(text)):
        if not word:
            continue
        # camelCase split BEFORE lowercasing. Lowercasing first erases the
        # case boundary the split depends on, so `useEffect` stayed one token
        # `useeffect` and "use effect" never matched it.
        parts = CAMEL_RE.sub(' ', word).split()
        for p in parts:
            p = p.lower()
            if p in STOPWORDS:
                continue
            out.append(p)
        if len(parts) > 1:
            # Keep the whole word as well. The camel split cannot tell
            # `parseHTMLString` (three words) from `GraphQL` (one), so
            # splitting alone makes "graphql" unfindable -- it becomes
            # "graph ql". Emitting both forms makes either spelling
            # searchable, and the whole form carries a high idf because
            # few documents contain it.
            whole = word.lower()
            if whole not in STOPWORDS:
                out.append(whole)
    return out


def bigrams(tokens):
    return ['%s %s' % (a, b) for a, b in zip(tokens, tokens[1:])]


# The prepositions that put their object in a subordinate phrase.
#
# A noun after one of these is the object of the preposition, not the
# subject of the query: in "add authentication to an api", "api" is the
# context and "authentication" is what the query is about.
PREPOSITIONS = {
    'about', 'against', 'at', 'for', 'from', 'in', 'into', 'of', 'on',
    'onto', 'to', 'via', 'with',
}

# The determiners that sit between a preposition and its object.
#
# "to an api" -- "an" has to be stepped over before the preposition
# "to" can be found.
DETERMINERS = {
    'a', 'an', 'each', 'every', 'my', 'our', 'some', 'that', 'the',
    'their', 'this', 'your',
}


def head_tokens(text):
    """The query's HEAD nouns -- the things the query is *about*.

    A word is the head of the query when it is not the object of a
    preposition. That is the difference between these two queries:

        "write a REST API"            -> head: {write, rest, api}
        "add authentication to an api" -> head: {add, authentication}

    The second sentence is *about* authentication; "api" is the thing
    being added to. The search uses this to tell a task row that names
    the query's subject ("Build an API" for "write a REST API") from one
    that merely appears in the query's context.

    Mirrors `head_tokens` in `src/tokenize.ts` exactly.
    """
    heads = set()
    if not text:
        return heads
    words = [w for w in re.split(r'[^a-z0-9]+', str(text).lower()) if w]
    for i, word in enumerate(words):
        # Step back over determiners to find the word that governs.
        j = i - 1
        while j >= 0 and words[j] in DETERMINERS:
            j -= 1
        if j >= 0 and words[j] in PREPOSITIONS:
            continue        # subordinate -- the object of a preposition
        heads.add(word)
    return heads


def task_content_sets(task):
    """The content-token sets of a task row, one per alternative.

    The 73 rows are all written "<verb> <object>" -- "Build an API",
    "Fix a failing build", "Write tests". The verb says *that* something
    happens; the object says *what*. A query that names the object is
    asking for that task, whatever verb it happens to use: "write a
    REST API" is the "Build an API" row.

    A row may list several things it covers, separated by "/": "Write a
    document / report / deck" covers three. Each alternative gets its
    own content set, and the row fires when the query contains one of
    them.

    The verb is the row's first token, so no list of verbs has to be
    maintained. An alternative is only stripped of its first token when
    that token IS the row's verb -- "Fix flaky / failing tests" has the
    verb "fix", so "Fix flaky" yields ["flaky"] and "failing tests"
    yields ["failing", "tests"], where "failing" is part of the object
    rather than a second verb.

    An alternative that is just the verb again ("Write / edit prose"
    splits to "Write") carries no information and is skipped.

    A camel-case word contributes both its parts and its whole form, so
    "LaTeX" yields ['la', 'te', 'x', 'latex'] and "3D" yields
    ['3', 'd', '3d']. A content set requires ALL of its tokens, so
    such a set can never be satisfied by a real query -- the "Write
    LaTeX" row, whose note recommends `latex-doctor`, was
    unreachable. Where one token contains the others, the set is
    reduced to that token: the whole form is what a query actually
    says.

    The sets are computed here, in the builder, so the two servers read
    the same numbers instead of deriving them separately.
    """
    row_tokens = list(dict.fromkeys(tokenize(task)))
    verb = row_tokens[0] if row_tokens else None
    out = []
    for alt in [p.strip() for p in task.split('/') if p.strip()]:
        toks = list(dict.fromkeys(tokenize(alt)))
        if not toks:
            continue
        if len(toks) == 1:
            if verb is not None and toks == [verb]:
                continue          # degenerate split: the verb alone
            out.append(toks)
            continue
        if verb is not None and toks[0] == verb:
            toks = toks[1:]
            if not toks:
                continue
        toks = collapse_camel_parts(toks)
        out.append(toks)
    return out


def collapse_camel_parts(toks):
    """Reduce a token set that mixes camel-case parts with the whole form.

    "LaTeX" is tokenised as ['la', 'te', 'x', 'latex']. A content set
    needs every one of its tokens, so the set can never fire -- the
    "Write LaTeX" task row, whose note recommends `latex-doctor`, was
    unreachable. Where one token contains the others, the whole form is
    the one a query actually contains, so the set collapses to it.
    """
    for w in toks:
        others = [t for t in toks if t != w]
        if others and all(t in w for t in others):
            return [w]
    return toks


# ------------------------------------------------------------------- build
BACKTICK = re.compile(r'`([^`]+)`')


def promote_named(note, names, own_kind, other_kind):
    """Move the entries a row's *note* names to the front of the row.

    The task table's note is prose written by a human, and it often says
    exactly which entry to use -- "Prefer the hand-authored
    `skill-creator-plus` pack", "use `architect`", "Pair with
    `silent-failure-hunter`". Nine of the 73 rows name an entry their
    own lists omit, and in each case the note is the *only* place that
    curation is written down. Dropping it loses the instruction
    entirely: "create a skill" would keep ranking `skill-creator` above
    the `skill-creator-plus` pack the note says to prefer.

    A named entry is promoted to the front, keeping the rest of the
    row's order intact. Names that are not library entries are ignored
    -- `.tsx`, `.jsx` and `§7` are prose, not entries.
    """
    if not note:
        return names
    named = []
    for raw in BACKTICK.findall(note):
        # an entry name is a bare identifier: no spaces, dots or slashes
        if not re.fullmatch(r'[A-Za-z0-9_-]+', raw):
            continue
        if raw in own_kind and raw not in named:
            named.append(raw)
    if not named:
        return names
    rest = [n for n in names if n not in named]
    return named + rest


def build():
    lib_path = os.path.join(BASE, '.library_data.json')
    with open(lib_path, encoding='utf-8') as fh:
        lib = json.load(fh)

    skills = lib['skills']
    agents = lib['agents']
    excluded = lib['excluded_agents']

    skill_names = [s['name'] for s in skills]
    agent_names = [a['name'] for a in agents]
    tier_of, domain_of = assign_tiers(skill_names, agent_names)

    # ---------------------------------------------------------- skill records
    skill_records = []
    for s in skills:
        name = s['name']
        skill_dir = os.path.join(BASE, s['path'].rstrip('/'))
        skill_md = os.path.join(skill_dir, 'SKILL.md')
        meta, parse_ok, parse_error, text, raw = yaml_frontmatter(skill_md)

        desc = s.get('desc', '')
        metadata = meta.get('metadata') if isinstance(meta.get('metadata'), dict) else {}

        bundle = scan_bundle(skill_dir, text)

        raw_keys = sorted(meta.keys()) if meta else []
        allowed = meta.get('allowed-tools') if meta else None
        if allowed is None and raw:
            allowed = regex_field(raw, 'allowed-tools')
        front = {
            'name': meta.get('name', name) if meta else name,
            'description': desc,
            'allowed_tools': norm_tools(allowed),
            'disable_model_invocation': bool(
                meta.get('disable-model-invocation', False)) if meta else False,
            'user_invocable': bool(meta.get('user-invocable', True)) if meta else True,
            'license': (meta.get('license') or '') if meta else '',
            'version': (meta.get('version') or '') if meta else '',
            'compatibility': (meta.get('compatibility') or '') if meta else '',
            'metadata': metadata,
            'prompt_signals': prompt_signals(metadata),
            'parse_ok': parse_ok,
            'parse_error': parse_error,
            'raw_keys': raw_keys,
        }

        name_tokens = tokenize(name)
        desc_tokens = tokenize(desc)

        skill_records.append({
            'id': 'skill:%s' % name,
            'kind': 'skill',
            'name': name,
            'title': s.get('title', name),
            'desc': desc,
            'desc_source': s.get('desc_source', 'body'),
            'path': s['path'].rstrip('/'),
            'skill_md': s['path'].rstrip('/') + '/SKILL.md',
            # The path *inside* the library, not the absolute one it
            # happens to sit at. The server resolves it against its own
            # root, so an absolute path would be both wrong on another
            # machine and a leak of the machine that built the index.
            'abs_path': s['path'].rstrip('/'),
            'source': s.get('source', ''),
            'copies': s.get('copies', 1),
            'locale_only': s.get('locale_only', False),
            'rescued_from_tmp': s.get('rescued_from_tmp', False),
            'tier': tier_of[('skill', name)],
            'domain': domain_of.get(name, ''),
            'frontmatter': front,
            'bundle': bundle,
            'tokens': {
                'name': name_tokens,
                'desc': desc_tokens,
                'name_bigrams': bigrams(name_tokens),
            },
        })

    # ---------------------------------------------------------- agent records
    agent_records = []
    for a in agents:
        name = a['name']
        agent_file = os.path.join(BASE, a['path'])
        meta, parse_ok, parse_error, text, raw = yaml_frontmatter(agent_file)
        metadata = meta.get('metadata') if isinstance(meta.get('metadata'), dict) else {}

        desc = a.get('desc', '')
        name_tokens = tokenize(name)
        desc_tokens = tokenize(desc)

        # `tools` and `model` come from YAML when the frontmatter parsed, and
        # from the regex reader otherwise -- so `Explore` (whose block is not
        # valid YAML) still carries its tool allow-list.
        tools_v = meta.get('tools') if meta else None
        if tools_v is None and raw:
            tools_v = regex_field(raw, 'tools')
        model_v = meta.get('model') if meta else None
        if model_v is None and raw:
            model_v = regex_field(raw, 'model')
        mode_v = meta.get('mode') if meta else None
        if mode_v is None and raw:
            mode_v = regex_field(raw, 'mode')

        agent_records.append({
            'id': 'agent:%s' % name,
            'kind': 'agent',
            'name': name,
            'title': name,
            'desc': desc,
            'desc_source': a.get('desc_source', 'body'),
            'path': a['path'],
            # Relative to the library root, like `path`. See the note
            # on the skill records.
            'abs_path': a['path'],
            'source': a.get('source', ''),
            'copies': a.get('copies', 1),
            'ensemble': a.get('ensemble', ''),
            'tier': tier_of[('agent', name)],
            'domain': '',
            'frontmatter': {
                'name': meta.get('name', name) if meta else name,
                'description': desc,
                'tools': norm_tools(tools_v),
                'model': (model_v or ''),
                'mode': (mode_v or ''),
                'permission': meta.get('permission') if meta else None,
                'metadata': metadata,
                'prompt_signals': prompt_signals(metadata),
                'parse_ok': parse_ok,
                'parse_error': parse_error,
                'raw_keys': sorted(meta.keys()) if meta else [],
            },
            'bundle': {
                'file_count': 1,
                'total_bytes': len(text.encode('utf-8')),
                'files': [{'path': os.path.basename(agent_file),
                           'bytes': len(text.encode('utf-8'))}],
                'refs': [],
                'refs_total': 0,
                'refs_resolved': 0,
                'refs_dangling': 0,
            },
            'tokens': {
                'name': name_tokens,
                'desc': desc_tokens,
                'name_bigrams': bigrams(name_tokens),
            },
        })

    # ------------------------------------------------------------ collections
    domain_counts = {}
    for name in skill_names:
        d = domain_of.get(name, '')
        domain_counts.setdefault(d, []).append(name)

    domains = []
    for dom, _ in DOMAINS:
        names = sorted(domain_counts.get(dom, []))
        if not names:
            continue
        domains.append({
            'name': dom,
            'skill_count': len(names),
            'skills': names,
            'tier': 2 if dom in CORE_DOMAINS else 3,
        })

    # ---------------------------------------------------------- task index
    known_skills = set(skill_names)
    known_agents = set(agent_names)
    tasks = []
    dropped = []
    for task, sk, ag, note in TASKS:
        s_keep = [x for x in sk if x in known_skills]
        a_keep = [x for x in ag if x in known_agents]
        for x in sk:
            if x not in known_skills:
                dropped.append({'task': task, 'ref': x, 'kind': 'skill'})
        for x in ag:
            if x not in known_agents:
                dropped.append({'task': task, 'ref': x, 'kind': 'agent'})
        # The note is prose, but it carries curation the lists do not:
        # "Prefer the hand-authored `skill-creator-plus` pack", "use
        # `architect`". Nine of the 73 rows name an entry their lists
        # omit, and in every case the note is saying *this is the one to
        # use*. Those names are promoted to the front of the row.
        s_keep = promote_named(note, s_keep, known_skills, known_agents)
        a_keep = promote_named(note, a_keep, known_agents, known_skills)
        tasks.append({
            'task': task,
            # The order is the curation. The table lists the *primary*
            # skill first -- `api-design` for "Build an API",
            # `error-handling` for "Fix a failing build" -- and the note
            # says which one that is. Sorting the list away would throw
            # the curation out and leave the row's members ranked only by
            # whatever their names happen to score. Deduplicate, but keep
            # the order the table chose.
            'skills': list(dict.fromkeys(s_keep)),
            'agents': list(dict.fromkeys(a_keep)),
            'notes': note,
            # the row's content tokens, per alternative. Precomputed so
            # both servers match the row the same way.
            'content': task_content_sets(task),
        })

    # --------------------------------------------------------------- postings
    postings = {}
    for rec in skill_records + agent_records:
        bucket = postings.setdefault(rec['kind'], {})
        for t in set(rec['tokens']['name'] + rec['tokens']['desc']):
            bucket.setdefault(t, []).append(rec['id'])
    for kind in postings:
        for t in postings[kind]:
            postings[kind][t].sort()

    by_tier = {1: 0, 2: 0, 3: 0}
    for rec in skill_records:
        by_tier[rec['tier']] += 1

    index = {
        'schema_version': 1,
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        # There is deliberately no absolute root here. The index is
        # portable: the server resolves every path against its own root
        # at runtime, so an absolute path would be wrong on any machine
        # but the one that built the index -- and it would name that
        # machine in a file anyone can read.
        'source_index': {
            'path': '.library_data.json',
            'sha256': sha256_file(lib_path),
            'skills': len(skills),
            'agents': len(agents),
        },
        'counts': {
            'skills': len(skills),
            'agents': len(agents),
            'held_aside': len(excluded),
            'by_tier': {'1': by_tier[1] + len(agent_records),
                        '2': by_tier[2],
                        '3': by_tier[3]},
            'skill_by_tier': {'1': by_tier[1], '2': by_tier[2], '3': by_tier[3]},
        },
        # The packs this tree actually publishes. The list is a fixed
        # constant in `tiering.py`, but a tree may not hold all of them
        # -- the public tree drops the ones whose licence does not
        # permit redistribution -- so the index reports the packs that
        # are really here, not the ones the library once had.
        'packs': [p for p in PACKS if p in set(skill_names)],
        'core_domains': list(CORE_DOMAINS),
        'domains': domains,
        'tasks': tasks,
        'task_index_notes': {
            'rows': len(tasks),
            'dropped': dropped,
        },
        'skills': skill_records,
        'agents': agent_records,
        'held_aside': [
            {'name': e['name'], 'orchestrator': e.get('orchestrator', ''),
             'reason': e.get('reason', ''), 'path': e.get('path', ''),
             'source': e.get('source', '')}
            for e in excluded
        ],
        'search': {
            'fields': ['name', 'description', 'prompt_signals', 'domain', 'tasks'],
            'tokenizer_version': 2,
            'stopwords': sorted(STOPWORDS),
            'postings': postings,
        },
    }
    return index


def main():
    index = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # sort_keys + a trailing newline, so two runs over an unchanged library
    # differ only in `generated_at`.
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(index, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write('\n')
    os.replace(tmp, OUT)

    size = os.path.getsize(OUT)
    print('wrote %s' % os.path.relpath(OUT, BASE))
    print('  schema_version : %d' % index['schema_version'])
    print('  skills         : %d' % index['counts']['skills'])
    print('  agents         : %d' % index['counts']['agents'])
    print('  held aside     : %d' % index['counts']['held_aside'])
    print('  by tier        : %s' % index['counts']['by_tier'])
    print('  domains        : %d' % len(index['domains']))
    print('  tasks          : %d (%d refs dropped)'
          % (len(index['tasks']), len(index['task_index_notes']['dropped'])))
    print('  size           : %.1f KB' % (size / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
