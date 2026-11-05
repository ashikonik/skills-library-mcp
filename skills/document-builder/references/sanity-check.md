# Sanity Check

Run this in full before delivering any document. Work through it in order - the passes are ordered so that the cheapest, most consequential failures surface first.

Do not run it from memory of what you wrote. Open the spec file and open the generated document. Checking a document against your recollection of it defeats the purpose, because your recollection is the thing that drifted.

## Pass 1 - Fidelity

The highest-stakes pass. One fabricated figure destroys more trust than ten formatting errors.

- [ ] Every number, date, name, citation, version, and quotation traces to a source or to the user. List them and check them one at a time - do not spot-check.
- [ ] No claim is stated more firmly than its source supports.
- [ ] No vague phrasing stands in for a fact that was never obtained. Search for hedges like "significant", "substantial", "many", "recent" and confirm each is a genuine choice, not a patch over a gap.
- [ ] Every `[[NEEDS ...]]` marker is counted. Report the count and locations to the user at delivery.
- [ ] Citations point to works that actually exist and say what they are cited for.
- [ ] Quotations are verbatim from the source and short.

## Pass 2 - Spec conformance

- [ ] Every outline section is present, in order.
- [ ] Nothing was added that the spec did not call for.
- [ ] Nothing from the "out of scope" list crept in.
- [ ] Length is within the agreed range - check actual pages, slides, or words rather than estimating.
- [ ] Format, template, and style match what was agreed.
- [ ] Each section accomplishes the purpose the spec assigned it, not merely covering the topic.

## Pass 3 - Internal consistency

This is the drift check, and it needs a full read rather than a skim.

- [ ] The same number is the same everywhere it appears. Cross-check figures repeated in text, tables, charts, and any executive summary.
- [ ] Terminology matches the lock. One name per concept, no synonyms that look like different things.
- [ ] No section contradicts another. Pay attention to the summary and conclusion, which are usually written last and are the most common place to find claims the body does not support.
- [ ] Every forward and backward reference resolves - "as discussed in Section 4" points to the right section, and that section discusses it.
- [ ] Acronyms are expanded on first use, once, and used consistently after.
- [ ] Tense, person, and voice are consistent throughout.

## Pass 4 - Visuals

- [ ] Every figure and table is referenced from the text.
- [ ] Numbering is sequential with no gaps or duplicates.
- [ ] Captions state the source and the takeaway.
- [ ] Axis labels and units are present.
- [ ] Chart values match the source data and the numbers in the prose.
- [ ] No figure plots an invented, estimated, or non-comparable value.
- [ ] Alt text is present.

## Pass 5 - Rendered output

Open the generated file and look at it. Do not skip this because the code ran without error - the most common document defects are invisible at generation time and obvious on sight.

- [ ] The file opens without repair prompts or errors.
- [ ] Images render, at adequate resolution, within margins, not clipped or stretched.
- [ ] Tables fit the page width and do not split awkwardly.
- [ ] No text overflows a slide, text box, or cell.
- [ ] Headings, numbering, table of contents, and page numbers are correct and updated.
- [ ] Fonts render as intended rather than silently substituting.
- [ ] For slides - nothing overlaps, speaker notes are attached to the right slides, and text is legible at presentation size.
- [ ] For spreadsheets - formulas compute, no error values, column widths show full contents.

For visual formats, render pages or slides to images and inspect them. The bundled format skills describe how.

## Pass 6 - Delivery readiness

- [ ] Filename is descriptive and dated where useful.
- [ ] No drafting scaffolding left behind - lorem ipsum, TODO notes, comments, tracked changes, or leftover template content.
- [ ] Document metadata does not carry over from a template.
- [ ] The file is in the outputs directory.

## Report

Tell the user, in a few lines:

1. Passed, or what failed.
2. Unresolved markers - how many and where.
3. Anything you assumed rather than confirmed.
4. Anything you noticed that is outside the spec but worth their attention.

Never report a pass you did not run. If a pass could not be completed - a file could not be rendered, a source could not be checked - say that plainly rather than omitting it. An unmentioned gap is indistinguishable from a verified one, which is exactly the failure this layer exists to prevent.
