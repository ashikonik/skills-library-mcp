// Computes the BM25 term for every entry and every query, and writes
// the results for the Python BM25 gate to compare.
//
// The comparison is on the *bit pattern*, not on a decimal rendering:
// two engines can print the same number differently and still differ
// by a unit in the last place. The bits are the number.
//
// Reads the queries on argv[2] as a JSON array of strings, and the
// BM25 weight on argv[3].
//
// The weight matters: at weight zero the arm contributes nothing to
// the score, so two engines that add it in different places in the
// sum would still agree on every score. The probe runs at a non-zero
// weight so the ordering guarantee is checked now.
import { loadIndex } from '../dist/index-loader.js';
import { SearchIndex, WEIGHT_BM25, setBm25Weight, bm25WeightInForce } from '../dist/search.js';
import { tokenize, bigrams, headTokens } from '../dist/tokenize.js';

const queries = JSON.parse(process.argv[2]);
const weight = process.argv[3] !== undefined ? Number(process.argv[3]) : WEIGHT_BM25;
const idx = new SearchIndex(loadIndex());
// Put the engine in force at the probe's weight, so the score the
// probe reports is the score the engine itself would produce.
setBm25Weight(weight);

// The bit pattern of a double, as a hex string. `DataView` reads the
// IEEE 754 bytes exactly, so two engines agree here only if they
// agree on every bit.
function bits(x) {
  const buf = new DataView(new ArrayBuffer(8));
  buf.setFloat64(0, x);
  let s = '';
  for (let i = 0; i < 8; i++) s += buf.getUint8(i).toString(16).padStart(2, '0');
  return s;
}

const out = {};
const mismatched = [];
let nonFinite = 0;

for (const q of queries) {
  const qTokens = tokenize(q);
  if (!qTokens.length) continue;
  const qBig = bigrams(qTokens);
  const qLower = q.toLowerCase().split(/\s+/).filter(Boolean).join(' ');
  const heads = headTokens(q);
  const row = {};
  for (const e of idx.entries) {
    const term = idx.bm25(e, qTokens);
    if (!Number.isFinite(term)) nonFinite++;
    row[e.id] = bits(term);
    // The score with the arm, for the inertness check.
    row[e.id + '\x00score'] = bits(idx.scoreEntry(e, qTokens, qBig, qLower, heads)[0]);
    // The score with the arm's contribution removed, computed by the
    // same code path. The Python gate checks that
    // `score == base + weight * term` exactly, which holds only if
    // the arm is added LAST in the sum.
    row[e.id + '\x00base'] = bits(idx.scoreEntryWithoutArm(e, qTokens, qBig, qLower, heads));
  }
  out[q] = row;
}

process.stdout.write(JSON.stringify({
  queries: Object.keys(out).length,
  mismatched,
  nonFinite,
  // The *shipped* constant, reported so the gate can check the
  // TypeScript engine's weight as well as Python's. The gate used to
  // check only Python, which meant the TypeScript engine could ship a
  // non-zero weight and the gate would still pass.
  shippedWeight: WEIGHT_BM25,
  weightInForce: bm25WeightInForce(),
  terms: out,
}));
