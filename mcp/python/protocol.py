#!/usr/bin/env python3
"""The protocol revision this server speaks.

There are two revisions in play, and the server serves both:

  - `2025-11-25` is the revision the MCP SDK ships with, and the one
    every current client speaks. It stays the default.
  - `2026-07-28` is a breaking revision. It adds `server/discover`,
    which becomes mandatory; every result carries a `resultType`; list
    results carry `ttlMs` and `cacheScope`; and pagination is
    cursor-based rather than offset-based.

A client that asks for the newer revision gets the newer revision. A
client that asks for the older one -- or for something the server does
not know -- gets `2025-11-25`.

The older revision's output is byte-identical to what this server
produced before the newer revision was added. That matters: the
agreement gate compares the two implementations' raw payloads, and a
client that never asked for the new revision must not see fields it
has never heard of. So `resultType`, `ttlMs` and `cacheScope` are
added *only* when the client negotiated `2026-07-28`.

This is the mirror of `mcp/src/protocol.ts`. The two must agree
exactly: a client that talks to one server and then the other must not
see a different protocol.
"""

import base64
import json

# The revisions this server speaks, newest first.
SUPPORTED_PROTOCOL_VERSIONS = (
    '2026-07-28',
    '2025-11-25',
    '2025-06-18',
    '2025-03-26',
    '2024-11-05',
    '2024-10-07',
)

# The revision served when the client asks for one we do not know.
DEFAULT_PROTOCOL_VERSION = '2025-11-25'

# The revision with the breaking changes.
CURRENT_PROTOCOL_VERSION = '2026-07-28'


def negotiate(requested):
    """The revision to serve a client that asked for `requested`.

    An unknown request gets the default -- the oldest revision every
    client understands -- rather than the newest. Answering a client
    that asked for something we do not know with our *newest* revision
    would hand it fields it cannot read; answering with the default
    keeps the conversation going.
    """
    if requested and requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return DEFAULT_PROTOCOL_VERSION


def is_current(version):
    """Is this the revision with the breaking changes?

    Only `2026-07-28` qualifies. Everything else -- including the older
    revisions this server still serves -- gets the original output, so
    a client that never asked for the new revision never sees a field
    it has not heard of.
    """
    return version == CURRENT_PROTOCOL_VERSION


def result_type(version):
    """The `resultType` for a result under `version`.

    `2026-07-28` requires every result to say whether it is complete.
    The older revision says nothing, and the field is absent rather
    than set to `"complete"` -- a client reading the old revision must
    not find a field it does not know.
    """
    if not is_current(version):
        return {}
    return {'resultType': 'complete'}


def cache_fields(version, ttl_ms, scope):
    """The cache fields for a list result under `version`.

    `2026-07-28` requires `ttlMs` and `cacheScope` on list results.
    `ttlMs` is how long the client may reuse the answer; the library
    changes when somebody adds a skill, so the TTL is short -- it is a
    cache, not a snapshot.

    `cacheScope` says how widely the answer is valid: `"session"` means
    the same for every caller in this session, which is true of the
    library's structure but not of a search's ranking.
    """
    if not is_current(version):
        return {}
    return {'ttlMs': ttl_ms, 'cacheScope': scope}


def encode_cursor(after, query):
    """Encode an opaque pagination cursor.

    `2026-07-28` replaces the offset with a cursor: the client does not
    say "skip 20 results", it says "continue from here". The difference
    matters because the result order is not stable across calls -- a
    skill that is added, or a score that changes, shifts every result
    after it. An offset silently skips or repeats entries; a cursor that
    names *the last result the client saw* does not.

    So the cursor holds the last result's identity, not its position.
    The next page starts after the entry with that identity. If the
    entry is gone -- the skill was removed, or the query matches
    differently -- the cursor is honoured as best it can be: the page
    starts at the end, and the caller is told the list changed.

    The cursor is opaque: it is base64url of a small JSON object. The
    client is not meant to read it, and its shape is not a promise.
    """
    payload = json.dumps({'after': after, 'q': query}, separators=(',', ':'),
                         sort_keys=True)
    return base64.urlsafe_b64encode(payload.encode('utf-8')).decode('ascii').rstrip('=')


def decode_cursor(cursor):
    """Decode a cursor.

    A cursor that cannot be read is not an error the caller can fix --
    it is a cursor they should not have. The caller gets `None`, which
    means "start from the beginning", and the page is served from the
    top rather than failing the whole call.
    """
    if not cursor:
        return None
    try:
        padding = '=' * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(cursor + padding).decode('utf-8')
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        after = parsed.get('after')
        q = parsed.get('q')
        if not isinstance(after, str) or not isinstance(q, str):
            return None
        return {'after': after, 'q': q}
    except Exception:
        return None


def cursor_matches(cursor, query):
    """Does a cursor belong to this query?

    A cursor issued for one query must not silently paginate another.
    The client would get results from a query it did not ask for, and
    the mismatch is invisible: the ids are valid, the results look
    reasonable, and the query string in the result disagrees with the
    query the client sent.
    """
    if not cursor:
        return True
    return cursor['q'] == query
