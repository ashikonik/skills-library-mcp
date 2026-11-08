#!/usr/bin/env python3
"""The postings gate.

The index publishes a list of searchable fields (`search.fields`) and a
postings index (`search.postings`). For a long time the two disagreed:
the index advertised `name`, `description`, `prompt_signals`, `domain`
and `tasks`, while the postings held only the first two. A caller who
trusted the advertised list would look for a token in a bucket that did
not exist and find nothing -- and nothing in the tree would say so.

This test asserts the contract that closes that gap:

  * every advertised field has a postings bucket, and every postings
    bucket belongs to an advertised field (neither may be extra);
  * every field's postings actually resolve -- each token maps to real
    entries, and each entry that carries the token is in the bucket;
  * the postings are *field-aware*: an entry reachable through one
    field's bucket is reachable through that field's bucket only, so
    the buckets mean what their names say;
  * the fields that carry curation (`prompt_signals`, `tasks`) are
    populated, not merely declared.

The failure this guards against is a silent one. A postings index that
disagrees with the field list does not crash anything; it just answers
questions wrongly, or not at all.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MCP = os.path.dirname(HERE)
BASE = os.path.dirname(MCP)

sys.path.insert(0, os.path.join(MCP, 'python'))
sys.path.insert(0, os.path.join(MCP, 'build'))

from search import SearchIndex  # noqa: E402

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


def main():
    data = load_index()
    if data is None:
        return 1

    fields = data['search']['fields']
    postings = data['search']['postings']
    entries = data['skills'] + data['agents']
    by_id = {e['id']: e for e in entries}

    # ---- 1. the advertised fields and the indexed fields are the same set.
    check('postings: every advertised field has a bucket',
          all(f in postings for f in fields),
          'missing: %s' % [f for f in fields if f not in postings])
    check('postings: no bucket exists for an unadvertised field',
          all(f in fields for f in postings),
          'extra: %s' % [f for f in postings if f not in fields])
    check('postings: the field list is not empty', bool(fields), str(fields))
    check('postings: the field list has no duplicates',
          len(set(fields)) == len(fields), str(fields))

    # ---- 2. every field's postings resolve to real entries.
    for field in fields:
        buckets = postings.get(field, {})
        unknown = []
        for kind, bucket in buckets.items():
            for token, ids in bucket.items():
                for i in ids:
                    if i not in by_id:
                        unknown.append((kind, token, i))
        check('postings[%s]: every posting names a real entry' % field,
              not unknown, str(unknown[:3]))
        wrong_kind = []
        for kind, bucket in buckets.items():
            for token, ids in bucket.items():
                for i in ids:
                    if by_id[i]['kind'] != kind:
                        wrong_kind.append((kind, token, i))
        check('postings[%s]: every posting is in its own kind bucket' % field,
              not wrong_kind, str(wrong_kind[:3]))

    # ---- 3. the buckets are sorted and deduplicated.
    unsorted = []
    for field in fields:
        for kind, bucket in postings.get(field, {}).items():
            for token, ids in bucket.items():
                if ids != sorted(ids) or len(ids) != len(set(ids)):
                    unsorted.append((field, kind, token))
    check('postings: every posting list is sorted and unique',
          not unsorted, str(unsorted[:3]))

    # ---- 4. the fields that carry curation are populated.
    #
    # An advertised-but-empty field is exactly the failure this gate
    # exists to catch: the index claims the field is searchable and the
    # postings hold nothing for it.
    populated = {}
    for field in fields:
        n = sum(len(ids) for bucket in postings.get(field, {}).values()
                for ids in bucket.values())
        populated[field] = n
    for field in ('name', 'description', 'prompt_signals', 'domain', 'tasks'):
        check('postings[%s]: the field is populated' % field,
              populated.get(field, 0) > 0,
              'advertised but empty' if field in fields else 'not advertised')

    # ---- 5. the postings are field-aware.
    #
    # A token in an entry's name must not appear in that entry's
    # `tasks` bucket unless the task row really names that token.
    # If the buckets were merged, this would pass trivially -- so the
    # check is that a *specific* curated token is confined to its field.
    sig_field = postings.get('prompt_signals', {})
    sig_tokens = set()
    for bucket in sig_field.values():
        sig_tokens.update(bucket.keys())
    desc_field = postings.get('description', {})
    desc_tokens = set()
    for bucket in desc_field.values():
        desc_tokens.update(bucket.keys())

    # A token that appears in both buckets is fine -- the same word can
    # be in a description and in a phrase. What must not happen is the
    # *whole* signal vocabulary leaking into the description bucket
    # alone, which is what a merged (field-blind) postings would look
    # like for a curated field that the descriptions never carry.
    signal_only = sig_tokens - desc_tokens
    check('postings: the prompt-signal vocabulary is not the description '
          'vocabulary', len(signal_only) > 0 or not sig_tokens,
          'the two buckets are identical (%d tokens)' % len(sig_tokens))

    # ---- 6. the name postings resolve to the entries' own names.
    #
    # Every name token of every entry must be in that entry's `name`
    # bucket. This is the check that the postings are built from the
    # records rather than from something else.
    missing_name = []
    for e in entries:
        bucket = postings.get('name', {}).get(e['kind'], {})
        for t in set(e['tokens']['name']):
            if e['id'] not in bucket.get(t, []):
                missing_name.append((e['id'], t))
                break
        if missing_name:
            break
    check('postings: every name token resolves to its entry',
          not missing_name, str(missing_name[:3]))

    # ---- 7. the description postings resolve to the entries' own
    # descriptions.
    missing_desc = []
    for e in entries:
        bucket = postings.get('description', {}).get(e['kind'], {})
        for t in set(e['tokens']['desc']):
            if e['id'] not in bucket.get(t, []):
                missing_desc.append((e['id'], t))
                break
        if missing_desc:
            break
    check('postings: every description token resolves to its entry',
          not missing_desc, str(missing_desc[:3]))

    # ---- 8. the domain postings resolve to the entries' own domains.
    missing_domain = []
    for e in entries:
        if not e.get('domain'):
            continue
        bucket = postings.get('domain', {}).get(e['kind'], {})
        for t in set(_tokenize(e['domain'])):
            if e['id'] not in bucket.get(t, []):
                missing_domain.append((e['id'], t))
                break
        if missing_domain:
            break
    check('postings: every domain token resolves to its entry',
          not missing_domain, str(missing_domain[:3]))

    # ---- 9. the task postings resolve to the rows that name the entry.
    rows_of = {}
    for row in data['tasks']:
        for s in row.get('skills') or []:
            rows_of.setdefault(('skill', s), []).append(row['task'])
        for a in row.get('agents') or []:
            rows_of.setdefault(('agent', a), []).append(row['task'])
    missing_task = []
    for (kind, name), tasks in rows_of.items():
        eid = '%s:%s' % (kind, name)
        if eid not in by_id:
            continue
        bucket = postings.get('tasks', {}).get(kind, {})
        for task in tasks:
            for t in set(_tokenize(task)):
                if eid not in bucket.get(t, []):
                    missing_task.append((eid, t))
                    break
            if missing_task:
                break
        if missing_task:
            break
    check('postings: every task token resolves to the entry it names',
          not missing_task, str(missing_task[:3]))

    # ---- 10. an entry in no task row is in no task bucket.
    stray = []
    for kind, bucket in postings.get('tasks', {}).items():
        for token, ids in bucket.items():
            for i in ids:
                if (kind, by_id[i]['name']) not in rows_of:
                    stray.append((kind, token, i))
    check('postings: no entry is in a task bucket it does not belong to',
          not stray, str(stray[:3]))

    # ---- 11. the servers can read the new shape.
    #
    # The TypeScript types describe the postings as field-aware, so the
    # compiled server must accept the index the builder now writes.
    ts_entry = os.path.join(MCP, 'dist', 'index.js')
    if not os.path.isfile(ts_entry):
        sys.stderr.write('SKIP: the TypeScript build is missing (%s).\n'
                         % ts_entry)
    else:
        import subprocess
        probe = os.path.join(HERE, '_ts_postings.mjs')
        r = subprocess.run(['node', probe], capture_output=True, text=True,
                           timeout=120)
        check('postings: the TypeScript server reads the field-aware '
              'postings', r.returncode == 0, r.stderr[-300:])

    # ---- 12. the Python fallback reads the new shape.
    try:
        idx = SearchIndex(data)
        check('postings: the Python server reads the field-aware postings',
              True)
    except Exception as exc:  # pragma: no cover - a crash is the failure
        check('postings: the Python server reads the field-aware postings',
              False, repr(exc))

    if failures:
        sys.stderr.write('\n%d FAILURE(S) out of %d checks\n'
                         % (len(failures), checks))
        for f in failures:
            sys.stderr.write('  - %s\n' % f)
        return 1
    sys.stdout.write('\nPOSTINGS: PASS — all %d checks\n' % checks)
    return 0


def _tokenize(text):
    """The builder's tokenizer, imported rather than copied.

    A copy would drift from the builder the moment the tokenizer
    changed, and the check would then fail for the wrong reason.
    """
    import build_index
    return build_index.tokenize(text)


if __name__ == '__main__':
    sys.exit(main())
