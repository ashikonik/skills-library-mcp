#!/usr/bin/env bash
# Rebuild everything the MCP server needs, from scratch, and prove it works.
#
#   ./rebuild.sh          build the index, install deps, compile, test
#   ./rebuild.sh --ci     the same, but treat any warning as a failure
#
# The order matters:
#
#   1. the index is built from the library, so it comes first;
#   2. the TypeScript is compiled, because the tests import from dist/;
#   3. the tests run last, against the compiled output.
#
# `npm ci` is used rather than `npm install` so the lockfile decides the
# dependency tree exactly -- a server that starts offline needs to start
# with the versions that were tested.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MCP_ROOT="$(cd "$HERE/.." && pwd)"
LIBRARY_ROOT="$(cd "$MCP_ROOT/.." && pwd)"
cd "$MCP_ROOT"

CI=0
[ "${1:-}" = "--ci" ] && CI=1

step() { echo; echo "==> $*"; }

step "building the search index"
python3 "$LIBRARY_ROOT/mcp/build/build_index.py"

step "installing dependencies"
if [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund
else
  npm install --no-audit --no-fund
fi

step "compiling the TypeScript server"
npm run build

step "smoke test: the server starts and answers"
node "$MCP_ROOT/scripts/smoke.mjs"

step "running the TypeScript tests"
npm test

step "running the end-to-end test"
# Drives the compiled server as a real subprocess over real stdio:
# dry run, apply, verify on disk, uninstall, verify gone. It points
# HOME at a temporary tree, so it never touches the real harness
# directories.
node "$MCP_ROOT/scripts/e2e.mjs"

step "running the Python test suite"
python3 "$LIBRARY_ROOT/mcp/tests/test_mcp.py"

step "running the cross-implementation agreement gate"
python3 "$LIBRARY_ROOT/mcp/tests/test_agreement.py"

step "running the protocol test"
python3 "$LIBRARY_ROOT/mcp/tests/test_jsonrpc.py"

step "running the installer parity gate"
python3 "$LIBRARY_ROOT/mcp/tests/test_installer_parity.py"

step "running the policy layer gate"
python3 "$LIBRARY_ROOT/mcp/tests/test_policy.py"

step "running the Skills extension gate"
python3 "$LIBRARY_ROOT/mcp/tests/test_skills_extension.py"

step "running the provenance gate"
python3 "$LIBRARY_ROOT/mcp/tests/test_provenance.py"

step "running the search rules gate"
# The ranking gate below measures the ranking; this one states the
# rules the ranking is supposed to follow and checks each of them
# directly, so a rule can stop working even when the ranking does
# not visibly change.
python3 "$LIBRARY_ROOT/mcp/tests/test_search_rules.py"

step "running the filter validation gate"
# A filter that names nothing is an error, not an empty result. This
# gate checks that, and checks that the two implementations resolve a
# filter the same way -- including the wording of the error.
python3 "$LIBRARY_ROOT/mcp/tests/test_filter_validation.py"

step "running the postings gate"
# The index advertises which fields are searchable, and carries a
# postings index for them. The two used to disagree -- the index
# advertised five fields and the postings held two -- so this gate
# checks that every advertised field has a bucket and that the
# buckets resolve.
python3 "$LIBRARY_ROOT/mcp/tests/test_postings.py"

step "checking the search ranking"
# The ranking gate is the only regression check on *order*, so it
# belongs here and not only under `.verify_all.py`.
python3 "$LIBRARY_ROOT/mcp/scripts/eval_search.py"

step "proving the gates can fail"
# A test that passes on broken code is not a test. Each of these
# breaks the code the gate guards and requires the gate to notice.
bash "$LIBRARY_ROOT/mcp/scripts/break_check_policy.sh"
bash "$LIBRARY_ROOT/mcp/scripts/break_check_skills.sh"
bash "$LIBRARY_ROOT/mcp/scripts/break_check_provenance.sh"
bash "$LIBRARY_ROOT/mcp/scripts/break_check_search.sh"
bash "$LIBRARY_ROOT/mcp/scripts/break_check_filters.sh"
bash "$LIBRARY_ROOT/mcp/scripts/break_check_postings.sh"

echo
echo "REBUILD: PASS"
echo "The server is at $MCP_ROOT/dist/index.js"
