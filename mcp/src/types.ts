/**
 * The shape of `mcp/data/index.json`, as the TypeScript server sees it.
 *
 * The index is the single shared artifact: the Python fallback server and
 * this server both read it, and both must produce byte-identical answers
 * for the same query. Keeping the types here — rather than inline in the
 * loader — means the loader, the search engine and the tool layer all
 * agree on the field names.
 */

export type Kind = 'skill' | 'agent';
export type Tier = 1 | 2 | 3;

export interface PromptSignals {
  phrases: string[];
  all_of: string[][];
  any_of: string[];
}

export interface SkillFrontmatter {
  name: string;
  description: string;
  allowed_tools: string[];
  disable_model_invocation: boolean;
  user_invocable: boolean;
  license: string;
  version: string;
  compatibility: string;
  metadata: Record<string, unknown>;
  prompt_signals: PromptSignals;
  parse_ok: boolean;
  parse_error: string | null;
  raw_keys: string[];
}

export interface AgentFrontmatter {
  name: string;
  description: string;
  tools: string[];
  model: string;
  mode: string;
  permission: unknown;
  metadata: Record<string, unknown>;
  prompt_signals: PromptSignals;
  parse_ok: boolean;
  parse_error: string | null;
  raw_keys: string[];
}

export interface BundleRef {
  target: string;
  resolves: boolean;
}

export interface BundleFile {
  path: string;
  bytes: number;
}

export interface Bundle {
  file_count: number;
  total_bytes: number;
  files: BundleFile[];
  refs: BundleRef[];
  refs_total: number;
  refs_resolved: number;
  refs_dangling: number;
}

export interface Tokens {
  name: string[];
  desc: string[];
  name_bigrams: string[];
}

export interface SkillRecord {
  id: string;
  kind: 'skill';
  name: string;
  title: string;
  desc: string;
  desc_source: 'yaml' | 'body';
  path: string;
  skill_md: string;
  abs_path: string;
  source: string;
  copies: number;
  locale_only: boolean;
  rescued_from_tmp: boolean;
  tier: Tier;
  domain: string;
  frontmatter: SkillFrontmatter;
  bundle: Bundle;
  tokens: Tokens;
}

export interface AgentRecord {
  id: string;
  kind: 'agent';
  name: string;
  title: string;
  desc: string;
  desc_source: 'yaml' | 'body';
  path: string;
  abs_path: string;
  source: string;
  copies: number;
  ensemble: string;
  tier: Tier;
  domain: string;
  frontmatter: AgentFrontmatter;
  bundle: Bundle;
  tokens: Tokens;
}

export type Entry = SkillRecord | AgentRecord;

export interface DomainEntry {
  name: string;
  skill_count: number;
  skills: string[];
  tier: Tier;
}

export interface TaskRow {
  task: string;
  skills: string[];
  agents: string[];
  notes: string;
  /**
   * The row's content-token sets, one per alternative -- the row's
   * tokens with its leading verb dropped. Computed by the index
   * builder so both servers match a row the same way.
   */
  content?: string[][];
}

export interface HeldAside {
  name: string;
  orchestrator: string;
  reason: string;
  path: string;
  source: string;
}

export interface LibraryIndex {
  schema_version: number;
  generated_at: string;
  /**
   * There is no absolute library root in the index. The index is
   * portable: the server resolves every path against its own root at
   * runtime, so the index never records where it was built.
   */
  source_index: {
    path: string;
    sha256: string;
    skills: number;
    agents: number;
  };
  counts: {
    skills: number;
    agents: number;
    held_aside: number;
    by_tier: Record<string, number>;
    skill_by_tier: Record<string, number>;
  };
  packs: string[];
  core_domains: string[];
  domains: DomainEntry[];
  tasks: TaskRow[];
  task_index_notes: { rows: number; dropped: unknown[] };
  skills: SkillRecord[];
  agents: AgentRecord[];
  held_aside: HeldAside[];
  search: {
    fields: string[];
    tokenizer_version: number;
    stopwords: string[];
    postings: Record<string, Record<string, string[]>>;
  };
}

/** One search hit, as returned by `search_library`. */
export interface SearchResult {
  id: string;
  kind: Kind;
  name: string;
  title: string;
  description: string;
  tier: Tier;
  domain: string;
  score: number;
  matched_on: string[];
  path: string;
  frontmatter?: unknown;
}

export interface SearchResponse {
  query: string;
  /** The size of the match set: entries that passed scoring and coverage. */
  total_matched: number;
  /** How many of the matched entries the relevance floor dropped. */
  filtered_out: number;
  returned: number;
  truncated: boolean;
  note: string;
  results: SearchResult[];
  /**
   * The cursor for the next page.
   *
   * Only under `2026-07-28`, and only when there is a next page.
   * The older revision has no cursor, and the field is absent there --
   * a client reading the older revision must not find a field it has
   * never heard of.
   */
  next_cursor?: string;
  /** The cursor no longer points at a result: the library changed. */
  cursor_stale?: boolean;
}
