#!/usr/bin/env python3
"""Provenance: who owns an entry, under what licence, and may it be shared.

The library is not the author's material. Most of it comes from other
people's plugins and collections, under licences that differ. The
`CREDITS.md` and `NOTICE` work already recorded that -- but it was
invisible at runtime, so no tool could tell a caller whether the entry
they were about to install was one they were allowed to hand on.

Now the provenance is joined into the index, and this test holds it to
four things:

  1. **The join is complete.** Every entry in the index has a
     provenance record, and every record has exactly one entry. A
     gap is reported, not patched over: a guess about a licence is
     worse than an admission that there is none.

  2. **The join is correct.** The owner, licence and verdict in the
     index are the ones in the provenance table -- not a copy that
     has drifted from it.

  3. **It is reachable.** `search_library` carries the verdict, the
     filters narrow by it, and `get_skill`/`get_agent` carry the
     whole record.

  4. **The two implementations agree.** The TypeScript server and the
     Python fallback must report the same verdict for the same entry,
     and filter the same way. A client that talks to one and then
     the other must not see a different licence.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
BASE = os.path.dirname(MCP)
sys.path.insert(0, os.path.join(MCP, 'python'))

INDEX = os.path.join(MCP, 'data', 'index.json')
PROVENANCE = os.path.join(MCP, 'data', 'provenance.json')
TS_ENTRY = os.path.join(MCP, 'dist', 'index.js')

# The verdicts the table may carry. A verdict outside this set is a
# typo, and a typo in a licence verdict is a licence nobody checked.
VERDICTS = {
    'redistributable',
    'included-with-terms',
    'fixture',
    'personal',
    'unknown',
}

failures = []
checks = []
skips = []


def check(label, condition, detail=''):
    checks.append(label)
    if condition:
        sys.stdout.write('ok   %s\n' % label)
    else:
        failures.append(label)
        sys.stdout.write('FAIL %s\n' % label)
        if detail:
            sys.stdout.write('     %s\n' % detail)


def skip(msg):
    skips.append(msg)
    sys.stderr.write('SKIP: %s\n' % msg)


def load(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


# ---------------------------------------------------------------- the join

def test_join_is_complete(index, prov):
    """Every entry has a record, and every record has one entry."""
    entries = index['skills'] + index['agents']
    table = {(r['kind'], r['name']): r for r in prov}

    missing = [e['id'] for e in entries if (e['kind'], e['name']) not in table]
    check('every entry in the index has a provenance record',
          not missing,
          'missing: %s' % ', '.join(missing[:10]))

    # The other direction: a record for an entry that is not in the
    # index is fine -- the held-aside agents and the fixtures are
    # recorded but not published -- so this is reported, not failed.
    entry_keys = {(e['kind'], e['name']) for e in entries}
    extra = sorted(k for k in table if k not in entry_keys)
    sys.stdout.write('ok   %d provenance records are not in the index '
                     '(held aside, fixtures, local files)\n' % len(extra))

    check('the provenance table has no duplicate keys',
          len(table) == len(prov),
          '%d records, %d unique' % (len(prov), len(table)))

    # The index's own summary must agree with the table.
    summary = index.get('provenance', {})
    check('the index carries a provenance summary',
          isinstance(summary, dict) and 'by_verdict' in summary,
          str(sorted(summary)) if isinstance(summary, dict) else str(summary))
    check('the summary lists no missing entries',
          summary.get('missing') == [],
          str(summary.get('missing')))


def test_join_is_correct(index, prov):
    """The index says what the table says."""
    table = {(r['kind'], r['name']): r for r in prov}
    entries = index['skills'] + index['agents']

    wrong_owner = []
    wrong_license = []
    wrong_verdict = []
    for e in entries:
        row = table.get((e['kind'], e['name']))
        if row is None:
            continue
        prov_e = e.get('provenance') or {}
        if prov_e.get('owner', '') != (row.get('owner') or ''):
            wrong_owner.append(e['id'])
        if prov_e.get('license', '') != (row.get('license') or ''):
            wrong_license.append(e['id'])
        if prov_e.get('verdict', '') != (row.get('verdict') or ''):
            wrong_verdict.append(e['id'])

    check('the owner in the index is the owner in the table',
          not wrong_owner, ', '.join(wrong_owner[:5]))
    check('the licence in the index is the licence in the table',
          not wrong_license, ', '.join(wrong_license[:5]))
    check('the verdict in the index is the verdict in the table',
          not wrong_verdict, ', '.join(wrong_verdict[:5]))

    # Every verdict must be one the table knows.
    bad = sorted({(e.get('provenance') or {}).get('verdict')
                  for e in entries}
                 - VERDICTS)
    check('every verdict is one the table defines', not bad, str(bad))

    # The summary's counts must add up to the entries it describes.
    by_verdict = index.get('provenance', {}).get('by_verdict', {})
    total = sum(by_verdict.values())
    check('the verdict counts add up to the number of entries',
          total == len(entries),
          '%d counted, %d entries' % (total, len(entries)))

    # The index is portable: it must not carry the machine's paths.
    leaky = [e['id'] for e in entries
             if (e.get('provenance') or {}).get('source')]
    check('the provenance carries no absolute source path',
          not leaky, ', '.join(leaky[:5]))


# ------------------------------------------------------------- reachable

def test_reachable(index):
    """A caller can ask the question and get an answer."""
    from search import SearchIndex

    idx = SearchIndex(index)

    # A search result carries the verdict, so a caller can filter on
    # it without a second call.
    out = idx.search('accessibility audit', limit=5)
    check('search_library returns results', len(out['results']) > 0)
    with_verdict = [r for r in out['results'] if 'verdict' in r]
    check('every search result carries a verdict',
          len(with_verdict) == len(out['results']),
          '%d of %d' % (len(with_verdict), len(out['results'])))
    check('every search result carries an owner',
          all('owner' in r for r in out['results']))
    check('every search result carries a licence',
          all('license' in r for r in out['results']))

    # The filters narrow by it. The two verdicts partition the match
    # set, so they must be disjoint -- an entry cannot be both
    # redistributable and under terms.
    redistributable = idx.search('test', limit=50, verdict='redistributable')
    terms = idx.search('test', limit=50, verdict='included-with-terms')
    red_ids = {r['id'] for r in redistributable['results']}
    terms_ids = {r['id'] for r in terms['results']}
    check('the two verdict filters do not overlap',
          not (red_ids & terms_ids),
          ', '.join(sorted(red_ids & terms_ids)[:5]))
    check('the two verdict filters are both non-empty',
          red_ids and terms_ids,
          '%d redistributable, %d under terms' % (len(red_ids), len(terms_ids)))

    # A filtered result must carry the verdict it was filtered on.
    #
    # The filtered set is *not* a subset of the unfiltered one: the
    # filter changes which candidates compete, so the relevance floor
    # falls differently and a different set survives it. That is
    # correct. What is being checked here is the membership rule, not
    # the ranking.
    check('a redistributable result says so',
          all(r['verdict'] == 'redistributable'
              for r in redistributable['results']),
          str({r['verdict'] for r in redistributable['results']}))
    check('a result under terms says so',
          all(r['verdict'] == 'included-with-terms'
              for r in terms['results']),
          str({r['verdict'] for r in terms['results']}))

    # The licence filter.
    mit = idx.search('test', limit=50, license='MIT')
    check('the licence filter returns only that licence',
          all(r['license'].lower() == 'mit'
              for r in mit['results']),
          str({r['license'] for r in mit['results']}))

    # The source filter: the container.
    containers = {e['provenance']['container'] for e in index['skills']
                  if e.get('provenance', {}).get('container')}
    check('the library holds entries from several containers',
          len(containers) > 1, '%d containers' % len(containers))
    one = sorted(containers)[0]
    by_source = idx.search('test', limit=50, source=one)
    check('the source filter returns only that container',
          all((e.get('provenance') or {}).get('container') == one
              for e in index['skills'] + index['agents']
              if e['id'] in {r['id'] for r in by_source['results']}),
          one)


# ---------------------------------------------------------- the two sides

def test_the_two_implementations_agree(index):
    """The TypeScript server and the Python fallback must agree."""
    if not os.path.isfile(TS_ENTRY):
        skip('the TypeScript build is missing (%s). Run `npm run build` '
             'in mcp/ first.' % TS_ENTRY)
        return

    script = os.path.join(HERE, '_ts_provenance.mjs')
    proc = subprocess.run(['node', script], capture_output=True, text=True,
                          timeout=120)
    if proc.returncode != 0:
        check('the TypeScript provenance probe runs', False, proc.stderr[-500:])
        return
    ts = json.loads(proc.stdout)

    check('the two implementations report the same number of entries',
          len(ts['entries']) == len(index['skills']) + len(index['agents']),
          'TS: %d, index: %d'
          % (len(ts['entries']),
             len(index['skills']) + len(index['agents'])))

    by_id = {e['id']: e for e in index['skills'] + index['agents']}
    mismatched = []
    for entry in ts['entries']:
        e = by_id.get(entry['id'])
        if e is None:
            mismatched.append('%s is not in the index' % entry['id'])
            continue
        prov = e.get('provenance') or {}
        if (entry['owner'] != prov.get('owner', '')
                or entry['license'] != prov.get('license', '')
                or entry['verdict'] != prov.get('verdict', '')):
            mismatched.append(entry['id'])
    check('the two implementations report the same provenance',
          not mismatched, ', '.join(mismatched[:5]))

    # The index is not enough. A server can hold a perfectly intact
    # index and still lie in the results it hands out -- a blank
    # owner, or a verdict that says "free to share" when the record
    # says otherwise. The probe above reports the provenance the
    # *search* returned, so a lie in the result assembly shows up.
    lying = []
    for entry in ts.get('reported', []):
        e = by_id.get(entry['id'])
        if e is None:
            continue
        prov = e.get('provenance') or {}
        if (entry['owner'] != (prov.get('owner') or '')
                or entry['license'] != (prov.get('license') or '')
                or entry['verdict'] != (prov.get('verdict') or '')):
            lying.append('%s: TS says %r/%r/%r, the record says %r/%r/%r'
                         % (entry['id'], entry['owner'], entry['license'],
                            entry['verdict'], prov.get('owner', ''),
                            prov.get('license', ''), prov.get('verdict', '')))
    check('the TypeScript search reports the provenance the record holds',
          not lying, '; '.join(lying[:5]))

    # The same, for the Python implementation: its results must carry
    # the record's provenance, not a constant or a blank.
    from search import SearchIndex
    py_idx = SearchIndex(index)
    py_lying = []
    for query in ('test', 'accessibility audit', 'python'):
        for r in py_idx.search(query, limit=100)['results']:
            prov = (by_id.get(r['id']) or {}).get('provenance') or {}
            if (r.get('owner', '') != (prov.get('owner') or '')
                    or r.get('license', '') != (prov.get('license') or '')
                    or r.get('verdict', '') != (prov.get('verdict') or '')):
                py_lying.append('%s: PY says %r/%r/%r, the record says %r/%r/%r'
                                % (r['id'], r.get('owner'), r.get('license'),
                                   r.get('verdict'), prov.get('owner', ''),
                                   prov.get('license', ''),
                                   prov.get('verdict', '')))
    check('the Python search reports the provenance the record holds',
          not py_lying, '; '.join(py_lying[:5]))

    # The filters must narrow the same way. The probe asks for a
    # verdict and a licence and reports what came back.
    for case in ts.get('filters', []):
        from search import SearchIndex
        idx = SearchIndex(index)
        kwargs = {}
        if case.get('verdict') is not None:
            kwargs['verdict'] = case['verdict']
        if case.get('license') is not None:
            kwargs['license'] = case['license']
        if case.get('source') is not None:
            kwargs['source'] = case['source']
        py = idx.search(case['query'], limit=50, **kwargs)
        py_ids = sorted(r['id'] for r in py['results'])
        check('the filter %r agrees between the two implementations'
              % case.get('label', case),
              py_ids == sorted(case['ids']),
              'TS: %s\nPY: %s' % (case['ids'], py_ids))


def main():
    if not os.path.isfile(INDEX):
        skip('the index is missing (%s). Run `python3 build/build_index.py` '
             'first.' % INDEX)
        sys.stderr.write('\nPROVENANCE: INCOMPLETE — the check did not run.\n')
        return 1
    if not os.path.isfile(PROVENANCE):
        skip('the provenance table is missing (%s). Run '
             '`python3 build/provenance.py` first.' % PROVENANCE)
        sys.stderr.write('\nPROVENANCE: INCOMPLETE — the check did not run.\n')
        return 1

    index = load(INDEX)
    prov = load(PROVENANCE)

    print('the join')
    test_join_is_complete(index, prov)

    print('\nthe join is correct')
    test_join_is_correct(index, prov)

    print('\nit is reachable')
    test_reachable(index)

    print('\nthe two implementations agree')
    test_the_two_implementations_agree(index)

    print()
    if failures:
        sys.stderr.write('\n%d FAILURE(S) out of %d checks\n'
                         % (len(failures), len(checks)))
        return 1
    if skips:
        sys.stderr.write('\n%d check(s) skipped\n' % len(skips))
        sys.stderr.write('PROVENANCE: INCOMPLETE — the check did not run.\n')
        return 1
    sys.stdout.write('\n%d checks, 0 failures, 0 skips\n' % len(checks))
    sys.stdout.write('\nPROVENANCE: PASS\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
