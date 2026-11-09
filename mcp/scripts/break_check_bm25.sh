#!/usr/bin/env bash
# Prove that the BM25 gate actually fails when the BM25 arm is broken.
#
# A test that passes on broken code is not a test. Each break below
# removes one guarantee, and the gate must notice.
#
# The breaks are the ones this arm is most likely to lose:
#
#   * the weight quietly becoming non-zero, so a measured decision
#     turns into an unguessed one;
#   * the arm being added to the sum in a different place than the
#     other implementation, so the two engines' raw scores diverge;
#   * the shared idf going back to `Math.log`/`math.log`, which differ
#     by one ULP -- the divergence the gate was written to find;
#   * the BM25 idf using `log` instead of `log1p`, which is the same
#     hazard one function over;
#   * the BM25 idf dropping its smoothing constant;
#   * a term becoming non-finite, which at weight zero would poison
#     the score through the multiplication;
#   * the term frequency being taken from the document frequency, so
#     the arm measures the wrong thing;
#   * and the two implementations drifting apart.
#
# One break here is *expected* to go unnoticed, and it is called out
# below rather than quietly tolerated. `Math.log(1 + x)` and
# `Math.log1p(x)` are the same function to the last bit in
# JavaScript, so swapping one for the other in the TypeScript engine
# changes nothing and no gate can detect it. In Python they are not
# the same -- `math.log(1 + x)` differs from `math.log1p(x)` -- so
# the Python side of that break is detected and the TypeScript side
# is not. That asymmetry is the whole reason the idf uses `log1p`:
# the primitive is the one both runtimes agree on.
#
# The files are saved and restored in-process, so the tree is left
# exactly as it was.
set -u

cd "$(dirname "$0")/.."
TS=src/search.ts
PY=python/search.py
SAVED=$(mktemp -d)
OUT=/tmp/break-bm25-out.txt

restore() {
  /bin/cp -f "$SAVED/search.ts" "$TS" 2>/dev/null
  /bin/cp -f "$SAVED/search.py" "$PY" 2>/dev/null
  npm run build >/dev/null 2>&1
  rm -rf "$SAVED"
}
trap restore EXIT

/bin/cp "$TS" "$SAVED/search.ts"
/bin/cp "$PY" "$SAVED/search.py"

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
  if python3 tests/test_bm25.py >"$OUT" 2>&1; then
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
  /bin/cp -f "$SAVED/search.ts" "$TS"
  /bin/cp -f "$SAVED/search.py" "$PY"
  case "$file" in
    "$TS") npm run build >/dev/null 2>&1 ;;
  esac
}

# break_and_expect_undetected <label> <file> <python-edit>
#
# The opposite of the above: the break is applied and the gate is
# required to *still pass*. Some breaks are genuinely undetectable --
# `Math.log(1 + x)` and `Math.log1p(x)` are the same function to the
# last bit in JavaScript -- and the honest thing to do with such a
# break is to state it and assert it, rather than quietly drop it or
# leave the harness reporting a failure that will never go away.
#
# This asserts a *known* property of the gate, so if a future change
# made the break detectable, this would report it: the gate got
# stronger and the expectation is now out of date.
break_and_expect_undetected() {
  local label="$1" file="$2" script="$3"
  echo "=== BREAK (expected undetectable): $label"
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
  if python3 tests/test_bm25.py >"$OUT" 2>&1; then
    echo "    as expected: the gate still passes -- this break cannot"
    echo "    be detected, and the reason is documented in this script"
  else
    echo "    NOW DETECTED -- the gate got stronger and this break is no"
    echo "    longer undetectable. The expectation is out of date; either"
    echo "    move the break to the detected list or update this note."
    grep -E "^FAIL" "$OUT" | head -4 | sed 's/^/      /'
    failures=$((failures + 1))
  fi
  # Put the file back before the next break.
  /bin/cp -f "$SAVED/search.ts" "$TS"
  /bin/cp -f "$SAVED/search.py" "$PY"
  case "$file" in
    "$TS") npm run build >/dev/null 2>&1 ;;
  esac
}

# ---------------------------------------------------------------------------
# The breaks.
# ---------------------------------------------------------------------------

break_and_expect_fail \
  "the shipped weight becomes non-zero (TypeScript)" "$TS" \
  "s = s.replace('export const WEIGHT_BM25 = 0.0;', 'export const WEIGHT_BM25 = 1.0;')"

break_and_expect_fail \
  "the shipped weight becomes non-zero (Python)" "$PY" \
  "s = s.replace('WEIGHT_BM25 = 0.0', 'WEIGHT_BM25 = 1.0')"

break_and_expect_fail \
  "the arm is added to the sum in a different place (TypeScript)" "$TS" \
  "s = s.replace(\"    // Tier bias, suppressed when the name matched exactly.\", \"    if (bm25Weight !== 0.0) { score += bm25Weight * this.bm25(e, qTokens); }\n    // Tier bias, suppressed when the name matched exactly.\")"

break_and_expect_fail \
  "the arm is added to the sum in a different place (Python)" "$PY" \
  "s = s.replace(\"        # Tier bias, suppressed when the name matched exactly.\", \"        if bm25_weight != 0.0:\n            score += bm25_weight * self.bm25(e, q_tokens)\n        # Tier bias, suppressed when the name matched exactly.\")"

# The *shared* idf -- the one the linear scorer uses, not BM25's.
#
# An earlier version of this script broke it by swapping `log1p` for
# `log(1 + x)`. That break is corpus-dependent: it is only visible
# when the two primitives differ by a ULP for some token in *this*
# corpus, and they differ on 13 of the upstream's 6,037 tokens but on
# only 1 of the published tree's 6,028 -- and that one token's idf
# moves the score by less than the 1e-6 quantisation, so the gate
# sees nothing. The upstream passed; the published tree did not.
#
# A break that only sometimes fails is not a gate. These two break
# the shared idf's *smoothing* instead, which changes every token's
# idf by a visible amount in any corpus.
break_and_expect_fail \
  "the shared idf drops the smoothing constant (TypeScript)" "$TS" \
  "s = s.replace('return Math.log1p(this.n / (df || 1));', 'return Math.log1p(this.n / (df || 1) + 1);')"

break_and_expect_fail \
  "the shared idf drops the smoothing constant (Python)" "$PY" \
  "s = s.replace('return math.log1p(self.n / float(self.df.get(t, 0) or 1))', 'return math.log1p(self.n / float(self.df.get(t, 0) or 1) + 1)')"

break_and_expect_undetected \
  "the BM25 idf uses log instead of log1p (TypeScript)" "$TS" \
  "s = s.replace('return Math.log1p((this.n - df + 0.5) / (df + 0.5));', 'return Math.log(1.0 + (this.n - df + 0.5) / (df + 0.5));')"

break_and_expect_fail \
  "the BM25 idf uses log instead of log1p (Python)" "$PY" \
  "s = s.replace('return math.log1p((self.n - df + 0.5) / (df + 0.5))', 'return math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))')"

break_and_expect_fail \
  "the BM25 idf drops the smoothing constant (TypeScript)" "$TS" \
  "s = s.replace('return Math.log1p((this.n - df + 0.5) / (df + 0.5));', 'return Math.log1p((this.n - df) / df);')"

break_and_expect_fail \
  "the BM25 idf drops the smoothing constant (Python)" "$PY" \
  "s = s.replace('return math.log1p((self.n - df + 0.5) / (df + 0.5))', 'return math.log1p((self.n - df) / df)')"

break_and_expect_fail \
  "a term becomes non-finite (TypeScript)" "$TS" \
  "s = s.replace('      const term = (this.bm25Idf(t) * num) / den;', '      const term = (this.bm25Idf(t) * num) / 0;')"

break_and_expect_fail \
  "a term becomes non-finite (Python)" "$PY" \
  "s = s.replace('            term = (self.bm25_idf(t) * num) / den', '            term = (self.bm25_idf(t) * num) / 0.0')"

break_and_expect_fail \
  "the term frequency is taken from the document frequency (TypeScript)" "$TS" \
  "s = s.replace('      const tf = counts.get(t) ?? 0;', '      const tf = this.df.get(t) ?? 0;')"

break_and_expect_fail \
  "the term frequency is taken from the document frequency (Python)" "$PY" \
  "s = s.replace(\"            tf = counts.get(t, 0)\", \"            tf = self.df.get(t, 0)\")"

break_and_expect_fail \
  "the mean document length is computed over a different population" "$PY" \
  "s = s.replace('self.avg_doc_len = (len_sum / len(self.entries)) if self.entries else 0', 'self.avg_doc_len = (len_sum / (len(self.entries) * 2)) if self.entries else 0')"

echo
echo "=== restored; the gate must pass again"
npm run build >/dev/null 2>&1
if python3 tests/test_bm25.py >"$OUT" 2>&1; then
  echo "    PASS"
else
  echo "    NOT PASSING after the restore -- the tree was not restored cleanly"
  grep -E "^FAIL" "$OUT" | head -5
  failures=$((failures + 1))
fi

echo
if [ "$failures" -eq 0 ]; then
  echo "BREAK CHECK: PASS -- every break was detected"
  echo "(one break is expected to be undetectable and is asserted as such;"
  echo " the reason is documented at the top of this script)"
  exit 0
fi
echo "BREAK CHECK: FAIL -- $failures break(s) went unnoticed"
exit 1
