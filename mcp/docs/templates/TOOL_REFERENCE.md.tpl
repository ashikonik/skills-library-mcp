# Tool reference

Eight tools. Five read, three write.

| # | Tool | Kind | Writes? |
|---|---|---|---|
| 1 | `search_library` | read | no |
| 2 | `get_skill` | read | no |
| 3 | `get_agent` | read | no |
| 4 | `get_skill_bundle` | read | no |
| 5 | `list_library` | read | no |
| 6 | `install_skills` | write | yes |
| 7 | `install_agents` | write | yes |
| 8 | `uninstall_skills` | write | yes (destructive) |

Every tool declares `title`, `inputSchema` and `annotations`
(`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`).

Descriptions are written as **scope statements**, not directives. A tool
description says what the tool covers and what it does *not* cover — it
does not tell the model what to do next. That keeps the descriptions
honest when a client renders them as reference material rather than
instructions.

---

## 1. `search_library`

Rank skills and agents by relevance to a query. Returns scored
candidates with the terms each matched on. Covers all {n_skills} skills and
{n_agents} agents. Not covered by `get_skill`, which returns one document in
full.

```jsonc
{
  "query": "competition math proof",     // required, 1–500 chars
  "limit": 10,                            // 1–50, default 10
  "kind": "skill",                        // "skill" | "agent"
  "tier": 1,                              // 1 | 2 | 3
  "domain": "Testing & QA",
  "include_body": false                   // default false
}
```

```jsonc
{
  "query": "accessibility audit WCAG",
  "total_matched": 6,
  "returned": 3,
  "truncated": true,
  "note": "Showing 3 of 6 matches. Refine the query to narrow down.",
  "results": [
    {
      "id": "skill:accessibility",
      "kind": "skill",
      "name": "accessibility",
      "description": "…",
      "tier": 3,
      "domain": "Frontend/UI & accessibility",
      "score": 22.75,
      "matched_on": ["accessibility", "audit", "wcag"],
      "path": "skills/accessibility"
    }
  ]
}
```

`matched_on` is the reason a result matched. The difference between
"here are ten things" and "here is the one, matched on `wcag`".

`truncated` is set when `total_matched > returned`. The `note` says so
in words.

**Ids are namespaced.** `skill:api-design` and `agent:api-design` are
different documents — `claude-security` exists as *both* a skill and an
agent. A bare name is accepted too, but resolves ambiguously in that
one case.

### How ranking works

Purely lexical — no embeddings, no network, no model. The score is:

| Signal | Weight |
|---|---|
| name token match | `3.0 × idf` |
| name token is a prefix/substring of a name token | `1.5 × idf` |
| description token match | `1.0 × idf` |
| query bigram matches a name bigram | `6.0` |
| matches a curated `metadata.promptSignals` phrase | `8.0 × idf` |
| matches a task-type row, strictly (60 % of the row's tokens) | `25.0` |
| matches a task-type row's content, at the query's head noun | `16.0` |
| matches a task-type row's content (the row's verb dropped) | `8.0` |
| is a task row's *later* entry, on a strict match | `−3.0` |
| tier 1 / tier 2 / tier 3 bias | `+1.0` / `+0.25` / `0` |
| is an agent | `+0.5` |

`idf(t) = ln(1 + N / df(t))`, over N = the number of entries in the
index.

**Tiers bias ranking; they never filter.** Every skill and agent stays
searchable at every tier. The tier bias is multiplied by
`(1 − name_exact_hit)`, so it can never override a direct name match,
and its maximum (1.0) is well below a single idf contribution
(≈3.0–6.0) — it only breaks ties among weak, description-only matches.

Two rules cut the noise before the limits apply:

- **Token coverage.** An entry must match two thirds of the query's
  *distinctive* tokens — those appearing in under 1.8 % of the corpus.
  A common word like "write" carries no information about which entry
  the query wants, so requiring it filters on luck rather than
  relevance.
- **Task rows.** A hand-written row of the {n_tasks}-row task index fires when
  the query has 60 % of the row's tokens, or the row's *content* (its
  verb dropped). A content match counts for more when the token is the
  query's **head** — what the query is *about*, not the context it
  mentions. "write a REST API" is about an API, so the "Build an API"
  row fires; "add authentication to an api" is about authentication, so
  it does not.

### The task table's curation reaches the ranking

The task table is hand-written, and it encodes a preference: a row
lists its **primary** entry first, and its note says which one that is
("`api-design` covers resource naming, status codes, pagination…",
"Prefer the hand-authored `skill-creator-plus` pack"). Two pieces of
that curation used to be lost on the way into the index, and both are
now preserved:

1. **The order.** The index keeps each row's order rather than sorting
   it, so position 0 is the row's primary entry.
2. **The note.** {n_noted_rows} of the {n_tasks} rows name an entry their own lists omit
   — "use `architect`", "pair with `silent-failure-hunter`" — and in
   every case the note is the only place that preference is written
   down. Those entries are promoted to the front of their row.

On a strict match, a row's later members are demoted by `3.0`. The
demotion is deliberate rather than a promotion of position 0: the
relevance floor is a fraction of the *top* score, so raising the
ceiling can evict a weaker but relevant entry from the bottom of the
list. Measured over the labelled query set, demoting lifts the
rank-1 and rank-3 counts while evicting nothing.

The content branch is left alone. A content match means the query named
the row's *object* — "write a REST API" reaches "Build an API" — not
that it asked for that specific task, so the row's members stay on
equal footing there.


Results are filtered by a **relevance floor** (drop anything below
`0.25 × topScore`), a **score threshold** (`score > 0`), and a **hard
cap** (`limit`, default 10, max 50). A query with no library match
returns an empty result set, not the whole library.

Ties break deterministically: score desc → tier asc → skill before
agent → shorter name → lexicographic name. Two independent
implementations produce byte-identical result lists.

Scores are compared with a tolerance of 1e-6 rather than for exact
equality. Two entries that match the same query tokens score the same
sum, but the terms arrive in a different order and the floating-point
addition lands on a different last bit — a difference of about 1e-15.
Comparing the raw doubles let that noise decide the order and the
tie-break above never ran, so the ranking of genuinely tied entries
changed every time the corpus grew by one entry. The smallest real
score difference the weights can produce is an idf step, several
hundredths, so the tolerance only groups together scores that are the
same score.

---

## 2. `get_skill`

Returns one skill: its `SKILL.md` body, parsed frontmatter, and the
manifest of its supporting files. Accepts a namespaced id
(`skill:tdd-workflow`) or a bare name. Not covered by
`get_skill_bundle`, which returns the supporting files themselves.

```jsonc
{ "id": "skill:math-olympiad", "include_body": true }
```

Returns the body, the frontmatter (with `tools` normalised to a real
JSON array), the bundle manifest (`file_count`, `total_bytes`, the file
list, and how many references resolve), and the skill's tier, domain
and tokens.

`include_body` defaults to `true`. Set it `false` for metadata only.

---

## 3. `get_agent`

Returns one agent: its definition body and parsed frontmatter,
including its tool allow-list and model. Accepts a namespaced id
(`agent:code-reviewer`) or a bare name. Not covered by
`install_agents`, which writes it into a harness.

```jsonc
{ "id": "agent:code-reviewer", "include_held_aside": false }
```

`include_held_aside` reaches the 14 agents that are held aside — the
ones whose names collide with a skill's, or that are too ambiguous to
classify automatically. With the flag, they are returned like any
other agent, marked `held_aside: true`.

---

## 4. `get_skill_bundle`

Returns a skill's supporting files. With no `files` argument it
returns the manifest only — paths, sizes and which references resolve.
With `files` it returns those files' contents, up to a byte cap. Not
covered by `get_skill`, which returns the `SKILL.md` body.

```jsonc
{
  "id": "skill:document-builder",
  "files": ["templates/report.md"],   // optional, max 50
  "max_bytes": 200000                 // default 200 KB, hard cap 2 MB
}
```

The largest bundle in the library is 7.1 MB, so the cap matters. Ask
for specific files, not the whole bundle.

---

## 5. `list_library`

Lists the library's structure: its domains, tiers, the seven hand-authored
packs, the task-type index, or overall statistics. Not covered by
`search_library`, which ranks entries by relevance to a query.

```jsonc
{ "section": "stats" }   // domains | tiers | packs | tasks | stats
```

| Section | Returns |
|---|---|
| `stats` | counts, tier distribution, domain and task counts, index metadata |
| `domains` | all {n_domains} domains with their skill lists and tier |
| `tiers` | tier-1 skills (the 7 packs), tier-1 agents, the tier distribution |
| `packs` | the seven hand-authored packs |
| `tasks` | the {n_tasks}-row task-type index |

---

## 6. `install_skills`

Installs skills into a coding harness so they auto-activate. Writes a
symlink into the library by default, so the installed skill stays in
sync with the source. Dry run unless `apply` is true. Not covered by
`search_library`, which finds candidates but writes nothing.

```jsonc
{
  "harness": "puku-cli",   // required
  "ids": ["skill:tdd-workflow"],  // required, 1–50
  "mode": "symlink",       // "symlink" | "copy", default "symlink"
  "tier": 1,               // optional: install a whole tier
  "apply": false,          // default false — a dry run
  "overwrite": false       // default false
}
```

**`apply` defaults to `false`.** A dry run returns the plan and writes
nothing at all. This is the single most important safety property of
the server, and it is enforced in code, not by convention.

### What each harness receives

| Harness | Target | Skill frontmatter |
|---|---|---|
| `claude-code` | `~/.claude/skills/<n>/` | `name`, `description`, `allowed-tools` (only when non-empty) |
| `codex` | `~/.codex/skills/<n>/` | `name`, `description` |
| `codex-agents` | `~/.codex/.agents/skills/<n>/` | same + `agents/openai.yaml` sidecar |
| `opencode` | `~/.config/opencode/skills/<n>/` | `name`, `description` |
| `cline` | `~/.clinerules/NN-<n>.md` | plain markdown, **no frontmatter** |
| `puku-cli` | `~/.puku-cli/skills/<n>/` | `name`, `description` |
| `agentsmd` | `<project>/AGENTS.md` | appended marked section, plain markdown |

Cline has no skills mechanism, so its file is plain markdown — a
`---` block there would be read as content.

### Write safety

Every one of these is enforced, and each has a test:

- `apply` defaults to **false** → a dry run writes nothing.
- Writes are confined to a fixed whitelist of harness directories.
  Anything outside is refused with the resolved path.
- `symlink` mode always points **into** the library, never out.
- `overwrite` defaults to **false** → existing paths are reported as
  skipped, not clobbered.
- `~/.claude/skills/learned/` is harness-managed and explicitly
  excluded.
- `install_agents` for `cline` returns an explicit "not supported"
  error rather than silently doing nothing.

Keys the target harness cannot parse are dropped rather than written —
and the dropped keys are reported in the result under `dropped_keys`,
so nothing is swallowed silently.

---

## 7. `install_agents`

Installs agent definitions into a coding harness. Each harness receives
the frontmatter dialect it expects. Dry run unless `apply` is true. Not
covered by `get_agent`, which returns a definition without writing it.

```jsonc
{
  "harness": "opencode",
  "ids": ["agent:code-reviewer"],
  "mode": "copy",          // default "copy" — agents differ per harness
  "apply": false,
  "overwrite": false
}
```

`mode` defaults to `copy` here, unlike skills. An agent's frontmatter
is rewritten per harness, so a symlink would install the *source*
frontmatter — the wrong dialect — rather than the emitted one.

### The dialects differ

| Harness | Agent frontmatter |
|---|---|
| `claude-code` | `name`, `description`, `tools: [...]`, `model:` |
| `opencode` | `description`, `mode: subagent\|primary`, `permission:` map |
| `codex` | `name`, `description` |
| `agentsmd` | `## <name>` + prose |
| `cline` | not supported |

**OpenCode agents take `permission:`, not `tools:`.** The two are
different shapes — one is an allow-list, the other a permission matrix
— so a translation is required:

```
Read, Grep, Glob          → read:   allow | ask
Write, Edit, NotebookEdit → edit:   allow | ask
Bash                      → bash:   allow | ask
WebFetch, WebSearch       → web:    ask
default                   → { edit: deny, read: allow, bash: deny }
```

The mapping was verified against the live
`~/.config/opencode/agents/architect.md`, which uses
`mode: subagent` and
`permission: {edit: deny, read: allow, bash: allow}`.

---

## 8. `uninstall_skills`

Removes skills this server installed from a harness. Refuses to remove
a symlink that points outside the library. Dry run unless `apply` is
true. Not covered by `install_skills`, which installs rather than
removes.

```jsonc
{
  "harness": "puku-cli",
  "names": ["tdd-workflow"],   // 1–50
  "apply": false
}
```

Takes **names**, not ids — the thing on disk is named by its skill
name.

The path removed is the skill **directory** (`<dir>/<name>`), not the
`SKILL.md` inside it. That is where a symlink install puts the link,
and removing the link is what takes the link away — removing the file
*inside* it would delete the library's own copy.

`AGENTS.md` has no path of its own to remove: it is a shared file, so
the tool refuses with an explanation rather than deleting the whole
thing. Remove the skill's marked section instead.

`destructiveHint` is `true` for this tool and `false` for the other
two. A client that honours the hint will confirm before calling it.

---

## Error contract

Errors come back as `isError: true` with a message that names the next
step. They are never transport crashes.

| Situation | Message |
|---|---|
| Unknown skill id | `Skill 'skill:X' not found. Use search_library to find valid ids.` |
| Unknown agent id | `Agent 'agent:X' not found. Use search_library to find valid ids, or pass include_held_aside=true.` |
| Unknown bundle path | `'foo.md' is not in the bundle of 'skill:X'. Available paths are listed in the manifest.` |
| Over the byte cap | `Requested files total 3,400,000 bytes; max_bytes is 200,000. The manifest is returned instead — request specific files.` |
| Target exists | the target's `status` is `skipped` and its `reason` is `target already exists; pass overwrite=true to replace it` |
| Outside the whitelist | `Refusing to write outside the harness directories: /resolved/path` |
| Harness-managed dir | `Refusing to write into the harness-managed directory: /resolved/path` |
| Uninstall outside the library | `Refusing to remove /path: it is a symlink pointing outside the library (/target).` |
| Unsupported harness/kind | `install_agents is not supported for harness 'cline' — Cline has no agent mechanism.` |
| Index missing | `mcp/data/index.json not found. Run scripts/rebuild.sh to build it.` |

Every message names what to do next, or what to ask for instead. Errors
that concern one target out of several are reported **per target**, in
that target's `reason` field, so a partial failure is visible instead
of collapsing the whole batch into one message.

A dry run returns the same shape as a real one, with `written: 0` and
the note `Dry run — nothing was written. N target(s) planned.`
