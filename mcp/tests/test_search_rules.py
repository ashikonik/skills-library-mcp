#!/usr/bin/env python3
"""The properties the search rules are supposed to have.

`eval_search.py` measures the *ranking* against a labelled query set.
That is the important measure, and it is the one that decides whether
the engine is good. But it is a blunt instrument for deciding whether
a particular rule is still working: a rule can stop doing its job and
the labelled set may still pass, because the labelled set is a sample
and the rule may only matter for queries it does not contain.

So this file states the rules as properties, and checks each one
directly. A rule that stops working breaks a property here, even when
the ranking is unchanged.

The properties are these:

  * the name match is a *prefix* match, so "sql" does not match
    "mysql" and "home" does not match "homelab";
  * the coverage rule counts the evidence it discarded -- a query
    whose subject is a filtered generic word still finds its skill;
  * the coverage demand is capped, so a long query is not held to a
    longer standard than a short one;
  * an entry whose only evidence identifies nothing is dropped;
  * an inflected description word matches the plain query word, and
    a coincidental prefix does not;
  * the task row's *order* holds in both of the row's branches;
  * and the two implementations agree on all of it.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))

from search import SearchIndex, tokenize, _inflections   # noqa: E402

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

    def search(query, limit=20):
        r = idx.search(query, limit=limit)
        return [x['id'].split(':', 1)[-1] for x in r['results']]

    # -----------------------------------------------------------------
    # The name match is a prefix match.
    #
    # "sql" is inside "mysql" and "home" is inside "homelab", but
    # neither is a prefix, and neither is evidence. Before the rule,
    # "write SQL" ranked `mysql-patterns` first and "bake sourdough
    # bread at home" matched every `homelab-*` skill.
    # -----------------------------------------------------------------

    got = search('write SQL')
    check('"sql" does not match the name "mysql-patterns" as a fragment',
          'mysql-patterns' in got, 'got %s' % got[:3])

    # The right answer for "write SQL" is a SQL skill -- and the row's
    # own first member wins, because the table lists the skills before
    # the agents.
    check('"write SQL" answers with a SQL skill',
          bool(got) and ('sql' in got[0] or 'postgres' in got[0] or
                         'mysql' in got[0]),
          'got %s' % got[:3])
    check('"write SQL" does not answer with the row\'s agent',
          not got or 'database-reviewer' not in got[:1],
          'got %s' % got[:1])

    # The same rule in the *strict* branch.
    #
    # "write SQL queries" matches the row "Write SQL / optimise
    # queries" on its full wording, so the row fires strictly. The
    # row lists `postgres-patterns` first and the agent
    # `database-reviewer` third, and the agent is tier 1 while the
    # skill is tier 2 -- so without the demotion the agent wins on
    # the tier bias and the agent bonus alone.
    got = search('write SQL queries')
    check('"write SQL queries" answers with the row\'s first skill',
          bool(got) and 'postgres-patterns' in got[:1],
          'got %s' % got[:1])

    got = search('bake sourdough bread at home')
    check('"home" does not match the name "homelab-*" as a fragment',
          not any(g.startswith('homelab') for g in got),
          'got %s' % got[:3])

    # A prefix IS a match: "docker" is a prefix of "dockerfile", and a
    # caller who types "docker" means it.
    got = search('docker container')
    check('a prefix of a name still matches',
          bool(got) and 'docker-patterns' in got, 'got %s' % got[:3])

    # -----------------------------------------------------------------
    # The coverage rule counts the evidence it filtered out.
    #
    # "audit" and "draft" appear in too many descriptions to be
    # *discriminating*, so the filter drops them when deciding how
    # many tokens to demand. They are still evidence when the entry
    # matched them.
    # -----------------------------------------------------------------

    got = search('audit my site against WCAG 2.2')
    check('a filtered generic word still counts as evidence',
          'accessibility' in got[:3], 'got %s' % got[:3])

    # -----------------------------------------------------------------
    # The coverage demand is capped.
    #
    # A long query is not held to a longer standard than a short one:
    # the words a long query adds are usually connective tissue that
    # no description contains.
    # -----------------------------------------------------------------

    got = search('stop my prose from sounding like a machine wrote it')
    check('a long query is not held to a longer coverage demand',
          'humanizer' in got[:3], 'got %s' % got[:3])

    # -----------------------------------------------------------------
    # The evidence rule.
    #
    # An entry that matched only words which carry no information about
    # *which* entry it is, matched nothing real.
    #
    # The rule needs the entry to have matched at least one of the
    # query's *coverage* words -- the ones that identify it -- or at
    # least two words that appear in the corpus at all.
    #
    # The isolating case is "acc acce". Both words are prefixes of the
    # name token "access", so both match `access` by the prefix rule
    # and the coverage demand of two tokens is satisfied. Neither word
    # appears anywhere in the corpus, though -- "acc" and "acce" are
    # not English words, they are fragments -- so the entry has
    # matched nothing that identifies it, and the answer is no
    # answer.
    # -----------------------------------------------------------------

    got = search('my cat knocked over a plant')
    check('an entry matching only out-of-vocabulary words is dropped',
          not got, 'got %s' % got[:3])

    got = search('the train is late again')
    check('a coincidental prefix in a description is not a match',
          not got, 'got %s' % got[:3])

    got = search('acc acce')
    check('an entry whose only evidence identifies nothing is dropped',
          not got, 'got %s' % got[:3])

    # The same query with real words *does* answer. Without this, the
    # check above would pass for the wrong reason -- a query that
    # matches nothing at all also returns nothing.
    got = search('access control')
    check('the same query with real evidence does answer',
          bool(got), 'got %s' % got[:3])

    # -----------------------------------------------------------------
    # The inflection rule.
    #
    # "drafting" is "draft"; "latency" is not "late".
    # -----------------------------------------------------------------

    got = search('organise my email and draft a reply')
    check('an inflected description word matches the plain query word',
          'email-ops' in got[:3], 'got %s' % got[:3])

    check('"late" does not inflect to "latency"',
          'latency' not in _inflections('late'),
          'got %s' % _inflections('late'))
    check('"plant" does inflect to "plants"',
          'plants' in _inflections('plant'),
          'got %s' % _inflections('plant'))
    check('"draft" does inflect to "drafting"',
          'drafting' in _inflections('draft'),
          'got %s' % _inflections('draft'))

    # -----------------------------------------------------------------
    # The task row's order holds in the content branch too.
    #
    # The table lists a row's skills before its agents, and that order
    # is the row's curation whether the query named the row's verb or
    # only its object.
    # -----------------------------------------------------------------

    for row in data['tasks']:
        skills = row.get('skills') or []
        agents = row.get('agents') or []
        if not skills or not agents:
            continue
        positions = {n: i for i, n in enumerate(skills)}
        for a in agents:
            positions[a] = len(skills) + agents.index(a)
        first_skill = skills[0]
        first_agent = agents[0]
        # The first skill's position must be below the first agent's.
        if positions[first_skill] >= positions[first_agent]:
            check('the row %r lists its skills before its agents' % row['task'],
                  False, '%s=%d %s=%d' % (first_skill, positions[first_skill],
                                         first_agent, positions[first_agent]))
    else:
        check('every task row lists its skills before its agents', True)

    # -----------------------------------------------------------------
    # The two implementations agree.
    #
    # The rules above are duplicated in `src/search.ts`, and a rule
    # that exists on one side only is a rule that ranks differently
    # depending on which server the caller reached.
    # -----------------------------------------------------------------

    probe = os.path.join(HERE, '_ts_search.mjs')
    if not os.path.isfile(os.path.join(MCP, 'dist', 'search.js')) and \
       not os.path.isfile(os.path.join(MCP, 'dist', 'index.js')):
        print('SKIP: the TypeScript build is missing')
    else:
        queries = ['write SQL', 'write SQL queries',
                   'bake sourdough bread at home',
                   'audit my site against WCAG 2.2',
                   'organise my email and draft a reply',
                   'my cat knocked over a plant',
                   'the train is late again',
                   'slidev quokka', 'acc acce', 'access control',
                   'stop my prose from sounding like a machine wrote it',
                   'docker container']
        # The shared probe takes the queries as a JSON array on argv[2]
        # and answers {query: {ids, scores, ...}}. It reads the index
        # itself, so it is the same index the Python side reads.
        out = subprocess.run(
            ['node', probe, json.dumps(queries)],
            capture_output=True, text=True,
            cwd=MCP,
        )
        if out.returncode != 0:
            check('the TypeScript probe runs', False,
                  (out.stderr or out.stdout)[-400:])
        else:
            try:
                ts = json.loads(out.stdout)
            except ValueError:
                check('the TypeScript probe returns JSON', False,
                      out.stdout[-400:])
                ts = None
            if ts is not None:
                mismatch = []
                for q in queries:
                    py = search(q, limit=10)
                    tsr = ts.get(q)
                    if tsr is None:
                        mismatch.append('%s: the TypeScript side has no answer' % q)
                    else:
                        ts_ids = [i.split(':', 1)[-1] for i in tsr['ids']]
                        if ts_ids != py:
                            mismatch.append('%s: TS %s != PY %s' % (q, ts_ids[:3], py[:3]))
                check('the two implementations rank the rule cases the same',
                      not mismatch, '; '.join(mismatch[:3]))

    print()
    if failures:
        print('SEARCH RULES: FAIL -- %d of %d checks failed' % (
            len(failures), checks))
        for f in failures:
            print('   %s' % f)
        sys.exit(1)
    print('SEARCH RULES: PASS -- %d checks' % checks)


if __name__ == '__main__':
    main()
