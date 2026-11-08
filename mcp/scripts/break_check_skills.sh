#!/usr/bin/env bash
# Prove that the Skills extension gate actually fails when the code it
# guards is broken.
#
# A test that passes on broken code is not a test. Each break below
# removes one guarantee, and the gate must notice. The files are saved
# and restored in-process, so the tree is left exactly as it was.
set -u

cd "$(dirname "$0")/.."
TS=src/skills-extension.ts
PY=python/skills_extension.py
SAVED=$(mktemp -d)

restore() {
  cp -f "$SAVED/se.ts" "$TS" 2>/dev/null
  cp -f "$SAVED/pse.py" "$PY" 2>/dev/null
  npm run build >/dev/null 2>&1
  rm -rf "$SAVED"
}
trap restore EXIT

cp "$TS" "$SAVED/se.ts"
cp "$PY" "$SAVED/pse.py"

failures=0

break_and_expect_fail() {
  local label="$1" file="$2" script="$3"
  echo "=== BREAK: $label"
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
  if [ "$file" = "$TS" ]; then
    npm run build >/dev/null 2>&1
  fi
  if python3 tests/test_skills_extension.py >/tmp/break-out.txt 2>&1; then
    echo "    NOT DETECTED -- the gate still passed"
    failures=$((failures + 1))
  else
    echo "    detected:"
    grep -E "^FAIL" /tmp/break-out.txt | head -4 | sed 's/^/      /'
    # If the gate died rather than reported a failure, say so: a crash
    # is a detection too, but a silent one is easy to misread.
    if ! grep -qE "^FAIL" /tmp/break-out.txt; then
      echo "      (the gate failed without a FAIL line -- see below)"
      tail -6 /tmp/break-out.txt | sed 's/^/      /'
    fi
  fi
  # Put the file back before the next break.
  cp "$SAVED/se.ts" "$TS"
  cp "$SAVED/pse.py" "$PY"
  if [ "$file" = "$TS" ]; then
    npm run build >/dev/null 2>&1
  fi
}

break_and_expect_fail \
  "the digest check is removed" "$PY" \
  "s = s.replace(\"    if actual != digest:\", \"    if False and actual != digest:\")"

break_and_expect_fail \
  "skills/get accepts any URI in the skill" "$PY" \
  "s = s.replace(\"    if uri != record['skills']['uri']:\", \"    if False:\")"

break_and_expect_fail \
  "the directory listing accepts a file" "$PY" \
  "s = s.replace(\"    if any(f['path'] == rel for f in record['bundle']['files']):\", \"    if False:\")"

break_and_expect_fail \
  "the TypeScript listing order changes" "$TS" \
  "s = s.replace(\"    a.skills.name < b.skills.name ? -1 : a.skills.name > b.skills.name ? 1 : 0,\", \"    1,\")"

break_and_expect_fail \
  "the TypeScript digest check is removed" "$TS" \
  "s = s.replace(\"  if (actual !== digest) {\", \"  if (false) {\")"

break_and_expect_fail \
  "the TypeScript skills/get accepts any URI" "$TS" \
  "s = s.replace(\"  if (uri !== record.skills.uri) return undefined;\", \"\")"

break_and_expect_fail \
  "the TypeScript directory listing accepts a file" "$TS" \
  "s = s.replace(\"  const isFile = record.bundle.files.some((f) => f.path === rel);\", \"  const isFile = false;\")"

break_and_expect_fail \
  "the TypeScript directory listing hides its subdirectories" "$TS" \
  "s = s.replace(\"      if (!seen.has(name)) seen.set(name, 'inode/directory');\", \"      if (!seen.has(name)) seen.set(name, 'application/octet-stream');\")"

break_and_expect_fail \
  "the TypeScript resource list loses its cursor" "$TS" \
  "s = s.replace(\"    result.nextCursor = encodeCursor(page[page.length - 1]!.uri, 'resources/list');\", \"\")"

break_and_expect_fail \
  "the Python resource list loses its cursor" "$PY" \
  "s = s.replace(\"        out['nextCursor'] = protocol.encode_cursor(\\n            page[-1]['uri'], 'resources/list')\", \"        out['__no_cursor__'] = protocol.encode_cursor(\\n            page[-1]['uri'], 'resources/list')\")"

echo
echo "=== restored; the gate must pass again"
npm run build >/dev/null 2>&1
if python3 tests/test_skills_extension.py >/tmp/break-out.txt 2>&1; then
  echo "    PASS"
else
  echo "    NOT PASSING after the restore -- the tree was not restored cleanly"
  grep -E "^FAIL" /tmp/break-out.txt | head -5
  failures=$((failures + 1))
fi

echo
if [ "$failures" -eq 0 ]; then
  echo "BREAK CHECK: PASS -- every break was detected"
  exit 0
fi
echo "BREAK CHECK: FAIL -- $failures break(s) went unnoticed"
exit 1
