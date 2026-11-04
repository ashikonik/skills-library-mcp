# Deep Dives

A deep dive should leave the reader able to hold a real conversation about the topic - to know what is settled, what is fought over, who fights about it, and what would change the picture. Coverage is not the goal; orientation is.

## Build the ladder

Move from intuition to formalism in stages, and never skip to the formal statement first.

1. **Why this exists** - the problem that made anyone care. A technique without its motivating problem is unmemorable.
2. **The core idea in plain language** - one paragraph a smart outsider could follow.
3. **The mechanism** - how it actually works, at the level of detail the user's stated background supports.
4. **The precise version** - the formal statement, the assumptions it requires, the conditions under which it holds.
5. **Where it breaks** - failure modes and the boundary of applicability. This is often the most useful section and the most commonly omitted.

## Explain the shape of the field, not just its content

- **The turning points.** Most fields have a handful of moments where the framing changed - a result that made a whole line of work obsolete, a dataset that redirected effort, a negative result that closed a door. Name them and explain what changed.
- **The camps.** Who disagrees with whom, and about what. Give each camp's strongest argument in a form its adherents would endorse, plus what evidence would move them. Where a disagreement is really about values or methodology rather than facts, say so.
- **The settled/contested line.** Be explicit about which is which. Presenting a live controversy as consensus, or a consensus as controversial, are both serious failures - and the second is the one that makes a newcomer waste months.
- **What is invisible from inside.** Assumptions the field shares so thoroughly that no paper states them. These are what an outsider most needs and what an insider is least likely to mention.

## The experienced-researcher layer

This is the part that separates a deep dive from a well-written encyclopedia entry. Mark it as judgment:

- Which celebrated results did not replicate, or only replicate under narrow conditions.
- Which benchmarks or metrics no longer measure anything useful.
- Which subfields are fashionable versus durable, and how you would tell.
- Where the publication incentives distort what appears in the literature.
- What a newcomer will predictably waste time on.

## Give an entry path

Close with a short reading list in the order it should be read, with a sentence on why each item is on it and what to take from it. Three to six items, not thirty. Note which are worth reading closely versus skimming, and flag anything that is widely cited but superseded.

## Calibration

Use the background the user gave in the interview. For someone new to the domain, spend more on motivation and the shape of the field, define every term inline, and be explicit about which distinctions matter and which are surface. For someone experienced, compress the orientation and go further into the disputes and the methodological detail - but keep the plain-language framing of hard ideas, since it costs a line and prevents misreads.

## Output structure

Adapt freely; this is a default rather than a template.

```
# <Topic>
## Why this exists
## The core idea
## How it works
   Intuition, then mechanism, then precise statement with assumptions
## Where it breaks
## How the field got here
   Turning points and what each changed
## Live disputes
   Each camp's strongest case and what would settle it
## What's settled vs. contested
## Judgment calls
   Marked as opinion: what's durable, what's fashion, what to avoid
## Where to start reading
```
