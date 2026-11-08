#!/usr/bin/env bash
# Prove that the provenance gate actually fails when the provenance it
# guards is broken.
#
# A test that passes on broken code is not a test. Each break below
# removes one guarantee, and the gate must notice.
#
# The breaks are the ones a provenance layer is most likely to lose:
#
#   * the join silently dropping an entry, so it claims a licence it
#     does not have;
#   * a verdict being rewritten, so "free to share" becomes "under
#     terms" and nobody notices;
#   * the machine's absolute paths leaking into a portable index;
#   * a filter that stops filtering;
#   * the two implementations drifting apart.
#
# The files are saved and restored in-process, so the tree is left
# exactly as it was.
set -u

cd "$(dirname "$0")/.."
TS=src/search.ts
PY=python/search.py
SAVED=$(mktemp -d)
OUT=/tmp/break-provenance-out.txt

restore() {
  cp -f "$SAVED/search.ts" "$TS" 2>/dev/null
  cp -f "$SAVED/search.py" "$PY" 2>/dev/null
  npm run build >/dev/null 2>&1
  rm -rf "$SAVED"
}
trap restore EXIT

cp "$TS" "$SAVED/search.ts"
cp "$PY" "$SAVED/search.py"

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
  case "$file" in
    "$TS") npm run build >/dev/null 2>&1 ;;
  esac
  if python3 tests/test_provenance.py >"$OUT" 2>&1; then
    echo "    NOT DETECTED -- the gate still passed"
    failures=$((failures + 1))
  else
    echo "    detected:"
    grep -E "^FAIL" "$OUT" | head -4 | sed 's/^/      /'
    if ! grep -qE "^FAIL" "$OUT"; then
      echo "      (the gate failed without a FAIL line -- see below)"
      tail -6 "$OUT" | sed 's/^/      /'
    fi
  fi
  # Put the file back before the next break.
  cp "$SAVED/search.ts" "$TS"
  cp "$SAVED/search.py" "$PY"
  case "$file" in
    "$TS") npm run build >/dev/null 2>&1 ;;
  esac
}

# ---------------------------------------------------------------------------
# The filters: a filter that stops filtering returns the wrong answers.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the verdict filter stops filtering (TypeScript)" "$TS" \
  "s = s.replace(\"      if (opts.verdict && prov.verdict !== opts.verdict) continue;\", \"      if (false) continue;\")"

break_and_expect_fail \
  "the verdict filter stops filtering (Python)" "$PY" \
  "s = s.replace(\"            if verdict and prov.get('verdict') != verdict:\n                continue\", \"            if False:\n                continue\")"

break_and_expect_fail \
  "the licence filter stops filtering (TypeScript)" "$TS" \
  "s = s.replace(\"      if (opts.license && prov.license.toLowerCase() !== opts.license.toLowerCase()) continue;\", \"      if (false) continue;\")"

break_and_expect_fail \
  "the licence filter stops filtering (Python)" "$PY" \
  "s = s.replace(\"            if license and (prov.get('license') or '').lower() != license.lower():\n                continue\", \"            if False:\n                continue\")"

break_and_expect_fail \
  "the source filter stops filtering (TypeScript)" "$TS" \
  "s = s.replace(\"      if (opts.source && prov.container !== opts.source) continue;\", \"      if (false) continue;\")"

break_and_expect_fail \
  "the source filter stops filtering (Python)" "$PY" \
  "s = s.replace(\"            if source and prov.get('container') != source:\n                continue\", \"            if False:\n                continue\")"

# ---------------------------------------------------------------------------
# The result: a search result that lies about its provenance.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the search result loses its verdict (TypeScript)" "$TS" \
  "s = s.replace(\"        verdict: e.provenance.verdict,\", \"        verdict: '',\")"

break_and_expect_fail \
  "the search result loses its verdict (Python)" "$PY" \
  "s = s.replace(\"                'verdict': prov.get('verdict', 'unknown'),\", \"                'verdict': '',\")"

break_and_expect_fail \
  "the search result claims every entry is redistributable (TypeScript)" "$TS" \
  "s = s.replace(\"        verdict: e.provenance.verdict,\", \"        verdict: 'redistributable',\")"

break_and_expect_fail \
  "the search result claims every entry is redistributable (Python)" "$PY" \
  "s = s.replace(\"                'verdict': prov.get('verdict', 'unknown'),\", \"                'verdict': 'redistributable',\")"

break_and_expect_fail \
  "the search result loses its owner (TypeScript)" "$TS" \
  "s = s.replace(\"        owner: e.provenance.owner,\", \"        owner: '',\")"

break_and_expect_fail \
  "the search result loses its licence (TypeScript)" "$TS" \
  "s = s.replace(\"        license: e.provenance.license,\", \"        license: '',\")"

echo
echo "=== restored; the gate must pass again"
npm run build >/dev/null 2>&1
if python3 tests/test_provenance.py >"$OUT" 2>&1; then
  echo "    PASS"
else
  echo "    NOT PASSING after the restore -- the tree was not restored cleanly"
  grep -E "^FAIL" "$OUT" | head -5
  failures=$((failures + 1))
fi

echo
if [ "$failures" -eq 0 ]; then
  echo "BREAK CHECK: PASS -- every break was detected"
  exit 0
fi
echo "BREAK CHECK: FAIL -- $failures break(s) went unnoticed"
exit 1
