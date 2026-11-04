#!/usr/bin/env bash
# Rebuild the library and verify it, end to end.
#
#   ./build.sh          rebuild + verify
#   ./build.sh --build  rebuild only
#   ./build.sh --verify verify only
#
# The MCP index is built from .library_data.json, so it comes after the
# library and before the verification -- the verification's last three
# steps need the index.
#
# The TypeScript compile is NOT run here. It needs npm, and this script
# must work on a machine with no Node at all. Use mcp/scripts/rebuild.sh
# for the full MCP build, or ./run.sh for the logged driver, which does
# both.
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-all}"

if [ "$MODE" != "--verify" ]; then
  echo "==> building library"
  python3 .build_library.py
  echo
  echo "==> building routing guide"
  python3 .build_guide.py
  echo
  echo "==> building inventory report"
  python3 .gen_report.py
  echo
  echo "==> building the MCP index"
  python3 mcp/build/build_index.py
  echo
fi

if [ "$MODE" != "--build" ]; then
  echo "==> verifying"
  python3 .verify_all.py
fi

echo
echo "Done. Start with README.md -> ROUTING_GUIDE.md"
echo
echo "The MCP server needs mcp/dist/ -- build it with:"
echo "  mcp/scripts/rebuild.sh"
