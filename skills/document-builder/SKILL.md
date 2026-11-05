---
name: document-builder
description: "Produce finished documents - Word (.docx), PowerPoint (.pptx), Excel (.xlsx), PDF, and markdown - with diagrams, charts, and other visuals where they earn their place. Use this skill whenever the user asks for a document, report, deck, slides, presentation, memo, proposal, one-pager, whitepaper, spreadsheet, or any deliverable they intend to send, submit, present, or file. Trigger it even when the format is unstated (\"write up my findings\", \"put this together for the client\", \"I need something to show the team\") and whenever the user asks to add a diagram, chart, figure, or visual to a document. This skill enforces a specification interview before drafting, strict source fidelity with no invented facts, drift control across long documents, and a mandatory verification pass before delivery. It bundles its own copies of the docx, pptx, xlsx, pdf, and frontend-design skills so it works standalone."
license: Bundled skills under vendor/ retain their original licenses. See each vendor/<name>/LICENSE.txt
---

# Document Builder

Three layers, run in order. Skipping any of them is what produces the two failures this skill exists to prevent - a polished document built on the wrong assumptions, and a polished document containing facts nobody can trace.

```
Layer 1  SPECIFY   Interview, then write and lock a spec. Nothing is drafted before approval.
Layer 2  BUILD     Draft against the spec, using the bundled format skill for the mechanics.
Layer 3  VERIFY    Run the sanity check. Nothing is delivered before it passes.
```

---

## Layer 1 - Specify

Interview before drafting. Every time, including when the request looks complete. A request that seems fully specified almost always leaves the audience, the boundaries, or the purpose unstated, and discovering that after a 20-page draft is expensive for everyone.

### Interview

Cover these. Use the interactive question tool for enumerable choices and prose for open ones. Group them into one or two rounds rather than a long interrogation - the point is precision, not ceremony.

**Purpose and audience**
- What decision or action should this document produce?
- Who reads it, and what do they already know? This sets the technical level and how much background to build.
- Who else sees it downstream - a supervisor, a client, a review committee? Documents are often written for one reader and judged by another.

**Format and constraints**
- Which format, and is that a hard requirement or your best guess? Say which format you would pick and why if they are unsure.
- Length, page or slide count, and any section structure that is mandated.
- Template, house style, or an existing document to match. Ask for the file if one exists rather than approximating it.

**Content and sources**
- What source material exists - uploads, prior conversation, notes, or research still to be done?
- What must be included, and what must be left out?
- Where numbers or citations appear, where do they come from?

**Visuals**
- Are diagrams, charts, or figures wanted, expected, or unwelcome?
- If data visuals are involved, does the underlying data exist yet? Do not proceed on the assumption that it does.

### Write the spec, get approval

Save a spec file to the working directory before drafting. It is the anti-drift anchor, and it needs to exist as a file rather than as conversation history that scrolls away.

```markdown
# Spec - <document title>
Purpose:        <the decision or action this serves>
Audience:       <primary, plus who else sees it>
Format:         <.docx / .pptx / etc>  Length: <pages, slides, words>
Style:          <template, tone, conventions>

## Outline
1. <Section> - <what it must accomplish> - <approx length> - <visual, if any>
2. ...

## Terminology lock
<term> = <definition and the exact form to use throughout>

## Sources
<what each section's facts come from>

## Open gaps
<facts still needed - see gap scan below>

## Out of scope
<explicitly excluded, so it does not creep back in>
```

Present it and wait for explicit approval. Silence is not approval. If the user revises it, update the file rather than only acknowledging the change in chat.

### Pre-flight gap scan

Before writing a single section, walk the approved outline and list every specific fact the document will require - figures, dates, names, citations, version numbers, prices, headcounts. Check each against available sources. Then ask for all the missing ones at once.

Doing this up front is what makes a strict no-invention rule livable. The alternative is stopping fourteen separate times mid-draft, which is why documents built this way usually end up with invented filler instead.

---

## Layer 2 - Build

### Read the bundled format skill first

This skill bundles its own copies of the format skills under `vendor/`. Read the relevant one before writing any generation code - they carry environment-specific details, library quirks, and rendering constraints that are not obvious and not guessable.

| Deliverable | Read |
|---|---|
| Word document, .docx, .dotx | `vendor/docx/GUIDE.md` |
| Slides, deck, .pptx, .potx | `vendor/pptx/GUIDE.md` |
| Spreadsheet, .xlsx, .csv | `vendor/xlsx/GUIDE.md` |
| PDF creation or form filling | `vendor/pdf/GUIDE.md` |
| HTML deliverable or web UI | `vendor/frontend-design/GUIDE.md` |

Several may apply - a report with charts needs the docx skill and the visual guidance below. Treat `vendor/<name>/` as that skill's root when following its instructions about script paths.

If an equivalent skill is also available in the environment outside this bundle, prefer whichever is newer. The bundled copies are snapshots and do not update themselves.

### Source fidelity

The specific failure to prevent is this one - the draft reaches a place where a number, date, citation, name, or quotation belongs, none is available, and something plausible appears instead. It reads exactly like the real thing, which is what makes it dangerous.

- **Never fill a factual slot from your own generation.** Not a statistic, not a date, not a citation, not an author, not a quotation, not a version number, not a company name.
- **Stop and ask** when a gap surfaces that the pre-flight scan missed. Do not defer it to the end and do not paper over it with vaguer language, which hides the gap instead of resolving it. Vagueness is a second failure mode - "significant growth" where a number was needed is not honest, it is just harder to catch.
- If the user wants a complete draft to react to, use a visible marker they can search for, and only with their agreement:

  ```
  [[NEEDS - Q3 2025 revenue figure, source unknown]]
  ```

  Markers must survive into the delivered file rather than being quietly resolved. The sanity check counts them and reports them.
- **Represent sources accurately.** Do not sharpen a hedged finding into a firm one, and do not attribute a claim to a source that only implies it.
- **Paraphrase rather than quote.** Keep quotations short and use them only where the exact wording carries the meaning.

### Drift control

Long documents drift - section 9 contradicts section 3, a term acquires a second name, the approved outline quietly gets abandoned. Drift is not a knowledge failure; it is a memory failure, and it needs mechanical countermeasures.

- **Re-read the spec file between sections.** Not the version in conversation history - the file. This is the single most effective countermeasure.
- **Draft in outline order** and mark progress in the spec as sections complete.
- **Honor the terminology lock.** One name per concept, used identically throughout. If a better term emerges, change it in the spec and apply it everywhere, rather than switching mid-document.
- **Log decisions as they are made** - a number's chosen unit, a scope call, a naming choice - in the spec. Undocumented decisions get re-decided differently later.
- **Do not silently expand scope.** If a section wants material the spec excluded, ask rather than adding it.
- **Build the file once, from complete content.** Assemble the text and visuals first, then generate. Regenerating a document repeatedly to make small edits is slow and is itself a source of drift, since each regeneration is an opportunity to lose a change.

### Visuals

Read `references/visuals.md` before producing any diagram, chart, or figure. It covers when a visual earns its place, choosing the right form, the data-integrity rules for charts, and implementation notes per format.

The short version - a visual must carry information the prose cannot. Decorative figures cost the reader time and cost you credibility.

---

## Layer 3 - Verify

Read `references/sanity-check.md` and run the full pass before delivering anything. This is not optional and it is not a formality - it is the layer that catches what the first two layers missed.

Report the result to the user in a few lines, including anything that failed and anything left unresolved. If unresolved markers remain, say so explicitly at delivery rather than letting the user discover them.

Then save the file to the outputs directory and present it.

---

## Bundled skills

`vendor/` contains verbatim copies of the docx, pptx, xlsx, pdf, and frontend-design skills as of packaging, including their licenses. They make this skill self-contained.

They are snapshots. They do not receive upstream fixes. To refresh, replace the folder contents with current copies from the environment's public skills directory, keeping each folder's internal structure intact so script paths continue to resolve.

Each bundled skill's own `SKILL.md` was renamed to `GUIDE.md` during packaging. A package may contain only one `SKILL.md`, at its root - nested ones cause upload to be rejected. Keep this rename when refreshing.

## Avoid

- Drafting before the spec is approved.
- Any invented fact, and any vague phrasing that conceals a missing one.
- Writing generation code before reading the relevant bundled format skill.
- Adding a visual because the document looks bare.
- Charting data that is partial, estimated, or not comparable across series.
- Delivering without running the sanity check, or running it and not reporting the result.
