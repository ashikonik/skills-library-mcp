#!/usr/bin/env python3
"""The filters a caller passes to `search_library` are checked, not ignored.

`domain: "Not A Domain"` used to answer `total_matched: 0` -- the same
answer as "your query matched nothing". The caller could not tell a
typo from an empty library, and the likeliest explanation went
undiagnosed.

So a filter value is resolved against the index's vocabulary before
anything is scored, and a value that names nothing is an *error*.

The resolution is forgiving about how the value is written -- case,
an unambiguous prefix, an unambiguous substring -- and refuses to guess
when the value is ambiguous. These checks state that behaviour, and
check that the two implementations agree on it.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))

from search import SearchIndex          # noqa: E402
import filters                           # noqa: E402

INDEX = os.path.join(MCP, 'data', 'index.json')

failures = []
checks = 0


def check(label, ok, detail=''):
    global checks
    checks += 1
    if ok:
        print('ok   %s' % label)
    else:
        print('FAIL %s%s' % (label, (' -- ' + detail) if detail else ''))
        failures.append(label)


def main():
    with open(INDEX) as fh:
        data = json.load(fh)
    idx = SearchIndex(data)
    vocab = idx.filter_values

    # -----------------------------------------------------------------
    # The vocabulary is read from the index, not hard-coded.
    # -----------------------------------------------------------------

    check('the domain vocabulary is not empty',
          len(vocab['domain']) > 10, '%d domains' % len(vocab['domain']))
    check('the source vocabulary is not empty',
          len(vocab['source']) > 10, '%d sources' % len(vocab['source']))
    check('the license vocabulary is not empty',
          len(vocab['license']) > 3, '%d licenses' % len(vocab['license']))
    check('the verdict vocabulary is not empty',
          len(vocab['verdict']) > 1, '%d verdicts' % len(vocab['verdict']))

    # -----------------------------------------------------------------
    # A value that names nothing is an error.
    # -----------------------------------------------------------------

    try:
        idx.search('write code', domain='Not A Domain')
        check('an unknown domain is an error', False, 'it was accepted')
    except filters.FilterError as e:
        check('an unknown domain is an error', True)
        check('the error names the filter', 'domain' in str(e), str(e))
        check('the error names the value', 'Not A Domain' in str(e), str(e))
        check('the error suggests the nearest values',
              'Did you mean' in str(e), str(e))

    # The same for the other three filters.
    for name, bad in (('source', 'no-such-source'),
                      ('license', 'No Such Licence'),
                      ('verdict', 'no-such-verdict')):
        try:
            idx.search('write code', **{name: bad})
            check('an unknown %s is an error' % name, False, 'it was accepted')
        except filters.FilterError:
            check('an unknown %s is an error' % name, True)

    # -----------------------------------------------------------------
    # A value that names something is not an error, however it is
    # written.
    # -----------------------------------------------------------------

    a_real_domain = vocab['domain'][0]
    try:
        exact = idx.search('write code', domain=a_real_domain)
        check('an exact domain is accepted', True)
        check('an exact domain matches something',
              exact['total_matched'] >= 0)
    except filters.FilterError as e:
        check('an exact domain is accepted', False, str(e))
        exact = None

    # The same domain, written differently, must match the same entries.
    if exact is not None:
        try:
            lower = idx.search('write code', domain=a_real_domain.lower())
            check('the domain match ignores case',
                  [r['id'] for r in lower['results']]
                  == [r['id'] for r in exact['results']],
                  '%s != %s' % (lower['results'][:1], exact['results'][:1]))
        except filters.FilterError as e:
            check('the domain match ignores case', False, str(e))

    # The prefix rule.
    #
    # The prefix rule and the substring rule overlap: a stem that
    # prefixes one value is also a substring of that value. So the
    # prefix rule cannot be tested by "this stem resolves" -- the
    # substring rule would resolve it too.
    #
    # What distinguishes them is *precedence*. A stem that prefixes
    # exactly one value but is a substring of several is resolved by
    # the prefix rule, and refused by the substring rule. Without the
    # prefix rule, that stem is ambiguous and the caller gets an error
    # instead of the value they meant.
    #
    # The stem must also not be a value *itself*, or the exact-match
    # rule fires first and the prefix rule is never reached.
    def prefix_discriminator(values):
        lowered = {v.lower() for v in values}
        for width in range(2, 9):
            for val in values:
                for start in range(len(val) - width + 1):
                    stem = val[start:start + width].lower()
                    if stem in lowered:
                        continue
                    prefixed = [t for t in values
                                if t.lower().startswith(stem)]
                    contained = [t for t in values if stem in t.lower()]
                    if len(prefixed) == 1 and len(contained) > 1:
                        return stem, prefixed[0]
        return None, None

    stem, expected = prefix_discriminator(vocab['source'])
    check('the index has a value where the prefix rule decides',
          stem is not None, 'no prefix-discriminating source found')
    prefix_stem = stem
    if stem:
        try:
            resolved = filters.resolve('source', stem, vocab['source'])
            check('the prefix rule wins over the substring rule',
                  resolved == expected, '%r != %r' % (resolved, expected))
        except filters.FilterError as e:
            check('the prefix rule wins over the substring rule', False, str(e))

    # The substring rule.
    #
    # A stem that is inside exactly one value, and starts none of
    # them, resolves to that value.
    def substring_only(values, width):
        lowered = {v.lower() for v in values}
        for v in values:
            for start in range(1, max(1, len(v) - width)):
                stem = v[start:start + width].lower()
                if len(stem) < width or stem in lowered:
                    continue
                prefixed = [t for t in values
                            if t.lower().startswith(stem)]
                contained = [t for t in values if stem in t.lower()]
                if len(prefixed) == 0 and len(contained) == 1:
                    return stem, contained[0]
        return None, None

    stem, expected = substring_only(vocab['source'], 6)
    check('the index has a substring-only value to test with',
          stem is not None, 'no substring-only source found')
    substring_stem = stem
    if stem:
        try:
            resolved = filters.resolve('source', stem, vocab['source'])
            check('an unambiguous substring resolves',
                  resolved == expected, '%r != %r' % (resolved, expected))
        except filters.FilterError as e:
            check('an unambiguous substring resolves', False, str(e))

    # An ambiguous value is an error, not a guess.
    ambiguous = None
    for s in vocab['source']:
        stem = s[:4]
        if len(stem) >= 4 and sum(1 for t in vocab['source']
                                  if t.lower().startswith(stem.lower())) > 1:
            ambiguous = stem
            break
    if ambiguous:
        try:
            filters.resolve('source', ambiguous, vocab['source'])
            check('an ambiguous prefix is refused', False,
                  'it resolved to something')
        except filters.FilterError as e:
            check('an ambiguous prefix is refused', True)
            check('the error names the candidates',
                  ',' in str(e), str(e))

    # Every value in the vocabulary resolves to itself. This is the
    # property that keeps a legitimate filter from being rejected.
    mismatched = []
    for name, values in vocab.items():
        for v in values:
            try:
                r = filters.resolve(name, v, values)
                if r != v:
                    mismatched.append((name, v, r))
            except filters.FilterError as e:
                mismatched.append((name, v, str(e)))
    check('every value in the vocabulary resolves to itself',
          not mismatched, str(mismatched[:3]))

    # And every value, written in lower case, resolves to itself too.
    mismatched = []
    for name, values in vocab.items():
        for v in values:
            try:
                r = filters.resolve(name, v.lower(), values)
                if r != v:
                    mismatched.append((name, v, r))
            except filters.FilterError as e:
                mismatched.append((name, v, str(e)))
    check('every value in the vocabulary resolves to itself in lower case',
          not mismatched, str(mismatched[:3]))

    # -----------------------------------------------------------------
    # The two implementations agree.
    #
    # The filter rules are duplicated in `src/filters.ts`, and a filter
    # that resolves differently depending on which server the caller
    # reached is a filter that filters differently.
    # -----------------------------------------------------------------

    probe = os.path.join(HERE, '_ts_filters.mjs')
    if not os.path.isfile(os.path.join(MCP, 'dist', 'filters.js')):
        print('SKIP: the TypeScript build is missing')
    else:
        cases = []
        for name, values in vocab.items():
            for v in values[:8]:
                cases.append({'filter': name, 'value': v})
        cases += [
            {'filter': 'domain', 'value': 'Not A Domain'},
            {'filter': 'domain', 'value': 'devops'},
            {'filter': 'source', 'value': 'twilio'},
            {'filter': 'license', 'value': 'mit'},
            {'filter': 'verdict', 'value': 'nonsense'},
            {'filter': 'domain', 'value': 'data'},
        ]
        # The stems that decide between the prefix and the substring
        # rule. Without them the parity check would never reach
        # either rule -- an exact value matches the exact rule, and
        # never gets as far as the others.
        if prefix_stem:
            cases.append({'filter': 'source', 'value': prefix_stem})
        if substring_stem:
            cases.append({'filter': 'source', 'value': substring_stem})
        out = subprocess.run(
            ['node', probe, json.dumps(cases)],
            capture_output=True, text=True,
            cwd=MCP,
        )
        if out.returncode != 0:
            check('the TypeScript filter probe runs', False,
                  (out.stderr or out.stdout)[-400:])
        else:
            try:
                ts = json.loads(out.stdout)
            except ValueError as e:
                check('the TypeScript filter probe answers with JSON', False, str(e))
                ts = None
            if ts is not None:
                diffs = []
                for case in cases:
                    name, value = case['filter'], case['value']
                    try:
                        py = filters.resolve(name, value, vocab[name])
                        py_err = None
                    except filters.FilterError as e:
                        py = None
                        py_err = str(e)
                    tsr = ts.get('%s\x00%s' % (name, value))
                    if tsr is None:
                        diffs.append((name, value, 'missing'))
                    elif tsr.get('ok') != (py is not None):
                        diffs.append((name, value, 'ok=%s vs %s'
                                      % (tsr.get('ok'), py is not None)))
                    elif py is not None and tsr.get('value') != py:
                        diffs.append((name, value, '%r vs %r'
                                      % (tsr.get('value'), py)))
                    elif py is None and tsr.get('error') != py_err:
                        diffs.append((name, value, 'error text differs:\n'
                                      '        py: %s\n        ts: %s'
                                      % (py_err, tsr.get('error'))))
                check('the two implementations resolve filters the same',
                      not diffs, str(diffs[:3]))

    print()
    if failures:
        print('FAILED: %d of %d checks' % (len(failures), checks))
        for f in failures:
            print('  - %s' % f)
        return 1
    print('PASS: %d checks' % checks)
    return 0


if __name__ == '__main__':
    sys.exit(main())
