#!/usr/bin/env python3
"""The Skills extension: its rules, and the parity of the two halves.

The extension (`io.modelcontextprotocol/skills`) is what lets a client
discover this library's skills as *skills* rather than as tools. It has
four methods, and every one of them has rules a client would notice if
they were broken:

  * `skills/list` -- metadata plus a complete manifest, never a body,
    never a partial manifest.
  * `skills/get` -- by URI; `-32602` for a URI the server did not issue.
  * `resources/read` -- the bytes, verified against the manifest.
  * `resources/directory/read` -- direct children only.

Two things are checked here.

**The rules.** The extension is checked against the specification:
every skill's manifest is complete, every digest matches the bytes on
disk, the final URI segment is the skill's name, and the names and
descriptions conform to the Agent Skills rules.

**The parity.** The TypeScript server and the Python fallback answer
these four methods, and they must answer them identically -- the same
entries, the same cursors, the same errors. A client that talks to one
and then the other must not see a different library.

The TypeScript side is driven through its built `dist/`, so the parity
checks skip (rather than fail) when the project has not been built --
but a skip is reported as incomplete, never as a pass.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
BASE = os.path.dirname(MCP)
sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))

import protocol  # noqa: E402
import skills_extension  # noqa: E402
from server import Server  # noqa: E402

TS_ENTRY = os.path.join(MCP, 'dist', 'index.js')
TS_SKILLS = os.path.join(HERE, '_ts_skills.mjs')

# The Agent Skills naming rule: lowercase, digits and hyphens, no
# leading, trailing or doubled hyphen.
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

failures = []
checks = 0
skips = []


def check(label, condition, detail=''):
    global checks
    checks += 1
    if condition:
        sys.stdout.write('ok   %s\n' % label)
    else:
        failures.append(label + (': ' + detail if detail else ''))
        sys.stderr.write('FAIL %s %s\n' % (label, detail))


def skip(label):
    """Record a check that did not run.

    A skip is not a pass. The gate below compares two implementations;
    if one of them is not there, nothing was compared, and saying
    PASS would claim a guarantee that was never checked.
    """
    skips.append(label)
    sys.stderr.write('SKIP %s\n' % label)


def new_revision_server():
    """A Python server that has negotiated the newer revision."""
    srv = Server()
    srv.handle({
        'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
        'params': {
            'protocolVersion': protocol.CURRENT_PROTOCOL_VERSION,
            'capabilities': {},
            'clientInfo': {'name': 'test', 'version': '1.0.0'},
        },
    })
    return srv


def call(srv, method, params=None):
    """One call, as `(result, error)`."""
    response = srv.handle({
        'jsonrpc': '2.0', 'id': 9, 'method': method, 'params': params or {},
    })
    if 'error' in response:
        return None, response['error']
    return response.get('result'), None


# ------------------------------------------------------------- the rules
def check_the_rules(srv):
    """The extension's own rules, checked against the index and the disk."""
    index = srv.index

    check('the index carries an extension view of every skill',
          all('skills' in s for s in index['skills']),
          '%d skills without one' % sum(1 for s in index['skills']
                                        if 'skills' not in s))

    bad_name = []
    bad_desc = []
    bad_uri = []
    incomplete = []
    for s in index['skills']:
        entry = s['skills']
        if not NAME_RE.match(entry['name']) or not 1 <= len(entry['name']) <= 64:
            bad_name.append(entry['name'])
        if not 1 <= len(entry['description']) <= 1024:
            bad_desc.append((s['name'], len(entry['description'])))
        # The final segment of the URI must be the skill's name.
        if entry['uri'] != 'skill://%s/SKILL.md' % entry['name']:
            bad_uri.append((s['name'], entry['uri']))
        # The manifest must include SKILL.md and every bundle file,
        # exactly once.
        uris = [r['uri'] for r in entry['resources']]
        if len(uris) != len(set(uris)):
            incomplete.append((s['name'], 'duplicate'))
        elif entry['uri'] not in uris:
            incomplete.append((s['name'], 'no SKILL.md'))
        elif len(uris) != s['bundle']['file_count']:
            incomplete.append((s['name'], '%d of %d files'
                               % (len(uris), s['bundle']['file_count'])))
    check('every served name conforms to the Agent Skills rules',
          not bad_name, str(bad_name[:5]))
    check('every served description is within 1024 characters',
          not bad_desc, str(bad_desc[:5]))
    check('every skill URI ends in the skill\'s own name',
          not bad_uri, str(bad_uri[:5]))
    check('every manifest is complete and has no duplicates',
          not incomplete, str(incomplete[:5]))

    # The digests must match the bytes on disk. The whole point of the
    # manifest is that a host can verify what it gets.
    bad_digest = []
    for s in index['skills']:
        for f in s['bundle']['files']:
            path = os.path.join(BASE, s['path'], f['path'])
            if not os.path.isfile(path):
                bad_digest.append((s['name'], f['path'], 'missing'))
                continue
            import hashlib
            with open(path, 'rb') as fh:
                actual = 'sha256:' + hashlib.sha256(fh.read()).hexdigest()
            if actual != f['digest']:
                bad_digest.append((s['name'], f['path'], actual))
    check('every manifest digest matches the bytes on disk',
          not bad_digest, str(bad_digest[:3]))

    # The adaptation must be recorded, not silent.
    #
    # The *number* is data, not a constant: the library grows, and a
    # new skill with a name that breaks the rules becomes another
    # exception. What must hold is that every skill that does not
    # conform is recorded as adapted -- and that no conforming skill
    # is. The count is checked against the problems the conformance
    # layer itself found, so a skill that is adapted but not recorded
    # is still caught.
    adapted = [s for s in index['skills']
               if s['skills'].get('name_override') or s['skills'].get('description_truncated')]
    expected = [s for s in index['skills'] if s['skills'].get('problems')]
    check('every skill that does not conform is recorded as adapted',
          len(adapted) == len(expected),
          '%d adapted, %d with problems: %s'
          % (len(adapted), len(expected),
             [s['skills']['name'] for s in index['skills']
              if s['skills'].get('problems')
              and not (s['skills'].get('name_override')
                       or s['skills'].get('description_truncated'))][:5]))
    check('the adaptation is recorded for at least one skill',
          len(adapted) > 0, 'no skill needed adapting')
    check('a skill served unchanged is not marked as adapted',
          all(not s['skills'].get('name_override')
              and not s['skills'].get('description_truncated')
              for s in index['skills']
              if not s['skills'].get('problems')),
          'a conforming skill was marked as adapted')

    # The vendored files must not have been edited to make them
    # conform: the served name is allowed to differ from the file's.
    for s in index['skills']:
        entry = s['skills']
        if entry.get('name_override'):
            file_name = s['frontmatter']['name']
            check('%s: the file keeps its own name' % s['name'],
                  file_name != entry['name'],
                  'the file was edited to %r' % entry['name'])


def check_the_methods(srv):
    """The four methods, answered as the specification requires."""
    result, error = call(srv, 'skills/list')
    check('skills/list is answered', error is None and result is not None,
          str(error))
    if result is None:
        return

    check('skills/list says the result is complete',
          result.get('resultType') == 'complete')
    check('skills/list carries a ttl and a scope',
          result.get('ttlMs', 0) >= 0 and result.get('cacheScope') == 'public',
          str({k: result.get(k) for k in ('ttlMs', 'cacheScope')}))
    check('skills/list has no body in it',
          all('body' not in s and 'content' not in s for s in result['skills']))

    # The listing is paginated, and the cursor must work.
    check('skills/list hands out a cursor',
          bool(result.get('nextCursor')), 'no nextCursor')
    cursor = result.get('nextCursor')
    if cursor:
        page2, err2 = call(srv, 'skills/list', {'cursor': cursor})
        check('the cursor is accepted', err2 is None, str(err2))
        if page2:
            first = {s['uri'] for s in result['skills']}
            second = {s['uri'] for s in page2['skills']}
            check('the second page does not repeat the first',
                  not (first & second), str(sorted(first & second)[:3]))
            check('the second page holds whole skills',
                  all(s.get('resources') for s in page2['skills']))

    # `skills/get` answers for every skill served, whether or not it was
    # on the page -- and refuses a URI the server did not issue.
    skill = result['skills'][0]
    got, err = call(srv, 'skills/get', {'uri': skill['uri']})
    check('skills/get answers for a listed skill', err is None and got is not None,
          str(err))
    if got:
        check('skills/get returns the skill under `skill`',
              got.get('skill', {}).get('uri') == skill['uri'])
        check('skills/get returns the same manifest as the listing',
              got['skill']['resources'] == skill['resources'])
        check('skills/get returns the same frontmatter as the listing',
              got['skill']['frontmatter'] == skill['frontmatter'])

    _, err = call(srv, 'skills/get', {'uri': 'skill://no-such-skill/SKILL.md'})
    check('skills/get refuses an unknown URI with -32602',
          err is not None and err.get('code') == -32602, str(err))

    _, err = call(srv, 'skills/get', {'uri': 'skill://access'})
    check('skills/get refuses a directory URI',
          err is not None and err.get('code') == -32602, str(err))

    _, err = call(srv, 'skills/get', {'uri': 'skill://access/../secrets'})
    check('skills/get refuses a URI that climbs out of the skill',
          err is not None and err.get('code') == -32602, str(err))

    # `resources/read` serves the bytes.
    read, err = call(srv, 'resources/read', {'uri': skill['uri']})
    check('resources/read answers for SKILL.md', err is None, str(err))
    if read:
        contents = read.get('contents', [])
        check('resources/read returns one content entry', len(contents) == 1)
        if contents:
            c = contents[0]
            check('resources/read reports the mime type',
                  c.get('mimeType') == 'text/markdown', str(c.get('mimeType')))
            check('resources/read returns the text, not a blob',
                  'text' in c and 'blob' not in c)
            check('resources/read says the result is complete',
                  read.get('resultType') == 'complete')

    _, err = call(srv, 'resources/read', {'uri': 'skill://access/nope.md'})
    check('resources/read refuses a file that does not exist',
          err is not None and err.get('code') == -32602, str(err))

    _, err = call(srv, 'resources/read',
                  {'uri': 'skill://access/../../.library_data.json'})
    check('resources/read refuses a URI that climbs out of the skill',
          err is not None and err.get('code') == -32602, str(err))

    # `resources/directory/read` lists the direct children only.
    root = skill['uri'].rsplit('/', 1)[0]
    children, err = call(srv, 'resources/directory/read', {'uri': root})
    check('resources/directory/read answers for a skill root',
          err is None and children is not None, str(err))
    if children:
        names = [r['name'] for r in children['resources']]
        check('the directory lists the direct children',
              'SKILL.md' in names, str(names[:5]))
        check('a child directory is reported as a directory',
              all(r['mimeType'] == 'inode/directory'
                  for r in children['resources']
                  if not r['name'].endswith('.md')
                  and r['name'] != 'SKILL.md'),
              str([r for r in children['resources']
                   if r['mimeType'] != 'inode/directory'
                   and not r['name'].endswith('.md')][:3]))
        check('no directory URI has a trailing slash',
              all(not r['uri'].endswith('/') for r in children['resources']))

    _, err = call(srv, 'resources/directory/read', {'uri': 'skill://access/nope'})
    check('resources/directory/read refuses a directory that does not exist',
          err is not None and err.get('code') == -32602, str(err))

    # A file is not a directory. The two refusals are distinguished by
    # their *message*, because the code is the same: a client that was
    # handed "skill://x/SKILL.md" and asked for its children should not
    # be told that the directory does not exist -- the directory does
    # exist, and it is the file it named that is wrong.
    _, err = call(srv, 'resources/directory/read', {'uri': skill['uri']})
    check('resources/directory/read refuses a file',
          err is not None and err.get('code') == -32602, str(err))
    check('resources/directory/read says a file is not a directory',
          err is not None and 'not a directory' in (err.get('message') or '').lower(),
          str(err))
    check('resources/directory/read says a missing directory does not exist',
          'does not exist' in (
              (call(srv, 'resources/directory/read',
                    {'uri': 'skill://access/nope'})[1] or {}).get('message') or '').lower()
          or 'unknown directory' in (
              (call(srv, 'resources/directory/read',
                    {'uri': 'skill://access/nope'})[1] or {}).get('message') or '').lower(),
          'the two refusals are not distinguished')

    check_every_directory(srv)


def check_every_directory(srv):
    """Every directory in every served skill must be readable.

    The server declares `directoryRead: true`, which is a promise that
    the *whole* namespace is walkable -- not just the roots, and not
    just the directories of one skill. A client that has to discover
    that some subdirectory is missing by hitting an error would be
    relying on a promise the server only kept for part of the library.

    So every directory implied by every manifest is read, and the
    children it reports are compared against the manifest: the manifest
    is the tree, and the listing must be exactly the tree's next level.
    """
    unreadable = []
    wrong = []
    total = 0

    for record in srv.index['skills']:
        entry = record['skills']
        prefix = 'skill://%s' % entry['name']
        files = [f['path'] for f in record['bundle']['files']]

        # Every directory in the skill: the root, plus every prefix of
        # every file.
        directories = {''}
        for path in files:
            parts = path.split('/')
            for depth in range(1, len(parts)):
                directories.add('/'.join(parts[:depth]))

        for rel in sorted(directories):
            uri = prefix if rel == '' else '%s/%s' % (prefix, rel)
            result, err = call(srv, 'resources/directory/read', {'uri': uri})
            total += 1
            if err is not None or result is None:
                unreadable.append((entry['name'], rel, str(err)[:80]))
                continue

            # The children must be exactly the next level of the tree.
            child_prefix = (rel + '/') if rel else ''
            expected = {}
            for path in files:
                if child_prefix and not path.startswith(child_prefix):
                    continue
                rest = path[len(child_prefix):]
                if not rest:
                    continue
                if '/' in rest:
                    expected.setdefault(rest.split('/', 1)[0], 'inode/directory')
                else:
                    expected.setdefault(rest, 'file')
            got = {r['name']: ('inode/directory' if r['mimeType'] == 'inode/directory'
                               else 'file')
                   for r in result['resources']}
            if got != expected:
                wrong.append((entry['name'], rel,
                              sorted(got.items())[:4], sorted(expected.items())[:4]))

    check('every directory in every skill can be read (%d directories)'
          % total,
          not unreadable, str(unreadable[:5]))
    check('every directory lists exactly its own children',
          not wrong, str(wrong[:5]))
    return fingerprint(srv)


def fingerprint(srv):
    """The same fingerprint the TypeScript driver computes.

    One line per directory, listing its children with their mime types,
    hashed. Two implementations that answer the same way produce the
    same digest; one that differs anywhere produces a different one.
    """
    import hashlib

    lines = []
    for record in srv.index['skills']:
        entry = record['skills']
        prefix = 'skill://%s' % entry['name']
        files = [f['path'] for f in record['bundle']['files']]

        directories = {''}
        for path in files:
            parts = path.split('/')
            for depth in range(1, len(parts)):
                directories.add('/'.join(parts[:depth]))

        for rel in sorted(directories):
            uri = prefix if rel == '' else '%s/%s' % (prefix, rel)
            result, err = call(srv, 'resources/directory/read', {'uri': uri})
            if err is not None or result is None:
                lines.append('%s\tERROR %s' % (uri, err.get('code')))
                continue
            children = ','.join(sorted(
                '%s=%s' % (r['name'], r['mimeType'])
                for r in result['resources']))
            lines.append('%s\t%s' % (uri, children))

    digest = hashlib.sha256('\n'.join(lines).encode('utf-8')).hexdigest()
    return {'count': len(lines), 'digest': digest}


def check_the_digest(srv, tmp_root):
    """The digest is checked against the bytes, not just reported.

    A manifest the server does not verify is a manifest the client has
    to trust blindly -- which is the thing the manifest exists to
    avoid. So the check is exercised by serving a file that does *not*
    match its digest, and the server must refuse it.
    """
    import shutil
    import tempfile

    # A copy of one skill, with one byte changed.
    record = srv.index['skills'][0]
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(BASE, record['path'])
        dst = os.path.join(tmp, record['path'])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copytree(src, dst)
        target = os.path.join(dst, 'SKILL.md')
        with open(target, 'a', encoding='utf-8') as fh:
            fh.write('\n<!-- tampered -->\n')

        # The server reads from the copy, but the index still describes
        # the original -- which is exactly the situation the digest is
        # there to catch.
        srv.root = tmp
        try:
            _, err = call(srv, 'resources/read',
                          {'uri': record['skills']['uri']})
            check('a file that does not match its digest is refused',
                  err is not None and 'digest' in (err.get('message') or '').lower(),
                  str(err))
        finally:
            srv.root = os.environ.get('SKILLS_LIBRARY_ROOT') or BASE


def check_the_old_revision(srv):
    """The extension belongs to the newer revision only."""
    old = Server()
    old.handle({
        'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
        'params': {
            'protocolVersion': protocol.DEFAULT_PROTOCOL_VERSION,
            'capabilities': {},
            'clientInfo': {'name': 'test', 'version': '1.0.0'},
        },
    })
    for method, params in (('skills/list', {}),
                            ('skills/get', {'uri': 'skill://access/SKILL.md'}),
                            ('resources/list', {}),
                            ('resources/read', {'uri': 'skill://access/SKILL.md'}),
                            ('resources/directory/read', {'uri': 'skill://access'})):
        _, err = call(old, method, params)
        check('the older revision does not answer %s' % method,
              err is not None and err.get('code') == -32601, str(err))


# ------------------------------------------------------------- the parity
def drive_ts():
    """Ask the TypeScript server the same questions."""
    proc = subprocess.run(['node', TS_SKILLS],
                          capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError('the TypeScript extension failed:\n%s' % proc.stderr[-2000:])
    return json.loads(proc.stdout)


def check_parity(srv):
    """The two implementations must answer identically."""
    if not os.path.isfile(TS_ENTRY):
        skip('the TypeScript build is missing (%s). Run `npm run build` '
             'in mcp/ first.' % TS_ENTRY)
        return

    ts = drive_ts()

    py_list, err = call(srv, 'skills/list')
    check('parity: skills/list agrees',
          err is None and py_list == ts['list'],
          'the two listings differ')
    check('parity: the cursor is byte-identical',
          py_list.get('nextCursor') == ts.get('cursor'),
          'python %r, typescript %r'
          % (py_list.get('nextCursor'), ts.get('cursor')))

    py_page2, _ = call(srv, 'skills/list', {'cursor': py_list.get('nextCursor')})
    py_names = [s['uri'] for s in py_page2['skills']]
    check('parity: the second page agrees',
          py_names == ts.get('page2Names'),
          'python %s, typescript %s' % (py_names[:3], ts.get('page2Names', [])[:3]))

    # `resources/list` -- the method the `resources` capability promises.
    py_res, py_res_err = call(srv, 'resources/list', {})
    check('resources/list is answered', py_res_err is None and py_res is not None,
          str(py_res_err))
    if py_res:
        check('resources/list says the result is complete',
              py_res.get('resultType') == 'complete')
        check('resources/list carries a ttl and a scope',
              py_res.get('ttlMs', 0) >= 0 and py_res.get('cacheScope') == 'public',
              str({k: py_res.get(k) for k in ('ttlMs', 'cacheScope')}))
        check('resources/list enumerates the served files',
              py_res['resources'], 'no resources')
        check('parity: resources/list agrees',
              py_res.get('resources') == ts.get('resources'),
              'the two listings differ')
        check('parity: the resource cursor is byte-identical',
              py_res.get('nextCursor') == ts.get('resourceCursor'),
              'python %r, typescript %r' % (py_res.get('nextCursor'),
                                            ts.get('resourceCursor')))
        py_res2, _ = call(srv, 'resources/list',
                          {'cursor': py_res.get('nextCursor')})
        py_res_names = [r['uri'] for r in py_res2['resources']]
        check('parity: the second resource page agrees',
              py_res_names == ts.get('resourcesPage2'),
              'python %s, typescript %s' % (py_res_names[:3],
                                            ts.get('resourcesPage2', [])[:3]))

    # Every method, for the same URIs, must give the same answer --
    # including the refusals. The URIs are fixed rather than taken from
    # the listing, so the two implementations are asked about the
    # *same* skill: a comparison of two answers about two different
    # skills would always differ, and would teach nothing. The key is
    # the label the driver script uses, so the two are looked up by the
    # same name.
    first = 'skill://access/SKILL.md'
    second = 'skill://accessibility/SKILL.md'
    root = 'skill://access'
    for key, method, params in (
            ('get', 'skills/get', {'uri': first}),
            ('getSecond', 'skills/get', {'uri': second}),
            ('getUnknown', 'skills/get',
             {'uri': 'skill://no-such-skill/SKILL.md'}),
            ('getDirectoryUri', 'skills/get', {'uri': root}),
            ('getTraversal', 'skills/get',
             {'uri': 'skill://access/../secrets'}),
            ('read', 'resources/read', {'uri': first}),
            ('readUnknown', 'resources/read',
             {'uri': 'skill://access/nope.md'}),
            ('readTraversal', 'resources/read',
             {'uri': 'skill://access/../../.library_data.json'}),
            ('dirRoot', 'resources/directory/read', {'uri': root}),
            ('dirUnknown', 'resources/directory/read',
             {'uri': 'skill://access/nope'}),
            ('dirFile', 'resources/directory/read', {'uri': first})):
        py_result, py_error = call(srv, method, params)
        ts_answer = ts.get(key)
        if ts_answer is None:
            # The driver did not run this case; say so rather than
            # quietly passing it.
            check('parity: %s was exercised on both sides' % key, False,
                  'the TypeScript driver did not run it')
            continue
        ts_result = ts_answer.get('result')
        ts_error = ts_answer.get('error')
        if py_error is not None or ts_error is not None:
            check('parity: %s gives the same refusal' % key,
                  py_error is not None and ts_error is not None
                  and py_error.get('code') == ts_error.get('code'),
                  'python %s, typescript %s' % (py_error, ts_error))
        else:
            check('parity: %s gives the same answer' % key,
                  py_result == ts_result,
                  'the two answers differ')

    # The refusals have to be refusals on *both* sides, not merely
    # equal. If the TypeScript server answered `skills/get` for a
    # directory URI, the parity comparison above would still see two
    # equal answers -- one of them wrong.
    for key, method, params in (
            ('getUnknown', 'skills/get',
             {'uri': 'skill://no-such-skill/SKILL.md'}),
            ('getDirectoryUri', 'skills/get', {'uri': 'skill://access'}),
            ('getTraversal', 'skills/get',
             {'uri': 'skill://access/../secrets'}),
            ('readUnknown', 'resources/read',
             {'uri': 'skill://access/nope.md'}),
            ('readTraversal', 'resources/read',
             {'uri': 'skill://access/../../.library_data.json'}),
            ('dirUnknown', 'resources/directory/read',
             {'uri': 'skill://access/nope'}),
            ('dirFile', 'resources/directory/read', {'uri': first})):
        ts_answer = ts.get(key) or {}
        ts_error = ts_answer.get('error')
        check('the TypeScript server refuses %s' % key,
              ts_error is not None and ts_error.get('code') == -32602,
              str(ts_answer)[:200])

    # The two directory refusals are distinguished by their *message*,
    # not by their code: a client that was handed a file and asked for
    # its children should not be told the directory does not exist --
    # it does exist, and it is the file it named that is wrong. The
    # TypeScript server has to distinguish them as well, or a client
    # that walks the namespace cannot tell "no such directory" from
    # "that is a file".
    dir_file = (ts.get('dirFile') or {}).get('error') or {}
    dir_unknown = (ts.get('dirUnknown') or {}).get('error') or {}
    check('the TypeScript server says a file is not a directory',
          'not a directory' in (dir_file.get('message') or '').lower(),
          str(dir_file)[:200])
    check('the TypeScript server says a missing directory does not exist',
          'does not exist' in (dir_unknown.get('message') or '').lower()
          or 'unknown directory' in (dir_unknown.get('message') or '').lower(),
          str(dir_unknown)[:200])

    # The TypeScript server must verify the digest too. The driver
    # serves a tampered copy of the library for this: without it, a
    # server that never checked the digest would pass.
    tampered = ts.get('tampered') or {}
    check('the TypeScript server refuses a file that does not match its digest',
          tampered.get('error') is not None
          and 'digest' in (tampered['error'].get('message') or '').lower(),
          str(tampered)[:200])

    # The whole directory namespace, fingerprinted on both sides. The
    # per-URI comparisons above cover a handful of directories; this
    # covers all of them, so a directory that only one implementation
    # can read is caught.
    py_sweep = fingerprint(srv)
    ts_sweep = ts.get('dirSweep') or {}
    check('the TypeScript driver walked every directory',
          ts_sweep.get('count') == py_sweep['count'],
          'python %s, typescript %s' % (py_sweep['count'],
                                        ts_sweep.get('count')))
    check('the TypeScript server read every directory without an error',
          ts_sweep.get('failed') == 0,
          '%s directories failed' % ts_sweep.get('failed'))
    check('parity: every directory in every skill agrees',
          py_sweep['digest'] == ts_sweep.get('digest'),
          'python %s, typescript %s' % (py_sweep['digest'],
                                        ts_sweep.get('digest')))


def main():
    srv = new_revision_server()
    check_the_rules(srv)
    check_the_methods(srv)
    check_the_digest(srv, None)
    check_the_old_revision(srv)
    check_parity(srv)

    if failures:
        sys.stderr.write('\n%d FAILURE(S) out of %d checks\n'
                         % (len(failures), checks))
        for f in failures:
            sys.stderr.write('  - %s\n' % f)
        return 1
    if skips:
        sys.stderr.write('\nSKILLS EXTENSION: INCOMPLETE — %d check(s) '
                         'did not run:\n' % len(skips))
        for s in skips:
            sys.stderr.write('  - %s\n' % s)
        sys.stderr.write('Build the TypeScript server (`npm run build` in '
                         'mcp/) and run this again. A skipped check is not '
                         'a passing check.\n')
        return 1
    sys.stdout.write('\nSKILLS EXTENSION: PASS — all %d checks\n' % checks)
    return 0


if __name__ == '__main__':
    sys.exit(main())
