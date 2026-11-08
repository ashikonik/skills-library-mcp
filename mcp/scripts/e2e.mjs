/**
 * The end-to-end test.
 *
 * Drives the *compiled* server as a real subprocess, speaks MCP to it
 * over stdio, and takes a skill all the way through: dry run, apply,
 * verify on disk, uninstall, verify gone.
 *
 * The dry run is checked first and hard, because a dry run that writes
 * anything is the worst bug this server could have -- it would put
 * files in a harness the caller never asked to touch.
 *
 * The harness directories are redirected to a temporary tree by
 * pointing `HOME` at it, so this never touches the real
 * `~/.puku-cli` or `~/.config/opencode`.
 *
 * Usage:
 *   node scripts/e2e.mjs              # the temporary-tree run
 *   node scripts/e2e.mjs --real       # against the real $HOME (opt-in)
 */
import { spawn } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  mkdtempSync, mkdirSync, existsSync, lstatSync, readlinkSync,
  readFileSync, rmSync, realpathSync,
} from 'node:fs';
import { tmpdir } from 'node:os';

const HERE = dirname(fileURLToPath(import.meta.url));
const MCP_ROOT = resolve(HERE, '..');
const ENTRY = join(MCP_ROOT, 'dist', 'index.js');
const LIBRARY = resolve(MCP_ROOT, '..');
const REAL = process.argv.includes('--real');

let failures = 0;
function check(label, condition, detail = '') {
  if (condition) {
    console.log(`ok   ${label}`);
  } else {
    failures += 1;
    console.error(`FAIL ${label} ${detail}`);
  }
}

/**
 * Send the requests, collect the responses by id.
 *
 * The server is asked to exit at the end by closing stdin, which is
 * what a real client does when the session ends.
 */
function drive(env, requests) {
  return new Promise((done) => {
    const child = spawn('node', [ENTRY], {
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
          if (msg.id !== undefined) responses.set(msg.id, msg);
        } catch {
          /* a non-JSON line on stdout is itself a finding */
        }
      }
      done({ code, out, err, responses });
    });
    child.stdin.write(requests.map((r) => JSON.stringify(r)).join('\n') + '\n');
    child.stdin.end();
  });
}

const INIT = {
  jsonrpc: '2.0',
  id: 1,
  method: 'initialize',
  params: {
    protocolVersion: '2025-06-18',
    capabilities: {},
    clientInfo: { name: 'e2e', version: '1' },
  },
};
const NOTIFY = { jsonrpc: '2.0', method: 'notifications/initialized' };

// ---------------------------------------------------------------- the tree
const home = REAL ? process.env.HOME : mkdtempSync(join(tmpdir(), 'e2e-home-'));
const pukuSkills = join(home, '.puku-cli', 'skills');
// The project root, where the server reads its policy file and writes
// its install manifest. It is pointed at a temporary tree so the test
// leaves nothing behind in the repository it runs from.
const project = REAL ? process.cwd() : mkdtempSync(join(tmpdir(), 'e2e-project-'));
const env = {
  SKILLS_LIBRARY_ROOT: LIBRARY,
  SKILLS_LIBRARY_PROJECT: project,
  HOME: home,
  USERPROFILE: home,
};
if (!REAL) {
  mkdirSync(pukuSkills, { recursive: true });
}

const NAME = 'tdd-workflow';
const LINK = join(pukuSkills, NAME);
const LIB_COPY = join(LIBRARY, 'skills', NAME);

// ------------------------------------------------------------------ 1. dry
console.log('=== 1. dry run (apply not set) ===');
const dry = await drive(env, [
  INIT,
  NOTIFY,
  {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'install_skills',
      arguments: { harness: 'puku-cli', ids: [`skill:${NAME}`] },
    },
  },
]);

const dryResult = dry.responses.get(2)?.result?.structuredContent;
check('dry run: the server answered', Boolean(dryResult), JSON.stringify(dry.responses.get(2)).slice(0, 300));
check('dry run: nothing was written', dryResult?.written === 0, String(dryResult?.written));
check('dry run: one target was planned', dryResult?.targets?.length === 1, String(dryResult?.targets?.length));
check('dry run: the target says "planned"',
  dryResult?.targets?.[0]?.status === 'planned', dryResult?.targets?.[0]?.status);
check('dry run: the planned path is the skill directory',
  dryResult?.targets?.[0]?.path === LINK, dryResult?.targets?.[0]?.path);
check('dry run: nothing exists on disk', !existsSync(LINK));
check('dry run: the note says it is a dry run',
  String(dryResult?.note ?? '').includes('Dry run'), String(dryResult?.note));

// ----------------------------------------------------------------- 2. apply
console.log('\n=== 2. apply ===');
const applied = await drive(env, [
  INIT,
  NOTIFY,
  {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'install_skills',
      arguments: { harness: 'puku-cli', ids: [`skill:${NAME}`], apply: true },
    },
  },
]);

const applyResult = applied.responses.get(2)?.result?.structuredContent;
check('apply: the server answered', Boolean(applyResult), JSON.stringify(applied.responses.get(2)).slice(0, 300));
check('apply: one target was written', applyResult?.written === 1, String(applyResult?.written));
check('apply: the target says "written"',
  applyResult?.targets?.[0]?.status === 'written', applyResult?.targets?.[0]?.status);

check('apply: the link exists on disk', existsSync(LINK) || isLink(LINK), LINK);
check('apply: it is a symlink', isLink(LINK));
check('apply: it is not nested one level deeper',
  !existsSync(join(LINK, NAME)), 'the link points at itself');
check('apply: it resolves to a real SKILL.md',
  existsSync(join(LINK, 'SKILL.md')));
check('apply: it points into the library',
  isLink(LINK) && realpathSync(LINK).startsWith(realpathSync(LIBRARY)),
  isLink(LINK) ? readlinkSync(LINK) : 'not a link');
check('apply: the reported path is the link',
  applyResult?.targets?.[0]?.path === LINK, applyResult?.targets?.[0]?.path);

// -------------------------------------------------------- 3. install twice
console.log('\n=== 3. install again, without overwrite ===');
const again = await drive(env, [
  INIT,
  NOTIFY,
  {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'install_skills',
      arguments: { harness: 'puku-cli', ids: [`skill:${NAME}`] },
    },
  },
]);
const againResult = again.responses.get(2)?.result?.structuredContent;
check('install again: it is skipped, not clobbered',
  againResult?.targets?.[0]?.status === 'skipped', againResult?.targets?.[0]?.status);
check('install again: the reason names the fix',
  String(againResult?.targets?.[0]?.reason ?? '').includes('overwrite=true'),
  String(againResult?.targets?.[0]?.reason));
check('install again: the link is still there', isLink(LINK));

// ------------------------------------------------------------- 4. uninstall
console.log('\n=== 4. uninstall (dry run) ===');
const unDry = await drive(env, [
  INIT,
  NOTIFY,
  {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'uninstall_skills',
      arguments: { harness: 'puku-cli', names: [NAME] },
    },
  },
]);
const unDryResult = unDry.responses.get(2)?.result?.structuredContent;
check('uninstall dry run: nothing was removed',
  unDryResult?.removed === 0, String(unDryResult?.removed));
check('uninstall dry run: the link is still there', isLink(LINK));
check('uninstall dry run: the note says it is a dry run',
  String(unDryResult?.note ?? '').includes('Dry run'), String(unDryResult?.note));

console.log('\n=== 5. uninstall (apply) ===');
const un = await drive(env, [
  INIT,
  NOTIFY,
  {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'uninstall_skills',
      arguments: { harness: 'puku-cli', names: [NAME], apply: true },
    },
  },
]);
const unResult = un.responses.get(2)?.result?.structuredContent;
check('uninstall: one target was removed', unResult?.removed === 1, String(unResult?.removed));
check('uninstall: the link is gone', !isLink(LINK) && !existsSync(LINK), LINK);
check("uninstall: the library's own SKILL.md survived",
  existsSync(join(LIB_COPY, 'SKILL.md')));

// ------------------------------------------------------------------ 6. copy
console.log('\n=== 6. copy mode ===');
const copied = await drive(env, [
  INIT,
  NOTIFY,
  {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'install_skills',
      arguments: { harness: 'puku-cli', ids: [`skill:${NAME}`], mode: 'copy', apply: true },
    },
  },
]);
const copyResult = copied.responses.get(2)?.result?.structuredContent;
check('copy: the target was written', copyResult?.written === 1, String(copyResult?.written));
check('copy: it is a real directory, not a link',
  existsSync(LINK) && !isLink(LINK));
check('copy: it holds a SKILL.md', existsSync(join(LINK, 'SKILL.md')));
check('copy: the copy is not a symlink to the library',
  !isLink(join(LINK, 'SKILL.md')));
const copiedText = existsSync(join(LINK, 'SKILL.md'))
  ? readFileSync(join(LINK, 'SKILL.md'), 'utf-8') : '';
check('copy: the frontmatter was rewritten for the harness',
  copiedText.startsWith('---') && copiedText.includes(`name: ${NAME}`),
  copiedText.slice(0, 120).replace(/\n/g, ' '));

// and the copy uninstalls too
const unCopy = await drive(env, [
  INIT,
  NOTIFY,
  {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'uninstall_skills',
      arguments: { harness: 'puku-cli', names: [NAME], apply: true },
    },
  },
]);
const unCopyResult = unCopy.responses.get(2)?.result?.structuredContent;
check('copy: it uninstalls too', unCopyResult?.removed === 1, String(unCopyResult?.removed));
check('copy: the directory is gone', !existsSync(LINK));

// ------------------------------------------------------------- 7. the agent
console.log('\n=== 7. install an agent into opencode ===');
const opencodeAgents = join(home, '.config', 'opencode', 'agents');
if (!REAL) mkdirSync(opencodeAgents, { recursive: true });
const agent = await drive(env, [
  INIT,
  NOTIFY,
  {
    jsonrpc: '2.0',
    id: 2,
    method: 'tools/call',
    params: {
      name: 'search_library',
      arguments: { query: 'code reviewer', kind: 'agent', limit: 3 },
    },
  },
]);
const agentHits = agent.responses.get(2)?.result?.structuredContent?.results ?? [];
check('agent: the search finds an agent',
  agentHits.length > 0 && agentHits[0].kind === 'agent',
  JSON.stringify(agentHits.map((h) => h.id)));

if (agentHits.length) {
  const agentId = agentHits[0].id;
  const agentInstall = await drive(env, [
    INIT,
    NOTIFY,
    {
      jsonrpc: '2.0',
      id: 2,
      method: 'tools/call',
      params: {
        name: 'install_agents',
        arguments: { harness: 'opencode', ids: [agentId], apply: true },
      },
    },
  ]);
  const agentResult = agentInstall.responses.get(2)?.result?.structuredContent;
  check('agent: the target was written', agentResult?.written === 1,
    JSON.stringify(agentResult?.targets?.[0]));
  const agentPath = agentResult?.targets?.[0]?.path;
  check('agent: the file exists', Boolean(agentPath) && existsSync(agentPath), String(agentPath));
  if (agentPath && existsSync(agentPath)) {
    const text = readFileSync(agentPath, 'utf-8');
    check('agent: it has frontmatter', text.startsWith('---'));
    check('agent: opencode agents take a permission matrix, not tools',
      text.includes('permission:') && !/^tools:/m.test(text),
      text.slice(0, 200).replace(/\n/g, ' '));
    check('agent: it declares a mode',
      /^mode:\s*(subagent|primary)/m.test(text),
      text.slice(0, 200).replace(/\n/g, ' '));
  }
}

// --------------------------------------------------------------- cleanup
if (!REAL) rmSync(home, { recursive: true, force: true });

function isLink(p) {
  try {
    return lstatSync(p).isSymbolicLink();
  } catch {
    return false;
  }
}

if (failures) {
  console.error(`\n${failures} E2E FAILURE(S)`);
  process.exit(1);
}
console.log('\nE2E: PASS');
