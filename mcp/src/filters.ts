/**
 * Validating the filters a caller passes to `search_library`.
 *
 * A filter that names nothing is an error, not an empty result.
 *
 * `domain: "Not A Domain"` used to answer `total_matched: 0`, which is
 * indistinguishable from "your query matched nothing". The caller has no
 * way to tell a typo from a genuinely empty library, and the most likely
 * explanation -- a misspelled or shortened domain -- goes undiagnosed.
 *
 * So the filter values are checked against the index before the search
 * runs. A value that names no entry raises `FilterError`, and the error
 * names the valid values nearest to what was asked for.
 *
 * The check is deliberately forgiving about *how* the value is written:
 *
 *   - the match is case-insensitive -- "DevOps & cloud" and "devops &
 *     cloud" are the same domain;
 *   - an unambiguous prefix resolves -- "DevOps" is the only domain that
 *     starts with "devops", so it resolves to "DevOps & cloud";
 *   - a substring resolves when it is unique -- "cloud" is inside exactly
 *     one domain name.
 *
 * What it will not do is guess. "data" is a prefix of several domains and
 * a substring of several more; it is ambiguous, and the error says so
 * rather than picking one.
 *
 * The Python side has the same module (`mcp/python/filters.py`), and the
 * agreement test compares the two on every filter value in the index.
 */

/** A filter argument that names nothing in the index. */
export class FilterError extends Error {  readonly filterName: string;
  readonly value: string;
  readonly valid: string[];
  readonly near: string[];

  constructor(filterName: string, value: string, valid: string[], near: string[]) {
    let msg = `Unknown ${filterName} ${JSON.stringify(value)}.`;
    if (near.length) {
      msg += ` Did you mean: ${near.map((n) => JSON.stringify(n)).join(', ')}?`;
    } else {
      msg += ` Valid values are: ${valid.map((v) => JSON.stringify(v)).join(', ')}.`;
    }
    super(msg);
    this.name = 'FilterError';
    this.filterName = filterName;
    this.value = value;
    this.valid = valid;
    this.near = near;
  }
}

/**
 * How many suggestions an error names. Enough to be useful, few enough
 * to read.
 */
export const NEAR_LIMIT = 5;

/** The filters that take a value drawn from the index. */
export type FilterName = 'domain' | 'source' | 'license' | 'verdict';

/**
 * The filter vocabulary of an index, as `{filter: [values]}`.
 *
 * `domainOf` and `provenanceOf` read the two fields the filters read,
 * so the vocabulary cannot drift from the data.
 */
export function vocabulary(
  entries: Array<{
    domain?: string;
    provenance?: { container?: string; license?: string; verdict?: string };
  }>,
  domainOf: (e: unknown) => string | undefined,
  provenanceOf: (e: unknown) => { container?: string; license?: string; verdict?: string } | undefined,
): Record<FilterName, string[]> {
  const domains = new Set<string>();
  const sources = new Set<string>();
  const licenses = new Set<string>();
  const verdicts = new Set<string>();
  for (const e of entries) {
    const d = domainOf(e);
    if (d) domains.add(d);
    const p = provenanceOf(e) ?? {};
    if (p.container) sources.add(p.container);
    if (p.license) licenses.add(p.license);
    if (p.verdict) verdicts.add(p.verdict);
  }
  return {
    domain: [...domains].sort(),
    source: [...sources].sort(),
    license: [...licenses].sort(),
    verdict: [...verdicts].sort(),
  };
}

/**
 * The comparison form of a filter value.
 *
 * Case is folded and the surrounding whitespace is dropped. Nothing else
 * is changed: "Apache-2.0" and "apache-2.0" are the same licence, but
 * "Apache 2.0" is not, and pretending otherwise would hide a real
 * mistake.
 */
export function normalise(value: string): string {
  return String(value ?? '')
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter((s) => s.length)
    .join(' ');
}

/**
 * The edit distance between two strings, as an integer.
 *
 * Levenshtein, with the usual unit costs. It is used only to rank the
 * suggestions, so an exact value does not matter -- what matters is that
 * the ranking is the same in both implementations, which it is, because
 * the rule is stated once in Python and mirrored here.
 */
export function distance(a: string, b: string): number {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;
  let previous: number[] = [];
  for (let j = 0; j <= b.length; j++) previous.push(j);
  for (let i = 1; i <= a.length; i++) {
    const current: number[] = [i];
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      current.push(Math.min(
        previous[j] + 1,          // deletion
        current[j - 1] + 1,       // insertion
        previous[j - 1] + cost,   // substitution
      ));
    }
    previous = current;
  }
  return previous[b.length];
}

/**
 * The values closest to `value`, nearest first.
 *
 * Ranking is by shared words, then by edit distance, then by the value
 * itself.
 *
 * Shared words come first because a filter value is a *name*, and names
 * are made of words. "Not A Domain" is not one character away from any
 * domain -- it is two words away -- so edit distance alone ranks it
 * randomly among forty equally-distant candidates. But it shares the
 * word "domain" with several of them, and those are the ones the caller
 * meant.
 *
 * The edit distance still matters, for the case where no word is shared:
 * a typo in one word of a multi-word name.
 *
 * The tie-break on the value matters too: two suggestions at the same
 * rank must come out in the same order in both engines.
 */
export function nearest(value: string, valid: string[], limit = NEAR_LIMIT): string[] {
  const want = normalise(value);
  const wantWords = new Set(want.split(' ').filter((w) => w.length));
  const scored = valid.map((v) => {
    const norm = normalise(v);
    const shared = [...wantWords].filter((w) => norm.split(' ').includes(w)).length;
    return { shared: -shared, d: distance(want, norm), v };
  });
  scored.sort((a, b) => {
    if (a.shared !== b.shared) return a.shared - b.shared;
    if (a.d !== b.d) return a.d - b.d;
    return a.v < b.v ? -1 : a.v > b.v ? 1 : 0;
  });
  return scored.slice(0, limit).map((s) => s.v);
}

/**
 * Resolve a filter value against the vocabulary `valid`.
 *
 * Returns the canonical value -- one of the strings in `valid` -- or
 * throws `FilterError`.
 *
 * The resolution order is:
 *
 *   1. an exact match, ignoring case and surrounding whitespace;
 *   2. a unique prefix -- "DevOps" -> "DevOps & cloud";
 *   3. a unique substring -- "cloud" -> "DevOps & cloud".
 *
 * A prefix or substring that matches more than one value is ambiguous,
 * and is an error: the caller asked for something the library cannot
 * answer unambiguously, and the error names the candidates.
 */
export function resolve(filterName: string, value: string | undefined, valid: string[]): string | undefined {
  if (value === undefined || value === null) return undefined;
  const raw = String(value).trim().split(/\s+/).filter((s) => s.length).join(' ');
  if (!raw) {
    // An empty filter is no filter.
    return undefined;
  }

  // 1. exact, ignoring case
  const folded = raw.toLowerCase();
  for (const v of valid) {
    if (v.toLowerCase() === folded) return v;
  }

  // 2. a unique prefix
  const prefixed = valid.filter((v) => v.toLowerCase().startsWith(folded));
  if (prefixed.length === 1) return prefixed[0];
  if (prefixed.length > 1) {
    throw new FilterError(filterName, raw, valid, [...prefixed].sort());
  }

  // 3. a unique substring
  const contained = valid.filter((v) => v.toLowerCase().includes(folded));
  if (contained.length === 1) return contained[0];
  if (contained.length > 1) {
    throw new FilterError(filterName, raw, valid, [...contained].sort());
  }

  // Nothing matched at all. Suggest the nearest valid values.
  throw new FilterError(filterName, raw, valid, nearest(raw, valid));
}
