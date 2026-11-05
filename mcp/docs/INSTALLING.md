# Installing skills and agents into a harness

The server can *find* a skill and *show* it to you. Installing is the
other half: it puts the skill where the harness looks for it, so the
harness activates it on its own.

Two layers, and they do different things:

| Layer | What it does | How it activates |
|---|---|---|
| **Search** | the agent pulls the skill's content into its context | the agent decides to use it, mid-task |
| **Install** | the skill is written into the harness's own directory | the harness loads it automatically |

Search is enough for most work. Install is for the skills you want
*always* available — the ones you would otherwise re-fetch every
session.

---

## The safety model

Every write tool is a **dry run unless `apply` is true**. This is
enforced in code, in both implementations, and it is tested.

```jsonc
// writes nothing, returns the plan
{ "harness": "puku-cli", "ids": ["skill:tdd-workflow"] }

// writes
{ "harness": "puku-cli", "ids": ["skill:tdd-workflow"], "apply": true }
```

A dry run returns the same shape as a real run — the same `targets`
array, the same paths — with `written: 0` and a note saying so. You
can see exactly what would happen before it happens.

### What the server will not do

| Refusal | Why |
|---|---|
| Write outside the harness whitelist | a bad `harness` value must not become a bad path |
| Write into `~/.claude/skills/learned/` | that directory is harness-managed; the harness owns it |
| Follow a symlink out of the library | an install must point *into* the library, never out |
| Overwrite an existing target | `overwrite` defaults to `false`; existing paths are reported, not clobbered |
| Install agents into Cline | Cline has no agent mechanism |

The whitelist:

```
~/.claude/skills        ~/.claude/agents
~/.codex/skills         ~/.codex/.agents/skills      ~/.codex/agents
~/.config/opencode/skills   ~/.config/opencode/agents
~/.clinerules
~/.puku-cli/skills
<project>/AGENTS.md
```

---

## Symlink or copy

**`symlink` (the default for skills)** creates a link into the library.
The link is at the **skill directory**, not at the `SKILL.md` inside
it:

```
~/.puku-cli/skills/tdd-workflow
  -> <library>/skills/tdd-workflow
```

The directory is what the harness looks for, and linking the whole
thing keeps the skill's supporting files — its `references/`, its
`scripts/`, its `agents/` — in sync too. A link at the `SKILL.md`
level would leave those behind.

The installed skill stays in sync with the source automatically. Edit
the library and the installed copy changes with it. Nothing is
duplicated.

**`copy`** writes a real file. Use it when:

- the target harness rewrites the file (some do, on first run);
- you want the install to be independent of the library;
- you are installing to a machine that does not have the library.

**`copy` (the default for agents)** — because an agent's frontmatter is
*rewritten* per harness. A symlink would install the source
frontmatter, which is the wrong dialect for the target.

---

## What each harness receives

The frontmatter dialects differ, and the wrong one breaks the target's
parser. Unknown keys are dropped rather than written — and the dropped
keys are reported in `dropped_keys`, so nothing is swallowed silently.

### Claude Code — skills

```yaml
---
name: tdd-workflow
description: Write the test first, watch it fail, then make it pass.
allowed-tools: [Read, Grep]
---
```

`allowed-tools` is included only when the source skill actually has
tools. Claude Code skills have no `tools:` field — that is an agent
field.

### Claude Code — agents

```yaml
---
name: code-reviewer
description: Reviews a diff for correctness, clarity and risk.
tools: [Read, Grep, Glob]
model: opus
---
```

### OpenCode — agents

```yaml
---
description: Reviews a diff for correctness, clarity and risk.
mode: subagent
permission:
  edit: deny
  read: allow
  bash: deny
---
```

OpenCode takes a **permission matrix**, not a tool allow-list. The two
are translated:

```
Read, Grep, Glob          -> read: allow | ask
Write, Edit, NotebookEdit -> edit: allow | ask
Bash                      -> bash: allow | ask
WebFetch, WebSearch       -> web:  ask
default                   -> { edit: deny, read: allow, bash: deny }
```

This shape was verified against the live
`~/.config/opencode/agents/architect.md`.

### Codex — skills

```yaml
---
name: tdd-workflow
description: Write the test first, watch it fail, then make it pass.
---
```

### Codex agents — skills plus a sidecar

```yaml
# ~/.codex/.agents/skills/<name>/SKILL.md
---
name: tdd-workflow
description: ...
---
```

```yaml
# ~/.codex/.agents/skills/<name>/agents/openai.yaml
interface:
  display_name: tdd-workflow
  short_description: Write the test first, watch it fail, then make it pass.
```

> Codex has **two** separate skill surfaces: `~/.codex/skills/` and
> `~/.codex/.agents/skills/`. They are different directories with
> different rules, and installing to the wrong one is a silent no-op.
> `~/.codex/AGENTS.md` says skills auto-load from `.agents/skills/`.
> The `codex` and `codex-agents` harness values exist to make the
> choice explicit.

### Cline — skills

Cline has no skills mechanism, so its file is plain markdown with no
frontmatter at all:

```markdown
# tdd-workflow

Write the test first, watch it fail, then make it pass.
```

A `---` block there would be read as content.

### puku-cli — skills

```yaml
---
name: tdd-workflow
description: Write the test first, watch it fail, then make it pass.
---
```

Written to `~/.puku-cli/skills/<name>/`, which is the path the
library's own README names as the activation path.

### AGENTS.md — the fallback

`AGENTS.md` is one shared file that many skills live in, so it is not
written the way the other targets are. Each skill gets its own
**marked section**, and the file is appended to:

```markdown
<!-- skills-library:tdd-workflow -->
## tdd-workflow

Write the test first, watch it fail, then make it pass.

…the rest of the skill's body…

<!-- skills-library:accessibility -->
## accessibility

Audit a UI against WCAG 2.2 Level AA.
```

The marker is an HTML comment, so it is invisible in the rendered file
but unambiguous on disk. It is what makes the file safe to share:

- a second skill **appends** its section — it does not overwrite the
  first;
- installing the same skill again is **skipped**, not duplicated;
- `overwrite: true` replaces **only that skill's section**, leaving
  every other skill's section intact.

The content is plain markdown with no frontmatter. An `AGENTS.md` is
read as a document, not parsed as a skill.

---

## The `tier` parameter

`install_skills` accepts a tier instead of a list of ids:

```jsonc
{ "harness": "puku-cli", "tier": 1 }
```

| Tier | Contents | Count |
|---|---|---|
| 1 | the seven hand-authored packs | 7 |
| 2 | the ten core domains | 269 |
| 3 | everything else | 701 |

A tier install is capped at 50 targets per call — the same cap an
explicit `ids` list has. When the tier is bigger than the cap, the
truncation is **reported**, not silent:

> Tier 3 holds 701 skills; only the first 50 are planned. Install the
> rest by id.

Tier 1 is the one worth installing wholesale: six skills, curated,
each a bundle of real material.

---

## Uninstalling

```jsonc
{ "harness": "puku-cli", "names": ["tdd-workflow"], "apply": true }
```

Takes **names**, not ids — the thing on disk is named by its skill
name.

The path removed is the skill **directory** (`<dir>/<name>`), which is
where a symlink install puts the link. Removing the link is what
takes the link away — removing the file *inside* it would delete the
library's own copy, which is the bug this rule exists to prevent.

The server refuses to remove a symlink that points outside the library.
If a target is not a symlink into the library, it is reported rather
than deleted, because it may be something the user put there.

`AGENTS.md` has no path of its own to remove — it is one shared file.
The tool refuses with an explanation rather than deleting the whole
thing. Remove the skill's marked section instead.
