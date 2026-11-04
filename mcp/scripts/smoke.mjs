/**
 * The smoke test.
 *
 * Starts the compiled server as a real subprocess, speaks MCP to it
 * over stdio, and checks that a single search comes back with a
 * sensible answer. This is the check that catches the failure modes
 * that unit tests miss: a bad entrypoint, a missing index, a server
 * that writes to stdout and corrupts the protocol stream.
 *
 * It exits non-zero on any failure, so `rebuild.sh` stops there.
 */
import { spawn } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const MCP_ROOT = resolve(HERE, '..');
const ENTRY = join(MCP_ROOT, 'dist', 'index.js');

let failures = 0;
function check(label, condition, detail = '') {
  if (condition) {
    console.log(`ok   ${label}`);
  } else {
    failures += 1;
    console.error(`FAIL ${label} ${detail}`);
  }
}

/** Send the request lines, collect the responses by id. */
function drive(binary, args, env) {
  return new Promise((resolvePromise) => {
    const child = spawn(binary, args, {
      env: { ...process.env, ...env },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let out = '';
    let err = '';
    child.stdout.on('data', (d) => { out += d.toString(); });
    child.stderr.on('data', (d) => { err += d.toString(); });
    child.on('close', (code) => {
      const responses = new Map();
      for (const line of out.split('\n')) {
        const t = line.trim();
        if (!t) continue;
        try {
          const msg = JSON.parse(t);
          responses.set(msg.id, msg);
        } catch {
          /* a non-JSON line on stdout is itself a finding */
        }
      }
      resolvePromise({ code, out, err, responses });
    });

    const requests = [
      { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'smoke', version: '1' } } },
      { jsonrpc: '2.0', method: 'notifications/initialized' },
      { jsonrpc: '2.0', id: 2, method: 'tools/list' },
      { jsonrpc: '2.0', id: 3, method: 'tools/call', params: { name: 'search_library', arguments: { query: 'accessibility audit WCAG', limit: 5 } } },
    ];
    child.stdin.write(requests.map((r) => JSON.stringify(r)).join('\n') + '\n');
    child.stdin.end();
  });
}

const res = await drive('node', [ENTRY], {
  SKILLS_LIBRARY_ROOT: resolve(MCP_ROOT, '..'),
});

check('the server exits cleanly', res.code === 0, res.err.slice(-400));
check('the server answered every request', res.responses.size === 3, String(res.responses.size));

const init = res.responses.get(1)?.result ?? {};
check('initialize returns a protocolVersion', Boolean(init.protocolVersion));
check('initialize returns serverInfo', init.serverInfo?.name === 'skills-library');

const tools = res.responses.get(2)?.result?.tools ?? [];
check('there are 8 tools', tools.length === 8, String(tools.length));

const sc = res.responses.get(3)?.result?.structuredContent;
const results = sc?.results ?? [];
check('the search returns results', results.length > 0, JSON.stringify(sc).slice(0, 200));
check(
  'skill:accessibility is the top hit',
  results[0]?.id === 'skill:accessibility',
  results[0]?.id ?? 'none',
);

if (failures) {
  console.error(`\n${failures} SMOKE FAILURE(S)`);
  process.exit(1);
}
console.log('\nSMOKE: PASS');
