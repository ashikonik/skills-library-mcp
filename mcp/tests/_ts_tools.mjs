// Lists the TypeScript server's tools, for the Python agreement test.
//
// Uses the SDK's InMemoryTransport and issues a real `tools/list`
// request, so this checks the same path a client would take -- not a
// private registry the SDK happens to expose.
//
// Writes a JSON array of {name, title, description, annotations} on
// stdout, in the server's registration order.
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { loadIndex } from '../dist/index-loader.js';
import { createServer } from '../dist/server.js';

const server = createServer({ index: loadIndex() });
const client = new Client({ name: 'agreement-test', version: '1.0.0' });

const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);

const { tools } = await client.listTools();
const out = tools.map((t) => ({
  name: t.name,
  title: t.title,
  description: t.description,
  annotations: t.annotations,
}));
process.stdout.write(JSON.stringify(out));
await client.close();
await server.close();
