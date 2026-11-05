# The scanner's rules

The scanner is `.build_library.py`. It walks a root directory, finds candidate files,
classifies them, and writes them out as `skills/<name>/` and `agents/<name>.md`.

This is the reference for **placement** and **frontmatter**. For how an entry is
*routed* afterwards, see `routing.md`; for whether it can be *published*, see
`publishing.md`.

---

## 1. What the scanner walks

**The root.** By default it is the machine's home directory — the library is a
consolidation of everything installed on the machine. Two things change that:

- `SKILLS_LIBRARY_SCAN_ROOT` overrides it. A published tree rebuilds itself from its
  own contents this way, because a clone has no other machine to scan.
- When the root *is* the library directory, the tree is the source: the copy step is
  skipped, because the files are already where they belong.

**What it skips.** `node_modules`, `.git`, `venv`, `.venv`, `site-packages`,
`__pycache__`, `.npm`, `.gradle`, `.m2`, `dist`, `build`, `.next`, `target`,
`.ruff_cache`.

Two that are deliberately *not* skipped:

- **`.cache`** — package caches vendor real skills. Typer's `.agents/skills/typer`
  lives in a uv archive cache and is a genuine, usable skill.
- **`vendor`** — a skill's own `vendor/` directory holds the working files it ships.
  `document-builder`'s docx/pptx/xlsx tooling is there, and dropping it makes the
  copied skill non-functional.

It also never re-scans the library's own `skills/` and `agents/` output (that would
feed back into itself), and never scans a *different* directory that holds its own
`.library_data.json` (that is a published copy of this same library, and scanning it
would double-count every entry).

## 2. Skills

A skill is any directory containing a file named exactly `SKILL.md`.

```
<root>/<somewhere>/<name>/SKILL.md
```

The entry's name is the frontmatter `name:`, or — when there is none — the
directory's own name. The whole directory is copied, supporting files included, so
the entry arrives with everything it needs.

**Duplicate names are a collision, not a merge.** If two directories on the machine
hold a skill with the same name, the builder picks one by a scoring function and
*skips the other entirely*, recording the collision. The scoring prefers:

- a non-locale path over a locale one (`ja-JP`, `zh-CN`, `tr`, `de`, …)
- a path outside `.tmp` over one inside it
- `~/Projects/ECC/skills/` over other projects
- this library's own directory over everything else
- the canonical upstream copy over a flattened adapter copy

**The `ponytail` case is the one to know.** Ponytail ships flattened copies of its
skills under `.openclaw/skills/`, with truncated descriptions that drop the trigger
phrases the routing guide matches on ("yagni", "be lazy", "over-engineering"). The
builder penalises anything under `/.openclaw/` specifically — a general
"penalise dot-directories" rule would flip about 69 existing skills.

### The frontmatter

```yaml
---
name: my-new-skill              # must match the directory name
description: >
  What it does, and when to use it. This is the routing surface.
---
```

| Field | Shape | Effect |
|---|---|---|
| `name` | a string | the entry's identity. Must equal the directory name. |
| `description` | a string, or a `>`/`|` block | what search matches on, and what the model reads before deciding to load the skill. |
| `allowed-tools` | a list, or a comma string | the tool allow-list. Normalised to a JSON array by the index builder. |
| `license` | a string | the licence the content is redistributed under. Read by the provenance resolver. |
| `metadata` | a map | carried through verbatim. `metadata.promptSignals` is special — see below. |
| `disable-model-invocation` | a boolean | `true` keeps the skill out of automatic activation. |
| `user-invocable` | a boolean | `false` hides it from the slash-command list. |
| `version`, `compatibility` | strings | informational. |

**`metadata.promptSignals`** is the strongest routing signal in the system. It is a
curated list of activation phrases, and an exact hit on one is worth more than any
description match:

```yaml
metadata:
  promptSignals:
    phrases: ["write a REST API", "design an endpoint"]
    allOf: [["migrate", "database"]]
    anyOf: ["openapi", "swagger"]
```

Eighteen skills in the library carry one. It is worth writing when the skill answers
a question people phrase in many ways.

### `description` and the YAML bug

The description is read through a real YAML parser, with a line-oriented fallback.
The fallback reads **one line per key**, so a plain scalar that continues on the next
line is truncated.

That is not hypothetical: it cost 17 skills in this library their activation
triggers. `math-olympiad` lost 629 characters, including every mention of "IMO" and
"Putnam" — so the skill was unreachable by search for the exact queries it exists to
catch.

The fix is a block scalar:

```yaml
description: >
  A long description, folded across
  several lines.
```

A `>` block scalar is folded into one line, and the parser handles it correctly.
`|` keeps the line breaks. Both are safe; a bare multi-line scalar is not.

## 3. Agents

An agent is a **single markdown file** — not a directory — with a frontmatter block.
It is copied to `agents/<name>.md`.

### The three hard rules

**Rule 1 — the file must be at least 200 characters.** Shorter files are skipped
outright. A two-line agent stub is not an agent.

**Rule 2 — it must carry a `name:` in its frontmatter, or be one of three
recognisable shapes without one:**

| Shape | How it is recognised | Name comes from |
|---|---|---|
| OpenCode style | `mode: subagent` in the frontmatter | the filename stem |
| VS Code style | the filename ends `.agent.md` | the stem, minus `.agent` |
| Prose style | no frontmatter at all, and it sits in a directory named `agents` | the filename stem |

**Rule 3 — it must *look* like an agent.** A file is only taken as an agent when at
least one of these holds:

- its directory is literally named `agents`
- it is **not** inside a companion directory — `references/`, `rules/`, `examples/`,
  `templates/`, `assets/`, `docs/` — and its filename starts with `agent`, `code-`,
  `build-`, `ecc-` or `tdd-`, or ends with one of the suffixes below, or it is one of
  the three shapes above
- it **declares itself a sub-agent**: `agents: [...]`, an empty `agents:`, an empty
  `handoffs:`, or a `target: <something>`

The suffix list is fixed and lives in `.build_library.py` as `AGENT_SUFFIX`:

```
-reviewer   -architect  -resolver   -planner   -specialist  -optimizer
-explorer   -evaluator  -updater    -cleaner   -hunter      -analyst
-operator   -harness    -generator  -finder     -packager    -sanitizer
-forker     -troubleshooter  -staff  -guide     -coordinator  -runner
-lookup     -creator    -verifier   -auditor   -critic      -scorer
-drafter    -mapper     -miner      -builder   -researcher  -loader
```

A file that *declares itself* a sub-agent is one whatever its filename is. That rule
exists because of VS Code's `Ask.agent.md` / `Plan.agent.md` / `Explore.agent.md`:
they name themselves in frontmatter and carry `agents:` or `handoffs:`, and a
filename heuristic alone would have missed them.

### What is explicitly *not* an agent

Even with a `name:` and 200+ characters, these are excluded:

| Excluded | Recognised by |
|---|---|
| slash commands | the directory is `commands`, or `command: true` in the frontmatter |
| commands that route to an agent | `agent: <name>` in the frontmatter — the *agent* never carries this key; it uses `agents:` for its own sub-agents |
| per-project memory files | the directory is `memory`, or `node_type: memory` |
| documentation | the filename is `readme.md`, `index.md` or `overview.md` |
| skill reference docs | the file sits in a companion directory, or is one of the shapes that merely *carry* a `name:` |

### The frontmatter

```yaml
---
name: my-new-agent
description: >
  What this agent judges, and when to dispatch it.
model: sonnet
tools: ["Read", "Grep", "Glob"]
---
```

| Field | Shape | Effect |
|---|---|---|
| `name` | a string | the entry's identity. Must equal the filename stem. |
| `description` | a string | what search matches on, and what the model reads before dispatching. |
| `tools` | a list, a comma string, or a space string | the allow-list. Normalised to a JSON array by the index builder. |
| `model` | a string | the model to run on. |
| `mode` | `subagent` / `primary` | the OpenCode agent shape. |
| `permission` | a map | the OpenCode permission matrix (`edit`, `read`, `bash`). Not the same as `tools:` — see the note below. |

**`tools:` and `permission:` are different things.** `tools:` is an allow-list of
tool names. `permission:` is a matrix of capabilities. The OpenCode shape uses
`permission:`, and the installer maps between them when it emits a file:

```
Read | Grep | Glob             -> read:   allow
Write | Edit | NotebookEdit    -> edit:   allow | deny
Bash                          -> bash:   allow | deny
WebFetch | WebSearch          -> web:    ask
```

A default of `{edit: deny, read: allow, bash: deny}` is what the live OpenCode agent
files use.

### Two agents in this library have invalid YAML

`Explore` and `silent-failure-hunter` carry an unquoted `:` inside a plain scalar,
which PyYAML rejects. The library does not lose them: the reader falls back to the
line-oriented parser and recovers the fields individually, and the index records
`parse_ok: false` with the error. The TypeScript server does the same, and the two
must agree — that is what the cross-implementation agreement test checks.

**Write a block scalar and you never have to think about this.**

## 4. The agent-specific set

Some agents are dispatch targets rather than standalone tools: they expect parameters
(a scan root, a workspace clone, a comparison result path) that only an orchestrating
workflow supplies. Invoking one directly produces nonsense.

They are kept, but under `agents/_agent-specific/`, with a README explaining what
dispatches each one. The list is `AGENT_SPECIFIC` in `.build_library.py`:

```
scan-inventory  scan-loader     scan-researcher  scan-verifier
patch-generator  patch-verifier  explore          report_researcher
analyzer        comparator      grader           logs-reader
workflow-expert documentation-writer
```

Adding to this set is a deliberate statement that the entry is not standalone.

## 5. What the scanner writes

```
skills/<name>/              the copied directory, with every supporting file
agents/<name>.md            the copied agent file
agents/_agent-specific/     the dispatch targets, plus their README
.library_data.json          the machine-readable record of everything above
```

`.library_data.json` holds, per entry: the name, the description and where it came
from (`desc_source: yaml` or `body`), the title (the first `#` heading), the source
path on the machine, the copy count, whether it is locale-only, and the path inside
the library.

**Never edit `.library_data.json` by hand.** It is wiped and rewritten on every
build. The record of what an entry *is* belongs in the entry's own frontmatter.

## 6. The audit that will catch a mistake

`.verify_all.py` runs the whole suite. The checks that bite hardest here:

| Check | Catches |
|---|---|
| source integrity | a copy that differs from its source; a `name:` that drifted from the directory |
| supporting files | a `copytree` that silently dropped a file |
| agent classification | a file the ground-truth scan calls an agent that the library lacks |
| frontmatter correctness | a description that does not match the real YAML |
| catalogue coverage | an entry that is in the library but missing from the guide |
| the packs check | a pack that lost its reference files |

The ground-truth scan (`.audit_find.py`) is a **second implementation** written on
purpose to disagree: it uses `find` rather than `os.walk`, PyYAML rather than the
regex parser, and no filename heuristics at all. When it agrees with the builder, the
agreement means something.
