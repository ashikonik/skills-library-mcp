/**
 * The protocol revision tests.
 *
 * The revision decides what a client sees. A client that asked for the
 * older revision must not find a field it has never heard of; a client
 * that asked for the newer one must find every field the newer revision
 * requires. Both mistakes are invisible to a client that does not know
 * the rules, so they are pinned here.
 *
 * This is the TypeScript half. `mcp/tests/test_protocol_parity.py` pins
 * the Python half and checks that the two agree.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  SUPPORTED_PROTOCOL_VERSIONS,
  DEFAULT_PROTOCOL_VERSION,
  CURRENT_PROTOCOL_VERSION,
  negotiate,
  isCurrent,
  resultType,
  cacheFields,
  encodeCursor,
  decodeCursor,
  cursorMatches,
} from '../protocol.js';

test('the supported versions are listed newest first', () => {
  assert.equal(SUPPORTED_PROTOCOL_VERSIONS[0], CURRENT_PROTOCOL_VERSION);
  assert.equal(SUPPORTED_PROTOCOL_VERSIONS[1], DEFAULT_PROTOCOL_VERSION);
});

test('the default is the revision every client understands', () => {
  assert.equal(DEFAULT_PROTOCOL_VERSION, '2025-11-25');
  assert.ok(SUPPORTED_PROTOCOL_VERSIONS.includes(DEFAULT_PROTOCOL_VERSION));
});

test('a supported request is served as itself', () => {
  for (const v of SUPPORTED_PROTOCOL_VERSIONS) {
    assert.equal(negotiate(v), v);
  }
});

test('an unknown request gets the default, not the newest', () => {
  // The newest revision would hand the client fields it cannot read.
  assert.equal(negotiate('2999-01-01'), DEFAULT_PROTOCOL_VERSION);
  assert.equal(negotiate('2025-11-26'), DEFAULT_PROTOCOL_VERSION);
  assert.equal(negotiate(''), DEFAULT_PROTOCOL_VERSION);
  assert.equal(negotiate(undefined), DEFAULT_PROTOCOL_VERSION);
  assert.equal(negotiate(null), DEFAULT_PROTOCOL_VERSION);
});

test('only the current revision counts as current', () => {
  assert.equal(isCurrent(CURRENT_PROTOCOL_VERSION), true);
  assert.equal(isCurrent(DEFAULT_PROTOCOL_VERSION), false);
  assert.equal(isCurrent('2024-11-05'), false);
  assert.equal(isCurrent(''), false);
});

test('the older revision gets no resultType at all', () => {
  // Not `resultType: "complete"` -- absent. A client reading the older
  // revision must not find a field it does not know.
  for (const v of SUPPORTED_PROTOCOL_VERSIONS) {
    if (v === CURRENT_PROTOCOL_VERSION) continue;
    assert.deepEqual(resultType(v), {});
    assert.equal('resultType' in resultType(v), false);
  }
});

test('the current revision gets resultType', () => {
  assert.deepEqual(resultType(CURRENT_PROTOCOL_VERSION), { resultType: 'complete' });
});

test('the older revision gets no cache fields at all', () => {
  for (const v of SUPPORTED_PROTOCOL_VERSIONS) {
    if (v === CURRENT_PROTOCOL_VERSION) continue;
    assert.deepEqual(cacheFields(v, 60_000, 'public'), {});
    assert.equal('ttlMs' in cacheFields(v, 60_000, 'public'), false);
    assert.equal('cacheScope' in cacheFields(v, 60_000, 'public'), false);
  }
});

test('the current revision gets ttlMs and cacheScope', () => {
  assert.deepEqual(cacheFields(CURRENT_PROTOCOL_VERSION, 60_000, 'public'), {
    ttlMs: 60_000,
    cacheScope: 'public',
  });
  assert.deepEqual(cacheFields(CURRENT_PROTOCOL_VERSION, 0, 'private'), {
    ttlMs: 0,
    cacheScope: 'private',
  });
});

test('the cache scope is one the spec defines', () => {
  // The spec allows exactly two: "public" and "private". A third value
  // would be a scope no client understands, and the client would have to
  // guess what it means.
  for (const scope of ['public', 'private'] as const) {
    const fields = cacheFields(CURRENT_PROTOCOL_VERSION, 60_000, scope);
    assert.equal(fields.cacheScope, scope);
  }
});

test('the revisions are distinct strings, not an ordering accident', () => {
  // A duplicate in the list would make `negotiate` ambiguous about
  // which revision it agreed to, and the list is what
  // `server/discover` reports.
  assert.equal(new Set(SUPPORTED_PROTOCOL_VERSIONS).size, SUPPORTED_PROTOCOL_VERSIONS.length);
});

test('a cursor round-trips', () => {
  const c = encodeCursor('skill:tdd-workflow', 'write tests');
  assert.deepEqual(decodeCursor(c), { after: 'skill:tdd-workflow', q: 'write tests' });
});

test('a cursor is opaque -- it does not read as the entry it names', () => {
  const c = encodeCursor('skill:tdd-workflow', 'write tests');
  assert.ok(!c.includes('tdd-workflow'), c);
  assert.ok(!c.includes('skill:'), c);
});

test('a cursor is url-safe', () => {
  // The cursor travels in a query string and in a JSON-RPC parameter.
  // `+`, `/` and `=` would have to be escaped, and a client that
  // forgot to escape them would send a broken cursor.
  const c = encodeCursor('skill:some/entry+with?chars', 'a query? with & chars');
  assert.match(c, /^[A-Za-z0-9_-]+$/);
  assert.deepEqual(decodeCursor(c), {
    after: 'skill:some/entry+with?chars',
    q: 'a query? with & chars',
  });
});

test('an unreadable cursor is ignored, not an error', () => {
  // The caller cannot fix a cursor they should not have. Failing the
  // whole call would be unkind; starting from the top is recoverable.
  assert.equal(decodeCursor('not base64 at all !!!'), undefined);
  assert.equal(decodeCursor(''), undefined);
  assert.equal(decodeCursor(undefined), undefined);
  assert.equal(decodeCursor(null), undefined);
  // Valid base64url, but not the shape a cursor has.
  assert.equal(decodeCursor(Buffer.from('{"nope":1}', 'utf-8').toString('base64url')), undefined);
  assert.equal(decodeCursor(Buffer.from('not json', 'utf-8').toString('base64url')), undefined);
});

test('a cursor is bound to its query', () => {
  // A cursor issued for one query must not silently paginate another:
  // the client would get results from a query it did not ask for.
  const c = decodeCursor(encodeCursor('skill:x', 'query one'));
  assert.equal(cursorMatches(c, 'query one'), true);
  assert.equal(cursorMatches(c, 'query two'), false);
  assert.equal(cursorMatches(undefined, 'anything'), true);
});
