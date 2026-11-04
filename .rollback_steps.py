#!/usr/bin/env python3
"""Roll back a logged build run from its per-step snapshots.

Complements git: git reverts the whole project in one move, this reverts
individual steps without touching history.

    python3 .rollback_steps.py --list
    python3 .rollback_steps.py <run_id> [--step N] [--dry-run]
"""
import json
import os
import shutil
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(BASE, 'logs')


def load_run(run_id):
    p = os.path.join(LOGS, run_id, 'manifest.json')
    if not os.path.isfile(p):
        return None
    with open(p, encoding='utf-8') as fh:
        return json.load(fh)


def list_runs():
    if not os.path.isdir(LOGS):
        print('no runs yet')
        return 0
    run_ids = sorted(d for d in os.listdir(LOGS)
                     if os.path.isfile(os.path.join(LOGS, d, 'manifest.json')))
    if not run_ids:
        print('no runs yet')
        return 0
    for rid in run_ids:
        m = load_run(rid)
        if not m:
            continue
        print('%s  %-5s  %d step(s)  commit %s' % (
            rid, m.get('status', '?'), len(m.get('steps', [])),
            (m.get('git', {}).get('commit_before') or '?')[:8]))
        for s in m.get('steps', []):
            changed = ','.join(s.get('changed') or []) or '-'
            print('   %2d %-16s %-5s %6.1fs  changed: %s' % (
                s.get('n', 0), s.get('name', '?'), s.get('status', '?'),
                s.get('duration_s', 0.0), changed))
    return 0


def restore_step(run_dir, step, dry_run):
    """Restore the files a step touched, from its snapshot dir."""
    snap = os.path.join(run_dir, step.get('snapshot_dir', ''))
    restored, deleted, missing = [], [], []
    for rel in step.get('touched') or []:
        src = os.path.join(snap, rel)
        dst = os.path.join(BASE, rel)
        if os.path.isfile(src):
            if not dry_run:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
            restored.append(rel)
        elif os.path.exists(dst):
            if not dry_run:
                os.remove(dst)
            deleted.append(rel)
        else:
            missing.append(rel)
    return restored, deleted, missing


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ('--list', '-l'):
        return list_runs()

    dry_run = '--dry-run' in argv
    run_id = next((a for a in argv if not a.startswith('--')), None)
    only_step = None
    if '--step' in argv:
        only_step = int(argv[argv.index('--step') + 1])

    if not run_id:
        print('usage: rollback.sh <run_id> [--step N] [--dry-run]', file=sys.stderr)
        return 2

    m = load_run(run_id)
    if not m:
        print('no such run: %s' % run_id, file=sys.stderr)
        return 2
    run_dir = os.path.join(LOGS, run_id)

    steps = m.get('steps', [])
    if only_step is not None:
        steps = [s for s in steps if s.get('n') == only_step]
        if not steps:
            print('run %s has no step %d' % (run_id, only_step), file=sys.stderr)
            return 2

    prefix = 'DRY RUN: would' if dry_run else 'Restoring'
    for s in steps:
        restored, deleted, missing = restore_step(run_dir, s, dry_run)
        print('%s step %d (%s):' % (prefix, s.get('n', 0), s.get('name', '?')))
        for r in restored:
            print('   restore %s' % r)
        for d in deleted:
            print('   delete  %s  (created by that step)' % d)
        for x in missing:
            print('   absent  %s  (nothing to restore)' % x)
        if not (restored or deleted or missing):
            print('   (no files declared)')

    if not dry_run:
        print()
        print('Rolled back run %s%s' % (
            run_id, ' step %d' % only_step if only_step is not None else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
