// Drives the TypeScript search from the Python agreement test.
//
// Reads a JSON array of queries on argv[2] and writes a JSON object of
// {query: {ids, scores, total, filtered_out, truncated, note}} on stdout.
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
    filtered_out: r.filtered_out,
    truncated: r.truncated,
    // The note states the counts the numeric fields carry. It is
    // part of the response, so the two implementations have to
    // agree on it word for word.
    note: r.note,
  };
}
process.stdout.write(JSON.stringify(out));
