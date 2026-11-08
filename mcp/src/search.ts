/**
 * The ranking engine — a pure function of the index, with no I/O.
 *
 * This is a port of `mcp/python/search.py`, and the two must produce the
 * *identical ordered list* of ids for any query. The Python fallback is
 * what runs when the MCP SDK is unavailable, so a divergent fallback is
 * worse than no fallback; `mcp/tests/test_agreement.py` is the gate.
 *
 * Scoring
 * -------
 *     idf(t)       = ln(1 + N / df(t))            N = number of entries
 *     name_exact   = 3.0 * idf(t)   t is a name token
 *     name_partial = 1.5 * idf(t)   t is a prefix of a name token
 *     desc_match   = 1.0 * idf(t)   t is a description token
 *     phrase       = 6.0            a query bigram matches a name bigram
 *     signal       = 8.0            t is in metadata.promptSignals.phrases
 *     task_match   = 25.0           the query matches a row of the task index
 *     task_content = 8.0            the query has the row's content, verb dropped
 *     task_head    = 16.0           the row's content is the query's HEAD noun
 *     tier_bias    = +1.0 / +0.25 / 0.0
 *     agent_bias   = +0.5
 *
 * The tier bias is multiplied by `(1 - name_exact_hit)`: tiering must
 * never override a direct name match, it only breaks ties among weak,
 * description-only matches. The maximum tier bias (1.0) is well below a
 * single idf contribution (~3.0-6.0), so it cannot reorder a strong match.
 *
 * Two rules filter the scored entries:
 *
 *   token coverage -- an entry must match two thirds of the query's
 *                     *distinctive* tokens, and at least two of them
 *                     when the query has two or more. A distinctive
 *                     token is one that appears in fewer than 1.8% of
 *                     the corpus; a common word like "write" carries no
 *                     information about which entry the query wants.
 *
 *   task rows      -- a hand-written row of the task index fires when
 *                     the query has 60% of the row's tokens (the strict
 *                     match, full bonus) or all of the row's *content*
 *                     -- the row's tokens with its leading verb dropped
 *                     (the content match, smaller bonus). "write a REST
 *                     API" is the "Build an API" row.
 *
 *                     A content match whose token is the query's HEAD
 *                     noun -- the thing the query is *about*, not the
 *                     context it mentions -- earns more than a plain
 *                     content match. "write a REST API" is about an API,
 *                     so the "Build an API" row fires; "add
 *                     authentication to an api" is about authentication,
 *                     so the row does not fire and the authentication
 *                     skill keeps the top slot.
 *
 * Results are limited three ways, so a query never returns every row:
 *
 *   1. score threshold -- only `score > 0`; a pure-stopword query returns 0
 *   2. hard cap -- `limit`, default 10, max 50
 *   3. relevance floor -- drop hits below `0.25 * topScore`
 *
 * Tie-break order is fixed: score desc, tier asc, skill before agent,
 * shorter name first, then lexicographic name.
 */
import { tokenize, bigrams, headTokens } from './tokenize.js';
import { encodeCursor } from './protocol.js';
import * as filters from './filters.js';
import type { FilterName } from './filters.js';
import type {
  Entry,
  LibraryIndex,
  SearchResponse,
  SearchResult,
  Tier,
} from './types.js';

export const DEFAULT_LIMIT = 10;
export const MAX_LIMIT = 50;
export const RELEVANCE_FLOOR = 0.25;
/**
 * The discount applied to a description match that was found through
 * the inflection rule rather than an exact token. See `inflections`.
 */
export const MORPH_DISCOUNT = 0.6;

/**
 * A token is "generic" when it appears in more than this fraction of
 * the corpus.
 *
 * Generic tokens are excluded from the token-coverage requirement.
 * The requirement exists to stop a single common word from matching
 * everything -- but it must require the *discriminating* tokens, not
 * the common ones.
 *
 * "write documentation" is the case that forced this. The rule
 * demanded two of the query's two tokens, so `documentation-lookup`
 * and `notion-research-documentation` -- whose names contain
 * "documentation" -- were dropped for not also containing "write",
 * and the only survivor was `mixpanelyst`, which mentions both words
 * in its description and nothing else. The subject of the query was
 * the one token that carried no information.
 *
 * 1.8% of the corpus is about 19 documents. A token in 20 or more is
 * common enough that requiring it is a filter on luck rather than on
 * relevance. The ratio was chosen by measuring, over a labelled query
 * set, how many entries each threshold let through and where the
 * wanted skill ended up -- see `mcp/scripts/eval_unified.py`.
 */
export const GENERIC_TOKEN_DF_RATIO = 0.018;

export const WEIGHT_NAME_EXACT = 3.0;
export const WEIGHT_NAME_PARTIAL = 1.5;
export const WEIGHT_DESC = 1.0;
export const WEIGHT_PHRASE = 6.0;
export const WEIGHT_SIGNAL = 8.0;
export const WEIGHT_TASK = 25.0;
/**
 * A task row can fire two ways, and they are not equally strong.
 *
 * The strict match -- 60% of the row's own tokens are in the query --
 * means the query used the row's words, and earns the full bonus.
 *
 * The content match -- the row's content is present, verb dropped --
 * only means the query named the object. "add authentication to an
 * api" contains "api", which fires the "Build an API" row; at the full
 * bonus that pushed `twilio-security-api-auth` -- the skill that is
 * actually about authentication -- down to fifth. A smaller bonus
 * keeps the row's skills in the running without outranking the more
 * specific match.
 */
export const WEIGHT_TASK_CONTENT = 8.0;
/**
 * A HEAD match -- the row's content token is the query's head noun --
 * is stronger evidence than a mere content match, because position
 * says what the query is *about*.
 *
 * "write a REST API" is about an API, so the "Build an API" row fires.
 * "add authentication to an api" is about authentication, and "api" is
 * only the thing being added to, so the row does not fire and the
 * authentication skill keeps the top slot.
 */
export const WEIGHT_TASK_HEAD = 16.0;
/**
 * On a HEAD match, the row's FIRST entry earns the row's full bonus
 * (`WEIGHT_TASK`), and the alternatives earn the head bonus. The row
 * already says which entry it recommends -- `api-design` is listed
 * first for "Build an API" -- so this applies the table's own curation
 * instead of a new constant.
 *
 * Why the split matters. The comparison that decides "write a REST
 * API" reduces, in closed form, to
 *
 *     diff = HEAD - PHRASE - 3*idf(rest) + idf(api)
 *
 * and the idf part is corpus-dependent: `df(rest)` was 20 in one tree
 * and 12 in the other, so idf(rest) moved from 4.006 to 4.376 while
 * the fixed bonuses stayed put. With one bonus for every member of the
 * row the margin was +0.199 locally and -0.810 in the smaller tree --
 * the same query, two answers. With the split the margin is +9.2 and
 * +8.2, because the curated signal now outweighs the drift in the
 * automatic evidence instead of merely competing with it.
 */
export const WEIGHT_TASK_HEAD_FIRST = WEIGHT_TASK;
/**
 * A task row's *first* entry is its documented first choice; the rest
 * are alternatives. The row's note says so in prose -- "`api-design`
 * covers resource naming, ...", "Use the build resolver for the
 * language" -- but the scorer cannot read prose, so the order was lost
 * and the row's members were ranked only by whatever their names
 * happened to score.
 *
 * The row's later members are therefore demoted, by a *fraction* of the
 * row's bonus, scaled by how deep they sit in the row. The fraction
 * and the cap were measured over the labelled query set; see
 * `mcp/scripts/eval_search.py`.
 *
 * Demoting rather than promoting matters: the relevance floor is a
 * fraction of the *top* score, so raising the ceiling can evict a
 * weaker but relevant entry from the bottom of the list.
 *
 * The row's order is the row's curation in *both* branches -- whether
 * the query named the row's verb or only its object. "write SQL"
 * names the row's object ("sql") but not its verb ("write"), so the
 * content branch fires -- and without the demotion
 * `database-reviewer` won: the agent is tier 1 while
 * `postgres-patterns` is tier 2, so the tier bias and the agent bonus
 * together put it ahead of the skills the row had been asked for.
 */
export const TASK_DEMOTE_FRACTION = 0.6;
/**
 * The demotion does not keep growing with depth. A row's third or
 * fourth member is a real alternative, not a worse version of the
 * first, and an unbounded demotion would push it out of the results
 * entirely rather than down the list.
 */
export const TASK_DEMOTE_MAX_DEPTH = 3;
/**
 * The demotion is also capped in absolute terms.
 *
 * A pure fraction of the bonus is not enough on its own. The strict
 * bonus is 25.0, so a depth-3 member of a long row would give up
 * 25.0 * 0.6 * 3 = 45.0 -- more than the whole bonus, which put the
 * row's agents at a *negative* score. The row "Fix a failing build"
 * lists `error-handling` first and the `build-*-resolver` agents
 * fourth, fifth and sixth, and they are exactly what the query wants:
 * the agents fell out of the top ten entirely.
 *
 * The cap says the demotion is a nudge, not a ban. A row's later
 * members stay reachable; the row's first choice leads.
 */
export const TASK_DEMOTE_MAX = 15.0;
export const TIER_BIAS: Record<number, number> = { 1: 1.0, 2: 0.25, 3: 0.0 };
export const AGENT_BIAS = 0.5;

/**
 * Round to 4 decimal places, ties to even -- exactly what Python's
 * `round(x, 4)` does.
 *
 * JS's `toFixed` rounds ties away from zero and can return a string, so
 * it disagrees with Python on values like 0.00005. The two servers must
 * print the same score, so the rounding is done here on the exact binary
 * value of the double, using BigInt, the way CPython does.
 */
export function round4(x: number): number {
  if (!Number.isFinite(x)) return x;
  if (x === 0) return x;

  const buf = new DataView(new ArrayBuffer(8));
  buf.setFloat64(0, x);
  const hi = buf.getUint32(0);
  const lo = buf.getUint32(4);
  const negative = (hi >>> 31) === 1;
  const expField = (hi >>> 20) & 0x7ff;
  let mant = (BigInt(hi & 0xfffff) << 32n) | BigInt(lo);
  let exp: number;
  if (expField === 0) {
    exp = -1022; // subnormal: no implicit leading 1
  } else {
    mant |= 1n << 52n;
    exp = expField - 1075;
  }

  // value = mant * 2^exp, exactly.
  let num = mant;
  let den = 1n;
  if (exp >= 0) {
    num = mant << BigInt(exp);
  } else {
    den = 1n << BigInt(-exp);
  }

  // q = round(num * 10^4 / den), ties to even.
  const scaled = num * 10000n;
  let q = scaled / den;
  const rem = scaled % den;
  const twice = rem * 2n;
  if (twice > den) {
    q += 1n;
  } else if (twice === den && q % 2n !== 0n) {
    q += 1n;
  }

  const res = Number(q) / 10000;
  return negative ? -res : res;
}

/**
 * Scores are compared with a tolerance, not with raw float equality.
 *
 * Two entries that match the same query tokens score the *same* sum, but
 * the terms arrive in a different order, so the floating-point addition
 * lands on a different last bit. The difference is around 1e-15 -- far
 * below anything a reader could call a different score -- but the sort
 * compared the raw doubles, so the noise decided the order and the
 * documented tie-break (tier, kind, shorter name, name) never ran.
 *
 * "machine learning model training" is the case that showed it:
 * `pytorch-patterns`, `ml-adoption-playbook` and `huggingface-llm-trainer`
 * all score 12.7920798526549..., differing by 2e-15, and their order
 * changed every time the corpus grew by one entry.
 *
 * The quantum is 1e-6: a millionth of a point. A real score difference --
 * the smallest the weights can produce is an idf step, which is several
 * hundredths -- is far above it, so this only groups together scores that
 * are the same score.
 *
 * The scale is an integer so that both engines compute the same key:
 * IEEE 754 multiplication is exactly specified, so `score * SCORE_SCALE`
 * is bit-identical in Python and JavaScript, and `trunc` is exact.
 */
export const SCORE_SCALE = 1000000;

/**
 * The score as an integer, for comparison with a tolerance.
 *
 * `Math.trunc` and Python's `math.trunc` agree: both truncate toward
 * zero, and both are exact for a value this small.
 */
export function scoreKey(score: number): number {
  return Math.trunc(score * SCORE_SCALE);
}

/**
 * Compare two strings by unicode code point, the way Python compares
 * `str`. JS's `<` compares UTF-16 code units, which orders astral
 * characters differently -- library names are ASCII today, but the
 * tie-break must not silently change if that stops being true.
 *
 * Exported so the parity test can drive it against Python's own
 * comparator. The tokenizer only ever emits `[a-z0-9]` tokens, so the
 * astral case cannot arise from a real search -- but a tie-break that
 * silently changes its ordering rule is the kind of thing that gets
 * discovered a year later, in a diff nobody reads.
 */
export function codepointCompare(a: string, b: string): number {
  const ac = Array.from(a);
  const bc = Array.from(b);
  const n = Math.min(ac.length, bc.length);
  for (let i = 0; i < n; i++) {
    const x = ac[i].codePointAt(0)!;
    const y = bc[i].codePointAt(0)!;
    if (x !== y) return x < y ? -1 : 1;
  }
  return ac.length === bc.length ? 0 : ac.length < bc.length ? -1 : 1;
}

/**
 * Do all of the phrase's content words appear in the query?
 *
 * The phrase is tokenized with the same tokenizer as the query, so the
 * function words inside a phrase ("the page is stuck") drop out and only
 * the content words have to be present. The order does not matter:
 * "stuck page" and "page stuck" are the same symptom.
 *
 * This is deliberately stricter than the substring test. `vercel-cli`
 * lists "build failed" among its symptoms, and a query of "fix a
 * failing build" contains neither the phrase nor the word "failed" --
 * so `vercel-cli` earns no credit for a build failure it cannot fix.
 */
function phraseTokensMatch(phrase: string, qTokens: string[]): boolean {
  const pTokens = tokenize(phrase);
  if (pTokens.length === 0) return false;
  const qSet = new Set(qTokens);
  return pTokens.every((t) => qSet.has(t));
}

/**
 * The inflected forms of a token -- what a description may use.
 *
 * English spells the same word several ways, and a description that
 * says "drafting" does not contain the word "draft". Without this,
 * "triage my inbox and draft the replies" missed `email-ops`, whose
 * description says "mailbox triage, drafting, ...", and "review my
 * code for security problems" missed `security-review` for the same
 * reason.
 *
 * The rule is deliberately narrow: it adds only the suffixes English
 * actually inflects. It is NOT a prefix rule. "late" does not match
 * "latency" and "plant" does not match "plantation", because a prefix
 * rule matches any word that happens to start the same way, and those
 * are coincidences of spelling rather than inflections.
 *
 * The Python side has the same function, and the agreement test
 * compares the two on every query.
 */
export function inflections(tok: string): string[] {
  const out: string[] = [];
  if (tok.endsWith('y') && tok.length > 3) out.push(tok.slice(0, -1) + 'ies');
  if (
    (tok.endsWith('s') || tok.endsWith('x') || tok.endsWith('z') ||
     tok.endsWith('ch') || tok.endsWith('sh')) && tok.length > 3
  ) {
    out.push(tok + 'es');
  }
  if (tok.length > 2) out.push(tok + 's');
  if (tok.length > 4) {
    out.push(tok + 'ing');
    if (tok.endsWith('e')) out.push(tok.slice(0, -1) + 'ing');
  }
  return out.filter((f) => f !== tok);
}

const morphCache = new Map<string, string[]>();

/** `inflections`, cached. The same token comes up in every query. */
export function inflectionsFor(tok: string): string[] {
  const hit = morphCache.get(tok);
  if (hit) return hit;
  const v = inflections(tok);
  morphCache.set(tok, v);
  return v;
}

export interface SearchOptions {
  limit?: number;
  kind?: 'skill' | 'agent';
  tier?: Tier;
  domain?: string;
  include_body?: boolean;
  /**
   * The container the entry came from -- the plugin, the collection,
   * the local project.
   *
   * It is the broadest of the three filters: it says where a thing
   * came from, not what it may be used for.
   */
  source?: string;
  /** The licence. Matched case-insensitively, exactly. */
  license?: string;
  /**
   * The redistribution verdict: `redistributable`,
   * `included-with-terms`, `fixture`, `personal` or `unknown`.
   */
  verdict?: string;
  /**
   * The pagination cursor: the id of the entry the previous page
   * ended on.
   *
   * The cursor is decoded *before* it reaches here -- the server
   * layer decodes it and checks that it belongs to this query. Only
   * used under `2026-07-28`. The older revision has no cursor, and a
   * client on it must not find a field it has never heard of.
   */
  cursor?: string;
}

export class SearchIndex {
  readonly data: LibraryIndex;
  readonly entries: Entry[];
  readonly n: number;
  readonly byId: Map<string, Entry>;

  private readonly df = new Map<string, number>();
  private readonly signals = new Map<string, string[]>();
  private readonly skillTasks = new Map<string, string[]>();
  private readonly agentTasks = new Map<string, string[]>();
  /** Each task row's content-token sets, by row text. */
  private readonly taskContent = new Map<string, string[][]>();
  /** Each entry's position in each task row. Position 0 is the row's
   *  primary entry -- the one its note recommends. */
  private readonly taskPositions = new Map<string, number>();
  /** The filter vocabulary, so a filter argument that names nothing can
   *  be reported as an error rather than as an empty result. See
   *  `mcp/src/filters.ts`. */
  readonly filterValues: Record<FilterName, string[]>;

  constructor(data: LibraryIndex) {
    this.data = data;
    this.entries = [...data.skills, ...data.agents];
    this.n = this.entries.length;
    this.byId = new Map(this.entries.map((e) => [e.id, e]));

    // idf over the whole corpus (skills + agents)
    for (const e of this.entries) {
      const toks = new Set([...e.tokens.name, ...e.tokens.desc]);
      for (const t of toks) {
        this.df.set(t, (this.df.get(t) ?? 0) + 1);
      }
    }

    // curated activation phrases, by entry id
    //
    // These are matched as PHRASES, not as loose tokens. The phrases are
    // user-facing symptom descriptions ("the page is stuck", "build
    // failed", "nothing showing"), not skill names. Matching their
    // individual words gave unrelated skills credit for a query --
    // `vercel-cli` lists "build failed" among its symptoms, so it scored
    // highly for "fix a failing build" while having nothing to do with
    // it. A phrase has to appear in the query as a phrase to count.
    for (const e of this.entries) {
      const ps = e.frontmatter.prompt_signals ?? { phrases: [], all_of: [], any_of: [] };
      const phrases = (ps.phrases ?? [])
        .map((p) => String(p).toLowerCase().trim())
        .filter((p) => p.length > 0);
      if (phrases.length) this.signals.set(e.id, phrases);
    }

    // task rows, for the task-shaped query path
    for (const t of data.tasks ?? []) {
      for (const s of t.skills ?? []) {
        const list = this.skillTasks.get(s) ?? [];
        list.push(t.task);
        this.skillTasks.set(s, list);
      }
      for (const a of t.agents ?? []) {
        const list = this.agentTasks.get(a) ?? [];
        list.push(t.task);
        this.agentTasks.set(a, list);
      }
      // The row's content-token sets. The index builder computes them,
      // so both servers match a row the same way.
      this.taskContent.set(t.task, (t.content ?? []).map((c) => [...c]));
    }

    // The filter vocabulary, so a filter argument that names nothing
    // can be reported as an error rather than as an empty result. See
    // `mcp/src/filters.ts`.
    this.filterValues = filters.vocabulary(
      this.entries,
      (e) => (e as Entry).domain,
      (e) => (e as Entry).provenance,
    );

    // ...and each entry's position in each row. The table lists a row's
    // primary entry first, so position 0 is that entry; a later member
    // is an alternative the row ranks below it.
    //
    // The two columns are numbered independently, so an agent at
    // agent-position 0 is NOT the row's first choice: the row's
    // primary entry is its first *skill*. An agent in the agents
    // column is an additional specialist the note points at --
    // "`database-reviewer` is PostgreSQL-specific: query
    // optimisation, schema design, security." -- and most rows list
    // one. So the agent positions start after the skill positions, and
    // only the first skill holds position 0.
    //
    // The key joins the name and the row with a separator that cannot
    // occur in either, so "a" + "bc" and "ab" + "c" stay distinct.
    for (const t of data.tasks ?? []) {
      const skills = t.skills ?? [];
      const agents = t.agents ?? [];
      skills.forEach((s, pos) => {
        this.taskPositions.set(`${s}|${t.task}`, pos);
      });
      agents.forEach((a, pos) => {
        this.taskPositions.set(`${a}|${t.task}`, skills.length + pos);
      });
    }
  }

  /**
   * The row's curation, applied to one of its members.
   *
   * The task table lists a row's *primary* entry first, and its note
   * says which one that is. A later member is an alternative, so it is
   * demoted -- the row's first choice is what the row recommends, and
   * the scorer cannot read the prose that says so.
   *
   * The demotion is a *fraction* of the row's bonus, scaled by the
   * member's depth in the row. A flat amount was tried first and it
   * did not work: the row "Write SQL / optimise queries" lists
   * `postgres-patterns`, `mysql-patterns` and then the agent
   * `database-reviewer`, and a flat 3.0 was not enough to stop the
   * agent winning "write SQL queries" -- the agent is tier 1 and gets
   * the agent bonus, so it led by 0.299.
   *
   * Scaling by depth is what makes the demotion match the table. The
   * row's first member is its recommendation and keeps the full bonus.
   * The second is an alternative and gives up a third of the bonus.
   * The third gives up more, and the depth is capped so that a row's
   * later members stay reachable rather than being pushed out of the
   * results altogether.
   */
  private rowBonus(base: number, e: Entry, task: string): number {
    const pos = this.taskPositions.get(`${e.name}|${task}`);
    if (pos === undefined || pos === 0) return base;
    const depth = Math.min(pos, TASK_DEMOTE_MAX_DEPTH);
    const demote = Math.min(base * TASK_DEMOTE_FRACTION * depth, TASK_DEMOTE_MAX);
    return base - demote;
  }

  private taskContentMatches(
    task: string,
    qTokens: string[],
    heads?: Set<string>,
    e?: Entry,
  ): number {
    /**
     * Does the query contain the task row's *content*?
     *
     * The row's content is the row's tokens with its leading verb
     * dropped -- "Build an API" -> ["api"]. The row may list several
     * alternatives ("Write a document / report / deck"), and the row
     * fires when the query contains one of them.
     *
     * A single content token fires the row when it is *distinctive* --
     * a word like "api" appears in too many entries to identify a task
     * on its own -- OR when it is the query's HEAD noun. "write a REST
     * API" is about an API, so the "Build an API" row fires even
     * though "api" is common. Two or more content tokens have to be
     * *all* present. That is what keeps "write tests" from reaching
     * "Fix flaky / failing tests": that row's alternatives are
     * ["flaky"] and ["failing", "tests"], and the second needs both
     * words.
     *
     * Returns the bonus to award -- 0 for no match,
     * `WEIGHT_TASK_HEAD` for a head match, `WEIGHT_TASK_CONTENT`
     * otherwise.
     *
     * `e` is the entry being scored. It is needed because a HEAD
     * match splits the bonus by the row's curation: the row's first
     * choice earns the row's full bonus, and the alternatives earn
     * the head bonus.
     */
    const qSet = new Set(qTokens);
    const headSet = heads ?? new Set<string>();
    let best = 0.0;
    for (const content of this.taskContent.get(task) ?? []) {
      if (content.length === 0) continue;
      if (content.length === 1) {
        const tok = content[0];
        if (!qSet.has(tok)) continue;
        if (!this.isGeneric(tok)) best = Math.max(best, WEIGHT_TASK_CONTENT);
        else if (headSet.has(tok)) best = Math.max(best, this.headBonus(e, task));
        continue;
      }
      if (content.every((t) => qSet.has(t))) {
        best = Math.max(best, WEIGHT_TASK_CONTENT);
      }
    }
    return best;
  }

  /**
   * The head bonus, with the row's curation applied.
   *
   * The row lists its *primary* entry first and its note says so in
   * prose -- "`api-design` covers resource naming, status codes,
   * pagination, versioning, rate limits." -- but the scorer cannot
   * read prose. So the first choice earns the row's full bonus on a
   * head match, and the alternatives earn the smaller head bonus.
   *
   * Without this split the curated signal merely competed with the
   * automatic evidence, and the competition was decided by the
   * corpus: the same query ranked differently in two trees that hold
   * the same skills. See `WEIGHT_TASK_HEAD_FIRST`.
   */
  private headBonus(e: Entry | undefined, task: string): number {
    if (!e) return WEIGHT_TASK_HEAD;
    const pos = this.taskPositions.get(`${e.name}|${task}`);
    if (pos === undefined || pos === 0) return WEIGHT_TASK_HEAD_FIRST;
    return WEIGHT_TASK_HEAD;
  }

  idf(t: string): number {
    const df = this.df.get(t) ?? 0;
    return Math.log(1.0 + this.n / (df || 1));
  }

  /**
   * Is this token too common to discriminate?
   *
   * A token that appears in more than `GENERIC_TOKEN_DF_RATIO` of the
   * corpus carries almost no information about which entry a query
   * wants. "write" appears in a few dozen entries; requiring an
   * entry to contain it is a filter on luck, not on relevance.
   */
  isGeneric(t: string): boolean {
    const df = this.df.get(t) ?? 0;
    return df > this.n * GENERIC_TOKEN_DF_RATIO;
  }

  /**
   * The query tokens that the coverage rule counts.
   *
   * Generic tokens are dropped, and duplicates are collapsed. If
   * nothing is left -- a query made entirely of common words -- the
   * full token list is used, so the rule still applies to it.
   */
  coverageTokens(qTokens: string[]): string[] {
    const specific: string[] = [];
    const seen = new Set<string>();
    for (const t of qTokens) {
      if (seen.has(t)) continue;
      seen.add(t);
      if (!this.isGeneric(t)) specific.push(t);
    }
    return specific.length > 0 ? specific : Array.from(new Set(qTokens));
  }

  /** (score, matchedOn, tokenHits, structured) for one entry. */
  scoreEntry(
    e: Entry,
    qTokens: string[],
    qBigrams: string[],
    queryLower = '',
    heads?: Set<string>,
  ): [number, string[], Set<string>, boolean] {
    let score = 0.0;
    const matched = new Set<string>();
    const tokenHits = new Set<string>();
    // `structured` is True when the entry matched a curated
    // `promptSignals` phrase, a task-index row, or a name bigram.
    // Those are authoritative hand-written matches, so the token
    // coverage rule does not apply to them.
    let structured = false;
    const nameTokens = e.tokens.name;
    const descTokens = new Set(e.tokens.desc);
    const nameBigrams = new Set(e.tokens.name_bigrams ?? []);

    let nameExactHit = false;
    for (const t of qTokens) {
      const idf = this.idf(t);
      if (nameTokens.includes(t)) {
        score += WEIGHT_NAME_EXACT * idf;
        matched.add(t);
        tokenHits.add(t);
        nameExactHit = true;
      } else if (nameTokens.some((nt) => nt.length > t.length && nt.startsWith(t))) {
        // The token must be a *prefix* of a name token, not a fragment
        // somewhere inside it.
        //
        // The old rule accepted the token anywhere in the name token,
        // and that matched words by accident: "home" in "homelab",
        // "late" in "template", "translate", and "sql" in "mysql".
        // "write SQL" ranked `mysql-patterns` first because "sql" was
        // found inside "mysql" -- a coincidence of spelling, not
        // evidence -- and "bake sourdough bread at home" matched every
        // `homelab-*` skill on the fragment "home".
        //
        // A prefix is still a partial match: "docker" is a prefix of
        // "dockerfile", "kuber" of "kubernetes", and both are what a
        // caller means when they type them.
        score += WEIGHT_NAME_PARTIAL * idf;
        matched.add(t);
        tokenHits.add(t);
      }
      if (descTokens.has(t)) {
        score += WEIGHT_DESC * idf;
        matched.add(t);
        tokenHits.add(t);
      } else if (inflectionsFor(t).some((f) => descTokens.has(f))) {
        // The description uses an inflected form of the query token --
        // "drafting" for "draft". The match is worth less than an exact
        // one, because it is a guess about the spelling rather than the
        // spelling itself.
        score += WEIGHT_DESC * idf * MORPH_DISCOUNT;
        matched.add(t);
        tokenHits.add(t);
      }
    }

    for (const bg of qBigrams) {
      if (nameBigrams.has(bg)) {
        score += WEIGHT_PHRASE;
        matched.add(bg);
        structured = true;
      }
    }

    const sig = this.signals.get(e.id);
    if (sig) {
      // A phrase must appear in the query as a phrase. The curated
      // phrases are symptom descriptions ("the page is stuck"), so a
      // loose word match would credit unrelated skills.
      for (const p of sig) {
        if (queryLower.includes(p) || phraseTokensMatch(p, qTokens)) {
          score += WEIGHT_SIGNAL;
          matched.add(p);
          structured = true;
          break;
        }
      }
    }

    // A task-shaped query ("fix a failing build") routes better through
    // the hand-written task index than through any automatic score.
    //
    // The row has to be *substantially* present in the query. An
    // earlier "all but one token" rule was too loose: "fix a failing
    // build" matched the row "Build a dashboard" on the single word
    // "build", which put four dashboard/API builders above
    // `error-handling`. The rule below needs at least 60% of the row's
    // content words, and at least two of them when the row has two or
    // more -- so "my build keeps failing" still finds "Fix a failing
    // build", but "fix a failing build" no longer finds "Build a
    // dashboard".
    //
    // The 60% rule reads the WHOLE row, verb included. The rows are
    // written "<verb> <object>" -- "Build an API" -- so it demanded
    // the query's verb as well as its object, and "write a REST API"
    // never reached the row that names the right skills. The row
    // also fires, for a smaller bonus, when the query contains the
    // row's *content* (the row's verb dropped) -- which is what
    // "write a REST API" has.
    const tasks = e.kind === 'skill'
      ? this.skillTasks.get(e.name)
      : this.agentTasks.get(e.name);
    if (tasks) {
      const qSet = new Set(qTokens);
      for (const task of tasks) {
        const tToks = tokenize(task);
        let strict = false;
        if (tToks.length > 0) {
          let overlap = 0;
          for (const t of tToks) if (qSet.has(t)) overlap++;
          // ceil(60%) of the row's content words
          let needed = Math.ceil((tToks.length * 6) / 10);
          if (tToks.length >= 2) needed = Math.max(2, needed);
          strict = overlap >= needed;
        }
        if (strict) {
          score += this.rowBonus(WEIGHT_TASK, e, task);
          matched.add(task);
          structured = true;
          break;
        }
        let bonus = this.taskContentMatches(task, qTokens, heads, e);
        if (bonus > 0) {
          // A content match: the query named the row's object, not the
          // row's verb, so the row has NOT accounted for the verb.
          // Nothing is suppressed.
          //
          // The row's *order* still counts, though. The table lists a
          // row's members in priority order -- its skills first, then
          // its agents -- and that order is the row's curation even
          // when the query named only the row's object. Without this,
          // "write SQL" ranked `database-reviewer` first: the agent is
          // tier 1 while `mysql-patterns` is tier 2, so the tier bias
          // and the agent bonus together put it ahead of the skills
          // the row had been asked for.
          //
          // The demotion is the same gradient the strict branch uses,
          // and it is gentle: a row's own alternatives stay reachable,
          // but the row's first choice leads.
          const pos = this.taskPositions.get(`${e.name}|${task}`);
          if (pos !== undefined && pos > 0) {
            const depth = Math.min(pos, TASK_DEMOTE_MAX_DEPTH);
            const demote = Math.min(bonus * TASK_DEMOTE_FRACTION * depth,
                                    TASK_DEMOTE_MAX);
            bonus = bonus - demote;
          }
          score += bonus;
          matched.add(task);
          structured = true;
          break;
        }
      }
    }

    // Tier bias, suppressed when the name matched exactly.
    const bias = (TIER_BIAS[e.tier ?? 3] ?? 0.0) * (nameExactHit ? 0.0 : 1.0);
    score += bias;
    if (e.kind === 'agent') score += AGENT_BIAS;

    return [score, Array.from(matched).sort(codepointCompare), tokenHits, structured];
  }

  search(query: string, opts: SearchOptions = {}): SearchResponse {
    const limit0 = opts.limit ?? DEFAULT_LIMIT;
    const qTokens = tokenize(query);
    if (qTokens.length === 0) {
      return {
        query,
        total_matched: 0,
        filtered_out: 0,
        returned: 0,
        truncated: false,
        note: '',
        results: [],
      };
    }
    // The filter arguments are resolved against the index's vocabulary
    // before anything is scored. A filter that names nothing is an
    // error, not an empty result -- see `mcp/src/filters.ts`.
    const domain = filters.resolve('domain', opts.domain, this.filterValues.domain);
    const source = filters.resolve('source', opts.source, this.filterValues.source);
    const license = filters.resolve('license', opts.license, this.filterValues.license);
    const verdict = filters.resolve('verdict', opts.verdict, this.filterValues.verdict);

    const qBigrams = bigrams(qTokens);
    const queryLower = (query ?? '')
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean)
      .join(' ');
    // The query's head nouns -- what it is *about*, as opposed to the
    // context it mentions. The task-row rule uses this to tell
    // "write a REST API" (about an API) from "add authentication to
    // an api" (about authentication).
    const heads = headTokens(query);

    const scored: Array<[number, Entry, string[]]> = [];
    for (const e of this.entries) {
      if (opts.kind && e.kind !== opts.kind) continue;
      if (opts.tier !== undefined && opts.tier !== null && e.tier !== opts.tier) continue;
      if (domain && e.domain !== domain) continue;
      // The provenance filters. A caller who needs to know what may
      // be redistributed asks for it here, rather than filtering the
      // results afterwards.
      const prov = e.provenance;
      if (source && prov.container !== source) continue;
      if (license && prov.license !== license) continue;
      if (verdict && prov.verdict !== verdict) continue;
      const [s, matched, tokenHits, structured] = this.scoreEntry(
        e, qTokens, qBigrams, queryLower, heads);
      if (s <= 0) continue;
      // Token coverage. A single generic token is not a match:
      // "how to bake sourdough bread at home" matched
      // `shopify-polaris-app-home` on the word "home", and
      // "quantum chromodynamics lattice simulation" matched
      // `web-game-foundations` on "simulation". An entry has to
      // match at least two thirds of the query's tokens, and at
      // least two when the query has two or more.
      //
      // An entry that matched a curated phrase, a task row or a
      // name bigram is exempt: those are hand-written, and the
      // task row "Review code I did not write" legitimately shares
      // only "code", "not" and "review" with its query.
      //
      // The rule counts only the *discriminating* query tokens.
      // "write documentation" has two tokens, so the rule demanded
      // both -- and `documentation-lookup`, whose name contains
      // "documentation", was dropped for not also containing
      // "write". The subject of the query was the one token that
      // carried the information; the generic verb was noise.
      const covTokens = this.coverageTokens(qTokens);
      if (!structured) {
        let needed = Math.ceil((covTokens.length * 2) / 3);
        if (covTokens.length >= 2) needed = Math.max(2, needed);
        // The demand is capped at two tokens.
        //
        // Two thirds of the query's tokens is the right *shape* -- a
        // query that names a subject should be answered by an entry
        // that covers it -- but it is the wrong *magnitude* once the
        // query is longer than the sentence that names the subject.
        // "stop my prose from sounding like a machine wrote it" has
        // five discriminating tokens, so the rule demanded four, and
        // `humanizer` -- which matches "sounding" and "wrote" -- was
        // thrown away for want of two more words that no skill's
        // description contains.
        //
        // Two is the number the rule already insisted on when the
        // query had two or more tokens. Beyond that, the demand grew
        // with the query's length, and length is evidence of nothing.
        needed = Math.min(needed, 2);
        // The hits are counted over *every* query token, not only the
        // ones that survived the generic-token filter.
        //
        // The filter drops the words that appear in too many
        // descriptions -- "audit", "draft", "review". That is right for
        // deciding *how many* tokens the rule should demand, but wrong
        // for deciding which tokens count as evidence: the filtered
        // word is still evidence when the entry matched it. "audit my
        // site against WCAG 2.2" leaves {site, against, wcag} after
        // the filter and demands two of them; `accessibility` matches
        // "wcag" and "audit", but "audit" had been discarded, so the
        // rule demanded "site" and "against" -- words no skill's
        // description contains -- and threw the right answer away.
        let hits = 0;
        for (const t of new Set(qTokens)) if (tokenHits.has(t)) hits++;
        if (hits < needed) continue;
        // The evidence rule.
        //
        // An entry that matched only words which carry no information
        // about *which* entry it is, matched nothing real. "my cat
        // knocked over a plant" matched `plant-care` on the word
        // "plant" -- and "plant" is the query's subject, but the
        // *coverage* words are the words that identify the entry, and
        // "plant" identifies none of them.
        //
        // The check has two halves. The entry must have matched at
        // least one word that appears in the corpus at all --
        // otherwise every word it matched is a coincidence. And it
        // must have matched at least one of the *coverage* words, or
        // at least two words overall: one word in the corpus is not
        // enough on its own, because "write" appears in a few dozen
        // descriptions and matching it says nothing.
        const inCorpus: string[] = [];
        for (const t of tokenHits) if ((this.df.get(t) ?? 0) > 0) inCorpus.push(t);
        let covInCorpus = 0;
        for (const t of covTokens) {
          if (tokenHits.has(t) && (this.df.get(t) ?? 0) > 0) covInCorpus++;
        }
        if (covInCorpus === 0 && inCorpus.length < 2) continue;
      }
      scored.push([s, e, matched]);
    }

    // The fixed tie-break order. The Python server must produce the
    // identical ordering, or the agreement test fails.
    //
    // The score is compared through `scoreKey`, so that scores which
    // differ only in the last floating-point bit are treated as equal
    // and the tie-break below decides their order.
    scored.sort((a, b) => {
      const aScore = scoreKey(a[0]);
      const bScore = scoreKey(b[0]);
      if (aScore !== bScore) return bScore - aScore;
      const at = a[1].tier ?? 3;
      const bt = b[1].tier ?? 3;
      if (at !== bt) return at - bt;
      const ak = a[1].kind === 'skill' ? 0 : 1;
      const bk = b[1].kind === 'skill' ? 0 : 1;
      if (ak !== bk) return ak - bk;
      if (a[1].name.length !== b[1].name.length) return a[1].name.length - b[1].name.length;
      return codepointCompare(a[1].name, b[1].name);
    });

    // The number of entries that matched, before the relevance floor.
    //
    // This is the size of the match set: the entries that passed
    // scoring and the coverage rule. It is *not* the number of
    // results, because the relevance floor then drops the entries
    // whose score is under a quarter of the best one.
    const total = scored.length;
    if (total === 0) {
      return {
        query,
        total_matched: 0,
        filtered_out: 0,
        returned: 0,
        truncated: false,
        note: '',
        results: [],
      };
    }

    const top = scored[0][0];
    const floor = top * RELEVANCE_FLOOR;
    const kept = scored.filter((t) => t[0] >= floor);

    // The entries the relevance floor dropped. Reporting this is what
    // makes the four counts tell one story: `total_matched` is the
    // match set, `filtered_out` is what the floor removed from it, and
    // `returned` is what came back. Before this field existed, the
    // floor silently hid entries -- a query reported 52 matches and
    // returned 37 with `truncated: false`, so the caller could not
    // tell that 15 had been dropped.
    const filteredOut = total - kept.length;

    const limit = Math.max(1, Math.min(Math.trunc(limit0) || DEFAULT_LIMIT, MAX_LIMIT));

    // Cursor pagination.
    //
    // The cursor names the last entry the client saw, and the page
    // starts after it. The cursor is honoured even if the entry is
    // gone -- then the page starts at the end, and `cursorStale`
    // says so, because a client that silently got an empty page would
    // think it had reached the end of the results.
    let start = 0;
    let cursorStale = false;
    if (opts.cursor) {
      const pos = kept.findIndex((t) => t[1].id === opts.cursor);
      if (pos >= 0) {
        start = pos + 1;
      } else {
        start = kept.length;
        cursorStale = true;
      }
    }

    const remaining = kept.length - start;
    const truncated = remaining > limit;
    const shown = kept.slice(start, start + limit);

    const results: SearchResult[] = shown.map(([s, e, matched]) => {
      const r: SearchResult = {
        id: e.id,
        kind: e.kind,
        name: e.name,
        title: e.title || e.name,
        description: e.desc ?? '',
        tier: e.tier,
        domain: e.domain ?? '',
        score: round4(s),
        matched_on: matched,
        path: e.path,
        owner: e.provenance.owner,
        license: e.provenance.license,
        verdict: e.provenance.verdict,
      };
      if (opts.include_body) r.frontmatter = e.frontmatter;
      return r;
    });

    let note = '';
    if (cursorStale) {
      note = 'The cursor no longer points at a result -- the library changed. This page is empty.';
    } else if (truncated) {
      note = `Showing ${limit} of ${remaining} matches. Refine the query to narrow it down.`;
    } else if (filteredOut > 0) {
      note = `Showing ${kept.length} of ${total} matches; ${filteredOut} were below the relevance floor.`;
    }
    const out: SearchResponse = {
      query,
      total_matched: total,
      filtered_out: filteredOut,
      returned: results.length,
      truncated,
      note,
      results,
    };

    // The cursor for the next page, when there is one. It names the
    // last entry of *this* page, so the next page starts after it --
    // not after an offset, which would skip or repeat entries if the
    // ranking changed between the two calls.
    //
    // The cursor is emitted whenever there is a next page, including
    // on the first one: the first page is where the client gets the
    // cursor it needs.
    if (truncated && results.length > 0) {
      out.nextCursor = encodeCursor(results[results.length - 1]!.id, query);
    }
    if (cursorStale) out.cursorStale = true;
    return out;
  }
}
