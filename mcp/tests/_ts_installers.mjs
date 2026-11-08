// Drives the TypeScript installer whitelist from the Python parity test.
//
// Reads the home directory on argv[2] and the project root on argv[3],
// and writes a JSON array of booleans on stdout: one per case, true
// when the target is allowed.
//
// The cases live in the Python test, so both implementations are
// driven over exactly the same list. `HOME` is set by the caller,
// because `installers.ts` reads it once, at module load.
import { join } from 'node:path';
import { checkTarget } from '../dist/installers.js';

const home = process.argv[2];
const project = process.argv[3];

const CASES = [
  ['agentsmd', 'AGENTS.md'],
  ['agentsmd', 'sub/AGENTS.md'],
  ['agentsmd', 'notes.txt'],
  ['agentsmd', 'deep/nested/file.txt'],
  ['agentsmd', '../outside.txt'],
  ['claude-code', '.claude/skills/tdd-workflow/SKILL.md'],
  ['claude-code', '.claude/skills/nested/deep/SKILL.md'],
  ['claude-code', '.claude/agents/thing.md'],
  ['claude-code', '.claude/skills/learned/thing/SKILL.md'],
  ['claude-code', '.codex/skills/thing/SKILL.md'],
  ['claude-code', '../escape.txt'],
  ['codex', '.codex/skills/thing/SKILL.md'],
  ['codex', '.codex/skills/nested/SKILL.md'],
  ['codex', '.claude/skills/thing/SKILL.md'],
  ['codex', 'elsewhere/file.txt'],
  ['puku-cli', '.puku-cli/skills/thing/SKILL.md'],
  ['puku-cli', '.claude/skills/thing/SKILL.md'],
];

const out = [];
for (const [harness, rel] of CASES) {
  const root = harness === 'agentsmd' ? project : home;
  const target = join(root, rel);
  out.push(checkTarget(harness, target, project) === null);
}
process.stdout.write(JSON.stringify(out));
