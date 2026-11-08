#!/usr/bin/env python3
"""Measure the search engine against a labelled query set.

The search engine has two rules that filter the scored entries, and
both were tuned against a labelled query set rather than by feel:

  the token-coverage rule -- an entry must match two thirds of the
                             query's *distinctive* tokens
  the task-index rule     -- a hand-written row fires when the query
                             has 60% of the row's tokens, or all of
                             the row's *content* (its verb dropped)

This script runs the real engine -- the same code the server runs --
over that query set and reports where the wanted skill landed. It is
the regression harness for the ranking: if a change makes the engine
worse, this says so.

    python3 scripts/eval_search.py            # the summary
    python3 scripts/eval_search.py --detail   # every query, with ranks

The thresholds live in the engine itself, so there is nothing to
configure here. To re-tune them, change the constants and re-run.

The labelled set itself lives in `mcp/python/evalranking.py`, because
the documentation renderer quotes these figures -- and a figure
written by hand into a template goes stale.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))

from evalranking import measure                    # noqa: E402

INDEX = os.path.join(MCP, 'data', 'index.json')


def main():
    with open(INDEX) as fh:
        data = json.load(fh)

    detail = '--detail' in sys.argv
    m = measure(data, detail=detail)

    print()
    print('the training set (the ranking was tuned against these)')
    print('  rank 1    : %2d / %d' % (m['top1'], m['measured']))
    print('  rank <= 3 : %2d / %d' % (m['top3'], m['measured']))
    print('  rank <=10 : %2d / %d' % (m['top10'], m['measured']))
    print()
    print('the validation set (held out -- never tuned against)')
    print('  rank 1    : %2d / %d' % (m['val_top1'], m['val_measured']))
    print('  rank <= 3 : %2d / %d' % (m['val_top3'], m['val_measured']))
    print('  rank <=10 : %2d / %d' % (m['val_top10'], m['val_measured']))
    print()
    print('negatives : %d leaked' % m['negatives'])
    print('results per query: median %d, max %d' % (
        m['median_results'], m['max_results']))
    if m['skipped']:
        print('skipped   : %d label(s) name a skill this tree does not '
              'publish -- %s' % (
                  len(m['skipped']),
                  ', '.join('%s (for %r)' % (p[1], p[0]) for p in m['skipped'])))
    if m['val_skipped']:
        print('skipped   : %d validation label(s) name a skill this tree '
              'does not publish -- %s' % (
                  len(m['val_skipped']),
                  ', '.join('%s (for %r)' % (p[1], p[0])
                            for p in m['val_skipped'])))
    if m['failures']:
        print()
        print('failures:')
        for f in m['failures']:
            print('   %s' % (f,))
        sys.exit(1)


if __name__ == '__main__':
    main()
