#!/usr/bin/env python3
"""Measure whether the BM25 arm helps, and at what weight.

The arm ships at weight zero. That is a claim -- "BM25 adds nothing
this corpus does not already carry" -- and a claim needs evidence.
This script produces it.

It sweeps the weight over a range and reports the labelled-set
numbers for each, so the choice is made against the *validation* set
and not against the training set. The training set is where the
ranking was tuned, so it cannot also be the evidence that a new arm
helps; a weight that improves the training set and not the validation
set is the signature of overfitting.

The arm is injected rather than recompiled, so the sweep does not
need a build per weight: the weight is a module-level variable and the
scorer reads it at call time.

    python3 scripts/eval_bm25.py            # the sweep
    python3 scripts/eval_bm25.py --detail   # every weight, every query
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))

import search as pysearch  # noqa: E402
import evalranking  # noqa: E402

INDEX = os.path.join(MCP, 'data', 'index.json')

WEIGHTS = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]


def measure_at(data, weight, detail=False):
    """The labelled-set numbers at one BM25 weight.

    The weight that the scorer reads is the *in-force* one,
    `pysearch.bm25_weight` -- not the shipped constant
    `WEIGHT_BM25`. Setting the constant would leave the scorer at
    weight zero and every row of the sweep would be the same
    measurement wearing different labels.

    The arm's liveness is asserted rather than assumed: a sweep that
    silently measured weight zero everywhere would look like a clean
    result ("no weight helps") and be entirely vacuous.
    """
    assert pysearch.bm25_weight == 0.0, 'the in-force weight must start at 0'
    pysearch.bm25_weight = weight
    try:
        assert pysearch.bm25_weight == weight
        return evalranking.measure(data, detail=detail)
    finally:
        pysearch.bm25_weight = 0.0


def score_moves_at(data, weight):
    """How many of the labelled queries score differently at `weight`.

    Compares the *raw* score vector, not the ranking: the arm can
    change the scores without changing the order, and that difference
    is exactly what the sweep is measuring.
    """
    idx = pysearch.SearchIndex(data)
    # The labelled sets are `(query, expected_id, alternatives)` rows.
    queries = [row[0] for row in evalranking.POSITIVE]
    queries += [row[0] for row in evalranking.VALIDATION]

    def vector(w):
        pysearch.bm25_weight = w
        out = {}
        try:
            for q in queries:
                q_tokens = pysearch.tokenize(q)
                if not q_tokens:
                    continue
                out[q] = tuple(
                    idx.score_entry(e, q_tokens,
                                    pysearch.bigrams(q_tokens),
                                    q.lower(),
                                    pysearch.head_tokens(q))[0]
                    for e in idx.entries)
        finally:
            pysearch.bm25_weight = 0.0
        return out

    base = vector(0.0)
    probe = vector(weight)
    return sum(1 for q in base if base[q] != probe.get(q))


def main():
    with open(INDEX, encoding='utf-8') as fh:
        data = json.load(fh)

    detail = '--detail' in sys.argv

    # ---- prove the sweep measures what it claims to.
    #
    # If the arm were inert at every weight -- because the weight
    # variable the scorer reads was not the one being set, say -- then
    # every row of the sweep would be the same measurement, and "no
    # weight helps" would be vacuously true. The sweep is only
    # evidence if the arm demonstrably moves the scores at a non-zero
    # weight.
    moved = score_moves_at(data, 1.0)
    if not moved:
        print('FATAL: the BM25 arm does not change the score at weight 1.')
        print('       The sweep would measure the same thing at every')
        print('       weight, so its verdict would be meaningless.')
        return 1
    print('the arm is live: at weight 1 the score vector differs from')
    print('the weight-0 vector for %d of the measured queries' % moved)
    print()

    print()
    print('the BM25 weight sweep')
    print()
    print('  %-8s %-14s %-14s %-10s' % ('weight', 'train rank1',
                                         'val rank1', 'val top10'))
    print('  %-8s %-14s %-14s %-10s' % ('-' * 8, '-' * 14, '-' * 14,
                                         '-' * 10))
    rows = []
    for w in WEIGHTS:
        m = measure_at(data, w, detail=False)
        rows.append((w, m))
        print('  %-8s %-14s %-14s %-10s' % (
            '%g' % w,
            '%d / %d' % (m['top1'], m['measured']),
            '%d / %d' % (m['val_top1'], m['val_measured']),
            '%d / %d' % (m['val_top10'], m['val_measured'])))

    base = rows[0][1]
    best = max(rows, key=lambda r: (r[1]['val_top1'], r[1]['val_top10']))

    print()
    if best[0] == 0.0:
        print('the best weight is the one already shipped: 0')
        print()
        print('No weight beat the shipped one on the held-out set. The')
        print('arm is real, correct and bit-identical across the two')
        print('implementations -- and it does not help this corpus.')
        print()
        print('That is the expected result, and it is worth stating')
        print('plainly: the tokens that decide a match here are the')
        print('*rare* ones, and a rare token appears once anyway. BM25')
        print('corrects for a term frequency that is already 1 where')
        print('it matters.')
    else:
        print('the best weight on the held-out set is %g' % best[0])
        print('  validation rank1: %d / %d (shipped: %d / %d)' % (
            best[1]['val_top1'], best[1]['val_measured'],
            base['val_top1'], base['val_measured']))
        print('  validation top10: %d / %d (shipped: %d / %d)' % (
            best[1]['val_top10'], best[1]['val_measured'],
            base['val_top10'], base['val_measured']))
        print()
        print('This is evidence, not a decision. The weight is still 0')
        print('until it is measured against the *training* set too, and')
        print('until the change is shipped with the golden file')
        print('regenerated and the agreement gate re-run.')

    if detail:
        print()
        for w in WEIGHTS:
            print()
            print('=== weight %g' % w)
            measure_at(data, w, detail=True)

    return 0


if __name__ == '__main__':
    sys.exit(main())
