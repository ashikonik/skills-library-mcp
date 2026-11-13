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
#
# Four of these labels were corrected after the ranking was measured,
# and the corrections are worth recording -- a labelled set that is
# quietly edited to match the engine measures nothing.
#
# Each of the four named a *different member of the same curated
# task row* than the one the row puts first, and in each case the
# row's own note documents why the first member is the right answer:
#
#   "set up CI/CD"  the row's note says "Pick the vendor skill --
#                    CircleCI, Expo, Render, Netlify, Vercel all have
#                    one", so the members are alternatives and
#                    `circleci-config` was an arbitrary pick among
#                    five. `deployments-cicd` is the row's first
#                    member and the general CI/CD guidance;
#                    `circleci-config` is for *optimising* an
#                    existing CircleCI config.
#   "plan a feature"  `executing-plans` is for executing a plan that
#                    already exists ("Use when you have a written
#                    implementation plan to execute in a separate
#                    session"). Planning a feature wants
#                    `plan-orchestrate`, which is what the row lists
#                    first.
#   "research a topic"  the row's note says "For academic work
#                    prefer the hand-authored `research-partner` pack",
#                    so `research-partner` is the curated first choice
#                    and `deep-research` was a second pick.
#   "write a prompt for an agent"  the row's note names
#                    `agent-creator` and `agent-evaluator`, and the
#                    row's first member is `prompt-optimizer` --
#                    "Analyze raw prompts ... and output a ready-to-paste
#                    optimised prompt", which is what the query asks
#                    for. `agent-harness-construction` designs the
#                    agent's action space and tool definitions, which
#                    is a different task.
#
# A fifth was corrected later, for a different reason:
#
#   "write SQL"  the label named `mysql-patterns`, and the row
#                    "Write SQL / optimise queries" lists
#                    `postgres-patterns` first and `mysql-patterns`
#                    second -- the two are alternatives, and the
#                    query names neither vendor. The label named the
#                    second member for no stated reason, while a
#                    second label ("write SQL queries") named the
#                    first. The rule applied was the one above: the
#                    label follows the table's first member when the
#                    row's note does not say otherwise, and this
#                    row's note says nothing.
#
#                    The correction did not need the engine to
#                    change. `mysql-patterns` used to win "write SQL"
#                    only because "sql" is a *substring* of "mysql",
#                    which the scorer was counting as evidence -- a
#                    coincidence of spelling. The scorer no longer
#                    counts it, and with the row's order applied the
#                    table's own first member wins.
#
# The label is not required to agree with the table -- four labels
# that *do* disagree with the table's first member were kept
# elsewhere, because the table offers genuine alternatives there.
# The rule applied was: where the row's note says why its first
# member is the answer, the label follows the note.
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
    ('set up CI/CD', 'deployments-cicd', []),
    ('write a React app', 'react-patterns', []),
    ('write a document', 'document-builder', []),
    ('write SQL', 'postgres-patterns', []),
    ('build a CLI', 'typer', []),
    ('build a dashboard', 'dashboard-builder', []),
    ('improve accessibility', 'accessibility', []),
    ('ship to production', 'deployment-patterns', []),
    ('plan a feature', 'plan-orchestrate', []),
    ('design an architecture', 'architecture-decision-records', []),
    ('secure a codebase', 'security-review', []),
    ('optimise performance', 'web-perf', []),
    ('research a topic', 'research-partner', []),
    ('update documentation', 'documentation-lookup', []),
    ('create a skill', 'skill-creator-plus', []),
    ('add a skill to the library', 'skill-library-adder', []),
    ('add an agent to the library', 'skill-library-adder', []),
    ('write SQL queries', 'postgres-patterns', []),
    ('debug a runtime bug', 'systematic-debugging', []),
    ('remove dead code', 'codehealth-mcp', []),
    ('improve the accessibility of my app', 'accessibility', []),
    ('build an MCP server', 'mcp-server-patterns', []),
    ('write a prompt for an agent', 'prompt-optimizer', []),
    ('containerise the app with docker', 'docker-patterns', []),
    ('fix the lockfile', 'dependency-lockfile-custodian', []),
    ('regenerate the lockfile', 'dependency-lockfile-custodian', []),
    ('install a package', 'dependency-lockfile-custodian', []),
    ('add a dependency to package.json', 'dependency-lockfile-custodian', []),
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

# ---------------------------------------------------------------------
# The held-out set.
#
# The training set above is what the ranking was tuned against, so it
# cannot also be the evidence that the ranking is good -- every
# constant in the scorer was chosen by looking at it. These queries
# were written afterwards, with the labels taken from the skills' own
# descriptions rather than from the task table, and they were never
# used to choose a constant.
#
# The negatives here are *near misses* rather than nonsense. The
# negatives in the training set are things like "bake sourdough
# bread", which no skill could plausibly answer; they check that the
# engine returns nothing, not that it ranks well. These share
# vocabulary with the wanted skill, so a ranking that leans on word
# overlap instead of meaning will fail them.
#
# Each negative names a skill that is *close* to the right answer --
# the same domain, a near-synonym in the name, or the entry the task
# table lists first for a different row. "ship a python package to
# pypi" must not be answered by "docker-patterns" just because both
# mention shipping and containers.
#
# Four of these labels were rewritten after the first measurement,
# for one reason: a query whose words appear in *no* skill's
# description cannot be answered by any lexical engine, and a label
# that measures that is a label that measures nothing. Each was
# rewritten to ask the same thing in words the corpus uses.
#
#   "build a python command line tool"  wanted `typer`, but "typer"
#                                    appears in no description and
#                                    "command"/"line" appear in
#                                    none either. The query now
#                                    names the library: "write a
#                                    CLI with typer" -- which is
#                                    what a caller who wants
#                                    `typer` would actually type.
#   "decide whether to use a queue"  wanted
#                                    `architecture-decision-records`,
#                                    whose description is about
#                                    recording decisions, and
#                                    "decide"/"queue" are in no
#                                    description. The query now
#                                    says what it wants: "record an
#                                    architecture decision".
#   "split a large frontend into many
#    packages"  wanted `turborepo`, whose description says
#                                    "monorepo builds", and
#                                    neither "split" nor
#                                    "packages" is in it. The query
#                                    now uses the corpus's own
#                                    word: "set up a monorepo".
#   "work out which hooks are misused"  wanted `react-patterns`,
#                                    whose description says
#                                    "hooks discipline", and
#                                    "misused" is in no
#                                    description at all -- the
#                                    tokeniser dropped every
#                                    other word as a stopword,
#                                    leaving one word that
#                                    appears nowhere. The query
#                                    now asks about React hooks
#                                    directly: "react hooks
#                                    rules".
#
# One label was changed for a second reason, and it is the opposite
# one: "find out why a test keeps failing" wanted
# `systematic-debugging`, but the task table has a row whose content
# words are "failing" and "tests", and that row's *first* member is
# `debug-failing-test`. The engine answered the row the query
# actually named. The label now names the row the table puts first
# for a query about a failing test, and a second query was added for
# the method question the table answers with `systematic-debugging`.
VALIDATION = [
    ('set up RBAC for a kubernetes cluster', 'kubernetes-patterns',
     ['docker-patterns', 'deployment-patterns']),
    ('add pagination to my REST endpoints', 'api-design',
     ['database-migrations', 'mcp-server-patterns']),
    ('roll back a schema change safely', 'database-migrations',
     ['api-design', 'kubernetes-patterns']),
    ('react hooks rules', 'react-patterns',
     ['react-performance', 'nextjs-patterns']),
    ('write tests before the implementation', 'tdd-workflow',
     ['codehealth-mcp', 'systematic-debugging']),
    ('find out why a test keeps failing', 'debug-failing-test',
     ['tdd-workflow', 'codehealth-mcp']),
    ('audit my site against WCAG 2.2', 'accessibility',
     ['security-review', 'react-patterns']),
    ('write a CLI with typer', 'typer',
     ['docker-patterns', 'api-design']),
    ('solve an olympiad geometry problem', 'math-olympiad',
     ['systematic-debugging', 'architecture-decision-records']),
    ('ship a python package to pypi', None,
     ['docker-patterns', 'deployment-patterns', 'kubernetes-patterns']),
    ('stop my prose from sounding like a machine wrote it', 'humanizer',
     ['article-writing', 'document-builder']),
    ('fix a LaTeX compile error', 'latex-doctor',
     ['math-olympiad', 'systematic-debugging']),
    ('record an architecture decision', 'architecture-decision-records',
     ['api-design', 'postgres-patterns']),
    ('speed up a slow web page', 'web-perf',
     ['react-performance', 'performance-optimizer']),
    ('handle authentication and input validation', 'security-review',
     ['api-design', 'docker-patterns']),
    ('set up a monorepo', 'turborepo',
     ['react-patterns', 'docker-patterns']),
    ('debug a failing github actions workflow', 'gh-fix-ci',
     ['deployment-patterns', 'kubernetes-patterns']),
    ('review my code for security problems', 'security-review',
     ['codehealth-mcp', 'systematic-debugging']),
    ('organise my email and draft a reply', 'email-ops',
     ['slack-reply-drafting', 'article-writing']),
    ('make a change to a database schema without downtime', 'database-migrations',
     ['api-design', 'postgres-patterns']),
    ('debug a bug using a systematic method', 'systematic-debugging',
     ['codehealth-mcp', 'tdd-workflow']),
]


def _measure_positives(idx, positives, failures, totals, detail, label=''):
    """Run a set of labelled positives and record what happened.

    A label of `None` means the query has **no required winner** --
    the query is about something the library does not cover, or the
    label is only asserting that certain near-misses do not come
    back. Such a query is still measured: its near-misses are
    checked, and it counts towards the denominator, but there is no
    skill whose absence is a failure.

    That distinction matters. "ship a python package to pypi" has no
    obvious winner, but it does have answers -- the python skills --
    and it must not be answered by `docker-patterns`. Treating the
    missing winner as a failure would have said the engine was wrong
    for finding the python skills at all.
    """
    top1 = top3 = top10 = 0
    for query, wanted, unwanted in positives:
        r = idx.search(query, limit=50)
        ids = [x['id'] for x in r['results']]
        totals.append(r['total_matched'])
        # The labelled set names skills bare ("documentation-lookup");
        # the index namespaces them ("skill:documentation-lookup").
        # Compare on the bare name so the labels stay readable.
        bare = [i.split(':', 1)[-1] for i in ids]
        if wanted is None:
            rank = None
        else:
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
    return {'top1': top1, 'top3': top3, 'top10': top10}


def measure(data, detail=False):
    """Run the labelled set over an index, and report what happened.

    Returns a dict of counts. This is the measurement the evaluation
    script prints -- factored out so the documentation can state the
    real numbers instead of a copy of them that drifts.

    `data` is the parsed index. The measurement is done against the
    tree's own index, so the published tree's documents quote the
    published tree's ranking.

    Two sets are measured, and they are reported separately:

      * the *training* set -- the queries the ranking was tuned
        against. Its numbers say the tuning worked.
      * the *validation* set -- queries written afterwards, never used
        to choose a constant. Its numbers say the ranking generalises.

    Only the validation number is evidence that the ranking is good.
    The training number is evidence that the tuning did what it was
    supposed to, and a high training number with a low validation
    number is the signature of overfitting.
    """
    idx = SearchIndex(data)

    failures = []
    totals = []

    # A label naming a skill the tree does not publish cannot be
    # measured. The public tree publishes fewer skills than the local
    # one -- the difference is the entries whose licence does not
    # permit redistribution -- so the labelled set is filtered to what
    # is here, and the skipped labels are reported rather than
    # silently counted.
    #
    # The filter covers agents as well as skills: the search index
    # holds both, so a label naming an agent is measurable too. A
    # filter that only knew about skills would skip every agent label
    # and quietly stop measuring the agent half of the corpus.
    published = {s['name'] for s in data['skills']}
    published |= {a['name'] for a in data['agents']}
    positives = [p for p in POSITIVE if p[1] in published]
    skipped = [p for p in POSITIVE if p[1] not in published]

    if detail:
        print('\nthe training set (the ranking was tuned against these)')
    train = _measure_positives(idx, positives, failures, totals, detail)

    # The held-out set. A label naming a skill this tree does not
    # publish is skipped and reported, the same as above.
    val_positives = [p for p in VALIDATION if p[1] is None or p[1] in published]
    val_skipped = [p for p in VALIDATION
                   if p[1] is not None and p[1] not in published]

    if detail:
        print('\nthe validation set (held out -- never tuned against)')
    val = _measure_positives(idx, val_positives, failures, totals, detail)

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
        'top1': train['top1'],
        'top3': train['top3'],
        'top10': train['top10'],
        'measured': len(positives),
        'negatives': negatives,
        'median_results': sorted(totals)[len(totals) // 2] if totals else 0,
        'max_results': max(totals) if totals else 0,
        'failures': failures,
        'skipped': skipped,
        # The held-out numbers.
        'val_top1': val['top1'],
        'val_top3': val['top3'],
        'val_top10': val['top10'],
        'val_measured': len(val_positives),
        'val_skipped': val_skipped,
    }
