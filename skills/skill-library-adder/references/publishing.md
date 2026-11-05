# Publishing: licences, credits and gates

The public repository is not a copy of the local library. It is a **filtered** copy:
only entries whose own licence permits redistribution are in it, each credited to its
real author, and the whole tree is checked twice before it is pushed.

This is the reference for the publishing half of adding an entry.

---

## 1. The rule

> An entry is published only if its **own** licence permits redistribution.

Not the licence of the repository, not the licence of the directory it sits in, not a
guess from the file's shape. The entry's own licence, resolved from the statements
the author actually made.

A licence that permits redistribution:

```
MIT   Apache-2.0   BSD   ISC   MPL   CC-BY
```

Anything else — Proprietary, UNLICENSED, a `LicenseRef`, a custom "copyright and
warranty" clause, or **no licence stated anywhere** — is `restricted`. Publishing
material whose licence forbids it would grant rights the author did not grant, so
those entries stay out of the public tree. They remain fully usable locally; the
filter is about redistribution, not about quality.

**GPL is deliberately absent from the permissive list.** It is copyleft, and a
copyleft skill redistributed inside an MIT repository would make the whole
repository GPL.

## 2. How the licence is resolved

`mcp/build/provenance.py` resolves each entry's licence by, in order:

1. **the container's manifest** — `license` in `plugin.json`. The Codex plugin cache
   and the plugin temp directory both carry one per plugin, and the manifest is the
   authoritative statement of provenance.
2. **the nearest `LICENSE` file walking up** from the entry's own directory. The
   walk starts at the entry itself: a skill that carries its own `LICENSE.txt` is
   licensed by it, and starting at the parent would miss exactly that file.
3. **a sibling `*.dist-info`** — the installed package's metadata directory, which
   sits beside the package rather than inside it. `License-Expression` in METADATA
   is used when there is no licence file.
4. **the entry's own frontmatter** `license:` field.

The source of the answer is recorded (`manifest`, `license file`, `dist-info`,
`frontmatter`) so a decision can be audited rather than taken on trust.

### The container layouts

The resolver walks *up* from the entry's source path and takes the **nearest**
manifest, because one marketplace holds dozens of plugins, each with its own author
and licence, and keying by the tree's root collapses them into whichever plugin was
found first. That is not hypothetical: it credited 51 Anthropic skills to "Asana",
because the marketplace's `asana` plugin was found first.

Three layouts are handled:

| Layout | Shape |
|---|---|
| flat plugin directory | `<plugin>/.codex-plugin/plugin.json` |
| versioned cache | `<plugin>/<version>/.codex-plugin/plugin.json` |
| marketplace | `<marketplace>/<plugin>/.claude-plugin/plugin.json` — plugins nested two levels down |

`glob` is deliberately not used for this: `**` does not traverse dot-directories,
and the manifest lives in `.codex-plugin/`, so a glob would find nothing and every
plugin would look unlicensed.

### The marketplace's own terms

A plugin that names no author belongs to whoever owns the marketplace it sits in,
and takes the marketplace's licence. Anthropic's directory says "Anthropic" in
`marketplace.json` and states MIT in its `LICENSE`.

## 3. The four verdicts

| Verdict | Meaning | Published? |
|---|---|---|
| `redistributable` | the licence permits redistribution | yes |
| `restricted` | the licence forbids it, or none is stated | no |
| `personal` | the maintainer's own project files — they leak machine paths | no |
| `fixture` | test input that happens to look like a skill | no |

`personal` and `fixture` are exclusions *regardless of licence*. A fixture is
placeholder content — "alpha", "beta", "minimal-plugin-skill" — and publishing it
would put meaningless entries in the catalogue and odd author names in the credits.

## 4. The library's own packs

The packs at the top level of the library — `caveman-mode`, `document-builder`,
`humanizer`, `latex-doctor`, `research-partner`, `skill-creator-plus`,
`skill-library-adder` — are the maintainer's own work. They are MIT (except
`skill-creator-plus`, which is Apache-2.0 by its own `LICENSE.txt`), and they are
credited to this repository.

**A pack's own LICENSE file wins over the manifest.** The file is the author's own
statement of terms, and a manifest that disagreed with it would be the manifest
lying.

### The restricted pack

`document-builder` is the maintainer's own work, but it **vendors Anthropic's
docx/pptx/xlsx/pdf skills** under `vendor/`, and their terms forbid
redistribution. So the pack as a whole cannot be published, and the manifest says
so:

```json
{
  "name": "document-builder",
  "restricted": true,
  "restricted_reason": "It bundles Anthropic's docx, pptx, xlsx and pdf skills under `vendor/`, and their terms forbid redistribution."
}
```

Saying so is more honest than shipping half of it.

### Registering a new pack

One file: `mcp/build/packs.json`.

```json
{
  "name": "my-pack",
  "license": "MIT",
  "min_files": 4,
  "summary": "One line, for the tables.",
  "detail": "The longer 'what it does' cell.",
  "why": "The 'why it is better than the marketplace equivalent' cell."
}
```

Everything else follows from that one edit:

| Consumer | What it does with the pack |
|---|---|
| `mcp/build/tiering.py` | the pack is tier 1 — the first thing to reach for |
| `mcp/build/provenance.py` | an own pack is MIT and credited to this repository |
| `.verify_packs.py` | the pack exists, is mirrored under `skills/`, and holds at least `min_files` files |
| `.build_guide.py` | the guide's "Standalone Packs" table |
| `.gen_report.py` | the report's "Curated standalone packs" table |
| `mcp/build/write_credits.py` | the credits' list of skills written for this library |

It used to be a literal in six files, so a new pack was tier 3 unless someone
remembered the tiering file, and a pack that no verifier knew about was a pack
nobody would notice breaking.

**A pack must be mirrored under `skills/`.** The verifier checks that the copy
under `skills/<name>/` has the same file count as the top-level directory. The
scanner does that on its own — a top-level directory with a `SKILL.md` is picked up
as a skill — but the check is there to catch a copy that went wrong.

## 5. The two gates

The public tree is assembled by copying, so it is checked against the filesystem
rather than against the assembler's own bookkeeping.

### The licence gate

Every entry marked `restricted`, `personal` or `fixture` must be **absent** from the
tree, and every entry marked `redistributable` must be **present**.

This compares the disk against the verdicts. Comparing the index instead would
prove nothing: the index is built from the same table the filter used, so it would
agree by construction. A copy step that went wrong once would ship content whose
licence forbids it, and the index's count would still look right.

### The leak gate

No absolute home path may survive the copy. The scanner flags exactly one thing:
**the builder's home directory**. It is passed in, so the same scanner works on any
machine and in CI, where the home is a temporary directory.

Third-party example paths are left alone — `/home/alice/`, `/Users/benlesh/` are the
upstream authors' own examples, and rewriting them would corrupt the content being
credited.

The leak can arrive from three places:

- a **generated artefact** — the index's `abs_path`, the provenance table's
  `source`, the run manifest's `library_root`;
- a **hand-written document** — a registration snippet with the author's absolute
  entrypoint;
- a **copied file** — a bundled note that mentions a path.

This is why the index records the path *inside* the library (`skills/foo`) rather
than the absolute one it happens to sit at, and why the public `.library_data.json`
replaces `source` with a container label (`plugin:zotero`, `marketplace:claude-plugins-official`,
`ecc`, `this-library`).

## 6. The credits

`CREDITS.md` is generated from the provenance table, never written by hand. A
hand-written credits file drifts the moment the library changes; a generated one
cannot.

Every published entry is attributed to its real upstream owner, with the licence it
carries and the repository it came from.

| Owner | What it means |
|---|---|
| `This library (hand-authored)` | this repository's own work — the packs |
| `plugin:<name>` | from a plugin's own manifest |
| `marketplace:<name>` | from a marketplace, credited to the marketplace's owner |
| `ecc` | from the ECC project |
| `codex-cache:<name>` | from the Codex plugin cache |
| `opencode-installed` / `ecc-installed` | from a harness's own install directory |
| `vscode-copilot-chat` | from the VS Code extension |
| `local-project:<name>` | from a project directory on the machine |

Two rules the credits hold to:

- **The repository is only printed when every entry in the group agrees on it.**
  An entry that names no repository is not a neutral abstention — it is a gap, and
  filling it with whatever the others say would attribute the whole group to a
  repository only some of it came from. Anthropic's 51 skills are the case that
  made this matter.
- **Aliases are merged.** The provenance resolver reads each container's own
  manifest, and each names its author differently: "OpenAI", "OpenAI (Codex)",
  "OpenAI Codex" are one organisation, and a credits file that lists them
  separately reads as three.

## 7. The publish sequence

```bash
# 1. Resolve the licences
python3 mcp/build/provenance.py
#    -> mcp/data/provenance.json, with a verdict per entry

# 2. Assemble the public tree (copies, filters, de-paths, gates)
python3 mcp/build/assemble_public.py

# 3. Write the licence, the notice and the credits
python3 mcp/build/write_credits.py

# 4. Prove no path leaked
python3 mcp/build/scan_leaks.py
```

`assemble_public.py` writes to a sibling directory — `../skills-library-mcp-public`
by default, or `$PUBLIC_TREE`. The public tree is a *separate* tree from the
working library: the working library holds machine paths and a machine scan's worth
of generators, and the published one holds only what belongs in a public
repository.

It wipes everything except `.git` before writing, so a stale file left behind is
not possible — every file in the tree is either published content or the server's
own source.

Then, in the public tree:

```bash
git add -A
git commit -m "..."
git push
```

## 8. When an entry cannot be published

It stays in the local library and stays fully usable — the MCP server serves it,
`install_skills` can install it, and search finds it. It is simply not in the
public repository, and the reason is recorded in the counts in `NOTICE`.

That is the correct outcome, not a failure. The alternative — publishing it — would
be publishing someone else's work under terms their author did not grant.

If the entry is the maintainer's own work and should be publishable, the problem is
almost always one of two things:

1. **It carries no licence statement.** Adding `license: MIT` to its frontmatter, or
   a `LICENSE` file beside it, fixes it.
2. **It vendors restricted content.** Then the pack or entry needs to be marked
   `restricted` in `mcp/build/packs.json`, with the reason — or the vendored part
   needs to be removed.
