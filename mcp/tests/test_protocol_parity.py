#!/usr/bin/env python3
"""The protocol revision tests, and the parity between the two halves.

The Python server and the TypeScript server both answer `initialize`,
and both must answer it the same way. A client that talks to one and
then the other must not see a different protocol -- so the two
implementations of the revision are compared directly, not only
through the agreement gate.

Checks:
  * the Python revision module behaves as the spec for the revisions
  * the TypeScript revision module agrees with it, function for
    function, on every input
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
BASE = os.path.dirname(MCP)
sys.path.insert(0, os.path.join(MCP, 'python'))

import protocol  # noqa: E402

TS_ENTRY = os.path.join(MCP, 'dist', 'index.js')
TS_PROTOCOL = os.path.join(MCP, 'dist', 'protocol.js')

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


def check_python_only():
    """The Python half, on its own."""
    check('python: the versions are listed newest first',
          protocol.SUPPORTED_PROTOCOL_VERSIONS[0] == protocol.CURRENT_PROTOCOL_VERSION)
    check('python: the default is 2025-11-25',
          protocol.DEFAULT_PROTOCOL_VERSION == '2025-11-25')
    check('python: the default is supported',
          protocol.DEFAULT_PROTOCOL_VERSION in protocol.SUPPORTED_PROTOCOL_VERSIONS)
    check('python: the versions are distinct',
          len(set(protocol.SUPPORTED_PROTOCOL_VERSIONS))
          == len(protocol.SUPPORTED_PROTOCOL_VERSIONS))

    for v in protocol.SUPPORTED_PROTOCOL_VERSIONS:
        check('python: %s is served as itself' % v,
              protocol.negotiate(v) == v)

    for bad in ('2999-01-01', '2025-11-26', '', None):
        check('python: %r gets the default' % (bad,),
              protocol.negotiate(bad) == protocol.DEFAULT_PROTOCOL_VERSION,
              str(protocol.negotiate(bad)))

    check('python: only the current revision is current',
          protocol.is_current(protocol.CURRENT_PROTOCOL_VERSION) is True
          and protocol.is_current(protocol.DEFAULT_PROTOCOL_VERSION) is False)

    for v in protocol.SUPPORTED_PROTOCOL_VERSIONS:
        if v == protocol.CURRENT_PROTOCOL_VERSION:
            continue
        check('python: %s gets no resultType' % v, protocol.result_type(v) == {})
        check('python: %s gets no cache fields' % v,
              protocol.cache_fields(v, 60_000, 'session') == {})

    check('python: the current revision gets resultType',
          protocol.result_type(protocol.CURRENT_PROTOCOL_VERSION)
          == {'resultType': 'complete'})
    check('python: the current revision gets ttlMs and cacheScope',
          protocol.cache_fields(protocol.CURRENT_PROTOCOL_VERSION, 60_000, 'session')
          == {'ttlMs': 60_000, 'cacheScope': 'session'})

    # ---- the cursor.
    c = protocol.encode_cursor('skill:tdd-workflow', 'write tests')
    check('python: a cursor round-trips',
          protocol.decode_cursor(c) == {'after': 'skill:tdd-workflow',
                                       'q': 'write tests'})
    check('python: a cursor is opaque',
          'tdd-workflow' not in c, c)
    check('python: a cursor is url-safe',
          all(ch.isalnum() or ch in '-_' for ch in c), c)
    check('python: an unreadable cursor is ignored',
          protocol.decode_cursor('not base64 at all !!!') is None)
    check('python: an empty cursor is ignored',
          protocol.decode_cursor('') is None and protocol.decode_cursor(None) is None)
    check('python: a cursor is bound to its query',
          protocol.cursor_matches(protocol.decode_cursor(c), 'write tests') is True
          and protocol.cursor_matches(protocol.decode_cursor(c), 'other') is False)


def drive_ts(requested):
    """Ask the TypeScript revision module to negotiate `requested`."""
    script = (
        "import {negotiate, isCurrent, resultType, cacheFields, "
        "SUPPORTED_PROTOCOL_VERSIONS, DEFAULT_PROTOCOL_VERSION, "
        "CURRENT_PROTOCOL_VERSION} from '%s';"
        "const r = %s;"
        "process.stdout.write(JSON.stringify({"
        "  versions: SUPPORTED_PROTOCOL_VERSIONS,"
        "  default: DEFAULT_PROTOCOL_VERSION,"
        "  current: CURRENT_PROTOCOL_VERSION,"
        "  negotiated: negotiate(r),"
        "  isCurrent: isCurrent(r),"
        "  resultType: resultType(r),"
        "  cacheFields: cacheFields(r, 60000, 'session'),"
        "}));"
    ) % (TS_PROTOCOL, json.dumps(requested))
    proc = subprocess.run(['node', '--input-type=module', '-e', script],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError('node failed: %s' % proc.stderr[-500:])
    return json.loads(proc.stdout)


def drive_ts_cursor(after, query):
    """Ask the TypeScript revision module to encode a cursor."""
    script = (
        "import {encodeCursor} from '%s';"
        "process.stdout.write(JSON.stringify(encodeCursor(%s, %s)));"
    ) % (TS_PROTOCOL, json.dumps(after), json.dumps(query))
    proc = subprocess.run(['node', '--input-type=module', '-e', script],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError('node failed: %s' % proc.stderr[-500:])
    return json.loads(proc.stdout)


def check_parity():
    """The two halves must agree, function for function."""
    if not os.path.isfile(TS_PROTOCOL):
        sys.stderr.write(
            'SKIP: the TypeScript build is missing (%s). Run `npm run build` '
            'in mcp/ first.\n' % TS_PROTOCOL)
        return

    cases = list(protocol.SUPPORTED_PROTOCOL_VERSIONS) + [
        '2999-01-01', '2025-11-26', '', None,
    ]
    for requested in cases:
        ts = drive_ts(requested)
        py_negotiated = protocol.negotiate(requested)
        check('parity: %r negotiates the same version' % (requested,),
              ts['negotiated'] == py_negotiated,
              'python %s, typescript %s' % (py_negotiated, ts['negotiated']))
        check('parity: %r reports the same currency' % (requested,),
              ts['isCurrent'] == protocol.is_current(py_negotiated))
        check('parity: %r yields the same resultType' % (requested,),
              ts['resultType'] == protocol.result_type(py_negotiated),
              'python %s, typescript %s'
              % (protocol.result_type(py_negotiated), ts['resultType']))
        check('parity: %r yields the same cache fields' % (requested,),
              ts['cacheFields'] == protocol.cache_fields(py_negotiated, 60_000, 'session'),
              'python %s, typescript %s'
              % (protocol.cache_fields(py_negotiated, 60_000, 'session'),
                 ts['cacheFields']))

    ts = drive_ts(protocol.DEFAULT_PROTOCOL_VERSION)
    check('parity: the supported versions are the same list',
          ts['versions'] == list(protocol.SUPPORTED_PROTOCOL_VERSIONS),
          'python %s, typescript %s'
          % (list(protocol.SUPPORTED_PROTOCOL_VERSIONS), ts['versions']))
    check('parity: the default is the same',
          ts['default'] == protocol.DEFAULT_PROTOCOL_VERSION)
    check('parity: the current revision is the same',
          ts['current'] == protocol.CURRENT_PROTOCOL_VERSION)

    # The cursor string itself. A cursor is opaque to the client, but
    # it is not opaque to the *other implementation*: a cursor the
    # Python server issued must work against the TypeScript server, or
    # a client that switched servers mid-pagination would lose its
    # place. So the two encoders must agree byte for byte.
    for after, query in (('skill:tdd-workflow', 'write tests'),
                         ('skill:a/b+c', 'a query? with & chars'),
                         ('', '')):
        py = protocol.encode_cursor(after, query)
        ts_c = drive_ts_cursor(after, query)
        check('parity: the cursor for %r is byte-identical' % (after,),
              ts_c == py,
              'python %r, typescript %r' % (py, ts_c))


def main():
    check_python_only()
    check_parity()

    if failures:
        sys.stderr.write('\n%d FAILURE(S) out of %d checks\n'
                         % (len(failures), checks))
        for f in failures:
            sys.stderr.write('  - %s\n' % f)
        return 1
    sys.stdout.write('\nPROTOCOL PARITY: PASS — all %d checks\n' % checks)
    return 0


if __name__ == '__main__':
    sys.exit(main())
