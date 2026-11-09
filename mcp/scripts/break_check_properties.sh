#!/usr/bin/env bash
# Prove that the property gate actually fails when an invariant breaks.
#
# The property gate asserts things that must hold of *every* response:
# the counts add up, `truncated` means what it says, the limit is
# honoured, every manifest is complete, every digest matches the bytes.
#
# Each break below removes one of those guarantees, and the gate must
# notice. The breaks are the ones a future change is most likely to
# make:
#
#   * `returned` counting the pre-floor set rather than the results
#     actually returned -- the exact bug the `filtered_out` field was
#     added to fix, in a new place;
#   * `filtered_out` counting the wrong thing;
#   * `truncated` being hard-coded to False, so a caller that paged
#     through a large result set was never told there was more;
#   * `truncated` comparing the wrong quantity;
#   * the limit not being clamped, so a caller could ask for a
#     million results and get them;
#   * the manifest losing its `SKILL.md`;
#   * a manifest listing the same URI twice;
#   * a digest that does not match the bytes;
#   * and a URI whose name segment is not the skill's name.
#
# The files are saved and restored in-process, so the tree is left
# exactly as it was.
set -u

cd "$(dirname "$0")/.."
PY=python/search.py
IDX=build/build_index.py
SAVED=$(mktemp -d)
OUT=/tmp/break-properties-out.txt

restore() {
  /bin/cp -f "$SAVED/search.py" "$PY" 2>/dev/null
  /bin/cp -f "$SAVED/build_index.py" "$IDX" 2>/dev/null
  rm -rf "$SAVED"
}
trap restore EXIT

/bin/cp "$PY" "$SAVED/search.py"
/bin/cp "$IDX" "$SAVED/build_index.py"

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
  # The index carries the manifests and the digests, so a break in
  # the builder needs the index rebuilt before the gate can see it.
  case "$file" in
    "$IDX") python3 build/build_index.py >/dev/null 2>&1 ;;
  esac
  if python3 tests/test_properties.py >"$OUT" 2>&1; then
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
  /bin/cp -f "$SAVED/search.py" "$PY"
  /bin/cp -f "$SAVED/build_index.py" "$IDX"
  case "$file" in
    "$IDX") python3 build/build_index.py >/dev/null 2>&1 ;;
  esac
}

# ---------------------------------------------------------------------------
# The breaks.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "returned counts the pre-floor set" "$PY" \
  "s = s.replace(\"        'returned': len(results),\", \"        'returned': total,\")"

break_and_expect_fail \
  "filtered_out counts the wrong thing" "$PY" \
  "s = s.replace('filtered_out = total - len(kept)', 'filtered_out = 0')"

break_and_expect_fail \
  "truncated is hard-coded to False" "$PY" \
  "s = s.replace('truncated = remaining > limit', 'truncated = False')"

break_and_expect_fail \
  "truncated compares the wrong quantity" "$PY" \
  "s = s.replace('truncated = remaining > limit', 'truncated = total > len(kept)')"

break_and_expect_fail \
  "the limit is not clamped" "$PY" \
  "s = s.replace('limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))', 'limit = max(1, int(limit or DEFAULT_LIMIT))')"

break_and_expect_fail \
  "the manifest loses its SKILL.md" "$IDX" \
  "s = s.replace(\"                    for f in bundle['files']\", \"                    for f in bundle['files'] if f['path'] != 'SKILL.md'\")"

break_and_expect_fail \
  "a manifest lists the same URI twice" "$IDX" \
  "s = s.replace(\"                'resources': [\n                    {\n                        'uri': f['uri'],\n                        'digest': f['digest'],\n                        'size': f['bytes'],\n                    }\n                    for f in bundle['files']\n                ],\", \"                'resources': [\n                    {\n                        'uri': f['uri'],\n                        'digest': f['digest'],\n                        'size': f['bytes'],\n                    }\n                    for f in bundle['files']\n                ] + [\n                    {\n                        'uri': bundle['files'][0]['uri'],\n                        'digest': bundle['files'][0]['digest'],\n                        'size': bundle['files'][0]['bytes'],\n                    }\n                ],\")"

break_and_expect_fail \
  "a digest does not match the bytes" "$IDX" \
  "s = s.replace(\"entry['digest'] = 'sha256:%s' % sha256_file(p)\", \"entry['digest'] = 'sha256:%s' % ('0' * 64)\")"

break_and_expect_fail \
  "a URI's name segment is not the skill's name" "$IDX" \
  "s = s.replace(\"return 'skill://%s/%s' % (skill_name, rel_path)\", \"return 'skill://%s/%s' % (skill_name.upper(), rel_path)\")"

echo
echo "=== restored; the gate must pass again"
if python3 tests/test_properties.py >"$OUT" 2>&1; then
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
