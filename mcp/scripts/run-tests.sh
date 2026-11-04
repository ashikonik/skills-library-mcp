#!/usr/bin/env bash
# Run the TypeScript test suite, and fail if it ran nothing.
#
# `node --test <dir>` discovers files by name convention. A file that
# does not match the convention is silently skipped, and the runner
# exits 0 with "tests 0" -- a false green. That happened here: the
# suite was named `test_search.ts`, which Node does not treat as a
# test file, so `npm test` passed while running nothing.
#
# This wrapper checks the count and refuses to report success on an
# empty run.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d dist/tests ]; then
  echo "FAIL: dist/tests does not exist -- run 'npm run build' first." >&2
  exit 1
fi

out="$(node --test dist/tests/ 2>&1)" || {
  echo "$out"
  echo "FAIL: the TypeScript test suite reported failures." >&2
  exit 1
}

echo "$out"

count="$(printf '%s\n' "$out" | grep -E '^ℹ tests [0-9]+' | awk '{print $3}' | tail -1)"

if [ -z "$count" ] || [ "$count" -eq 0 ]; then
  echo >&2
  echo "FAIL: the TypeScript test suite ran 0 tests." >&2
  echo "      Node only discovers files matching *.test.js, *-test.js or test-*.js." >&2
  echo "      A green run that ran nothing is worse than a red one." >&2
  exit 1
fi

echo
echo "TYPESCRIPT TESTS: PASS — $count tests"
