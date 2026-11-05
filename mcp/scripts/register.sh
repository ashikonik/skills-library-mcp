#!/usr/bin/env bash
# Register the skills-library MCP server with a coding agent.
#
#   ./register.sh                    print the snippet for every harness
#   ./register.sh puku-cli           print the snippet for one harness
#   ./register.sh --apply HARNESS    write it into the harness's config
#   ./register.sh --list             list the harnesses and their config paths
#
# The server is a *local* stdio server: absolute `node`, absolute
# entrypoint, no registry, no network, no global state touched by the
# build. Registration is a one-time, explicit step per harness.
#
# Two rules the snippets obey:
#
#   * never `bunx` -- it is not installed on this machine, and a
#     `bunx` server that cannot start is worse than no server.
#   * never `npx -y` -- it needs the network on every cold start, and
#     the whole point of this server is that it starts offline.
#
# `--apply` writes to the harness's own configuration file. It never
# edits an existing server entry; it only adds one under the name
# `skills-library`.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MCP_ROOT="$(cd "$HERE/.." && pwd)"
LIBRARY_ROOT="$(cd "$MCP_ROOT/.." && pwd)"
ENTRY="$MCP_ROOT/dist/index.js"

SERVER_NAME="skills-library"
DESCRIPTION="Search the local skills-and-agents library and pull the best match for a task."

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
}

# --------------------------------------------------------------- harness table
# name | config path | format
#
# The formats differ per harness, so each one has its own writer rather
# than one generic "edit some JSON" routine. A wrong key in the wrong
# file is silently ignored by the harness -- the server just never
# appears -- so this table is the thing that has to be right.
#
# `puku-cli` and `claude-code` also read a *project-level*
# `<project>/.puku-cli/mcp.json` and `<project>/.mcp.json`, which is the
# known-good shape on this machine (the portfolio project uses it). The
# global file is the one that applies everywhere, so that is the default
# here; `--project <dir>` writes the project-level file instead.
harness_config() {
  case "$1" in
    claude-code) echo "$HOME/.claude.json|json-global" ;;
    puku-cli)    echo "$HOME/.puku-cli/puku-cli.json|json-global" ;;
    opencode)    echo "$HOME/.config/opencode/opencode.json|opencode" ;;
    codex)       echo "$HOME/.codex/config.toml|toml" ;;
    codex-agents) echo "$HOME/.codex/config.toml|toml" ;;
    cline)       echo "|none" ;;
    agentsmd)    echo "|none" ;;
    *)           return 1 ;;
  esac
}

# The project-level config path for a harness, if it has one.
project_config() {
  case "$1" in
    puku-cli)    echo "$PROJECT_DIR/.puku-cli/mcp.json" ;;
    claude-code) echo "$PROJECT_DIR/.mcp.json" ;;
    *)           echo "" ;;
  esac
}

HARNESSES=(claude-code puku-cli opencode codex codex-agents cline agentsmd)

# ------------------------------------------------------------------- printing
print_snippet() {
  local h="$1"
  local cfg fmt
  cfg="$(harness_config "$h" | cut -d'|' -f1)"
  fmt="$(harness_config "$h" | cut -d'|' -f2)"

  echo "=== $h"
  case "$fmt" in
    json-global)
      cat <<EOF
# $cfg
{
  "mcpServers": {
    "$SERVER_NAME": {
      "command": "node",
      "args": ["$ENTRY"],
      "env": { "SKILLS_LIBRARY_ROOT": "$LIBRARY_ROOT" }
    }
  }
}
EOF
      ;;
    opencode)
      cat <<EOF
# $cfg
{
  "mcp": {
    "$SERVER_NAME": {
      "type": "local",
      "command": ["node", "$ENTRY"],
      "environment": { "SKILLS_LIBRARY_ROOT": "$LIBRARY_ROOT" }
    }
  }
}
EOF
      ;;
    toml)
      cat <<EOF
# $cfg
[mcp_servers.$SERVER_NAME]
command = "node"
args = ["$ENTRY"]
env = { SKILLS_LIBRARY_ROOT = "$LIBRARY_ROOT" }
EOF
      ;;
    none)
      cat <<EOF
# $h has no MCP configuration surface on this machine.
#
# The server still works: any MCP host that can spawn a process can run
#     node $ENTRY
# and speak to it over stdio. See mcp/docs/REGISTERING.md.
EOF
      ;;
  esac
  local pcfg
  pcfg="$(project_config "$h")"
  if [ -n "$pcfg" ]; then
    echo "# or, scoped to one project (--project <dir>):"
    echo "# $pcfg"
  fi
  echo
}

# ------------------------------------------------------------------- applying
# A tiny JSON writer. Python is already a hard dependency of this
# project (the whole library toolchain is Python), so there is no
# reason to hand-roll JSON editing in bash.
apply_json() {
  local path="$1" key="$2" payload="$3"
  python3 - "$path" "$key" "$payload" "$SERVER_NAME" <<'PY'
import json, os, sys, shutil, tempfile

path, key, payload, server_name = sys.argv[1:5]
entry = json.loads(payload)

if os.path.exists(path):
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
else:
    data = {}

existing = data.get(key)
if not isinstance(existing, dict):
    existing = {}
if server_name in existing:
    print('refusing to overwrite the existing %r server in %s' % (server_name, path))
    sys.exit(1)
existing[server_name] = entry
data[key] = existing

# Keep the file readable. puku-cli's own config is machine-written, but
# a hand-readable config is one someone can check by eye.
os.makedirs(os.path.dirname(path), exist_ok=True)
bak = path + '.bak'
if os.path.exists(path):
    shutil.copy2(path, bak)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
with os.fdopen(fd, 'w', encoding='utf-8') as fh:
    json.dump(data, fh, indent=2)
    fh.write('\n')
os.replace(tmp, path)
print('wrote %s  (backup at %s)' % (path, bak))
PY
}

apply_toml() {
  local path="$1"
  python3 - "$path" "$ENTRY" "$LIBRARY_ROOT" "$SERVER_NAME" <<'PY'
import os, sys, shutil

path, entry, root, name = sys.argv[1:5]
block = ('[%s]\ncommand = "node"\nargs = ["%s"]\nenv = { SKILLS_LIBRARY_ROOT = "%s" }\n'
         % ('mcp_servers.' + name, entry, root))

if os.path.exists(path):
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
else:
    text = ''
if ('[mcp_servers.%s]' % name) in text:
    print('refusing to overwrite the existing %r server in %s' % (name, path))
    sys.exit(1)
os.makedirs(os.path.dirname(path), exist_ok=True)
if os.path.exists(path):
    shutil.copy2(path, path + '.bak')
with open(path, 'a', encoding='utf-8') as fh:
    if text and not text.endswith('\n'):
        fh.write('\n')
    fh.write('\n' + block)
print('wrote %s  (backup at %s.bak)' % (path, path))
PY
}

apply_one() {
  local h="$1"
  local cfg fmt
  cfg="$(harness_config "$h" | cut -d'|' -f1)"
  fmt="$(harness_config "$h" | cut -d'|' -f2)"

  if [ ! -f "$ENTRY" ]; then
    echo "the server is not built: $ENTRY is missing." >&2
    echo "run mcp/scripts/rebuild.sh first." >&2
    exit 1
  fi

  # A project-level target overrides the global one.
  if [ -n "$PROJECT_DIR" ]; then
    local pcfg
    pcfg="$(project_config "$h")"
    if [ -n "$pcfg" ]; then
      cfg="$pcfg"
      fmt="json-project"
    fi
  fi

  case "$fmt" in
    json-global)
      apply_json "$cfg" mcpServers "$(printf '{"command":"node","args":["%s"],"env":{"SKILLS_LIBRARY_ROOT":"%s"}}' "$ENTRY" "$LIBRARY_ROOT")"
      ;;
    json-project)
      apply_json "$cfg" mcpServers "$(printf '{"command":"node","args":["%s"],"env":{"SKILLS_LIBRARY_ROOT":"%s"}}' "$ENTRY" "$LIBRARY_ROOT")"
      ;;
    opencode)
      apply_json "$cfg" mcp "$(printf '{"type":"local","command":["node","%s"],"environment":{"SKILLS_LIBRARY_ROOT":"%s"}}' "$ENTRY" "$LIBRARY_ROOT")"
      ;;
    toml)
      apply_toml "$cfg"
      ;;
    none)
      echo "$h has no MCP configuration surface on this machine -- nothing to apply." >&2
      echo "see mcp/docs/REGISTERING.md for how to drive it directly." >&2
      exit 1
      ;;
  esac
}

# ----------------------------------------------------------------------- main
APPLY=0
TARGETS=()
PROJECT_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --project)
      PROJECT_DIR="${2:?--project needs a directory}"
      shift 2
      ;;
    --list)
      for h in "${HARNESSES[@]}"; do
        printf '%-14s %s\n' "$h" "$(harness_config "$h" | cut -d'|' -f1)"
      done
      exit 0
      ;;
    -h|--help) usage; exit 0 ;;
    *)
      if ! harness_config "$1" >/dev/null 2>&1; then
        echo "unknown harness: $1" >&2
        echo "known: ${HARNESSES[*]}" >&2
        exit 2
      fi
      TARGETS+=("$1"); shift
      ;;
  esac
done

if [ ${#TARGETS[@]} -eq 0 ]; then
  TARGETS=("${HARNESSES[@]}")
fi

if [ "$APPLY" -eq 1 ]; then
  for h in "${TARGETS[@]}"; do
    echo "==> $h"
    apply_one "$h"
    echo
  done
  echo "Done. Restart the harness to pick the server up."
else
  for h in "${TARGETS[@]}"; do
    print_snippet "$h"
  done
  cat <<EOF
Nothing has been written. To apply one of these:
    ./register.sh --apply <harness>

The entrypoint must exist before registration:
    $ENTRY
EOF
fi
