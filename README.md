# Skills & Agents Library — with a local MCP server

**852 skills** and **93 agents** in one library, plus a local
MCP server that lets any coding agent find them.

The library is the content: markdown instruction files with YAML frontmatter —
a skill is instructions you follow, an agent is a sub-agent you delegate a role
to. The MCP server is the way in. It runs over stdio, offline, with no registry
and no network, so puku-cli, Claude Code, Codex, OpenCode, Cline or anything
else that speaks MCP can search the library and pull the best match into its
context.

```bash
cd mcp
./scripts/rebuild.sh          # build the index, compile, run every test
./scripts/register.sh --apply puku-cli
```

Then, in a fresh session:

> Find me the skill for writing a REST API and install it.

---

## What is in here

| Path | What it is |
|---|---|
| `skills/<name>/` | 852 skills — `SKILL.md` plus every supporting file |
| `agents/<name>.md` | 93 standalone agent definitions |
| `agents/_agent-specific/` | 6 pipeline-internal agents, with a README explaining each |
| `mcp/` | **The MCP server** — two implementations, one specification |
| `ponytail/` | An upstream collection, kept whole under its own MIT licence |
| `ROUTING_GUIDE.md` | The routing guide: task → skill/agent lookup, in 38 domains |
| `CREDITS.md` | **Who wrote what**, with each upstream's licence |
| `NOTICE` | Which entries were left out, and why |
| `.library_data.json` | The machine-readable index the generators read |

Every bundled skill and agent keeps **its own licence**. This repository's MIT
licence covers the server, the tooling and the packs written for it — not the
third-party content. `CREDITS.md` says who wrote each piece and under what
terms; `NOTICE` says what was excluded and why.

---

## The eight tools

| Tool | What it does |
|---|---|
| `search_library` | ranks every entry by relevance to a query |
| `get_skill` | one skill: body, frontmatter, bundle manifest |
| `get_agent` | one agent: body, frontmatter, tools, model |
| `get_skill_bundle` | a skill's supporting files, under a byte cap |
| `list_library` | domains, tiers, packs, the task-type index, statistics |
| `install_skills` | writes skills into a harness so they auto-activate |
| `install_agents` | writes agent definitions into a harness |
| `uninstall_skills` | removes what this server installed |

Search is enough for most work — the agent pulls the skill's content into its
context and uses it. Install is for the skills you want *always* available.

Full detail: [`mcp/docs/TOOL_REFERENCE.md`](mcp/docs/TOOL_REFERENCE.md).

---

## The two servers

| | TypeScript | Python |
|---|---|---|
| Path | `mcp/dist/index.js` | `mcp/python/server.py` |
| Dependencies | `@modelcontextprotocol/sdk` 1.32.2, `yaml`, `zod` | **none** — stdlib only |
| Transport | the SDK's `StdioServerTransport` | hand-rolled JSON-RPC 2.0 |

The Python one is not a stripped-down version. It is a second implementation of
the same specification, and a gate test requires both to produce **identical**
answers — identical id lists, identical scores, identical tokenizer output,
identical tool surface.

The fallback exists because it needs nothing installed. If the SDK cannot be
installed — offline, locked down, vendored — the server still runs.

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

Details: [`mcp/docs/INSTALLING.md`](mcp/docs/INSTALLING.md).

---

## Rebuilding

```bash
./build.sh            # rebuild + verify
./build.sh --build    # rebuild only
./build.sh --verify   # verify only
```

The generators are idempotent. The TypeScript server is built separately,
because it needs npm and the library toolchain must work without Node:

```bash
cd mcp && ./scripts/rebuild.sh     # index + deps + compile + every test
```

`run.sh` is the logged driver. Each step is snapshotted, run, logged and
validated under `logs/<run_id>/`, and any step can be rolled back without
touching git history:

```bash
./run.sh                # every step, with per-step logs + validation
./run.sh --list         # list the declared steps
./rollback.sh --list    # every run and its steps
./rollback.sh <run_id> --step N   # restore one step
```

Nothing is ever pruned from `logs/`.

---

## Verifying

```bash
python3 .verify_all.py      # runs every check below, exits non-zero on failure
```

| Check | What it proves |
|---|---|
| `.audit_find.py` | Ground-truth re-scan using `find` + real PyYAML — deliberately different logic from the builder, so it can disagree |
| `.audit_agents.py` | Classifies every agent candidate and diffs against the library |
| `.audit_sources.py` | Every recorded source still exists; every copy is byte-identical to it |
| `.audit_contents.py` | Every supporting file of every skill was copied — no missing, differing or extra files |
| `.audit_guide.py` | The guide lists every skill and agent, and its counts are correct |
| `.verify_paths.py` | Every path referenced in the docs exists on disk |
| `.verify_packs.py` | The packs and `humanizer.zip` are intact and correctly mirrored |
| `.audit_drift.py` | The build picks up a skill that appears and drops one that disappears |
| `.audit_frontmatter.py` | Every stored description equals the real YAML frontmatter — the guard against frontmatter truncation |
| `mcp/tests/test_mcp.py` | The MCP index, the search, the tool surface, and the write-safety rules |
| `mcp/tests/test_agreement.py` | The Python and TypeScript servers rank identically |
| `mcp/tests/test_jsonrpc.py` | The protocol, spoken to both servers over real pipes |
| `mcp/scripts/eval_search.py` | The ranking, against a labelled query set |

`python3 .verify_determinism.py` additionally proves the generators are
byte-reproducible.

---

## Licence

The server, the tooling and the packs written for this library are MIT — see
[`LICENSE`](LICENSE).

Every bundled skill and agent is third-party work under its own licence, and
is redistributed on those terms. [`CREDITS.md`](CREDITS.md) attributes every
entry to its real upstream owner; [`NOTICE`](NOTICE) records what was left out
and why.

141 entries are **not** in this repository, because their licence does
not permit redistribution. Publishing them would grant rights their authors
did not grant.
