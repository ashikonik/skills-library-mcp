# skills-library — an MCP server for the Skills & Agents library

This library holds **977 skills** and **102 agents** — markdown
instruction files with YAML frontmatter, gathered from every harness
config on this machine. Until now it was an archive: nothing activated
it.

This is a **local MCP server** that lets any MCP-capable coding agent
discover and pull them. It runs over stdio, offline, with no registry
and no network.

```bash
cd <library>/mcp
./scripts/rebuild.sh          # build the index, compile, run every test
./scripts/register.sh --apply puku-cli
```

Then, in a fresh session:

> Find me the skill for writing a REST API and install it.

---

## The eight tools

| Tool | What it does |
|---|---|
| `search_library` | ranks all 1,078 entries by relevance to a query |
| `get_skill` | one skill: body, frontmatter, bundle manifest |
| `get_agent` | one agent: body, frontmatter, tools, model |
| `get_skill_bundle` | a skill's supporting files, under a byte cap |
| `list_library` | domains, tiers, packs, the task-type index, statistics |
| `install_skills` | writes skills into a harness so they auto-activate |
| `install_agents` | writes agent definitions into a harness |
| `uninstall_skills` | removes what this server installed |

Search is enough for most work — the agent pulls the skill's content
into its context and uses it. Install is for the skills you want
*always* available.

Full detail: [`docs/TOOL_REFERENCE.md`](docs/TOOL_REFERENCE.md).

---

## The two servers

| | TypeScript | Python |
|---|---|---|
| Path | `dist/index.js` | `python/server.py` |
| Dependencies | `@modelcontextprotocol/sdk` 1.32.2, `yaml`, `zod` | **none** — stdlib only |
| Transport | the SDK's `StdioServerTransport` | hand-rolled JSON-RPC 2.0 |

The Python one is not a stripped-down version. It is a second
implementation of the same specification, and a gate test requires
both to produce **identical** answers:

- 74 queries → identical id lists and identical scores
- 5,741 vocabulary tokens → identical tokenizer output
- 1,078 documents → identical `name`, `description`, `tools`, `model`
- 8 tools → identical names, titles, descriptions, annotations, order

The fallback exists because it needs nothing installed. If the SDK
cannot be installed — offline, locked down, vendored — the server still
runs.

---

## Safety

Every write tool is a **dry run unless `apply` is true**.

```jsonc
// plans, writes nothing
{ "harness": "puku-cli", "ids": ["skill:tdd-workflow"] }

// writes
{ "harness": "puku-cli", "ids": ["skill:tdd-workflow"], "apply": true }
```

- Writes are confined to a fixed whitelist of harness directories.
- Symlinks point **into** the library, never out.
- `overwrite` defaults to `false`.
- `~/.claude/skills/learned/` is harness-managed and excluded.
- Uninstall refuses to remove a symlink pointing outside the library.

Details: [`docs/INSTALLING.md`](docs/INSTALLING.md).

---

## Layout

```
mcp/
├── build/     the index builder (Python, no Node)
├── src/       the TypeScript server
├── python/    the stdlib-only fallback server
├── tests/     the Python test suite and the golden file
├── scripts/   rebuild, register, smoke, test
├── data/      index.json — generated
└── docs/      architecture, registration, tools, installing
```

---

## Testing

```bash
npm test                        # 46 TypeScript tests
python3 tests/test_mcp.py       # 99 checks: index, search, safety
python3 tests/test_agreement.py # the cross-implementation gate
python3 tests/test_jsonrpc.py   # the protocol, against both servers
python3 scripts/eval_search.py  # the ranking, against a labelled query set
node scripts/smoke.mjs          # start the server, check it answers
node scripts/e2e.mjs            # install -> verify on disk -> uninstall
```

The end-to-end test drives the compiled server as a real subprocess
over real stdio, and takes a skill all the way through: dry run, apply,
check the link on disk, uninstall, check it is gone. It points `HOME`
at a temporary tree, so it never touches the real harness directories.

`eval_search.py` is the regression harness for the *ranking*. It runs
the real engine over 34 labelled queries — each naming the skill that
should win, and any that must not outrank it — plus 11 negatives that
must return nothing, and exits non-zero if the wanted skill falls out
of the top ten or a negative leaks. `--detail` prints every query with
its rank.

All of them run from the library's own logged driver:

```bash
cd .. && ./run.sh
```

Each step is snapshotted, logged and validated under `logs/<run_id>/`,
and any step can be rolled back without touching git history.

---

## Documentation

| Document | What it covers |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | why two servers, why lexical, how the index works |
| [`docs/REGISTERING.md`](docs/REGISTERING.md) | how to register with each harness |
| [`docs/TOOL_REFERENCE.md`](docs/TOOL_REFERENCE.md) | the eight tools, in detail |
| [`docs/INSTALLING.md`](docs/INSTALLING.md) | how skills land in a harness |
