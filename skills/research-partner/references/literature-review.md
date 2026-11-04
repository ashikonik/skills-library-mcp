# Structured Literature Review

A review is an argument about a body of work, not a list of what exists. Its credibility comes from a stated method - a reader should be able to see what you searched, what you excluded, and therefore what your conclusion is and is not entitled to claim.

## Protocol first

Settle these with the user before searching, and record them in the output:

- **Review question** - precise enough that a paper can be judged in or out. "What's been done on retrieval augmentation" is not; "which retrieval-augmentation methods have been evaluated on multi-hop QA since 2023, and what do they claim to improve" is.
- **Sources searched** - databases, venues, preprint servers, and whether backward/forward citation chasing was used.
- **Search queries** - the literal strings. This is what lets someone reproduce or extend the review.
- **Inclusion and exclusion criteria** - date range, venue tier, language, study type, minimum evidence standard. State the reason for each exclusion, since an unexplained exclusion looks like cherry-picking.
- **Known coverage limits** - what this review cannot see. Paywalled work, non-English literature, industry work that never publishes, negative results that were never written up.

## Screening

Work in passes rather than reading everything deeply. Title and abstract first to exclude the clearly irrelevant, then full text on survivors. Keep a record of counts at each stage - candidates found, excluded at screening, included - and the reasons for exclusion in aggregate. Where a borderline paper was excluded, say so; borderline cases are where a reader's judgment may reasonably differ from yours.

## Extraction

Pull the same fields from every included paper so they can be compared. Adapt the schema to the field, but typically: citation, problem addressed, core method or intervention, data or population, evaluation setup, headline result, stated limitations, and what the paper assumes without arguing for it.

That last field is the one most reviews skip and the one that most often explains why two literatures talk past each other.

## Synthesis

Organize by **claim, mechanism, or finding** - never by paper. A section per paper is an annotated bibliography wearing a review's clothes, and it hides exactly the thing the user needs: where the field agrees, where it splits, and why.

Useful organizing spines:
- By the question each cluster of work is really answering, which is often not the question it says it is answering.
- By methodological approach, when the approach determines what conclusions are reachable.
- Chronologically, but only when the field genuinely moved in stages and the sequence explains the current state.
- By assumption, when incompatible assumptions are the reason results conflict.

For each cluster, state what is well-supported, what is contested, and what rests on a single unreplicated result. Where results conflict, look for the methodological difference that explains the conflict - different populations, different metrics, different baselines - before concluding someone is wrong.

## Gap analysis

Distinguish three kinds of gap, because they are worth wildly different amounts:

- **Unexplored** - nobody has tried it. Ask why. Often there is a good reason, and finding it saves the user months.
- **Underdetermined** - tried, but the evidence is too weak or too narrow to conclude. Usually the most tractable and publishable gap.
- **Contested** - tried repeatedly with conflicting results. High value if you can identify the moderating variable everyone missed.

## Threats to the review itself

Close with an honest account of how the review could be wrong: search coverage, selection bias from venue or recency filters, the fact that literature skews positive, and any place where the synthesis rests on your interpretation rather than the authors'.

## Output structure

Adapt to the agreed format, but by default:

```
# <Review question>
## Scope and method
   Question, sources, queries, inclusion/exclusion, screening counts, coverage limits
## What the field agrees on
## Where it splits
   Each contested point with the strongest case on each side and what would settle it
## Methods and evidence quality
## Gaps
   Unexplored / underdetermined / contested, with an assessment of tractability
## Threats to this review
## Included works
   Full citations, with a one-line note on what each contributes
```
