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
  * `tools/list` returns exactly 8 tools with inputSchema and annotations
  * `tools/call` returns content[0].text and structuredContent
  * an unknown method returns -32601
  * an unknown tool returns isError, not a transport crash
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


def drive(cmd, env=None):
    """Run one server and return its parsed responses, keyed by id."""
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
         'params': {'protocolVersion': '2025-06-18', 'capabilities': {},
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
    check('%s: tools/list returns exactly 8 tools' % label, len(tools) == 8,
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
