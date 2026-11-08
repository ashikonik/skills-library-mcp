// Drives the TypeScript Skills extension, for the agreement test.
//
// The SDK's own `Client` cannot be used here: it always asks for
// `LATEST_PROTOCOL_VERSION` and refuses any revision it does not
// know -- and `2026-07-28` is exactly the revision the SDK does not
// know. So the handshake is driven raw over the transport, the way a
// real client that speaks the newer revision would.
//
// Writes a JSON object on stdout: the answers to each extension call.
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { cpSync, mkdtempSync, appendFileSync, rmSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { loadIndex, libraryRoot } from '../dist/index-loader.js';
import { createServer } from '../dist/server.js';

// A tampered copy of one skill, so the digest check is exercised.
//
// The copy holds a skill whose `SKILL.md` has one byte appended to it.
// The index still describes the original, so the file on disk no
// longer matches the manifest -- and the server must refuse to serve
// it. Without this, removing the digest check changes nothing
// observable and the gate would pass on broken code.
//
// The tampered skill is deliberately *not* one of the skills the
// parity comparison reads. The Python side serves the real tree, so
// if the tampered skill were also in the parity set, the two sides
// would disagree about it for a reason that has nothing to do with
// parity -- and the comparison would be meaningless.
//
// The directory on disk and the served name are not always the same:
// `Zotero` is served as `zotero`. The index points at the *directory*,
// so the copy has to land under the directory's name for the index
// entry to resolve; the URI uses the served name.
const TAMPERED_DIR = 'Zotero';
const TAMPERED_SKILL = 'zotero';
const TAMPERED_URI = `skill://${TAMPERED_SKILL}/SKILL.md`;

const realRoot = libraryRoot();
const tamperedRoot = mkdtempSync(join(tmpdir(), 'skills-tamper-'));
cpSync(join(realRoot, 'skills', TAMPERED_DIR),
       join(tamperedRoot, 'skills', TAMPERED_DIR), { recursive: true });
appendFileSync(join(tamperedRoot, 'skills', TAMPERED_DIR, 'SKILL.md'),
               '\n<!-- tampered -->\n');
// The index is read from the real library; only the *files* are
// tampered with.
cpSync(join(realRoot, 'mcp', 'data', 'index.json'),
       join(tamperedRoot, 'mcp', 'data', 'index.json'), { recursive: true });
// The rest of the library is the real one: only the tampered skill's
// directory is taken from the copy.
for (const entry of readdirSync(join(realRoot, 'skills'))) {
  if (entry === TAMPERED_DIR) continue;
  cpSync(join(realRoot, 'skills', entry),
         join(tamperedRoot, 'skills', entry), { recursive: true, dereference: true });
}
process.env.SKILLS_LIBRARY_ROOT = tamperedRoot;

const server = createServer({ index: loadIndex() });

const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
await server.connect(serverTransport);

// A raw JSON-RPC peer: send the handshake, then the calls.
let nextId = 1;
const pending = new Map();

await clientTransport.start();

clientTransport.onmessage = (message) => {
  if (message.id !== undefined && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
};

function send(method, params) {
  const id = nextId++;
  const promise = new Promise((resolve) => pending.set(id, resolve));
  clientTransport.send({ jsonrpc: '2.0', id, method, params });
  return promise;
}

const init = await send('initialize', {
  protocolVersion: '2026-07-28',
  capabilities: {},
  clientInfo: { name: 'agreement-test', version: '1.0.0' },
});
if (init.error) {
  process.stderr.write('initialize failed: %s\n', JSON.stringify(init.error));
  process.exit(1);
}
if (init.result.protocolVersion !== '2026-07-28') {
  process.stderr.write(
    'the server did not negotiate 2026-07-28: %s\n', init.result.protocolVersion,
  );
  process.exit(1);
}

await clientTransport.send({
  jsonrpc: '2.0',
  method: 'notifications/initialized',
});

// Each call is answered or refused; both are recorded, because the
// agreement gate has to compare the refusals too.
async function call(method, params) {
  const res = await send(method, params);
  if (res.error) {
    return { error: { code: res.error.code, message: res.error.message } };
  }
  return { result: res.result };
}

const list = await call('skills/list', {});
const cursor = list.result?.nextCursor ?? null;
const page2 = cursor ? await call('skills/list', { cursor }) : { result: { skills: [] } };

// The URIs the comparison uses. They are fixed rather than taken from
// the listing, so the two implementations are asked about the *same*
// skill: a comparison of two answers about two different skills would
// always differ, and would teach nothing.
const FIRST = 'skill://access/SKILL.md';
const SECOND = 'skill://accessibility/SKILL.md';
const ROOT = 'skill://access';

// A skill with supporting files, so the manifest and the directory
// reading have something to talk about.
const withFiles = (list.result?.skills ?? []).find((s) => s.resources.length > 1);
const bundleUri = withFiles?.uri ?? null;
const childUri = withFiles?.resources?.find((r) => !r.uri.endsWith('SKILL.md'))?.uri ?? null;
const dirUri = childUri ? childUri.replace(/\/[^/]+$/, '') : null;

// Every directory in every served skill, read and summarised.
//
// The server declares `directoryRead: true`, which is a promise that
// the whole namespace is walkable. The sweep checks that promise
// against the TypeScript side, and the Python side runs the same
// sweep, so the two are compared on the same set.
//
// The summary is a digest of the whole tree: every directory, its
// children, and the mime type of each child. A compact fingerprint
// rather than 2,918 separate comparisons -- but one that changes if
// any directory anywhere is wrong.
const dirSweep = await sweepDirectories();

/**
 * Read every directory in every served skill and fingerprint the result.
 *
 * The fingerprint is the SHA-256 of a canonical text: one line per
 * directory, listing its children with their mime types. Two
 * implementations that answer the same way produce the same
 * fingerprint; one that differs anywhere produces a different one.
 */
async function sweepDirectories() {
  const index = loadIndex();
  const lines = [];
  let count = 0;
  let failed = 0;

  for (const record of index.skills) {
    const entry = record.skills;
    const prefix = `skill://${entry.name}`;
    const files = (record.bundle?.files ?? []).map((f) => f.path);

    const directories = new Set(['']);
    for (const path of files) {
      const parts = path.split('/');
      for (let depth = 1; depth < parts.length; depth += 1) {
        directories.add(parts.slice(0, depth).join('/'));
      }
    }

    for (const rel of [...directories].sort()) {
      const uri = rel === '' ? prefix : `${prefix}/${rel}`;
      const answer = await call('resources/directory/read', { uri });
      count += 1;
      if (answer.error) {
        failed += 1;
        lines.push(`${uri}\tERROR ${answer.error.code}`);
        continue;
      }
      const children = (answer.result?.resources ?? [])
        .map((r) => `${r.name}=${r.mimeType}`)
        .sort()
        .join(',');
      lines.push(`${uri}\t${children}`);
    }
  }

  const digest = createHash('sha256').update(lines.join('\n')).digest('hex');
  return { count, failed, digest };
}

const resources = await call('resources/list', {});
const resourceCursor = resources.result?.nextCursor ?? null;
const resourcesPage2 = resourceCursor
  ? await call('resources/list', { cursor: resourceCursor })
  : { result: { resources: [] } };

const out = {
  list: list.result ?? null,
  listError: list.error ?? null,
  cursor,
  page2Names: (page2.result?.skills ?? []).map((s) => s.uri),
  resources: resources.result?.resources ?? null,
  resourcesError: resources.error ?? null,
  resourceCursor,
  resourcesPage2: (resourcesPage2.result?.resources ?? []).map((r) => r.uri),
  get: await call('skills/get', { uri: FIRST }),
  getSecond: await call('skills/get', { uri: SECOND }),
  getUnknown: await call('skills/get', { uri: 'skill://no-such-skill/SKILL.md' }),
  getDirectoryUri: await call('skills/get', { uri: ROOT }),
  getTraversal: await call('skills/get', { uri: 'skill://access/../secrets' }),
  read: await call('resources/read', { uri: FIRST }),
  readChild: childUri ? await call('resources/read', { uri: childUri }) : null,
  readUnknown: await call('resources/read', { uri: 'skill://access/nope.md' }),
  readTraversal: await call(
    'resources/read',
    { uri: 'skill://access/../../.library_data.json' },
  ),
  dirRoot: await call('resources/directory/read', { uri: ROOT }),
  dirChild: dirUri ? await call('resources/directory/read', { uri: dirUri }) : null,
  dirUnknown: await call('resources/directory/read', { uri: 'skill://access/nope' }),
  dirFile: await call('resources/directory/read', { uri: FIRST }),
  // The fingerprint of every directory in every skill.
  dirSweep,
  // A skill with supporting files, for the manifest comparison.
  bundle: withFiles
    ? { uri: withFiles.uri, resources: withFiles.resources }
    : null,
  // A file that does *not* match its manifest digest. The server must
  // refuse it: a manifest the server does not verify is a manifest the
  // client has to trust blindly, which is the thing the manifest
  // exists to avoid.
  //
  // The tampering is done by copying the library's first skill into a
  // temporary tree and appending a byte to its `SKILL.md`. The server
  // is started against that tree, so the index still describes the
  // original while the file on disk has changed -- exactly the
  // situation the digest is there to catch.
  tampered: await call('resources/read', { uri: TAMPERED_URI }),
};

process.stdout.write(JSON.stringify(out));

await server.close();
rmSync(tamperedRoot, { recursive: true, force: true });
