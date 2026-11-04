/**
 * The tokenizer — mirrored exactly in Python (`mcp/build/build_index.py`).
 *
 * The two implementations must agree token for token; the differential
 * test in `mcp/tests/test_agreement.py` pushes every token in the corpus's
 * vocabulary through both and compares. A divergence here silently
 * changes every search result, so the rules are written out rather than
 * inferred.
 *
 *  1. camelCase split BEFORE lowercasing. Lowercasing first erases the
 *     case boundary the split depends on: `useEffect` must yield
 *     `use`, `effect` — not `useeffect`.
 *  2. lower-case, then strip everything that is not `[a-z0-9]`.
 *  3. drop the function words.
 *
 * The stopword list deliberately does NOT contain `test`, `write`,
 * `fix`, `review`, `build`, `debug`, `run`, `create`, `update`,
 * `generate`, `deploy`. Those are this library's domain vocabulary —
 * stripping them made "write tests first" fail to surface
 * `tdd-workflow` in an earlier prototype.
 */
export const STOPWORDS: ReadonlySet<string> = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'been', 'being', 'but', 'by',
  'can', 'could', 'did', 'do', 'does', 'for', 'from', 'had', 'has', 'have',
  'he', 'her', 'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its',
  'me', 'my', 'of', 'on', 'or', 'our', 'out', 'she', 'so', 'such', 'than',
  'that', 'the', 'their', 'them', 'then', 'there', 'these', 'they', 'this',
  'those', 'to', 'too', 'up', 'us', 'was', 'we', 'were', 'what', 'when',
  'where', 'which', 'while', 'who', 'whom', 'why', 'will', 'with', 'would',
  'you', 'your',
]);

/** Insert a space at a lower/digit -> upper boundary. */
const CAMEL_RE = /(?<=[a-z0-9])(?=[A-Z])/g;
const WORD_RE = /[^A-Za-z0-9]+/g;

export function tokenize(text: string | null | undefined): string[] {
  if (!text) return [];
  const out: string[] = [];
  for (const word of String(text).split(WORD_RE)) {
    if (word === '') continue;
    // camelCase split before lowercasing, so `useEffect` yields `use` and
    // `effect` and "use effect" matches.
    const parts = word.replace(CAMEL_RE, ' ').split(' ').filter(Boolean);
    for (const p of parts) {
      const lower = p.toLowerCase();
      if (STOPWORDS.has(lower)) continue;
      out.push(lower);
    }
    if (parts.length > 1) {
      // Keep the whole word as well. The camel split cannot tell
      // `parseHTMLString` (three words) from `GraphQL` (one), so
      // splitting alone makes "graphql" unfindable -- it becomes
      // "graph ql". Emitting both forms makes either spelling
      // searchable, and the whole form carries a high idf because
      // few documents contain it.
      const whole = word.toLowerCase();
      if (!STOPWORDS.has(whole)) out.push(whole);
    }
  }
  return out;
}

export function bigrams(tokens: string[]): string[] {
  const out: string[] = [];
  for (let i = 0; i + 1 < tokens.length; i++) {
    out.push(`${tokens[i]} ${tokens[i + 1]}`);
  }
  return out;
}

/**
 * The prepositions that put their object in a subordinate phrase.
 *
 * A noun after one of these is the object of the preposition, not the
 * subject of the query: in "add authentication to an api", "api" is the
 * context and "authentication" is what the query is about.
 */
export const PREPOSITIONS: ReadonlySet<string> = new Set([
  'about', 'against', 'at', 'for', 'from', 'in', 'into', 'of', 'on',
  'onto', 'to', 'via', 'with',
]);

/**
 * The determiners that sit between a preposition and its object.
 *
 * "to an api" -- "an" has to be stepped over before the preposition
 * "to" can be found.
 */
export const DETERMINERS: ReadonlySet<string> = new Set([
  'a', 'an', 'each', 'every', 'my', 'our', 'some', 'that', 'the',
  'their', 'this', 'your',
]);

/**
 * The query's HEAD nouns -- the things the query is *about*.
 *
 * A word is the head of the query when it is not the object of a
 * preposition. That is the difference between these two queries:
 *
 *   "write a REST API"            -> head: {write, rest, api}
 *   "add authentication to an api" -> head: {add, authentication}
 *
 * The second sentence is *about* authentication; "api" is the thing
 * being added to. The search uses this to tell a task row that names
 * the query's subject ("Build an API" for "write a REST API") from one
 * that merely appears in the query's context.
 *
 * The head set is computed from the raw words, so it keeps words the
 * tokenizer dropped as stopwords out of the way -- "to" and "an" are
 * skipped on the way back, but "write" is not a preposition and so
 * stands.
 */
export function headTokens(text: string | null | undefined): Set<string> {
  const heads = new Set<string>();
  if (!text) return heads;
  const words = String(text).toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
  for (let i = 0; i < words.length; i++) {
    const word = words[i];
    // Step back over determiners to find the word that governs.
    let j = i - 1;
    while (j >= 0 && DETERMINERS.has(words[j])) j--;
    if (j >= 0 && PREPOSITIONS.has(words[j])) continue;   // subordinate
    heads.add(word);
  }
  return heads;
}
