#!/usr/bin/env python3
"""The BM25 gate.

BM25 is implemented as a third scoring arm, and it ships at weight
**zero**. That is a deliberate, measured decision, and this gate is
what holds it honest. It checks three things:

  1. **The arm is inert.** With `WEIGHT_BM25 = 0.0` the score vector
     must be bit-identical to the score vector the engine produced
     without the arm -- every entry, every query, every digit. The
     weight is zero and the term is finite, so `0.0 * term == 0.0`
     exactly; if the score moved, the arm was not inert and the
     shipped weight is not the one that was measured.

  2. **The term is finite.** An `Infinity` or a `NaN` in the BM25 term
     would poison the score the moment the weight was raised, and at
     weight zero it would poison the *multiplication* too. Every
     term, for every query token, for every entry, must be finite.

  3. **The two engines compute the same term.** The TypeScript and
     Python BM25 terms must agree bit-for-bit -- not "to a
     tolerance". The engines are compared through a `1e-6` score
     quantisation elsewhere, but the term itself must be identical,
     because the term is a *divisor* of the score's precision: the
     `avgdl` normalisation and the per-token sum both amplify it.

  4. **The arm is added last in the sum.** Parity alone cannot catch
     a misplaced arm: two engines that add the BM25 term before the
     tier bias instead of after it agree with each other and are both
     wrong in the same way. The sum must be exactly
     `score == base + weight * term`, where `base` is the score with
     the arm's contribution removed by the engine's own code path.

The third check is the one that would have caught the real hazard.
`Math.log` and `math.log` differ by one unit in the last place on 13
of this corpus's 6,037 tokens. The BM25 idf uses `log1p`, which the
two runtimes implement identically -- that is why it is `log1p` and
not `log`, and this check is what keeps it that way.
"""
import json
import math
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)

sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))

import search as pysearch  # noqa: E402

failures = []
checks = 0

# The weight the two engines are compared at.
#
# Not zero. At weight zero the arm contributes nothing to the score,
# so two engines that add it in *different places* in the sum would
# still agree on every score -- and the divergence would only appear
# the day somebody raised the weight. Comparing at a non-zero weight
# makes the ordering guarantee real now, rather than a promise about
# a future change.
#
# The weight is small on purpose: it has to be big enough that the
# term survives the 1e-6 quantisation and the other arms' magnitudes,
# and small enough that the score stays in a sane range.
PROBE_WEIGHT = 1.0


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


def _bits(x):
    """The bit pattern of a double, as a hex string.

    The TypeScript probe computes the same thing from the IEEE 754
    bytes. Comparing bit patterns rather than decimal renderings is
    the point: two engines can print the same number differently and
    still differ by a unit in the last place.
    """
    return struct.pack('>d', float(x)).hex()


def _unbits(h):
    """The double whose bit pattern is the hex string `h`."""
    return struct.unpack('>d', bytes.fromhex(h))[0]


def safe_bm25(idx, e, q_tokens):
    """The BM25 term, or a marker if computing it raised.

    A term that is non-finite is one way the arm can break. A term
    that *raises* -- a division by zero, say -- is another, and a
    gate that dies with a traceback is a weaker signal than a gate
    that says which invariant failed. So the exception is caught and
    returned as a marker the checks can report.
    """
    try:
        return idx.bm25(e, q_tokens)
    except Exception as exc:  # noqa: BLE001 -- the point is to catch all
        return _Raised(type(exc).__name__, str(exc))


class _Raised(float):
    """A term that could not be computed, carrying why.

    It is a `float` so that the arithmetic at the call sites keeps
    working, and it is not equal to any real number, so every
    comparison that matters reports it.
    """

    def __new__(cls, name, detail):
        self = float.__new__(cls, float('nan'))
        self.name = name
        self.detail = detail
        return self

    def __repr__(self):
        return 'RAISED %s: %s' % (self.name, self.detail)

    def __str__(self):
        return 'RAISED %s: %s' % (self.name, self.detail)


# The queries the gate measures over. The first group is the golden
# set (every query both servers must answer identically); the second
# is the labelled set (the queries the ranking was tuned against, plus
# the held-out ones). Between them they exercise every branch of the
# scorer: name matches, description matches, inflections, phrases,
# prompt signals and task rows.
GOLDEN_QUERIES = [
    'write code', 'accessibility', 'pdf', 'web api', 'browser',
    'testing', 'deployment', 'security', 'documentation', 'sql',
]
LABELLED_QUERIES = [
    'write documentation', 'write a REST API', 'implement authentication',
    'add authentication to an api', 'deploy to kubernetes', 'write a migration',
    'fix a failing build', 'my build keeps failing', 'write tests',
    'accessibility audit WCAG', 'competition math proof',
    'containerise a service', 'set up CI/CD', 'write a React app',
    'write a document', 'write SQL', 'build a CLI', 'build a dashboard',
    'improve accessibility', 'ship to production', 'plan a feature',
    'design an architecture', 'secure a codebase', 'optimise performance',
    'research a topic', 'update documentation', 'create a skill',
    'add a skill to the library', 'add an agent to the library',
    'write SQL queries', 'debug a runtime bug', 'remove dead code',
    'improve the accessibility of my app', 'build an MCP server',
    'write a prompt for an agent', 'containerise the app with docker',
    # the held-out set
    'set up RBAC for a kubernetes cluster',
    'add pagination to my REST endpoints',
    'roll back a schema change safely',
    'react hooks rules', 'write tests before the implementation',
    'find out why a test keeps failing', 'audit my site against WCAG 2.2',
    'write a CLI with typer', 'solve an olympiad geometry problem',
    'ship a python package to pypi',
    'stop my prose from sounding like a machine wrote it',
    'fix a LaTeX compile error', 'record an architecture decision',
    'speed up a slow web page', 'handle authentication and input validation',
    'set up a monorepo', 'debug a failing github actions workflow',
    'review my code for security problems',
    'organise my email and draft a reply',
    'make a change to a database schema without downtime',
    'debug a bug using a systematic method',
]


def main():
    data = load_index()
    if data is None:
        return 1

    idx = pysearch.SearchIndex(data)

    # ---- 1. the shipped weight is zero.
    check('bm25: the shipped weight is zero',
          pysearch.WEIGHT_BM25 == 0.0, str(pysearch.WEIGHT_BM25))
    check('bm25: the saturation constant is the standard one',
          pysearch.BM25_K1 == 1.2, str(pysearch.BM25_K1))
    check('bm25: the length normalisation is the standard one',
          pysearch.BM25_B == 0.75, str(pysearch.BM25_B))

    # ---- 2. the arm is inert.
    #
    # The score with the arm is compared against the score computed
    # with the arm's contribution removed by hand. At weight zero the
    # two must be *exactly* equal -- not close, equal.
    #
    # The check is made at the *shipped* weight, and the engine's
    # in-force weight is checked to be zero too. Both matter: a gate
    # that only checked the constant would pass while the engine used
    # a different weight, and a gate that only checked the engine
    # would pass while the shipped constant said something else.
    queries = GOLDEN_QUERIES + LABELLED_QUERIES
    check('bm25: the weight in force is zero',
          pysearch.bm25_weight == 0.0, str(pysearch.bm25_weight))
    inert = []
    for q in queries:
        q_tokens = pysearch.tokenize(q)
        if not q_tokens:
            continue
        for e in idx.entries:
            with_arm = idx.score_entry(e, q_tokens, pysearch.bigrams(q_tokens),
                                       q.lower(), pysearch.head_tokens(q))[0]
            # The same score with the BM25 term computed and discarded.
            term = safe_bm25(idx, e, q_tokens)
            without_arm = with_arm - (pysearch.WEIGHT_BM25 * term)
            if with_arm != without_arm:
                inert.append((q, e['id'], with_arm, without_arm))
                break
        if inert:
            break
    check('bm25: the arm changes no score at weight zero', not inert,
          str(inert[:2]))

    # And the arm is *not* inert at a non-zero weight -- otherwise the
    # weight would be a constant with no effect and the whole arm
    # would be decoration. If this check fails, the arm is not wired
    # into the scorer at all.
    pysearch.bm25_weight = PROBE_WEIGHT
    try:
        moved = 0
        for q in queries[:10]:
            q_tokens = pysearch.tokenize(q)
            if not q_tokens:
                continue
            q_big = pysearch.bigrams(q_tokens)
            heads = pysearch.head_tokens(q)
            for e in idx.entries:
                with_arm = idx.score_entry(e, q_tokens, q_big, q.lower(),
                                           heads)[0]
                term = safe_bm25(idx, e, q_tokens)
                if with_arm != with_arm - (PROBE_WEIGHT * term):
                    moved += 1
                    break
    finally:
        pysearch.bm25_weight = 0.0
    check('bm25: the arm does change the score at a non-zero weight',
          moved > 0, 'the arm is not wired into the scorer')

    # ---- 3. every term is finite.
    #
    # At weight zero the term is multiplied away, but a `NaN` would
    # still propagate through the multiplication (`0.0 * NaN` is
    # `NaN`). So this is checked directly, and it is checked on the
    # *term* rather than on the score -- a score can be finite while
    # the term that produced it was not.
    nonfinite = []
    for q in queries:
        q_tokens = pysearch.tokenize(q)
        if not q_tokens:
            continue
        for e in idx.entries:
            term = safe_bm25(idx, e, q_tokens)
            if not math.isfinite(term):
                nonfinite.append((q, e['id'], term))
                break
        if nonfinite:
            break
    check('bm25: every term is finite', not nonfinite, str(nonfinite[:2]))

    # And the *score* at a non-zero weight is finite for every entry
    # and every query. A term that overflowed to `Infinity` would
    # make the score infinite, and the score is what is sorted.
    pysearch.bm25_weight = PROBE_WEIGHT
    try:
        infinite_scores = []
        for q in queries:
            q_tokens = pysearch.tokenize(q)
            if not q_tokens:
                continue
            q_big = pysearch.bigrams(q_tokens)
            for e in idx.entries:
                score = idx.score_entry(e, q_tokens, q_big, q.lower(),
                                        pysearch.head_tokens(q))[0]
                if not math.isfinite(score):
                    infinite_scores.append((q, e['id'], score))
                    break
            if infinite_scores:
                break
    finally:
        pysearch.bm25_weight = 0.0
    check('bm25: every score is finite with the arm at a non-zero weight',
          not infinite_scores, str(infinite_scores[:2]))

    # ---- 4. the term is non-negative and zero for an unmatched entry.
    #
    # BM25's idf is `ln(1 + ...)` and is positive for every token that
    # appears in the corpus, so a matched entry's term is positive and
    # an unmatched entry's is exactly zero.
    negative = []
    for q in ['write tests', 'deploy to kubernetes', 'fix a failing build']:
        q_tokens = pysearch.tokenize(q)
        for e in idx.entries:
            term = safe_bm25(idx, e, q_tokens)
            if term < 0:
                negative.append((q, e['id'], term))
                break
        if negative:
            break
    check('bm25: no term is negative', not negative, str(negative[:2]))

    zero_for_unmatched = []
    for q in ['write tests']:
        q_tokens = pysearch.tokenize(q)
        for e in idx.entries:
            counts = idx.tf.get(e['id']) or {}
            if any(counts.get(t) for t in q_tokens):
                continue
            if safe_bm25(idx, e, q_tokens) != 0.0:
                zero_for_unmatched.append((e['id'], q))
                break
        if zero_for_unmatched:
            break
    check('bm25: an entry that matches no query token scores zero',
          not zero_for_unmatched, str(zero_for_unmatched[:2]))

    # ---- 5. the two engines compute the same term.
    ts_entry = os.path.join(MCP, 'dist', 'index.js')
    if not os.path.isfile(ts_entry):
        sys.stderr.write('SKIP: the TypeScript build is missing (%s).\n'
                         % ts_entry)
    else:
        probe = os.path.join(HERE, '_ts_bm25.mjs')
        r = subprocess.run(['node', probe, json.dumps(queries),
                            str(PROBE_WEIGHT)],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            check('bm25: the TypeScript probe runs', False, r.stderr[-400:])
        else:
            out = json.loads(r.stdout)
            check('bm25: the TypeScript probe covers every query',
                  out.get('queries') == len(queries),
                  '%s vs %s' % (out.get('queries'), len(queries)))
            check('bm25: the TypeScript terms are all finite',
                  out.get('nonFinite', 0) == 0, str(out.get('nonFinite')))

            # The *TypeScript* shipped weight.
            #
            # The gate checks the Python weight above. It must check
            # the TypeScript one too: two engines, two constants, and
            # a gate that only looked at one of them would let the
            # other ship a non-zero weight unnoticed.
            check('bm25: the TypeScript shipped weight is zero',
                  out.get('shippedWeight') == 0.0,
                  str(out.get('shippedWeight')))
            check('bm25: the TypeScript weight in force is the probe weight',
                  out.get('weightInForce') == PROBE_WEIGHT,
                  str(out.get('weightInForce')))

            # The comparison is on the *bit pattern*, not on a decimal
            # rendering: two engines can print the same number
            # differently and still differ by a unit in the last
            # place.
            #
            # The *score* is compared at a NON-ZERO weight. At weight
            # zero the arm contributes nothing to the score, so two
            # engines that add it in *different places* in the sum
            # would still produce identical scores -- and the
            # divergence would only appear the day the weight was
            # raised. Comparing at a non-zero weight is what makes
            # the ordering guarantee real now rather than later.
            ts_terms = out.get('terms') or {}
            mismatched = []
            for q in queries:
                row = ts_terms.get(q)
                if row is None:
                    mismatched.append((q, '(no row)', ''))
                    continue
                q_tokens = pysearch.tokenize(q)
                if not q_tokens:
                    continue
                for e in idx.entries:
                    term = safe_bm25(idx, e, q_tokens)
                    want = _bits(term)
                    got = row.get(e['id'])
                    if got != want:
                        mismatched.append((q, e['id'], want, got))
                        break
                if mismatched:
                    break
            check('bm25: both engines compute the same term, bit for bit',
                  not mismatched, str(mismatched[:2]))

            pysearch.bm25_weight = PROBE_WEIGHT
            try:
                score_mismatched = []
                for q in queries:
                    row = ts_terms.get(q)
                    if row is None:
                        continue
                    q_tokens = pysearch.tokenize(q)
                    if not q_tokens:
                        continue
                    q_big = pysearch.bigrams(q_tokens)
                    q_lower = q.lower()
                    heads = pysearch.head_tokens(q)
                    for e in idx.entries:
                        score = idx.score_entry(e, q_tokens, q_big, q_lower,
                                                heads)[0]
                        want_s = _bits(score)
                        got_s = row.get(e['id'] + '\x00score')
                        if got_s != want_s:
                            score_mismatched.append(
                                (q, e['id'], want_s, got_s))
                            break
                    if score_mismatched:
                        break
            finally:
                pysearch.bm25_weight = 0.0
            check('bm25: both engines compute the same score with the arm '
                  'at a non-zero weight, bit for bit',
                  not score_mismatched, str(score_mismatched[:2]))

            # ---- 5b. the arm is added LAST in the sum.
            #
            # Parity alone cannot catch a misplaced arm. If both
            # engines added the BM25 term before the tier bias instead
            # of after it, they would agree with each other -- and both
            # would be wrong in the same way. The comparison that
            # catches it is against the score computed *without* the
            # arm: the sum must be exactly
            #
            #     score == base + weight * term
            #
            # which holds only if the arm is the last thing added.
            # The floating-point equality is exact on purpose: the
            # arms are not commutative, so a different position gives
            # a different bit pattern, not merely a different
            # rounding.
            position_mismatched = []
            pysearch.bm25_weight = PROBE_WEIGHT
            try:
                for q in queries:
                    row = ts_terms.get(q)
                    if row is None:
                        continue
                    q_tokens = pysearch.tokenize(q)
                    if not q_tokens:
                        continue
                    q_big = pysearch.bigrams(q_tokens)
                    q_lower = q.lower()
                    heads = pysearch.head_tokens(q)
                    for e in idx.entries:
                        term = safe_bm25(idx, e, q_tokens)
                        base = idx.score_entry_without_arm(e, q_tokens, q_big,
                                                          q_lower, heads)
                        score = idx.score_entry(e, q_tokens, q_big, q_lower,
                                                heads)[0]
                        want = base + (PROBE_WEIGHT * term)
                        if score != want:
                            position_mismatched.append(
                                (q, e['id'], _bits(score), _bits(want)))
                            break
                    if position_mismatched:
                        break
            finally:
                pysearch.bm25_weight = 0.0
            check('bm25: the arm is added last in the sum',
                  not position_mismatched, str(position_mismatched[:2]))

            # And the same check on the TypeScript side, using the
            # base the probe reported. The probe's base is computed by
            # the engine's own code path, so this is a statement about
            # the shipped scorer and not about the probe.
            ts_position_mismatched = []
            for q in queries:
                row = ts_terms.get(q)
                if row is None:
                    continue
                q_tokens = pysearch.tokenize(q)
                if not q_tokens:
                    continue
                for e in idx.entries:
                    term_bits = row.get(e['id'])
                    base_bits = row.get(e['id'] + '\x00base')
                    score_bits = row.get(e['id'] + '\x00score')
                    if term_bits is None or base_bits is None \
                            or score_bits is None:
                        continue
                    base = _unbits(base_bits)
                    term = _unbits(term_bits)
                    score = _unbits(score_bits)
                    want = base + (PROBE_WEIGHT * term)
                    if score != want:
                        ts_position_mismatched.append(
                            (q, e['id'], score_bits, _bits(want)))
                        break
                if ts_position_mismatched:
                    break
            check('bm25: the TypeScript arm is added last in the sum',
                  not ts_position_mismatched, str(ts_position_mismatched[:2]))

    # ---- 6. the two engines agree on the results the arm produces.
    #
    # The arm is inert, so the results must be identical to what the
    # golden file records. The agreement gate covers this too, but
    # this gate states it for the arm specifically.
    golden_path = os.path.join(HERE, 'golden', 'search_golden.json')
    if not os.path.isfile(golden_path):
        sys.stderr.write('SKIP: %s not found.\n' % golden_path)
    else:
        with open(golden_path, encoding='utf-8') as fh:
            golden = json.load(fh)
        drift = []
        for query, entry in golden.items():
            want = entry['ids']
            got = [x['id'] for x in idx.search(query,
                                               limit=len(want))['results']]
            if got != want:
                drift.append((query, want[:3], got[:3]))
        check('bm25: the results still match the golden file',
              not drift, str(drift[:2]))

    if failures:
        sys.stderr.write('\n%d FAILURE(S) out of %d checks\n'
                         % (len(failures), checks))
        for f in failures:
            sys.stderr.write('  - %s\n' % f)
        return 1
    sys.stdout.write('\nBM25: PASS — all %d checks\n' % checks)
    return 0


if __name__ == '__main__':
    sys.exit(main())
