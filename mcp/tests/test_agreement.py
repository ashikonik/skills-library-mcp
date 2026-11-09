#!/usr/bin/env python3
"""The cross-implementation gate.

The single most valuable test in the project: the Python fallback is
what runs when the MCP SDK is unavailable, so a divergent fallback is
worse than no fallback.

Four comparisons, all of which must agree exactly:

  1. **Search results.** The same golden queries through both
     implementations must produce the identical ordered id list.
  2. **The tokenizer.** Every token in the corpus vocabulary must
     tokenize the same way in both.
  3. **Frontmatter.** The Python hand-rolled reader and the TypeScript
     `yaml` reader must agree on `name`, `description`, `allowed-tools`,
     `tools` and `model` for every skill and agent.
  4. **The tool surface.** Both servers must expose the same 8 tools
     with the same annotations.

The TypeScript side is driven through its built `dist/`, so the test
skips (rather than fails) when the project has not been built yet --
a fresh clone should not report a false failure.

**A skip is not a pass.** When the TypeScript build is missing the gate
compares nothing, and it exits non-zero saying INCOMPLETE rather than
PASS. A verification that did not check the thing it claims to check
must not report success.

Run with `--update-golden` to regenerate `golden/search_golden.json`.
That is deliberately a separate flag: regenerating the golden file to
make a test pass would defeat the point of having one.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
BASE = os.path.dirname(MCP)
PYTHON = sys.executable

sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))
sys.path.insert(0, HERE)

from queries import GOLDEN_QUERIES, NO_MATCH_QUERIES   # noqa: E402
from search import load_index                            # noqa: E402

GOLDEN = os.path.join(HERE, 'golden', 'search_golden.json')
TS_ENTRY = os.path.join(MCP, 'dist', 'index.js')

failures = []
skips = []

# `--update-golden` rewrites the golden file from the Python results.
# It is a maintenance mode, not a check: the TypeScript comparisons
# below it are not applicable, because the whole point is to record
# what one implementation currently produces before the other is
# compared against it. The public tree's assembler runs it in a tree
# with no TypeScript build at all.
UPDATING = '--update-golden' in sys.argv


def fail(msg):
    failures.append(msg)
    sys.stderr.write('FAIL: %s\n' % msg)


def ok(msg):
    sys.stdout.write('ok   %s\n' % msg)


def skip(msg):
    """Record a check that did not run.

    A skip is not a pass. The point of this gate is that the Python
    fallback and the TypeScript server agree; if the TypeScript build
    is missing, the gate compared nothing, and saying PASS would claim
    a guarantee it never checked.
    """
    skips.append(msg)
    sys.stderr.write('SKIP: %s\n' % msg)


# --------------------------------------------------------------- 1. search
def python_results(idx, queries):
    out = {}
    for q in queries:
        r = idx.search(q, limit=10)
        out[q] = {
            'ids': [x['id'] for x in r['results']],
            'scores': [x['score'] for x in r['results']],
            'total': r['total_matched'],
            # The count of the entries the relevance floor dropped.
            # It is part of the response, so the two implementations
            # have to agree on it: a divergence here is the same class
            # of bug as a divergence in the ids.
            'filtered_out': r['filtered_out'],
            'truncated': r['truncated'],
            # The note is the human-readable half of the same
            # quartet. It states the counts the numeric fields
            # carry -- "Showing 10 of 32 matches; 3 were below the
            # relevance floor" -- so a divergence in the note is a
            # divergence in the numbers, dressed as prose. If the
            # two engines disagree about which count is the
            # denominator, the note is where it shows.
            'note': r['note'],
        }
    return out


def ts_results(queries):
    """Run the built TypeScript search over the same queries."""
    script = os.path.join(HERE, '_ts_search.mjs')
    proc = subprocess.run(
        ['node', script, json.dumps(queries)],
        capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError('the TypeScript search failed:\n%s' % proc.stderr)
    return json.loads(proc.stdout)


def check_search(idx):
    py = python_results(idx, GOLDEN_QUERIES)

    # The golden file is written from the PYTHON results, and it is
    # written whether or not the TypeScript build is present: it
    # describes this corpus, and the public tree regenerates its own
    # before its build exists. The TypeScript comparison below is what
    # needs the build.
    if '--update-golden' in sys.argv:
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        with open(GOLDEN, 'w', encoding='utf-8') as fh:
            json.dump(py, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        ok('wrote the golden file')
    elif os.path.isfile(GOLDEN):
        with open(GOLDEN, encoding='utf-8') as fh:
            recorded = json.load(fh)
        drift = 0
        for q in GOLDEN_QUERIES:
            rec = recorded.get(q)
            if rec is None:
                fail('the golden file has no entry for %r' % q)
                drift += 1
            elif rec['ids'] != py[q]['ids']:
                fail('the golden file disagrees with the current search for %r\n'
                     '  golden : %s\n  current: %s'
                     % (q, rec['ids'][:5], py[q]['ids'][:5]))
                drift += 1
        if drift == 0:
            ok('the golden file matches the current search output')
    else:
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        with open(GOLDEN, 'w', encoding='utf-8') as fh:
            json.dump(py, fh, indent=1, sort_keys=True, ensure_ascii=False)
            fh.write('\n')
        ok('wrote the golden file')

    if UPDATING:
        return
    if not os.path.isfile(TS_ENTRY):
        skip('the TypeScript build is missing (%s). Run `npm run build` '
             'in mcp/ first.' % TS_ENTRY)
        return

    ts = ts_results(GOLDEN_QUERIES)

    mismatched = 0
    for q in GOLDEN_QUERIES:
        if py[q]['ids'] != ts[q]['ids']:
            fail('search mismatch for %r\n  python: %s\n  ts    : %s'
                 % (q, py[q]['ids'][:5], ts[q]['ids'][:5]))
            mismatched += 1
        elif py[q]['scores'] != ts[q]['scores']:
            fail('score mismatch for %r\n  python: %s\n  ts    : %s'
                 % (q, py[q]['scores'][:5], ts[q]['scores'][:5]))
            mismatched += 1
        elif py[q]['total'] != ts[q]['total']:
            fail('total mismatch for %r\n  python: %s\n  ts    : %s'
                 % (q, py[q]['total'], ts[q]['total']))
            mismatched += 1
        elif py[q]['filtered_out'] != ts[q]['filtered_out']:
            fail('filtered_out mismatch for %r\n  python: %s\n  ts    : %s'
                 % (q, py[q]['filtered_out'], ts[q]['filtered_out']))
            mismatched += 1
        elif py[q]['truncated'] != ts[q]['truncated']:
            fail('truncated mismatch for %r\n  python: %s\n  ts    : %s'
                 % (q, py[q]['truncated'], ts[q]['truncated']))
            mismatched += 1
        elif py[q]['note'] != ts[q]['note']:
            fail('note mismatch for %r\n  python: %s\n  ts    : %s'
                 % (q, py[q]['note'], ts[q]['note']))
            mismatched += 1
    if mismatched == 0:
        ok('search: %d queries produce identical id lists, scores and counts'
           % len(GOLDEN_QUERIES))

    # The three no-match queries must return nothing, in both.
    for q in NO_MATCH_QUERIES:
        if py[q]['ids']:
            fail('a query with no library match returned results: %r -> %s'
                 % (q, py[q]['ids'][:3]))
        if ts[q]['ids']:
            fail('the TypeScript search returned results for a no-match '
                 'query: %r -> %s' % (q, ts[q]['ids'][:3]))
    ok('no-match queries return an empty result set in both')


# ------------------------------------------------------------ 2. tokenizer
def check_tokenizer(idx):
    """Every token in the corpus vocabulary must tokenize the same way."""
    vocab = set()
    for e in idx.entries:
        vocab.update(e['tokens']['name'])
        vocab.update(e['tokens']['desc'])
    vocab = sorted(vocab)
    sys.stdout.write('     %d vocabulary tokens\n' % len(vocab))

    script = os.path.join(HERE, '_ts_tokenize.mjs')
    if UPDATING:
        return
    if not os.path.isfile(TS_ENTRY):
        skip('the TypeScript build is missing.')
        return
    proc = subprocess.run(
        ['node', script, json.dumps(vocab)],
        capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        fail('the TypeScript tokenizer failed:\n%s' % proc.stderr)
        return

    from build_index import tokenize as py_tokenize  # local import
    from build_index import head_tokens as py_head_tokens  # local import

    ts_map = json.loads(proc.stdout)
    ts_heads = ts_map.pop('__heads__', {})
    bad = 0
    for t in vocab:
        py = py_tokenize(t)
        ts = ts_map.get(t)
        if py != ts:
            fail('tokenizer mismatch for %r: python %s, ts %s' % (t, py, ts))
            bad += 1
            if bad > 20:
                break
    if bad == 0:
        ok('tokenizer: %d vocabulary tokens agree' % len(vocab))

    # The head-noun set decides whether a task row fires, so the two
    # implementations must agree on it as well.
    bad = 0
    for t in vocab:
        py = sorted(py_head_tokens(t))
        ts = ts_heads.get(t)
        if py != ts:
            fail('head-token mismatch for %r: python %s, ts %s' % (t, py, ts))
            bad += 1
            if bad > 20:
                break
    if bad == 0:
        ok('head tokens: %d vocabulary tokens agree' % len(vocab))


# ---------------------------------------------------------- 3. frontmatter
def check_frontmatter(idx):
    """The two readers must agree on every field the library stores."""
    script = os.path.join(HERE, '_ts_frontmatter.mjs')
    if UPDATING:
        return
    if not os.path.isfile(TS_ENTRY):
        skip('the TypeScript build is missing.')
        return

    paths = []
    for e in idx.entries:
        paths.append(e['path'] if e['kind'] == 'skill' else e['path'])
    proc = subprocess.run(
        ['node', script, json.dumps(paths)],
        capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        fail('the TypeScript frontmatter reader failed:\n%s' % proc.stderr)
        return
    ts_map = json.loads(proc.stdout)

    from frontmatter import field_of, norm_tools, parse_frontmatter

    bad = 0
    for e in idx.entries:
        rel = e['path'] if e['kind'] == 'skill' else e['path']
        abs_path = os.path.join(BASE, rel)
        data, parse_ok, parse_error, text, raw = parse_frontmatter(abs_path)
        py = {
            'name': field_of(raw, data, 'name'),
            'description': ' '.join(field_of(raw, data, 'description').split()),
            'tools': norm_tools(data.get('tools')) if data.get('tools') is not None
                     else norm_tools(field_of(raw, data, 'tools')),
            'model': field_of(raw, data, 'model'),
            'parse_ok': parse_ok,
        }
        ts = ts_map.get(rel)
        if ts is None:
            fail('the TypeScript reader returned nothing for %s' % rel)
            bad += 1
            continue
        for key in ('name', 'description', 'tools', 'model'):
            if py[key] != ts[key]:
                fail('frontmatter mismatch on %s for %r\n  python: %r\n  ts    : %r'
                     % (rel, key, py[key], ts[key]))
                bad += 1
                if bad > 20:
                    break
        if bad > 20:
            break
    if bad == 0:
        ok('frontmatter: %d documents agree on name, description, tools, model'
           % len(idx.entries))


# ---------------------------------------------------------- 4. tool surface
def check_tools():
    """Both servers must expose the same 8 tools with the same annotations.

    The comparison is against what a *client* receives, not against the
    module-level constant. The descriptions carry the library's size,
    and that number is filled in from the index when the server starts
    -- so the constant holds a placeholder and the served list holds the
    real count. Comparing the constant would compare a placeholder with
    a number and report a difference that no client would ever see.
    """
    script = os.path.join(HERE, '_ts_tools.mjs')
    if UPDATING:
        return
    if not os.path.isfile(TS_ENTRY):
        skip('the TypeScript build is missing.')
        return

    from server import Server

    py_tools = Server().tools

    proc = subprocess.run(
        ['node', script],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        fail('the TypeScript tool list failed:\n%s' % proc.stderr)
        return
    ts_tools = json.loads(proc.stdout)

    py_names = [t['name'] for t in py_tools]
    ts_names = [t['name'] for t in ts_tools]
    if py_names != ts_names:
        fail('the tool lists differ:\n  python: %s\n  ts    : %s'
             % (py_names, ts_names))
        return
    ok('tool surface: the same %d tools in the same order' % len(py_names))

    by_name = {t['name']: t for t in ts_tools}
    for t in py_tools:
        ts = by_name[t['name']]
        for field in ('title', 'description'):
            if t[field] != ts.get(field):
                fail('tool %s: %s differs\n  python: %r\n  ts    : %r'
                     % (t['name'], field, t[field], ts.get(field)))
        if t['annotations'] != ts.get('annotations'):
            fail('tool %s: annotations differ\n  python: %s\n  ts    : %s'
                 % (t['name'], t['annotations'], ts.get('annotations')))

    expected = {'search_library', 'get_skill', 'get_agent', 'get_skill_bundle',
                'list_library', 'install_skills', 'install_agents',
                'uninstall_skills', 'uninstall_agents', 'policy_get'}
    if set(py_names) != expected:
        fail('the tool set is not the expected %d: %s'
             % (len(expected), sorted(py_names)))
    for t in py_tools:
        if len(t['name']) > 17:
            fail('tool name %r is longer than 17 characters' % t['name'])
    ok('tool surface: titles, descriptions and annotations agree')


def check_cursor(idx):
    """Both servers must paginate the same way.

    The cursor is opaque, but it is not opaque to *the other
    implementation*: a cursor the Python server issued must work
    against the TypeScript server, or a client that switched servers
    mid-pagination would lose its place. So the cursor string itself
    is compared -- if the two encoders disagree by a single byte, the
    cursors do not cross over.
    """
    script = os.path.join(HERE, '_ts_cursor.mjs')
    if UPDATING:
        return
    if not os.path.isfile(TS_ENTRY):
        skip('the TypeScript build is missing.')
        return

    from server import Server

    query = 'code review refactoring'
    limit = 3

    proc = subprocess.run(
        ['node', script, query, str(limit)],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        fail('the TypeScript cursor failed:\n%s' % proc.stderr[-800:])
        return
    ts = json.loads(proc.stdout)

    # The Python server, under the newer revision, the same way.
    srv = Server()
    srv.protocol_version = '2026-07-28'
    page1 = srv.tool_search_library({'query': query, 'limit': limit})
    cursor = page1.get('nextCursor')
    page2 = srv.tool_search_library(
        {'query': query, 'limit': limit, 'cursor': cursor}) if cursor else {'results': []}

    py_ids1 = [r['id'] for r in page1.get('results', [])]
    py_ids2 = [r['id'] for r in page2.get('results', [])]

    if py_ids1 != ts['page1']:
        fail('cursor: the first page differs\n  python: %s\n  ts    : %s'
             % (py_ids1, ts['page1']))
        return
    ok('cursor: the first page agrees (%d results)' % len(py_ids1))

    if cursor != ts['cursor']:
        fail('cursor: the cursor string differs\n  python: %r\n  ts    : %r'
             % (cursor, ts['cursor']))
        return
    ok('cursor: the cursor string is byte-identical')

    if py_ids2 != ts['page2']:
        fail('cursor: the second page differs\n  python: %s\n  ts    : %s'
             % (py_ids2, ts['page2']))
        return
    ok('cursor: the second page agrees (%d results)' % len(py_ids2))

    if not cursor:
        fail('cursor: no cursor was issued')
        return
    if set(py_ids1) & set(py_ids2):
        fail('cursor: the second page repeats the first: %s'
             % sorted(set(py_ids1) & set(py_ids2)))
        return
    ok('cursor: the pages do not overlap')


def main():
    idx = load_index()
    check_search(idx)
    check_tokenizer(idx)
    check_frontmatter(idx)
    check_tools()
    check_cursor(idx)

    if failures:
        sys.stderr.write('\n%d FAILURE(S)\n' % len(failures))
        return 1
    if UPDATING:
        sys.stdout.write('\nGOLDEN FILE REWRITTEN — the TypeScript '
                         'comparisons were not run.\n')
        return 0
    if skips:
        # The gate did not run in full. Saying PASS here would claim a
        # guarantee that was never checked -- and the whole point of
        # this test is that the two implementations agree, which is
        # only knowable if both were compared.
        sys.stderr.write(
            '\nAGREEMENT: INCOMPLETE — %d check(s) did not run:\n' % len(skips))
        for s in skips:
            sys.stderr.write('  - %s\n' % s)
        sys.stderr.write(
            'Build the TypeScript server (`npm run build` in mcp/) and\n'
            'run this again. A skipped check is not a passing check.\n')
        return 1
    sys.stdout.write('\nAGREEMENT: PASS — the Python and TypeScript servers agree\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
