---
name: skill-library-adder
description: >
  Adds a new skill or a new agent to this library and to the MCP server that serves it.
  Use this whenever the user wants to add an entry to the Skills & Agents library, put a
  new skill or agent into the catalogue, register a hand-authored pack, make a new agent
  installable through the MCP server, or asks "how do I add X to the library". Trigger it
  for phrases like "add this skill to the library", "publish this agent", "make my
  new skill searchable", "register a pack", "why isn't my skill in the search results",
  or "how do I get this into the MCP server". It covers where a file must live so the
  scanner picks it up, the frontmatter each kind needs, the rules that decide whether a
  markdown file is treated as an agent, how to route the new entry through the task
  table and the domain table so search finds it, and the licence and credit rules that
  govern whether it can be published at all.
license: MIT
---

# Adding an entry to the library

This library is a **scan**, not a registry. There is no "add" button: content is found
by walking the machine, classified by a set of rules, and written out as `skills/` and
`agents/`. Everything that makes an entry appear — and everything that makes it
findable afterwards — follows from those rules.

This skill is the procedure. It has four parts, and skipping any one of them produces
an entry that exists but does not work.

| Part | What it decides | Reference |
|---|---|---|
| 1. Placement | whether the scanner sees the file at all | `references/scanner-rules.md` |
| 2. Frontmatter | what the index records about the entry | `references/scanner-rules.md` |
| 3. Routing | whether search finds it for the right query | `references/routing.md` |
| 4. Publishing | whether it can be published, and to whom it is credited | `references/publishing.md` |

`scripts/add_entry.py` does the mechanical half of part 1 and part 2: it scaffolds the
directory, writes a valid `SKILL.md` or agent file, and prints what is still left to do
by hand. It never edits the generated documents — those are rebuilt, not edited.

---

## 1. Decide what kind of entry this is

**A skill** is a directory with a `SKILL.md` at its root, plus whatever supporting
files it needs. It carries *method*: conventions, a procedure, a checklist. The user
loads it and follows it.

**An agent** is a single markdown file with a frontmatter block, carrying *judgement*:
a role, a perspective, a way of looking at a problem. The user dispatches it and it
does the work.

The test is what the model does with it. If the model needs to be told *how* to do
something, it is a skill. If the model needs to *be* something while doing it, it is an
agent. A reviewer's checklist is a skill; a reviewer is an agent.

If it is both, split it: the procedure goes in the skill, the judgement goes in the
agent, and the agent's description points at the skill.

## 2. Place the file

A skill goes at `<root>/<name>/SKILL.md`, where `<root>` is the directory the skill
belongs in — the library's own `skills/` for something written for it, or the harness
directory it came from (`~/.claude/skills/`, `~/.config/opencode/skills/`,
`~/.codex/.agents/skills/`) for something already installed.

An agent goes as a single file named `<name>.md`.

**The library's own packs are different.** A pack is a *hand-authored, self-contained*
directory at the top level of the library — `caveman-mode/`, `humanizer/`,
`skill-creator-plus/`. A pack carries its own reference files, is tier 1 in the search
ranking, is credited to this repository, and is published as this repository's own
work. Adding one is a bigger decision than adding a skill: read
`references/publishing.md` before you commit to it.

### Use the script for the mechanical part

```bash
# A new skill
python3 skill-library-adder/scripts/add_entry.py skill \
    --name my-new-skill \
    --description "What it does, and when to use it." \
    --root skills

# A new agent
python3 skill-library-adder/scripts/add_entry.py agent \
    --name my-new-agent \
    --description "What it judges, and when to dispatch it." \
    --root agents
```

The script writes the file, validates the frontmatter against the same rules the
scanner uses, and prints the remaining manual steps. It refuses to overwrite anything
unless you pass `--force`.

## 3. Get the frontmatter right

The scanner reads the frontmatter, and the index records it. For a skill:

```yaml
---
name: my-new-skill
description: >
  One or two sentences saying what it does and, more importantly, when to
  reach for it. The description is what search matches on.
---
```

For an agent:

```yaml
---
name: my-new-agent
description: >
  What this agent judges, and when to dispatch it.
model: sonnet
tools: ["Read", "Grep", "Glob"]
---
```

Three rules that are not obvious:

- **`name` must match the directory name** (for a skill) or the filename stem (for an
  agent). The library's own audit checks for drift between the two and fails the build.
- **The description is the whole routing surface.** Search does not read the body. A
  description that does not say *when* to use the entry will not be found when it is
  needed. Say what it does **and** the situations that should trigger it.
- **The description must be valid YAML.** A plain scalar with an unquoted `:` in it
  fails the parse — that is exactly what broke two agents in this library, and the
  reader falls back to a line-oriented parser that loses fields. Use a `>` block
  scalar, as above, and the problem cannot arise.

Full detail, including the fields each harness understands and the exact detection
rules: `references/scanner-rules.md`.

## 4. Make it findable

An entry that is scanned but never returned by a search is an entry nobody uses. Three
things decide whether it surfaces:

1. **Its domain** — from `mcp/build/domains.py`. The domain is a keyword match on the
   name, first-match-wins. A skill whose name matches no keyword lands in "Other /
   uncategorised" and is ranked by tier 3.
2. **Its tier** — from `mcp/build/tiering.py`. Tier 1 is the packs and the agents,
   tier 2 is the ten core domains, tier 3 is everything else. Tier is a ranking bias,
   never a filter: a tier 3 skill is still returned, it just has to score higher.
3. **The task table** — `mcp/build/tasks.py`. This is the strongest router in the
   system: a query shaped like a task row ("write a REST API") fires that row, and
   every member of the row gets a large bonus. A row naming the new entry is the
   difference between "found on the fifth page" and "found".

So: add the entry to the domain table if its name matches no existing keyword, and
add a task row if there is a task-shaped question it answers. The rows are the
curation; without them the search falls back to name and description matching, which
is much weaker.

Details and the worked examples: `references/routing.md`.

## 5. Rebuild and verify

The library is generated. After adding an entry, rebuild and let the verification
suite prove it:

```bash
./run.sh          # the logged build: every step, with snapshots and validation
```

`run.sh` runs the scanner, the guide builder, the report builder, the index builder,
the TypeScript build and all thirteen verification steps, logging each one under
`logs/<run_id>/` with a snapshot of every file it touched. If a step fails, the log
names what broke and `rollback.sh <run_id> --step N` puts that step back.

Two checks will fail if you skip the routing work:

- the guide's catalogue must list every skill and agent in the library
- the index's tier counts must sum to the entry count, and tier 1 must be exactly the
  published packs plus every agent

## 6. Publish it (or find out why you cannot)

Publishing is **licence-driven, not taste-driven**. An entry is published only if its
own licence permits redistribution; anything else is left out, and the reason is
recorded rather than hidden. The public tree is then gated twice: a licence gate that
compares the filesystem against the verdicts, and a leak gate that proves no absolute
home path survived the copy.

An entry written for this library is MIT and is credited to this repository. An entry
copied from somewhere else carries that author's licence and that author's credit —
and if their licence forbids redistribution, it stays out of the public tree while
remaining fully usable locally.

The full procedure, the licence rules, the provenance resolution order and what to do
when an entry cannot be published: `references/publishing.md`.

---

## The checklist

Before you call it done:

- [ ] The file is where the scanner will find it, with the right name
- [ ] `name` matches the directory or filename
- [ ] The description says what it does **and** when to use it
- [ ] The frontmatter is valid YAML (a `>` block scalar for a long description)
- [ ] The entry has a domain — add a keyword to `mcp/build/domains.py` if it has none
- [ ] A task row names it, if there is a task-shaped question it answers
- [ ] `./run.sh` passes, and the new entry is in the guide and in the index
- [ ] `search_library` returns it for the query you expect
- [ ] The licence is known, and the credits say who wrote it

## What this skill deliberately does not do

- It does not edit `ROUTING_GUIDE.md` or `SKILLS_AND_AGENTS_REPORT.md`. Those are
  generated; editing them is undone by the next build.
- It does not touch `.library_data.json`. That is the scanner's output.
- It does not decide licences. It resolves them, from the source's own statements.
- It does not install anything into a harness. That is the `install_skills` tool, and
  it is a separate decision with its own safety rules.
