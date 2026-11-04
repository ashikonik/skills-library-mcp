#!/usr/bin/env python3
"""A tolerant frontmatter reader, plus the per-harness emitters.

Stdlib only -- no `yaml` package. PyYAML is not guaranteed to be present
where the fallback runs, so this module hand-rolls the subset of YAML the
library actually uses, and falls back to a line-oriented parser when
even that fails.

Two things make this harder than a YAML parse:

  1. **Two agents have invalid YAML.** `Explore` and `silent-failure-hunter`
     carry an unquoted `:` inside a plain scalar, which PyYAML rejects.
     Rather than losing their whole frontmatter block, the reader falls
     back to a line-oriented parser and recovers the fields individually.
     The TypeScript server does the same thing, and the two must agree
     -- see `mcp/tests/test_agreement.py`.

  2. **Each harness wants a different dialect.** Claude Code skills use
     `allowed-tools`; Claude Code agents use `tools:` and `model:`;
     OpenCode agents use `mode:` and a `permission:` matrix instead of
     a tool allow-list; Codex wants a `metadata:` block plus an
     `agents/openai.yaml` sidecar; Cline wants plain markdown with no
     frontmatter at all. Unknown keys break the target's parser, so
     they are dropped -- and reported, not silently swallowed.
"""
import json
import os
import re

FRONTMATTER_RE = re.compile(r'^\s*---\s*\n(.*?)\n---', re.S)

# The keys the library's frontmatter uses. Anything outside this set is
# not read by the line-oriented parser.
FM_KEYS = (
    'name', 'description', 'tools', 'model', 'mode', 'permission',
    'license', 'version', 'compatibility', 'metadata', 'origin',
    'allowed-tools', 'disable-model-invocation', 'user-invocable',
    'argument-hint', 'color', 'effort', 'target', 'agents', 'handoffs',
    'tier', 'category', 'tags',
)


def frontmatter_block(text):
    """The raw frontmatter block, without the `---` fences."""
    m = FRONTMATTER_RE.match(text or '')
    return m.group(1) if m else ''


def regex_field(raw, key):
    """Read one field with the line-oriented parser.

    Handles the shapes the regex parser handled before -- a value on the
    same line as the key, and a `>`/`|` block scalar continued on the
    following indented lines -- and additionally the two shapes the
    library uses in the agents whose YAML does not parse:

      * an inline YAML list:  tools: ['search', 'read']
      * a quoted scalar:      model: 'opus'

    The inline list is returned as a real list, so it round-trips
    through `norm_tools` the way a parsed YAML list would.
    """
    if not raw:
        return ''
    m = re.search(r'^%s:\s*(.*)$' % re.escape(key), raw, re.M)
    if not m:
        return ''
    v = m.group(1).strip()
    if v in ('>', '|', '>-', '|-'):
        lines = raw.split('\n')
        try:
            i = next(k for k, l in enumerate(lines)
                     if l.startswith(key + ':'))
        except StopIteration:
            return ''
        buf = []
        for l in lines[i + 1:]:
            if l.strip() and not l.startswith(' '):
                break
            buf.append(l.strip())
        return ' '.join(x for x in buf if x).strip('"').strip("'").strip()
    if v.startswith('[') and v.endswith(']'):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip('"').strip("'")
                for x in inner.split(',') if x.strip()]
    if len(v) > 1 and v[0] == v[-1] and v[0] in ('"', "'"):
        return v[1:-1]
    return v.strip('"').strip("'")


def norm_tools(v):
    """Normalise the `tools:` field to a list of strings.

    Three shapes are in use across the library: a YAML list, a comma
    string and a space-separated string.
    """
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    if not s:
        return []
    if s.startswith('[') and s.endswith(']'):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except ValueError:
            pass
    if ',' in s:
        return [x.strip() for x in s.split(',') if x.strip()]
    return [x for x in s.split() if x]


def _parse_yaml_subset(raw):
    """Parse the subset of YAML the library uses, with no yaml package.

    Supports: `key: value`, `key: [a, b]`, `key:` followed by an
    indented block (a list of `- item` or a `key: value` mapping), and
    simple quoted scalars. This is deliberately minimal -- PyYAML is
    tried first when it is available.
    """
    out = {}
    lines = raw.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith('#'):
            i += 1
            continue
        if line.startswith((' ', '\t', '-')):
            i += 1
            continue
        m = re.match(r'^([A-Za-z0-9_.-]+):\s*(.*)$', line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val == '':
            # A block follows: a list, a nested mapping, or nothing.
            block = []
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or lines[j].startswith((' ', '\t'))):
                block.append(lines[j])
                j += 1
            out[key] = _parse_block(block)
            i = j
            continue
        if val.startswith('[') and val.endswith(']'):
            inner = val[1:-1].strip()
            out[key] = [x.strip().strip('"').strip("'")
                        for x in inner.split(',') if x.strip()] if inner else []
        elif val in ('true', 'false'):
            out[key] = val == 'true'
        elif val in ('null', '~'):
            out[key] = None
        else:
            out[key] = val.strip('"').strip("'")
        i += 1
    return out


def _parse_block(block):
    """Parse an indented block: a list of `- item`, or a mapping."""
    items = [l for l in block if l.strip()]
    if not items:
        return None
    if all(l.strip().startswith('- ') or l.strip() == '-' for l in items):
        return [l.strip()[1:].strip().strip('"').strip("'") for l in items]
    mapping = {}
    for l in items:
        m = re.match(r'^\s*([A-Za-z0-9_.-]+):\s*(.*)$', l)
        if m:
            mapping[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return mapping or None


def parse_frontmatter(path):
    """(data, parse_ok, parse_error, text, raw) for one document.

    PyYAML is used when it is installed and the block parses; otherwise
    the hand-rolled subset parser; otherwise the line-oriented reader.
    """
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError as e:
        return {}, False, str(e), '', ''

    raw = frontmatter_block(text)
    if not raw:
        return {}, True, None, text, ''

    try:
        import yaml
    except ImportError:
        yaml = None

    if yaml is not None:
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as e:
            # Not valid YAML -- fall through to the subset parser, which
            # recovers the fields the library actually stores.
            data = _parse_yaml_subset(raw)
            return data, False, str(e).split('\n')[0], text, raw
        if isinstance(data, dict):
            return data, True, None, text, raw
        return _parse_yaml_subset(raw), False, 'frontmatter is not a mapping', text, raw

    data = _parse_yaml_subset(raw)
    return data, True, None, text, raw


def field_of(raw, data, key):
    """Read one field, preferring the parsed map and falling back to the
    line-oriented reader.

    A list is joined with ', ' either way, so a parsed YAML list and a
    regex-recovered inline list produce the same string.
    """
    v = (data or {}).get(key)
    if v is None:
        v = regex_field(raw, key)
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (list, tuple)):
        return ', '.join(str(x) for x in v)
    return str(v).strip()


def read_body(path):
    """The body of a document, without its frontmatter block."""
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError:
        return ''
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text
    return text[m.end():].lstrip('\n')


# ---------------------------------------------------------------- emitters
TOOL_TO_PERMISSION = {
    'Read': 'allow', 'Grep': 'allow', 'Glob': 'allow', 'Write': 'allow',
    'Edit': 'allow', 'Bash': 'allow', 'WebFetch': 'ask', 'WebSearch': 'ask',
}

HARNESSES = ('claude-code', 'codex', 'codex-agents', 'opencode', 'cline',
             'puku-cli', 'agentsmd')


def permission_map(tools):
    """The `tools:` -> `permission:` mapping for OpenCode agents.

    OpenCode agents take a permission *matrix*, not a tool allow-list, so
    the two have to be translated rather than copied. Verified against the
    live `~/.config/opencode/agents/architect.md`, which uses
    `mode: subagent` and `permission: {edit: deny, read: allow, bash: allow}`.
    """
    perm = {'edit': 'deny', 'read': 'allow', 'bash': 'deny'}
    for t in tools or []:
        p = TOOL_TO_PERMISSION.get(t)
        if not p:
            continue
        if t in ('Read', 'Grep', 'Glob'):
            perm['read'] = p
        elif t in ('Write', 'Edit', 'NotebookEdit'):
            perm['edit'] = p
        elif t == 'Bash':
            perm['bash'] = p
        elif t in ('WebFetch', 'WebSearch'):
            perm['web'] = p
    return perm


def yaml_scalar(s):
    """Quote a value only when YAML would misread it unquoted.

    A plain YAML scalar may contain `-`, `.`, `/` and most punctuation.
    What it may not do is start with an indicator character, contain
    `: ` or ` #`, or be something YAML would parse as a number or a
    boolean. Quoting everything would be safe but ugly -- and it would
    make the emitted frontmatter differ from what the harnesses
    themselves write.
    """
    if s == '':
        return "''"
    if s != s.strip():
        return json.dumps(s)
    if re.match(r'^[-?:,\[\]{}#&*!|>\'"%@`]', s):
        return json.dumps(s)
    if ': ' in s or ' #' in s:
        return json.dumps(s)
    if re.match(r'^(true|false|null|yes|no|on|off|~)$', s, re.I):
        return json.dumps(s)
    if re.match(r'^[-+]?(\d[\d_]*(\.\d*)?([eE][-+]?\d+)?|\.\d+)$', s):
        return json.dumps(s)
    if s.endswith(':'):
        return json.dumps(s)
    return s


def _fm_block(lines):
    return '\n'.join(['---'] + lines + ['---', ''])


def emit_skill(harness, name, description, allowed_tools=None):
    """(content, dropped_keys) for a skill in this harness's dialect."""
    dropped = []
    if harness == 'cline':
        # Cline has no skills mechanism. The rule is plain markdown, with
        # no frontmatter -- a `---` block would be read as content.
        return '# %s\n\n%s\n' % (name, description), dropped
    if harness == 'agentsmd':
        # An AGENTS.md is a document, not a skill file. Plain markdown.
        return '## %s\n\n%s\n' % (name, description), dropped
    if harness == 'claude-code':
        lines = ['name: %s' % yaml_scalar(name),
                 'description: %s' % yaml_scalar(description)]
        if allowed_tools:
            lines.append('allowed-tools: [%s]'
                         % ', '.join(yaml_scalar(t) for t in allowed_tools))
        else:
            dropped.append('allowed-tools')
        return _fm_block(lines), dropped
    lines = ['name: %s' % yaml_scalar(name),
             'description: %s' % yaml_scalar(description)]
    return _fm_block(lines), dropped


def emit_openai_agent_yaml(name, description):
    """The Codex `agents/openai.yaml` sidecar."""
    return ('interface:\n'
            '  display_name: %s\n'
            '  short_description: %s\n' % (yaml_scalar(name),
                                           yaml_scalar(description[:80])))


# The marker that delimits one skill's section in a shared AGENTS.md.
# It carries the skill name, so two skills in the same file can be
# told apart and one can be replaced without disturbing the other.
AGENTSMD_MARKER_PREFIX = '<!-- skills-library:'
AGENTSMD_MARKER = AGENTSMD_MARKER_PREFIX + '%s -->'


def emit_agentsmd_section(name, description, body=''):
    """One skill's section in an `AGENTS.md`.

    Plain markdown, no frontmatter -- an `AGENTS.md` is read as a
    document, not parsed as a skill. The marker is an HTML comment, so
    it is invisible in the rendered file but unambiguous on disk.
    """
    text = '%s\n## %s\n\n%s\n' % (AGENTSMD_MARKER % name, name, description)
    if body:
        text += '\n' + body.strip() + '\n'
    return text


def emit_agent(harness, name, description, tools=None, model='', mode=''):
    """(content, dropped_keys) for an agent in this harness's dialect."""
    dropped = []
    if harness == 'cline':
        return '', ['agent']
    if harness == 'claude-code':
        lines = ['name: %s' % yaml_scalar(name),
                 'description: %s' % yaml_scalar(description)]
        if tools:
            lines.append('tools: [%s]' % ', '.join(yaml_scalar(t) for t in tools))
        if model:
            lines.append('model: %s' % yaml_scalar(model))
        return _fm_block(lines), dropped
    if harness == 'opencode':
        lines = ['description: %s' % yaml_scalar(description),
                 'mode: %s' % (mode or 'subagent'),
                 'permission:']
        for k, v in permission_map(tools).items():
            lines.append('  %s: %s' % (k, v))
        return _fm_block(lines), dropped
    lines = ['name: %s' % yaml_scalar(name),
             'description: %s' % yaml_scalar(description)]
    return _fm_block(lines), dropped
