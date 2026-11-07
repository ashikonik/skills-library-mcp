# Vendored upstream: mattpocock/skills

This directory is a clone of [mattpocock/skills](https://github.com/mattpocock/skills),
held in the library so the upstream's licence travels with its content and so the
attribution in `CREDITS.md` can be checked against a real file.

| | |
|---|---|
| Upstream | `https://github.com/mattpocock/skills` |
| Commit | `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` |
| Committed | 2026-10-31 |
| Author | Matt Pocock — <https://www.aihero.dev> |
| Licence | MIT — © 2026 Matt Pocock (see `LICENSE` in this directory) |
| Plugin | `mattpocock-skills`, version 1.3.2 |

The clone's own `.git` is removed when this tree is assembled for publication, so
the published repository does not carry a nested repository. The commit above is
the pin.

## What was changed, and why

Two changes were made to the clone. Everything else is upstream's own work,
byte for byte.

### 1. `code-review` is now `mattpocock-code-review`

The upstream ships a skill called `code-review`: a two-axis review of the diff
between `HEAD` and a fixed point, along the axes *Standards* and *Spec*. This
library already had a skill called `code-review` — the CodeRabbit skill, which
runs the CodeRabbit CLI and summarises its findings. They are different skills
that share a name, and the scanner's rule for a duplicate name is to keep one and
skip the other, which would have silently dropped one of them.

The upstream is explicit about this case. In
[`.out-of-scope/harness-name-collisions.md`](https://github.com/mattpocock/skills/blob/main/.out-of-scope/harness-name-collisions.md)
it says:

> Skill names are not changed because a harness ships a built-in command or skill
> with the same name (`/prototype`, `/research`, `/code-review`, and so on).
> Requests to rename a skill, or add an alias, to avoid a collision are out of
> scope.

and names namespaced invocation as the way through. This library is one flat
namespace, so the namespace is the directory and the frontmatter `name:`:
`mattpocock-code-review`. Both skills stay in the catalogue, both are findable,
and the upstream's refusal to rename is honoured rather than overridden.

The upstream's own name is preserved in the credit: the entry is attributed to
Matt Pocock and the `mattpocock-skills` repository, not to this library.

### 2. `in-progress/` and `misc/` moved to `not-shipped/`

The upstream ships 27 of its 39 skills in the `mattpocock-skills` plugin. The
other 12 are in two buckets it does not publish, and the plugin manifest at
`.claude-plugin/plugin.json` says so — it lists exactly 27 paths.

The upstream's [`SCOPE.md`](https://github.com/mattpocock/skills/blob/main/SCOPE.md)
describes them:

> - **`engineering/`, `productivity/`, `in-progress/`**: the bar above.
> - **`misc/`**: frozen and unmaintained. Every issue is closed.

and [`.out-of-scope/frozen-misc-skills.md`](https://github.com/mattpocock/skills/blob/main/.out-of-scope/frozen-misc-skills.md)
is blunter:

> They aren't promoted: they don't ship in the Claude Code plugin, they have no
> docs page, and I'm not running them day to day, so I can't tell whether a fix
> is right or notice when one breaks something else.

So the two buckets moved here, unchanged, to `not-shipped/in-progress/` and
`not-shipped/misc/`. The scanner skips that directory (see `NOT_SHIPPED` in
`.build_library.py`), so these skills stay in the tree — readable, auditable, and
one `git mv` away from being published — without being entries in the library.

`skills/deprecated/` is left where the upstream put it. It is empty: the upstream
says "a retired skill is deleted".

This is the upstream's own curation, not a judgement made here. If the upstream
promotes one of these later, moving it back is a one-line change in
`.claude-plugin/plugin.json` and a `git mv`.

## What was not changed

The skill text, the `agents/openai.yaml` companions, the docs pages, the
`CHANGELOG.md`, the `.out-of-scope/` notes and the `LICENSE` are upstream's, as
they are.

## Licence

MIT — © 2026 Matt Pocock. The `LICENSE` file in this directory is the
authoritative statement, and it rides along into the published tree. The
upstream's terms permit redistribution, so these entries are published on the
strength of their own licence rather than at the repository owner's instruction.
