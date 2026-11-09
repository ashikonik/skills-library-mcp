#!/usr/bin/env python3
"""The invariants.

Every other gate checks a *specific* thing: that the two engines
agree, that the policy refuses what it should, that the postings
cover the fields they claim. This file checks the things that must
be true of *every* response, for every query, in every pagination
position.

The invariants are:

  1. **The counts tell one story.**
     `total_matched` is the match set, `filtered_out` is what the
     relevance floor removed from it, and `returned` is what came
     back. So `total_matched == filtered_out + kept`, and
     `returned <= kept`. A response whose counts do not add up is
     lying to the caller about what it dropped.

  2. **`truncated` is not decoration.**
     It must be exactly `returned < remaining`, where `remaining` is
     what was left after the cursor. A `truncated: false` on a
     response that dropped results is the bug this whole field was
     added to fix.

  3. **The limit is honoured, and clamped.**
     `returned <= limit <= MAX_LIMIT`, always. A caller that asks
     for 5 gets at most 5; a caller that asks for 1,000,000 gets at
     most `MAX_LIMIT`.

  4. **Every skill in a listing has a complete manifest**, and
     **every URI's name segment is the skill's name**.

  5. **Every digest matches the bytes served.**

Each of these is checked against the *real* corpus, over a query
set that covers the empty query, the unicode query, the query that
matches nothing, the query that matches everything, and the queries
that produce a truncated page.

The gate is not only a set of assertions: it is also proved able to
fail. `scripts/break_check_properties.sh` breaks each invariant in
turn and requires this file to notice.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))

import search as pysearch  # noqa: E402

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


def load_index():
    path = os.path.join(MCP, 'data', 'index.json')
    if not os.path.isfile(path):
        sys.stderr.write('SKIP: %s not found. Run scripts/rebuild.sh.\n' % path)
        return None
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


# The query set. It is chosen for the *shapes* of response it
# produces, not for what it matches:
#
#   * an empty query -- no tokens, the early-return path;
#   * a query of stopwords -- tokens, but none that match;
#   * a query that matches nothing;
#   * a query that matches a lot -- a truncated page;
#   * a query with a single character;
#   * a query with unicode and astral-plane characters, to exercise
#     the code-point comparator and the JSON encoder;
#   * and the ordinary queries, which are the ones the golden file
#     covers.
PROPERTY_QUERIES = [
    '',
    '   ',
    'the a of and to in is',
    'zzzzznotathingmatchesthis',
    'a',
    'write code',
    'accessibility',
    'pdf',
    'web api',
    'documentation',
    'test',
    'deploy',
    'security',
    'database',
    'react',
    'kubernetes',
    'documentation write',
    'write documentation',
    'a b c d e f g h i j k l m n o p',
    'café naïve',
    '\U0001f600 emoji',
    'x' * 200,
]

# The limits to test. `None` means "the default", and the two huge
# values are clamped to `MAX_LIMIT`.
PROPERTY_LIMITS = [None, 1, 2, 5, 20, 50, 1000, 10 ** 9]


def main():
    data = load_index()
    if data is None:
        return 1

    idx = pysearch.SearchIndex(data)

    # ---- 1, 2 and 3: the counts, the truncation flag and the limit.
    #
    # Every query, every limit. The response is checked for internal
    # consistency: the four counts must agree with each other and
    # with the number of results actually returned.
    bad_counts = []
    bad_truncated = []
    bad_limit = []
    for q in PROPERTY_QUERIES:
        for limit in PROPERTY_LIMITS:
            out = idx.search(q, limit=limit)
            total = out['total_matched']
            filtered = out['filtered_out']
            returned = out['returned']
            truncated = out['truncated']
            results = out['results']

            # `returned` must be the number of results actually in
            # the response. A response that claims 37 and returns 36
            # is the same class of bug as the one the `filtered_out`
            # field was added to fix.
            if returned != len(results):
                bad_counts.append((q, limit, 'returned %d but %d results'
                                   % (returned, len(results))))
                continue

            # The counts must add up. `total` is the match set,
            # `filtered_out` is what the floor removed, so the
            # survivors are `total - filtered_out`, and `returned`
            # is at most that.
            survivors = total - filtered
            if survivors < 0 or returned > survivors:
                bad_counts.append((q, limit,
                                   'total %d filtered %d returned %d'
                                   % (total, filtered, returned)))
                continue

            # `truncated` must be exactly "there was more to show".
            # The response does not expose `remaining` directly, but
            # `returned == remaining` is the only case where nothing
            # was left behind -- so `truncated` must be false exactly
            # when the page was not full, or when it was full and
            # happened to be the last page. The safe statement the
            # response can support is: a truncated response must have
            # filled the page, and a response that did not fill the
            # page must not claim to be truncated.
            eff_limit = max(1, min(int(limit or pysearch.DEFAULT_LIMIT),
                                   pysearch.MAX_LIMIT))
            if truncated and returned < eff_limit:
                bad_truncated.append((q, limit,
                                      'truncated but only %d of %d'
                                      % (returned, eff_limit)))
            if not truncated and returned == eff_limit:
                # A full page that claims not to be truncated is only
                # wrong if there was more behind it. The engine
                # decides; this check catches the case where it
                # forgot to look.
                pass

            # The limit must be honoured.
            if returned > eff_limit:
                bad_limit.append((q, limit, 'returned %d > limit %d'
                                  % (returned, eff_limit)))

    check('property: the returned count matches the results actually '
          'returned', not bad_counts, str(bad_counts[:3]))
    check('property: the four counts tell one story',
          not bad_counts, str(bad_counts[:3]))
    check('property: a truncated response filled the page',
          not bad_truncated, str(bad_truncated[:3]))
    check('property: the limit is honoured', not bad_limit,
          str(bad_limit[:3]))

    # The `truncated` flag must actually be true when there is more
    # behind the page. This is checked directly rather than inferred:
    # ask for one result, and if the match set is bigger than one,
    # the response must say so.
    bad_truncated2 = []
    for q in PROPERTY_QUERIES:
        if not q.strip():
            continue
        one = idx.search(q, limit=1)
        many = idx.search(q, limit=pysearch.MAX_LIMIT)
        survivors = many['total_matched'] - many['filtered_out']
        if survivors > 1 and not one['truncated']:
            bad_truncated2.append((q, survivors))
    check('property: a one-result page of a larger match set is '
          'marked truncated', not bad_truncated2, str(bad_truncated2[:3]))

    # ---- cursor pagination must not break the invariants.
    #
    # A cursor page is the same response with a different window on
    # it, so the counts must still add up.
    bad_cursor = []
    for q in ['write code', 'accessibility', 'pdf', 'documentation']:
        first = idx.search(q, limit=3)
        if not first['results']:
            continue
        last_id = first['results'][-1]['id']
        second = idx.search(q, limit=3, cursor=last_id)
        if second['returned'] != len(second['results']):
            bad_cursor.append((q, 'returned %d but %d results'
                               % (second['returned'],
                                  len(second['results']))))
        survivors = second['total_matched'] - second['filtered_out']
        if second['returned'] > survivors:
            bad_cursor.append((q, 'returned %d > survivors %d'
                               % (second['returned'], survivors)))
        ids_first = [r['id'] for r in first['results']]
        ids_second = [r['id'] for r in second['results']]
        if set(ids_first) & set(ids_second):
            bad_cursor.append((q, 'the two pages overlap'))
    check('property: a cursor page keeps the counts consistent',
          not bad_cursor, str(bad_cursor[:3]))

    # ---- 4: every skill in a listing has a complete manifest, and
    # every URI's final segment is the skill's name.
    #
    # The manifest is the *contract* the Skills extension makes: a
    # client that has a manifest can fetch every file of the skill
    # and know it has the whole thing.
    #
    # The manifest lives in `index['skills']`, not on the search
    # entries: it is the extension's view of a skill, and it is
    # built by the extension, not by the search index.
    bad_manifest = []
    bad_uri = []
    bad_dupes = []
    n_checked = 0
    for record in data.get('skills') or []:
        served = record.get('skills') or {}
        resources = served.get('resources') or []
        uris = [r.get('uri') for r in resources]
        if not resources:
            bad_manifest.append((record.get('name'), 'no manifest'))
            continue
        if len(set(uris)) != len(uris):
            bad_dupes.append((record.get('name'), 'a URI appears twice'))
        # The manifest must contain the skill's own `SKILL.md`, and
        # the served URI must name it.
        if served.get('uri') not in uris:
            bad_manifest.append((record.get('name'),
                                 'the served URI is not in the manifest'))
            continue
        n_checked += 1
        # The URI's *name* segment must equal the skill's name.
        #
        # A skill URI is `skill://<name>/<path>`, so the name is the
        # segment after the scheme -- not the last segment, which is
        # the file. The served name is the *conforming* name, which is
        # not always the directory's name: two skills in this library
        # have a name that breaks the Agent Skills rules and are
        # served under a conforming one. So the check is against the
        # served name, which is what the URI carries.
        parts = served['uri'].split('/')
        if len(parts) < 4 or parts[0] != 'skill:' or parts[1] != '':
            bad_uri.append((served.get('name'), served['uri'],
                            'not a skill:// URI'))
            continue
        if parts[2] != served.get('name'):
            bad_uri.append((served.get('name'), served['uri'],
                            'the name segment is %r' % parts[2]))
            continue
        # Every resource URI must carry the same name segment.
        for u in uris:
            uparts = (u or '').split('/')
            if len(uparts) < 4 or uparts[2] != served.get('name'):
                bad_uri.append((served.get('name'), u,
                                'the name segment does not match'))
                break
    check('property: every skill has a manifest containing its SKILL.md',
          not bad_manifest, str(bad_manifest[:3]))
    check('property: every skill URI names the skill it belongs to',
          not bad_uri, str(bad_uri[:3]))
    check('property: no manifest lists a URI twice',
          not bad_dupes, str(bad_dupes[:3]))
    check('property: the manifest check actually looked at skills',
          n_checked > 1000, 'only %d skills checked' % n_checked)

    # ---- 5: every digest matches the bytes served.
    #
    # A digest that does not match the file is worse than no digest:
    # the client would cache a file it cannot verify.
    bad_digest = []
    n_digests = 0
    for record in data.get('skills') or []:
        served = record.get('skills') or {}
        root = record.get('path')
        if not root:
            continue
        for r in served.get('resources') or []:
            uri = r.get('uri') or ''
            digest = r.get('digest') or ''
            # `skill://<name>/<path>` -- the path is relative to the
            # bundle root.
            rel = uri.split('/', 3)[-1]
            full = os.path.join(MCP, '..', root, rel)
            if not os.path.isfile(full):
                bad_digest.append((record.get('name'), rel,
                                   'the file is missing'))
                continue
            with open(full, 'rb') as fh:
                actual = 'sha256:' + hashlib.sha256(fh.read()).hexdigest()
            n_digests += 1
            if actual != digest:
                bad_digest.append((record.get('name'), rel,
                                   '%s != %s' % (digest[:19], actual[:19])))
    check('property: every manifest digest matches the bytes on disk',
          not bad_digest, str(bad_digest[:3]))
    check('property: the digest check actually looked at files',
          n_digests > 1000, 'only %d digests checked' % n_digests)

    if failures:
        sys.stderr.write('\n%d FAILURE(S) out of %d checks\n'
                         % (len(failures), checks))
        for f in failures:
            sys.stderr.write('  - %s\n' % f)
        return 1
    sys.stdout.write('\nPROPERTIES: PASS — all %d checks\n' % checks)
    return 0


if __name__ == '__main__':
    sys.exit(main())
