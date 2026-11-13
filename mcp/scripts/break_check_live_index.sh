#!/usr/bin/env bash
# Prove that the live-index gate actually fails when the reload is broken.
#
# A test that passes on broken code is not a test. Each break below
# removes one part of the reload, and the gate must notice.
#
# The reload is what stops a long-running server from serving a stale
# index. Without it, a server that outlives a rebuild answers from the
# library as it was when the process started: `get_agent` reports
# "not found" for an agent that is on disk, and the tool descriptions
# quote a size the library no longer has.
#
# The breaks are the ones the reload could plausibly lose:
#
#   * the fingerprint never changing, so the reload never fires;
#   * the index being reloaded but the search engine not rebuilt, so
#     the search keeps ranking against the old corpus;
#   * the descriptions not being rewritten, so the server keeps
#     claiming the old size;
#   * a failed reload throwing instead of being reported, so one
#     half-written index breaks every tool.
#
# The files are saved and restored in-process, so the tree is left
# exactly as it was -- and the restore is checked, because a restore
# that silently fails would make the next break meaningless.
set -u

cd "$(dirname "$0")/.."
TS=src/server.ts
LIVE=src/live-index.ts
SAVED=$(mktemp -d)
OUT=/tmp/break-live-index-out.txt

restore() {
  cp -f "$SAVED/server.ts" "$TS" 2>/dev/null
  cp -f "$SAVED/live-index.ts" "$LIVE" 2>/dev/null
  npm run build >/dev/null 2>&1
  for pair in "$TS:$SAVED/server.ts" "$LIVE:$SAVED/live-index.ts"; do
    local now="${pair%%:*}" then="${pair#*:}"
    if ! cmp -s "$now" "$then"; then
      echo "RESTORE FAILED: $now does not match its saved copy" >&2
    fi
  done
  rm -rf "$SAVED"
}
trap restore EXIT

cp "$TS" "$SAVED/server.ts"
cp "$LIVE" "$SAVED/live-index.ts"

failures=0

# break_and_expect_fail <label> <file> <python-edit>
#
# The edit receives the file's text in `s` and must leave it changed.
# If the edit does not change the file, the anchor has moved and the
# break is reported as not applicable -- silently passing would be the
# worst outcome, so it counts as a failure of the harness.
break_and_expect_fail() {
  local label="$1" file="$2" script="$3"
  echo "=== BREAK: $label"
  local before
  before=$(md5sum "$file" | cut -d' ' -f1)

  python3 - "$file" <<PYEOF
import sys
p = sys.argv[1]
s = open(p).read()
$script
open(p, 'w').write(s)
PYEOF
  if [ $? -ne 0 ]; then
    echo "    (could not apply the break -- the code moved)"
    failures=$((failures + 1))
    return
  fi
  local after
  after=$(md5sum "$file" | cut -d' ' -f1)
  if [ "$before" = "$after" ]; then
    echo "    NOT APPLIED -- the anchor text was not found"
    failures=$((failures + 1))
    return
  fi
  npm run build >/dev/null 2>&1
  if node --test dist/tests/live-index.test.js >"$OUT" 2>&1; then
    echo "    NOT DETECTED -- the gate still passed"
    failures=$((failures + 1))
  else
    echo "    detected:"
    grep -E "^✖" "$OUT" | head -4 | sed 's/^/      /'
    if ! grep -qE "^✖" "$OUT"; then
      echo "      (the gate failed without a failing test -- see below)"
      tail -8 "$OUT" | sed 's/^/      /'
    fi
  fi
  # Put the file back before the next break.
  cp "$SAVED/server.ts" "$TS"
  cp "$SAVED/live-index.ts" "$LIVE"
  npm run build >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# The fingerprint never changes.
#
# The reload is driven by the index file's mtime and size. If the
# fingerprint is pinned, the file is never seen to change, and the
# server serves the index it started with forever.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the index fingerprint never changes" "$LIVE" \
  "s = s.replace('now.mtimeMs !== this.fingerprint.mtimeMs ||\n      now.size !== this.fingerprint.size', 'false')"

break_and_expect_fail \
  "the reload never fires" "$TS" \
  "s = s.replace('const next = live.current();', 'const next = index;')"

# ---------------------------------------------------------------------------
# The search engine is not rebuilt over the new index.
#
# The index is reloaded but the BM25 statistics are not, so the
# ranking is computed over a corpus that is no longer the one being
# searched.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the search engine is not rebuilt over the new index" "$TS" \
  "s = s.replace('search = new SearchIndex(next);', 'search = new SearchIndex(index);')"

# ---------------------------------------------------------------------------
# The descriptions are not rewritten.
#
# The SDK takes a description *string* when a tool is registered, so
# a description that quotes the library's size has to be rewritten by
# hand when the index moves.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the tool descriptions are not rewritten" "$TS" \
  "s = s.replace('rewriteDescriptions?.();', '/* no rewrite */')"

# ---------------------------------------------------------------------------
# A failed reload throws instead of being reported.
#
# An index written halfway -- or one with a malformed entry -- must
# not break every tool. The previous index stays in service and the
# error is reported.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "a failed reload throws instead of being reported" "$TS" \
  "s = s.replace('      liveError = e instanceof Error ? e.message : String(e);\n      return;', '      throw e;')"

# ---------------------------------------------------------------------------
# The gate must pass again after the restore.
# ---------------------------------------------------------------------------

echo
echo "=== restored; the gate must pass again"
npm run build >/dev/null 2>&1
if node --test dist/tests/live-index.test.js >"$OUT" 2>&1; then
  echo "    PASS"
else
  echo "    NOT PASSING after the restore -- the tree was not restored cleanly"
  grep -E "^✖" "$OUT" | head -6 | sed 's/^/      /'
  failures=$((failures + 1))
fi

echo
if [ "$failures" -eq 0 ]; then
  echo "BREAK CHECK: PASS -- every break was detected"
  exit 0
fi
echo "BREAK CHECK: FAIL -- $failures break(s) went unnoticed"
exit 1
