#!/usr/bin/env python3
"""The MCP server test suite.

Covers the index, the search, the tool surface, the protocol, and the
write safety rules. Written against the Python fallback server, because
that is the one that must work with no Node installed.

The assertions that matter most are the ones that would catch a
regression in the library's own frontmatter fix -- those fail if the
fix is reverted, which is what makes this suite a guard rather than a
smoke test.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
BASE = os.path.dirname(MCP)
PYTHON = sys.executable

sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))
sys.path.insert(0, HERE)

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


# ------------------------------------------------------------------ 1. index
def test_index(idx):
    """The index must describe the tree it was built from.

    The counts are derived, not hard-coded: the local library holds more
    entries than the published one, because the difference is the entries
    whose licence does not permit redistribution. A hard-coded count would
    make the published tree look broken when it is not.
    """
    d = idx.data
    check('index: schema_version is 1', d['schema_version'] == 1)
    check('index: the skill count matches the tree',
          d['counts']['skills'] == len(d['skills']),
          str(d['counts']['skills']))
    check('index: the agent count matches the tree',
          d['counts']['agents'] == len(d['agents']),
          str(d['counts']['agents']))
    check('index: the held-aside count matches the tree',
          d['counts']['held_aside'] == len(d.get('held_aside') or []),
          str(d['counts']['held_aside']))
    total = (d['counts']['by_tier']['1'] + d['counts']['by_tier']['2']
             + d['counts']['by_tier']['3'])
    check('index: the tiers sum to the entry count',
          total == d['counts']['skills'] + d['counts']['agents'], str(total))
    check('index: tier 1 holds the packs and every agent',
          d['counts']['by_tier']['1'] == len(d['packs']) + d['counts']['agents'],
          str(d['counts']['by_tier']['1']))
    check('index: the skill tiers sum to the skill count',
          (d['counts']['skill_by_tier']['1'] + d['counts']['skill_by_tier']['2']
           + d['counts']['skill_by_tier']['3']) == d['counts']['skills'],
          str(d['counts']['skill_by_tier']))
    tier1_skills = sorted(s['name'] for s in d['skills'] if s['tier'] == 1)
    check('index: the tier-1 skills are exactly the published packs',
          tier1_skills == sorted(d['packs']), str(tier1_skills))
    check('index: 38 domains', len(d['domains']) == 38, str(len(d['domains'])))
    # The task table's row count is not written down here. A literal goes
    # stale the moment a row is added, and a stale literal is a failed
    # build that says nothing about the index. What matters is that the
    # index holds exactly the rows the table holds -- the same rows the
    # routing guide prints.
    from tasks import TASKS
    check('index: the task rows match the task table',
          len(d['tasks']) == len(TASKS),
          'index %d, table %d' % (len(d['tasks']), len(TASKS)))


# --------------------------------------------------- 2. the frontmatter fix
def test_descriptions(idx):
    """Every stored description must equal the real YAML description.

    This is the regression guard for the Phase 1 fix. It fails if the
    fix is reverted.
    """
    try:
        import yaml
    except ImportError:
        sys.stderr.write('SKIP: PyYAML is not installed.\n')
        return

    from build_index import frontmatter, regex_field

    shorter = []
    mismatched = []
    yaml_count = 0
    body_count = 0

    for e in idx.entries:
        # A skill's `path` is its directory; `skill_md` is the file. An
        # agent's `path` is the file itself.
        rel = e['skill_md'] if e['kind'] == 'skill' else e['path']
        path = os.path.join(BASE, rel)
        try:
            with open(path, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
        except OSError:
            mismatched.append((e['id'], 'file missing: %s' % rel))
            continue
        raw = frontmatter(text)
        if not raw:
            if e['kind'] == 'skill':
                body_count += 1
            continue
        try:
            data = yaml.safe_load(raw)
            if not isinstance(data, dict):
                continue
        except yaml.YAMLError:
            # Explore / silent-failure-hunter: the regex fallback is expected.
            continue
        desc = data.get('description')
        if desc is None:
            if e['kind'] == 'skill':
                body_count += 1
            continue
        if e['kind'] != 'skill':
            continue
        yaml_count += 1
        norm = ' '.join(str(desc).split())
        stored = ' '.join(e['desc'].split())
        if norm != stored:
            mismatched.append((e['id'], 'stored %d chars, yaml %d chars'
                              % (len(stored), len(norm))))
        if len(norm) > len(stored) + 4:
            shorter.append((e['id'], len(stored), len(norm)))

    check('descriptions: every stored description equals the YAML one',
          not mismatched, str(mismatched[:3]))
    check('descriptions: no stored description is shorter than the YAML one',
          not shorter, str(shorter[:3]))
    check('descriptions: every skill but one has a YAML description',
          yaml_count == idx.data['counts']['skills'] - 1, str(yaml_count))
    check('descriptions: exactly 1 skill has no frontmatter description',
          body_count == 1, str(body_count))

    by_id = {e['id']: e for e in idx.entries}
    mo = by_id.get('skill:math-olympiad')
    check('descriptions: math-olympiad keeps IMO and Putnam',
          bool(mo) and 'IMO' in mo['desc'] and 'Putnam' in mo['desc'])
    acc = by_id.get('skill:accessibility')
    check('descriptions: accessibility keeps "WCAG 2.2 Level AA"',
          bool(acc) and 'WCAG 2.2 Level AA' in acc['desc'])
    check('descriptions: math-olympiad is not the truncated 75-character one',
          bool(mo) and len(mo['desc']) > 500,
          str(len(mo['desc']) if mo else 0))


# ------------------------------------------------------------- 3. postings
def test_postings(idx):
    postings = idx.data['search']['postings']
    missing = []
    for kind in ('skill', 'agent'):
        bucket = postings.get(kind, {})
        for e in idx.entries:
            if e['kind'] != kind:
                continue
            for t in set(e['tokens']['name'] + e['tokens']['desc']):
                if e['id'] not in bucket.get(t, []):
                    missing.append((e['id'], t))
                    break
            if missing:
                break
        if missing:
            break
    check('postings: every token resolves to its entry', not missing,
          str(missing[:3]))


# --------------------------------------------------------------- 4. bundles
def test_bundles(idx):
    total_refs = 0
    total_dangling = 0
    bad = []
    for e in idx.entries:
        b = e['bundle']
        total_refs += b['refs_total']
        total_dangling += b['refs_dangling']
        if b['refs_dangling'] != b['refs_total'] - b['refs_resolved']:
            bad.append(e['id'])
    check('bundles: refs_dangling == refs_total - refs_resolved',
          not bad, str(bad[:3]))
    check('bundles: more than 1000 references are recorded',
          total_refs > 1000, str(total_refs))
    sys.stdout.write('     %d refs, %d already dangling in the source tree\n'
                     % (total_refs, total_dangling))


# --------------------------------------------------------------- 5. search
def test_search(idx):
    r = idx.search('accessibility audit WCAG', limit=10)
    check('search: "accessibility audit WCAG" ranks skill:accessibility first',
          r['results'] and r['results'][0]['id'] == 'skill:accessibility',
          r['results'][0]['id'] if r['results'] else 'no results')

    r = idx.search('competition math proof', limit=10)
    ids = [x['id'] for x in r['results']]
    check('search: "competition math proof" finds skill:math-olympiad',
          'skill:math-olympiad' in ids, str(ids))
    check('search: "competition math proof" finds nothing else',
          len(ids) == 1, str(ids))

    r = idx.search('the', limit=10)
    check('search: a pure-stopword query returns nothing',
          r['total_matched'] == 0 and r['returned'] == 0, str(r['total_matched']))

    r = idx.search('a', limit=10)
    check('search: a one-letter query returns nothing', r['returned'] == 0,
          str(r['returned']))

    r = idx.search('zzzzqqqq nonexistent gibberish', limit=10)
    check('search: a query with no match returns nothing', r['returned'] == 0,
          str(r['returned']))

    r = idx.search('api', limit=10)
    check('search: the default limit is 10', len(r['results']) <= 10,
          str(len(r['results'])))

    r = idx.search('api', limit=500)
    check('search: the limit is capped at 50', len(r['results']) <= 50,
          str(len(r['results'])))

    r = idx.search('fix a failing build', limit=10)
    ids = [x['id'] for x in r['results']]
    check('search: "fix a failing build" finds the build resolvers',
          any(i.startswith('agent:') and 'build-resolver' in i for i in ids),
          str(ids[:3]))
    check('search: "fix a failing build" finds error-handling',
          'skill:error-handling' in ids, str(ids[:5]))

    r = idx.search('code', kind='agent', limit=50)
    check('search: kind=agent returns only agents',
          all(x['kind'] == 'agent' for x in r['results']))
    r = idx.search('code', tier=1, limit=50)
    check('search: tier=1 returns only tier-1 entries',
          all(x['tier'] == 1 for x in r['results']))
    r = idx.search('code', domain='Security', limit=50)
    check('search: domain=Security returns only that domain',
          all(x['domain'] == 'Security' for x in r['results']))

    r = idx.search('api', limit=50, include_body=True)
    check('search: include_body adds the frontmatter',
          r['results'] and 'frontmatter' in r['results'][0])


def test_search_counts(idx):
    """The four count fields have to tell one story.

    `total_matched`, `filtered_out`, `returned` and `truncated` are
    four numbers a caller reads together. Before `filtered_out`
    existed, the relevance floor silently dropped entries: a query
    reported 52 matches, returned 37, and said `truncated: false` --
    so the caller could not tell that 15 had been dropped and that the
    match set was bigger than the page.
    """
    queries = ['test', 'api', 'documentation', 'write', 'database',
               'deploy', 'review', 'security']
    coherent = True
    truncated_ok = True
    for q in queries:
        for limit in (1, 10, 50, 500):
            r = idx.search(q, limit=limit)
            label = '%r limit=%d' % (q, limit)
            kept = r['total_matched'] - r['filtered_out']

            if r['filtered_out'] < 0 or r['returned'] < 0 \
                    or r['total_matched'] < 0:
                coherent = False
            if r['returned'] > kept:
                coherent = False
            # `truncated` means "there is more to come", not "the page
            # is full".
            if r['truncated'] != (kept > r['returned']):
                truncated_ok = False

    check('search: the four counts agree with each other', coherent)
    check('search: truncated means there is more to come', truncated_ok)

    r = idx.search('test', limit=500)
    if r['filtered_out'] > 0:
        check('search: the note names the relevance floor',
              'relevance floor' in r['note'], r['note'])
        check('search: the note names how many were dropped',
              str(r['filtered_out']) in r['note'], r['note'])
    else:
        check('search: a query with nothing dropped has no floor note',
              'relevance floor' not in r['note'], r['note'])

    r = idx.search('zzzzqqqq nonexistent gibberish token', limit=10)
    check('search: a query with no match reports coherent zeroes',
          r['total_matched'] == 0 and r['filtered_out'] == 0
          and r['returned'] == 0 and r['truncated'] is False
          and r['note'] == '', str(r))


def test_search_rules(idx):
    """The two rules that filter the scored entries.

    The token-coverage rule requires coverage of the query's
    *distinctive* tokens. A generic verb must not be required: it
    carries no information about which entry the query wants.

    The task-index rule fires on a row's *content* -- the row's tokens
    with its leading verb dropped -- so "write a REST API" reaches the
    "Build an API" row. It fires harder when the row's content is the
    query's HEAD noun: what the query is *about*, not the context it
    mentions.
    """
    # the subject is the only distinctive token; "write" is generic
    r = idx.search('write documentation', limit=10)
    ids = [x['id'] for x in r['results']]
    check('search: "write documentation" ranks skill:documentation-lookup first',
          ids and ids[0] == 'skill:documentation-lookup', str(ids[:3]))
    check('search: "write documentation" finds more than one entry',
          len(ids) > 1, str(ids[:3]))

    # the task row fires on the content, so the API row is reachable
    r = idx.search('write a REST API', limit=10)
    ids = [x['id'] for x in r['results']]
    check('search: "write a REST API" finds skill:api-design',
          'skill:api-design' in ids, str(ids[:3]))
    # the query is ABOUT an API, so the row fires and the general API
    # skill takes the top slot. Without the head rule the row never
    # fired -- "api" is too common to identify a task on its own -- and
    # a vendor skill whose name happens to contain "rest api" won.
    check('search: "write a REST API" ranks skill:api-design first',
          ids and ids[0] == 'skill:api-design', str(ids[:3]))

    # the task row fires on the content, so the k8s row is reachable
    r = idx.search('deploy to kubernetes', limit=10)
    ids = [x['id'] for x in r['results']]
    check('search: "deploy to kubernetes" ranks skill:kubernetes-patterns first',
          ids and ids[0] == 'skill:kubernetes-patterns', str(ids[:3]))

    # a content match is a weaker signal than a strict one: the more
    # specific skill must still win
    r = idx.search('add authentication to an api', limit=10)
    ids = [x['id'] for x in r['results']]
    check('search: "add authentication to an api" ranks the auth skill first',
          ids and ids[0] == 'skill:twilio-security-api-auth', str(ids[:3]))
    # "api" is the object of "to" here, so the head rule must not fire
    # the "Build an API" row and put the API builder in the top three
    check('search: a subordinate noun does not fire the task row',
          'skill:api-design' not in ids[:3], str(ids[:3]))

    # the coverage rule must still reject a description-only match
    r = idx.search('quantum chromodynamics lattice simulation', limit=10)
    check('search: a description-only match is still rejected',
          r['total_matched'] == 0, str(r['total_matched']))
    r = idx.search('bake sourdough bread at home', limit=10)
    check('search: a common word alone does not match',
          r['total_matched'] == 0, str(r['total_matched']))


def test_task_curation(idx):
    """The task table's curation must reach the ranking.

    The table lists a row's *primary* entry first and says so in its
    note. Two pieces of that curation were being lost: the order
    itself, and the entries a note names but the row's lists omit.

    This is the regression guard for both.
    """
    tasks = {t['task']: t for t in idx['tasks']}

    # 1. the order survives into the index
    row = tasks['Build an API']
    check('tasks: the row keeps its curated order',
          row['skills'][:2] == ['api-design', 'api-connector-builder'],
          str(row['skills'][:3]))
    check('tasks: the row has no duplicate entries',
          len(row['skills']) == len(set(row['skills'])), str(row['skills']))

    # 2. an entry named only in the note is promoted to the front
    row = tasks['Create a skill']
    check('tasks: a note-named entry is promoted to the front',
          row['skills'][0] == 'skill-creator-plus', str(row['skills']))
    row = tasks['Infrastructure / Kubernetes']
    check('tasks: a note-named agent is promoted to the front',
          row['agents'][0] == 'architect', str(row['agents']))

    # 3. the promotion reaches the ranking
    r = idx.search('create a skill', limit=10)
    ids = [x['id'] for x in r['results']]
    check('search: "create a skill" ranks skill:skill-creator-plus first',
          ids and ids[0] == 'skill:skill-creator-plus', str(ids[:3]))

    # 4. the row's later members are demoted, not promoted.
    #    "Write tests" lists `tdd-workflow` first and `laravel-tdd`
    #    sixth. The note names `tdd-guide` -- the agent that enforces
    #    write-tests-first -- so the agent leads, and the row's first
    #    *skill* must still outrank its later alternatives.
    r = idx.search('write tests', limit=10)
    ids = [x['id'] for x in r['results']]
    check('search: the row\'s first skill outranks its later alternatives',
          'skill:tdd-workflow' in ids
          and ('skill:laravel-tdd' not in ids
               or ids.index('skill:tdd-workflow')
               < ids.index('skill:laravel-tdd')),
          str(ids[:4]))


# ------------------------------------------------------------ 6. the server
def largest_bundle_id():
    """The id of the skill with the most supporting files.

    Discovered rather than hard-coded, because the public tree publishes
    fewer skills than the local one and a name present locally may be
    absent there -- `document-builder` is one such case, since its vendored
    tree is Anthropic's and its licence does not permit redistribution.
    """
    with open(os.path.join(MCP, 'data', 'index.json'), encoding='utf-8') as fh:
        idx = json.load(fh)
    best = max(idx['skills'], key=lambda s: s['bundle']['file_count'])
    return best['id']


def test_server():
    """Spawn the Python fallback and speak MCP to it."""
    bundle_id = largest_bundle_id()
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
         'params': {'protocolVersion': '2025-06-18', 'capabilities': {},
                    'clientInfo': {'name': 'test', 'version': '1'}}},
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
        {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
         'params': {'name': 'search_library',
                    'arguments': {'query': 'accessibility audit WCAG',
                                  'limit': 3}}},
        {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call',
         'params': {'name': 'get_skill',
                    'arguments': {'id': 'skill:math-olympiad'}}},
        {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call',
         'params': {'name': 'get_skill',
                    'arguments': {'id': 'skill:does-not-exist'}}},
        {'jsonrpc': '2.0', 'id': 6, 'method': 'tools/call',
         'params': {'name': 'get_skill_bundle',
                    'arguments': {'id': bundle_id}}},
        {'jsonrpc': '2.0', 'id': 7, 'method': 'no/such/method'},
        {'jsonrpc': '2.0', 'id': 8, 'method': 'tools/call',
         'params': {'name': 'no_such_tool', 'arguments': {}}},
    ]
    payload = '\n'.join(json.dumps(r) for r in requests) + '\n'
    proc = subprocess.run(
        [PYTHON, os.path.join(MCP, 'python', 'server.py')],
        input=payload, capture_output=True, text=True, timeout=300,
    )
    check('server: the fallback server exits cleanly', proc.returncode == 0,
          proc.stderr[-400:])

    responses = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        responses[msg.get('id')] = msg

    # A notification gets no response, so the ids must be 1..8 and no more.
    check('server: a notification gets no response',
          set(responses) == set(range(1, 9)), str(sorted(responses)))

    init = responses[1]['result']
    check('server: initialize negotiates the protocol version',
          init['protocolVersion'] == '2025-06-18',
          str(init.get('protocolVersion')))
    check('server: initialize reports the server name',
          init['serverInfo']['name'] == 'skills-library')

    tools = responses[2]['result']['tools']
    check('server: exactly 8 tools', len(tools) == 8, str(len(tools)))
    names = [t['name'] for t in tools]
    expected = ['search_library', 'get_skill', 'get_agent', 'get_skill_bundle',
                'list_library', 'install_skills', 'install_agents',
                'uninstall_skills']
    check('server: the tool names are the expected 8', names == expected,
          str(names))
    check('server: every tool name is at most 17 characters',
          all(len(n) <= 17 for n in names))
    check('server: every tool has a title',
          all(t.get('title') for t in tools))
    check('server: every tool declares its annotations',
          all(t.get('annotations') for t in tools))
    check('server: the read tools are marked read-only',
          all(t['annotations']['readOnlyHint'] for t in tools
              if t['name'] in ('search_library', 'get_skill', 'get_agent',
                               'get_skill_bundle', 'list_library')))
    check('server: the write tools are not marked read-only',
          not any(t['annotations']['readOnlyHint'] for t in tools
                  if t['name'] in ('install_skills', 'install_agents',
                                   'uninstall_skills')))
    check('server: uninstall_skills is marked destructive',
          [t for t in tools
           if t['name'] == 'uninstall_skills'][0]['annotations']['destructiveHint'])
    check('server: every tool has an inputSchema',
          all(t.get('inputSchema') for t in tools))

    sc = responses[3]['result'].get('structuredContent')
    check('server: search_library returns structured content',
          bool(sc) and sc['results'][0]['id'] == 'skill:accessibility',
          str(sc['results'][0]['id']) if sc else 'none')

    skill = responses[4]['result']['structuredContent']
    check('server: get_skill returns the body', len(skill.get('body', '')) > 5000,
          str(len(skill.get('body', ''))))
    check('server: get_skill returns the full description',
          'Putnam' in skill.get('description', ''))

    err = responses[5]['result']
    check('server: an unknown skill is an error, not a crash',
          err.get('isError') is True)
    check('server: the error names the next step',
          'search_library' in err['content'][0]['text'])

    bundle = responses[6]['result']['structuredContent']
    check('server: get_skill_bundle returns a manifest',
          bundle['file_count'] > 100, str(bundle.get('file_count')))
    check('server: get_skill_bundle with no files returns no content',
          'files' in bundle and all('content' not in f for f in bundle['files']))

    check('server: an unknown method is -32601',
          responses[7]['error']['code'] == -32601,
          str(responses[7].get('error')))

    check('server: an unknown tool is an error, not a crash',
          responses[8]['result'].get('isError') is True)


# ------------------------------------------------- 7. the write safety rules
def test_write_safety(idx):
    """`install_skills` with apply:false must write nothing."""
    import shutil
    import tempfile
    import installers
    from installers import install_skill, install_agent, skill_target_path

    home = os.path.expanduser('~')

    # The harness directory is redirected to a temporary tree, so this
    # test measures the *installer's* behaviour rather than whatever
    # happens to be installed on the machine running it. A test that
    # reads the real ~/.puku-cli fails the moment a skill is really
    # installed there -- which is the state the library wants to reach.
    tmp = tempfile.mkdtemp(prefix='write-safety-test-')
    original = dict(installers.TARGET_DIRS)
    try:
        installers.TARGET_DIRS['puku-cli'] = [os.path.join(tmp, 'skills')]
        puku = os.path.join(tmp, 'skills')
        os.makedirs(puku, exist_ok=True)

        before = set()
        for root, dirs, files in os.walk(puku):
            for f in files:
                before.add(os.path.join(root, f))
        before_dirs = set(os.listdir(puku))

        t = install_skill('puku-cli', 'tdd-workflow', 'skill:tdd-workflow',
                          'test', [], 'skills/tdd-workflow',
                          os.path.join(BASE, 'skills', 'tdd-workflow', 'SKILL.md'),
                          BASE, mode='symlink', apply=False)
        check('install: a dry run reports "planned"', t['status'] == 'planned',
              t.get('status', ''))
        check('install: a dry run writes nothing',
              not os.path.exists(skill_target_path('puku-cli', 'tdd-workflow')))

        after = set()
        for root, dirs, files in os.walk(puku):
            for f in files:
                after.add(os.path.join(root, f))
        after_dirs = set(os.listdir(puku))
        check('install: a dry run leaves the harness directory byte-identical',
              before == after and before_dirs == after_dirs)
    finally:
        installers.TARGET_DIRS.clear()
        installers.TARGET_DIRS.update(original)
        shutil.rmtree(tmp, ignore_errors=True)

    # The whitelist must refuse a path outside the harness directories.
    from installers import check_target
    err = check_target('puku-cli', '/tmp/evil')
    check('install: a path outside the whitelist is refused',
          bool(err) and 'Refusing' in err, str(err))
    err = check_target('claude-code',
                       os.path.join(home, '.claude', 'skills', 'learned', 'x'))
    check('install: the harness-managed learned/ directory is refused',
          bool(err) and 'Refusing' in err, str(err))

    # Cline has no agent mechanism, and the error must say so.
    t = install_agent('cline', 'code-reviewer', 'agent:code-reviewer', 'x',
                      [], '', '', '', BASE, '', apply=False)
    check('install: install_agents for Cline is refused with an explanation',
          t['status'] == 'error' and 'not supported' in t.get('reason', ''),
          t.get('reason', ''))


def test_install_targets(idx):
    """`install_skills` accepts ids, a tier, or both.

    Either one alone is enough. Neither one is enough -- and saying so
    is better than a KeyError.
    """
    import server as pyserver

    srv = pyserver.Server()

    # A tier alone installs that tier.
    out = srv.tool_install_skills({'harness': 'puku-cli', 'tier': 1})
    tier1 = [t['id'] for t in out['targets']]
    # The tier-1 skills are the packs this tree publishes. The count is
    # read from the index rather than hard-coded, because the public
    # tree publishes fewer packs than the local one -- five of the six
    # are excluded by their licence.
    n_packs = len(idx.data.get('packs') or [])
    check('install: a tier alone selects that tier',
          len(tier1) == n_packs and all(':' in i for i in tier1),
          str(tier1))
    check('install: a tier install is a dry run by default',
          out['apply'] is False and out['written'] == 0, str(out.get('note')))

    # A tier of 701 skills is capped, and the truncation is reported.
    out = srv.tool_install_skills({'harness': 'puku-cli', 'tier': 3})
    check('install: a large tier is capped at 50 targets',
          len(out['targets']) == 50, str(len(out['targets'])))
    check('install: the truncation is reported, not silent',
          bool(out['errors']) and 'only the first' in out['errors'][0],
          str(out['errors'][:1]))

    # Neither ids nor tier is an error that names the fix.
    try:
        srv.tool_install_skills({'harness': 'puku-cli'})
        ok, msg = False, 'no error raised'
    except pyserver.ToolError as e:
        ok, msg = True, str(e)
    check('install: neither ids nor tier is refused with an explanation',
          ok and 'ids' in msg and 'tier' in msg, msg)

    # A tier given alongside ids is a filter -- and a skill filtered
    # out must be reported, not silently dropped.
    out = srv.tool_install_skills({
        'harness': 'puku-cli', 'ids': ['skill:tdd-workflow'], 'tier': 1})
    check('install: a tier filters the given ids',
          len(out['targets']) == 0, str(len(out['targets'])))
    check('install: a filtered-out skill is reported',
          bool(out['errors']) and 'tier 2, not tier 1' in out['errors'][0],
          str(out['errors'][:1]))


def test_agentsmd(idx):
    """`AGENTS.md` is one shared file; each skill gets its own section.

    The generic "the target exists" rule cannot apply here -- it would
    refuse the second skill, because the file exists after the first
    one lands.
    """
    import shutil
    import tempfile
    from installers import install_skill

    tmp = tempfile.mkdtemp(prefix='agentsmd-test-')
    try:
        lib = os.path.join(BASE, 'skills')
        results = []
        for name in ('alpha', 'beta'):
            results.append(install_skill(
                'agentsmd', name, 'skill:' + name, 'desc of ' + name, [],
                'skills/' + name,
                os.path.join(lib, name, 'SKILL.md'),
                BASE, mode='copy', apply=True, project_root=tmp))

        check('agentsmd: both skills are written',
              all(r['status'] == 'written' for r in results),
              str([r['status'] for r in results]))

        path = os.path.join(tmp, 'AGENTS.md')
        check('agentsmd: the file exists', os.path.isfile(path))
        text = open(path, encoding='utf-8').read() if os.path.isfile(path) else ''

        check('agentsmd: the first skill is present', 'desc of alpha' in text)
        check('agentsmd: the second skill is present', 'desc of beta' in text)
        check('agentsmd: each skill has its own marker',
              text.count('skills-library:alpha') == 1
              and text.count('skills-library:beta') == 1)
        check('agentsmd: the content is plain markdown, not frontmatter',
              '---' not in text.split('## alpha')[0].replace(
                  '<!-- skills-library:alpha -->', ''),
              text[:120])

        # Installing the same skill again must not duplicate it, and
        # replacing it must not disturb the other skill.
        again = install_skill(
            'agentsmd', 'alpha', 'skill:alpha', 'desc of alpha', [],
            'skills/alpha', os.path.join(lib, 'alpha', 'SKILL.md'),
            BASE, mode='copy', apply=True, project_root=tmp)
        check('agentsmd: a repeated install is skipped',
              again['status'] == 'skipped', again.get('status', ''))

        replaced = install_skill(
            'agentsmd', 'alpha', 'skill:alpha', 'NEW desc', [],
            'skills/alpha', os.path.join(lib, 'alpha', 'SKILL.md'),
            BASE, mode='copy', apply=True, overwrite=True, project_root=tmp)
        check('agentsmd: an overwrite is written',
              replaced['status'] == 'written', replaced.get('status', ''))
        text = open(path, encoding='utf-8').read()
        check('agentsmd: the overwrite replaced only that section',
              'NEW desc' in text and 'desc of beta' in text
              and text.count('skills-library:alpha') == 1,
              text[:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------ 8. the bundle
def test_bundle_contents(idx):
    """A skill with supporting files must return them."""
    by_id = {e['id']: e for e in idx.entries}
    # The largest bundle is discovered, not named: the public tree
    # publishes fewer skills than the local one, so a name present locally
    # may be absent there.
    biggest = max(idx.data['skills'], key=lambda s: s['bundle']['file_count'])
    check('bundle: the largest bundle has supporting files',
          biggest['bundle']['file_count'] > 100,
          '%s: %d' % (biggest['name'], biggest['bundle']['file_count']))

    # The 114 references that already dangle in the source tree must be
    # recorded, not hidden.
    dangling = sum(e['bundle']['refs_dangling'] for e in idx.entries)
    check('bundle: the pre-existing dangling references are recorded',
          dangling > 100, str(dangling))


def test_symlink_roundtrip(idx):
    """Install a skill as a symlink, then remove it.

    Two things go wrong here if the paths are wrong, and both are
    silent:

      * the link lands one level too deep
        (`<dir>/<name>/<name>`), so the harness never sees the skill;
      * the removal goes through the link and deletes the *library's*
        real `SKILL.md` instead of the link.

    So this test asserts on the link itself -- that it is a symlink,
    that it points into the library, that the library's file is still
    there afterwards, and that uninstalling takes the link and
    nothing else.
    """
    import shutil
    import tempfile
    import installers

    tmp = tempfile.mkdtemp(prefix='symlink-test-')
    original = dict(installers.TARGET_DIRS)
    try:
        # Point the harness directory at a temporary one, so this
        # test never touches the real ~/.puku-cli.
        installers.TARGET_DIRS['puku-cli'] = [os.path.join(tmp, 'skills')]

        name = 'tdd-workflow'
        src = os.path.join(BASE, 'skills', name, 'SKILL.md')
        lib_copy = os.path.join(tmp, 'library', name)
        os.makedirs(os.path.dirname(lib_copy), exist_ok=True)
        shutil.copytree(os.path.join(BASE, 'skills', name), lib_copy)

        t = installers.install_skill(
            'puku-cli', name, 'skill:' + name, 'test', [],
            os.path.join('library', name), src, tmp,
            mode='symlink', apply=True)

        link = os.path.join(tmp, 'skills', name)
        check('symlink: the install is written',
              t['status'] == 'written', t.get('reason', ''))
        check('symlink: the link sits at <dir>/<name>, not one level deeper',
              os.path.islink(link), link)
        check('symlink: the link points into the library',
              os.path.islink(link)
              and os.path.realpath(link).startswith(os.path.realpath(tmp)),
              os.path.realpath(link) if os.path.lexists(link) else 'missing')
        check('symlink: the link resolves to a real SKILL.md',
              os.path.isfile(os.path.join(link, 'SKILL.md')))
        check('symlink: the path reported is the link, not the file inside it',
              t['path'] == link, t['path'])

        # Uninstall must take the link and leave the library alone.
        u = installers.uninstall_target(link, True, tmp)
        check('symlink: the uninstall is removed', u['status'] == 'removed',
              u.get('reason', ''))
        check('symlink: the link is gone', not os.path.lexists(link))
        check("symlink: the library's own SKILL.md survived the uninstall",
              os.path.isfile(os.path.join(lib_copy, 'SKILL.md')))

        # The uninstall path the server uses must find the link, not
        # the file inside it.
        path, err = installers.uninstall_skill_path('puku-cli', name)
        check('symlink: the uninstall path is the link path',
              path == link and err is None, str((path, err)))
    finally:
        installers.TARGET_DIRS.clear()
        installers.TARGET_DIRS.update(original)
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    from search import load_index
    idx = load_index()

    test_index(idx)
    test_descriptions(idx)
    test_postings(idx)
    test_bundles(idx)
    test_search(idx)
    test_search_counts(idx)
    test_search_rules(idx)
    test_task_curation(idx)
    test_server()
    test_write_safety(idx)
    test_install_targets(idx)
    test_agentsmd(idx)
    test_bundle_contents(idx)
    test_symlink_roundtrip(idx)

    if failures:
        sys.stderr.write('\n%d FAILURE(S) out of %d checks\n'
                         % (len(failures), checks))
        for f in failures:
            sys.stderr.write('  - %s\n' % f)
        return 1
    sys.stdout.write('\nMCP TESTS: PASS — all %d checks\n' % checks)
    return 0


if __name__ == '__main__':
    sys.exit(main())
