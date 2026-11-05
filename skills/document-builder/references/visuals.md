# Visuals, Diagrams, and Charts

## When a visual earns its place

Add a visual when it carries something the prose cannot express efficiently - a spatial relationship, the shape of a distribution, a sequence with branching, a structure with many connections, or a comparison across several dimensions at once.

Do not add one because a section looks text-heavy, because a report "should have figures", or because the data happens to be available. A decorative figure costs the reader attention and signals that the rest of the document may also be padding.

Two quick tests:
- If the caption alone conveys the whole point, delete the figure and keep the sentence.
- If a reader would have to consult the prose to interpret the figure, the figure is incomplete, not helpful.

Confirm the visual plan in the spec during Layer 1. Adding unrequested figures late is a form of scope drift.

## Choosing the form

| What you need to show | Use | Not |
|---|---|---|
| Change over time | Line chart | Bar chart with time on x-axis, unless intervals are discrete |
| Comparison across categories | Bar chart, sorted by value | Pie chart |
| Composition, few parts | Stacked bar, or a table | Pie chart with more than four slices |
| Relationship between two variables | Scatter plot | Two overlaid line charts |
| Distribution | Histogram or box plot | Mean alone |
| Process with steps and branches | Flowchart | Numbered prose list, when branching exists |
| System components and connections | Architecture or block diagram | A table of components |
| Hierarchy or classification | Tree diagram | Nested bullets, when depth exceeds three |
| Sequence of interactions between parties | Sequence diagram | Prose narration |
| Precise values readers will look up | Table | Any chart |

That last row matters more than it looks. A chart communicates shape; a table communicates values. When readers need to find a specific number, a chart actively obstructs them.

## Data integrity for charts

A chart makes data look authoritative regardless of whether it is. The rules from the fidelity section apply with more force here, because a fabricated value in a figure is far harder to spot than one in a sentence.

- **Never plot an invented, estimated, or interpolated value.** If a series has gaps, either show the gaps or do not chart the series.
- **Do not plot values that were not measured comparably** - different definitions, periods, populations, or methods. If they must appear together, separate them visually and state the difference in the caption.
- **Start bars at zero.** Truncating a bar axis exaggerates differences and is the most common way an honest dataset produces a misleading figure. Line charts may use a non-zero axis when showing change, but say so.
- **Label axes with units.** An unlabeled axis is an unusable chart.
- **Caption with the source and the takeaway** - what the data is, where it came from, and what the reader should conclude. If you cannot state the takeaway, reconsider whether the chart belongs.
- **Round consistently** and never to more precision than the source supports.

## Diagram construction

- One idea per diagram. Two loosely related ideas make two diagrams.
- Aim for under about a dozen nodes. Beyond that, decompose into an overview plus detail views.
- Direction should be consistent and conventional - flows top-to-bottom or left-to-right, not both in one figure.
- Label the edges, not just the boxes. Unlabeled arrows are where diagrams lose their meaning.
- Legends only when the encoding is not self-evident.
- Keep the color palette small, and never let color be the only thing distinguishing two elements - it fails in greyscale printing and for colorblind readers. Pair it with shape, position, or a label.

## Implementation

Read the relevant bundled format skill first; it governs how visuals are placed in that format.

- **Charts in .docx and .pptx** - follow the bundled skill's guidance. Native chart objects stay editable in Office; rendered images are more predictable across viewers. Ask the user which matters more if the document will be edited by others.
- **Diagrams** - generate as an image and place it, unless the bundled skill offers a native path. Ensure adequate resolution for print if the document may be printed.
- **Spreadsheets** - see `vendor/xlsx/GUIDE.md` for charts anchored to live cell ranges, which update when the data does.
- **HTML deliverables** - see `vendor/frontend-design/GUIDE.md`.

Whatever the route, inspect the rendered result before delivering. Figures that overflow margins, clip labels, or render at unreadable sizes are common and invisible until someone looks. The sanity check requires this.

## Accessibility and print

- Alt text on every figure, describing what it shows rather than that it is a chart.
- Legible at final printed size, not just on screen.
- Readable in greyscale.
- Numbered and referenced from the text ("Figure 3 shows..."), so a figure separated from its page still has a home.
