---
name: humanizer
description: >
  Rewrites text to sound like a real person wrote it — not an AI. Use this skill
  any time the user asks to humanize, de-AI, rewrite, make sound natural, remove
  AI patterns, or fix robotic-sounding text. Also trigger when the user pastes
  text and says things like "make this mine," "fix this," "this sounds like AI,"
  or "clean this up." Even if the user doesn't use the word "humanize," if they're
  handing over a block of text and want it to sound more human or personal, use
  this skill. Always apply the full banned-patterns list below — never skip it,
  never explain it to the user unless asked.
---

# Humanizer Skill

Rewrite the user's text so it sounds like a real person wrote it. Not a polished, corporate, AI-flavored person. An actual human — direct, a little uneven in the right ways, with actual specifics and a point of view.

This skill draws on Wikipedia's *Signs of AI Writing* page, plus community-compiled pattern lists (word frequency studies, structural tells, tone issues). Two reference files hold the exhaustive detail:

- `references/banned-words.md` — the full word/phrase ban list (nouns, verbs, adjectives, adverbs, phrases)
- `references/pattern-details.md` — structural, grammatical, and tonal patterns with severity ratings, examples, and fixes

Read both before doing a rewrite of any real length. For quick fixes on short text, the condensed lists below usually cover it.

---

## The Core Job

Take whatever the user gives you and rewrite it, stripping every AI tell. Don't summarize what you changed. Don't explain your edits. Just give them the rewritten text, ready to use.

Match the register the user's original text implies — casual stays casual, professional stays professional. Humanizing isn't the same as dumbing down or making everything sound breezy.

---

## Kill-On-Sight List (highest severity, no exceptions)

- **Em dash overuse** — one per 500 words max. Use commas or periods instead.
- **"Delve," "moreover," "furthermore," "underscore," "tapestry," "testament to," "landscape" (metaphorical)** and the rest of the AI vocabulary (full list in `references/banned-words.md`)
- **"Not X, but Y" / "it's not just X, it's Y"** constructions — pick one description, say it once
- **Rule of three used reflexively** — triplets everywhere ("innovative, transformative, and groundbreaking") — vary the number
- **Rhetorical question immediately answered** — "The result? Chaos." — either ask for real or just state it
- **Forced hot-take phrasing** — "Here's the thing," "Hot take:," "And honestly?," "That's the real unlock" — cut it, say the actual thing
- **Bullet points replacing sentences** in narrative or conversational writing
- **Section headers** in anything shorter than a real report
- **Bloated, repetitive conclusions** starting with "Overall," "In conclusion," "In summary"
- **Self-referential AI language** — "As an AI language model," "As a large language model," any knowledge-cutoff disclaimer, prompt-echoing
- **Vague attribution** — "experts say," "studies show," "many believe" — with nothing named
- **Generic metaphors** — "a symphony of," "a tapestry of," "a delicate balance," "nestled in"
- **Defaulting to "Emily" or "Sarah"** for example names, or generic proper nouns generally — use something specific instead

---

## How to Rewrite

**Keep the meaning. Change the feel.**

- Vary sentence length on purpose — don't let every sentence run the same rhythm
- Use contractions ("it's," "don't," "we've") — AI underuses them
- Let a sentence fragment stand if it lands better than a full sentence would
- Use real specifics — actual names, numbers, examples — instead of vague placeholders or "from X to Y" ranges
- Cut any sentence that exists to sound thorough rather than say something
- If a phrase does no work, delete it — don't swap it for a different filler phrase
- Keep a consistent voice start to finish; don't let tone drift between formal and casual mid-piece
- Don't sand down a real opinion into "there are pros and cons" — if the user's original take had an edge, keep it
- Show reactions through what's said or done rather than explaining them afterward ("...which was surprising because...")

**What you're aiming for:** text that sounds like one specific person with a point of view wrote it — not a content generator trying not to be wrong.

For a full pass on longer or higher-stakes text, check the piece against `references/pattern-details.md` category by category (punctuation, overused constructions, structure, tone, specificity, repetition).

---

## What NOT to Do

- Don't explain what you changed or list your edits
- Don't preface with "Here's the rewritten version:" — just give it
- Don't add a summary at the end
- Don't ask clarifying questions unless the text is so short or ambiguous you genuinely can't tell what it's for
- Don't flatten a distinctive or opinionated voice into something safe and balanced

---

## Quick Self-Check Before Outputting

- Any word from `references/banned-words.md` that isn't load-bearing?
- Any construction from the kill-on-sight list?
- Any sentence that ends in tacked-on analysis or explains a reaction that was already shown?
- Any opening filler, closing sign-off, or restated conclusion?
- Are all the sentences roughly the same length and shape? If so, vary them.
- Does every proper noun/example feel specific, or did something default to generic?

If any of these hit, cut or rewrite before responding.
