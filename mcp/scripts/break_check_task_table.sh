#!/usr/bin/env bash
# Prove that the task-table gate actually fails when the table breaks.
#
# The task table is 74 rows of hand-written curation. A gate that
# checks it is only useful if it can fail, and the ways it can go
# wrong are specific:
#
#   * a row naming an entry the library does not have, which the
#     builder drops and the author never notices;
#   * a row's note naming an entry its lists omit, so the note
#     describes a row that is not the row;
#   * a row naming the same entry twice, which costs it a position;
#   * a row with no content and no members, which routes nowhere;
#   * two rows with the same task, so one is unreachable;
#   * a row the postings cannot route to, so the search never finds
#     it;
#   * the index drifting from the table it was generated from.
#
# The files are saved and restored in-process, so the tree is left
# exactly as it was.
set -u

cd "$(dirname "$0")/.."
TASKS=build/tasks.py
BUILDER=build/build_index.py
SAVED=$(mktemp -d)
OUT=/tmp/break-task-table-out.txt

restore() {
  /bin/cp -f "$SAVED/tasks.py" "$TASKS" 2>/dev/null
  /bin/cp -f "$SAVED/build_index.py" "$BUILDER" 2>/dev/null
  python3 build/build_index.py >/dev/null 2>&1
  rm -rf "$SAVED"
}
trap restore EXIT

/bin/cp "$TASKS" "$SAVED/tasks.py"
/bin/cp "$BUILDER" "$SAVED/build_index.py"

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
  # The index carries the task rows, so a break in the table or the
  # builder needs the index rebuilt before the gate can see it.
  python3 build/build_index.py >/dev/null 2>&1
  if python3 tests/test_task_table.py >"$OUT" 2>&1; then
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
  /bin/cp -f "$SAVED/tasks.py" "$TASKS"
  /bin/cp -f "$SAVED/build_index.py" "$BUILDER"
  python3 build/build_index.py >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# The breaks.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "a row names an entry the library does not have" "$TASKS" \
  "s = s.replace(\"('Refactor / simplify', ['coding-standards', 'codehealth-mcp'],\", \"('Refactor / simplify', ['coding-standards', 'codehealth-mcp', 'no-such-skill'],\")"

break_and_expect_fail \
  "a row's note names an entry its lists omit" "$TASKS" \
  "s = s.replace(\"['refactor-cleaner'],\", \"[],\")"

break_and_expect_fail \
  "a row names the same entry twice" "$TASKS" \
  "s = s.replace(\"['coding-standards', 'codehealth-mcp'],\", \"['coding-standards', 'coding-standards'],\")"

# The row must lose *both* its lists to become empty. Emptying only
# the skill list leaves the row with an agent in it -- still a member
# -- so the break would not be the break it claims to be, and the
# gate would be right to pass.
break_and_expect_fail \
  "a row has no members at all" "$TASKS" \
  "s = s.replace(\"('Refactor / simplify', ['coding-standards', 'codehealth-mcp'],\", \"('Refactor / simplify', [],\")
s = s.replace(\"['refactor-cleaner'],\", \"[],\")"

break_and_expect_fail \
  "two rows have the same task" "$TASKS" \
  "s = s.replace(\"('Refactor / simplify',\", \"('Remove dead code',\")"

break_and_expect_fail \
  "a row's members are not routable by its text" "$BUILDER" \
  "s = s.replace(\"if field == 'tasks':\", \"if field == 'tasks' and False:\")"

break_and_expect_fail \
  "the index drifts from the table" "$BUILDER" \
  "s = s.replace(\"'skills': list(dict.fromkeys(s_keep)),\", \"'skills': list(dict.fromkeys(s_keep)) + ['drift-marker'],\")"

echo
echo "=== restored; the gate must pass again"
python3 build/build_index.py >/dev/null 2>&1
if python3 tests/test_task_table.py >"$OUT" 2>&1; then
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
