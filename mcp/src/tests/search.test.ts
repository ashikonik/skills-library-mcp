/**
 * The TypeScript search tests.
 *
 * Run with `node --test dist/tests/`. Two jobs:
 *
 *  1. Reproduce `golden/search_golden.json` exactly. The golden file is
 *     written by the Python implementation, so this is a genuine
 *     cross-implementation replay, not a self-check.
 *  2. Unit-test the tokenizer on the shapes that broke it -- camelCase,
 *     snake_case, hyphenated, punctuation, CJK, emoji.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { tokenize, bigrams, headTokens } from '../tokenize.js';
import { SearchIndex, round4 } from '../search.js';
import { loadIndex } from '../index-loader.js';

const HERE = dirname(fileURLToPath(import.meta.url));
// dist/tests/ -> mcp/
const MCP_ROOT = resolve(HERE, '..', '..');
const LIBRARY_ROOT = resolve(MCP_ROOT, '..');
const GOLDEN = join(MCP_ROOT, 'tests', 'golden', 'search_golden.json');

const idx = new SearchIndex(loadIndex());

// ------------------------------------------------------------- tokenizer
test('tokenize splits camelCase', () => {
  assert.deepEqual(tokenize('useEffect'), ['use', 'effect', 'useeffect']);
  assert.deepEqual(tokenize('parseHTMLString'),
    ['parse', 'htmlstring', 'parsehtmlstring']);
  assert.deepEqual(tokenize('MySkillName'), ['skill', 'name', 'myskillname']);
});

test('tokenize keeps an acronym whole as well as split', () => {
  // The camel split cannot tell `parseHTMLString` from `GraphQL`, so
  // splitting alone makes "graphql" unfindable. Both forms are emitted.
  assert.deepEqual(tokenize('GraphQL guide'), ['graph', 'ql', 'graphql', 'guide']);
  assert.deepEqual(tokenize('gRPC streaming'), ['g', 'rpc', 'grpc', 'streaming']);
});

test('tokenize splits snake_case and kebab-case', () => {
  assert.deepEqual(tokenize('snake_case_name'), ['snake', 'case', 'name']);
  assert.deepEqual(tokenize('kebab-case-name'), ['kebab', 'case', 'name']);
});

test('tokenize lowercases and strips punctuation', () => {
  assert.deepEqual(tokenize('API design'), ['api', 'design']);
  assert.deepEqual(tokenize('REST, GraphQL; gRPC!'),
    ['rest', 'graph', 'ql', 'graphql', 'g', 'rpc', 'grpc']);
});

test('tokenize keeps the library\'s domain vocabulary', () => {
  // These must NOT be stopwords -- they are this library's domain
  // vocabulary, and stripping them made "write tests first" fail to
  // surface tdd-workflow.
  for (const word of ['test', 'write', 'fix', 'review', 'build', 'debug',
                       'run', 'create', 'update', 'generate', 'deploy']) {
    assert.ok(tokenize(word).length > 0, `${word} must survive tokenize`);
  }
});

test('tokenize drops the function words', () => {
  assert.deepEqual(tokenize('the page is stuck'), ['page', 'stuck']);
  assert.deepEqual(tokenize('a an the of to'), []);
});

test('tokenize handles CJK and emoji without crashing', () => {
  assert.doesNotThrow(() => tokenize('日本語のスキル 🎉'));
  assert.deepEqual(tokenize('🎉'), []);
});

test('bigrams are consecutive token pairs', () => {
  assert.deepEqual(bigrams(['a', 'b', 'c']), ['a b', 'b c']);
  assert.deepEqual(bigrams(['a']), []);
});

// ------------------------------------------------------------- head nouns
test('headTokens finds what the query is about', () => {
  // "api" is the head here -- it is what the query is about.
  const heads = headTokens('write a REST API');
  assert.ok(heads.has('api'), 'api must be a head');
  assert.ok(heads.has('rest'), 'rest must be a head');
});

test('headTokens drops the object of a preposition', () => {
  // "api" here is the object of "to"; the query is about
  // authentication, and the head rule must not fire the "Build an
  // API" row.
  const heads = headTokens('add authentication to an api');
  assert.ok(heads.has('authentication'), 'authentication must be a head');
  assert.ok(!heads.has('api'), 'api is subordinate and must not be a head');
});

test('headTokens steps over determiners to find the preposition', () => {
  // "an" sits between "to" and "api"; without skipping it the
  // preposition would be missed and "api" would look like a head.
  const heads = headTokens('add auth to an api');
  assert.ok(!heads.has('api'), 'api is subordinate and must not be a head');
});

// ------------------------------------------------------------- round4
test('round4 matches Python round(x, 4)', () => {
  assert.equal(round4(22.7556789), 22.7557);
  assert.equal(round4(0.00005), 0.0001);   // ties away from zero
  assert.equal(round4(26.97851234), 26.9785);
  assert.equal(round4(12.0), 12.0);
  assert.equal(round4(-1.23456789), -1.2346);
});

// ------------------------------------------------------------- golden
test('reproduces the golden search output exactly', () => {
  const golden = JSON.parse(readFileSync(GOLDEN, 'utf-8')) as Record<
    string,
    { ids: string[]; scores: number[]; total: number }
  >;
  let checked = 0;
  for (const [query, expected] of Object.entries(golden)) {
    const r = idx.search(query, { limit: 10 });
    assert.deepEqual(
      r.results.map((x) => x.id),
      expected.ids,
      `ids differ for ${JSON.stringify(query)}`,
    );
    assert.deepEqual(
      r.results.map((x) => x.score),
      expected.scores,
      `scores differ for ${JSON.stringify(query)}`,
    );
    assert.equal(r.total_matched, expected.total,
      `total differs for ${JSON.stringify(query)}`);
    checked++;
  }
  assert.ok(checked >= 60, `expected at least 60 golden queries, got ${checked}`);
});

// ------------------------------------------------------------- behaviour
test('a query with no library match returns nothing', () => {
  for (const q of ['zzzzqqqq nonexistent gibberish token',
                   'quantum chromodynamics lattice simulation',
                   'how to bake sourdough bread at home']) {
    const r = idx.search(q, { limit: 10 });
    assert.equal(r.returned, 0, `${q} returned ${r.returned} results`);
  }
});

test('a pure-stopword query returns nothing', () => {
  assert.equal(idx.search('the').returned, 0);
  assert.equal(idx.search('a an the of').returned, 0);
});

test('the limit is capped at 50', () => {
  assert.ok(idx.search('api', { limit: 500 }).results.length <= 50);
});

// ------------------------------------------------- the four count fields
//
// `total_matched`, `filtered_out`, `returned` and `truncated` have to
// tell one story. Before `filtered_out` existed, the relevance floor
// silently dropped entries: a query reported 52 matches, returned 37,
// and said `truncated: false` -- so the caller could not tell that 15
// had been dropped and that the match set was bigger than the page.
test('the four counts agree with each other', () => {
  const queries = ['test', 'api', 'documentation', 'write', 'database',
                   'deploy', 'review', 'security'];
  for (const q of queries) {
    for (const limit of [1, 10, 50, 500]) {
      const r = idx.search(q, { limit });
      const label = `${JSON.stringify(q)} limit=${limit}`;

      assert.ok(r.total_matched >= 0, `${label}: total_matched is negative`);
      assert.ok(r.filtered_out >= 0, `${label}: filtered_out is negative`);
      assert.ok(r.returned >= 0, `${label}: returned is negative`);

      // The match set is the kept entries plus the ones the floor
      // dropped. The kept entries are the ones on this page plus the
      // ones the page could not hold.
      const kept = r.total_matched - r.filtered_out;
      assert.ok(
        r.returned <= kept,
        `${label}: returned ${r.returned} exceeds the ${kept} kept entries`,
      );

      // `truncated` means "there is more to come", not "the page is
      // full". With a limit of 500 the page holds everything the floor
      // kept, so nothing is truncated.
      assert.equal(
        r.truncated,
        kept > r.returned,
        `${label}: truncated does not match the number of results`,
      );
    }
  }
});

test('the note names the number of results when entries were dropped', () => {
  // A query whose match set is larger than the page must say so.
  const r = idx.search('test', { limit: 500 });
  if (r.filtered_out > 0) {
    assert.match(r.note, /relevance floor/,
      'the note must name the relevance floor when it drops entries');
    assert.match(r.note, new RegExp(String(r.filtered_out)),
      'the note must name how many entries were dropped');
  }
  if (r.truncated) {
    assert.match(r.note, /of \d+ matches/,
      'the note must name the size of the match set when the page is short');
  }
});

test('a query with no match reports a coherent set of zeroes', () => {
  const r = idx.search('zzzzqqqq nonexistent gibberish token', { limit: 10 });
  assert.equal(r.total_matched, 0);
  assert.equal(r.filtered_out, 0);
  assert.equal(r.returned, 0);
  assert.equal(r.truncated, false);
  assert.equal(r.note, '');
});

// ------------------------------------------------------- the filter rules
test('the coverage rule requires the distinctive tokens, not the generic ones', () => {
  // "write" is generic; "documentation" is the subject. The rule must
  // not demand the generic verb, or the skill whose NAME is the subject
  // is dropped.
  const r = idx.search('write documentation', { limit: 10 });
  assert.equal(r.results[0]?.id, 'skill:documentation-lookup');
  assert.ok(r.returned > 1, 'more than one entry should survive');
});

test('a task row fires on its content, so the row is reachable', () => {
  // "write a REST API" is the "Build an API" row.
  const ids = idx.search('write a REST API', { limit: 10 }).results.map((x) => x.id);
  assert.ok(ids.includes('skill:api-design'), ids.join(', '));

  const k8s = idx.search('deploy to kubernetes', { limit: 10 }).results.map((x) => x.id);
  assert.equal(k8s[0], 'skill:kubernetes-patterns');
});

test('a content match is weaker than a strict one', () => {
  // "add authentication to an api" fires the "Build an API" row, but
  // the more specific auth skill must still come first.
  const ids = idx.search('add authentication to an api', { limit: 10 })
    .results.map((x) => x.id);
  assert.equal(ids[0], 'skill:twilio-security-api-auth');
});

test('a task row fires when its content is the query head', () => {
  // "write a REST API" is ABOUT an API, so the "Build an API" row
  // fires and the general API skill wins. Without the head rule the
  // row never fired -- "api" is too common to identify a task on its
  // own -- and a vendor skill whose name happens to contain
  // "rest api" took the top slot instead.
  const ids = idx.search('write a REST API', { limit: 10 }).results.map((x) => x.id);
  assert.equal(ids[0], 'skill:api-design', ids.join(', '));
});

test('the head rule does not fire on a subordinate noun', () => {
  // "add authentication to an api" is about authentication; "api" is
  // only the thing being added to. The "Build an API" row must not
  // fire, or the API builder would outrank the auth skill.
  const ids = idx.search('add authentication to an api', { limit: 10 })
    .results.map((x) => x.id);
  assert.equal(ids[0], 'skill:twilio-security-api-auth', ids.join(', '));
  assert.ok(!ids.slice(0, 3).includes('skill:api-design'), ids.join(', '));
});

test('a description-only match is still rejected', () => {
  assert.equal(idx.search('quantum chromodynamics lattice simulation').returned, 0);
  assert.equal(idx.search('bake sourdough bread at home').returned, 0);
});

test('the results are ordered by score, then tier, then kind, then name', () => {
  const r = idx.search('code', { limit: 50 });
  for (let i = 1; i < r.results.length; i++) {
    const a = r.results[i - 1];
    const b = r.results[i];
    if (a.score !== b.score) {
      assert.ok(a.score > b.score, 'scores must be descending');
      continue;
    }
    if (a.tier !== b.tier) {
      assert.ok(a.tier < b.tier, 'tier must break the tie ascending');
      continue;
    }
    if (a.kind !== b.kind) {
      assert.equal(a.kind, 'skill', 'a skill must come before an agent');
      continue;
    }
    assert.ok(
      a.name.length < b.name.length ||
        (a.name.length === b.name.length && a.name <= b.name),
      'shorter name first, then lexicographic',
    );
  }
});
