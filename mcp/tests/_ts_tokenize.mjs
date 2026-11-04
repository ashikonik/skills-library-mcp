// Drives the TypeScript tokenizer from the Python agreement test.
//
// Reads a JSON array of strings on argv[2] and writes a JSON object of
// {input: tokenArray} on stdout.
//
// The head-noun set is returned alongside, under the key
// "__heads__": {input: [head, ...]}. `headTokens` decides whether a
// task row fires, so the two implementations must agree on it too --
// a divergence here would silently reorder results in one server.
import { tokenize, headTokens } from '../dist/tokenize.js';

const words = JSON.parse(process.argv[2]);
const out = {};
for (const w of words) {
  out[w] = tokenize(w);
}
out.__heads__ = {};
for (const w of words) {
  out.__heads__[w] = Array.from(headTokens(w)).sort();
}
process.stdout.write(JSON.stringify(out));
