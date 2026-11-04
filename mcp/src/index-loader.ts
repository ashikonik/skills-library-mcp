/**
 * Loads `mcp/data/index.json` — the shared artifact both servers read.
 *
 * The index is ~5 MB and is read once at startup. It carries
 * descriptions, tokens and bundle manifests only; the actual SKILL.md
 * bodies are read lazily, one file at a time, when a tool is asked for
 * them. Nothing here loads 8.4 MB of skill text into memory.
 */
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { LibraryIndex } from './types.js';

const HERE = dirname(fileURLToPath(import.meta.url));

/** `mcp/` — the package root, whether running from `src/` or `dist/`. */
export const MCP_ROOT = resolve(HERE, '..');

/**
 * The library root. `SKILLS_LIBRARY_ROOT` overrides it, so the server
 * can be pointed at a checkout somewhere else without a rebuild.
 */
export function libraryRoot(): string {
  const env = process.env.SKILLS_LIBRARY_ROOT;
  if (env) return resolve(env);
  return resolve(MCP_ROOT, '..');
}

export function indexPath(): string {
  return join(libraryRoot(), 'mcp', 'data', 'index.json');
}

export function loadIndex(path?: string): LibraryIndex {
  const p = path ?? indexPath();
  if (!existsSync(p)) {
    throw new Error(
      `mcp/data/index.json not found (looked at ${p}). ` +
        `Run scripts/rebuild.sh to build it.`,
    );
  }
  const raw = readFileSync(p, 'utf-8');
  return JSON.parse(raw) as LibraryIndex;
}
