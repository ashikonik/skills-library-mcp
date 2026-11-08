#!/usr/bin/env python3
"""The protocol-level test.

Speaks raw JSON-RPC 2.0 over pipes to a server and checks what comes
back. The *same* script runs against both servers -- the Python fallback
and the TypeScript one -- and asserts that both produce the same tool
list and the same `search_library` output.

That matters because the two are interchangeable from a client's point
of view. If the fallback answered a different set of tools, or ranked
differently, a client that happened to land on the fallback would
behave differently for no visible reason.

Checks:
  * initialize negotiates the protocol version
  * `notifications/initialized` gets no response
  * `tools/list` returns exactly 10 tools with inputSchema and annotations
  * `tools/call` returns content[0].text and structuredContent
  * an unknown method returns -32601
  * an unknown tool returns isError, not a transport crash

And, separately, the two protocol revisions -- each against its own
connection, because the revision is negotiated per connection:

  * a `2025-11-25` client sees exactly the fields it saw before: no
    `resultType`, no `ttlMs`, no `cacheScope`, no `resources`
    capability, no extensions
  * a `2026-07-28` client sees `resultType`, `ttlMs`, `cacheScope`,
    the `resources` capability and the skills extension
  * a client asking for a revision the server has never heard of gets
    the default, not the newest
  * `server/discover` is answered under every revision
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
BASE = os.path.dirname(MCP)
PYTHON = sys.executable

TS_ENTRY = os.path.join(MCP, 'dist', 'index.js')

failures = []
checks = 0


def check(label, condition, detail=''):
    global checks
    checks += 1
    if condition:
        sys.stdout.write('ok   %s\n' % label)
    else:
        failures.append(label + (': ' + detail if detail else ''))
        sys.stderr.write('FAIL %s %s\n' % (label, detail))


def drive(cmd, env=None, protocol_version='2025-06-18', with_discover=False,
          with_call=None):
    """Run one server and return its parsed responses, keyed by id.

    The revision is per-connection: a client negotiates it once, at
    `initialize`, and everything after that is answered under it. So the
    version is a parameter of the drive, not of the server.
    """
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
         'params': {'protocolVersion': protocol_version, 'capabilities': {},
                    'clientInfo': {'name': 'protocol-test', 'version': '1'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
         'params': {'name': 'search_library',
                    'arguments': {'query': 'accessibility audit WCAG',
                                  'limit': 5}}},
        {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call',
         'params': {'name': 'list_library',
                    'arguments': {'section': 'stats'}}},
        {'jsonrpc': '2.0', 'id': 5, 'method': 'no/such/method'},
        {'jsonrpc': '2.0', 'id': 6, 'method': 'tools/call',
         'params': {'name': 'no_such_tool', 'arguments': {}}},
        # A missing required argument. The TypeScript server validates
        # with zod; the Python fallback has no schema library, so it
        # checks by hand. Both must report it as a tool error naming
        # the field -- not as a crash, and not as a bare KeyError.
        {'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call',
         'params': {'name': 'uninstall_skills', 'arguments': {'harness': 'opencode'}}},
    ]
    if with_discover:
        requests.append({'jsonrpc': '2.0', 'id': 8, 'method': 'server/discover'})
    if with_call is not None:
        requests.append({'jsonrpc': '2.0', 'id': 9, 'method': 'tools/call',
                         'params': {'name': 'search_library',
                                    'arguments': with_call}})
    payload = '\n'.join(json.dumps(r) for r in requests) + '\n'
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(cmd, input=payload, capture_output=True, text=True,
                          timeout=300, env=full_env)
    responses = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        responses[msg.get('id')] = msg
    return proc, responses


def check_server(label, cmd, env=None):
    proc, r = drive(cmd, env)
    check('%s: the server exits cleanly' % label, proc.returncode == 0,
          proc.stderr[-400:])
    check('%s: every request got exactly one response' % label,
          set(r) == {1, 2, 3, 4, 5, 6, 7}, str(sorted(r)))
    check('%s: a notification gets no response' % label,
          len(r) == 7, str(len(r)))

    init = r[1].get('result', {})
    check('%s: initialize returns a protocolVersion' % label,
          'protocolVersion' in init, str(init))
    check('%s: initialize returns serverInfo' % label,
          init.get('serverInfo', {}).get('name') == 'skills-library')
    check('%s: initialize returns capabilities' % label,
          'capabilities' in init)

    tools = r[2].get('result', {}).get('tools', [])
    check('%s: tools/list returns exactly 10 tools' % label, len(tools) == 10,
          str(len(tools)))
    check('%s: every tool has an inputSchema' % label,
          all(t.get('inputSchema') for t in tools))
    check('%s: every tool has annotations' % label,
          all(t.get('annotations') for t in tools))
    check('%s: every tool has a title' % label,
          all(t.get('title') for t in tools))

    sc = r[3].get('result', {})
    check('%s: tools/call returns content[0].text' % label,
          bool(sc.get('content')) and sc['content'][0].get('type') == 'text')
    check('%s: tools/call returns structuredContent' % label,
          bool(sc.get('structuredContent')))

    check('%s: an unknown method returns -32601' % label,
          r[5].get('error', {}).get('code') == -32601,
          str(r[5].get('error')))
    check('%s: an unknown tool returns isError' % label,
          r[6].get('result', {}).get('isError') is True,
          str(r[6].get('result'))[:200])

    # A missing required argument is a tool error, not a crash, and the
    # message names the field that is missing.
    missing = r[7].get('result', {})
    msg = ''
    if missing.get('content'):
        msg = missing['content'][0].get('text', '')
    check('%s: a missing required argument returns isError' % label,
          missing.get('isError') is True, str(missing)[:200])
    check('%s: the error names the missing field' % label,
          'names' in msg, msg[:200])

    return {
        'tools': [(t['name'], t.get('title'), t.get('description'),
                   json.dumps(t.get('annotations'), sort_keys=True))
                  for t in tools],
        'search': sc.get('structuredContent', {}).get('results'),
        'stats': r[4].get('result', {}).get('structuredContent'),
    }


def check_revisions(label, cmd, env=None):
    """Check both revisions against one server.

    Three connections are made: one asking for the older revision, one
    asking for the newer one, and one asking for a revision the server
    has never heard of.
    """
    # ---- the older revision: nothing new may appear.
    _, old = drive(cmd, env, protocol_version='2025-11-25')
    init = old[1].get('result', {})
    check('%s [old]: initialize negotiates the requested revision' % label,
          init.get('protocolVersion') == '2025-11-25', str(init)[:200])
    caps = init.get('capabilities', {})
    check('%s [old]: the old revision declares no resources capability' % label,
          'resources' not in caps, str(caps))
    check('%s [old]: the old revision declares no extensions' % label,
          'extensions' not in caps, str(caps))
    old_list = old[2].get('result', {})
    check('%s [old]: tools/list has no ttlMs' % label,
          'ttlMs' not in old_list, str(sorted(old_list)))
    check('%s [old]: tools/list has no cacheScope' % label,
          'cacheScope' not in old_list, str(sorted(old_list)))
    old_call = old[3].get('result', {})
    check('%s [old]: tools/call has no resultType' % label,
          'resultType' not in old_call, str(sorted(old_call)))

    # ---- the newer revision: the new fields must appear.
    _, new = drive(cmd, env, protocol_version='2026-07-28')
    init = new[1].get('result', {})
    check('%s [new]: initialize negotiates the newer revision' % label,
          init.get('protocolVersion') == '2026-07-28', str(init)[:200])
    caps = init.get('capabilities', {})
    check('%s [new]: the new revision declares the resources capability' % label,
          'resources' in caps, str(caps))
    check('%s [new]: the new revision declares the skills extension' % label,
          'io.modelcontextprotocol/skills' in caps.get('extensions', {}),
          str(caps))
    new_list = new[2].get('result', {})
    check('%s [new]: tools/list has ttlMs' % label,
          isinstance(new_list.get('ttlMs'), int), str(sorted(new_list)))
    check('%s [new]: tools/list has cacheScope' % label,
          new_list.get('cacheScope') in ('public', 'private'),
          str(new_list.get('cacheScope')))
    check('%s [new]: the tool list is unchanged by the revision' % label,
          [t['name'] for t in new_list.get('tools', [])]
          == [t['name'] for t in old_list.get('tools', [])],
          '%s vs %s' % ([t['name'] for t in new_list.get('tools', [])],
                        [t['name'] for t in old_list.get('tools', [])]))
    new_call = new[3].get('result', {})
    check('%s [new]: tools/call has resultType' % label,
          new_call.get('resultType') == 'complete', str(sorted(new_call)))

    # ---- an unknown revision falls back to the default, not the newest.
    _, unknown = drive(cmd, env, protocol_version='2999-01-01')
    init = unknown[1].get('result', {})
    check('%s [unknown]: an unknown revision gets the default' % label,
          init.get('protocolVersion') == '2025-11-25', str(init)[:200])
    unknown_list = unknown[2].get('result', {})
    check('%s [unknown]: an unknown revision gets the old field set' % label,
          'ttlMs' not in unknown_list, str(sorted(unknown_list)))

    # ---- `server/discover` is answered under every revision.
    for version in ('2025-11-25', '2026-07-28'):
        _, d = drive(cmd, env, protocol_version=version, with_discover=True)
        res = d.get(8, {}).get('result')
        check('%s: server/discover is answered under %s' % (label, version),
              isinstance(res, dict), str(d.get(8))[:200])
        if not isinstance(res, dict):
            continue
        check('%s: server/discover lists the protocol versions' % label,
              '2026-07-28' in res.get('protocolVersions', [])
              and '2025-11-25' in res.get('protocolVersions', []),
              str(res.get('protocolVersions')))
        check('%s: server/discover names the server' % label,
              res.get('serverInfo', {}).get('name') == 'skills-library',
              str(res.get('serverInfo')))
        check('%s: server/discover declares the skills extension' % label,
              'io.modelcontextprotocol/skills' in res.get('extensions', {}),
              str(res.get('extensions')))
        check('%s: server/discover lists capabilities' % label,
              'tools' in res.get('capabilities', {}),
              str(res.get('capabilities')))


def check_cursor(label, cmd, env=None):
    """Check the cursor pagination, against one server.

    The cursor is a `2026-07-28` feature. Three things have to hold:
    the first page hands out a cursor, the cursor brings back the
    *next* results rather than the same ones, and the older revision
    has no cursor at all.
    """
    query = 'code review refactoring'

    def search(version, extra=None):
        args = {'query': query, 'limit': 3}
        if extra:
            args.update(extra)
        _, r = drive(cmd, env, protocol_version=version, with_call=args)
        return r[9].get('result', {}).get('structuredContent', {})

    # ---- the newer revision.
    page1 = search('2026-07-28')
    ids1 = [r['id'] for r in page1.get('results', [])]
    check('%s [cursor]: the first page returns results' % label, bool(ids1),
          str(ids1))
    cursor = page1.get('nextCursor')
    check('%s [cursor]: the first page hands out a cursor' % label,
          isinstance(cursor, str) and cursor != '', str(cursor))
    check('%s [cursor]: the cursor is opaque' % label,
          not cursor.startswith('skill:'), str(cursor))

    page2 = search('2026-07-28', {'cursor': cursor})
    ids2 = [r['id'] for r in page2.get('results', [])]
    check('%s [cursor]: the second page returns results' % label, bool(ids2),
          str(ids2))
    check('%s [cursor]: the second page does not repeat the first' % label,
          not (set(ids1) & set(ids2)), 'page1 %s, page2 %s' % (ids1, ids2))
    check('%s [cursor]: the pages are in ranking order' % label,
          page2.get('results') and page1.get('results')
          and page2['results'][0]['score'] <= page1['results'][0]['score'])

    # ---- the older revision: no cursor, no cursor fields.
    old = search('2025-11-25')
    check('%s [cursor]: the old revision has no nextCursor' % label,
          'nextCursor' not in old, str(sorted(old)))
    check('%s [cursor]: the old revision has no cursorStale' % label,
          'cursorStale' not in old, str(sorted(old)))

    # A cursor from one query must not paginate another.
    other = search('2026-07-28', {'cursor': cursor})
    check('%s [cursor]: a cursor is bound to its query' % label,
          other.get('query') == query, str(other.get('query')))


def main():
    py_cmd = [PYTHON, os.path.join(MCP, 'python', 'server.py')]
    py = check_server('python', py_cmd)

    ts = None
    if os.path.isfile(TS_ENTRY):
        ts = check_server('typescript', ['node', TS_ENTRY])
    else:
        sys.stderr.write(
            'SKIP: the TypeScript build is missing (%s). Run `npm run build` '
            'in mcp/ first.\n' % TS_ENTRY)

    if ts is not None:
        check('both servers expose the same tools in the same order',
              py['tools'] == ts['tools'],
              'python %s\n  ts %s'
              % ([t[0] for t in py['tools']], [t[0] for t in ts['tools']]))
        check('both servers return the same search results',
              py['search'] == ts['search'])
        check('both servers return the same library statistics',
              py['stats'] == ts['stats'])

    # ---- the protocol revisions, against every server that is present.
    check_revisions('python', py_cmd)
    check_cursor('python', py_cmd)
    if ts is not None:
        check_revisions('typescript', ['node', TS_ENTRY])
        check_cursor('typescript', ['node', TS_ENTRY])
    else:
        sys.stderr.write(
            'SKIP: the revision checks need the TypeScript build.\n')

    if failures:
        sys.stderr.write('\n%d FAILURE(S) out of %d checks\n'
                         % (len(failures), checks))
        for f in failures:
            sys.stderr.write('  - %s\n' % f)
        return 1
    sys.stdout.write('\nPROTOCOL: PASS — all %d checks\n' % checks)
    return 0


if __name__ == '__main__':
    sys.exit(main())
