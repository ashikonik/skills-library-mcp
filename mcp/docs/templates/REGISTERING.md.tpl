# Registering the skills-library MCP server

The server is a **local stdio server**. It lives inside the library, it
reads the library's own index, and it starts offline. Nothing is
uploaded, nothing is fetched, no registry is consulted.

```
node <library>/mcp/dist/index.js
```

That is the whole registration. Everything below is how to make a
harness spawn it automatically.

---

## Before you register

The entrypoint must exist. It is built, not committed:

```bash
cd <library>/mcp
./scripts/rebuild.sh          # index -> deps -> compile -> test
```

`rebuild.sh` also writes `mcp/data/index.json`, which the server loads
at startup. Without it the server exits with a message naming the file.

---

## The one command

```bash
cd <library>/mcp
./scripts/register.sh --list          # what each harness reads
./scripts/register.sh puku-cli       # print the snippet
./scripts/register.sh --apply puku-cli
```

`--apply` writes into the harness's own config file and **refuses to
overwrite an existing `skills-library` entry**. It leaves a `.bak`
next to the file it changed.

> **For puku-cli, use its own CLI instead.** `puku-cli mcp add` is the
> supported path — it writes the file with the same lock the CLI
> itself uses, so a concurrent session cannot clobber it:
>
> ```bash
> puku-cli mcp add --scope user skills-library \
>   -e SKILLS_LIBRARY_ROOT=<library> \
>   -- node <library>/mcp/dist/index.js
> ```
>
> Note the argument order: the name comes **before** `-e`, or the
> parser reads the server name as an environment variable. Then check
> it with `puku-cli mcp list`, which spawns the server and reports
> whether it connected.

### Why absolute `node` and an absolute entrypoint

Both are deliberate, and both were checked against this machine:

- **Never `bunx`.** `bun` is not installed here. `~/.codex/config.toml`
  already carries a `bunx` server entry that can never start. A server
  entry that fails to start is worse than no entry.
- **Never `npx -y`.** It needs the network on every cold start. The
  whole point of this server is that it starts offline in a fraction of
  a second.
- **Absolute `node`** because harnesses do not always inherit the
  user's shell `PATH`, and a shell function or alias would not resolve
  for them either.
- **Absolute entrypoint** because the harness's working directory is
  the *project*, not the library.

---

## Per harness

### puku-cli

puku-cli reads three scopes, and the file each one lives in was read
out of the CLI's own source rather than guessed:

| Scope | File | Key |
|---|---|---|
| **user** | `~/.puku-cli/puku-cli.json` | top-level `mcpServers` |
| **local** | `~/.puku-cli/puku-cli.json` | `projects["<cwd>"].mcpServers` |
| **project** | `<project>/.mcp.json` | top-level `mcpServers` |

The user-scope entry this produced:

```jsonc
// ~/.puku-cli/puku-cli.json
{
  "mcpServers": {
    "skills-library": {
      "type": "stdio",
      "command": "node",
      "args": ["<library>/mcp/dist/index.js"],
      "env": { "SKILLS_LIBRARY_ROOT": "<library>" }
    }
  }
}
```

> `<project>/.puku-cli/mcp.json` is **not** a puku-cli surface — the
> CLI does not read it. The portfolio project uses that path for
> Playwright and Figma, but puku-cli reads those from
> `<project>/.mcp.json`. Use the project scope above.

Verified with the CLI's own tooling:

```
$ puku-cli mcp list
Checking MCP server health...
skills-library: node <library>/mcp/dist/index.js - ✓ Connected
```

### Claude Code

```jsonc
// ~/.claude.json
{
  "mcpServers": {
    "skills-library": {
      "command": "node",
      "args": ["<library>/mcp/dist/index.js"],
      "env": { "SKILLS_LIBRARY_ROOT": "<library>" }
    }
  }
}
```

Project-scoped: `<project>/.mcp.json`.

### OpenCode

OpenCode's key is `mcp`, not `mcpServers`, and a local server is
declared with `"type": "local"`:

```jsonc
// ~/.config/opencode/opencode.json
{
  "mcp": {
    "skills-library": {
      "type": "local",
      "command": ["node", "<library>/mcp/dist/index.js"],
      "environment": { "SKILLS_LIBRARY_ROOT": "<library>" }
    }
  }
}
```

Note `environment`, not `env` — that is OpenCode's spelling. The shape
was checked against the `McpLocalConfig` type in the installed
`@opencode-ai/sdk`.

Verified with the CLI's own tooling:

```
$ opencode mcp list
┌  MCP Servers
│
●  ✓ skills-library connected
│      node <library>/mcp/dist/index.js
│
└  1 server(s)
```

### Codex

```toml
# ~/.codex/config.toml
[mcp_servers.skills-library]
command = "node"
args = ["<library>/mcp/dist/index.js"]
env = { SKILLS_LIBRARY_ROOT = "<library>" }
```

### Cline

Cline has no MCP configuration surface on this machine. The server is
still usable: any host that can spawn a process can run

```bash
node <library>/mcp/dist/index.js
```

and speak to it over stdio. Where no MCP surface exists, the fallback
is to feed content directly with `get_skill`.

---

## `SKILLS_LIBRARY_ROOT`

The server derives the library root from its own location
(`mcp/..`). `SKILLS_LIBRARY_ROOT` overrides it, so a checkout
elsewhere on disk can be served without a rebuild. It is set
explicitly in every snippet above so the server cannot be misled by a
symlinked entrypoint.

---

## Verifying a registration

```bash
# The server starts and answers on its own:
node <library>/mcp/dist/index.js
```

It should print two lines to **stderr**:

```
[skills-library] loaded {n_skills} skills + {n_agents} agents from .../mcp/data/index.json
[skills-library] ready
```

and then wait. It prints nothing to stdout — stdout *is* the protocol
stream, and a stray print there corrupts it.

A one-shot check that exercises the whole path:

```bash
cd <library>/mcp
node scripts/smoke.mjs
```

---

## Uninstalling

Remove the `skills-library` entry from the harness's config file. The
entrypoint itself can stay; nothing else depends on it. If you also
want the server's own state gone:

```bash
rm -rf <library>/mcp/dist \
       <library>/mcp/node_modules
```

The index (`mcp/data/index.json`) is regenerated by `rebuild.sh`, so
there is no reason to delete it by hand.
