#!/usr/bin/env python3
"""The task table, row by row.

The task table is the curated prior: 74 rows that say "when the user
asks for X, these are the skills that do X". It is the one part of
the ranking that a human wrote, and it is the part a script is most
likely to break silently -- a skill is renamed, a row's note names an
entry that is no longer in the library, and the row keeps working
while getting worse.

So every row is checked -- twice, once against the **source table**
(`build/tasks.py`) and once against the **built index**:

  1. **Every entry the row names exists.** A row that names a skill
     that is no longer in the library routes the user to nothing.
     The entry is silently dropped by the scorer and the row's
     curation is quietly worse than it looks.

  2. **Every entry the row's *note* names is in the row's list.**
     The note is where the curation is explained, and the build
     promotes a note-named entry to the front. If the note names an
     entry the lists omit, the note is describing a row that is not
     the row.

  3. **No row names the same entry twice.** A duplicate is a copy
     -and-paste error, and it costs the row a position.

  4. **Every row has content.** An empty row is a row that matches
     nothing, and it is dead weight in the index.

  5. **Every row's task text is distinct.** Two rows with the same
     task are the same row, and the second one is unreachable.

Both halves are necessary. The builder drops entries the library
does not have and deduplicates the lists, so a broken table produces
a clean-looking index: reading the index alone cannot see defects
1, 3 or 4 at all. The source-table checks are what catch them.

And the stale-router check: the index's *search postings* must be
able to find every row by its own task text. A row the postings
cannot route to is a row the search will never reach.

The gate is proved able to fail: `scripts/break_check_task_table.sh`
breaks each invariant in turn and requires this file to notice.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))

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


# The entries a note names are written in backticks or in plain
# prose. The build extracts them; this gate uses the same convention
# -- a backticked token that looks like an entry name.
NOTE_ENTRY = re.compile(r'`([A-Za-z0-9][A-Za-z0-9._-]*)`')


def main():
    data = load_index()
    if data is None:
        return 1

    tasks = data['tasks']
    skill_names = {s['name'] for s in data['skills']}
    agent_names = {a['name'] for a in data['agents']}

    # ---- 1. every entry a row names exists.
    #
    # Checked against the index first, and then against the source
    # table further down -- the index check is the weaker of the two,
    # because the builder has already dropped the unknowns by the
    # time the index exists.
    missing_skills = []
    missing_agents = []
    for row in tasks:
        for s in row.get('skills') or []:
            if s not in skill_names:
                missing_skills.append((row['task'], s))
        for a in row.get('agents') or []:
            if a not in agent_names:
                missing_agents.append((row['task'], a))
    check('tasks: every skill a row names is in the library',
          not missing_skills, str(missing_skills[:5]))
    check('tasks: every agent a row names is in the library',
          not missing_agents, str(missing_agents[:5]))

    # ---- 2. every entry a note names is in the row's lists.
    #
    # The note is where the curation is explained. A note that names
    # an entry the row's lists omit describes a row that is not the
    # row -- either the list lost the entry, or the note is stale.
    note_unlisted = []
    for row in tasks:
        note = row.get('notes') or ''
        listed = set(row.get('skills') or []) | set(row.get('agents') or [])
        for token in NOTE_ENTRY.findall(note):
            # Only tokens that name an entry *in this library* count.
            # A note may mention a tool that is not a skill --
            # "the architect/planner agent" is prose.
            if token in skill_names or token in agent_names:
                if token not in listed:
                    note_unlisted.append((row['task'], token))
    check('tasks: every entry a note names is in the row\'s lists',
          not note_unlisted, str(note_unlisted[:5]))

    # ---- 3. no row names the same entry twice.
    dupes = []
    for row in tasks:
        for field in ('skills', 'agents'):
            names = row.get(field) or []
            if len(names) != len(set(names)):
                seen = set()
                dup = [n for n in names if n in seen or seen.add(n)]
                dupes.append((row['task'], field, dup))
    check('tasks: no row names the same entry twice', not dupes,
          str(dupes[:5]))

    # ---- 4. every row has content.
    #
    # A row with no skills and no agents routes the user nowhere.
    #
    # A row with no `content` is a different matter. The row's task
    # text is what fires the *strict* match, and the content -- the
    # row's tokens with its leading verb dropped -- is what fires the
    # looser one. Two rows in this table have no content, because they
    # are one-word rows ("Containerise", "Do SEO") where there is no
    # verb to drop: dropping the only token would leave nothing. So
    # the requirement is not "every row has content" but "every row
    # without content is still reachable by its own text" -- which is
    # checked below, against the real scorer.
    empty_rows = []
    for row in tasks:
        if not (row.get('skills') or []) and not (row.get('agents') or []):
            empty_rows.append(row['task'])
    check('tasks: no row is empty', not empty_rows, str(empty_rows[:5]))

    # ---- 5. every row's task text is distinct.
    seen = {}
    dup_tasks = []
    for row in tasks:
        t = row['task']
        if t in seen:
            dup_tasks.append(t)
        seen[t] = True
    check('tasks: every row\'s task text is distinct', not dup_tasks,
          str(dup_tasks[:5]))

    # ---- the stale-router check.
    #
    # The postings must be able to route a query to every row. The
    # postings are `token -> ids`, so the check is: for every entry a
    # row names, that entry must appear in the bucket of at least one
    # token of the row's task text.
    #
    # An entry that does not appear is unreachable by its row -- the
    # search would only ever find it by accident, through some other
    # row's tokens. That is the stale-router failure: the row says
    # "for this task, use these", and the search cannot route to them.
    #
    # The tokenizer is the project's, not the standard library's: the
    # postings were built with it, so the check must use the same one.
    from build_index import tokenize  # noqa: E402

    postings = data['search']['postings']
    task_bucket = postings.get('tasks') or {}

    def routed_ids(kind, token):
        return set((task_bucket.get(kind) or {}).get(token) or [])

    unreachable = []
    for row in tasks:
        tokens = tokenize(row['task'])
        if not tokens:
            continue
        skill_ids = set()
        agent_ids = set()
        for t in tokens:
            skill_ids |= routed_ids('skill', t)
            agent_ids |= routed_ids('agent', t)
        for name in row.get('skills') or []:
            if 'skill:' + name not in skill_ids:
                unreachable.append((row['task'], name,
                                    'not routable by the task text'))
        for name in row.get('agents') or []:
            if 'agent:' + name not in agent_ids:
                unreachable.append((row['task'], name,
                                    'not routable by the task text'))
    check('tasks: every row member is routable by the row\'s own text',
          not unreachable, str(unreachable[:5]))

    # And the postings must actually cover the task text: for every
    # token of every row's task, there must be a bucket entry -- or
    # the token is one no entry uses, which is a different problem
    # (a row that says something the library has no word for).
    uncovered = []
    for row in tasks:
        for t in tokenize(row['task']):
            if not (routed_ids('skill', t) or routed_ids('agent', t)):
                uncovered.append((row['task'], t))
                break
    check('tasks: the task postings cover every row\'s task text',
          not uncovered, str(uncovered[:5]))

    # ---- the table itself, checked against the source.
    #
    # The index is generated from `build/tasks.py`. If the two drift,
    # the index is describing a table nobody wrote.
    #
    # The checks below are against the *source table*, not the index,
    # and that is the whole point of them. The builder applies two
    # normalising transforms on the way to the index: it drops
    # entries the library does not have, and it deduplicates the
    # lists. So a table that names an unknown entry, or names the same
    # entry twice, produces an index that looks perfectly clean -- the
    # defect is normalised away before anything is written. A gate
    # that reads only the index therefore cannot see those defects at
    # all: it would pass on a table that is broken.
    #
    # The builder records the drops in its own log, but a log is not a
    # gate -- nothing fails. The table is the input, and the input is
    # what has to be checked.
    try:
        from tasks import TASKS  # noqa: E402
    except ImportError:
        sys.stderr.write('SKIP: build/tasks.py is not importable.\n')
        TASKS = None
    if TASKS is not None:
        # ---- the source table: every entry it names exists.
        #
        # A row that names a skill the library does not have routes
        # the user to nothing. The builder drops it and says so, but
        # the row still ships, still costs the author a slot in their
        # own curation, and still reads as if the entry were there.
        table_missing_skills = []
        table_missing_agents = []
        for t in TASKS:
            for s in t[1] or []:
                if s not in skill_names:
                    table_missing_skills.append((t[0], s))
            for a in t[2] or []:
                if a not in agent_names:
                    table_missing_agents.append((t[0], a))
        check('tasks: the table names only skills the library has',
              not table_missing_skills, str(table_missing_skills[:5]))
        check('tasks: the table names only agents the library has',
              not table_missing_agents, str(table_missing_agents[:5]))

        # ---- the source table: every entry a note names is listed.
        #
        # The note is where the curation is explained. A note that
        # names an entry the row's lists omit describes a row that is
        # not the row -- either the list lost the entry, or the note
        # is stale. The builder *promotes* a note-named entry to the
        # front of the list, but it cannot promote one that is not
        # there at all.
        #
        # The rule is kind-scoped, matching the builder's own
        # `promote_named`: a *skill* named in the note belongs in the
        # row's skill list, an *agent* in its agent list. A note that
        # names a skill where an agent is expected is a different
        # mistake -- the entry would be promoted into a list it does
        # not belong to, or dropped.
        #
        # And a note may *deliberately* point at another row's entry
        # -- "there is no dedicated Kubernetes agent, use
        # `architect`" is a cross-reference, not a routing claim. The
        # builder treats a note-named entry of the *wrong* kind as
        # prose, and so does this check: only a note-named entry of
        # the row's *own* kinds has to be listed.
        table_note_unlisted = []
        table_note_wrong_kind = []
        for t in TASKS:
            note = t[3] or ''
            skills = set(t[1] or [])
            agents = set(t[2] or [])
            for token in NOTE_ENTRY.findall(note):
                if token in skill_names and token not in skills:
                    # A skill named in a note. If the note is routing
                    # the row at a skill, the skill must be listed.
                    table_note_unlisted.append((t[0], token, 'skill'))
                elif token in agent_names and token not in agents:
                    table_note_wrong_kind.append((t[0], token, 'agent'))
        check('tasks: the table lists every entry its notes name',
              not table_note_unlisted, str(table_note_unlisted[:5]))
        # An agent named in the note must be in the row's *agent* list.
        # The builder drops a skill out of an agent slot and promotes
        # the note-named agent to the front -- so a note that names an
        # agent the row does not list is a row whose curation is
        # weaker than it reads.
        check('tasks: the table lists every agent its notes name',
              not table_note_wrong_kind, str(table_note_wrong_kind[:5]))

        # ---- the source table: no row names the same entry twice.
        #
        # The builder deduplicates, so the index never shows the
        # duplicate. The table still has it, and the author still
        # paid a position for it.
        table_dupes = []
        for t in TASKS:
            for field, names in (('skills', t[1]), ('agents', t[2])):
                names = names or []
                if len(names) != len(set(names)):
                    seen = set()
                    dup = [n for n in names if n in seen or seen.add(n)]
                    table_dupes.append((t[0], field, dup))
        check('tasks: the table never names the same entry twice',
              not table_dupes, str(table_dupes[:5]))

        # ---- the source table: every row has members.
        #
        # A row with no skills and no agents routes the user nowhere.
        # The builder keeps such a row -- there is nothing to drop --
        # so it reaches the index as a row that matches nothing.
        table_empty = [t[0] for t in TASKS
                       if not (t[1] or []) and not (t[2] or [])]
        check('tasks: the table has no empty row', not table_empty,
              str(table_empty[:5]))

        # ---- the source table: every row's task text is distinct.
        table_seen = set()
        table_dup_tasks = []
        for t in TASKS:
            if t[0] in table_seen:
                table_dup_tasks.append(t[0])
            table_seen.add(t[0])
        check('tasks: the table\'s task texts are distinct',
              not table_dup_tasks, str(table_dup_tasks[:5]))

        check('tasks: the index has every row of the table',
              len(tasks) == len(TASKS),
              'index %d, table %d' % (len(tasks), len(TASKS)))
        # A table row is `(task, skills, agents, notes)`.
        table_names = {t[0] for t in TASKS}
        index_names = {t['task'] for t in tasks}
        check('tasks: the index and the table name the same rows',
              table_names == index_names,
              str(sorted(index_names ^ table_names)[:5]))

        # And the index's copy of each row matches the table's -- after
        # the two documented transforms the builder applies: entries
        # that are not in the library are dropped, and entries the
        # row's *note* names are promoted to the front.
        #
        # The check uses the builder's own `promote_named`, so it
        # cannot drift from the implementation: if the promotion
        # changes, the expectation changes with it.
        #
        # The transforms are not cosmetic. "Refactor / simplify" lists
        # the *skill* names `coding-standards` and `codehealth-mcp`
        # in its *agent* slot; the builder drops them (they are not
        # agents) and promotes `refactor-cleaner`, which the note
        # names. The index is right and the table row is a typo.
        from build_index import promote_named  # noqa: E402

        drifted = []
        by_name = {t[0]: t for t in TASKS}
        for row in tasks:
            src = by_name.get(row['task'])
            if src is None:
                continue
            note = src[3]
            want_skills = list(dict.fromkeys(
                promote_named(note,
                              [x for x in (src[1] or []) if x in skill_names],
                              skill_names, agent_names)))
            want_agents = list(dict.fromkeys(
                promote_named(note,
                              [x for x in (src[2] or []) if x in agent_names],
                              agent_names, skill_names)))
            if list(row.get('skills') or []) != want_skills:
                drifted.append((row['task'], 'skills',
                                list(row.get('skills') or []), want_skills))
            elif list(row.get('agents') or []) != want_agents:
                drifted.append((row['task'], 'agents',
                                list(row.get('agents') or []), want_agents))
            elif (row.get('notes') or '') != (note or ''):
                drifted.append((row['task'], 'notes'))
        check('tasks: the index matches the table row for row',
              not drifted, str(drifted[:5]))

        # And the builder must say what it dropped. A row that names
        # an entry the library does not have is a row the author
        # expected to route somewhere and cannot -- and the builder
        # records the drop, so the record and the index must agree.
        #
        # The drops are a *defect*, not a tolerated state: the
        # source-table check above fails on them. What this check
        # adds is that the index carries none of them -- the drop
        # happened, and it happened completely.
        dropped = []
        for row in tasks:
            src = by_name.get(row['task'])
            if src is None:
                continue
            for x in src[1] or []:
                if x not in skill_names:
                    dropped.append((row['task'], x, 'skill'))
            for x in src[2] or []:
                if x not in agent_names:
                    dropped.append((row['task'], x, 'agent'))
        leaked = []
        for row in tasks:
            for x in row.get('skills') or []:
                if x not in skill_names:
                    leaked.append((row['task'], x, 'skill'))
            for x in row.get('agents') or []:
                if x not in agent_names:
                    leaked.append((row['task'], x, 'agent'))
        check('tasks: no dropped entry survives into the index',
              not leaked, str(leaked[:5]))
        sys.stdout.write('     (%d table entr%s name an entry the library '
                         'does not have; the builder drops them)\n'
                         % (len(dropped),
                            'y' if len(dropped) == 1 else 'ies'))

    # ---- every row must be reachable by its own task text.
    #
    # This is the check that says the row works, not merely that it
    # is well-formed. A row whose members never appear for a query
    # that names the row is a row the user cannot reach, and no
    # amount of the row being internally consistent makes it useful.
    #
    # The query is the row's own task text, lower-cased, which is the
    # most direct phrasing of "I want this task done".
    sys.path.insert(0, os.path.join(MCP, 'python'))
    import search as pysearch  # noqa: E402

    idx = pysearch.SearchIndex(data)
    unreachable_rows = []
    for row in tasks:
        members = set()
        for name in row.get('skills') or []:
            members.add('skill:' + name)
        for name in row.get('agents') or []:
            members.add('agent:' + name)
        if not members:
            continue
        out = idx.search(row['task'], limit=50)
        ids = {r['id'] for r in out['results']}
        if not (members & ids):
            unreachable_rows.append((row['task'], sorted(members)[:3],
                                     sorted(ids)[:3]))
    check('tasks: every row is reachable by its own task text',
          not unreachable_rows, str(unreachable_rows[:5]))

    if failures:
        sys.stderr.write('\n%d FAILURE(S) out of %d checks\n'
                         % (len(failures), checks))
        for f in failures:
            sys.stderr.write('  - %s\n' % f)
        return 1
    sys.stdout.write('\nTASK TABLE: PASS — all %d checks\n' % checks)
    return 0


if __name__ == '__main__':
    sys.exit(main())
