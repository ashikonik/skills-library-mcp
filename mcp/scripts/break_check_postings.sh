#!/usr/bin/env bash
# Prove that the postings gate actually fails when the postings it
# guards are broken.
#
# A test that passes on broken code is not a test. Each break below
# removes one guarantee from the index builder, and the gate must
# notice.
#
# The breaks are the ones a postings index is most likely to lose --
# each of them was a real defect in this index:
#
#   * the postings holding only the name and the description, while
#     the index advertises five searchable fields -- the drift this
#     whole gate exists to catch;
#   * the advertised field list growing a field the postings do not
#     cover;
#   * a field's bucket losing an entry that carries the token;
#   * a curated field (`prompt_signals`, `tasks`) being declared but
#     left empty;
#   * an entry appearing in a bucket it does not belong to.
#
# The builder is saved and restored in-process, and the index is
# rebuilt after every break, so the tree is left exactly as it was.
set -u

cd "$(dirname "$0")/.."
BUILDER=build/build_index.py
SAVED=$(mktemp -d)
OUT=/tmp/break-postings-out.txt
INDEX=data/index.json
INDEX_SAVED="$SAVED/index.json"

restore() {
  /bin/cp -f "$SAVED/build_index.py" "$BUILDER" 2>/dev/null
  if [ -f "$INDEX_SAVED" ]; then
    /bin/cp -f "$INDEX_SAVED" "$INDEX" 2>/dev/null
  fi
  rm -rf "$SAVED"
}
trap restore EXIT

/bin/cp "$BUILDER" "$SAVED/build_index.py"
if [ -f "$INDEX" ]; then
  /bin/cp "$INDEX" "$INDEX_SAVED"
fi

failures=0

# break_and_expect_fail <label> <python-edit>
#
# The edit receives the builder's text in `s` and must leave it
# changed. If the edit does not change the file, the anchor has moved
# and the break is reported as not applicable -- silently passing
# would be the worst outcome, so it counts as a failure of the harness.
break_and_expect_fail() {
  local label="$1" script="$2"
  echo "=== BREAK: $label"
  local before
  before=$(md5sum "$BUILDER" | cut -d' ' -f1)
  python3 - "$BUILDER" <<PYEOF
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
  after=$(md5sum "$BUILDER" | cut -d' ' -f1)
  if [ "$before" = "$after" ]; then
    echo "    NOT APPLIED -- the anchor text was not found"
    failures=$((failures + 1))
    return
  fi
  # Rebuild the index with the broken builder, then run the gate
  # against it. The builder is the thing that is broken, so the index
  # has to be regenerated for the break to be visible.
  if ! python3 "$BUILDER" >/dev/null 2>&1; then
    echo "    the builder no longer runs -- the break is too violent"
    failures=$((failures + 1))
    /bin/cp -f "$SAVED/build_index.py" "$BUILDER"
    python3 "$BUILDER" >/dev/null 2>&1
    return
  fi
  if python3 tests/test_postings.py >"$OUT" 2>&1; then
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
  # Put the builder back before the next break.
  /bin/cp -f "$SAVED/build_index.py" "$BUILDER"
  python3 "$BUILDER" >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# The breaks.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the postings cover only the name and the description" \
  "s = s.replace(\"    for rec in skill_records + agent_records:\n        for field in SEARCH_FIELDS:\", \"    for rec in skill_records + agent_records:\n        for field in ['name', 'description']:\")"

break_and_expect_fail \
  "the advertised field list names a field the postings do not cover" \
  "s = s.replace(\"    SEARCH_FIELDS = ['name', 'description', 'prompt_signals', 'domain',\n                      'tasks']\", \"    SEARCH_FIELDS = ['name', 'description', 'prompt_signals', 'domain',\n                      'tasks', 'license']\")"

break_and_expect_fail \
  "a field's bucket loses an entry that carries the token" \
  "s = s.replace(\"            for t in set(field_tokens(field, rec)):\n                bucket.setdefault(t, []).append(rec['id'])\", \"            for t in set(field_tokens(field, rec)):\n                if field != 'domain':\n                    bucket.setdefault(t, []).append(rec['id'])\")"

break_and_expect_fail \
  "the prompt-signal bucket is declared but left empty" \
  "s = s.replace(\"        if field == 'prompt_signals':\", \"        if field == 'prompt_signals':\n            return []\n        if False:\")"

break_and_expect_fail \
  "the task bucket is declared but left empty" \
  "s = s.replace(\"        if field == 'tasks':\", \"        if field == 'tasks':\n            return []\n        if False:\")"

break_and_expect_fail \
  "an entry appears in a task bucket it does not belong to" \
  "s = s.replace(\"            for task in task_rows_of.get((rec['kind'], rec['name']), []):\", \"            for task in task_rows_of.get((rec['kind'], rec['name']), []) + ['Write new code']:\")"

break_and_expect_fail \
  "the postings buckets are not sorted" \
  "s = s.replace(\"            for t in postings[field][kind]:\n                postings[field][kind][t].sort()\", \"            for t in postings[field][kind]:\n                postings[field][kind][t] = list(reversed(postings[field][kind][t]))\")"

echo
echo "=== restored; the gate must pass again"
python3 "$BUILDER" >/dev/null 2>&1
if python3 tests/test_postings.py >"$OUT" 2>&1; then
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
