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
  /** `sha256:<64 lowercase hex>`. Absent for a bundle scanned without a name. */
  digest?: string;
  /** The MIME type of the file, by its extension. */
  mime?: string;
  /** The `skill://` URI of the file. */
  uri?: string;
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

/**
 * The Skills extension's view of one skill, as the *index* records it.
 *
 * Separate from the search record because the two answer different
 * questions. The search record describes the entry as the *index* knows
 * it -- the name it was found under, the description the library
 * recorded. This one describes the entry as the *extension* serves it:
 * under a name that conforms to the Agent Skills rules, with the
 * frontmatter verbatim, and with a complete manifest.
 */
export interface SkillManifest {
  /** The served name. Equal to the record's `name` unless overridden. */
  name: string;
  /** The served description. */
  description: string;
  /** The URI of the skill's `SKILL.md`. */
  uri: string;
  /** Every YAML frontmatter field, unchanged. */
  frontmatter: Record<string, unknown>;
  /** The complete file manifest: every file, exactly once. */
  resources: SkillResource[];
  /** Set when the served name differs from the file's. */
  name_override?: string | null;
  /** Set when the served description was cut. */
  description_truncated?: string | null;
  /** The Agent Skills rules the file broke, if any. */
  problems: string[];
}

/**
 * A skill entry, as the extension *serves* it.
 *
 * The specification's entry is `{uri, frontmatter, resources}`. The
 * served name and description are in the frontmatter -- that is where
 * the specification puts them -- so repeating them at the top level
 * would be a second copy that could disagree with the first.
 *
 * The three extra fields appear only when the server adapted the skill
 * to make it conform: a client that compares the frontmatter against
 * the file it read needs to know that the server changed something.
 */
export interface SkillEntry {
  uri: string;
  frontmatter: Record<string, unknown>;
  resources: SkillResource[];
  name_override?: string | null;
  description_truncated?: string | null;
  problems?: string[];
}

/** One file in a skill's manifest. */
export interface SkillResource {
  uri: string;
  digest: string;
  size: number;
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
  /** The Skills extension's view of this skill. */
  skills: SkillManifest;
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
  nextCursor?: string;
  /** The cursor no longer points at a result: the library changed. */
  cursorStale?: boolean;
}
