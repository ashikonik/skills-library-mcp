// Checks that the TypeScript server accepts the field-aware postings.
//
// The builder now writes `postings[field][kind][token]`. The compiled
// server has to read that shape -- the type declares it, but a type
// declaration is not a runtime check, and an index whose postings the
// server cannot read would fail silently at the point of use.
//
// Writes a JSON summary on stdout: the field list, the postings
// fields, and whether they agree.
import { loadIndex } from '../dist/index-loader.js';

const data = loadIndex();
const fields = data.search.fields ?? [];
const postings = data.search.postings ?? {};

const missing = fields.filter((f) => !(f in postings));
const extra = Object.keys(postings).filter((f) => !fields.includes(f));

// The postings must resolve: every id in every bucket must be a real
// entry id, in the bucket's own kind.
const byId = new Map();
for (const e of [...(data.skills ?? []), ...(data.agents ?? [])]) {
  byId.set(e.id, e);
}
const unknown = [];
for (const [field, kinds] of Object.entries(postings)) {
  for (const [kind, bucket] of Object.entries(kinds)) {
    for (const [token, ids] of Object.entries(bucket)) {
      for (const id of ids) {
        const e = byId.get(id);
        if (!e) unknown.push(`${field}/${kind}/${token}/${id}`);
        else if (e.kind !== kind) unknown.push(`${field}/${kind}/${token}/${id}`);
      }
    }
  }
}

// The curated fields must actually hold something.
const empty = fields.filter((field) => {
  const kinds = postings[field] ?? {};
  let n = 0;
  for (const bucket of Object.values(kinds)) {
    for (const ids of Object.values(bucket)) n += ids.length;
  }
  return n === 0;
});

const out = { fields, postingFields: Object.keys(postings), missing, extra, unknown, empty };
process.stdout.write(JSON.stringify(out));

if (missing.length || extra.length || unknown.length || empty.length) {
  process.exitCode = 1;
}
