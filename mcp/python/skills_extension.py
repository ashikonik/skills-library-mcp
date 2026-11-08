#!/usr/bin/env python3
"""The Skills extension (`io.modelcontextprotocol/skills`).

This is the mirror of `mcp/src/skills-extension.ts`. The two must agree
exactly: a client that talks to one server and then the other must not
see a different extension, and a cursor issued by one must work against
the other.

The extension serves the library's skills to MCP clients:

  * `skills/list` -- every skill, as metadata plus a complete file
    manifest. The bodies are not in the listing: a client that wants
    to know what skills exist should not have to download 66 MB to find
    out.
  * `skills/get` -- one skill by URI, for a client that has a URI but
    not a listing. A server that only lists is not conformant: a host
    must be able to load a skill it was told about by URI.
  * `resources/read` -- the bytes of a file, verified against the
    manifest's digest.
  * `resources/directory/read` -- the direct children of a directory.

The shape comes from SEP-2640 and the Agent Skills specification:

  * A skill entry is `{uri, frontmatter, resources}`. The
    `frontmatter` is verbatim -- every YAML field, unchanged -- because
    a host compares it field-by-field against the `SKILL.md` it read.
  * `resources` is the complete manifest: every file in the skill,
    exactly once, each with its URI, SHA-256 digest and byte size. It
    is never absent and never split across pages.
  * The final segment of a skill's URI path is the skill's `name`.
  * Directory URIs have no trailing slash; a child directory is
    reported with `mimeType: "inode/directory"`.

The Python fallback has no third-party dependencies, so the SHA-256
comes from `hashlib` and the YAML comes from the index the builder
already parsed.
"""

import base64
import hashlib
import os

import protocol

# The extension's own id.
SKILLS_EXTENSION_ID = 'io.modelcontextprotocol/skills'

# How long a client may treat a skills listing as fresh.
SKILLS_TTL_MS = 300_000

# How many skills one page of `skills/list` holds.
SKILLS_PAGE_SIZE = 100

# How many resources one page of `resources/list` holds.
#
# A page holds whole resources, never a file in pieces, so the page
# size is a page of files.
RESOURCES_PAGE_SIZE = 500

# The URI scheme this server serves skills under.
SKILL_SCHEME = 'skill://'

# The error the extension defines for an unknown URI: "invalid params".
INVALID_PARAMS = -32602


class SkillError(Exception):
    """An error the extension defines: an unknown URI, or a bad path."""

    def __init__(self, message, code=INVALID_PARAMS):
        super().__init__(message)
        self.code = code


def digest_of(data):
    """The SHA-256 of some bytes, as the extension writes it."""
    return hashlib.sha256(data).hexdigest()


def sorted_skills(index):
    """The served skills, in a stable order.

    The order is by served name, not by the index order. The index order
    is the order the library was scanned in, which changes when the
    library is re-scanned; a client that paged through the listing
    would see a different order for the same library. A cursor names
    the last skill it saw, so the order has to be stable for the cursor
    to mean anything.
    """
    return sorted(index['skills'], key=lambda s: s['skills']['name'])


def skill_entry(record):
    """The entry for a skill, in the shape the extension serves."""
    entry = record['skills']
    out = {
        'uri': entry['uri'],
        'frontmatter': entry['frontmatter'],
        'resources': entry['resources'],
    }
    if entry.get('name_override'):
        out['name_override'] = entry['name_override']
    if entry.get('description_truncated'):
        out['description_truncated'] = entry['description_truncated']
    if entry.get('problems'):
        out['problems'] = entry['problems']
    return out


def find_by_uri(index, uri):
    """The skill a URI names.

    The URI is `skill://<served-name>/<path>`, or `skill://<served-name>`
    for the skill's own directory. The name is the *served* name, which
    is not always the directory's name -- two skills in this library have
    a name that breaks the Agent Skills rules and are served under a
    conforming one. So the lookup goes through the index rather than
    through the filesystem, and a URI built from the directory name is
    not a URI this server issued.
    """
    if not isinstance(uri, str) or not uri.startswith(SKILL_SCHEME):
        return None
    rest = uri[len(SKILL_SCHEME):]
    slash = rest.find('/')
    name = rest if slash < 0 else rest[:slash]
    for record in index['skills']:
        if record['skills']['name'] == name:
            return record
    return None


def find_skill_md(index, uri):
    """The skill a `skills/get` URI names.

    `skills/get` takes the URI of a skill's `SKILL.md`, and only that.
    A URI that names the skill's directory, or one of its other files,
    is not a skill URI -- and a URI that climbs out of the skill with
    `..` is not a URI this server issued at all.

    The distinction matters because `skills/get` returns the *whole*
    skill: accepting `skill://x/../y` would answer with a skill the
    client did not name.
    """
    record = find_by_uri(index, uri)
    if record is None:
        return None
    if uri != record['skills']['uri']:
        return None
    return record


def file_path_in_skill(record, uri):
    """The path of a file inside a skill, relative to the skill's dir.

    `None` when the URI does not name a file in this skill -- a path
    that escapes the skill (`../`), a path to nothing, or a URI that
    names the skill itself with no file.
    """
    prefix = '%s%s/' % (SKILL_SCHEME, record['skills']['name'])
    if not uri.startswith(prefix):
        return None
    rel = uri[len(prefix):]
    if not rel:
        return None
    parts = rel.split('/')
    if any(p in ('..', '.', '') for p in parts):
        return None
    return rel


def read_skill_file(root, index, uri):
    """The file a `resources/read` URI names, with its bytes.

    The digest is checked against the manifest before the bytes are
    returned. That is the point of the manifest: a host verifies the
    bytes it got against the digest the server published, and the
    server verifying them first means a corrupted or swapped file is
    reported rather than served.

    Returns `(record, rel, data, mime, digest)`.
    """
    record = find_by_uri(index, uri)
    if record is None:
        raise SkillError('Unknown skill URI: %s' % uri)
    rel = file_path_in_skill(record, uri)
    if rel is None:
        raise SkillError('Unknown resource URI: %s' % uri)

    # The path is resolved against the skill's directory and then checked
    # to be inside it, so a URI can never reach a file outside the skill.
    directory = os.path.realpath(os.path.join(root, record['path']))
    abs_path = os.path.realpath(os.path.join(directory, rel))
    if abs_path != directory and not abs_path.startswith(directory + os.sep):
        raise SkillError('Unknown resource URI: %s' % uri)
    if not os.path.isfile(abs_path):
        raise SkillError('Unknown resource URI: %s' % uri)

    with open(abs_path, 'rb') as fh:
        data = fh.read()

    entry = None
    for f in record['bundle']['files']:
        if f['path'] == rel:
            entry = f
            break
    if entry is None or not entry.get('digest'):
        raise SkillError('No manifest entry for %s' % uri)
    digest = entry['digest']
    actual = 'sha256:%s' % digest_of(data)
    if actual != digest:
        raise SkillError(
            'Digest mismatch for %s: the manifest says %s, the file is %s'
            % (uri, digest, actual))
    return record, rel, data, entry.get('mime', 'application/octet-stream'), digest


def read_skill_directory(index, uri):
    """The children of a directory inside a skill.

    Only the direct children, as the specification requires. A child
    directory is reported with `mimeType: "inode/directory"` and no
    trailing slash on its URI.
    """
    record = find_by_uri(index, uri)
    if record is None:
        raise SkillError('Unknown skill URI: %s' % uri)
    prefix = '%s%s' % (SKILL_SCHEME, record['skills']['name'])
    if uri != prefix and not uri.startswith(prefix + '/'):
        raise SkillError('Unknown directory URI: %s' % uri)
    rel = '' if uri == prefix else uri[len(prefix) + 1:]
    if any(p in ('..', '.') for p in rel.split('/')):
        raise SkillError('Unknown directory URI: %s' % uri)

    # A URI that names a *file* is not a directory, and the
    # specification says a directory read of anything else is
    # `-32602`. The manifest is the tree, so the check is against it.
    if any(f['path'] == rel for f in record['bundle']['files']):
        raise SkillError('Not a directory: %s' % uri)

    # A directory is a prefix of the files in the manifest. The manifest
    # is the tree: a host may answer a directory query from it, and the
    # specification says a live directory result must not extend the
    # retained manifest.
    directory = (rel + '/') if rel else ''
    seen = {}
    for f in record['bundle']['files']:
        if directory and not f['path'].startswith(directory):
            continue
        rest = f['path'][len(directory):]
        if not rest:
            continue
        if '/' in rest:
            name = rest.split('/', 1)[0]
            if name not in seen:
                seen[name] = 'inode/directory'
        else:
            seen[rest] = f.get('mime', 'application/octet-stream')

    # A directory with no children is not a directory. Without this, a
    # URI for a path that does not exist would answer with an empty
    # listing -- which reads as "this directory is empty" rather than
    # "there is nothing here".
    if not seen:
        raise SkillError('Unknown directory URI: %s' % uri)

    return [
        {'uri': '%s/%s%s' % (prefix, directory, name), 'name': name, 'mimeType': mime}
        for name, mime in sorted(seen.items())
    ]


def list_skills(index, cursor=None):
    """One page of `skills/list`.

    The page holds whole skills, never parts of a manifest: a skill's
    `resources` are atomic, so the entry is either on the page or not.
    """
    all_skills = sorted_skills(index)
    start = 0

    if cursor:
        decoded = protocol.decode_cursor(cursor)
        if decoded and protocol.cursor_matches(decoded, 'skills/list'):
            after = decoded['after']
            for pos, record in enumerate(all_skills):
                if record['skills']['name'] == after:
                    start = pos + 1
                    break

    page = all_skills[start:start + SKILLS_PAGE_SIZE]
    out = {'skills': [skill_entry(s) for s in page]}
    if start + SKILLS_PAGE_SIZE < len(all_skills) and page:
        out['nextCursor'] = protocol.encode_cursor(
            page[-1]['skills']['name'], 'skills/list')
    return out


def all_resources(index):
    """Every resource the server serves, in a stable order.

    The `resources` capability is declared, so `resources/list` has to
    answer: a client that reads the capability and then calls the
    method would get `-32601` otherwise. The list is the skills in
    served-name order, and within a skill the files in manifest order --
    the same order the manifest itself lists them, so a client that has
    seen a manifest sees the same files again.

    The order has to be stable for the cursor to mean anything, so it
    is built from the sorted skills rather than from the index order.
    """
    out = []
    for record in sorted_skills(index):
        name = record['skills']['name']
        for f in record['bundle']['files']:
            out.append({
                'uri': f.get('uri') or ('%s%s/%s' % (SKILL_SCHEME, name, f['path'])),
                'name': f['path'].rsplit('/', 1)[-1],
                'mimeType': f.get('mime', 'application/octet-stream'),
                'size': f['bytes'],
            })
    return out


def list_resources(index, cursor=None):
    """One page of `resources/list`.

    The cursor names the last resource of the previous page. Resources
    are atomic -- a file is either on the page or not -- so the cursor
    can name one of them.
    """
    all_resources_list = all_resources(index)
    start = 0

    if cursor:
        decoded = protocol.decode_cursor(cursor)
        if decoded and protocol.cursor_matches(decoded, 'resources/list'):
            after = decoded['after']
            for pos, r in enumerate(all_resources_list):
                if r['uri'] == after:
                    start = pos + 1
                    break

    page = all_resources_list[start:start + RESOURCES_PAGE_SIZE]
    out = {'resources': page}
    if start + RESOURCES_PAGE_SIZE < len(all_resources_list) and page:
        out['nextCursor'] = protocol.encode_cursor(
            page[-1]['uri'], 'resources/list')
    return out


def is_textual(mime):
    """Is this MIME type text?

    Text is served as `text`, everything else as `blob`. A client reads
    `text` into the model's context; `blob` is base64 and is decoded by
    the client. Serving a PNG as `text` would corrupt it, and serving a
    markdown file as `blob` would make the client decode it needlessly.
    """
    return (mime.startswith('text/')
            or mime in ('application/json', 'application/yaml',
                        'application/xml', 'image/svg+xml'))


def contents_for(uri, data, mime):
    """The `contents` entry for a file."""
    if is_textual(mime):
        return {'uri': uri, 'mimeType': mime, 'text': data.decode('utf-8')}
    return {
        'uri': uri,
        'mimeType': mime,
        'blob': base64.b64encode(data).decode('ascii'),
    }
