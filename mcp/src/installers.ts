/**
 * The installers — one per harness, all behind the same safety rules.
 *
 * Three rules hold for every write:
 *
 *  1. **Dry run by default.** `apply` defaults to `false`; the tool
 *     returns a plan and writes nothing.
 *  2. **A path whitelist.** Writes are confined to a fixed set of
 *     harness directories. Anything outside is refused, not sanitised.
 *  3. **Symlinks point inward.** A symlink mode always targets a path
 *     inside the library, never out of it, and `uninstall` refuses to
 *     remove a symlink whose target is outside the library.
 *
 * `~/.claude/skills/learned/` is harness-managed and explicitly excluded:
 * writing into it fights the harness that owns it.
 */
import {
  mkdirSync,
  symlinkSync,
  existsSync,
  lstatSync,
  readlinkSync,
  rmSync,
  unlinkSync,
  copyFileSync,
  cpSync,
  writeFileSync,
  readdirSync,
  statSync,
  readFileSync,
} from 'node:fs';
import { homedir } from 'node:os';
import { join, resolve, relative, isAbsolute, sep, dirname } from 'node:path';
import type { Harness, SkillInput, AgentInput } from './frontmatter.js';
import {
  agentsmdMarker,
  emitAgentsmdSection,
  emitSkill,
  emitAgent,
  emitOpenAIAgentYaml,
  replaceSection,
} from './frontmatter.js';

export const HOME = homedir();

/** The directories this server may write to. */
export const TARGET_DIRS: Record<Harness, string[]> = {
  'claude-code': [join(HOME, '.claude', 'skills'), join(HOME, '.claude', 'agents')],
  codex: [join(HOME, '.codex', 'skills')],
  'codex-agents': [join(HOME, '.codex', '.agents', 'skills')],
  opencode: [join(HOME, '.config', 'opencode', 'skills'), join(HOME, '.config', 'opencode', 'agents')],
  cline: [join(HOME, '.clinerules')],
  'puku-cli': [join(HOME, '.puku-cli', 'skills')],
  agentsmd: [], // resolved against the project root, below
};

/** Harness-managed directories that must never be written to. */
export const EXCLUDED_PREFIXES = [join(HOME, '.claude', 'skills', 'learned')];

export type Mode = 'symlink' | 'copy';

export interface InstallTarget {
  harness: Harness;
  kind: 'skill' | 'agent';
  id: string;
  name: string;
  path: string;
  action: 'symlink' | 'copy' | 'write';
  status: 'planned' | 'written' | 'skipped' | 'error';
  reason?: string;
  dropped_keys?: string[];
  sidecars?: Array<{ path: string; action: string; status: string }>;
}

export interface InstallResult {
  harness: Harness;
  mode: Mode;
  apply: boolean;
  targets: InstallTarget[];
  written: number;
  skipped: number;
  errors: string[];
  note: string;
}

/** Is `p` inside `base`? Used to enforce the whitelist. */
export function isInside(base: string, p: string): boolean {
  const rel = relative(resolve(base), resolve(p));
  return rel !== '' && !rel.startsWith('..') && !isAbsolute(rel);
}

/**
 * Check a target path against the whitelist.
 *
 * Returns an error message, or `null` when the path is allowed.
 */
export function checkTarget(harness: Harness, target: string, projectRoot?: string): string | null {
  const bases =
    harness === 'agentsmd'
      ? [join(projectRoot ?? process.cwd(), 'AGENTS.md')]
      : TARGET_DIRS[harness];

  if (bases.length === 0) {
    return `Unsupported harness '${harness}'.`;
  }
  const resolved = resolve(target);
  const allowed = bases.some((b) => {
    if (harness === 'agentsmd') {
      // agentsmd writes one file, not a directory.
      return resolve(b) === resolved || isInside(resolve(b, '..'), resolved);
    }
    return isInside(b, resolved) || resolve(b) === resolved;
  });
  if (!allowed) {
    return `Refusing to write outside the harness directories: ${resolved}`;
  }
  for (const ex of EXCLUDED_PREFIXES) {
    if (isInside(ex, resolved)) {
      return `Refusing to write into the harness-managed directory: ${resolved}`;
    }
  }
  return null;
}

/** Where a skill lands for a harness. */
export function skillTargetPath(harness: Harness, name: string, projectRoot?: string): string {
  switch (harness) {
    case 'claude-code':
      return join(TARGET_DIRS['claude-code'][0], name, 'SKILL.md');
    case 'codex':
      return join(TARGET_DIRS.codex[0], name, 'SKILL.md');
    case 'codex-agents':
      return join(TARGET_DIRS['codex-agents'][0], name, 'SKILL.md');
    case 'opencode':
      return join(TARGET_DIRS.opencode[0], name, 'SKILL.md');
    case 'cline':
      // Cline rules are flat, numbered files.
      return join(TARGET_DIRS.cline[0], `${name}.md`);
    case 'puku-cli':
      return join(TARGET_DIRS['puku-cli'][0], name, 'SKILL.md');
    case 'agentsmd':
      return join(projectRoot ?? process.cwd(), 'AGENTS.md');
  }
}

/** Where an agent lands for a harness. */
export function agentTargetPath(harness: Harness, name: string, projectRoot?: string): string {
  switch (harness) {
    case 'claude-code':
      return join(TARGET_DIRS['claude-code'][1], `${name}.md`);
    case 'opencode':
      return join(TARGET_DIRS.opencode[1], `${name}.md`);
    case 'agentsmd':
      return join(projectRoot ?? process.cwd(), 'AGENTS.md');
    default:
      throw new Error(`install_agents is not supported for harness '${harness}'.`);
  }
}

/** The library path a symlink should point at. */
export function symlinkSource(kind: 'skill' | 'agent', libraryRoot: string, libPath: string): string {
  return join(libraryRoot, libPath);
}

function ensureDir(p: string): void {
  mkdirSync(p, { recursive: true });
}

/**
 * Is `p` a symlink?
 *
 * `existsSync` follows a link, so a link whose target is gone reads as
 * absent. `lstat` sees the link itself.
 */
function isSymlink(p: string): boolean {
  try {
    return lstatSync(p).isSymbolicLink();
  } catch {
    return false;
  }
}

function writeSymlink(target: string, source: string): void {
  ensureDir(join(target, '..'));
  symlinkSync(source, target);
}

function writeCopy(target: string, source: string): void {
  ensureDir(join(target, '..'));
  copyFileSync(source, target);
}

/** Copy the supporting files of a skill alongside its SKILL.md. */
function copyBundle(destDir: string, srcDir: string): void {
  ensureDir(destDir);
  for (const name of readdirSync(srcDir)) {
    if (name === 'SKILL.md') continue;
    const src = join(srcDir, name);
    const dst = join(destDir, name);
    if (statSync(src).isDirectory()) {
      cpSync(src, dst, { recursive: true });
    } else {
      copyFileSync(src, dst);
    }
  }
}

export interface InstallSkillArgs {
  harness: Harness;
  name: string;
  id: string;
  description: string;
  allowed_tools?: string[];
  libPath: string;
  skillMdAbs: string;
  libraryRoot: string;
  mode: Mode;
  apply: boolean;
  overwrite: boolean;
  projectRoot?: string;
}

/**
 * Install one skill as a section in a shared `AGENTS.md`.
 *
 * `AGENTS.md` is one file that many skills live in, so the "target
 * exists" rule cannot be "the file exists" -- that would refuse the
 * second skill. Instead each skill gets a marked section, and the file
 * is appended to.
 */
function installAgentsmdSkill(a: InstallSkillArgs, target: string): InstallTarget {
  const section = emitAgentsmdSection(a.name, a.description, readBodyText(a.skillMdAbs));
  const marker = agentsmdMarker(a.name);

  let existing = '';
  if (existsSync(target)) {
    existing = readFileSync(target, 'utf-8');
  }

  const already = existing.includes(marker);
  if (already && !a.overwrite) {
    return {
      harness: 'agentsmd',
      kind: 'skill',
      id: a.id,
      name: a.name,
      path: target,
      action: 'write',
      status: 'skipped',
      reason:
        'AGENTS.md already has a section for this skill; ' +
        'pass overwrite=true to replace it',
    };
  }

  if (!a.apply) {
    return {
      harness: 'agentsmd',
      kind: 'skill',
      id: a.id,
      name: a.name,
      path: target,
      action: 'write',
      status: 'planned',
    };
  }

  try {
    ensureDir(dirname(target));
    if (already) {
      // Replace just this skill's section, leaving the rest of the
      // file -- including other skills' sections -- alone.
      writeFileSync(target, replaceSection(existing, marker, section), 'utf-8');
    } else {
      const prefix = existing && !existing.endsWith('\n') ? existing + '\n' : existing;
      writeFileSync(target, prefix + section, 'utf-8');
    }
  } catch (e) {
    return {
      harness: 'agentsmd',
      kind: 'skill',
      id: a.id,
      name: a.name,
      path: target,
      action: 'write',
      status: 'error',
      reason: e instanceof Error ? e.message : String(e),
    };
  }

  return {
    harness: 'agentsmd',
    kind: 'skill',
    id: a.id,
    name: a.name,
    path: target,
    action: 'write',
    status: 'written',
    dropped_keys: [],
    sidecars: [],
  };
}

export function installSkill(a: InstallSkillArgs): InstallTarget {
  const target = skillTargetPath(a.harness, a.name, a.projectRoot);
  const err = checkTarget(a.harness, target, a.projectRoot);
  if (err) {
    return {
      harness: a.harness,
      kind: 'skill',
      id: a.id,
      name: a.name,
      path: target,
      action: 'write',
      status: 'error',
      reason: err,
    };
  }

  // AGENTS.md is a shared file, not one file per skill. It gets its
  // own path through the function: each skill is a marked section,
  // appended, so a second install does not overwrite the first.
  if (a.harness === 'agentsmd') {
    return installAgentsmdSkill(a, target);
  }

  // Cline rules are plain markdown, so a symlink to the library's
  // SKILL.md would carry frontmatter Cline cannot read.
  const useSymlink = a.mode === 'symlink' && a.harness !== 'cline';

  // A symlink replaces the skill *directory*, not the SKILL.md inside
  // it. The directory is what the harness looks for, and linking the
  // whole thing keeps the supporting files in sync too.
  //
  // `target` is `<dir>/<name>/SKILL.md` for every directory-style
  // harness, so the link path is its parent -- NOT `<parent>/<name>`,
  // which would nest the link one level too deep.
  const linkPath = useSymlink ? dirname(target) : target;

  // `existsSync` resolves *through* a symlink, so a link whose target
  // has gone missing would look absent -- and the install would then
  // fail on the existing link. `lstat` sees the link itself.
  const exists = existsSync(linkPath) || isSymlink(linkPath);
  if (exists && !a.overwrite) {
    return {
      harness: a.harness,
      kind: 'skill',
      id: a.id,
      name: a.name,
      path: linkPath,
      action: useSymlink ? 'symlink' : 'write',
      status: 'skipped',
      reason: 'target already exists; pass overwrite=true to replace it',
    };
  }

  if (!a.apply) {
    return {
      harness: a.harness,
      kind: 'skill',
      id: a.id,
      name: a.name,
      path: linkPath,
      action: useSymlink ? 'symlink' : 'write',
      status: 'planned',
    };
  }

  try {
    if (useSymlink) {
      // Remove the link itself. Removing the file *inside* it would
      // delete the library's real SKILL.md.
      if (isSymlink(linkPath)) {
        unlinkSync(linkPath);
      } else if (exists) {
        rmSync(linkPath, { force: true, recursive: true });
      }
      ensureDir(dirname(linkPath));
      symlinkSync(a.libraryRoot + sep + a.libPath, linkPath);
      return {
        harness: a.harness,
        kind: 'skill',
        id: a.id,
        name: a.name,
        path: linkPath,
        action: 'symlink',
        status: 'written',
      };
    }

    if (exists) rmSync(target, { force: true, recursive: false });
    ensureDir(dirname(target));
    const emitted = emitSkill(a.harness, {
      name: a.name,
      description: a.description,
      allowed_tools: a.allowed_tools,
    });
    const body = readBodyText(a.skillMdAbs);
    writeFileSync(target, emitted.content + body, 'utf-8');
    const sidecars: InstallTarget['sidecars'] = [];
    if (a.harness === 'codex-agents') {
      const sidecar = join(join(target, '..'), 'agents', 'openai.yaml');
      ensureDir(join(sidecar, '..'));
      writeFileSync(sidecar, emitOpenAIAgentYaml({ name: a.name, description: a.description }), 'utf-8');
      sidecars.push({ path: sidecar, action: 'write', status: 'written' });
    }
    // Copy the supporting files alongside the rewritten SKILL.md.
    const srcDir = join(a.skillMdAbs, '..');
    try {
      copyBundle(join(target, '..'), srcDir);
    } catch {
      /* a skill with no supporting files is fine */
    }
    return {
      harness: a.harness,
      kind: 'skill',
      id: a.id,
      name: a.name,
      path: target,
      action: 'write',
      status: 'written',
      dropped_keys: emitted.dropped_keys,
      sidecars,
    };
  } catch (e) {
    return {
      harness: a.harness,
      kind: 'skill',
      id: a.id,
      name: a.name,
      path: target,
      action: useSymlink ? 'symlink' : 'write',
      status: 'error',
      reason: e instanceof Error ? e.message : String(e),
    };
  }
}

export interface InstallAgentArgs {
  harness: Harness;
  name: string;
  id: string;
  description: string;
  tools?: string[];
  model?: string;
  mode?: string;
  agentAbs: string;
  libraryRoot: string;
  libPath: string;
  installMode: Mode;
  apply: boolean;
  overwrite: boolean;
  projectRoot?: string;
}

export function installAgent(a: InstallAgentArgs): InstallTarget {
  if (a.harness === 'cline') {
    return {
      harness: a.harness,
      kind: 'agent',
      id: a.id,
      name: a.name,
      path: '',
      action: 'write',
      status: 'error',
      reason:
        "install_agents is not supported for harness 'cline' — Cline has no agent mechanism. " +
        'Use install_skills for Cline instead, which writes plain-markdown rules to ~/.clinerules/.',
    };
  }
  const target = agentTargetPath(a.harness, a.name, a.projectRoot);
  const err = checkTarget(a.harness, target, a.projectRoot);
  if (err) {
    return {
      harness: a.harness,
      kind: 'agent',
      id: a.id,
      name: a.name,
      path: target,
      action: 'write',
      status: 'error',
      reason: err,
    };
  }

  const exists = existsSync(target);
  if (exists && !a.overwrite) {
    return {
      harness: a.harness,
      kind: 'agent',
      id: a.id,
      name: a.name,
      path: target,
      action: 'write',
      status: 'skipped',
      reason: 'target already exists; pass overwrite=true to replace it',
    };
  }

  if (!a.apply) {
    return {
      harness: a.harness,
      kind: 'agent',
      id: a.id,
      name: a.name,
      path: target,
      action: 'write',
      status: 'planned',
    };
  }

  try {
    if (exists) rmSync(target, { force: true });
    ensureDir(join(target, '..'));
    const emitted = emitAgent(a.harness, {
      name: a.name,
      description: a.description,
      tools: a.tools,
      model: a.model,
      mode: a.mode,
    });
    const body = readBodyText(a.agentAbs);
    writeFileSync(target, emitted.content + body, 'utf-8');
    return {
      harness: a.harness,
      kind: 'agent',
      id: a.id,
      name: a.name,
      path: target,
      action: 'write',
      status: 'written',
      dropped_keys: emitted.dropped_keys,
    };
  } catch (e) {
    return {
      harness: a.harness,
      kind: 'agent',
      id: a.id,
      name: a.name,
      path: target,
      action: 'write',
      status: 'error',
      reason: e instanceof Error ? e.message : String(e),
    };
  }
}

/** The body of a document, without its frontmatter block. */
export function readBodyText(path: string): string {
  let text = '';
  try {
    text = readFileSync(path, 'utf-8');
  } catch {
    return '';
  }
  const m = /^\s*---\s*\n([\s\S]*?)\n---\s*\n?/.exec(text);
  return m ? text.slice(m[0].length) : text;
}

/**
 * Where an installed skill lives on disk, for removal.
 *
 * A symlink install replaces the skill *directory* with a link; a copy
 * install puts the rewritten `SKILL.md` and the supporting files inside
 * that same directory. Removing the directory handles both -- and a
 * symlink is removed as a link, so the library's own files are never
 * touched.
 *
 * `AGENTS.md` is shared by many skills, so there is no single path to
 * remove; that case is refused with an explanation rather than deleting
 * the whole file.
 */
export function uninstallSkillPath(
  harness: Harness,
  name: string,
  projectRoot?: string,
): { path: string; error?: string } {
  if (harness === 'agentsmd') {
    return {
      path: '',
      error:
        'AGENTS.md is a shared file, so one skill has no path of its own to ' +
        'remove. Delete its section from the file instead -- the section is ' +
        `marked '<!-- skills-library:${name} -->'.`,
    };
  }
  const target = skillTargetPath(harness, name, projectRoot);
  if (harness === 'cline') {
    // Cline rules are flat files, one per skill.
    return { path: target };
  }
  return { path: dirname(target) };
}

/**
 * Remove an installed skill or agent.
 *
 * A symlink whose target is outside the library is refused: the caller
 * may have put something there, and deleting it is not this tool's
 * call.
 */
export function uninstallTarget(
  target: string,
  apply: boolean,
  libraryRoot: string,
): { status: 'planned' | 'removed' | 'skipped' | 'error'; reason?: string } {
  if (!existsSync(target) && !isSymlink(target)) {
    return { status: 'skipped', reason: 'nothing installed at that path' };
  }
  let isLink = false;
  let linkTarget = '';
  try {
    const st = lstatSync(target);
    isLink = st.isSymbolicLink();
    if (isLink) linkTarget = readlinkSync(target);
  } catch {
    /* fall through */
  }
  if (isLink) {
    const abs = isAbsolute(linkTarget) ? linkTarget : resolve(target, '..', linkTarget);
    if (!isInside(libraryRoot, abs)) {
      return {
        status: 'error',
        reason: `Refusing to remove ${target}: it is a symlink pointing outside the library (${abs}).`,
      };
    }
  }
  if (!apply) return { status: 'planned' };
  try {
    rmSync(target, { force: true, recursive: true });
    return { status: 'removed' };
  } catch (e) {
    return { status: 'error', reason: e instanceof Error ? e.message : String(e) };
  }
}

/** The file a skill lives in, for a harness. */
export function skillEntryPath(harness: Harness, name: string): string {
  return skillTargetPath(harness, name);
}
