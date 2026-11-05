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
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { SearchIndex } from './search.js';
import type { LibraryIndex, Entry, SkillRecord, AgentRecord } from './types.js';
import { libraryRoot } from './index-loader.js';
import {
  installSkill,
  installAgent,
  uninstallTarget,
  uninstallSkillPath,
  agentTargetPath,
  type Mode,
} from './installers.js';
import type { Harness } from './frontmatter.js';

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

export function createServer(deps: Deps): McpServer {
  const index = deps.index;
  const search = new SearchIndex(index);
  const root = libraryRoot();

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
  const nSkills = String(index.skills.length);
  const nAgents = String(index.agents.length);
  // The pack count, read from the index for the same reason: the pack
  // list grows, and a literal "six" in a tool description would go
  // stale the first time somebody registers an eighth pack.
  const nPacks = String(index.packs.length);

  const server = new McpServer(
    { name: 'skills-library', version: '1.0.0' },
    {
      instructions:
        `Searches a local library of ${nSkills} skills and ${nAgents} agents, and installs them into ` +
        'coding harnesses. Start with search_library to find candidates, then get_skill ' +
        'or get_agent to read one. install_skills and install_agents make a skill ' +
        'auto-activate in the target harness; both are dry runs unless apply is true.',
    },
  );

  // ------------------------------------------------------------ 1. search
  server.registerTool(
    'search_library',
    {
      title: 'Search library',
      description:
        'Rank skills and agents by relevance to a query. Returns scored candidates with ' +
        `the terms each matched on. Covers all ${nSkills} skills and ${nAgents} agents. ` +
        'Not covered by get_skill, which returns one document in full.',
      inputSchema: {
        query: z.string().min(1).max(500),
        limit: z.number().int().min(1).max(50).default(10),
        kind: z.enum(['skill', 'agent']).optional(),
        tier: z.union([z.literal(1), z.literal(2), z.literal(3)]).optional(),
        domain: z.string().optional(),
        include_body: z.boolean().default(false),
      },
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async ({ query, limit, kind, tier, domain, include_body }) => {
      const out = search.search(query, { limit, kind, tier, domain, include_body });
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
            `include_held_aside=true for the 14 agents held aside from the library.`,
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
        `Lists the library's structure: its domains, tiers, the ${nPacks} hand-authored ` +
        'packs, the task-type index, or overall statistics. ' +
        'Not covered by search_library, which ranks entries by relevance to a query.',
      inputSchema: {
        section: z
          .enum(['domains', 'tiers', 'packs', 'tasks', 'stats'])
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
              `The ${nPacks} hand-authored packs are the highest-quality material in the ` +
              'library and the first thing to reach for.',
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

  return server;
}

/** Exposed for the tests: the agent target path for a harness. */
export { agentTargetPath };
