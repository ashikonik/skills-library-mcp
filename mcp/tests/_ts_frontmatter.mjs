// Drives the TypeScript frontmatter reader from the Python agreement test.
//
// Reads a JSON array of library-relative paths on argv[2] and writes a
// JSON object of {path: {name, description, tools, model, parse_ok}}.
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseFrontmatter, normTools, regexFieldRaw } from '../dist/frontmatter.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const LIBRARY_ROOT = resolve(HERE, '..', '..');

const paths = JSON.parse(process.argv[2]);
const out = {};
for (const rel of paths) {
  const abs = join(LIBRARY_ROOT, rel);
  const fm = parseFrontmatter(abs);
  const field = (key) => {
    const v = fm.data?.[key];
    if (v === null || v === undefined) {
      const r = regexFieldRaw(fm.raw, key);
      return Array.isArray(r) ? r.join(', ') : r;
    }
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (Array.isArray(v)) return v.map((x) => String(x)).join(', ');
    return String(v).trim();
  };
  const tools = fm.data?.tools;
  out[rel] = {
    name: field('name'),
    description: field('description').split(/\s+/).filter(Boolean).join(' '),
    tools: tools === null || tools === undefined
      ? normTools(regexFieldRaw(fm.raw, 'tools'))
      : normTools(tools),
    model: field('model'),
    parse_ok: fm.parse_ok,
  };
}
process.stdout.write(JSON.stringify(out));
