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
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))

from search import SearchIndex                       # noqa: E402

INDEX = os.path.join(MCP, 'data', 'index.json')

# (query, the skill that should win, [skills that must not outrank it])
POSITIVE = [
    ('write documentation', 'documentation-lookup', ['mixpanelyst']),
    ('write a REST API', 'api-design', []),
    ('implement authentication', 'twilio-security-api-auth', []),
    ('add authentication to an api', 'twilio-security-api-auth', []),
    ('deploy to kubernetes', 'kubernetes-patterns', ['netlify-deploy']),
    ('write a migration', 'database-migrations', []),
    ('fix a failing build', 'error-handling', []),
    ('my build keeps failing', 'error-handling', []),
    ('write tests', 'tdd-workflow', []),
    ('accessibility audit WCAG', 'accessibility', []),
    ('competition math proof', 'math-olympiad', []),
    ('containerise a service', 'docker-patterns', []),
    ('set up CI/CD', 'circleci-config', []),
    ('write a React app', 'react-patterns', []),
    ('write a document', 'document-builder', []),
    ('write SQL', 'mysql-patterns', []),
    ('build a CLI', 'typer', []),
    ('build a dashboard', 'dashboard-builder', []),
    ('improve accessibility', 'accessibility', []),
    ('ship to production', 'deployment-patterns', []),
    ('plan a feature', 'executing-plans', []),
    ('design an architecture', 'architecture-decision-records', []),
    ('secure a codebase', 'security-review', []),
    ('optimise performance', 'performance-optimizer', []),
    ('research a topic', 'deep-research', []),
    ('update documentation', 'doc-updater', []),
    ('create a skill', 'skill-creator-plus', []),
    ('add a skill to the library', 'skill-library-adder', []),
    ('add an agent to the library', 'skill-library-adder', []),
    ('write SQL queries', 'postgres-patterns', []),
    ('debug a runtime bug', 'systematic-debugging', []),
    ('remove dead code', 'codehealth-mcp', []),
    ('improve the accessibility of my app', 'accessibility', []),
    ('build an MCP server', 'mcp-server-patterns', []),
    ('write a prompt for an agent', 'agent-harness-construction', []),
    ('containerise the app with docker', 'docker-patterns', []),
]

# (query, a skill that must NOT appear, or None for "nothing at all")
NEGATIVE = [
    ('bake sourdough bread at home', 'shopify-polaris-app-home'),
    ('quantum chromodynamics lattice simulation', 'web-game-foundations'),
    ('how to bake sourdough bread at home', 'shopify-polaris-app-home'),
    ('my cat knocked over a plant', None),
    ('the weather in copenhagen tomorrow', None),
    ('how do I make pasta', None),
    ('give me a recipe for risotto', None),
    ('what is the capital of Peru', None),
    ('translate this to french', None),
    ('the train is late again', None),
    ('what should I eat for dinner', None),
]


def main():
    with open(INDEX) as fh:
        data = json.load(fh)
    idx = SearchIndex(data)

    detail = '--detail' in sys.argv
    top1 = top3 = top10 = 0
    failures = []
    totals = []

    # A label naming a skill the tree does not publish cannot be measured.
    # The public tree publishes fewer skills than the local one -- the
    # difference is the entries whose licence does not permit
    # redistribution -- so the labelled set is filtered to what is here,
    # and the skipped labels are reported rather than silently counted.
    published = {s['name'] for s in data['skills']}
    positives = [p for p in POSITIVE if p[1] in published]
    skipped = [p for p in POSITIVE if p[1] not in published]

    for query, wanted, unwanted in positives:
        r = idx.search(query, limit=50)
        ids = [x['id'] for x in r['results']]
        totals.append(r['total_matched'])
        # The labelled set names skills bare ("documentation-lookup"); the
        # index namespaces them ("skill:documentation-lookup"). Compare on
        # the bare name so the labels stay readable.
        bare = [i.split(':', 1)[-1] for i in ids]
        rank = bare.index(wanted) + 1 if wanted in bare else None
        if rank is not None:
            if rank <= 1:
                top1 += 1
            if rank <= 3:
                top3 += 1
            if rank <= 10:
                top10 += 1
        else:
            failures.append((query, wanted, 'absent'))
        for u in unwanted:
            if u in bare and rank is not None and bare.index(u) < rank - 1:
                failures.append((query, wanted, 'outranked by %s' % u))
        if detail:
            print('  %-42s rank=%-5s total=%-4d %s' % (
                query, rank, r['total_matched'], ', '.join(ids[:4])))

    negatives = 0
    for query, unwanted in NEGATIVE:
        r = idx.search(query, limit=50)
        ids = [x['id'] for x in r['results']]
        bare = [i.split(':', 1)[-1] for i in ids]
        if unwanted:
            if unwanted in bare:
                negatives += 1
                failures.append((query, None, 'leaked %s' % unwanted))
        elif ids:
            negatives += 1
            failures.append((query, None, 'returned %s' % ids[:3]))
        if detail:
            print('  NEG %-42s %s' % (query, ids[:3]))

    print()
    print('rank 1    : %2d / %d' % (top1, len(positives)))
    print('rank <= 3 : %2d / %d' % (top3, len(positives)))
    print('rank <=10 : %2d / %d' % (top10, len(positives)))
    print('negatives : %d leaked' % negatives)
    print('results per query: median %d, max %d' % (
        sorted(totals)[len(totals) // 2], max(totals)))
    if skipped:
        print('skipped   : %d label(s) name a skill this tree does not '
              'publish -- %s' % (
                  len(skipped),
                  ', '.join('%s (for %r)' % (p[1], p[0]) for p in skipped)))
    if failures:
        print()
        print('failures:')
        for f in failures:
            print('   %s' % (f,))
        sys.exit(1)
    print()
    print('SEARCH EVAL: PASS')


if __name__ == '__main__':
    main()
