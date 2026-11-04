# Comparison Tables

A comparison table is only useful if its columns discriminate and its cells are trustworthy. Most bad tables fail on one of those two things: they include dimensions where every row says the same thing, or they place numbers side by side that were never measured under comparable conditions.

## Choose discriminating dimensions

Pick columns that separate the rows. Draft the table, then delete every column where all rows share a value - it costs width and carries no information. If a shared property matters, state it in a sentence above the table instead.

Choose dimensions by what the user's decision actually depends on. A table meant to help someone pick a method needs cost, requirements, and failure modes; a table meant to show intellectual lineage needs assumptions and mechanisms. Ask which, and say in the caption what the table is for.

Keep to roughly seven columns. Beyond that the table stops being scannable, and the fix is usually to split into two tables addressing two different questions.

## Make cells trustworthy

- **Distinguish "not reported" from "not applicable" from "unknown."** These mean completely different things and collapsing them into a dash destroys information - the first is a criticism of the paper, the second is a property of the method, the third is a limit of this analysis.
- **Never infer a value into a cell.** If a paper does not state its training cost, the cell says not reported. A plausible estimate silently becomes a fact once it is in a grid.
- **Note where numbers came from** when they are drawn from different sources - self-reported by the authors, from an independent reproduction, or from a third-party benchmark. Self-reported numbers are systematically optimistic and readers should know which they are looking at.
- **Flag non-comparable numbers explicitly.** Different splits, metrics, hardware, preprocessing, or evaluation protocols make a direct comparison misleading even when both numbers are correct. Where this happens, mark the cells and explain it beneath the table rather than quietly presenting them as equivalent.
- **Keep cells short.** A cell holding two sentences means that dimension needs prose, not a grid.

## Always follow with prose

A table shows differences; it does not say what they mean. After it, give a short "which to choose when" - the conditions under which each option is the right one, and any option that is dominated by another and should generally not be picked. This is the part the user actually needs and the part tables cannot express.

Also state what the table does not capture. Maturity, community support, how well something works when the assumptions are violated, how much tacit expertise it takes to get right - these rarely fit in a grid and often decide the outcome.

## Structure

```
<One line: what this table compares and what decision it serves>

| Approach | Dimension 1 | Dimension 2 | ... |
|---|---|---|---|

Notes: <non-comparable cells, source of numbers, anything flagged>

## Which to choose when
   Conditions favoring each; anything dominated
## What this table doesn't capture
```

For a long table, consider rendering it as a visual for readability - but only when the values are settled, since presentation polish makes uncertain data look authoritative.
