/**
 * The TypeScript provenance, reported as JSON.
 *
 * The point of this script is parity: the Python implementation and
 * this one must agree about every entry's owner, licence and verdict,
 * and about what each filter narrows to. A client that talks to one
 * server and then the other must not see a different licence.
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { SearchIndex } from '../dist/search.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const MCP = dirname(HERE);
const index = JSON.parse(
  readFileSync(join(MCP, 'data', 'index.json'), 'utf-8'),
);

const search = new SearchIndex(index);

// Every entry, with its three provenance fields. The comparison is
// against the index the Python side reads, so a drift in either
// implementation shows up as a disagreement.
const entries = [...index.skills, ...index.agents].map((e) => ({
  id: e.id,
  owner: e.provenance?.owner ?? '',
  license: e.provenance?.license ?? '',
  verdict: e.provenance?.verdict ?? '',
}));

// The provenance the *search* reports.
//
// Reading the index above only proves the index is intact. It does
// not prove the server tells the truth: a search result could carry
// a blank owner, or claim every entry is redistributable, and the
// index would still be perfectly consistent. The fields below come
// out of the result objects the search actually builds, so a lie in
// the result assembly shows up here.
const searchProvenance = new Map();
for (const query of ['test', 'accessibility audit', 'python']) {
  const out = search.search(query, { limit: 100 });
  for (const r of out.results) {
    searchProvenance.set(r.id, {
      id: r.id,
      owner: r.owner ?? '',
      license: r.license ?? '',
      verdict: r.verdict ?? '',
    });
  }
}
const reported = [...searchProvenance.values()];

// The filters. Each is a real question a caller can ask, and each
// must narrow to the same set in both implementations.
const FILTERS = [
  { label: 'verdict=redistributable', query: 'test', verdict: 'redistributable' },
  { label: 'verdict=included-with-terms', query: 'test', verdict: 'included-with-terms' },
  { label: 'license=MIT', query: 'test', license: 'MIT' },
];

// One container, taken from the library itself so the probe does not
// have to know the name.
const containers = [...new Set(
  [...index.skills, ...index.agents]
    .map((e) => e.provenance?.container)
    .filter(Boolean),
)].sort();
if (containers.length > 0) {
  FILTERS.push({
    label: `source=${containers[0]}`,
    query: 'test',
    source: containers[0],
  });
}

const filters = FILTERS.map((f) => {
  const opts = { limit: 50 };
  if (f.verdict !== undefined) opts.verdict = f.verdict;
  if (f.license !== undefined) opts.license = f.license;
  if (f.source !== undefined) opts.source = f.source;
  const out = search.search(f.query, opts);
  return {
    label: f.label,
    query: f.query,
    verdict: f.verdict ?? null,
    license: f.license ?? null,
    source: f.source ?? null,
    ids: out.results.map((r) => r.id).sort(),
  };
});

process.stdout.write(JSON.stringify({ entries, reported, filters }, null, 2));
