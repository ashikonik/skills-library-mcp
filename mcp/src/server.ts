/**
 * The tool surface — 8 tools, transport-independent.
 *
 * The shape follows the library's own `skills/build-mcp-server/SKILL.md`
 * §Phase 3 Pattern B: a *search + execute* pair rather than one
 * one-per-skill tool. Read tools and write tools are separate, per the
 * Anthropic Directory rule, so a client can allow `search_library` and
 * `get_skill` without also allowing `install_skills`.
 *
 * Descriptions are scope statements, never behavioural directives. "Not
 * covered by `get_skill`" tells a model what a tool does not do;
 * "Use `get_skill` instead" tells it what to do, which is the model's
 * job, not the schema's.
 */
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { readFileSync, existsSync, statSync, lstatSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { SearchIndex } from './search.js';
import type { LibraryIndex, Entry, SkillRecord, AgentRecord } from './types.js';
import { libraryRoot } from './index-loader.js';
import { LiveIndex } from './live-index.js';
import {
  installSkill,
  installAgent,
  uninstallTarget,
  uninstallSkillPath,
  agentTargetPath,
  skillTargetPath,
  checkTarget,
  type Mode,
} from './installers.js';
import type { Harness } from './frontmatter.js';
import { installRevisionHandlers, installRevisionResultFields, installSkillsExtension, RevisionState } from './revision.js';
import { decodeCursor, cursorMatches, type Cursor } from './protocol.js';
import { FilterError } from './filters.js';
import { defaultPolicy, describePolicy, loadPolicy, permit, refusalFields, type Policy } from './policy.js';
import { recordInstall, forgetInstall, recordsFor } from './manifest.js';

export const DEFAULT_BUNDLE_BYTES = 200_000;
export const MAX_BUNDLE_BYTES = 2_000_000;

const HARNESSES = [
  'claude-code',
  'codex',
  'codex-agents',
  'opencode',
  'cline',
  'puku-cli',
  'agentsmd',
] as const;

/**
 * The most targets one install call may touch. An explicit `ids` list
 * is capped at the same number; a tier install is capped by it too,
 * and reports the truncation rather than silently dropping the tail.
 */
const MAX_INSTALL_TARGETS = 50;

export interface Deps {
  index: LibraryIndex;
  indexPath?: string;
}

interface ToolTextResult {
  [key: string]: unknown;
  content: Array<{ type: 'text'; text: string }>;
  structuredContent?: Record<string, unknown>;
  isError?: boolean;
}

function asError(message: string): ToolTextResult {
  return { content: [{ type: 'text', text: message }], isError: true };
}

function asText(payload: unknown): ToolTextResult {
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
  const result: ToolTextResult = { content: [{ type: 'text', text }] };
  if (payload !== null && typeof payload === 'object' && !Array.isArray(payload)) {
    result.structuredContent = payload as Record<string, unknown>;
  }
  return result;
}

/** Resolve an id (`skill:x` / `agent:x`) or a bare name to an entry. */
function resolveEntry(index: LibraryIndex, id: string): Entry | undefined {
  if (index.skills.some((s) => s.id === id) || index.agents.some((a) => a.id === id)) {
    return [...index.skills, ...index.agents].find((e) => e.id === id);
  }
  return [...index.skills, ...index.agents].find((e) => e.name === id);
}

/**
 * Would this install replace something that is already there?
 *
 * The fact the policy needs. It is true when the caller asked to
 * overwrite *and* there is something to overwrite -- a request to
 * replace nothing is not a replacement.
 */
function overwriteRequested(
  index: LibraryIndex,
  harness: Harness,
  ids: string[] | undefined,
  tier: number | undefined,
  mode: Mode,
  projectRoot: string,
): boolean {
  let wanted = ids ?? [];
  if (wanted.length === 0) {
    if (tier === undefined) return false;
    wanted = index.skills.filter((s) => s.tier === tier).map((s) => s.id);
  }
  for (const id of wanted) {
    const e = resolveEntry(index, id);
    if (!e || e.kind !== 'skill') continue;
    let path: string;
    try {
      path = skillTargetPath(harness, e.name, projectRoot);
    } catch {
      continue;
    }
    const link = mode === 'symlink' ? dirname(path) : path;
    if (existsSync(link) || isSymlinkPath(link)) return true;
  }
  return false;
}

/** Is `p` a symlink? `existsSync` follows a link; `lstat` sees it. */
function isSymlinkPath(p: string): boolean {
  try {
    return lstatSync(p).isSymbolicLink();
  } catch {
    return false;
  }
}

export function createServer(deps: Deps): McpServer {
  // The index, and the search engine over it, are refreshed when the
  // index *file* changes.
  //
  // A long-running server outlives the build that produced its index.
  // Serving the stale one is a quiet failure: `get_agent` reports "not
  // found" for an agent that is on disk, and `search_library` cannot
  // find what the caller just added. The file's mtime and size are
  // checked before each tool call, so the reload costs one `stat`.
  //
  // The check is on the file, not on in-memory state, because the file
  // is the shared artifact -- the Python server reads the same path and
  // the two must never disagree about what the library contains.
  const live = new LiveIndex(deps.indexPath, deps.index);
  let index = live.current();
  let search = new SearchIndex(index);
  // The error from a failed reload, if the last one failed. The
  // previous index stays in service and the error is reported, so a
  // half-written index degrades the answer rather than removing it.
  let liveError: string | null = null;

  // The tool descriptions quote the library's size, and the SDK
  // captures a description string when a tool is registered. So the
  // descriptions have to be *rewritten* when the index moves, or the
  // server would claim a size the library no longer has.
  //
  // The rewrite is a callback the index refresh calls, set after the
  // tools are registered.
  let rewriteDescriptions: (() => void) | null = null;

  /** Reload the index and the search engine if the file has changed. */
  const refresh = (): void => {
    const next = live.current();
    if (next === index) return;
    // The search engine is built over the new index. If that fails --
    // an index written halfway, a malformed entry -- the old index is
    // kept and the error is remembered. Serving the previous index is
    // better than serving nothing: the caller gets answers, and the
    // error is reported rather than thrown at every tool call.
    try {
      search = new SearchIndex(next);
    } catch (e) {
      liveError = e instanceof Error ? e.message : String(e);
      return;
    }
    index = next;
    liveError = null;
    // The counts in the descriptions now have to match the new index.
    rewriteDescriptions?.();
  };

  const root = libraryRoot();

  // The policy in force, and the error from loading it, if any.
  //
  // A malformed policy file is an error, not a silent fall back to the
  // defaults: the file was written to say something, and ignoring it
  // would make the server's behaviour depend on a typo. The error is
  // carried so `policy_get` can report it.
  const projectRoot = process.env.SKILLS_LIBRARY_PROJECT ?? process.cwd();
  let policy: Policy = defaultPolicy();
  let policyError: string | null = null;
  try {
    policy = loadPolicy(projectRoot);
  } catch (e) {
    policy = defaultPolicy();
    policyError = e instanceof Error ? e.message : String(e);
  }

  // The library's size, as the index reports it.
  //
  // The instructions and the tool descriptions say how big the library
  // is, and the library grows -- that is what it is for. A literal count
  // goes stale the first time somebody adds a skill, and a stale count
  // in a tool description is not cosmetic: it is a claim the server
  // makes to the model about its own coverage, and the agreement gate
  // compares it byte for byte against the Python fallback. So the count
  // is read from the index, in both implementations, and the two cannot
  // drift apart.
  // These are read through getters rather than captured, so a
  // description never claims a count the library no longer has. The
  // agreement gate compares the descriptions byte for byte against the
  // Python fallback, and the two read the same index -- so a count
  // that moved would show up there rather than silently here.
  const nSkills = (): string => String(live.current().skills.length);
  const nAgents = (): string => String(live.current().agents.length);
  // The pack count, read from the index for the same reason: the pack
  // list grows, and a literal "six" in a tool description would go
  // stale the first time somebody registers an eighth pack.
  const nPacks = (): string => String(live.current().packs.length);

  const server = new McpServer(
    { name: 'skills-library', version: '1.0.0' },
    {
      instructions:
        `Searches a local library of ${nSkills()} skills and ${nAgents()} agents, and installs them into ` +
        'coding harnesses. Start with search_library to find candidates, then get_skill ' +
        'or get_agent to read one. install_skills and install_agents make a skill ' +
        'auto-activate in the target harness; both are dry runs unless apply is true.',
    },
  );

  // --------------------------------------------------- the live index
  //
  // Every tool refreshes the index before it runs, so a server that
  // has been running across a rebuild answers from the library as it
  // is now rather than as it was when the process started.
  //
  // The wrapper is installed here, once, rather than by editing the
  // ten handlers: a refresh that has to be remembered in ten places is
  // a refresh that will be forgotten in the eleventh.
  const registerTool = server.registerTool.bind(server);
  (server as unknown as { registerTool: unknown }).registerTool = (
    ...args: unknown[]
  ): unknown => {
    const [name, config, handler] = args as [
      string,
      unknown,
      ((...a: unknown[]) => unknown) | undefined,
    ];
    if (typeof handler !== 'function') {
      return (registerTool as (...a: unknown[]) => unknown)(...args);
    }
    const wrapped = async (...a: unknown[]): Promise<unknown> => {
      refresh();
      return handler(...a);
    };
    return (registerTool as (...a: unknown[]) => unknown)(name, config, wrapped);
  };

  // ------------------------------------------------------- the revision
  //
  // The protocol revision is negotiated per connection, so it lives in
  // a `RevisionState` rather than in a constant. It is created before
  // the tools are registered because the tools close over it: a tool
  // has to know which revision it is answering under.
  //
  // `installRevisionHandlers` must run *after* the tools are
  // registered -- it wraps the SDK's own `tools/list` and `tools/call`
  // handlers, and there is nothing to wrap until they exist.
  const revision = new RevisionState();

  // ------------------------------------------------------------ 1. search
  server.registerTool(
    'search_library',
    {
      title: 'Search library',
      description:
        'Rank skills and agents by relevance to a query. Returns scored candidates with ' +
        `the terms each matched on. Covers all ${nSkills()} skills and ${nAgents()} agents. ` +
        'Not covered by get_skill, which returns one document in full.',
      inputSchema: {
        query: z.string().min(1).max(500),
        limit: z.number().int().min(1).max(50).default(10),
        kind: z.enum(['skill', 'agent']).optional(),
        tier: z.union([z.literal(1), z.literal(2), z.literal(3)]).optional(),
        domain: z.string().optional(),
        // The provenance filters. A caller that needs to know what may
        // be redistributed asks for it here, rather than filtering the
        // results afterwards.
        source: z.string().optional(),
        license: z.string().optional(),
        verdict: z.enum([
          'redistributable',
          'included-with-terms',
          'fixture',
          'personal',
          'unknown',
        ]).optional(),
        include_body: z.boolean().default(false),
        // The pagination cursor. Under `2026-07-28` it appears in the
        // published schema too; the zod schema cannot change with the
        // revision, so it always accepts the argument and the
        // behaviour below decides whether it is honoured.
        cursor: z.string().optional(),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ query, limit, kind, tier, domain, source, license, verdict, include_body, cursor }) => {
      // The cursor is a `2026-07-28` feature. On the older revision it
      // is not in the published schema, and a client that sends one
      // anyway is speaking a dialect this server does not serve -- the
      // cursor is ignored rather than half-honoured.
      let decoded: Cursor | undefined;
      if (revision.current && cursor) {
        const c = decodeCursor(cursor);
        if (c && cursorMatches(c, query)) decoded = c;
      }
      let out: ReturnType<typeof search.search>;
      try {
        out = search.search(query, {
          limit,
          kind,
          tier,
          domain,
          source,
          license,
          verdict,
          include_body,
          cursor: decoded?.after,
        });
      } catch (e) {
        // A filter that names nothing is a mistake in the call, not an
        // empty library. The caller is told which filter was wrong and
        // what the valid values are.
        if (e instanceof FilterError) return asError(e.message);
        throw e;
      }

      // The cursor fields belong to `2026-07-28`. On the older
      // revision they are removed: a client reading the old revision
      // must not find a field it has never heard of, and the
      // agreement gate compares the raw payloads.
      if (!revision.current) {
        delete out.nextCursor;
        delete out.cursorStale;
      }
      return asText(out);
    },
  );

  // ---------------------------------------------------------- 2. get_skill
  server.registerTool(
    'get_skill',
    {
      title: 'Get skill',
      description:
        'Returns one skill: its SKILL.md body, parsed frontmatter, and the manifest of ' +
        'its supporting files. Accepts a namespaced id (skill:tdd-workflow) or a bare ' +
        'name. ' +
        'Not covered by get_skill_bundle, which returns the supporting files themselves.',
      inputSchema: {
        id: z.string().min(1),
        include_body: z.boolean().default(true),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ id, include_body }) => {
      const e = resolveEntry(index, id);
      if (!e || e.kind !== 'skill') {
        return asError(
          `Skill '${id}' not found. Use search_library to find valid ids.`,
        );
      }
      const s = e as SkillRecord;
      const abs = join(root, s.skill_md);
      let body = '';
      let body_error = '';
      if (existsSync(abs)) {
        body = readFileSync(abs, 'utf-8');
      } else {
        body_error = `The file ${s.skill_md} is missing from the library tree.`;
      }
      const out = {
        id: s.id,
        kind: 'skill',
        name: s.name,
        title: s.title,
        description: s.desc,
        desc_source: s.desc_source,
        tier: s.tier,
        domain: s.domain,
        path: s.path,
        frontmatter: s.frontmatter,
        // The whole provenance record: who owns it, under what
        // licence, and whether it may be redistributed.
        provenance: s.provenance,
        bundle: {
          file_count: s.bundle.file_count,
          total_bytes: s.bundle.total_bytes,
          refs_total: s.bundle.refs_total,
          refs_resolved: s.bundle.refs_resolved,
          refs_dangling: s.bundle.refs_dangling,
          files: s.bundle.files.map((f) => ({ path: f.path, bytes: f.bytes })),
        },
        body: include_body ? body : undefined,
        body_error: body_error || undefined,
      };
      return asText(out);
    },
  );

  // ---------------------------------------------------------- 3. get_agent
  server.registerTool(
    'get_agent',
    {
      title: 'Get agent',
      description:
        'Returns one agent: its definition body and parsed frontmatter, including its ' +
        'tool allow-list and model. Accepts a namespaced id (agent:code-reviewer) or a ' +
        'bare name. ' +
        'Not covered by install_agents, which writes it into a harness.',
      inputSchema: {
        id: z.string().min(1),
        include_held_aside: z.boolean().default(false),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ id, include_held_aside }) => {
      const e = resolveEntry(index, id);
      if (!e || e.kind !== 'agent') {
        // The 14 agents held aside are reachable when explicitly asked for.
        if (include_held_aside) {
          const held = index.held_aside.find((h) => h.name === id || `agent:${h.name}` === id);
          if (held) {
            const abs = join(root, held.path);
            const body = existsSync(abs) ? readFileSync(abs, 'utf-8') : '';
            return asText({
              id: `agent:${held.name}`,
              kind: 'agent',
              name: held.name,
              held_aside: true,
              orchestrator: held.orchestrator,
              reason: held.reason,
              path: held.path,
              body,
            });
          }
        }
        return asError(
          `Agent '${id}' not found. Use search_library to find valid ids, or pass ` +
            `include_held_aside=true for the 14 agents held aside from the library.` +
            // A failed reload is the one case where "not found" is not
            // the whole story: the entry may be on disk and the
            // server may not have been able to read it. Saying so
            // saves the caller from hunting for an agent that is
            // already there.
            (liveError
              ? ` The index could not be reloaded: ${liveError}`
              : ''),
        );
      }
      const a = e as AgentRecord;
      const abs = join(root, a.path);
      const body = existsSync(abs) ? readFileSync(abs, 'utf-8') : '';
      return asText({
        id: a.id,
        kind: 'agent',
        name: a.name,
        description: a.desc,
        desc_source: a.desc_source,
        tier: a.tier,
        ensemble: a.ensemble,
        path: a.path,
        frontmatter: a.frontmatter,
        // The whole provenance record: who owns it, under what
        // licence, and whether it may be redistributed.
        provenance: a.provenance,
        body,
      });
    },
  );

  // -------------------------------------------------- 4. get_skill_bundle
  server.registerTool(
    'get_skill_bundle',
    {
      title: 'Get skill bundle',
      description:
        "Returns a skill's supporting files. With no files argument it returns the " +
        'manifest only — paths, sizes and which references resolve. With files it ' +
        'returns those files\' contents, up to a byte cap. ' +
        'Not covered by get_skill, which returns the SKILL.md body.',
      inputSchema: {
        id: z.string().min(1),
        files: z.array(z.string()).max(50).optional(),
        max_bytes: z.number().int().min(1).max(MAX_BUNDLE_BYTES).default(DEFAULT_BUNDLE_BYTES),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ id, files, max_bytes }) => {
      const e = resolveEntry(index, id);
      if (!e || e.kind !== 'skill') {
        return asError(`Skill '${id}' not found. Use search_library to find valid ids.`);
      }
      const s = e as SkillRecord;
      const manifest = s.bundle.files.map((f) => ({ path: f.path, bytes: f.bytes }));

      if (!files || files.length === 0) {
        return asText({
          id: s.id,
          name: s.name,
          file_count: s.bundle.file_count,
          total_bytes: s.bundle.total_bytes,
          refs_total: s.bundle.refs_total,
          refs_resolved: s.bundle.refs_resolved,
          refs_dangling: s.bundle.refs_dangling,
          files: manifest,
          note: 'Manifest only. Pass files=["path"] to read contents.',
        });
      }

      const known = new Map(s.bundle.files.map((f) => [f.path, f.bytes]));
      const missing = files.filter((f) => !known.has(f));
      if (missing.length > 0) {
        return asError(
          `'${missing.join("', '")}' is not in the bundle of '${s.id}'. ` +
            `Available paths are listed in the manifest.`,
        );
      }
      const total = files.reduce((n, f) => n + (known.get(f) ?? 0), 0);
      if (total > max_bytes) {
        return asError(
          `Requested files total ${total.toLocaleString('en-US')} bytes; max_bytes is ` +
            `${max_bytes.toLocaleString('en-US')}. The manifest is returned instead — ` +
            `request specific files.`,
        );
      }

      const base = join(root, s.path);
      const contents: Array<{ path: string; bytes: number; content: string }> = [];
      for (const f of files) {
        const abs = join(base, f);
        if (!existsSync(abs)) {
          return asError(`'${f}' is listed in the manifest but missing on disk at ${abs}.`);
        }
        contents.push({
          path: f,
          bytes: known.get(f) ?? 0,
          content: readFileSync(abs, 'utf-8'),
        });
      }
      return asText({ id: s.id, name: s.name, files: contents, total_bytes: total });
    },
  );

  // ------------------------------------------------------- 5. list_library
  server.registerTool(
    'list_library',
    {
      title: 'List library',
      description:
        `Lists the library's structure: its domains, tiers, the ${nPacks()} hand-authored ` +
        'packs, the task-type index, the provenance of every entry, or overall ' +
        'statistics. ' +
        'Not covered by search_library, which ranks entries by relevance to a query.',
      inputSchema: {
        section: z
          .enum(['domains', 'tiers', 'packs', 'tasks', 'stats', 'provenance'])
          .default('stats'),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ section }) => {
      switch (section) {
        case 'domains':
          return asText(
            index.domains.map((d) => ({
              name: d.name,
              skill_count: d.skill_count,
              tier: d.tier,
              skills: d.skills,
            })),
          );
        case 'tiers':
          return asText({
            tier_1_skills: index.packs,
            tier_1_agents: index.agents.filter((a) => a.tier === 1).map((a) => a.name),
            by_tier: index.counts.by_tier,
            note:
              'Tiers bias ranking, they never filter. Every skill and agent stays ' +
              'searchable; a tier only breaks ties among weak, description-only matches.',
          });
        case 'packs':
          return asText({
            packs: index.packs,
            note:
              `The ${nPacks()} hand-authored packs are the highest-quality material in the ` +
              'library and the first thing to reach for.',
          });
        case 'provenance':
          return asText({
            ...index.provenance,
            note:
              'The redistribution verdict per entry. `redistributable` may be shared ' +
              'freely; `included-with-terms` may be shared, but its terms say how; ' +
              '`fixture` and `personal` are never published. ' +
              'Use the `verdict`, `license` and `source` filters on search_library to ' +
              'find the entries of one kind.',
          });
        case 'tasks':
          return asText(
            index.tasks.map((t) => ({
              task: t.task,
              skills: t.skills,
              agents: t.agents,
              notes: t.notes,
            })),
          );
        case 'stats':
        default:
          return asText({
            schema_version: index.schema_version,
            generated_at: index.generated_at,
            // The live root, not the one the index was built at. The
            // index records no root at all: it is portable, and this
            // server is the one that knows where it lives.
            library_root: root,
            counts: index.counts,
            domains: index.domains.length,
            tasks: index.tasks.length,
            held_aside: index.held_aside.length,
            tokenizer_version: index.search.tokenizer_version,
          });
      }
    },
  );

  // --------------------------------------------------- 6. install_skills
  server.registerTool(
    'install_skills',
    {
      title: 'Install skills',
      description:
        'Installs skills into a coding harness so they auto-activate. Writes a ' +
        'symlink into the library by default, so the installed skill stays in sync ' +
        'with the source. Dry run unless apply is true. ' +
        'Not covered by search_library, which finds candidates but writes nothing.',
      inputSchema: {
        harness: z.enum(HARNESSES),
        ids: z.array(z.string().min(1)).min(1).max(50).optional(),
        mode: z.enum(['symlink', 'copy']).default('symlink'),
        tier: z.union([z.literal(1), z.literal(2), z.literal(3)]).optional(),
        apply: z.boolean().default(false),
        overwrite: z.boolean().default(false),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ harness, ids, mode, tier, apply, overwrite }) => {
      const targets = [];
      const errors: string[] = [];

      // `ids` and `tier` are two ways to say what to install. Either
      // one alone is enough; neither one is enough.
      if ((!ids || ids.length === 0) && tier === undefined) {
        return asError(
          "install_skills needs 'ids' or 'tier'. Pass ids to install " +
            'specific skills, or tier to install a whole tier.',
        );
      }

      let wanted = ids ?? [];
      // The policy, before any of it happens. A dry run and a write
      // are different operations: a plan writes nothing, so it needs
      // no authorisation -- refusing it would make the tool useless,
      // since the plan is how a caller finds out what a write would
      // do.
      const refusal = permit(
        apply ? 'install.skills' : 'install.skills.plan',
        {
          apply,
          overwrite,
          args: {
            overwrite_requested: overwriteRequested(
              index,
              harness as Harness,
              ids,
              tier,
              mode as Mode,
              projectRoot,
            ),
          },
        },
        policy,
      );
      if (refusal) return asText(refusalFields(refusal));

      if (wanted.length === 0) {
        // A tier install. Tier 3 holds 701 skills, so the batch is
        // capped the way an explicit id list is -- and the truncation
        // is reported rather than silent.
        const tierSkills = index.skills.filter((s) => s.tier === tier);
        if (tierSkills.length > MAX_INSTALL_TARGETS) {
          errors.push(
            `Tier ${tier} holds ${tierSkills.length} skills; only the first ` +
              `${MAX_INSTALL_TARGETS} are planned. Install the rest by id.`,
          );
        }
        wanted = tierSkills.slice(0, MAX_INSTALL_TARGETS).map((s) => s.id);
      }

      for (const id of wanted) {
        const e = resolveEntry(index, id);
        if (!e || e.kind !== 'skill') {
          errors.push(`Skill '${id}' not found. Use search_library to find valid ids.`);
          continue;
        }
        const s = e as SkillRecord;
        if (tier !== undefined && s.tier !== tier) {
          // A tier given alongside ids is a filter. Silently returning
          // nothing would look like the skill was installed, so say
          // what happened.
          errors.push(
            `Skill '${id}' is tier ${s.tier}, not tier ${tier}; it was skipped.`,
          );
          continue;
        }
        const t = installSkill({
          harness: harness as Harness,
          name: s.name,
          id: s.id,
          description: s.desc,
          allowed_tools: s.frontmatter.allowed_tools,
          libPath: s.path,
          skillMdAbs: join(root, s.skill_md),
          libraryRoot: root,
          mode: mode as Mode,
          apply,
          overwrite,
        });
        targets.push(t);
      }
      const skipped = targets.filter((t) => t.status === 'skipped').length;
      const written = targets.filter((t) => t.status === 'written').length;
      const note = apply
        ? `${written} written, ${skipped} skipped.`
        : `Dry run — nothing was written. ${targets.length} target(s) planned.`;
      // Every write is recorded, so a later uninstall knows what this
      // server put there -- and only that. A write that was refused is
      // not recorded: nothing was written.
      if (apply) {
        for (const t of targets) {
          if (t.status !== 'written') continue;
          const err = recordInstall(
            projectRoot,
            harness,
            t.kind,
            t.name,
            t.path,
            t.action,
          );
          if (err) errors.push(err);
        }
      }
      return asText({
        harness,
        mode,
        apply,
        targets,
        written,
        skipped,
        errors,
        note,
      });
    },
  );

  // --------------------------------------------------- 7. install_agents
  server.registerTool(
    'install_agents',
    {
      title: 'Install agents',
      description:
        'Installs agent definitions into a coding harness. Each harness receives the ' +
        'frontmatter dialect it expects. Dry run unless apply is true. ' +
        'Not covered by get_agent, which returns a definition without writing it.',
      inputSchema: {
        harness: z.enum(HARNESSES),
        ids: z.array(z.string().min(1)).min(1).max(50),
        mode: z.enum(['symlink', 'copy']).default('copy'),
        apply: z.boolean().default(false),
        overwrite: z.boolean().default(false),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ harness, ids, mode, apply, overwrite }) => {
      const targets = [];
      const errors: string[] = [];

      const refusal = permit(
        apply ? 'install.agents' : 'install.agents.plan',
        { apply, overwrite },
        policy,
      );
      if (refusal) return asText(refusalFields(refusal));

      for (const id of ids) {
        const e = resolveEntry(index, id);
        if (!e || e.kind !== 'agent') {
          errors.push(`Agent '${id}' not found. Use search_library to find valid ids.`);
          continue;
        }
        const a = e as AgentRecord;
        const t = installAgent({
          harness: harness as Harness,
          name: a.name,
          id: a.id,
          description: a.desc,
          tools: a.frontmatter.tools,
          model: a.frontmatter.model,
          mode: a.frontmatter.mode,
          agentAbs: join(root, a.path),
          libraryRoot: root,
          libPath: a.path,
          installMode: mode as Mode,
          apply,
          overwrite,
        });
        targets.push(t);
      }
      const skipped = targets.filter((t) => t.status === 'skipped').length;
      const written = targets.filter((t) => t.status === 'written').length;
      const note = apply
        ? `${written} written, ${skipped} skipped.`
        : `Dry run — nothing was written. ${targets.length} target(s) planned.`;
      if (apply) {
        for (const t of targets) {
          if (t.status !== 'written') continue;
          const err = recordInstall(
            projectRoot,
            harness,
            t.kind,
            t.name,
            t.path,
            t.action,
          );
          if (err) errors.push(err);
        }
      }
      return asText({
        harness,
        mode,
        apply,
        targets,
        written,
        skipped,
        errors,
        note,
      });
    },
  );

  // ------------------------------------------------- 8. uninstall_skills
  server.registerTool(
    'uninstall_skills',
    {
      title: 'Uninstall skills',
      description:
        'Removes skills this server installed from a harness. Refuses to remove a ' +
        'symlink that points outside the library. Dry run unless apply is true. ' +
        'Not covered by install_skills, which installs rather than removes.',
      inputSchema: {
        harness: z.enum(HARNESSES),
        names: z.array(z.string().min(1)).min(1).max(50),
        apply: z.boolean().default(false),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ harness, names, apply }) => {
      const refusal = permit(
        apply ? 'uninstall.skills' : 'uninstall.skills.plan',
        { apply },
        policy,
      );
      if (refusal) return asText(refusalFields(refusal));

      const targets = [];
      for (const name of names) {
        const { path, error } = uninstallSkillPath(harness as Harness, name);
        if (error) {
          targets.push({ name, path, status: 'error' as const, reason: error });
          continue;
        }
        const r = uninstallTarget(path, apply, root);
        targets.push({ name, path, ...r });
      }
      const removed = targets.filter((t) => t.status === 'removed').length;
      const note = apply
        ? `${removed} removed.`
        : `Dry run — nothing was removed. ${targets.length} target(s) planned.`;
      return asText({ harness, apply, targets, removed, note });
    },
  );

  // ------------------------------------------------- 9. uninstall_agents
  server.registerTool(
    'uninstall_agents',
    {
      title: 'Uninstall agents',
      description:
        'Removes agents this server installed from a harness. Refuses to remove a ' +
        'file that is not one of ours, so it cannot destroy something else. Dry run ' +
        'unless apply is true. Not covered by install_agents, which installs rather ' +
        'than removes.',
      inputSchema: {
        harness: z.enum(['claude-code', 'opencode', 'agentsmd']),
        names: z.array(z.string().min(1)).min(1).max(50),
        apply: z.boolean().default(false),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: true,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ harness, names, apply }) => {
      const refusal = permit(
        apply ? 'uninstall.agents' : 'uninstall.agents.plan',
        { apply },
        policy,
      );
      if (refusal) return asText(refusalFields(refusal));

      // The manifest is the gate. A file that this server did not
      // write is refused with the `not_ours` wall rather than removed:
      // the harness's agent directory holds other people's agents too,
      // and this tool has no way to know which are which except by
      // having written them.
      const { records, error: manifestError } = recordsFor(projectRoot, harness, 'agent');
      const targets = [];
      for (const name of names) {
        let target: string;
        try {
          target = agentTargetPath(harness as Harness, name, projectRoot);
        } catch (e) {
          targets.push({
            name,
            path: '',
            status: 'error' as const,
            reason: e instanceof Error ? e.message : String(e),
          });
          continue;
        }
        // The whitelist still applies to a removal: this server does
        // not delete files it was never allowed to write.
        const wall = checkTarget(harness as Harness, target, projectRoot);
        if (wall) {
          targets.push({
            name,
            path: target,
            status: 'error' as const,
            wall: wall.wall,
            reason: wall.message,
          });
          continue;
        }
        if (manifestError) {
          targets.push({
            name,
            path: target,
            status: 'error' as const,
            reason: manifestError,
          });
          continue;
        }
        const ours = records.filter((r) => r.path === target);
        if (ours.length === 0) {
          targets.push({
            name,
            path: target,
            status: 'error' as const,
            wall: 'not_ours',
            reason:
              `Refusing to remove ${target}: it is not a file this server ` +
              'installed, so removing it could destroy something else. Remove ' +
              'it yourself if you are sure.',
          });
          continue;
        }
        const r = uninstallTarget(target, apply, root);
        if (r.status === 'removed') forgetInstall(projectRoot, target);
        targets.push({ name, path: target, ...r });
      }
      const removed = targets.filter((t) => t.status === 'removed').length;
      const note = apply
        ? `${removed} removed.`
        : `Dry run — nothing was removed. ${targets.length} target(s) planned.`;
      return asText({ harness, apply, targets, removed, note });
    },
  );

  // ------------------------------------------------------ 10. policy_get
  server.registerTool(
    'policy_get',
    {
      title: 'Get the policy',
      description:
        'Reports the safety rules this server enforces: every rule, its verdict, ' +
        'and why. A project may tighten the policy by denying rule ids in ' +
        '.skills-library/policy.json; the report says which rules the project file ' +
        'tightened. Read-only.',
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => asText(describePolicy(policy, policyError)),
  );

  // ------------------------------------------- the live descriptions
  //
  // The tool descriptions quote the library's size, and the SDK takes
  // a description *string* when a tool is registered. So when the
  // index moves, the descriptions have to be rewritten -- otherwise
  // the server claims a size the library no longer has, which is a
  // claim the model makes about the server's own coverage.
  //
  // The rewrite goes through the SDK's own `update` method, so the
  // list-changed notification the SDK sends is the SDK's.
  rewriteDescriptions = () => {
    const registered = (server as unknown as {
      _registeredTools?: Record<string, { update?: (u: { description?: string }) => void }>;
    })._registeredTools;
    if (!registered) return;
    const update = (name: string, description: string): void => {
      registered[name]?.update?.({ description });
    };
    update(
      'search_library',
      'Rank skills and agents by relevance to a query. Returns scored candidates with ' +
        `the terms each matched on. Covers all ${nSkills()} skills and ${nAgents()} agents. ` +
        'Not covered by get_skill, which returns one document in full.',
    );
    update(
      'list_library',
      `Lists the library's structure: its domains, tiers, the ${nPacks()} hand-authored ` +
        'packs, the task-type index, the provenance of every entry, or overall ' +
        'statistics. ' +
        'Not covered by search_library, which ranks entries by relevance to a query.',
    );
  };

  // ------------------------------------------------------- the revision
  //
  // The handlers are installed last: they wrap the SDK's own
  // `tools/list` and `tools/call` handlers, and there is nothing to
  // wrap until the tools exist.
  installRevisionHandlers(server.server, revision);
  installRevisionResultFields(server.server, revision);

  // The Skills extension. It goes on last because it also uses the
  // fallback handler, and it has to be *after* the revision handlers so
  // that the fallback chain is: skills extension, then the revision's
  // `server/discover`, then the SDK's own.
  installSkillsExtension(server.server, revision, () => live.current(), libraryRoot());

  return server;
}

/** Exposed for the tests: the agent target path for a harness. */
export { agentTargetPath };
