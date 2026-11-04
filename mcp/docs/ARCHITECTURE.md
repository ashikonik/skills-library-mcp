# Architecture

Two servers, one artifact, one index.

```
                        .library_data.json
                                |
                    mcp/build/build_index.py
                                |
                     mcp/data/index.json
                        /              \
             mcp/src/**  (TS)      mcp/python/**  (Python)
             SDK-backed server     stdlib-only fallback
                        \              /
                         identical answers
```

The index is the only thing the two servers share. It is a derived
artifact — the servers never depend on the machine scan, and the index
can be rebuilt without rescanning anything.

---

## Why two implementations

The library's own philosophy is **adversarial verification**: a second
implementation with deliberately different logic, which is *required* to
disagree loudly if it disagrees.

The Python fallback is not a "simplified" server. It is a second
implementation of the same specification, written from the same rules
but with different code, so that a bug in one is unlikely to be a bug
in the other.

The fallback exists for a real reason: the Python server needs **no
dependencies at all**. If the SDK cannot be installed — an offline
machine, a locked-down environment, a vendored checkout — the server
still runs, because it is stdlib Python and a JSON file.

### What "agree" means

The agreement gate (`mcp/tests/test_agreement.py`) checks five things
across both implementations:

| Check | Scope |
|---|---|
| search | 74 queries → identical id lists **and identical scores**, in identical order |
| tokenizer | 5,741 vocabulary tokens → identical output |
| head tokens | 5,741 vocabulary tokens → identical head-noun sets |
| frontmatter | 1,078 documents → identical `name`, `description`, `tools`, `model` |
| tool surface | 8 tools → identical names, titles, descriptions, annotations, order |

The scores must match to the last decimal. That is why
`round4()` in TypeScript is implemented with `BigInt` on the exact
binary value of the double: JavaScript's `toFixed` rounds ties away
from zero, Python's `round()` rounds them to even, and the two
disagree on exactly the values most likely to appear.

Similarly, the tie-break order compares names by **code point**, not by
UTF-16 code unit, because JavaScript's `<` on strings compares code
units and Python's compares code points. They differ on characters
outside the Basic Multilingual Plane.

---

## Why lexical search, not embeddings

No network, no model files, no 200 MB download — the server must start
offline, in a fraction of a second, every session.

More importantly: **a lexical scorer can be re-implemented by hand in
two languages and required to agree exactly.** An embedding scorer
cannot — model drift, tokenizer versions and floating-point ordering
would silently change results, and the cross-implementation gate would
be unenforceable.

The corpus also carries its own supervision. Eighteen skills have
hand-curated `metadata.promptSignals` phrases, and those phrases are
matched *as phrases*, not as loose tokens. Matching them loosely gave
`vercel-cli` credit for "build failed" — a symptom it lists — so it
scored 41.82 for "fix a failing build" while having nothing to do with
it.

---

## The two rules that filter the results

Scoring alone is not enough: with 1078 entries, almost any query
matches *something*. Two rules cut the noise. Both were tuned against
a labelled query set, not by feel — `mcp/scripts/eval_search.py` is
that set, and it is a verification step.

A third rule — the task table's own curation — does not filter, but it
orders what survives; it is described in section 3.

### 1. Token coverage

An entry must match at least two thirds of the query's **distinctive**
tokens, and at least two when the query has two or more.

*Distinctive* means: appearing in fewer than 1.8 % of the corpus. A
common word carries no information about which entry the query wants,
and requiring it filters on luck rather than relevance. "write" appears
in 37 of 1078 entries.

This rule is what stops "bake sourdough bread at home" from reaching
`shopify-polaris-app-home` on the word "home", and "quantum
chromodynamics lattice simulation" from reaching
`web-game-foundations` on "simulation".

The distinction was measured, not guessed. Before the rule counted only
distinctive tokens, "write documentation" returned just `mixpanelyst` —
`documentation-lookup` was dropped for not also containing the generic
verb "write", even though the subject of the query was "documentation"
and the skill's *name* is that subject.

### 2. Task rows

The 73 hand-written rows of the task index are a better router for
task-shaped queries than any automatic score. A row fires three ways:

| Match | Condition | Bonus |
|---|---|---|
| strict | the query has 60 % of the row's tokens | 25.0 |
| head | the row's content is the query's **head noun** | 16.0 |
| content | the row's content is present, verb dropped | 8.0 |

The rows are written "<verb> <object>" — "Build an API". The strict
rule reads the *whole* row, so it demanded the query's verb as well as
its object, and "write a REST API" never reached the row that names
the right skills. The **content** match drops the row's verb: "write a
REST API" has the content "api", which is what "Build an API" is about.

A single content token fires the row when it is distinctive, or when it
is the query's **head** — the thing the query is *about*, as opposed to
the context it merely mentions. That distinction is the whole point:

```
"write a REST API"            → head: {write, rest, api}
"add authentication to an api" → head: {add, authentication}
```

The first is about an API, so the "Build an API" row fires and
`api-design` takes the top slot. The second is about authentication;
"api" is only the thing being added to, so the row does **not** fire and
`twilio-security-api-auth` keeps the top slot. Without the head rule
both queries fired the row, and the API builder outranked the skill
that was actually about authentication.

`head_tokens` lives in the shared tokenizer, so both servers compute
it identically — the cross-implementation gate pushes all 5741 corpus
vocabulary tokens through both and compares.

### 3. The table's own curation

The task table is hand-written, and it encodes a *preference*: a row
lists its **primary** entry first, and its note says which one that
is.

```
('Build an API', ['api-design', 'api-connector-builder', 'mcp-server-patterns'],
 ['database-reviewer'],
 '`api-design` covers resource naming, status codes, pagination, versioning, rate limits.')
```

Two pieces of that curation used to be lost between the table and the
ranking, and both are now preserved:

1. **The order.** The builder sorted each row's lists, so position 0
   carried no meaning. It now keeps the order the table chose.
2. **The note.** Nine of the 73 rows name an entry their own lists
   omit — "use `architect`", "pair with `silent-failure-hunter`",
   "prefer `skill-creator-plus`" — and in every case the note is the
   *only* place that preference is written down. Those entries are
   promoted to the front of their row.

On a strict match, a row's later members are demoted by 3.0.

The demotion is a demotion rather than a promotion of position 0, and
the reason is the relevance floor: it is a fraction of the *top*
score, so raising the ceiling can evict a weaker but relevant entry
from the bottom of the list. Measured over the labelled set, demoting
lifts the rank-1 and rank-3 counts while evicting nothing; promoting
the primary entry instead evicts entries at the same strengths.

The content branch is left alone. A content match means the query
named the row's *object* — "write a REST API" reaches "Build an API" —
not that it asked for that specific task, so the row's members stay on
equal footing there.

### Measured, not felt

```
rank 1    : 20 / 34
rank <= 3 : 28 / 34
rank <=10 : 34 / 34
negatives : 0 leaked
```

Run `python3 mcp/scripts/eval_search.py --detail` to see every query
with its rank.


---

## Layout

```
mcp/
├── build/
│   ├── build_index.py     the index builder
│   ├── domains.py         the 38 DOMAINS name-lists
│   ├── tiering.py         assign_tiers() -- the only place tiers are computed
│   └── tasks.py           the 73-row task-type index
├── data/
│   └── index.json         the generated artifact (gitignored)
├── src/                   TypeScript server
│   ├── index.ts           the ONLY file that knows the transport
│   ├── server.ts          createServer() -- transport-independent
│   ├── search.ts          ranking engine (pure, no I/O)
│   ├── tokenize.ts        tokenizer
│   ├── frontmatter.ts     tolerant reader + per-harness emitters
│   ├── installers.ts      per-harness installers
│   ├── index-loader.ts    loads the index
│   ├── types.ts
│   └── tests/             Node's built-in runner
├── python/                the fallback server (stdlib only)
│   ├── server.py          hand-rolled JSON-RPC 2.0 over stdio
│   ├── search.py          the same ranking algorithm, ported
│   ├── tokenize.py        the same tokenizer, ported
│   ├── frontmatter.py     the same reader and emitters, ported
│   └── installers.py      the same installers, ported
├── tests/                 Python test suite
│   ├── test_mcp.py        index, descriptions, search, safety
│   ├── test_agreement.py  the cross-implementation gate
│   ├── test_jsonrpc.py    the protocol, against both servers
│   ├── queries.py         the 74 golden queries
│   └── golden/            the checked-in golden file
├── scripts/
│   ├── rebuild.sh         build everything and test it
│   ├── register.sh        print or apply the harness config
│   ├── run-tests.sh       the TypeScript suite, with a zero-test guard
│   └── smoke.mjs          start the server and check it answers
└── docs/
    ├── ARCHITECTURE.md    this file
    ├── REGISTERING.md     how to register with each harness
    ├── TOOL_REFERENCE.md  the eight tools
    └── INSTALLING.md      how skills land in a harness
```

---

## The index

`mcp/data/index.json` is the shared artifact. It carries
**descriptions, tokens and bundle manifests only** — not the SKILL.md
text.

| Measured | |
|---|---|
| Total SKILL.md text | 8.4 MB |
| Total bundle size | 66 MB (5,685 files) |
| Index size | ~5 MB |

So the servers never load the text. `search_library` does **zero** file
I/O; `get_skill` reads one file; `get_skill_bundle` reads only the
named files, under a byte cap.

### Why the index is not a new key in `.library_data.json`

The Phase 1 frontmatter fix changes `.library_data.json` once, and
everything downstream follows from it. Keeping the index separate
means it can be rebuilt without re-scanning the machine — which is
what makes the build fast and the determinism check cheap.

### Determinism

The index is written with `sort_keys=True`, `ensure_ascii=False` and a
trailing newline. Two runs over an unchanged library are byte-identical
apart from `generated_at`. `.verify_determinism.py` proves it by
rebuilding everything a second time and comparing hashes.

---

## The protocol layer

### The TypeScript server

`src/index.ts` is the only file that knows about the transport.
Everything above it is transport-independent, so the same server can be
driven over stdio in production and in-process in a test — which is
exactly what `mcp/tests/_ts_tools.mjs` does, using the SDK's
`InMemoryTransport.createLinkedPair()`.

Dependencies are pinned exactly:

| Package | Version | Why |
|---|---|---|
| `@modelcontextprotocol/sdk` | `1.32.2` (exact) | the transport and the tool registry |
| `yaml` | `^2.8.1` | frontmatter parsing |
| `zod` | `^4.1.13` | input schemas |

The SDK is pinned exactly, not to a range: a server that must start
offline needs to start with the versions that were tested.

Only `z.string()`, `z.number()`, `z.enum()` and `z.boolean()` are used
— an API surface that is identical across zod 3 and zod 4, so the pin
can move without a rewrite.

### The Python server

Hand-rolled JSON-RPC 2.0 over stdio, newline-delimited — matching the
SDK exactly (`serializeMessage = JSON.stringify(m) + '\n'`).

Three properties matter more than the rest:

- **stdout is protocol-only.** All logging goes to stderr. A stray
  `print` corrupts the stream, and it is the most common way a
  hand-rolled MCP server breaks.
- **Notifications get no response.** `notifications/initialized` has no
  `id`, and must not produce a reply.
- **Nothing raises out of the loop.** Every handler exception becomes a
  JSON-RPC error. A crash in one tool must not take the server down.

Protocol versions are negotiated by echoing the client's when known:
`2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05, 2024-10-07`.

---

## The frontmatter problem

Two agents — `Explore` and `silent-failure-hunter` — carry an unquoted
`:` inside a plain scalar, which PyYAML rejects. Rather than losing
their whole frontmatter block, the reader falls back to a line-oriented
parser and recovers the fields individually.

Both implementations do this, and both must produce the *same* answer.
That is the `frontmatter` check in the agreement gate: 1,078 documents,
four fields each.

The fallback also has to recover two shapes the strict parser handles
differently:

- an inline YAML list — `tools: ['search', 'read']`
- a quoted scalar — `model: 'opus'`

Without that, Python returned a real list where TypeScript returned a
stringified one, and the gate caught it.

### The `agentsmd` dialect

`AGENTS.md` is one shared file that many skills live in. It gets its
own path through the installer: each skill is a marked section,
appended, with an HTML-comment marker so the file stays safe to share.

---

## The tiering

`assign_tiers()` in `mcp/build/tiering.py` is the **only** place tier
numbers are computed.

| Tier | What | Count |
|---|---|---|
| 1 | the six hand-authored packs + all 102 agents | 108 |
| 2 | skills whose *first* matching domain is one of the ten core domains | 269 |
| 3 | everything else | 701 |

Tier 2 uses **first-match-wins**, not any-match — any-match gives 291.
First-match-wins guarantees the index's domain is exactly the domain
the routing guide prints, so the index and the guide can never disagree.

**Tiers bias ranking; they never filter.** Every skill and agent stays
searchable at every tier. The tier bias is multiplied by
`(1 − name_exact_hit)`, so it can never override a direct name match,
and its maximum (1.0) is well below a single idf contribution
(≈3.0–6.0) — it only breaks ties among weak, description-only matches.

---

## The build

```
.build_library.py    →  .library_data.json   (machine scan)
.build_guide.py      →  ROUTING_GUIDE.md     (from .library_data.json)
.gen_report.py       →  SKILLS_AND_AGENTS_REPORT.md  (independent scan)
build_index.py       →  mcp/data/index.json  (from .library_data.json)
npm run build        →  mcp/dist/            (TypeScript)
```

The guide reads `.library_data.json`. The report does **not** — it
re-scans the machine independently, on purpose. That is what makes the
report a check on the library rather than a copy of it.

`.verify_all.py` runs thirteen checks, and the last four are skipped with
a message (not failed) when the index is missing — a fresh clone
without a built index should not report a false failure. The skipped
steps are named in the output, so a green run never hides them.

---

## The safety model

Every write tool is a dry run unless `apply` is true. This is enforced
in code, in both implementations, and it is tested.

| Rule | Enforced where |
|---|---|
| `apply` defaults to `false` | the tool schema and the handler |
| Writes confined to a fixed whitelist | `check_target` / `checkTarget` |
| Symlinks point into the library | the installer resolves the target before writing |
| `overwrite` defaults to `false` | the tool schema and the handler |
| `~/.claude/skills/learned/` excluded | `EXCLUDED_PREFIXES` |
| Uninstall refuses an outward symlink | `uninstall_target` / `uninstallTarget` |

---

## Why the search is *not* an embedding

Restated, because it is the decision most likely to be questioned:

1. **Offline.** The server starts in a fraction of a second, every
   session, with no network.
2. **No model files.** No 200 MB download, no runtime, no dependency.
3. **Determinism and auditability.** Two hand-written implementations
   can be required to agree exactly. Two embedding models cannot.
4. **The corpus supervises itself.** Eighteen skills carry hand-curated
   activation phrases; exact hits beat fuzzy similarity, and the
   phrases are matched as phrases.

---

## Git and rollback

Two layers, kept deliberately:

- **Git** is the coarse layer. It reverts the whole project.
- **Per-step snapshots** are the fine layer. They revert one step,
  without touching git history.

`./run.sh` runs each build step as a discrete, snapshotted, validated
step and records everything under `logs/<run_id>/`:

```
logs/20261104T162731Z/
  manifest.json     every step: command, exit code, sha256 before/after,
                    changed files, validation assertions, problems
  01-build-library.log
  ...
  snapshot/01-build-library/
```

`./rollback.sh <run_id> [--step N]` restores from the snapshot.
Nothing is ever pruned from `logs/` without asking.
