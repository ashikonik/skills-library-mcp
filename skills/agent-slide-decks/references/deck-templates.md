# Deck templates

## Pitch deck (10 slides)

1. Title — company, one-line position
2. Problem — who hurts, how much
3. Solution — what you built, in one sentence
4. Product — what it actually does
5. Traction — the number that proves it
6. Market — size, bottom-up
7. Business model — how you make money
8. Competition — why you win
9. Team — why you
10. The ask — amount and use of funds

## Explainer (8 slides)

1. Title — the claim
2. The problem — concrete, with a number
3. Why it happens — the mechanism
4. What most people try — and why it fails
5. The insight — the turn
6. Proof — data or a result
7. What to do — three steps
8. Summary — one sentence to repeat

## Talk (12 slides, 20 minutes)

Use the talk structure, not the document structure:

- 1 title
- 2 the hook
- 3 why this matters to the audience
- 4-9 one idea per slide
- 10 the takeaway
- 11 what to do next
- 12 questions

## Marp frontmatter reference

```yaml
---
marp: true
theme: default
paginate: true
size: 16:9
header: 'Company name'
footer: 'Confidential'
style: |
  section { font-size: 32px; }
  h1 { color: #f43f5e; }
  section.lead h1 { font-size: 56px; }
---
```

Per-slide directives:

```markdown
<!-- _class: lead -->
<!-- _backgroundColor: #111 -->
<!-- _paginate: false -->
```

## Export

```bash
marp deck.md -o deck.html
marp deck.md -o deck.pdf --pdf-notes --pdf-outlines
marp deck.md -o deck.pptx
```

## python-pptx layout indices

| Index | Layout |
|---|---|
| 0 | Title slide |
| 1 | Title and content |
| 2 | Section header |
| 3 | Two content |
| 4 | Comparison |
| 5 | Title only |
| 6 | Blank |
