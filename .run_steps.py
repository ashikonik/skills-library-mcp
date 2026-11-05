#!/usr/bin/env python3
"""Logged build driver for the Skills_n_Agents library.

Runs each build step as a discrete, snapshotted, validated step and records
everything under logs/<run_id>/ so any step can be inspected, validated, or
rolled back without touching git history.

Design notes
------------
* The step table below declares the files each step may touch. The snapshot is
  taken from that declaration, never guessed, so the snapshot is deterministic.
* Every step writes its own log file with the full command output.
* sha256 before/after of every touched file is recorded, so "did this step
  actually change anything?" is answerable after the fact.
* The manifest is written incrementally — a crashed run still leaves a record.
* Nothing is ever pruned. Older runs are summarised only after the user asks.

Usage:
    python3 .run_steps.py                 # run all steps
    python3 .run_steps.py --list          # list the declared steps
    python3 .run_steps.py --only NAME     # run one step (by name)
    python3 .run_steps.py --skip NAME     # skip a step (repeatable)
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(BASE, 'logs')
PY = sys.executable

# ---------------------------------------------------------------- step table
# touched: files this step may modify (snapshotted before the step runs)
# validate: key into VALIDATORS below
STEPS = [
    {
        'name': 'build-library',
        'command': [PY, '.build_library.py'],
        'touched': ['.library_data.json'],
        'validate': 'build-library',
        'desc': 'Scan the machine and rebuild skills/ + agents/ + .library_data.json',
    },
    {
        'name': 'build-guide',
        'command': [PY, '.build_guide.py'],
        'touched': ['ROUTING_GUIDE.md'],
        'validate': 'build-guide',
        'desc': 'Regenerate ROUTING_GUIDE.md from .library_data.json',
    },
    {
        'name': 'gen-report',
        'command': [PY, '.gen_report.py'],
        'touched': ['SKILLS_AND_AGENTS_REPORT.md'],
        'validate': 'gen-report',
        'desc': 'Regenerate SKILLS_AND_AGENTS_REPORT.md (independent machine scan)',
    },
    {
        'name': 'build-index',
        'command': [PY, 'mcp/build/build_index.py'],
        'touched': ['mcp/data/index.json'],
        'validate': 'build-index',
        'desc': 'Build the MCP search index from the library',
    },
    {
        'name': 'build-server',
        'command': ['npm', 'run', 'build'],
        'cwd': 'mcp',
        'touched': ['mcp/dist'],
        'validate': None,
        'desc': 'Compile the TypeScript MCP server',
    },
    {
        'name': 'verify-all',
        'command': [PY, '.verify_all.py'],
        'touched': [],
        'validate': None,
        'desc': 'Run the full verification suite',
    },
    {
        'name': 'determinism',
        'command': [PY, '.verify_determinism.py'],
        'touched': [],
        'validate': None,
        'desc': 'Rebuild everything a second time and prove the output is byte-identical',
    },
    {
        'name': 'mcp-tests',
        'command': [PY, 'mcp/tests/test_mcp.py'],
        'touched': [],
        'validate': None,
        'desc': 'Run the MCP server test suite',
    },
    {
        'name': 'mcp-agreement',
        'command': [PY, 'mcp/tests/test_agreement.py'],
        'touched': [],
        'validate': None,
        'desc': 'Assert the TypeScript and Python servers rank identically',
    },
    {
        'name': 'mcp-protocol',
        'command': [PY, 'mcp/tests/test_jsonrpc.py'],
        'touched': [],
        'validate': None,
        'desc': 'Speak raw JSON-RPC to both servers and compare their answers',
    },
    {
        'name': 'mcp-node-tests',
        'command': ['npm', 'test'],
        'cwd': 'mcp',
        'touched': [],
        'validate': None,
        'desc': 'Run the TypeScript test suite with Node\'s built-in runner',
    },
    {
        'name': 'mcp-e2e',
        'command': ['node', 'scripts/e2e.mjs'],
        'cwd': 'mcp',
        'touched': [],
        'validate': None,
        'desc': ('Drive the compiled server over stdio: install a skill, '
                 'check it on disk, uninstall it'),
    },
    {
        'name': 'provenance',
        'command': [PY, 'mcp/build/provenance.py'],
        'touched': ['mcp/data/provenance.json'],
        'validate': None,
        'desc': ('Resolve the licence and the real owner of every entry in '
                 'the library'),
    },
    {
        'name': 'assemble-public',
        'command': [PY, 'mcp/build/assemble_public.py'],
        'touched': [],
        'validate': None,
        'desc': ('Assemble the publishable tree: licence-filtered, '
                 'de-pathed, and gated by the licence and leak checks'),
    },
    {
        'name': 'write-credits',
        'command': [PY, 'mcp/build/write_credits.py'],
        'touched': [],
        'validate': None,
        'desc': ('Write the public tree\'s LICENSE, NOTICE and CREDITS.md '
                 'from the provenance table'),
    },
    {
        'name': 'scan-leaks',
        'command': [PY, 'mcp/build/scan_leaks.py'],
        'touched': [],
        'validate': None,
        'desc': ('Assert the public tree names no absolute home path -- '
                 'the builder\'s own, and nobody else\'s'),
    },
]


# ------------------------------------------------------------------ helpers
def sha256(path):
    """The hash of a file, or of a whole directory tree.

    A directory's hash is taken over its sorted (relative path, file hash)
    pairs, so a build that rewrites a file inside it changes the hash even
    though the directory entry itself did not.
    """
    if os.path.isdir(path):
        h = hashlib.sha256()
        for root, dirs, files in os.walk(path):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, path)
                h.update(rel.encode('utf-8'))
                h.update(b'\0')
                h.update((sha256(full) or '').encode('utf-8'))
                h.update(b'\0')
        return 'dir:' + h.hexdigest()
    if not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def utcnow():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def git(*args):
    try:
        r = subprocess.run(['git'] + list(args), cwd=BASE,
                           capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    except OSError:
        return None


def snapshot(run_dir, step_no, name, files):
    """Copy each declared file into the step's snapshot dir.

    Returns (dir, before_hashes, missing_before) where missing_before lists
    files that did not exist yet — rollback must delete those, not restore.
    """
    snap = os.path.join(run_dir, 'snapshot', '%02d-%s' % (step_no, name))
    before, missing = {}, []
    for rel in files:
        src = os.path.join(BASE, rel)
        before[rel] = sha256(src)
        if before[rel] is None:
            missing.append(rel)
            continue
        dst = os.path.join(snap, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    if files:
        os.makedirs(snap, exist_ok=True)
    return snap, before, missing


def restore(run_dir, step_no, name, files):
    """Restore files from a step's snapshot. Files that did not exist before
    the step are deleted."""
    snap = os.path.join(run_dir, 'snapshot', '%02d-%s' % (step_no, name))
    restored, deleted = [], []
    for rel in files:
        src = os.path.join(snap, rel)
        dst = os.path.join(BASE, rel)
        if os.path.isdir(src):
            # Replace the tree wholesale -- a build may have added or
            # removed files inside it, and a merge would keep the stale ones.
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            elif os.path.exists(dst):
                os.remove(dst)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copytree(src, dst)
            restored.append(rel)
        elif os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            restored.append(rel)
        elif os.path.exists(dst):
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            else:
                os.remove(dst)
            deleted.append(rel)
    return restored, deleted


# --------------------------------------------------------------- validators
def _load_library_data():
    p = os.path.join(BASE, '.library_data.json')
    if not os.path.isfile(p):
        return None
    with open(p, encoding='utf-8') as fh:
        return json.load(fh)


def validate_build_library(snap_dir):
    """The library must be self-consistent, and the truncation fix must hold.

    The *counts* are deliberately not asserted against constants. This
    library grows -- that is what it is for -- and a validator that
    demands an exact skill count turns every addition into a build
    failure that has to be answered by editing the validator. The
    number that must hold is the one that is a property of the tree
    rather than of history: the library must describe exactly what is
    on disk.

    What *is* asserted:

      * the library's contents match the directories on disk;
      * nothing was silently lost relative to the previous build, unless
        it is genuinely gone from the machine;
      * no description got shorter (a new truncation);
      * the named skills still carry their full descriptions.
    """
    assertions, problems = [], []
    data = _load_library_data()
    if data is None:
        return ['.library_data.json missing'], ['index not written']

    n_sk = len(data['skills'])
    n_ag = len(data['agents'])
    assertions.append('skill count == %d' % n_sk)
    assertions.append('agent count == %d' % n_ag)

    # The library must describe exactly what is on disk. A builder that
    # failed to copy a skill (or copied one it did not record) produces a
    # library that disagrees with the tree, and the index is built from
    # the library -- so the whole search surface would be quietly wrong.
    on_disk_skills = sum(
        1 for n in os.listdir(os.path.join(BASE, 'skills'))
        if os.path.isdir(os.path.join(BASE, 'skills', n)))
    assertions.append('skills on disk == %d' % on_disk_skills)
    if n_sk != on_disk_skills:
        problems.append('the library holds %d skills but the tree holds %d'
                        % (n_sk, on_disk_skills))
    on_disk_agents = sum(
        1 for n in os.listdir(os.path.join(BASE, 'agents'))
        if n.endswith('.md'))
    assertions.append('agents on disk == %d' % on_disk_agents)
    if n_ag != on_disk_agents:
        problems.append('the library holds %d agents but the tree holds %d'
                        % (n_ag, on_disk_agents))

    # Name sets must be identical to the snapshot — the fix must not change
    # which skills/agents are discovered.
    prev = os.path.join(snap_dir, '.library_data.json')
    if os.path.isfile(prev):
        with open(prev, encoding='utf-8') as fh:
            old = json.load(fh)
        old_sk = {s['name'] for s in old['skills']}
        new_sk = {s['name'] for s in data['skills']}
        old_ag = {a['name'] for a in old['agents']}
        new_ag = {a['name'] for a in data['agents']}

        # A name that vanished is a failure only when the content is
        # still on disk: then the builder dropped it, which is a bug.
        # When the content is genuinely gone from the machine, the
        # library is right and the disappearance is reported, not
        # failed -- an upstream skill being uninstalled is not a
        # regression in this repository.
        def _lost(old_names, new_names, kind):
            lost = old_names - new_names
            still_there = []
            for nm in sorted(lost):
                for rec in (old['skills'] if kind == 'skill' else old['agents']):
                    if rec['name'] != nm:
                        continue
                    src = rec.get('source') or ''
                    if kind == 'skill':
                        if os.path.isfile(os.path.join(src, 'SKILL.md')):
                            still_there.append(nm)
                    elif os.path.isfile(src):
                        still_there.append(nm)
                    break
            return lost, still_there

        for kind, old_names, new_names in (('skill', old_sk, new_sk),
                                            ('agent', old_ag, new_ag)):
            lost, still_there = _lost(old_names, new_names, kind)
            added = sorted(new_names - old_names)
            assertions.append('%s names added since the snapshot: %d %s'
                              % (kind, len(added), added[:5]))
            assertions.append('%s names lost since the snapshot: %d %s'
                              % (kind, len(lost), sorted(lost)[:5]))
            if still_there:
                problems.append('the builder dropped %d %s that are still on '
                                'disk: %s' % (len(still_there), kind,
                                              still_there[:5]))

        # No description may get SHORTER than it was (that would be a new
        # truncation introduced by a change).
        #
        # The comparison is on the whitespace-normalised text, and it ignores
        # the difference between a literal backslash-escape and the character
        # it escapes: YAML resolves `\"` to `"`, so a description can legitimately
        # get a few characters shorter without losing a word. The real
        # regression -- a truncated description -- loses far more than that.
        old_desc = {s['name']: s.get('desc', '') for s in old['skills']}

        def _norm(t):
            return ' '.join((t or '').split()).replace('\\"', '"').replace("\\'", "'")

        shorter = []
        for s in data['skills']:
            n = s['name']
            if n not in old_desc:
                continue
            new_len = len(_norm(s.get('desc', '')))
            old_len = len(_norm(old_desc[n]))
            if new_len < old_len - 4:
                shorter.append('%s (%d -> %d)' % (n, old_len, new_len))
        assertions.append('no description shorter than snapshot')
        if shorter:
            problems.append('descriptions got shorter: %s' % shorter[:5])
        longer = [n for n, s in ((x['name'], x) for x in data['skills'])
                  if n in old_desc and len(s.get('desc', '')) > len(old_desc[n])]
        assertions.append('descriptions that grew: %d' % len(longer))

    # The truncation fix itself: descriptions now come from YAML, and the
    # skills that were truncated carry their full activation triggers.
    yaml_skills = sum(1 for s in data['skills'] if s.get('desc_source') == 'yaml')
    body_skills = sum(1 for s in data['skills'] if s.get('desc_source') == 'body')
    assertions.append('desc_source == yaml for %d skills' % yaml_skills)
    assertions.append('desc_source == body for %d skills' % body_skills)
    if body_skills > 1:
        problems.append('expected 1 skill to fall back to its body summary, '
                        'got %d' % body_skills)
    by_name = {s['name']: s.get('desc', '') for s in data['skills']}
    for name, needle in (('math-olympiad', 'Putnam'),
                          ('accessibility', 'WCAG 2.2 Level AA')):
        if needle not in by_name.get(name, ''):
            problems.append('%s description is missing %r — the truncation '
                            'fix is not in effect' % (name, needle))
    assertions.append('math-olympiad and accessibility carry full descriptions')
    return assertions, problems


def validate_generated(rel, min_bytes=1000):
    """A generated document must exist and be substantial."""
    p = os.path.join(BASE, rel)
    assertions, problems = [], []
    if not os.path.isfile(p):
        return ['%s exists' % rel], ['%s was not written' % rel]
    size = os.path.getsize(p)
    assertions.append('%s size == %d bytes' % (rel, size))
    if size < min_bytes:
        problems.append('%s is only %d bytes' % (rel, size))
    return assertions, problems


def validate_build_index(snap_dir):
    """The index must describe the library, and its own counts must agree.

    The counts are read from the index and checked against each other --
    not against constants. This library grows, and a validator that
    pins the entry count turns every addition into a build failure
    that has to be answered by editing the validator. What must hold is
    that the index is *internally* consistent and that it matches the
    library it was built from.
    """
    assertions, problems = [], []
    p = os.path.join(BASE, 'mcp/data/index.json')
    if not os.path.isfile(p):
        return ['index.json exists'], ['index.json was not written']
    with open(p, encoding='utf-8') as fh:
        idx = json.load(fh)
    assertions.append('schema_version == %s' % idx.get('schema_version'))
    if idx.get('schema_version') != 1:
        problems.append('unexpected schema_version %r' % idx.get('schema_version'))
    c = idx.get('counts', {})
    assertions.append('counts: %s' % json.dumps(c.get('by_tier')))

    n_sk = len(idx.get('skills', []))
    n_ag = len(idx.get('agents', []))
    total = n_sk + n_ag
    assertions.append('skills == %d, agents == %d, entries == %d'
                      % (n_sk, n_ag, total))
    if c.get('skills') != n_sk:
        problems.append('counts.skills is %r but the index holds %d'
                        % (c.get('skills'), n_sk))
    if c.get('agents') != n_ag:
        problems.append('counts.agents is %r but the index holds %d'
                        % (c.get('agents'), n_ag))

    # The tiers must account for every entry, with nothing lost and
    # nothing counted twice.
    by_tier = c.get('by_tier', {})
    tier_sum = sum(by_tier.get(str(i), 0) for i in (1, 2, 3))
    assertions.append('the tiers sum to %d' % tier_sum)
    if tier_sum != total:
        problems.append('the tiers sum to %d but the index holds %d entries'
                        % (tier_sum, total))
    skill_tier_sum = sum(c.get('skill_by_tier', {}).get(str(i), 0)
                          for i in (1, 2, 3))
    assertions.append('the skill tiers sum to %d' % skill_tier_sum)
    if skill_tier_sum != n_sk:
        problems.append('the skill tiers sum to %d but the index holds %d '
                        'skills' % (skill_tier_sum, n_sk))

    # The tier-1 skills are exactly the packs the index publishes, and
    # every agent is tier 1. That is the definition, and it is checked
    # here because the index is what the search engine ranks with.
    tier1_skills = sorted(s['name'] for s in idx.get('skills', [])
                           if s.get('tier') == 1)
    packs = sorted(idx.get('packs') or [])
    assertions.append('tier-1 skills == the published packs')
    if tier1_skills != packs:
        problems.append('tier-1 skills are %s but the packs are %s'
                        % (tier1_skills, packs))
    agents_not_tier1 = [a['name'] for a in idx.get('agents', [])
                        if a.get('tier') != 1]
    assertions.append('every agent is tier 1')
    if agents_not_tier1:
        problems.append('%d agents are not tier 1: %s'
                        % (len(agents_not_tier1), agents_not_tier1[:5]))

    # The index must agree with the library it was built from.
    data = _load_library_data()
    if data is not None:
        lib_sk = {s['name'] for s in data['skills']}
        lib_ag = {a['name'] for a in data['agents']}
        idx_sk = {s['name'] for s in idx.get('skills', [])}
        idx_ag = {a['name'] for a in idx.get('agents', [])}
        assertions.append('the index holds exactly the library\'s entries')
        if lib_sk != idx_sk:
            problems.append('the index and the library disagree on skills: '
                            '+%s -%s' % (sorted(idx_sk - lib_sk)[:5],
                                          sorted(lib_sk - idx_sk)[:5]))
        if lib_ag != idx_ag:
            problems.append('the index and the library disagree on agents: '
                            '+%s -%s' % (sorted(idx_ag - lib_ag)[:5],
                                          sorted(lib_ag - idx_ag)[:5]))
    return assertions, problems


def validate_gen_report(snap_dir):
    """The report must exist and must agree with the library it describes.

    The report is generated by an independent machine scan, so it can drift
    from `.library_data.json`. Where both carry the same skill, the
    description shown in the report must be the one the library holds —
    otherwise the two generated documents contradict each other.
    """
    assertions, problems = [], []
    p = os.path.join(BASE, 'SKILLS_AND_AGENTS_REPORT.md')
    if not os.path.isfile(p):
        return ['SKILLS_AND_AGENTS_REPORT.md exists'], ['report was not written']
    size = os.path.getsize(p)
    assertions.append('SKILLS_AND_AGENTS_REPORT.md size == %d bytes' % size)
    if size < 1000:
        problems.append('report is only %d bytes' % size)

    data = _load_library_data()
    if data is None:
        return assertions, problems

    # Every skill's row in the report is `| `name` | desc | copies | `path` |`.
    with open(p, encoding='utf-8') as fh:
        text = fh.read()
    rows = {}
    for m in re.finditer(r'^\| `([^`]+)` \| (.*?) \| (\d+) \| `([^`]+)` \|$',
                         text, re.M):
        rows.setdefault(m.group(1), (m.group(2), m.group(4)))

    lib = {s['name']: s.get('desc', '') for s in data['skills']}
    checked = 0
    for name, (desc, path) in rows.items():
        if name not in lib:
            continue
        expected = lib[name]
        if not expected:
            continue
        # The report prints a placeholder for a skill with no frontmatter
        # description. The library falls back to a body summary for those, so
        # there is nothing to compare — the two are consistent by construction.
        if desc.startswith('_(') and desc.endswith(')_'):
            continue
        checked += 1
        # The report clips descriptions; a clipped row is a prefix of the
        # full text (plus the ellipsis the clipper appends).
        if desc != expected and not expected.startswith(desc.rstrip('.…')):
            problems.append('report description differs from library for %r' % name)
            if len(problems) >= 5:
                break
    assertions.append('report rows checked against library: %d' % checked)
    assertions.append('report agrees with .library_data.json')
    return assertions, problems


VALIDATORS = {
    'build-library': validate_build_library,
    'build-guide': lambda snap: validate_generated('ROUTING_GUIDE.md'),
    'gen-report': validate_gen_report,
    'build-index': validate_build_index,
}


# --------------------------------------------------------------------- main
def write_manifest(path, manifest):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write('\n')
    os.replace(tmp, path)


def main():
    argv = sys.argv[1:]
    if '--list' in argv:
        for s in STEPS:
            print('%-16s %s' % (s['name'], s['desc']))
        return 0

    only = None
    skip = set()
    i = 0
    while i < len(argv):
        if argv[i] == '--only':
            only = argv[i + 1]
            i += 2
        elif argv[i] == '--skip':
            skip.add(argv[i + 1])
            i += 2
        else:
            i += 1

    steps = [s for s in STEPS if s['name'] not in skip]
    if only:
        steps = [s for s in steps if s['name'] == only]
        if not steps:
            print('no step named %r' % only, file=sys.stderr)
            return 2

    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    run_dir = os.path.join(LOGS, run_id)
    os.makedirs(os.path.join(run_dir, 'snapshot'), exist_ok=True)

    manifest = {
        'run_id': run_id,
        'started_at': utcnow(),
        'library_root': BASE,
        'git': {
            'commit_before': git('rev-parse', 'HEAD'),
            'commit_after': None,
            'dirty_before': bool(git('status', '--porcelain')),
        },
        'steps': [],
    }
    manifest_path = os.path.join(run_dir, 'manifest.json')
    write_manifest(manifest_path, manifest)

    failures = []
    for n, step in enumerate(steps, 1):
        name = step['name']
        print('==> [%d/%d] %s — %s' % (n, len(steps), name, step['desc']))
        log_name = '%02d-%s.log' % (n, name)
        log_path = os.path.join(run_dir, log_name)

        snap_dir, before, missing = snapshot(run_dir, n, name, step['touched'])

        # A step may declare a working directory relative to the library
        # root. `npm` must run inside mcp/ to find its package.json; the
        # declared files still resolve against BASE.
        cwd = os.path.join(BASE, step['cwd']) if step.get('cwd') else BASE

        started = utcnow()
        t0 = time.time()
        proc = subprocess.run(step['command'], cwd=cwd,
                              capture_output=True, text=True)
        duration = time.time() - t0
        ended = utcnow()

        with open(log_path, 'w', encoding='utf-8') as fh:
            fh.write('$ %s\n' % ' '.join(step['command']))
            fh.write('# started  %s\n' % started)
            fh.write('# ended    %s\n' % ended)
            fh.write('# exit     %d\n' % proc.returncode)
            fh.write('# duration %.2fs\n\n' % duration)
            fh.write('--- stdout ---\n')
            fh.write(proc.stdout)
            if proc.stderr.strip():
                fh.write('\n--- stderr ---\n')
                fh.write(proc.stderr)

        after = {rel: sha256(os.path.join(BASE, rel)) for rel in step['touched']}
        changed = [rel for rel in step['touched'] if before.get(rel) != after.get(rel)]

        record = {
            'n': n,
            'name': name,
            'desc': step['desc'],
            'command': ' '.join(step['command']),
            'exit_code': proc.returncode,
            'status': 'pass' if proc.returncode == 0 else 'fail',
            'started_at': started,
            'ended_at': ended,
            'duration_s': round(duration, 2),
            'touched': step['touched'],
            'sha256_before': before,
            'sha256_after': after,
            'changed': changed,
            'missing_before': missing,
            'log': log_name,
            'snapshot_dir': os.path.relpath(snap_dir, run_dir),
            'validation': None,
        }

        # Validation runs only when the step itself succeeded.
        if proc.returncode == 0 and step['validate'] in VALIDATORS:
            assertions, problems = VALIDATORS[step['validate']](snap_dir)
            record['validation'] = {
                'exit_code': 0 if not problems else 1,
                'assertions': assertions,
                'problems': problems,
            }
            if problems:
                record['status'] = 'fail'
                for pb in problems:
                    print('    PROBLEM: %s' % pb)
            else:
                print('    validation ok (%d assertions)' % len(assertions))

        manifest['steps'].append(record)
        write_manifest(manifest_path, manifest)

        if record['status'] != 'pass':
            failures.append(name)
            print('    FAILED — see %s' % log_path)
            break

    manifest['ended_at'] = utcnow()
    manifest['status'] = 'fail' if failures else 'pass'
    manifest['failed_steps'] = failures
    manifest['git']['commit_after'] = git('rev-parse', 'HEAD')
    manifest['git']['dirty_after'] = bool(git('status', '--porcelain'))
    write_manifest(manifest_path, manifest)

    # Keep a tracked copy of the latest manifest so a fresh clone knows the
    # last known-good state.
    #
    # The tracked copy is redacted: it is committed, and a committed file
    # must not name the absolute path of the machine that produced it.
    # The unredacted manifest stays in `logs/`, which is not tracked.
    last = os.path.join(BASE, 'mcp', 'docs', 'last-run.json')
    try:
        os.makedirs(os.path.dirname(last), exist_ok=True)
        with open(manifest_path, encoding='utf-8') as fh:
            tracked = json.load(fh)
        tracked.pop('library_root', None)
        with open(last, 'w', encoding='utf-8') as fh:
            json.dump(tracked, fh, indent=2, sort_keys=True)
            fh.write('\n')
    except (OSError, ValueError):
        pass

    print()
    print('run %s: %s' % (run_id, manifest['status']))
    print('manifest: %s' % manifest_path)
    if failures:
        print('failed steps: %s' % ', '.join(failures))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
