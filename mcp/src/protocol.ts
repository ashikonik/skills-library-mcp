/**
 * The protocol revision this server speaks.
 *
 * There are two revisions in play, and the server serves both:
 *
 *  - `2025-11-25` is the revision the MCP SDK ships with, and the one
 *    every current client speaks. It stays the default.
 *  - `2026-07-28` is a breaking revision. It adds `server/discover`,
 *    which becomes mandatory; every result carries a `resultType`; list
 *    results carry `ttlMs` and `cacheScope`; and pagination is
 *    cursor-based rather than offset-based.
 *
 * A client that asks for the newer revision gets the newer revision.
 * A client that asks for the older one -- or for something the server
 * does not know -- gets `2025-11-25`.
 *
 * The older revision's output is byte-identical to what this server
 * produced before the newer revision was added. That matters: the
 * agreement gate compares the two implementations' raw payloads, and a
 * client that never asked for the new revision must not see fields it
 * has never heard of. So `resultType`, `ttlMs` and `cacheScope` are
 * added *only* when the client negotiated `2026-07-28`.
 *
 * The SDK does not know about `2026-07-28`: its own list of supported
 * versions stops at `2025-11-25`, and a client asking for the newer
 * revision would silently be answered with the older one. The
 * `initialize` handler is therefore overridden -- see
 * `mcp/src/server.ts`.
 */

/** The revisions this server speaks, newest first. */
export const SUPPORTED_PROTOCOL_VERSIONS: readonly string[] = [
  '2026-07-28',
  '2025-11-25',
  '2025-06-18',
  '2025-03-26',
  '2024-11-05',
  '2024-10-07',
];

/** The revision served when the client asks for one we do not know. */
export const DEFAULT_PROTOCOL_VERSION = '2025-11-25';

/** The revision with the breaking changes. */
export const CURRENT_PROTOCOL_VERSION = '2026-07-28';

/**
 * The revision to serve a client that asked for `requested`.
 *
 * An unknown request gets the default -- the oldest revision every
 * client understands -- rather than the newest. Answering a client
 * that asked for something we do not know with our *newest* revision
 * would hand it fields it cannot read; answering with the default
 * keeps the conversation going.
 */
export function negotiate(requested: string | undefined | null): string {
  if (requested && SUPPORTED_PROTOCOL_VERSIONS.includes(requested)) {
    return requested;
  }
  return DEFAULT_PROTOCOL_VERSION;
}

/**
 * Is this the revision with the breaking changes?
 *
 * Only `2026-07-28` qualifies. Everything else -- including the older
 * revisions this server still serves -- gets the original output, so
 * a client that never asked for the new revision never sees a field
 * it has not heard of.
 */
export function isCurrent(version: string): boolean {
  return version === CURRENT_PROTOCOL_VERSION;
}

/**
 * The `resultType` for a result under `version`.
 *
 * `2026-07-28` requires every result to say whether it is complete.
 * The older revision says nothing, and the field is absent rather
 * than set to `"complete"` -- a client reading the old revision must
 * not find a field it does not know.
 */
export function resultType(version: string): { resultType?: string } {
  if (!isCurrent(version)) return {};
  return { resultType: 'complete' };
}

/**
 * The cache fields for a list result under `version`.
 *
 * `2026-07-28` requires `ttlMs` and `cacheScope` on list results.
 * `ttlMs` is how long the client may reuse the answer; the library
 * changes when somebody adds a skill, so the TTL is short -- it is a
 * cache, not a snapshot.
 *
 * `cacheScope` says who may reuse the answer: `"public"` means it is
 * the same for every caller and a shared cache may serve it to anyone;
 * `"private"` means it depends on the caller's own context and a
 * cached copy must not cross authorization boundaries.
 *
 * The library's listings are public -- the catalogue is the same for
 * everyone, and the same for every page of it. A filtered or
 * caller-specific answer would be private.
 */
export type CacheScope = 'public' | 'private';

export function cacheFields(
  version: string,
  ttlMs: number,
  scope: CacheScope,
): { ttlMs?: number; cacheScope?: string } {
  if (!isCurrent(version)) return {};
  return { ttlMs, cacheScope: scope };
}

/**
 * The opaque pagination cursor.
 *
 * `2026-07-28` replaces the offset with a cursor: the client does not
 * say "skip 20 results", it says "continue from here". The difference
 * matters because the result order is not stable across calls -- a
 * skill that is added, or a score that changes, shifts every result
 * after it. An offset silently skips or repeats entries; a cursor that
 * names *the last result the client saw* does not.
 *
 * So the cursor holds the last result's identity, not its position.
 * The next page starts after the entry with that identity. If the
 * entry is gone -- the skill was removed, or the query matches
 * differently -- the cursor is honoured as best it can be: the page
 * starts at the end, and the caller is told the list changed.
 *
 * The cursor is opaque: it is base64url of a small JSON object. The
 * client is not meant to read it, and its shape is not a promise.
 */
export interface Cursor {
  /** The id of the last entry on the previous page. */
  after: string;
  /** The query the cursor was issued for. */
  q: string;
}

/** Encode a cursor. */
export function encodeCursor(after: string, query: string): string {
  // The keys are sorted so the byte string does not depend on the order
  // the properties happen to be written in. The Python mirror sorts its
  // keys too, and a cursor the two implementations disagree about
  // would not cross between servers.
  const payload = JSON.stringify({ after, q: query } satisfies Cursor);
  return Buffer.from(payload, 'utf-8').toString('base64url');
}

/**
 * Decode a cursor.
 *
 * A cursor that cannot be read is not an error the caller can fix --
 * it is a cursor they should not have. The caller gets `undefined`,
 * which means "start from the beginning", and the page is served from
 * the top rather than failing the whole call.
 */
export function decodeCursor(cursor: string | undefined | null): Cursor | undefined {
  if (!cursor) return undefined;
  try {
    const raw = Buffer.from(cursor, 'base64url').toString('utf-8');
    const parsed = JSON.parse(raw) as Partial<Cursor>;
    if (typeof parsed.after !== 'string' || typeof parsed.q !== 'string') {
      return undefined;
    }
    return { after: parsed.after, q: parsed.q };
  } catch {
    return undefined;
  }
}

/**
 * Does a cursor belong to this query?
 *
 * A cursor issued for one query must not silently paginate another.
 * The client would get results from a query it did not ask for, and
 * the mismatch is invisible: the ids are valid, the results look
 * reasonable, and the query string in the result disagrees with the
 * query the client sent.
 */
export function cursorMatches(cursor: Cursor | undefined, query: string): boolean {
  if (!cursor) return true;
  return cursor.q === query;
}
