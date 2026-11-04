/**
 * A tolerant frontmatter reader, plus the per-harness emitters.
 *
 * Two things make this harder than a YAML parse:
 *
 *  1. **Two agents have invalid YAML.** `Explore` and `silent-failure-hunter`
 *     carry an unquoted `:` inside a plain scalar, which PyYAML rejects.
 *     Rather than losing their whole frontmatter block, the reader falls
 *     back to a line-oriented parser and recovers the fields individually.
 *     The Python fallback server does the same thing, and the two must
 *     agree -- see `mcp/tests/test_agreement.py`.
 *
 *  2. **Each harness wants a different dialect.** Claude Code skills use
 *     `allowed-tools`; Claude Code agents use `tools:` and `model:`;
 *     OpenCode agents use `mode:` and a `permission:` matrix instead of
 *     a tool allow-list; Codex wants a `metadata:` block plus an
 *     `agents/openai.yaml` sidecar; Cline wants plain markdown with no
 *     frontmatter at all. Unknown keys break the target's parser, so
 *     they are dropped -- and reported, not silently swallowed.
 */
import YAML from 'yaml';
import { readFileSync, existsSync } from 'node:fs';

export interface ParsedFrontmatter {
  data: Record<string, unknown>;
  parse_ok: boolean;
  parse_error: string | null;
  text: string;
  raw: string;
}

/** Extract the raw frontmatter block, without the `---` fences. */
export function frontmatterBlock(text: string): string {
  const m = /^\s*---\s*\n([\s\S]*?)\n---/.exec(text);
  return m ? m[1] : '';
}

/**
 * Read one field with the line-oriented parser — the YAML fallback.
 *
 * Handles the two shapes the regex parser handled before: a value on the
 * same line as the key, and a `>`/`|` block scalar continued on the
 * following indented lines.
 */
export function regexField(raw: string, key: string): string {
  if (!raw) return '';
  const re = new RegExp(`^${escapeRegExp(key)}:\\s*(.*)$`, 'm');
  const m = re.exec(raw);
  if (!m) return '';
  const v = m[1].trim();
  if (v === '>' || v === '|' || v === '>-' || v === '|-') {
    const lines = raw.split('\n');
    let i = lines.findIndex((l) => l.startsWith(key + ':'));
    if (i < 0) return '';
    const buf: string[] = [];
    for (const l of lines.slice(i + 1)) {
      if (l.trim() && !l.startsWith(' ')) break;
      buf.push(l.trim());
    }
    return buf
      .filter(Boolean)
      .join(' ')
      .trim()
      .replace(/^["']|["']$/g, '');
  }
  return v.replace(/^["']|["']$/g, '');
}

/**
 * Read one field with the line-oriented parser, keeping the two shapes
 * the library uses in the agents whose YAML does not parse:
 *
 *   * an inline YAML list:  tools: ['search', 'read']
 *   * a quoted scalar:      model: 'opus'
 *
 * The inline list is returned as a real array, so it round-trips
 * through `normTools` the way a parsed YAML list would.
 */
export function regexFieldRaw(raw: string, key: string): string | string[] {
  if (!raw) return '';
  const re = new RegExp(`^${escapeRegExp(key)}:\\s*(.*)$`, 'm');
  const m = re.exec(raw);
  if (!m) return '';
  const v = m[1].trim();
  if (v === '>' || v === '|' || v === '>-' || v === '|-') {
    const lines = raw.split('\n');
    const i = lines.findIndex((l) => l.startsWith(key + ':'));
    if (i < 0) return '';
    const buf: string[] = [];
    for (const l of lines.slice(i + 1)) {
      if (l.trim() && !l.startsWith(' ')) break;
      buf.push(l.trim());
    }
    return buf
      .filter(Boolean)
      .join(' ')
      .trim()
      .replace(/^["']|["']$/g, '');
  }
  if (v.startsWith('[') && v.endsWith(']')) {
    const inner = v.slice(1, -1).trim();
    if (!inner) return [];
    return inner
      .split(',')
      .map((x) => x.trim().replace(/^["']|["']$/g, ''))
      .filter((x) => x.length > 0);
  }
  if (v.length > 1 && v[0] === v[-1] && (v[0] === '"' || v[0] === "'")) {
    return v.slice(1, -1);
  }
  return v.replace(/^["']|["']$/g, '');
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Parse the subset of YAML the library uses, with no YAML parser.
 *
 * Supports: `key: value`, `key: [a, b]`, `key:` followed by an
 * indented block (a list of `- item` or a `key: value` mapping), and
 * simple quoted scalars. This is deliberately minimal -- the `yaml`
 * package is tried first when the block parses.
 *
 * It exists because two agents carry an unquoted `:` inside a plain
 * scalar, which a strict YAML parser rejects. Losing their whole
 * frontmatter block would be worse than reading it approximately, and
 * the Python fallback does exactly the same thing.
 */
export function parseYamlSubset(raw: string): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  const lines = raw.split('\n');
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim() || line.trim().startsWith('#')) {
      i++;
      continue;
    }
    if (/^[ \t-]/.test(line)) {
      i++;
      continue;
    }
    const m = /^([A-Za-z0-9_.-]+):\s*(.*)$/.exec(line);
    if (!m) {
      i++;
      continue;
    }
    const key = m[1];
    const val = m[2].trim();
    if (val === '') {
      // A block follows: a list, a nested mapping, or nothing.
      const block: string[] = [];
      let j = i + 1;
      while (j < lines.length && (!lines[j].trim() || /^[ \t]/.test(lines[j]))) {
        block.push(lines[j]);
        j++;
      }
      out[key] = parseBlock(block);
      i = j;
      continue;
    }
    if (val.startsWith('[') && val.endsWith(']')) {
      const inner = val.slice(1, -1).trim();
      out[key] = inner
        ? inner
            .split(',')
            .map((x) => x.trim().replace(/^["']|["']$/g, ''))
            .filter((x) => x.length > 0)
        : [];
    } else if (val === 'true' || val === 'false') {
      out[key] = val === 'true';
    } else if (val === 'null' || val === '~') {
      out[key] = null;
    } else {
      out[key] = val.replace(/^["']|["']$/g, '');
    }
    i++;
  }
  return out;
}

function parseBlock(block: string[]): unknown {
  const items = block.filter((l) => l.trim());
  if (items.length === 0) return null;
  if (items.every((l) => l.trim().startsWith('- ') || l.trim() === '-')) {
    return items.map((l) =>
      l.trim().slice(1).trim().replace(/^["']|["']$/g, ''),
    );
  }
  const mapping: Record<string, string> = {};
  for (const l of items) {
    const m = /^\s*([A-Za-z0-9_.-]+):\s*(.*)$/.exec(l);
    if (m) mapping[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
  }
  return Object.keys(mapping).length > 0 ? mapping : null;
}

/**
 * Parse a document's frontmatter.
 *
 * The `yaml` package is tried first; when the block is not valid YAML,
 * the lenient subset parser takes over, and the raw frontmatter is
 * kept so that individual fields can still be recovered.
 */
export function parseFrontmatter(path: string): ParsedFrontmatter {
  let text = '';
  try {
    text = readFileSync(path, 'utf-8');
  } catch {
    return { data: {}, parse_ok: false, parse_error: 'file not readable', text: '', raw: '' };
  }
  const raw = frontmatterBlock(text);
  if (!raw) return { data: {}, parse_ok: true, parse_error: null, text, raw: '' };
  try {
    const parsed = YAML.parse(raw);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return {
        data: parsed as Record<string, unknown>,
        parse_ok: true,
        parse_error: null,
        text,
        raw,
      };
    }
    return {
      data: parseYamlSubset(raw),
      parse_ok: false,
      parse_error: 'frontmatter is not a mapping',
      text,
      raw,
    };
  } catch (e) {
    // Not valid YAML -- fall through to the subset parser, which
    // recovers the fields the library actually stores.
    return {
      data: parseYamlSubset(raw),
      parse_ok: false,
      parse_error: e instanceof Error ? e.message.split('\n')[0] : String(e),
      text,
      raw,
    };
  }
}

/**
 * Normalise the `tools:` field to a string array.
 *
 * Three shapes are in use across the library: a YAML list, a comma string
 * and a space-separated string.
 */
export function normTools(v: unknown): string[] {
  if (v === null || v === undefined) return [];
  if (Array.isArray(v)) {
    return v.map((x) => String(x).trim()).filter((x) => x.length > 0);
  }
  const s = String(v).trim();
  if (!s) return [];
  if (s.startsWith('[') && s.endsWith(']')) {
    try {
      const parsed = JSON.parse(s);
      if (Array.isArray(parsed)) {
        return parsed.map((x) => String(x).trim()).filter((x) => x.length > 0);
      }
    } catch {
      /* fall through */
    }
  }
  if (s.includes(',')) {
    return s
      .split(',')
      .map((x) => x.trim())
      .filter((x) => x.length > 0);
  }
  return s.split(/\s+/).filter((x) => x.length > 0);
}

/**
 * Read one field, preferring YAML and falling back to the line parser.
 *
 * The builder does the same thing, so an agent whose frontmatter is not
 * valid YAML gets the same description the library recorded.
 */
export function fieldOf(raw: string, data: Record<string, unknown>, key: string): string {
  const v = data?.[key];
  if (v === null || v === undefined) return regexField(raw, key);
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (Array.isArray(v)) return v.map((x) => String(x)).join(', ');
  return String(v).trim();
}

// ---------------------------------------------------------------- emitters

export type Harness =
  | 'claude-code'
  | 'codex'
  | 'codex-agents'
  | 'opencode'
  | 'cline'
  | 'puku-cli'
  | 'agentsmd';

export interface SkillInput {
  name: string;
  description: string;
  allowed_tools?: string[];
}

export interface AgentInput {
  name: string;
  description: string;
  tools?: string[];
  model?: string;
  mode?: string;
}

/**
 * The `tools:` -> `permission:` mapping for OpenCode agents.
 *
 * OpenCode agents take a permission *matrix*, not a tool allow-list, so
 * the two have to be translated rather than copied. Verified against the
 * live `~/.config/opencode/agents/architect.md`, which uses
 * `mode: subagent` and `permission: {edit: deny, read: allow, bash: allow}`.
 */
export const TOOL_TO_PERMISSION: Record<string, 'allow' | 'deny' | 'ask'> = {
  Read: 'allow',
  Grep: 'allow',
  Glob: 'allow',
  Write: 'allow',
  Edit: 'allow',
  Bash: 'allow',
  WebFetch: 'ask',
  WebSearch: 'ask',
};

export function permissionMap(tools: string[]): Record<string, string> {
  const perm: Record<string, string> = {
    edit: 'deny',
    read: 'allow',
    bash: 'deny',
  };
  for (const t of tools) {
    const p = TOOL_TO_PERMISSION[t];
    if (!p) continue;
    if (t === 'Read' || t === 'Grep' || t === 'Glob') perm.read = p;
    else if (t === 'Write' || t === 'Edit' || t === 'NotebookEdit') perm.edit = p;
    else if (t === 'Bash') perm.bash = p;
    else if (t === 'WebFetch' || t === 'WebSearch') perm.web = p;
  }
  return perm;
}

export interface Emitted {
  content: string;
  dropped_keys: string[];
}

function fmBlock(lines: string[]): string {
  return ['---', ...lines, '---', ''].join('\n');
}

/**
 * Quote a value only when YAML would misread it unquoted.
 *
 * A plain YAML scalar may contain `-`, `.`, `/` and most punctuation.
 * What it may not do is start with an indicator character, contain
 * `: ` or ` #`, or be something YAML would parse as a number or a
 * boolean. Quoting everything would be safe but ugly -- and it would
 * make the emitted frontmatter differ from what the harnesses
 * themselves write.
 */
function yamlScalar(s: string): string {
  if (s === '') return "''";
  if (s !== s.trim()) return JSON.stringify(s);
  if (/^[-?:,[\]{}#&*!|>'"%@`]/.test(s)) return JSON.stringify(s);
  if (/: /.test(s) || / #/.test(s)) return JSON.stringify(s);
  if (/^(true|false|null|yes|no|on|off|~)$/i.test(s)) return JSON.stringify(s);
  if (/^[-+]?(\d[\d_]*(\.\d*)?([eE][-+]?\d+)?|\.\d+)$/.test(s)) {
    return JSON.stringify(s);
  }
  if (s.endsWith(':')) return JSON.stringify(s);
  return s;
}

/** Claude Code / puku-cli / OpenCode skill: `name` + `description`. */
export function emitSkill(harness: Harness, s: SkillInput): Emitted {
  const dropped: string[] = [];
  switch (harness) {
    case 'cline':
      // Cline has no skills mechanism. The rule is plain markdown, with
      // no frontmatter -- a `---` block would be read as content.
      return {
        content: `# ${s.name}\n\n${s.description}\n`,
        dropped_keys: dropped,
      };
    case 'claude-code': {
      const lines = [`name: ${yamlScalar(s.name)}`, `description: ${yamlScalar(s.description)}`];
      if (s.allowed_tools && s.allowed_tools.length > 0) {
        lines.push(`allowed-tools: [${s.allowed_tools.map((t) => yamlScalar(t)).join(', ')}]`);
      } else {
        dropped.push('allowed-tools');
      }
      return { content: fmBlock(lines), dropped_keys: dropped };
    }
    case 'codex':
    case 'codex-agents': {
      const lines = [`name: ${yamlScalar(s.name)}`, `description: ${yamlScalar(s.description)}`];
      return { content: fmBlock(lines), dropped_keys: dropped };
    }
    case 'opencode': {
      const lines = [`name: ${yamlScalar(s.name)}`, `description: ${yamlScalar(s.description)}`];
      return { content: fmBlock(lines), dropped_keys: dropped };
    }
    case 'agentsmd':
      return { content: `## ${s.name}\n\n${s.description}\n`, dropped_keys: dropped };
    default:
      return {
        content: fmBlock([`name: ${yamlScalar(s.name)}`, `description: ${yamlScalar(s.description)}`]),
        dropped_keys: dropped,
      };
  }
}

/** The Codex `agents/openai.yaml` sidecar. */
export function emitOpenAIAgentYaml(s: SkillInput): string {
  return [
    'interface:',
    `  display_name: ${yamlScalar(s.name)}`,
    `  short_description: ${yamlScalar(s.description.slice(0, 80))}`,
    '',
  ].join('\n');
}

/**
 * The marker that delimits one skill's section in a shared AGENTS.md.
 * It carries the skill name, so two skills in the same file can be
 * told apart and one can be replaced without disturbing the other.
 */
export const AGENTSMD_MARKER_PREFIX = '<!-- skills-library:';
export const AGENTSMD_MARKER = AGENTSMD_MARKER_PREFIX + '%s -->';

export function agentsmdMarker(name: string): string {
  return AGENTSMD_MARKER.replace('%s', name);
}

/**
 * One skill's section in an `AGENTS.md`.
 *
 * Plain markdown, no frontmatter -- an `AGENTS.md` is read as a
 * document, not parsed as a skill. The marker is an HTML comment, so
 * it is invisible in the rendered file but unambiguous on disk.
 */
export function emitAgentsmdSection(
  name: string,
  description: string,
  body = '',
): string {
  let text = `${agentsmdMarker(name)}\n## ${name}\n\n${description}\n`;
  if (body) {
    text += `\n${body.trim()}\n`;
  }
  return text;
}

/**
 * Replace the section starting at `marker` with `section`.
 *
 * The section runs until the next marker, or to the end of the file.
 */
export function replaceSection(text: string, marker: string, section: string): string {
  const start = text.indexOf(marker);
  if (start < 0) return text;
  const rest = text.slice(start + marker.length);
  const nxt = rest.indexOf(AGENTSMD_MARKER_PREFIX);
  const end = nxt < 0 ? text.length : start + marker.length + nxt;
  return text.slice(0, start) + section + text.slice(end);
}

/** Claude Code / OpenCode agent frontmatter. */
export function emitAgent(harness: Harness, a: AgentInput): Emitted {
  const dropped: string[] = [];
  switch (harness) {
    case 'cline':
      // Agents are not supported for Cline; the caller reports that.
      return { content: '', dropped_keys: ['agent'] };
    case 'claude-code': {
      const lines = [`name: ${yamlScalar(a.name)}`, `description: ${yamlScalar(a.description)}`];
      if (a.tools && a.tools.length > 0) {
        lines.push(`tools: [${a.tools.map((t) => yamlScalar(t)).join(', ')}]`);
      }
      if (a.model) lines.push(`model: ${yamlScalar(a.model)}`);
      return { content: fmBlock(lines), dropped_keys: dropped };
    }
    case 'opencode': {
      const lines = [`description: ${yamlScalar(a.description)}`];
      lines.push(`mode: ${a.mode || 'subagent'}`);
      const perm = permissionMap(a.tools ?? []);
      lines.push('permission:');
      for (const [k, v] of Object.entries(perm)) {
        lines.push(`  ${k}: ${v}`);
      }
      return { content: fmBlock(lines), dropped_keys: dropped };
    }
    case 'agentsmd':
      return { content: `## ${a.name}\n\n${a.description}\n`, dropped_keys: dropped };
    default:
      return {
        content: fmBlock([`name: ${yamlScalar(a.name)}`, `description: ${yamlScalar(a.description)}`]),
        dropped_keys: dropped,
      };
  }
}

/** Read a skill's SKILL.md body, minus its frontmatter. */
export function readBody(path: string): { body: string; frontmatter: ParsedFrontmatter } {
  const fm = parseFrontmatter(path);
  let body = fm.text;
  if (fm.raw) {
    const idx = fm.text.indexOf(`\n---`, fm.text.indexOf('---') + 3);
    body = idx >= 0 ? fm.text.slice(idx + 4) : fm.text;
  }
  return { body: body.replace(/^\n+/, ''), frontmatter: fm };
}

export function fileExists(p: string): boolean {
  return existsSync(p);
}
