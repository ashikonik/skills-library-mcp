# Authoring Reference

Deeper material that doesn't need to sit in SKILL.md. Read the section you need.

- [Writing descriptions that trigger correctly](#writing-descriptions-that-trigger-correctly)
- [Common failure modes](#common-failure-modes)
- [Context budget](#context-budget)
- [Choosing between SKILL.md, references, and scripts](#choosing-between-skillmd-references-and-scripts)
- [Diagnosing a skill that isn't working](#diagnosing-a-skill-that-isnt-working)

---

## Writing descriptions that trigger correctly

The description does two jobs at once: it tells the model what the skill does, and it
tells the model when to reach for it. Most weak descriptions do only the first.

A useful shape: **what it does** + **concrete trigger contexts** + **explicit
non-triggers** when there's a confusable neighbour.

### Before and after

**Weak:** `Helps with data analysis.`

Nothing here distinguishes it from Claude's default behaviour, and "data analysis" is so
broad it will either trigger constantly or never.

**Better:** `Runs cohort retention analysis on subscription event data. Use whenever the
user asks about churn, retention curves, cohort tables, or "why are users leaving" for
any dataset with per-user timestamped events. Also use when they upload a CSV of
subscription or signup events and ask what it shows. Not for one-off aggregate queries
like total revenue, which need no special handling.`

That version names the artifact, names the phrasings, covers an implicit case (uploading
a file without naming the analysis), and rules out the near-miss.

### Coverage to aim for

- **The obvious phrasing** — how someone who knows what they want would ask.
- **The naive phrasing** — how someone who doesn't know the jargon would ask.
- **The implicit case** — they describe a situation, not a request.
- **The near-miss exclusion** — the adjacent thing this is *not* for.

### Things that reliably hurt

- **Angle brackets.** Rejected at upload. `<input>` becomes "the input file".
- **Naming your own tooling as the trigger.** "Use when the user wants the FooBar
  pipeline" only fires if they already know the name. Describe the problem, not the brand.
- **Stacking synonyms with no context.** "documents, files, papers, PDFs, text, writing"
  reads as keyword soup and makes the skill fire on everything.
- **Burying when-to-use in the body.** The body isn't loaded until after the trigger
  decision. Trigger information in the body cannot help.
- **Describing implementation.** "Uses a three-pass regex approach" is invisible to the
  triggering decision and wastes characters against the 1024 limit.

### On pushiness

Undertriggering is the more common failure, so leaning pushy is right — but pushy means
*broad coverage of genuine cases*, not overclaiming. "Use this for any question about
anything involving text" gets the skill loaded constantly, wastes context, and trains
the model to ignore it. Push on the cases it genuinely serves.

---

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Skill never triggers | Description reads as capability, not context; or the query is simple enough to handle directly | Add concrete trigger phrasings; check the test queries are substantive enough to warrant consulting a skill |
| Triggers on everything | Keyword soup, or an over-broad domain claim | Narrow to the real domain; add explicit non-triggers |
| Triggers, then the model ignores the instructions | Buried under too much preamble, or instructions conflict | Move the operative steps up; remove contradictions — models resolve conflicts unpredictably |
| Works on test cases, fails in the wild | Overfit to the examples you iterated on | Replace specifics with principles; add a test case deliberately unlike the others |
| Model wastes turns on setup | Skill describes a procedure that should be a bundled script | Write the script once, put it in `scripts/`, point at it |
| Output format drifts run to run | Format described in prose rather than shown | Give an exact template to fill in |
| Model over-explains its own process | Skill reads as a checklist to perform visibly | State that the process is internal and only results are surfaced |
| Breaks when a file is missing | Skill assumes the happy path | Name what to do when the input isn't there |

---

## Context budget

Three levels load at different times, and the cost profile differs sharply:

| Level | When loaded | Rough cost | Implication |
|---|---|---|---|
| name + description | Always, for every skill installed | ~100 tokens each | This is a tax on every conversation the user ever has. Keep it tight. |
| SKILL.md body | On trigger | 500-3000 tokens | Real but paid only when relevant |
| `references/`, `scripts/` | On demand | Free until read; scripts can run without being read at all | Push detail here aggressively |

The asymmetry is the whole design. A 200-word description on a rarely-used skill is a
permanent cost for occasional benefit. A 2000-line reference file that's read once a month
costs nothing the rest of the time. When SKILL.md gets long, the question isn't "what can
I delete" but "what can move down a level with a clear pointer left behind".

A pointer is only useful if it says *when* to follow it. `See references/aws.md` is weak;
`If deploying to AWS, read references/aws.md for the role setup` tells the model whether
this applies before it spends a read.

---

## Choosing between SKILL.md, references, and scripts

**SKILL.md** — the decision-making layer. Workflow, judgment calls, when to branch, what
good output looks like. If the model needs it to decide *what to do*, it goes here.

**references/** — lookup material. Schemas, API details, per-variant instructions, long
examples. If the model needs it only in specific branches, it goes here. Give files over
~300 lines a table of contents.

**scripts/** — anything deterministic and repeated. The test from the main workflow is
worth restating: if you watch several test runs independently write substantially the
same helper, that's the signal. Write it once properly, with error messages that tell the
caller what went wrong.

A script also buys reliability. Prose instructions for a fiddly transformation get
followed approximately; a script gets followed exactly. Prefer scripts wherever the task
is mechanical, and reserve prose for the parts that genuinely need judgment.

---

## Diagnosing a skill that isn't working

Work in this order — it's cheapest first, and each step rules out a class of cause.

1. **Is it installed and visible?** Confirm it appears in the available skills list. A
   surprising share of "the skill doesn't work" is "the skill isn't loaded".
2. **Does it trigger?** Ask something squarely in its domain and see whether it gets
   consulted. If not, the problem is the description — nothing in the body matters yet.
3. **Does it trigger and get ignored?** Read the body as the model sees it. Look for
   contradictions, instructions buried past the point of attention, and rules stated so
   rigidly the model can't tell which applies.
4. **Does it follow instructions but produce the wrong thing?** The instructions are
   clear and wrong. This is the good failure — it's specific and fixable. Check whether
   the skill assumes context the model doesn't have.
5. **Is it inconsistent across runs?** Underspecified output format, or genuine ambiguity
   in the task. Show an exact template rather than describing one.

Reading transcripts beats reading final outputs at every one of these steps. The output
tells you *that* something went wrong; the transcript tells you *where* the model went
off the path, which is what you actually need to fix it.
