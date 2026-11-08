#!/usr/bin/env python3
"""The install manifest: what this server wrote, and where.

`install_agents` writes real files into `~/.claude/agents/` and
`~/.config/opencode/agents/`. Without a record of those writes there is
no way back: the harness directory is full of things this server did
not put there, and a blanket "uninstall everything in this directory"
would destroy them.

So every write is recorded. The manifest lives beside the project's
policy file -- `<project>/.skills-library/` -- because both are
per-project state that a project may want to check in, or to ignore.

**The manifest is a claim, not a guarantee.** It records what this
server wrote; it cannot prove that a path still holds what was written
there. So an uninstall checks both: the manifest says we wrote it, and
the thing on disk still looks like what we wrote. A path in the
manifest that has since been replaced by something else is refused with
the `not_ours` wall rather than removed.

**A missing manifest is not an error.** It means this server has not
written anything for this project -- or that the project removed the
file. Either way there is nothing to uninstall, and an uninstall in
that state says so rather than failing.
"""
import json
import os

MANIFEST_DIR = '.skills-library'
MANIFEST_FILE = 'installs.json'
SCHEMA_VERSION = 1


def manifest_path(project_root):
    """Where the manifest lives for a project."""
    return os.path.join(project_root, MANIFEST_DIR, MANIFEST_FILE)


def load_manifest(project_root):
    """Read the manifest. A missing or malformed one reads as empty.

    A malformed manifest is *not* silently ignored -- it is reported,
    because a manifest that cannot be read may still list files that
    need removing, and pretending it is empty would strand them. The
    error is carried alongside the (empty) records so the caller can
    say so.
    """
    path = manifest_path(project_root)
    if not os.path.isfile(path):
        return [], None
    try:
        with open(path, encoding='utf-8') as fh:
            parsed = json.load(fh)
    except (OSError, ValueError) as e:
        return [], 'cannot read %s: %s' % (path, e)
    if not isinstance(parsed, dict) or not isinstance(parsed.get('installs'), list):
        return [], ('%s is malformed: it must be a JSON object with an '
                    '"installs" array' % path)
    records = []
    for entry in parsed['installs']:
        if not isinstance(entry, dict):
            continue
        if not entry.get('path') or not entry.get('kind'):
            continue
        records.append(entry)
    return records, None


def save_manifest(project_root, records):
    """Write the manifest. Returns an error string, or None."""
    path = manifest_path(project_root)
    payload = {'schema_version': SCHEMA_VERSION, 'installs': records}
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write('\n')
    except OSError as e:
        return 'cannot write %s: %s' % (path, e)
    return None


def record_install(project_root, harness, kind, name, path, action):
    """Record one write. Returns an error string, or None.

    A record is keyed by the path it describes: writing the same path
    twice replaces the earlier record rather than duplicating it, so
    the manifest stays one line per path.
    """
    records, _ = load_manifest(project_root)
    kept = [r for r in records if r.get('path') != path]
    kept.append({'harness': harness, 'kind': kind, 'name': name,
                 'path': path, 'action': action})
    kept.sort(key=lambda r: (r.get('harness', ''), r.get('kind', ''),
                             r.get('name', ''), r.get('path', '')))
    return save_manifest(project_root, kept)


def forget_install(project_root, path):
    """Drop the record for a path that has been removed."""
    records, _ = load_manifest(project_root)
    kept = [r for r in records if r.get('path') != path]
    if len(kept) == len(records):
        return None
    return save_manifest(project_root, kept)


def records_for(project_root, harness, kind):
    """The records for one harness and kind."""
    records, error = load_manifest(project_root)
    if error:
        return [], error
    return [r for r in records
            if r.get('harness') == harness and r.get('kind') == kind], None
