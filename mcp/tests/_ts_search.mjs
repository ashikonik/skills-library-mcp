// Drives the TypeScript search from the Python agreement test.
//
// Reads a JSON array of queries on argv[2] and writes a JSON object of
// {query: {ids, scores, total}} on stdout.
import { loadIndex } from '../dist/index-loader.js';
import { SearchIndex } from '../dist/search.js';

const queries = JSON.parse(process.argv[2]);
const idx = new SearchIndex(loadIndex());
const out = {};
for (const q of queries) {
  const r = idx.search(q, { limit: 10 });
  out[q] = {
    ids: r.results.map((x) => x.id),
    scores: r.results.map((x) => x.score),
    total: r.total_matched,
  };
}
process.stdout.write(JSON.stringify(out));
