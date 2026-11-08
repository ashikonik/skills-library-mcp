#!/usr/bin/env bash
# Prove that the policy gate actually fails when the policy it guards is
# broken.
#
# A test that passes on broken code is not a test. Each break below
# removes one guarantee the policy layer is supposed to provide, and
# the gate must notice.
#
# The breaks are the ones that a policy layer is most likely to lose
# silently:
#
#   * a deny that quietly becomes an allow;
#   * a wall that stops being scoped to its operation, so it fires for
#     operations it has nothing to do with;
#   * the "a surface not in the table is not an implicit yes" rule
#     being relaxed;
#   * a project policy file that loosens a rule instead of tightening
#     it, or a malformed one that is silently ignored;
#   * the two implementations drifting apart.
#
# The files are saved and restored in-process, so the tree is left
# exactly as it was.
set -u

cd "$(dirname "$0")/.."
TS=src/policy-rules.ts
TS_EVAL=src/policy.ts
PY_RULES=python/policy_rules.py
PY_EVAL=python/policy.py
SAVED=$(mktemp -d)
OUT=/tmp/break-policy-out.txt

restore() {
  cp -f "$SAVED/policy-rules.ts" "$TS" 2>/dev/null
  cp -f "$SAVED/policy.ts" "$TS_EVAL" 2>/dev/null
  cp -f "$SAVED/policy_rules.py" "$PY_RULES" 2>/dev/null
  cp -f "$SAVED/policy.py" "$PY_EVAL" 2>/dev/null
  npm run build >/dev/null 2>&1
  rm -rf "$SAVED"
}
trap restore EXIT

cp "$TS" "$SAVED/policy-rules.ts"
cp "$TS_EVAL" "$SAVED/policy.ts"
cp "$PY_RULES" "$SAVED/policy_rules.py"
cp "$PY_EVAL" "$SAVED/policy.py"

failures=0

# break_and_expect_fail <label> <file> <python-edit>
#
# The edit is a Python snippet that receives the file's text in `s`
# and must leave it changed. If the edit does not change the file, the
# anchor has moved and the break is reported as not applicable --
# silently passing would be the worst outcome, so it counts as a
# failure of the harness rather than a pass.
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
    "$TS"|"$TS_EVAL") npm run build >/dev/null 2>&1 ;;
  esac
  if python3 tests/test_policy.py >"$OUT" 2>&1; then
    echo "    NOT DETECTED -- the gate still passed"
    failures=$((failures + 1))
  else
    echo "    detected:"
    grep -E "^FAIL" "$OUT" | head -4 | sed 's/^/      /'
    # If the gate died rather than reported a failure, say so: a crash
    # is a detection too, but a silent one is easy to misread.
    if ! grep -qE "^FAIL" "$OUT"; then
      echo "      (the gate failed without a FAIL line -- see below)"
      tail -6 "$OUT" | sed 's/^/      /'
    fi
  fi
  # Put the file back before the next break.
  cp "$SAVED/policy-rules.ts" "$TS"
  cp "$SAVED/policy.ts" "$TS_EVAL"
  cp "$SAVED/policy_rules.py" "$PY_RULES"
  cp "$SAVED/policy.py" "$PY_EVAL"
  case "$file" in
    "$TS"|"$TS_EVAL") npm run build >/dev/null 2>&1 ;;
  esac
}

# ---------------------------------------------------------------------------
# The rule table: a deny that becomes an allow.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the outside-whitelist wall becomes an allow (TypeScript)" "$TS" \
  "s = s.replace(\"    id: 'SL-5',\n    operation: 'install.skills',\n    verdict: 'deny',\", \"    id: 'SL-5',\n    operation: 'install.skills',\n    verdict: 'allow',\")"

break_and_expect_fail \
  "the outside-whitelist wall becomes an allow (Python)" "$PY_RULES" \
  "s = s.replace(\"        'id': 'SL-5',\n        'operation': 'install.skills',\n        'verdict': DENY,\", \"        'id': 'SL-5',\n        'operation': 'install.skills',\n        'verdict': ALLOW,\")"

break_and_expect_fail \
  "the apply gate on install.skills is dropped (TypeScript)" "$TS" \
  "s = s.replace(\"    evidence: 'apply',\n    hint: 'Pass apply=true to write the files.',\", \"    hint: 'Pass apply=true to write the files.',\")"

break_and_expect_fail \
  "the apply gate on install.skills is dropped (Python)" "$PY_RULES" \
  "s = s.replace(\"        'evidence': 'apply',\n        'hint': 'Pass apply=true to write the files.',\", \"        'hint': 'Pass apply=true to write the files.',\")"

# ---------------------------------------------------------------------------
# The evaluator: the guarantees that are easy to lose silently.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "an uncovered operation becomes an allow (TypeScript)" "$TS_EVAL" \
  "s = s.replace(\"    rule: 'SL-0',\n    operation,\n    verdict: 'deny',\", \"    rule: 'SL-0',\n    operation,\n    verdict: 'allow',\")"

break_and_expect_fail \
  "an uncovered operation becomes an allow (Python)" "$PY_EVAL" \
  "s = s.replace(\"        'rule': 'SL-0',\n        'operation': operation,\n        'verdict': DENY,\", \"        'rule': 'SL-0',\n        'operation': operation,\n        'verdict': ALLOW,\")"

break_and_expect_fail \
  "a wall stops being scoped to its operation (TypeScript)" "$TS_EVAL" \
  "s = s.replace(\"    if (rule.operation !== operation) continue;\", \"\")"

break_and_expect_fail \
  "a wall stops being scoped to its operation (Python)" "$PY_EVAL" \
  "s = s.replace(\"        if rule['operation'] != operation:\n            continue\", \"        if False:\n            continue\")"

break_and_expect_fail \
  "a wall's fact no longer has to be true (TypeScript)" "$TS_EVAL" \
  "s = s.replace(\"  return ctx.args?.[rule.appliesWhen] === true;\", \"  return ctx.args?.[rule.appliesWhen] !== undefined;\")"

break_and_expect_fail \
  "a wall's fact no longer has to be true (Python)" "$PY_EVAL" \
  "s = s.replace(\"    return args.get(rule['applies_when']) is True\", \"    return rule['applies_when'] in args\")"

break_and_expect_fail \
  "evidence no longer has to be true (TypeScript)" "$TS_EVAL" \
  "s = s.replace(\"    if (value !== true) return false;\", \"    if (value === undefined) return false;\")"

break_and_expect_fail \
  "evidence no longer has to be true (Python)" "$PY_EVAL" \
  "s = s.replace(\"        if value is not True:\n            return False\", \"        if value is None:\n            return False\")"

break_and_expect_fail \
  "a deny no longer outranks a satisfied conditional (TypeScript)" "$TS_EVAL" \
  "s = s.replace(\"    if (verdict === 'deny') {\n      return {\n        rule: rule.id,\n        operation,\n        verdict: 'deny',\", \"    if (verdict === 'deny') {\n      if (false) return {\n        rule: rule.id,\n        operation,\n        verdict: 'deny',\")"

break_and_expect_fail \
  "a deny no longer outranks a satisfied conditional (Python)" "$PY_EVAL" \
  "s = s.replace(\"        if verdict == DENY:\n            return {\n                'rule': rule['id'],\n                'operation': operation,\n                'verdict': DENY,\n                'reason': _reason_of(policy, rule),\n                'hint': rule.get('hint'),\n            }\n        # A conditional wall\", \"        if verdict == DENY and False:\n            return {\n                'rule': rule['id'],\n                'operation': operation,\n                'verdict': DENY,\n                'reason': _reason_of(policy, rule),\n                'hint': rule.get('hint'),\n            }\n        # A conditional wall\")"

# ---------------------------------------------------------------------------
# The project policy file: it may only tighten.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "a project file may loosen a rule (TypeScript)" "$TS_EVAL" \
  "s = s.replace(\"    policy.rules.set(id, { verdict: 'deny', reason: rule.reason });\", \"    policy.rules.set(id, { verdict: 'allow', reason: rule.reason });\")"

break_and_expect_fail \
  "a project file may loosen a rule (Python)" "$PY_EVAL" \
  "s = s.replace(\"        policy['rules'][rule_id] = {'verdict': DENY, 'reason': rule['reason']}\", \"        policy['rules'][rule_id] = {'verdict': ALLOW, 'reason': rule['reason']}\")"

break_and_expect_fail \
  "a malformed project file is ignored instead of being an error (TypeScript)" "$TS_EVAL" \
  "s = s.replace(\"  if (!file || typeof file !== 'object' || !Array.isArray(file.deny)) {\", \"  if (false) {\")"

break_and_expect_fail \
  "a malformed project file is ignored instead of being an error (Python)" "$PY_EVAL" \
  "s = s.replace(\"    if not isinstance(parsed, dict) or not isinstance(parsed.get('deny'), list):\", \"    if False:\")"

break_and_expect_fail \
  "an unknown rule id in a project file is ignored (TypeScript)" "$TS_EVAL" \
  "s = s.replace(\"    if (!rule) {\", \"    if (false) {\")"

break_and_expect_fail \
  "an unknown rule id in a project file is ignored (Python)" "$PY_EVAL" \
  "s = s.replace(\"        if rule is None:\", \"        if False:\")"

# ---------------------------------------------------------------------------
# Parity: the two implementations must not drift apart.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the Python table drifts from the TypeScript one" "$PY_RULES" \
  "s = s.replace(\"    'id': 'SL-9',\", \"    'id': 'SL-09',\")"

break_and_expect_fail \
  "the TypeScript table drifts from the Python one" "$TS" \
  "s = s.replace(\"    id: 'SL-10',\", \"    id: 'SL-10x',\")"

echo
echo "=== restored; the gate must pass again"
npm run build >/dev/null 2>&1
if python3 tests/test_policy.py >"$OUT" 2>&1; then
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
