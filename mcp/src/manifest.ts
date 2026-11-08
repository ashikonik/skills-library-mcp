/**
 * The install manifest: what this server wrote, and where.
 *
 * `install_agents` writes real files into `~/.claude/agents/` and
 * `~/.config/opencode/agents/`. Without a record of those writes there
 * is no way back: the harness directory is full of things this server
 * did not put there, and a blanket "uninstall everything in this
 * directory" would destroy them.
 *
 * So every write is recorded. The manifest lives beside the project's
 * policy file -- `<project>/.skills-library/` -- because both are
 * per-project state that a project may want to check in, or to ignore.
 *
 * **The manifest is a claim, not a guarantee.** It records what this
 * server wrote; it cannot prove that a path still holds what was
 * written there. So an uninstall checks both: the manifest says we
 * wrote it, and the thing on disk still looks like what we wrote. A
 * path in the manifest that has since been replaced by something else
 * is refused with the `not_ours` wall rather than removed.
 *
 * **A missing manifest is not an error.** It means this server has not
 * written anything for this project -- or that the project removed the
 * file. Either way there is nothing to uninstall, and an uninstall in
 * that state says so rather than failing.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

export const MANIFEST_DIR = '.skills-library';
export const MANIFEST_FILE = 'installs.json';
export const MANIFEST_SCHEMA_VERSION = 1;

export interface InstallRecord {
  harness: string;
  kind: 'skill' | 'agent';
  name: string;
  path: string;
  action: string;
}

/** Where the manifest lives for a project. */
export function manifestPath(projectRoot: string): string {
  return join(projectRoot, MANIFEST_DIR, MANIFEST_FILE);
}

/**
 * Read the manifest. A missing or malformed one reads as empty.
 *
 * A malformed manifest is *not* silently ignored -- it is reported,
 * because a manifest that cannot be read may still list files that
 * need removing, and pretending it is empty would strand them. The
 * error is carried alongside the (empty) records so the caller can
 * say so.
 */
export function loadManifest(
  projectRoot: string,
): { records: InstallRecord[]; error: string | null } {
  const path = manifestPath(projectRoot);
  if (!existsSync(path)) return { records: [], error: null };
  let parsed: unknown;
  try {
    parsed = JSON.parse(readFileSync(path, 'utf-8'));
  } catch (e) {
    return {
      records: [],
      error: `cannot read ${path}: ${e instanceof Error ? e.message : String(e)}`,
    };
  }
  if (
    parsed === null ||
    typeof parsed !== 'object' ||
    !Array.isArray((parsed as { installs?: unknown }).installs)
  ) {
    return {
      records: [],
      error: `${path} is malformed: it must be a JSON object with an "installs" array`,
    };
  }
  const records: InstallRecord[] = [];
  for (const entry of (parsed as { installs: unknown[] }).installs) {
    if (entry === null || typeof entry !== 'object') continue;
    const r = entry as Partial<InstallRecord>;
    if (!r.path || !r.kind) continue;
    records.push({
      harness: String(r.harness ?? ''),
      kind: r.kind,
      name: String(r.name ?? ''),
      path: r.path,
      action: String(r.action ?? ''),
    });
  }
  return { records, error: null };
}

/** Write the manifest. Returns an error string, or null. */
export function saveManifest(projectRoot: string, records: InstallRecord[]): string | null {
  const path = manifestPath(projectRoot);
  const payload = { schema_version: MANIFEST_SCHEMA_VERSION, installs: records };
  try {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, `${JSON.stringify(payload, null, 2)}\n`, 'utf-8');
  } catch (e) {
    return `cannot write ${path}: ${e instanceof Error ? e.message : String(e)}`;
  }
  return null;
}

/**
 * Record one write. Returns an error string, or null.
 *
 * A record is keyed by the path it describes: writing the same path
 * twice replaces the earlier record rather than duplicating it, so
 * the manifest stays one line per path.
 */
export function recordInstall(
  projectRoot: string,
  harness: string,
  kind: 'skill' | 'agent',
  name: string,
  path: string,
  action: string,
): string | null {
  const { records } = loadManifest(projectRoot);
  const kept = records.filter((r) => r.path !== path);
  kept.push({ harness, kind, name, path, action });
  kept.sort((a, b) =>
    `${a.harness}\u0000${a.kind}\u0000${a.name}\u0000${a.path}`.localeCompare(
      `${b.harness}\u0000${b.kind}\u0000${b.name}\u0000${b.path}`,
    ),
  );
  return saveManifest(projectRoot, kept);
}

/** Drop the record for a path that has been removed. */
export function forgetInstall(projectRoot: string, path: string): string | null {
  const { records } = loadManifest(projectRoot);
  const kept = records.filter((r) => r.path !== path);
  if (kept.length === records.length) return null;
  return saveManifest(projectRoot, kept);
}

/** The records for one harness and kind. */
export function recordsFor(
  projectRoot: string,
  harness: string,
  kind: 'skill' | 'agent',
): { records: InstallRecord[]; error: string | null } {
  const { records, error } = loadManifest(projectRoot);
  if (error) return { records: [], error };
  return {
    records: records.filter((r) => r.harness === harness && r.kind === kind),
    error: null,
  };
}
