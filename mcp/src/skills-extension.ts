/**
 * The Skills extension (`io.modelcontextprotocol/skills`).
 *
 * This is the official extension for serving Agent Skills over MCP. It
 * gives a client three things the tool surface cannot:
 *
 *  * `skills/list` — every skill, as metadata plus a complete file
 *    manifest. The bodies are *not* in the listing: a client that wants
 *    to know what skills exist should not have to download 66 MB to find
 *    out.
 *  * `skills/get` — one skill by URI, for a client that has a URI but
 *    not a listing. A server that only lists is not conformant: a host
 *    must be able to load a skill it was told about by URI.
 *  * `resources/read` — the bytes of a file, verified against the
 *    manifest's digest.
 *
 * The shape comes from SEP-2640 and the Agent Skills specification:
 *
 *  * A skill entry is `{uri, frontmatter, resources}`. The `frontmatter`
 *    is *verbatim* — every YAML field, unchanged — because a host
 *    compares it field-by-field against the `SKILL.md` it read.
 *  * `resources` is the complete manifest: every file in the skill,
 *    exactly once, each with its URI, SHA-256 digest and byte size.
 *    It is never absent and never split across pages.
 *  * The final segment of a skill's URI path is the skill's `name`.
 *  * `resources/directory/read` lists a directory's direct children.
 *    It is optional, and the server only declares it if it is
 *    implemented — the declaration is a promise to a client.
 *
 * Every result carries `resultType`, `ttlMs` and `cacheScope`; those
 * come from `mcp/src/protocol.ts`, which owns the revision decision.
 */
import { readFileSync, existsSync, statSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join, resolve, sep } from 'node:path';
import type { LibraryIndex, SkillRecord, SkillEntry } from './types.js';
import { encodeCursor, decodeCursor, cursorMatches } from './protocol.js';

export const SKILLS_EXTENSION_ID = 'io.modelcontextprotocol/skills';

/** How long a client may treat a skills listing as fresh. */
export const SKILLS_TTL_MS = 300_000;

/** How many skills one page of `skills/list` holds. */
export const SKILLS_PAGE_SIZE = 100;

/**
 * How many resources one page of `resources/list` holds.
 *
 * A page holds whole resources, never a file in pieces, so the page
 * size is a page of files.
 */
export const RESOURCES_PAGE_SIZE = 500;

/** The URI scheme this server serves skills under. */
export const SKILL_SCHEME = 'skill://';

/**
 * The error the extension defines for an unknown URI.
 *
 * `-32602` is "invalid params". The specification is explicit: an
 * unknown skill URI returns `-32602` and the host stops loading.
 */
export const INVALID_PARAMS = -32602;

export class SkillError extends Error {
  readonly code: number;

  constructor(message: string, code: number = INVALID_PARAMS) {
    super(message);
    this.name = 'SkillError';
    this.code = code;
  }
}

/**
 * The served skills, in a stable order.
 *
 * The order is by served name, not by the index order. The index order
 * is the order the library was scanned in, which changes when the
 * library is re-scanned; a client that paged through the listing would
 * see a different order for the same library. A cursor names the last
 * skill it saw, so the order has to be stable for the cursor to mean
 * anything.
 */
export function sortedSkills(index: LibraryIndex): SkillRecord[] {
  return [...index.skills].sort((a, b) =>
    a.skills.name < b.skills.name ? -1 : a.skills.name > b.skills.name ? 1 : 0,
  );
}

/**
 * The entry for a skill, in the shape the extension serves.
 *
 * The specification's entry is `{uri, frontmatter, resources}`. The
 * served name and description are *in* the frontmatter -- that is where
 * the specification puts them -- so repeating them at the top level
 * would be a second copy that could disagree with the first.
 *
 * The three extra fields appear only when the server adapted the skill
 * to make it conform: a client that compares the frontmatter against
 * the file it read needs to know that the server changed something.
 */
export function skillEntry(record: SkillRecord): SkillEntry {
  const entry = record.skills;
  return {
    uri: entry.uri,
    frontmatter: entry.frontmatter,
    resources: entry.resources,
    ...(entry.name_override ? { name_override: entry.name_override } : {}),
    ...(entry.description_truncated ? { description_truncated: entry.description_truncated } : {}),
    ...(entry.problems.length ? { problems: entry.problems } : {}),
  } as SkillEntry;
}

/**
 * Find the skill a URI names.
 *
 * The URI is `skill://<served-name>/<path>`. The name is the *served*
 * name, which is not always the directory's name -- two skills in this
 * library have a name that breaks the Agent Skills rules and are served
 * under a conforming one. So the lookup goes through the index rather
 * than through the filesystem, and a URI built from the directory name
 * is not a URI this server issued.
 */
export function findByUri(index: LibraryIndex, uri: string): SkillRecord | undefined {
  if (typeof uri !== 'string' || !uri.startsWith(SKILL_SCHEME)) return undefined;
  const rest = uri.slice(SKILL_SCHEME.length);
  const slash = rest.indexOf('/');
  const name = slash < 0 ? rest : rest.slice(0, slash);
  return index.skills.find((s) => s.skills.name === name);
}

/**
 * The skill a `skills/get` URI names.
 *
 * `skills/get` takes the URI of a skill's `SKILL.md`, and only that.
 * A URI that names the skill's directory, or one of its other files,
 * is not a skill URI -- and a URI that climbs out of the skill with
 * `..` is not a URI this server issued at all.
 *
 * The distinction matters because `skills/get` returns the *whole*
 * skill: accepting `skill://x/../y` would answer with a skill the
 * client did not name.
 */
export function findSkillMd(index: LibraryIndex, uri: string): SkillRecord | undefined {
  const record = findByUri(index, uri);
  if (!record) return undefined;
  if (uri !== record.skills.uri) return undefined;
  return record;
}

/**
 * The path of a file inside a skill, relative to the skill's directory.
 *
 * `undefined` when the URI does not name a file in this skill -- a
 * path that escapes the skill (`../`), a path to nothing, or a URI that
 * names the skill itself with no file.
 */
export function filePathInSkill(record: SkillRecord, uri: string): string | undefined {
  const prefix = `${SKILL_SCHEME}${record.skills.name}/`;
  if (!uri.startsWith(prefix)) return undefined;
  const rel = uri.slice(prefix.length);
  if (!rel) return undefined;
  // A path that climbs out of the skill is not a path in the skill.
  const parts = rel.split('/');
  if (parts.some((p) => p === '..' || p === '.' || p === '')) return undefined;
  return rel;
}

/**
 * The file a `resources/read` URI names, with its bytes.
 *
 * The digest is checked against the manifest before the bytes are
 * returned. That is the point of the manifest: a host verifies the
 * bytes it got against the digest the server published, and the server
 * verifying them first means a corrupted or swapped file is reported
 * rather than served.
 */
export function readSkillFile(
  root: string,
  index: LibraryIndex,
  uri: string,
): { record: SkillRecord; rel: string; bytes: Buffer; mime: string; digest: string } {
  const record = findByUri(index, uri);
  if (!record) {
    throw new SkillError(`Unknown skill URI: ${uri}`);
  }
  const rel = filePathInSkill(record, uri);
  if (rel === undefined) {
    throw new SkillError(`Unknown resource URI: ${uri}`);
  }

  // The path is resolved against the skill's directory and then checked
  // to be inside it, so a URI can never reach a file outside the skill.
  const dir = resolve(root, record.path);
  const abs = resolve(dir, rel);
  if (abs !== dir && !abs.startsWith(dir + sep)) {
    throw new SkillError(`Unknown resource URI: ${uri}`);
  }
  if (!existsSync(abs) || !statSync(abs).isFile()) {
    throw new SkillError(`Unknown resource URI: ${uri}`);
  }

  const bytes = readFileSync(abs);
  const entry = record.bundle.files.find((f) => f.path === rel);
  const digest = entry?.digest;
  if (!digest) {
    throw new SkillError(`No manifest entry for ${uri}`);
  }
  const actual = 'sha256:' + digestOf(bytes);
  if (actual !== digest) {
    throw new SkillError(
      `Digest mismatch for ${uri}: the manifest says ${digest}, the file is ${actual}`,
    );
  }
  return { record, rel, bytes, mime: entry?.mime ?? 'application/octet-stream', digest };
}

/** The SHA-256 of some bytes, as the extension writes it. */
export function digestOf(bytes: Buffer): string {
  return createHash('sha256').update(bytes).digest('hex');
}

/**
 * The children of a directory inside a skill.
 *
 * Only the direct children, as the specification requires. A child
 * directory is reported with `mimeType: "inode/directory"` and no
 * trailing slash on its URI.
 */
export function readSkillDirectory(
  index: LibraryIndex,
  uri: string,
): { uri: string; name: string; mimeType: string }[] {
  const record = findByUri(index, uri);
  if (!record) {
    throw new SkillError(`Unknown skill URI: ${uri}`);
  }
  const prefix = `${SKILL_SCHEME}${record.skills.name}`;
  if (uri !== prefix && !uri.startsWith(prefix + '/')) {
    throw new SkillError(`Unknown directory URI: ${uri}`);
  }
  const rel = uri === prefix ? '' : uri.slice(prefix.length + 1);
  if (rel.split('/').some((p) => p === '..' || p === '.')) {
    throw new SkillError(`Unknown directory URI: ${uri}`);
  }

  // A URI that names a *file* is not a directory, and the
  // specification says a directory read of anything else is
  // `-32602`. The manifest is the tree, so the check is against it.
  const isFile = record.bundle.files.some((f) => f.path === rel);
  if (isFile) {
    throw new SkillError(`Not a directory: ${uri}`);
  }

  // A directory is a prefix of the files in the manifest. The manifest
  // is the tree: a host may answer a directory query from it, and the
  // specification says a live directory result must not extend the
  // retained manifest.
  const dir = rel ? rel + '/' : '';
  const seen = new Map<string, string>();
  for (const file of record.bundle.files) {
    if (dir && !file.path.startsWith(dir)) continue;
    const rest = file.path.slice(dir.length);
    if (!rest) continue;
    const slash = rest.indexOf('/');
    if (slash < 0) {
      // A file directly in this directory.
      seen.set(rest, file.mime ?? 'application/octet-stream');
    } else {
      // A subdirectory: reported once, by its own name.
      const name = rest.slice(0, slash);
      if (!seen.has(name)) seen.set(name, 'inode/directory');
    }
  }

  // A directory with no children is not a directory. Without this, a
  // URI for a path that does not exist would answer with an empty
  // listing -- which reads as "this directory is empty" rather than
  // "there is nothing here".
  if (seen.size === 0) {
    throw new SkillError(`Unknown directory URI: ${uri}`);
  }

  const out = [...seen.entries()].map(([name, mimeType]) => ({
    uri: `${prefix}/${dir}${name}`,
    name,
    mimeType,
  }));
  out.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));
  return out;
}

/**
 * One page of `skills/list`.
 *
 * The page holds whole skills, never parts of a manifest: a skill's
 * `resources` are atomic, so the entry is either on the page or not.
 */
export function listSkills(
  index: LibraryIndex,
  cursor: string | undefined,
): { skills: SkillEntry[]; nextCursor?: string } {
  const all = sortedSkills(index);
  let start = 0;

  if (cursor) {
    const decoded = decodeCursor(cursor);
    if (decoded && cursorMatches(decoded, 'skills/list')) {
      const pos = all.findIndex((s) => s.skills.name === decoded.after);
      if (pos >= 0) start = pos + 1;
    }
  }

  const page = all.slice(start, start + SKILLS_PAGE_SIZE);
  const result: { skills: SkillEntry[]; nextCursor?: string } = {
    skills: page.map(skillEntry),
  };
  if (start + SKILLS_PAGE_SIZE < all.length && page.length > 0) {
    result.nextCursor = encodeCursor(page[page.length - 1]!.skills.name, 'skills/list');
  }
  return result;
}

/**
 * Every resource the server serves, in a stable order.
 *
 * The `resources` capability is declared, so `resources/list` has to
 * answer: a client that reads the capability and then calls the method
 * would get `-32601` otherwise. The list is the skills in served-name
 * order, and within a skill the files in manifest order -- the same
 * order the manifest itself lists them, so a client that has seen a
 * manifest sees the same files again.
 *
 * The order has to be stable for the cursor to mean anything, so it
 * is built from the sorted skills rather than from the index order.
 */
export interface ListedResource {
  uri: string;
  name: string;
  mimeType: string;
  size: number;
}

/** Every served resource, in a stable order. */
export function allResources(index: LibraryIndex): ListedResource[] {
  const out: ListedResource[] = [];
  for (const record of sortedSkills(index)) {
    const name = record.skills.name;
    for (const file of record.bundle.files) {
      out.push({
        uri: file.uri ?? `skill://${name}/${file.path}`,
        name: file.path.split('/').pop() ?? file.path,
        mimeType: file.mime ?? 'application/octet-stream',
        size: file.bytes,
      });
    }
  }
  return out;
}

/**
 * One page of `resources/list`.
 *
 * The cursor names the last resource of the previous page. Resources
 * are atomic -- a file is either on the page or not -- so the cursor
 * can name one of them.
 */
export function listResources(
  index: LibraryIndex,
  cursor: string | undefined,
): { resources: ListedResource[]; nextCursor?: string } {
  const all = allResources(index);
  let start = 0;

  if (cursor) {
    const decoded = decodeCursor(cursor);
    if (decoded && cursorMatches(decoded, 'resources/list')) {
      const pos = all.findIndex((r) => r.uri === decoded.after);
      if (pos >= 0) start = pos + 1;
    }
  }

  const page = all.slice(start, start + RESOURCES_PAGE_SIZE);
  const result: { resources: ListedResource[]; nextCursor?: string } = {
    resources: page,
  };
  if (start + RESOURCES_PAGE_SIZE < all.length && page.length > 0) {
    result.nextCursor = encodeCursor(page[page.length - 1]!.uri, 'resources/list');
  }
  return result;
}
