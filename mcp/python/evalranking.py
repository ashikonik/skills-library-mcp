#!/usr/bin/env python3
"""The labelled query set, and the measurement over it.

Two different labelled sets live in this project, and they answer
different questions:

  * `mcp/tests/queries.py` -- the *golden* set. Every query must return
    the same results in both implementations. It checks that the two
    servers agree.

  * this file -- the *labelled* set. Each query names the skill that
    should win, and some name skills that must NOT win. It checks that
    the search is *good*, not merely that it is consistent.

The two are independent: a search can be perfectly consistent and
useless, and a search can be excellent and inconsistent between
implementations. Both have to hold.

This module lives in `mcp/python/` rather than in `mcp/scripts/`
because two things need it: the evaluation script, and the
documentation renderer -- which quotes the ranking figures in the
architecture guide. When the figures were written by hand into the
template, they went stale; the renderer now measures them against the
tree's own index instead.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from search import SearchIndex  # noqa: E402

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


def measure(data, detail=False):
    """Run the labelled set over an index, and report what happened.

    Returns a dict of counts. This is the measurement the evaluation
    script prints -- factored out so the documentation can state the
    real numbers instead of a copy of them that drifts.

    `data` is the parsed index. The measurement is done against the
    tree's own index, so the published tree's documents quote the
    published tree's ranking.
    """
    idx = SearchIndex(data)

    top1 = top3 = top10 = 0
    failures = []
    totals = []

    # A label naming a skill the tree does not publish cannot be
    # measured. The public tree publishes fewer skills than the local
    # one -- the difference is the entries whose licence does not
    # permit redistribution -- so the labelled set is filtered to what
    # is here, and the skipped labels are reported rather than
    # silently counted.
    published = {s['name'] for s in data['skills']}
    positives = [p for p in POSITIVE if p[1] in published]
    skipped = [p for p in POSITIVE if p[1] not in published]

    for query, wanted, unwanted in positives:
        r = idx.search(query, limit=50)
        ids = [x['id'] for x in r['results']]
        totals.append(r['total_matched'])
        # The labelled set names skills bare ("documentation-lookup");
        # the index namespaces them ("skill:documentation-lookup").
        # Compare on the bare name so the labels stay readable.
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

    return {
        'top1': top1,
        'top3': top3,
        'top10': top10,
        'measured': len(positives),
        'negatives': negatives,
        'median_results': sorted(totals)[len(totals) // 2] if totals else 0,
        'max_results': max(totals) if totals else 0,
        'failures': failures,
        'skipped': skipped,
    }
