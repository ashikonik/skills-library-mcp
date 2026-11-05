# Routing: how an entry is found

Scanning is not discovery. An entry that is scanned but never returned by a search
is an entry nobody uses. This is the reference for the three things that decide
whether a query finds the entry you just added.

---

## 1. What the search actually reads

The search is **pure lexical** — no embeddings, no model, no network. That is a
deliberate choice: it can be implemented independently in Python and TypeScript and
**required to agree exactly**, which an embedding scorer cannot.

Five fields are searched: the name, the description, the `metadata.promptSignals`
phrases, the domain, and the task table. The body of the document is **not**
searched — `search_library` does zero file I/O.

### The tokenizer

NFKC-normalise, lowercase, split camelCase **before** stripping punctuation
(`useEffect` → `use`, `effect`, so "use effect" matches), then split on
non-alphanumerics. Bigrams are emitted over the token sequence.

Only true function words are dropped — articles, prepositions, pronouns,
auxiliaries, conjunctions, about 45 of them. `test`, `write`, `fix`, `review`,
`build`, `debug` and `run` are **kept**: they are this library's domain vocabulary,
and an earlier prototype that stripped them made "write tests first" fail to surface
`tdd-workflow`.

### The scores

```
idf(t)        = ln(1 + N / df(t))
name_exact    = 3.0 * idf(t)    t is a name token
name_partial  = 1.5 * idf(t)    t is a prefix/substring of a name token
desc_match    = 1.0 * idf(t)    t is a description token
phrase        = 6.0             a query bigram matches a name bigram
signal        = 8.0 * idf(t)    t is in metadata.promptSignals.phrases
task_match    = 25.0            the query matches a task row
task_content  = 8.0             the query has the row's content, verb dropped
task_head     = 16.0            the row's content is the query's HEAD noun
task_demote   = -3.0            a later member of a fired row
tier_bias     = +1.0 / +0.25 / 0.0   tier 1 / 2 / 3
agent_bias    = +0.5            the entry is an agent
```

The tier bias is **multiplied by `(1 − name_exact_hit)`** — tiering never overrides a
direct name match, it only breaks ties among weak description-only matches. And the
maximum tier bias (1.0) is well below a single idf contribution (typically 3–6), so
it cannot reorder a strong match.

### What gets dropped

1. **Score threshold** — only `score > 0` survives. A query of pure function words
   returns nothing, not 1,078 rows.
2. **Hard cap** — `limit`, default 10, maximum 50.
3. **Relevance floor** — anything below `0.25 × topScore` is dropped.

### The tie-break

Score desc → tier asc → skill before agent → shorter name → lexicographic name. It
is fixed, because the TypeScript server must produce the identical ordering, and the
cross-implementation test compares the ordered id lists byte for byte.

---

## 2. The domain table

`mcp/build/domains.py` holds the domain names and their keyword lists. The domain is
a **keyword match on the name**, and it is **first-match-wins**: the first domain
whose keyword matches wins, and the rest are not considered.

The keyword match is word-boundary anchored, so `hit('agent-creator', ['agent'])`
fires on the whole word "agent" and `hit('test', ['test'])` does not fire on
"testing-writer".

### Why first-match-wins

"Any match" would put 291 skills in the ten core domains; first-match-wins puts 269.
The difference is not a count — it is that with first-match-wins, the domain in the
index is **exactly the domain the routing guide prints for that skill**. A skill
filed under "Security" by the guide and under "Other" by the index would route
differently depending on which tool answered.

### Adding your entry to the table

If your entry's name matches no keyword, it lands in "Other / uncategorised" and
ranks as tier 3. Two options:

- **Rename the entry** so it matches an existing keyword. `api-design` matches
  "API & integration" on the `api-` prefix; `tdd-workflow` matches "Testing & QA"
  on `tdd`. This is the cheapest fix and the one most entries use.
- **Add a keyword** to the domain the entry belongs to.

Put the keyword in the right domain, in the order that domain already uses. The
order matters within a domain only for ties, but the *domain order* matters
globally, because the first domain to match wins. Adding a broad keyword to an
early domain will steal entries from later ones.

The ten core domains are tier 2. Adding an entry to one of them is what promotes
it out of tier 3:

```
Core engineering practice   API & integration        Testing & QA
Security                   Data, databases & pipelines
DevOps & cloud             Architecture & design
Backend & API frameworks    Code review & quality
Frontend, UI & accessibility
```

---

## 3. The task table — the strongest router

`mcp/build/tasks.py` is a hand-written table of 73 rows, each `<task> → [skills],
[agents], note`. It is the section 2 router of the routing guide, and the index
reads the same table, so the guide and the search tool route the same way.

**A row that fires is worth 25.0 — more than any name or description match can
reach.** A row whose *content* is the query's head noun is worth 16.0. That is the
difference between "found on the fifth page" and "found".

```python
('Build an API', ['api-design', 'api-connector-builder', 'mcp-server-patterns'],
 ['code-architect', 'planner', 'code-architect'],
 '`api-design` covers resource naming, versioning and pagination.'),
```

### The row's order is the curation

The first entry in a row is its documented first choice. When a row fires on a head
match, that first entry earns the full 25.0 and the alternatives earn 16.0; on a
strict match the later members are **demoted** by 3.0.

Demoting rather than promoting is the measured choice: the relevance floor is a
fraction of the *top* score, so raising the ceiling evicts weaker-but-relevant
entries from the bottom of the list. Over the labelled query set, demoting lifts
rank-1 and rank-3 counts while evicting nothing.

### The note is part of the row

The note is prose, and it often names the entry the row means — "Prefer the
hand-authored `skill-creator-plus` pack", "use `architect`", "Pair with
`silent-failure-hunter`". Nine of the 73 rows name an entry their own lists omit,
and in every case the note is the only place that preference is written down. The
index builder promotes a note-named entry to the front of the row, so the curation
survives into the ranking.

**When you add a row, put the entry you mean first, and say so in the note if the
order is not obvious.**

### What a row fires on

The row's *content* is its tokens with the leading verb dropped — "Build an API"
→ `["api"]`. It fires when the query contains that content, and the strength
depends on position:

```
"write a REST API"            -> head: {write, rest, api}     -> the row fires
"add authentication to an api" -> head: {add, authentication}  -> the row does not
```

A word is the query's **head** when it is not the object of a preposition. The
first sentence is *about* an API; in the second, "api" is the thing being added to,
and the query is about authentication. This is why `api-design` takes the top slot
for the first and `twilio-security-api-auth` keeps it for the second.

### Adding a row

```python
('Review a data pipeline',
 ['data-pipeline-review', 'sql-patterns'],
 ['code-reviewer'],
 'The pipeline reviewer checks the extraction and the schema.'),
```

Rules:

- The task text is a **verb phrase** — "Write an API", not "APIs". The verb is
  dropped when the content is computed.
- The first skill in the list is the recommended one.
- Only name entries that exist. A name that is not in the library is dropped by the
  index builder, and the drop is recorded in `index.json` under
  `task_index_notes` — so the discrepancy is visible rather than silent.
- A row may list several things it covers, separated by `/`: "Write a document /
  report / deck". Each alternative gets its own content set.

---

## 4. `metadata.promptSignals`

Eighteen skills carry a curated set of activation phrases:

```yaml
metadata:
  promptSignals:
    phrases: ["write a REST API", "design an endpoint"]
```

An exact hit on one of these is worth `8.0 * idf(t)` — more than a description
match, and it fires regardless of whether the phrase appears anywhere in the
description.

This is the mechanism for the entries whose users phrase the request many different
ways. If your entry answers a question that gets asked five ways, this is where the
five ways go.

---

## 5. How to check that it works

### The query you expect

```bash
python3 - <<'PY'
import sys, os
sys.path.insert(0, 'mcp/python')
sys.path.insert(0, 'mcp/build')
from search import load_index
idx = load_index()
for r in idx.search("your query here", limit=10)['results']:
    print('%8.2f  %-14s %s' % (r['score'], r['id'], r['name']))
PY
```

### The labelled set

`mcp/scripts/eval_search.py` runs the real engine over 34 labelled queries naming
the skill that should win, plus 11 negatives that must return nothing. It is a
verification step, so a change that degrades the ranking **fails the build** rather
than passing unnoticed.

```bash
python3 mcp/scripts/eval_search.py --detail
```

Add a labelled query for your entry when you add it — that is what stops a later
change from quietly demoting it.

### The two servers must agree

```bash
python3 mcp/tests/test_agreement.py
```

This pushes 74 golden queries through the Python and the TypeScript servers and
compares the ordered id lists *and* the scores. If your change makes the two
implementations disagree, it fails here.

### The golden file

`mcp/tests/golden/search_golden.json` records what the search returns for those 74
queries. It is checked in, and regenerating it takes a deliberate flag:

```bash
python3 mcp/tests/test_agreement.py --update-golden
```

**Read the diff before you regenerate it.** The golden file is a property of the
corpus as much as of the engine: adding an entry legitimately changes some results,
but it also means the file no longer describes what it used to. A regenerated golden
file that hides a regression is worse than no golden file.
