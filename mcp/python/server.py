#!/usr/bin/env python3
"""The stdlib-only Python fallback MCP server.

This runs when the TypeScript server is unavailable -- no Node, no
`npm install`, no MCP SDK. It speaks the same JSON-RPC 2.0 over stdio
as the SDK, and exposes the same 8 tools with the same behaviour, so a
client cannot tell which one it is talking to apart from the
implementation.

Four properties matter, and three of them are ways this kind of server
usually breaks:

  1. **stdout is protocol-only.** All logging goes to stderr. A stray
     `print` corrupts the stream -- this is the single most common way
     a hand-rolled MCP server fails.
  2. **Notifications get no response.** `notifications/initialized` has
     no `id`, so replying to it would be a protocol error.
  3. **Never raise out of the loop.** Every handler exception becomes a
     JSON-RPC error, not a crash.
  4. **The tool list and the search results must match the TypeScript
     server exactly.** `mcp/tests/test_agreement.py` is the gate.

Messages are newline-delimited JSON, exactly as the SDK serialises them
(`JSON.stringify(m) + '\\n'`).
"""
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from search import load_index, DEFAULT_LIMIT, MAX_LIMIT   # noqa: E402
from installers import (                            # noqa: E402
    install_skill, install_agent, uninstall_target,
    skill_target_path, uninstall_skill_path,
)

PROTOCOL_VERSIONS = ('2025-11-25', '2025-06-18', '2025-03-26',
                     '2024-11-05', '2024-10-07')

DEFAULT_BUNDLE_BYTES = 200_000
MAX_BUNDLE_BYTES = 2_000_000

TOOLS = [
    {
        'name': 'search_library',
        'title': 'Search library',
        'description': (
            'Rank skills and agents by relevance to a query. Returns scored '
            'candidates with the terms each matched on. Covers all 976 skills '
            'and 102 agents. Not covered by get_skill, which returns one '
            'document in full.'),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'minLength': 1, 'maxLength': 500},
                'limit': {'type': 'integer', 'minimum': 1, 'maximum': MAX_LIMIT,
                          'default': DEFAULT_LIMIT},
                'kind': {'type': 'string', 'enum': ['skill', 'agent']},
                'tier': {'type': 'integer', 'enum': [1, 2, 3]},
                'domain': {'type': 'string'},
                'include_body': {'type': 'boolean', 'default': False},
            },
            'required': ['query'],
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
    },
    {
        'name': 'get_skill',
        'title': 'Get skill',
        'description': (
            'Returns one skill: its SKILL.md body, parsed frontmatter, and the '
            'manifest of its supporting files. Accepts a namespaced id '
            '(skill:tdd-workflow) or a bare name. Not covered by '
            'get_skill_bundle, which returns the supporting files themselves.'),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'id': {'type': 'string', 'minLength': 1},
                'include_body': {'type': 'boolean', 'default': True},
            },
            'required': ['id'],
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
    },
    {
        'name': 'get_agent',
        'title': 'Get agent',
        'description': (
            'Returns one agent: its definition body and parsed frontmatter, '
            'including its tool allow-list and model. Accepts a namespaced id '
            '(agent:code-reviewer) or a bare name. Not covered by '
            'install_agents, which writes it into a harness.'),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'id': {'type': 'string', 'minLength': 1},
                'include_held_aside': {'type': 'boolean', 'default': False},
            },
            'required': ['id'],
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
    },
    {
        'name': 'get_skill_bundle',
        'title': 'Get skill bundle',
        'description': (
            "Returns a skill's supporting files. With no files argument it "
            'returns the manifest only — paths, sizes and which references '
            "resolve. With files it returns those files' contents, up to a "
            'byte cap. Not covered by get_skill, which returns the SKILL.md '
            'body.'),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'id': {'type': 'string', 'minLength': 1},
                'files': {'type': 'array', 'items': {'type': 'string'},
                          'maxItems': 50},
                'max_bytes': {'type': 'integer', 'minimum': 1,
                              'maximum': MAX_BUNDLE_BYTES,
                              'default': DEFAULT_BUNDLE_BYTES},
            },
            'required': ['id'],
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
    },
    {
        'name': 'list_library',
        'title': 'List library',
        'description': (
            "Lists the library's structure: its domains, tiers, the six "
            'hand-authored packs, the task-type index, or overall statistics. '
            'Not covered by search_library, which ranks entries by relevance '
            'to a query.'),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'section': {'type': 'string',
                            'enum': ['domains', 'tiers', 'packs', 'tasks', 'stats'],
                            'default': 'stats'},
            },
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
    },
    {
        'name': 'install_skills',
        'title': 'Install skills',
        'description': (
            'Installs skills into a coding harness so they auto-activate. '
            'Writes a symlink into the library by default, so the installed '
            'skill stays in sync with the source. Dry run unless apply is '
            'true. Not covered by search_library, which finds candidates but '
            'writes nothing.'),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'harness': {'type': 'string', 'enum': [
                    'claude-code', 'codex', 'codex-agents', 'opencode',
                    'cline', 'puku-cli', 'agentsmd']},
                'ids': {'type': 'array', 'items': {'type': 'string'},
                        'minItems': 1, 'maxItems': 50},
                'mode': {'type': 'string', 'enum': ['symlink', 'copy'],
                         'default': 'symlink'},
                'tier': {'type': 'integer', 'enum': [1, 2, 3]},
                'apply': {'type': 'boolean', 'default': False},
                'overwrite': {'type': 'boolean', 'default': False},
            },
            'required': ['harness'],
        },
        'annotations': {'readOnlyHint': False, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
    },
    {
        'name': 'install_agents',
        'title': 'Install agents',
        'description': (
            'Installs agent definitions into a coding harness. Each harness '
            'receives the frontmatter dialect it expects. Dry run unless '
            'apply is true. Not covered by get_agent, which returns a '
            'definition without writing it.'),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'harness': {'type': 'string', 'enum': [
                    'claude-code', 'codex', 'codex-agents', 'opencode',
                    'cline', 'puku-cli', 'agentsmd']},
                'ids': {'type': 'array', 'items': {'type': 'string'},
                        'minItems': 1, 'maxItems': 50},
                'mode': {'type': 'string', 'enum': ['symlink', 'copy'],
                         'default': 'copy'},
                'apply': {'type': 'boolean', 'default': False},
                'overwrite': {'type': 'boolean', 'default': False},
            },
            'required': ['harness', 'ids'],
        },
        'annotations': {'readOnlyHint': False, 'destructiveHint': False,
                        'idempotentHint': True, 'openWorldHint': False},
    },
    {
        'name': 'uninstall_skills',
        'title': 'Uninstall skills',
        'description': (
            'Removes skills this server installed from a harness. Refuses to '
            'remove a symlink that points outside the library. Dry run unless '
            'apply is true. Not covered by install_skills, which installs '
            'rather than removes.'),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'harness': {'type': 'string', 'enum': [
                    'claude-code', 'codex', 'codex-agents', 'opencode',
                    'cline', 'puku-cli', 'agentsmd']},
                'names': {'type': 'array', 'items': {'type': 'string'},
                          'minItems': 1, 'maxItems': 50},
                'apply': {'type': 'boolean', 'default': False},
            },
            'required': ['harness', 'names'],
        },
        'annotations': {'readOnlyHint': False, 'destructiveHint': True,
                        'idempotentHint': True, 'openWorldHint': False},
    },
]


def log(msg):
    sys.stderr.write('[skills-library] %s\n' % msg)


class ToolError(Exception):
    """A tool-level error. Reported as `isError`, not as a crash."""


def required(args, key, tool):
    """A required argument, or a tool error that says what is missing.

    The TypeScript server validates its input with zod, so a missing
    argument comes back as a clear message naming the field. This
    fallback has no schema library, so it checks by hand -- but it must
    not raise a bare `KeyError`, which reaches the caller as an opaque
    "'names'" with no indication of what to do about it.

    The two servers must fail the same way: the protocol test asserts
    an unknown tool returns `isError`, and a bare KeyError would be a
    crash instead.
    """
    if key not in args or args[key] is None:
        raise ToolError(
            "%s requires '%s'. Pass %s, or call tools/list for the schema."
            % (tool, key, _quoted_example(key)))
    return args[key]


def _quoted_example(key):
    """An example value for the error message."""
    if key in ('harness',):
        return "'claude-code'"
    if key in ('names', 'ids'):
        return "['tdd-workflow']"
    if key in ('id',):
        return "'skill:tdd-workflow'"
    return "a value for '%s'" % key


# The most targets one install call may touch. The schema caps an
# explicit `ids` list at the same number; a tier install is capped by
# it too, and reports the truncation rather than silently dropping
# the tail.
MAX_INSTALL_TARGETS = 50


class Server:

    def __init__(self, index_path=None):
        self.index = load_index(index_path)
        self.entries = list(self.index['skills']) + list(self.index['agents'])
        self.by_id = {e['id']: e for e in self.entries}
        self.by_name = {e['name']: e for e in self.entries}
        self.root = os.environ.get('SKILLS_LIBRARY_ROOT') or BASE

    # ------------------------------------------------------------ helpers
    def resolve(self, id_):
        e = self.by_id.get(id_)
        if e:
            return e
        return self.by_name.get(id_)

    # ------------------------------------------------------------- tools
    def tool_search_library(self, args):
        q = args.get('query', '')
        limit = args.get('limit', DEFAULT_LIMIT)
        out = self.index.search(
            q,
            limit=limit,
            kind=args.get('kind'),
            tier=args.get('tier'),
            domain=args.get('domain'),
            include_body=args.get('include_body', False),
        )
        return out

    def tool_get_skill(self, args):
        e = self.resolve(args.get('id', ''))
        if not e or e['kind'] != 'skill':
            raise ToolError("Skill '%s' not found. Use search_library to find "
                            "valid ids." % args.get('id', ''))
        s = e
        abs_path = os.path.join(self.root, s['skill_md'])
        body = ''
        body_error = ''
        if os.path.isfile(abs_path):
            with open(abs_path, encoding='utf-8', errors='replace') as fh:
                body = fh.read()
        else:
            body_error = ('The file %s is missing from the library tree.'
                          % s['skill_md'])
        out = {
            'id': s['id'],
            'kind': 'skill',
            'name': s['name'],
            'title': s['title'],
            'description': s['desc'],
            'desc_source': s['desc_source'],
            'tier': s['tier'],
            'domain': s['domain'],
            'path': s['path'],
            'frontmatter': s['frontmatter'],
            'bundle': {
                'file_count': s['bundle']['file_count'],
                'total_bytes': s['bundle']['total_bytes'],
                'refs_total': s['bundle']['refs_total'],
                'refs_resolved': s['bundle']['refs_resolved'],
                'refs_dangling': s['bundle']['refs_dangling'],
                'files': [{'path': f['path'], 'bytes': f['bytes']}
                          for f in s['bundle']['files']],
            },
        }
        if args.get('include_body', True):
            out['body'] = body
        if body_error:
            out['body_error'] = body_error
        return out

    def tool_get_agent(self, args):
        id_ = args.get('id', '')
        e = self.resolve(id_)
        if not e or e['kind'] != 'agent':
            if args.get('include_held_aside', False):
                for h in self.index.get('held_aside', []):
                    if h['name'] == id_ or 'agent:%s' % h['name'] == id_:
                        abs_path = os.path.join(self.root, h['path'])
                        body = ''
                        if os.path.isfile(abs_path):
                            with open(abs_path, encoding='utf-8',
                                      errors='replace') as fh:
                                body = fh.read()
                        return {
                            'id': 'agent:%s' % h['name'],
                            'kind': 'agent',
                            'name': h['name'],
                            'held_aside': True,
                            'orchestrator': h.get('orchestrator', ''),
                            'reason': h.get('reason', ''),
                            'path': h.get('path', ''),
                            'body': body,
                        }
            raise ToolError(
                "Agent '%s' not found. Use search_library to find valid ids, or "
                "pass include_held_aside=true for the 14 agents held aside from "
                "the library." % id_)
        a = e
        abs_path = os.path.join(self.root, a['path'])
        body = ''
        if os.path.isfile(abs_path):
            with open(abs_path, encoding='utf-8', errors='replace') as fh:
                body = fh.read()
        return {
            'id': a['id'],
            'kind': 'agent',
            'name': a['name'],
            'description': a['desc'],
            'desc_source': a['desc_source'],
            'tier': a['tier'],
            'ensemble': a.get('ensemble', ''),
            'path': a['path'],
            'frontmatter': a['frontmatter'],
            'body': body,
        }

    def tool_get_skill_bundle(self, args):
        e = self.resolve(args.get('id', ''))
        if not e or e['kind'] != 'skill':
            raise ToolError("Skill '%s' not found. Use search_library to find "
                            "valid ids." % args.get('id', ''))
        s = e
        manifest = [{'path': f['path'], 'bytes': f['bytes']}
                    for f in s['bundle']['files']]
        files = args.get('files')
        max_bytes = args.get('max_bytes', DEFAULT_BUNDLE_BYTES)
        if not files:
            return {
                'id': s['id'], 'name': s['name'],
                'file_count': s['bundle']['file_count'],
                'total_bytes': s['bundle']['total_bytes'],
                'refs_total': s['bundle']['refs_total'],
                'refs_resolved': s['bundle']['refs_resolved'],
                'refs_dangling': s['bundle']['refs_dangling'],
                'files': manifest,
                'note': ('Manifest only. Pass files=["path"] to read '
                         'contents.'),
            }
        known = {f['path']: f['bytes'] for f in s['bundle']['files']}
        missing = [f for f in files if f not in known]
        if missing:
            raise ToolError(
                "'%s' is not in the bundle of '%s'. Available paths are listed "
                "in the manifest." % ("', '".join(missing), s['id']))
        total = sum(known.get(f, 0) for f in files)
        if total > max_bytes:
            raise ToolError(
                'Requested files total %s bytes; max_bytes is %s. The manifest '
                'is returned instead — request specific files.'
                % ('{:,}'.format(total), '{:,}'.format(max_bytes)))
        base = os.path.join(self.root, s['path'])
        contents = []
        for f in files:
            abs_path = os.path.join(base, f)
            if not os.path.isfile(abs_path):
                raise ToolError("'%s' is listed in the manifest but missing on "
                                "disk at %s." % (f, abs_path))
            with open(abs_path, encoding='utf-8', errors='replace') as fh:
                contents.append({'path': f, 'bytes': known.get(f, 0),
                                 'content': fh.read()})
        return {'id': s['id'], 'name': s['name'], 'files': contents,
                'total_bytes': total}

    def tool_list_library(self, args):
        section = args.get('section', 'stats')
        idx = self.index
        if section == 'domains':
            return [{'name': d['name'], 'skill_count': d['skill_count'],
                     'tier': d['tier'], 'skills': d['skills']}
                    for d in idx['domains']]
        if section == 'tiers':
            return {
                'tier_1_skills': idx['packs'],
                'tier_1_agents': [a['name'] for a in idx['agents']
                                  if a['tier'] == 1],
                'by_tier': idx['counts']['by_tier'],
                'note': ('Tiers bias ranking, they never filter. Every skill '
                         'and agent stays searchable; a tier only breaks ties '
                         'among weak, description-only matches.'),
            }
        if section == 'packs':
            return {
                'packs': idx['packs'],
                'note': ('The six hand-authored packs are the highest-quality '
                         'material in the library and the first thing to reach '
                         'for.'),
            }
        if section == 'tasks':
            return [{'task': t['task'], 'skills': t['skills'],
                     'agents': t['agents'], 'notes': t.get('notes', '')}
                    for t in idx['tasks']]
        return {
            'schema_version': idx['schema_version'],
            'generated_at': idx['generated_at'],
            # The index records the absolute path it was built at, which
            # is the builder's machine and not the reader's. The live
            # root is the one that matters.
            'library_root': self.root,
            'counts': idx['counts'],
            'domains': len(idx['domains']),
            'tasks': len(idx['tasks']),
            'held_aside': len(idx.get('held_aside', [])),
            'tokenizer_version': idx['search']['tokenizer_version'],
        }

    def tool_install_skills(self, args):
        harness = required(args, 'harness', 'install_skills')
        mode = args.get('mode', 'symlink')
        tier = args.get('tier')
        apply_ = args.get('apply', False)
        overwrite = args.get('overwrite', False)
        ids = args.get('ids') or []

        # `ids` and `tier` are two ways to say what to install. Either
        # one alone is enough; neither one is enough.
        if not ids and tier is None:
            raise ToolError("install_skills needs 'ids' or 'tier'. Pass ids "
                            "to install specific skills, or tier to install "
                            "a whole tier.")

        targets, errors = [], []
        if not ids:
            # A tier install. Tier 3 holds 701 skills, so the batch is
            # capped the way an explicit id list is -- and the
            # truncation is reported rather than silent.
            tier_skills = [e for e in self.index['skills'] if e['tier'] == tier]
            if len(tier_skills) > MAX_INSTALL_TARGETS:
                errors.append(
                    'Tier %d holds %d skills; only the first %d are planned. '
                    'Install the rest by id.'
                    % (tier, len(tier_skills), MAX_INSTALL_TARGETS))
                tier_skills = tier_skills[:MAX_INSTALL_TARGETS]
            ids = [e['id'] for e in tier_skills]

        for id_ in ids:
            e = self.resolve(id_)
            if not e or e['kind'] != 'skill':
                errors.append("Skill '%s' not found. Use search_library to find "
                              "valid ids." % id_)
                continue
            if tier is not None and e['tier'] != tier:
                # A tier given alongside ids is a filter. Silently
                # returning nothing would look like the skill was
                # installed, so say what happened.
                errors.append("Skill '%s' is tier %d, not tier %d; it was "
                              "skipped." % (id_, e['tier'], tier))
                continue
            targets.append(install_skill(
                harness, e['name'], e['id'], e['desc'],
                e['frontmatter'].get('allowed_tools', []),
                e['path'], os.path.join(self.root, e['skill_md']),
                self.root, mode=mode, apply=apply_, overwrite=overwrite))
        return self._install_payload(harness, mode, apply_, targets, errors)

    def tool_install_agents(self, args):
        harness = required(args, 'harness', 'install_agents')
        ids = required(args, 'ids', 'install_agents')
        mode = args.get('mode', 'copy')
        apply_ = args.get('apply', False)
        overwrite = args.get('overwrite', False)
        targets, errors = [], []
        for id_ in ids:
            e = self.resolve(id_)
            if not e or e['kind'] != 'agent':
                errors.append("Agent '%s' not found. Use search_library to find "
                              "valid ids." % id_)
                continue
            fm = e['frontmatter']
            targets.append(install_agent(
                harness, e['name'], e['id'], e['desc'],
                fm.get('tools', []), fm.get('model', ''), fm.get('mode', ''),
                os.path.join(self.root, e['path']), self.root, e['path'],
                install_mode=mode, apply=apply_, overwrite=overwrite))
        return self._install_payload(harness, mode, apply_, targets, errors)

    @staticmethod
    def _install_payload(harness, mode, apply_, targets, errors):
        written = sum(1 for t in targets if t['status'] == 'written')
        skipped = sum(1 for t in targets if t['status'] == 'skipped')
        note = ('%d written, %d skipped.' % (written, skipped) if apply_
                else 'Dry run — nothing was written. %d target(s) planned.'
                     % len(targets))
        return {'harness': harness, 'mode': mode, 'apply': apply_,
                'targets': targets, 'written': written, 'skipped': skipped,
                'errors': errors, 'note': note}

    def tool_uninstall_skills(self, args):
        harness = required(args, 'harness', 'uninstall_skills')
        names = required(args, 'names', 'uninstall_skills')
        apply_ = args.get('apply', False)
        targets = []
        for name in names:
            path, err = uninstall_skill_path(harness, name)
            if err:
                targets.append({'name': name, 'path': '', 'status': 'error',
                                'reason': err})
                continue
            r = uninstall_target(path, apply_, self.root)
            targets.append({'name': name, 'path': path, 'status': r['status'],
                            'reason': r.get('reason')})
        removed = sum(1 for t in targets if t['status'] == 'removed')
        note = ('%d removed.' % removed if apply_
                else 'Dry run — nothing was removed. %d target(s) planned.'
                     % len(targets))
        return {'harness': harness, 'apply': apply_, 'targets': targets,
                'removed': removed, 'note': note}

    # ------------------------------------------------------- dispatch
    def call_tool(self, name, args):
        table = {
            'search_library': self.tool_search_library,
            'get_skill': self.tool_get_skill,
            'get_agent': self.tool_get_agent,
            'get_skill_bundle': self.tool_get_skill_bundle,
            'list_library': self.tool_list_library,
            'install_skills': self.tool_install_skills,
            'install_agents': self.tool_install_agents,
            'uninstall_skills': self.tool_uninstall_skills,
        }
        fn = table.get(name)
        if fn is None:
            raise ToolError("Unknown tool '%s'." % name)
        return fn(args or {})

    # --------------------------------------------------------- protocol
    def handle(self, msg):
        """Handle one request. Returns a response dict, or None for a
        notification."""
        method = msg.get('method')
        msg_id = msg.get('id')
        params = msg.get('params') or {}

        if method == 'initialize':
            client_version = params.get('protocolVersion')
            version = (client_version if client_version in PROTOCOL_VERSIONS
                       else PROTOCOL_VERSIONS[0])
            return {
                'jsonrpc': '2.0', 'id': msg_id,
                'result': {
                    'protocolVersion': version,
                    'capabilities': {'tools': {'listChanged': False}},
                    'serverInfo': {'name': 'skills-library', 'version': '1.0.0'},
                    'instructions': (
                        'Searches a local library of 976 skills and 102 agents, '
                        'and installs them into coding harnesses. Start with '
                        'search_library to find candidates, then get_skill or '
                        'get_agent to read one. install_skills and '
                        'install_agents make a skill auto-activate in the '
                        'target harness; both are dry runs unless apply is '
                        'true.'),
                },
            }

        if method in ('notifications/initialized', 'notifications/cancelled'):
            return None   # a notification gets no response

        if method == 'ping':
            return {'jsonrpc': '2.0', 'id': msg_id, 'result': {}}

        if method == 'tools/list':
            return {'jsonrpc': '2.0', 'id': msg_id, 'result': {'tools': TOOLS}}

        if method == 'tools/call':
            name = params.get('name')
            args = params.get('arguments') or {}
            try:
                payload = self.call_tool(name, args)
            except ToolError as e:
                return {
                    'jsonrpc': '2.0', 'id': msg_id,
                    'result': {
                        'content': [{'type': 'text', 'text': str(e)}],
                        'isError': True,
                    },
                }
            except Exception as e:                      # noqa: BLE001
                log('tool %s failed: %s' % (name, e))
                log(traceback.format_exc())
                return {
                    'jsonrpc': '2.0', 'id': msg_id,
                    'result': {
                        'content': [{'type': 'text',
                                     'text': 'The tool %s failed: %s'
                                             % (name, e)}],
                        'isError': True,
                    },
                }
            text = (json.dumps(payload, indent=2, ensure_ascii=False)
                    if not isinstance(payload, str) else payload)
            result = {'content': [{'type': 'text', 'text': text}]}
            if isinstance(payload, dict):
                result['structuredContent'] = payload
            return {'jsonrpc': '2.0', 'id': msg_id, 'result': result}

        # An unknown method is a protocol error, not a crash.
        return {
            'jsonrpc': '2.0', 'id': msg_id,
            'error': {'code': -32601,
                      'message': 'Method not found: %s' % method},
        }


def main():
    try:
        server = Server()
    except Exception as e:                              # noqa: BLE001
        log('failed to load the index: %s' % e)
        return 1
    log('loaded %d skills + %d agents'
        % (server.index['counts']['skills'], server.index['counts']['agents']))

    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            log('skipping a line that is not JSON')
            continue
        try:
            resp = server.handle(msg)
        except Exception as e:                          # noqa: BLE001
            log('handler failed: %s' % e)
            log(traceback.format_exc())
            resp = {'jsonrpc': '2.0', 'id': msg.get('id'),
                    'error': {'code': -32603,
                              'message': 'Internal error: %s' % e}}
        if resp is None:
            continue
        out.write(json.dumps(resp, ensure_ascii=False) + '\n')
        out.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
