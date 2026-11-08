// Produces the pagination cursors for the Python agreement test.
//
// The SDK's own `Client` cannot be used here: it always asks for
// `LATEST_PROTOCOL_VERSION` and refuses any revision it does not
// know -- and `2026-07-28` is exactly the revision the SDK does not
// know. So the handshake is driven raw over the transport, the way a
// real client that speaks the newer revision would.
//
// Writes a JSON object on stdout: the first page's ids, the cursor,
// and the second page's ids.
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { loadIndex } from '../dist/index-loader.js';
import { createServer } from '../dist/server.js';

const query = process.argv[2] ?? 'code review refactoring';
const limit = Number(process.argv[3] ?? 3);

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
  process.stderr.write('initialize failed: %s\n' % JSON.stringify(init.error));
  process.exit(1);
}
if (init.result.protocolVersion !== '2026-07-28') {
  process.stderr.write(
    'the server did not negotiate 2026-07-28: %s\n' % init.result.protocolVersion,
  );
  process.exit(1);
}

await clientTransport.send({
  jsonrpc: '2.0',
  method: 'notifications/initialized',
});

const call = async (cursor) => {
  const args = { query, limit };
  if (cursor) args.cursor = cursor;
  const res = await send('tools/call', {
    name: 'search_library',
    arguments: args,
  });
  if (res.error) {
    process.stderr.write('tools/call failed: %s\n' % JSON.stringify(res.error));
    process.exit(1);
  }
  return res.result.structuredContent ?? {};
};

const page1 = await call(null);
const cursor = page1.next_cursor ?? null;
const page2 = cursor ? await call(cursor) : { results: [] };

process.stdout.write(
  JSON.stringify({
    query,
    limit,
    page1: (page1.results ?? []).map((r) => r.id),
    cursor,
    page2: (page2.results ?? []).map((r) => r.id),
    truncated: page1.truncated ?? false,
    total_matched: page1.total_matched ?? 0,
  }),
);

await server.close();
