/**
 * The tool surface tests.
 *
 * Every tool this server publishes is called here, by name, through the
 * real SDK client -- the same path a client takes. That is the point:
 * a tool that is registered but never called is a tool nobody has
 * checked, and the failure it hides is exactly the kind that only
 * shows up in someone else's harness.
 *
 * The install and uninstall tools are called as *dry runs*. `apply`
 * defaults to false, so they plan and report without writing: this
 * file must never touch a real `~/.puku-cli`.
 *
 * This is the TypeScript half. `mcp/tests/test_agreement.py` pins the
 * Python half and checks that the two agree.
 */
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { loadIndex } from '../index-loader.js';
import { createServer } from '../server.js';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';

let server: McpServer;
let client: Client;

/** The ten tools this server publishes, in registration order. */
const TOOLS = [
  'search_library',
  'get_skill',
  'get_agent',
  'get_skill_bundle',
  'list_library',
  'install_skills',
  'install_agents',
  'uninstall_skills',
  'uninstall_agents',
  'policy_get',
] as const;

/** A skill and an agent that both exist in the library. */
const SKILL_ID = 'skill:tdd-workflow';
const AGENT_ID = 'agent:code-reviewer';

before(async () => {
  server = createServer({ index: loadIndex() });
  client = new Client({ name: 'tools-test', version: '1.0.0' });
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

/** Call a tool and return the raw result. */
async function call(name: string, args: Record<string, unknown> = {}) {
  return (await client.callTool({ name, arguments: args })) as any;
}

/** The text of a tool result, which is where the errors live. */
function textOf(result: any): string {
  return (result?.content ?? [])
    .filter((c: any) => c.type === 'text')
    .map((c: any) => c.text)
    .join('\n');
}

test('the server publishes exactly the ten tools it claims to', async () => {
  const { tools } = await client.listTools();
  assert.deepEqual(tools.map((t) => t.name), [...TOOLS]);
});

test('every tool carries a title and a description', async () => {
  const { tools } = await client.listTools();
  for (const t of tools) {
    assert.ok(t.title, `${t.name} has no title`);
    assert.ok(
      t.description && t.description.length > 20,
      `${t.name} has no description`,
    );
  }
});

test('search_library ranks the library and names what it matched on', async () => {
  const result = await call('search_library', { query: 'write a REST API', limit: 3 });
  assert.ok(!result.isError, textOf(result));
  const payload = result.structuredContent;
  assert.equal(typeof payload.total_matched, 'number');
  assert.ok(payload.results.length > 0, 'a query like this matches something');
  assert.ok(payload.results.length <= 3, 'the limit is honoured');
  assert.ok(payload.results[0].id, 'a result names the entry it found');
  assert.ok(payload.results[0].name, 'a result names the entry');
});

test('search_library refuses an empty query rather than returning everything', async () => {
  const result = await call('search_library', { query: '' });
  assert.ok(result.isError, 'an empty query is refused');
});

test('get_skill returns one skill in full', async () => {
  const result = await call('get_skill', { id: SKILL_ID });
  assert.ok(!result.isError, textOf(result));
  const payload = result.structuredContent;
  assert.equal(payload.name, 'tdd-workflow');
  assert.ok(payload.body && payload.body.includes('---'), 'the frontmatter is there');
});

test('get_skill says so when the skill does not exist', async () => {
  const result = await call('get_skill', { id: 'skill:no-such-skill-at-all' });
  assert.ok(result.isError, 'a missing skill is an error');
  assert.match(textOf(result), /not found/i);
});

test('get_agent returns one agent with its tool allow-list', async () => {
  const result = await call('get_agent', { id: AGENT_ID });
  assert.ok(!result.isError, textOf(result));
  const payload = result.structuredContent;
  assert.ok(payload.body, 'the agent body is there');
  // The allow-list is part of the agent's frontmatter, which the tool
  // returns parsed -- not a field of its own.
  assert.ok(payload.frontmatter, 'the frontmatter is there');
  assert.ok(payload.frontmatter.tools, 'the agent declares its tools');
  assert.ok(Array.isArray(payload.frontmatter.tools), 'the tools are a list');
  assert.equal(payload.frontmatter.name, 'code-reviewer');
});

test('get_skill_bundle returns the manifest, and the files when asked', async () => {
  const manifest = await call('get_skill_bundle', { id: SKILL_ID });
  assert.ok(!manifest.isError, textOf(manifest));
  assert.ok(Array.isArray(manifest.structuredContent.files));

  const files = await call('get_skill_bundle', { id: SKILL_ID, files: ['SKILL.md'] });
  assert.ok(!files.isError, textOf(files));
  assert.ok(files.structuredContent.files.length >= 1);
});

test('list_library reports each section', async () => {
  // `list_library` answers in text, not in a structured payload: each
  // section is a different shape, and the caller reads it as JSON.
  for (const section of ['domains', 'tiers', 'packs', 'tasks', 'stats', 'provenance']) {
    const result = await call('list_library', { section });
    assert.ok(!result.isError, `${section}: ${textOf(result)}`);
    const text = textOf(result);
    assert.ok(text.length > 0, `${section} says nothing`);
    // Every section is JSON, so the caller can parse it rather than
    // scrape it.
    JSON.parse(text);
  }
});

test('install_skills plans without writing', async () => {
  const result = await call('install_skills', {
    harness: 'puku-cli',
    ids: [SKILL_ID],
  });
  assert.ok(!result.isError, textOf(result));
  const payload = result.structuredContent;
  assert.equal(payload.apply, false, 'apply is false -- this is a dry run');
  assert.match(payload.note, /Dry run/);
  assert.equal(payload.written, 0, 'a dry run writes nothing');
});

test('install_agents plans without writing', async () => {
  const result = await call('install_agents', {
    harness: 'claude-code',
    ids: [AGENT_ID],
  });
  assert.ok(!result.isError, textOf(result));
  assert.equal(result.structuredContent.apply, false);
  assert.equal(result.structuredContent.written, 0);
});

test('uninstall_skills plans without writing', async () => {
  const result = await call('uninstall_skills', {
    harness: 'puku-cli',
    names: ['tdd-workflow'],
  });
  assert.ok(!result.isError, textOf(result));
  assert.equal(result.structuredContent.apply, false);
});

test('uninstall_agents plans without writing', async () => {
  const result = await call('uninstall_agents', {
    harness: 'claude-code',
    names: ['code-reviewer'],
  });
  assert.ok(!result.isError, textOf(result));
  assert.equal(result.structuredContent.apply, false);
});

test('policy_get reports the rules in force', async () => {
  const result = await call('policy_get');
  assert.ok(!result.isError, textOf(result));
  const payload = result.structuredContent;
  assert.ok(Array.isArray(payload.rules), 'the rules are listed');
  assert.ok(payload.rules.length > 0, 'there is at least one rule');
  for (const rule of payload.rules) {
    assert.ok(rule.id, 'a rule names its id');
    assert.ok(rule.verdict, 'a rule names its verdict');
  }
});

test('an unknown tool is refused by name', async () => {
  const result = await call('no_such_tool', {});
  assert.ok(result.isError, 'an unknown tool is an error');
});

test('every tool is callable and returns content', async () => {
  // The sweep. Each tool is called with the arguments it advertises, and
  // the call must return -- not throw, not hang, not crash the server.
  // A tool that is registered but never exercised is the gap this file
  // exists to close.
  const calls: Array<[string, Record<string, unknown>]> = [
    ['search_library', { query: 'test', limit: 1 }],
    ['get_skill', { id: SKILL_ID }],
    ['get_agent', { id: AGENT_ID }],
    ['get_skill_bundle', { id: SKILL_ID }],
    ['list_library', { section: 'stats' }],
    ['install_skills', { harness: 'puku-cli', ids: [SKILL_ID] }],
    ['install_agents', { harness: 'claude-code', ids: [AGENT_ID] }],
    ['uninstall_skills', { harness: 'puku-cli', names: ['tdd-workflow'] }],
    ['uninstall_agents', { harness: 'claude-code', names: ['code-reviewer'] }],
    ['policy_get', {}],
  ];

  // The sweep must cover exactly the tools the server publishes. If a
  // tool is added and not called here, this fails -- which is the point:
  // the coverage cannot fall behind the surface without a red test.
  assert.deepEqual(calls.map(([n]) => n), [...TOOLS]);

  for (const [name, args] of calls) {
    const result = await call(name, args);
    assert.ok(result, `${name} returned nothing`);
    assert.ok(Array.isArray(result.content), `${name} returned no content`);
  }
});
