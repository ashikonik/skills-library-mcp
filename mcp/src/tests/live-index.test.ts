/**
 * The live-index tests.
 *
 * The index is a file on disk, and a server can outlive the build
 * that produced it. Before this, the server read the index once at
 * startup and answered from that copy forever: `get_agent` reported
 * "not found" for an agent that was on disk, and `search_library`
 * could not find what the caller had just added.
 *
 * The failure was quiet. Nothing errored -- the server simply
 * described a library smaller than the library.
 *
 * These tests pin the fix: a server started against an index, then
 * shown a *different* index on disk, must answer from the new one --
 * without a restart, and without the caller being told to restart.
 */
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, copyFileSync, utimesSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { loadIndex, indexPath } from '../index-loader.js';
import { createServer } from '../server.js';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';

let server: McpServer;
let client: Client;
let dir: string;
let livePath: string;

/** The real index, copied somewhere we may modify it. */
let baseIndex: ReturnType<typeof loadIndex>;

before(async () => {
  baseIndex = loadIndex();
  dir = mkdtempSync(join(tmpdir(), 'live-index-'));
  livePath = join(dir, 'index.json');
  copyFileSync(indexPath(), livePath);

  server = createServer({ index: baseIndex, indexPath: livePath });
  client = new Client({ name: 'live-index-test', version: '1.0.0' });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([
    server.connect(serverTransport),
    client.connect(clientTransport),
  ]);
});

after(async () => {
  await client?.close();
  await server?.close();
});

/** Call a tool and return the parsed result. */
async function call(name: string, args: Record<string, unknown> = {}) {
  const res = (await client.callTool({ name, arguments: args })) as any;
  const text = (res?.content ?? [])
    .filter((c: any) => c.type === 'text')
    .map((c: any) => c.text)
    .join('\n');
  try {
    return { ...res, payload: JSON.parse(text) };
  } catch {
    return { ...res, payload: null, text };
  }
}

/**
 * Write a new index to the live path, with one agent added.
 *
 * The mtime is bumped forward explicitly: on a fast filesystem two
 * writes can land in the same millisecond, and a fingerprint that
 * only compared mtime would miss the change. The size differs too,
 * because the agent adds bytes.
 */
function writeIndexWithExtraAgent(extraAgent: string): void {
  const next = JSON.parse(JSON.stringify(baseIndex)) as any;
  // The entry has to be complete: the search engine reads `tokens`
  // from every entry, and an entry without them breaks the index --
  // which would make this test measure a malformed fixture rather
  // than the reload.
  const tokens = {
    name: [extraAgent],
    name_bigrams: [],
    desc: ['synthetic', 'agent', 'live', 'index'],
  };
  next.agents = [
    ...next.agents,
    {
      id: `agent:${extraAgent}`,
      kind: 'agent',
      name: extraAgent,
      desc: 'A synthetic agent used by the live-index test.',
      desc_source: 'yaml',
      domain: '',
      ensemble: '',
      tier: 1,
      path: `agents/${extraAgent}.md`,
      abs_path: `agents/${extraAgent}.md`,
      bundle: {
        file_count: 0, total_bytes: 0,
        refs_total: 0, refs_resolved: 0, refs_dangling: 0,
        files: [],
      },
      copies: 0,
      provenance: {
        container: 'this-library', license: 'Apache-2.0',
        license_source: 'license file', owner: 'test',
        reason: '', repository: null, url: null, verdict: 'redistributable',
      },
      frontmatter: { name: extraAgent, description: 'synthetic', tools: [], raw_keys: [] },
      tokens,
    },
  ];
  next.counts = { ...next.counts, agents: next.agents.length };
  writeFileSync(livePath, JSON.stringify(next));
  const future = new Date(Date.now() + 5000);
  utimesSync(livePath, future, future);
}

test('a server started against an index answers from the index on disk', async () => {
  const res = await call('search_library', { query: 'synthetic live index agent' });
  assert.equal(res.isError, undefined);
  assert.ok(Array.isArray(res.payload?.results));
});

test('an agent added to the index file after startup becomes findable', async () => {
  const AGENT = 'live-index-synthetic-agent';
  writeIndexWithExtraAgent(AGENT);

  const search = await call('search_library', {
    query: 'synthetic live index agent',
    kind: 'agent',
  });
  const ids = (search.payload?.results ?? []).map((r: any) => r.id);
  assert.ok(
    ids.includes(`agent:${AGENT}`),
    `the agent added after startup should be findable; got ${JSON.stringify(ids)}`,
  );
});

test('get_agent finds an agent that was added after startup', async () => {
  const AGENT = 'live-index-synthetic-agent';
  const res = await call('get_agent', { id: AGENT });
  assert.equal(res.isError, undefined, `get_agent should not error: ${res.text}`);
  assert.equal(res.payload?.name, AGENT);
});

test('the tool descriptions quote the current count, not the startup count', async () => {
  const tools = (await client.listTools()) as any;
  const search = tools.tools.find((t: any) => t.name === 'search_library');
  const description = search?.description ?? '';
  const m = description.match(/Covers all (\d+) skills and (\d+) agents\./);
  assert.ok(m, `the description should state the counts: ${description}`);
  assert.equal(Number(m![1]), baseIndex.skills.length);
  assert.equal(
    Number(m![2]),
    baseIndex.agents.length + 1,
    'the agent count should have moved with the index',
  );
});

test('a missing agent still reports not found', async () => {
  const res = await call('get_agent', { id: 'no-such-agent-anywhere' });
  assert.equal(res.isError, true);
  assert.match(res.text, /not found/);
});

test('a malformed index is reported, not thrown at every tool', async () => {
  // An index written halfway -- or one with a malformed entry -- must
  // not break every tool. The previous index stays in service and the
  // error is reported, because a server that answers nothing is worse
  // than one that answers from the last good index.
  const good = readFileSync(livePath, 'utf-8');
  const broken = JSON.parse(good) as any;
  // An entry the search engine cannot build over: no `tokens`.
  broken.agents = [
    ...broken.agents,
    {
      id: 'agent:malformed', kind: 'agent', name: 'malformed',
      desc: 'a malformed entry', tier: 1, path: 'agents/malformed.md',
      frontmatter: { name: 'malformed', description: 'x', tools: [], raw_keys: [] },
    },
  ];
  writeFileSync(livePath, JSON.stringify(broken));
  const future = new Date(Date.now() + 10_000);
  utimesSync(livePath, future, future);

  const res = await call('get_agent', { id: 'no-such-agent-anywhere' });
  // The call must come back, not throw. Either the previous index is
  // still in service (the not-found error) or the reload failed and
  // the error says so -- but it must be an answer, not a crash.
  assert.ok(res.isError !== undefined || res.payload !== null);
  assert.match(res.text, /not found|could not be reloaded/);

  // Put the good index back, so the other tests are unaffected.
  writeFileSync(livePath, good);
  const later = new Date(Date.now() + 20_000);
  utimesSync(livePath, later, later);
});
