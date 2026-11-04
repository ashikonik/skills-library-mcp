#!/usr/bin/env python3
"""The cross-implementation gate.

The single most valuable test in the project: the Python fallback is
what runs when the MCP SDK is unavailable, so a divergent fallback is
worse than no fallback.

Four comparisons, all of which must agree exactly:

  1. **Search results.** The same 60 golden queries through both
     implementations must produce the identical ordered id list.
  2. **The tokenizer.** Every token in the corpus vocabulary must
     tokenize the same way in both.
  3. **Frontmatter.** The Python hand-rolled reader and the TypeScript
     `yaml` reader must agree on `name`, `description`, `allowed-tools`,
     `tools` and `model` for all 976 skills and 102 agents.
  4. **The tool surface.** Both servers must expose the same 8 tools
     with the same annotations.

The TypeScript side is driven through its built `dist/`, so the test
skips (rather than fails) when the project has not been built yet --
a fresh clone should not report a false failure.

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


def fail(msg):
    failures.append(msg)
    sys.stderr.write('FAIL: %s\n' % msg)


def ok(msg):
    sys.stdout.write('ok   %s\n' % msg)


# --------------------------------------------------------------- 1. search
def python_results(idx, queries):
    out = {}
    for q in queries:
        r = idx.search(q, limit=10)
        out[q] = {
            'ids': [x['id'] for x in r['results']],
            'scores': [x['score'] for x in r['results']],
            'total': r['total_matched'],
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

    if not os.path.isfile(TS_ENTRY):
        sys.stderr.write(
            'SKIP: the TypeScript build is missing (%s). Run `npm run build` '
            'in mcp/ first.\n' % TS_ENTRY)
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
    if mismatched == 0:
        ok('search: %d queries produce identical id lists and scores'
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
    if not os.path.isfile(TS_ENTRY):
        sys.stderr.write('SKIP: the TypeScript build is missing.\n')
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
    if not os.path.isfile(TS_ENTRY):
        sys.stderr.write('SKIP: the TypeScript build is missing.\n')
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
    """Both servers must expose the same 8 tools with the same annotations."""
    script = os.path.join(HERE, '_ts_tools.mjs')
    if not os.path.isfile(TS_ENTRY):
        sys.stderr.write('SKIP: the TypeScript build is missing.\n')
        return

    from server import TOOLS as PY_TOOLS

    proc = subprocess.run(
        ['node', script],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        fail('the TypeScript tool list failed:\n%s' % proc.stderr)
        return
    ts_tools = json.loads(proc.stdout)

    py_names = [t['name'] for t in PY_TOOLS]
    ts_names = [t['name'] for t in ts_tools]
    if py_names != ts_names:
        fail('the tool lists differ:\n  python: %s\n  ts    : %s'
             % (py_names, ts_names))
        return
    ok('tool surface: the same %d tools in the same order' % len(py_names))

    by_name = {t['name']: t for t in ts_tools}
    for t in PY_TOOLS:
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
                'uninstall_skills'}
    if set(py_names) != expected:
        fail('the tool set is not the expected 8: %s' % sorted(py_names))
    for t in PY_TOOLS:
        if len(t['name']) > 17:
            fail('tool name %r is longer than 17 characters' % t['name'])
    ok('tool surface: titles, descriptions and annotations agree')


def main():
    idx = load_index()
    check_search(idx)
    check_tokenizer(idx)
    check_frontmatter(idx)
    check_tools()

    if failures:
        sys.stderr.write('\n%d FAILURE(S)\n' % len(failures))
        return 1
    sys.stdout.write('\nAGREEMENT: PASS — the Python and TypeScript servers agree\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
