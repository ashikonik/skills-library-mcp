// Drives the TypeScript string comparator from the Python agreement test.
//
// Reads a JSON array of [a, b] pairs on argv[2] and writes a JSON
// array of -1/0/1 on stdout: the comparator's verdict for each pair.
//
// The pair list lives in the Python test, so both implementations are
// driven over exactly the same inputs.
import { codepointCompare } from '../dist/search.js';

const pairs = JSON.parse(process.argv[2]);
const out = pairs.map(([a, b]) => codepointCompare(a, b));
process.stdout.write(JSON.stringify(out));
