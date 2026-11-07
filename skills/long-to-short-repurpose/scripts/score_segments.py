#!/usr/bin/env python3
"""Score transcript segments for highlight potential.

Reads a transcript with timestamps on stdin (one segment per line, in the
format `[   12.34 →   45.67] text`), scores each segment, and prints the
top candidates in JSON.

Usage:
    python3 score_segments.py < transcript.txt
    python3 score_segments.py --min-score 4 < transcript.txt
"""
from __future__ import annotations

import argparse
import json
import re
import sys

LINE_RE = re.compile(r"^\[\s*([\d.]+)\s*→\s*([\d.]+)\s*\]\s*(.*)$")

NUMBERS = re.compile(r"\b\d+(\.\d+)?%?\b")
QUESTIONS = re.compile(r"\?")
EMOTIONAL = re.compile(
    r"\b(never|always|worst|best|mistake|wrong|secret|actually|huge|amazing)\b", re.I)
CONCLUSION = re.compile(
    r"\b(so the point is|that's why|the takeaway|in summary|basically)\b", re.I)
CONTEXT_DEP = re.compile(
    r"\b(as I said|like before|earlier|again|as mentioned)\b", re.I)
HEDGES = re.compile(r"\b(might|maybe|kind of|sort of|i think|perhaps)\b", re.I)


def score(text: str, is_start: bool = False) -> tuple[int, list[str]]:
    """Score one segment. Returns (score, reasons)."""
    total = 0
    reasons: list[str] = []

    if NUMBERS.search(text):
        total += 3
        reasons.append("number")
    if QUESTIONS.search(text):
        total += 2
        reasons.append("question")
    if EMOTIONAL.search(text):
        total += 2
        reasons.append("emotional")
    if CONCLUSION.search(text):
        total += 2
        reasons.append("conclusion")
    if CONTEXT_DEP.search(text):
        total -= 3
        reasons.append("context-dependent")
    if HEDGES.search(text):
        total -= 1
        reasons.append("hedged")
    if is_start:
        total -= 2
        reasons.append("starts mid-sentence")

    return total, reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-score", type=int, default=4)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true",
                        help="Emit full JSON instead of a table")
    args = parser.parse_args()

    candidates = []
    seen_previous = False

    for raw in sys.stdin:
        match = LINE_RE.match(raw.strip())
        if not match:
            continue

        start = float(match.group(1))
        end = float(match.group(2))
        text = match.group(3).strip()

        points, reasons = score(text, is_start=seen_previous)
        seen_previous = not text.endswith((".", "!", "?", '"'))

        if points >= args.min_score:
            candidates.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "duration": round(end - start, 2),
                "score": points,
                "reasons": reasons,
                "text": text,
            })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    candidates = candidates[: args.limit]

    if args.json:
        print(json.dumps(candidates, indent=2, ensure_ascii=False))
        return 0

    if not candidates:
        print("No candidates above the threshold.", file=sys.stderr)
        return 0

    for c in candidates:
        reasons = ", ".join(c["reasons"])
        print(f"[{c['score']:>3}] {c['start']:8.2f} → {c['end']:8.2f} "
              f"({c['duration']:5.1f}s)  {reasons}")
        print(f"      {c['text'][:110]}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
