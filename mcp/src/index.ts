#!/usr/bin/env node
/**
 * The entry point — the ONLY file that knows the transport.
 *
 * Everything above this file is transport-independent, so the same server
 * can be driven over stdio here or in-process by a test. Nothing may be
 * written to stdout: on the stdio transport stdout *is* the protocol
 * stream, and a stray `print` corrupts it. All logging goes to stderr.
 */
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { createServer } from './server.js';
import { loadIndex, indexPath } from './index-loader.js';

function log(msg: string): void {
  process.stderr.write(`[skills-library] ${msg}\n`);
}

async function main(): Promise<void> {
  let index;
  try {
    index = loadIndex();
  } catch (e) {
    log(e instanceof Error ? e.message : String(e));
    process.exit(1);
  }

  log(
    `loaded ${index.counts.skills} skills + ${index.counts.agents} agents from ${indexPath()}`,
  );

  const server = createServer({ index });
  const transport = new StdioServerTransport();
  await server.connect(transport);
  log('ready');
}

main().catch((e) => {
  log(e instanceof Error ? (e.stack ?? e.message) : String(e));
  process.exit(1);
});
