#!/usr/bin/env bash
# Prove that the search rules gate actually fails when a rule is broken.
#
# A test that passes on broken code is not a test. Each break below
# removes one rule from the scorer, and the gate must notice.
#
# The breaks are the ones a search scorer is most likely to lose --
# each of them was a real defect in this scorer, found by the labelled
# query set and fixed:
#
#   * the name match going back to "anywhere in the token", so "sql"
#     matches "mysql" and "home" matches "homelab";
#   * the coverage rule forgetting the evidence it filtered out, so
#     "audit my site against WCAG 2.2" cannot reach `accessibility`;
#   * the coverage demand growing with the query's length, so a long
#     query is held to a standard no description meets;
#   * the evidence rule disappearing, so "acc acce" answers with
#     `access` on two fragments that are not words;
#   * the inflection rule disappearing, so "draft" no longer reaches
#     a description that says "drafting";
#   * the inflection rule widening into a prefix rule, so "late"
#     reaches "latency" and "plant" reaches "plantation";
#   * the task row's order being dropped, so an agent outranks the
#     skills the row was asked for;
#   * and the two implementations drifting apart.
#
# The files are saved and restored in-process, so the tree is left
# exactly as it was.
set -u

cd "$(dirname "$0")/.."
TS=src/search.ts
PY=python/search.py
SAVED=$(mktemp -d)
OUT=/tmp/break-search-out.txt

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
  if python3 tests/test_search_rules.py >"$OUT" 2>&1; then
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
# The name match is a prefix match.
#
# Reverting to "the token appears anywhere in the name token" is what
# made "sql" match "mysql-patterns" and "home" match every
# "homelab-*" skill.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the name match goes back to matching anywhere in the token (TypeScript)" "$TS" \
  "s = s.replace('nt.length > t.length && nt.startsWith(t)', 'nt.length > t.length && nt.includes(t)')"

break_and_expect_fail \
  "the name match goes back to matching anywhere in the token (Python)" "$PY" \
  "s = s.replace('any(nt.startswith(t) for nt in name_tokens if len(nt) > len(t))', 'any(t in nt for nt in name_tokens if len(nt) > len(t))')"

# ---------------------------------------------------------------------------
# The coverage rule counts the evidence it filtered out.
#
# The generic-token filter drops "audit", "draft" and "review" when
# deciding *how many* tokens to demand. Counting only the surviving
# tokens as evidence threw away the right answer for "audit my site
# against WCAG 2.2".
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the coverage rule forgets the evidence it filtered out (TypeScript)" "$TS" \
  "s = s.replace('for (const t of new Set(qTokens)) if (tokenHits.has(t)) hits++;', 'for (const t of covTokens) if (tokenHits.has(t)) hits++;')"

break_and_expect_fail \
  "the coverage rule forgets the evidence it filtered out (Python)" "$PY" \
  "s = s.replace('hits = sum(1 for t in set(q_tokens) if t in token_hits)', 'hits = sum(1 for t in cov_tokens if t in token_hits)')"

# ---------------------------------------------------------------------------
# The coverage demand is capped.
#
# Without the cap, "stop my prose from sounding like a machine wrote
# it" demanded four tokens and threw away `humanizer`.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the coverage demand grows with the query's length (TypeScript)" "$TS" \
  "s = s.replace('needed = Math.min(needed, 2);', 'needed = needed;')"

break_and_expect_fail \
  "the coverage demand grows with the query's length (Python)" "$PY" \
  "s = s.replace('needed = min(needed, 2)', 'needed = needed')"

# ---------------------------------------------------------------------------
# The evidence rule.
#
# An entry that matched only fragments which appear nowhere in the
# corpus matched nothing real: "acc acce" matches `access` twice,
# once for each fragment, and neither fragment is a word.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the evidence rule disappears (TypeScript)" "$TS" \
  "s = s.replace('if (covInCorpus === 0 && inCorpus.length < 2) continue;', 'if (false) continue;')"

break_and_expect_fail \
  "the evidence rule disappears (Python)" "$PY" \
  "s = s.replace(\"                if not cov_in_corpus and len(in_corpus) < 2:\n                    continue\", \"                if False:\n                    continue\")"

# ---------------------------------------------------------------------------
# The inflection rule.
#
# "drafting" is "draft", so a query that says "draft" reaches a
# description that says "drafting". Without it, `email-ops` was
# unreachable from "organise my email and draft a reply".
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the inflection rule disappears (TypeScript)" "$TS" \
  "s = s.replace('} else if (inflectionsFor(t).some((f) => descTokens.has(f))) {', '} else if (false) {')"

break_and_expect_fail \
  "the inflection rule disappears (Python)" "$PY" \
  "s = s.replace('elif any(dt in _inflections_for(t) for dt in desc_tokens):', 'elif False:')"

# ---------------------------------------------------------------------------
# The inflection rule is not a prefix rule.
#
# A prefix rule matches any word that happens to start the same way:
# "late" would reach "latency", and "plant" would reach "plantation".
# That is a coincidence of spelling, not an inflection.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the inflection rule widens into a prefix rule (TypeScript)" "$TS" \
  "s = s.replace('} else if (inflectionsFor(t).some((f) => descTokens.has(f))) {', '} else if ([...descTokens].some((d) => d.startsWith(t))) {')"

break_and_expect_fail \
  "the inflection rule widens into a prefix rule (Python)" "$PY" \
  "s = s.replace('elif any(dt in _inflections_for(t) for dt in desc_tokens):', 'elif any(dt.startswith(t) for dt in desc_tokens):')"

# ---------------------------------------------------------------------------
# The task row's order.
#
# The table lists a row's skills before its agents, and in the order
# the table gives them. Without the demotion, "write SQL" and "write
# SQL queries" ranked `database-reviewer` first -- the agent is tier
# 1 while the skills are tier 2.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the task row's order is dropped in the strict branch (TypeScript)" "$TS" \
  "s = s.replace('    const demote = Math.min(base * TASK_DEMOTE_FRACTION * depth, TASK_DEMOTE_MAX);\n    return base - demote;', '    return base;')"

break_and_expect_fail \
  "the task row's order is dropped in the strict branch (Python)" "$PY" \
  "s = s.replace(\"        demote = min(base * TASK_DEMOTE_FRACTION * depth, TASK_DEMOTE_MAX)\n        return base - demote\", \"        return base\")"

break_and_expect_fail \
  "the task row's order is dropped in the content branch (TypeScript)" "$TS" \
  "s = s.replace('          const pos = this.taskPositions.get(\`\${e.name}|\${task}\`);\n          if (pos !== undefined && pos > 0) {\n            const depth = Math.min(pos, TASK_DEMOTE_MAX_DEPTH);\n            const demote = Math.min(bonus * TASK_DEMOTE_FRACTION * depth,\n                                    TASK_DEMOTE_MAX);\n            bonus = bonus - demote;\n          }', '          const pos = this.taskPositions.get(\`\${e.name}|\${task}\`);\n          if (false) {\n            bonus = 0;\n          }')"

break_and_expect_fail \
  "the task row's order is dropped in the content branch (Python)" "$PY" \
  "s = s.replace(\"                    pos = self.task_positions.get((e['name'], task))\n                    if pos is not None and pos > 0:\n                        depth = min(pos, TASK_DEMOTE_MAX_DEPTH)\n                        demote = min(bonus * TASK_DEMOTE_FRACTION * depth,\n                                     TASK_DEMOTE_MAX)\n                        bonus = bonus - demote\", \"                    pos = self.task_positions.get((e['name'], task))\n                    if False:\n                        bonus = 0\")"

# ---------------------------------------------------------------------------
# The demotion is capped.
#
# Without the cap, the row's later members score *negative* and fall
# out of the results. The row "Fix a failing build" lists the
# `build-*-resolver` agents fourth, fifth and sixth, and they are
# exactly what that query wants.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the demotion is not capped, so a row's later members are evicted (TypeScript)" "$TS" \
  "s = s.replace('const demote = Math.min(base * TASK_DEMOTE_FRACTION * depth, TASK_DEMOTE_MAX);', 'const demote = base * TASK_DEMOTE_FRACTION * depth;')"

break_and_expect_fail \
  "the demotion is not capped, so a row's later members are evicted (Python)" "$PY" \
  "s = s.replace('demote = min(base * TASK_DEMOTE_FRACTION * depth, TASK_DEMOTE_MAX)', 'demote = base * TASK_DEMOTE_FRACTION * depth')"

# ---------------------------------------------------------------------------
# The two implementations agree.
#
# A rule that exists on one side only is a rule that ranks
# differently depending on which server the caller reached.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the two implementations drift apart (TypeScript)" "$TS" \
  "s = s.replace('export const MORPH_DISCOUNT = 0.6;', 'export const MORPH_DISCOUNT = 0.0;')"

break_and_expect_fail \
  "the two implementations drift apart (Python)" "$PY" \
  "s = s.replace('MORPH_DISCOUNT = 0.6', 'MORPH_DISCOUNT = 0.0')"

echo
echo "=== restored; the gate must pass again"
npm run build >/dev/null 2>&1
if python3 tests/test_search_rules.py >"$OUT" 2>&1; then
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
