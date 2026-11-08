#!/usr/bin/env bash
# Prove that the filter-validation gate actually fails when a rule is
# broken.
#
# A test that passes on broken code is not a test. Each break below
# removes one rule from the filter resolution, and the gate must
# notice.
#
# The breaks are the ones a filter resolver is most likely to lose:
#
#   * the "names nothing is an error" rule disappearing, so a
#     misspelled domain goes back to answering "nothing matched";
#   * the case-insensitive match disappearing, so "mit" stops finding
#     the "MIT" licence;
#   * the prefix rule disappearing, so "DevOps" stops finding the
#     "DevOps & cloud" domain;
#   * the substring rule disappearing, so "twilio" stops finding the
#     "plugin:twilio-developer-kit" source;
#   * the ambiguity rule disappearing, so a value that could mean
#     several things is guessed at instead of refused;
#   * and the two implementations drifting apart.
#
# The files are saved and restored in-process, so the tree is left
# exactly as it was.
set -u

cd "$(dirname "$0")/.."
TS=src/filters.ts
PY=python/filters.py
SAVED=$(mktemp -d)
OUT=/tmp/break-filters-out.txt

restore() {
  cp -f "$SAVED/filters.ts" "$TS" 2>/dev/null
  cp -f "$SAVED/filters.py" "$PY" 2>/dev/null
  npm run build >/dev/null 2>&1
  rm -rf "$SAVED"
}
trap restore EXIT

cp "$TS" "$SAVED/filters.ts"
cp "$PY" "$SAVED/filters.py"

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
  if python3 tests/test_filter_validation.py >"$OUT" 2>&1; then
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
  cp "$SAVED/filters.ts" "$TS"
  cp "$SAVED/filters.py" "$PY"
  case "$file" in
    "$TS") npm run build >/dev/null 2>&1 ;;
  esac
}

# ---------------------------------------------------------------------------
# A filter that names nothing is an error.
#
# Before the rule, `domain: "Not A Domain"` answered "nothing
# matched", which is what an empty library answers too.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the 'names nothing is an error' rule disappears (TypeScript)" "$TS" \
  "s = s.replace('  throw new FilterError(filterName, raw, valid, nearest(raw, valid));', '  return valid[0];')"

break_and_expect_fail \
  "the 'names nothing is an error' rule disappears (Python)" "$PY" \
  "s = s.replace('    raise FilterError(filter_name, raw, valid, nearest(raw, valid))', '    return valid[0]')"

# ---------------------------------------------------------------------------
# The case-insensitive match.
#
# "mit" must find the "MIT" licence, and "devops & cloud" must find
# the "DevOps & cloud" domain.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the case-insensitive match disappears (TypeScript)" "$TS" \
  "s = s.replace('  const folded = raw.toLowerCase();', '  const folded = raw;')"

break_and_expect_fail \
  "the case-insensitive match disappears (Python)" "$PY" \
  "s = s.replace('    folded = raw.lower()', '    folded = raw')"

# ---------------------------------------------------------------------------
# The prefix rule.
#
# "DevOps" is the only domain that starts with "devops", so it
# resolves -- without this, the caller has to spell out
# "DevOps & cloud".
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the prefix rule disappears (TypeScript)" "$TS" \
  "s = s.replace('  const prefixed = valid.filter((v) => v.toLowerCase().startsWith(folded));', '  const prefixed: string[] = [];')"

break_and_expect_fail \
  "the prefix rule disappears (Python)" "$PY" \
  "s = s.replace('    prefixed = [v for v in valid if v.lower().startswith(folded)]', '    prefixed = []')"

# ---------------------------------------------------------------------------
# The substring rule.
#
# "twilio" is inside exactly one source name, so it resolves.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the substring rule disappears (TypeScript)" "$TS" \
  "s = s.replace('  const contained = valid.filter((v) => v.toLowerCase().includes(folded));', '  const contained: string[] = [];')"

break_and_expect_fail \
  "the substring rule disappears (Python)" "$PY" \
  "s = s.replace('    contained = [v for v in valid if folded in v.lower()]', '    contained = []')"

# ---------------------------------------------------------------------------
# The ambiguity rule.
#
# A value that could mean several things is refused, not guessed at.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the ambiguity rule disappears (TypeScript)" "$TS" \
  "s = s.replace('  if (prefixed.length > 1) {\n    throw new FilterError(filterName, raw, valid, [...prefixed].sort());\n  }', '  if (prefixed.length > 1) {\n    return prefixed[0];\n  }')"

break_and_expect_fail \
  "the ambiguity rule disappears (Python)" "$PY" \
  "s = s.replace('    if len(prefixed) > 1:\n        raise FilterError(filter_name, raw, valid, sorted(prefixed))', '    if len(prefixed) > 1:\n        return prefixed[0]')"

# ---------------------------------------------------------------------------
# The two implementations agree.
#
# A filter that resolves differently depending on which server the
# caller reached is a filter that filters differently.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the two implementations drift apart (TypeScript)" "$TS" \
  "s = s.replace('export const NEAR_LIMIT = 5;', 'export const NEAR_LIMIT = 1;')"

# The Python side reads the limit at *call* time, not at import time --
# so the constant itself is not what has to change; the call has to.
break_and_expect_fail \
  "the two implementations drift apart (Python)" "$PY" \
  "s = s.replace('def nearest(value, valid, limit=NEAR_LIMIT):', 'def nearest(value, valid, limit=1):')"

echo
echo "=== restored; the gate must pass again"
npm run build >/dev/null 2>&1
if python3 tests/test_filter_validation.py >"$OUT" 2>&1; then
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
