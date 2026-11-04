#!/usr/bin/env python3
"""The live end-to-end check: the real server, the real harness paths.

This drives the Python fallback over stdio exactly as an MCP host would,
and checks the behaviours the plan's verification section names:

  * `search_library` routes correctly
  * `get_skill` returns the FULL `math-olympiad` description -- the
    frontmatter truncation fix, which was impossible before it
  * an install dry-run writes nothing
  * the OpenCode agent frontmatter matches the live `architect.md` shape

It is a *live* check, so it touches the real harness directories when
`apply` is true. The dry-run part never does.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
ROOT = os.path.dirname(MCP)

ENV = {
    'PATH': '/usr/bin:/bin',
    'HOME': os.path.expanduser('~'),
    'SKILLS_LIBRARY_ROOT': ROOT,
}


def call(method, params, rid=1):
    req = {'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params}
    proc = subprocess.run(
        [sys.executable, os.path.join(MCP, 'python', 'server.py')],
        input=json.dumps(req) + '\n',
        capture_output=True, text=True, timeout=60, env=ENV,
    )
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get('id') == rid:
            return obj
    return {'error': (proc.stderr or proc.stdout)[-600:]}


def tool(name, args, rid=1):
    r = call('tools/call', {'name': name, 'arguments': args}, rid)
    res = r.get('result')
    if res is None:
        raise SystemExit('%s failed: %s' % (name, r))
    if res.get('isError'):
        raise SystemExit('%s errored: %s' % (name, res))
    return res.get('structuredContent', {})


def main():
    failures = []

    def check(label, ok, detail=''):
        print(('ok   ' if ok else 'FAIL ') + label
              + (('  -- ' + str(detail)) if detail else ''))
        if not ok:
            failures.append(label)

    # 1. the search routes the way the plan's verification expects
    for query, wanted in (('write a REST API', 'skill:api-design'),
                          ('competition math proof', 'skill:math-olympiad'),
                          ('accessibility audit WCAG', 'skill:accessibility'),
                          ('deploy to kubernetes', 'skill:kubernetes-patterns'),
                          ('remove dead code', 'skill:codehealth-mcp')):
        sc = tool('search_library', {'query': query, 'limit': 5})
        ids = [r['id'] for r in sc.get('results', [])]
        check('search: %r finds %s first' % (query, wanted),
              bool(ids) and ids[0] == wanted, ids[:3])

    # 2. the frontmatter fix survives into the server
    sc = tool('get_skill', {'id': 'skill:math-olympiad'})
    desc = (sc.get('frontmatter') or {}).get('description', '')
    check('get_skill: the math-olympiad description is complete',
          len(desc) > 500 and 'IMO' in desc and 'Putnam' in desc,
          '%d chars' % len(desc))
    body = sc.get('body') or ''
    check('get_skill: the math-olympiad body is returned', len(body) > 5000,
          '%d chars' % len(body))

    # 3. a dry run writes nothing
    target = os.path.expanduser('~/.puku-cli/skills')
    before = sorted(os.listdir(target)) if os.path.isdir(target) else []
    sc = tool('install_skills',
              {'harness': 'puku-cli', 'ids': ['skill:docker-patterns'],
               'apply': False})
    after = sorted(os.listdir(target)) if os.path.isdir(target) else []
    check('install: a dry run writes nothing', before == after,
          '%s -> %s' % (before, after))
    check('install: the dry run returns a plan',
          bool(sc.get('targets')) and sc.get('written') == 0,
          'targets=%d written=%d skipped=%d' % (
              len(sc.get('targets') or []), sc.get('written'),
              sc.get('skipped')))

    # 4. the OpenCode agent dialect matches the live file's shape
    live = os.path.expanduser('~/.config/opencode/agents/architect.md')
    if os.path.isfile(live):
        text = open(live, encoding='utf-8').read()
        check('opencode: the live agent declares a mode',
              'mode: subagent' in text)
        check('opencode: the live agent declares a permission matrix',
              'permission:' in text)

    # 5. a missing required argument is a tool error, not a crash
    r = call('tools/call',
             {'name': 'uninstall_skills', 'arguments': {'harness': 'opencode'}})
    res = r.get('result', {})
    text = ''
    if res.get('content'):
        text = res['content'][0].get('text', '')
    check('uninstall: a missing required argument is a tool error',
          res.get('isError') is True, str(res)[:160])
    check('uninstall: the error names the missing field',
          'names' in text, text[:160])

    print()
    if failures:
        print('%d LIVE CHECK(S) FAILED' % len(failures))
        for f in failures:
            print('  - %s' % f)
        return 1
    print('LIVE CHECK: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
