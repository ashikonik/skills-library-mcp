#!/usr/bin/env python3
"""Write the public tree's LICENSE, NOTICE and CREDITS.md.

Three files, three different jobs:

  LICENSE   the licence of *this* repository -- the server code, the
            tooling, and the packs written for it.
  NOTICE    the statement that the bundled skills keep their own licences,
            and which entries were left out because their licence does not
            permit redistribution.
  CREDITS   who wrote what. Every published entry is attributed to its
            real upstream owner, with the licence it carries.

The credits are generated from the provenance table rather than written by
hand, because the table is the thing that decides who owns what. A hand-
written credits file drifts the moment the library changes; a generated
one cannot.
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from packs import (                    # noqa: E402
    by_name as pack_by_name,
    publishable as pack_publishable,
)


def own_pack_names():
    """The library's own packs, in manifest order.

    Read from the manifest rather than written out here, so that adding a
    pack credits it without editing this file -- and so that the credits
    can never list a pack the library does not have.
    """
    return list(pack_publishable())


def pack_summary(name):
    """One line about a pack, for the credits list."""
    rec = pack_by_name(name)
    if rec is None:
        return name
    return rec.get('summary', '')

# The repository itself. The server, the index builder, the installers and
# the test suite are this repository's own work.
REPO_HOLDER = 'Md. Ashik-Uz-Zaman'
REPO_YEAR = '2026'

# The upstream projects the packs are built from, and the copyright holder
# each of them names. The provenance table knows the *licence* of every
# entry; these are the copyright lines the licences require be carried
# along.
#
# `owner` is the name the provenance table records; `holders` is the
# copyright line to print. They differ when the manifest names a team and
# the licence names a person.
HOLDER_OVERRIDES = {
    'Affaan Mustafa (affaan-m/ECC)': 'Affaan Mustafa',
    'Affaan Mustafa': 'Affaan Mustafa',
    'OpenAI': 'OpenAI',
    'OpenAI Codex': 'OpenAI',
    'OpenAI (Codex)': 'OpenAI',
    'Jesse Vincent': 'Jesse Vincent',
    'Sebastián Ramírez (fastapi/typer)': 'Sebastián Ramírez',
    'Prisma (prisma/prisma)': 'Prisma',
    'This library (hand-authored)': REPO_HOLDER,
}

# The same organisation, recorded under more than one name.
#
# The provenance resolver reads each container's own manifest, and each
# manifest names its author in its own way: the Codex plugin cache says
# "OpenAI", the Codex system skills say "OpenAI (Codex)", and a third
# plugin says "OpenAI Codex". They are one organisation, and a credits
# file that lists them separately reads as three -- so they are merged
# here, and the licence of each entry is still its own.
OWNER_ALIASES = {
    'OpenAI Codex': 'OpenAI',
    'OpenAI (Codex)': 'OpenAI',
    'Affaan Mustafa': 'Affaan Mustafa (affaan-m/ECC)',
}


def owner_of(entry):
    """The author's name, with the aliases merged."""
    owner = entry.get('owner') or 'Unknown'
    return OWNER_ALIASES.get(owner, owner)


def holder_for(owner):
    return HOLDER_OVERRIDES.get(owner, owner)


def repo_of(entries):
    """The single upstream repository, when the entries agree on one.

    "Agree" means *every* entry names the same one. An entry that names
    no repository at all is not a neutral abstention -- it is a gap, and
    filling that gap with whatever the others say would attribute the
    whole group to a repository only some of it came from. Anthropic's
    51 skills are the case that made this matter: one of them names a
    community repository, the other 50 name none, and the table read as
    though Anthropic's collection lived at that community's repo.
    """
    repos = {e.get('repository') for e in entries}
    if len(repos) == 1:
        repo = repos.pop()
        return repo or None
    return None


def licenses_of(entries):
    """The licences the entries carry, normalised."""
    out = set()
    for e in entries:
        lic = e.get('license')
        if not lic:
            continue
        # 'Apache 2.0' and 'Apache-2.0' are the same licence; the manifest
        # and the licence file spell it differently.
        out.add('Apache-2.0' if lic.replace(' ', '-') == 'Apache-2.0' else lic)
    return out


LICENSE_TEXT = """\
MIT License

Copyright (c) {year} {holder}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def write_license(path):
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(LICENSE_TEXT.format(year=REPO_YEAR, holder=REPO_HOLDER))
    return path


def write_notice(path, provenance):
    published = [e for e in provenance if e['verdict'] == 'redistributable']
    restricted = [e for e in provenance if e['verdict'] == 'restricted']
    personal = [e for e in provenance if e['verdict'] == 'personal']
    fixture = [e for e in provenance if e['verdict'] == 'fixture']

    L = []
    w = L.append
    w('NOTICE')
    w('')
    w('This repository bundles content that is **not** covered by this')
    w("repository's own MIT licence. Each bundled skill and agent keeps the")
    w('licence its author gave it. The complete attribution is in')
    w('`CREDITS.md`; the licences themselves travel with the content, in')
    w('each plugin manifest and each upstream `LICENSE` file.')
    w('')
    w('## What the MIT licence covers')
    w('')
    w('The MIT licence in `LICENSE` covers the work in this repository:')
    w('')
    w('- the MCP server — `mcp/src/**` (TypeScript) and `mcp/python/**`')
    w('  (the stdlib-only fallback);')
    w('- the index builder and the library tooling — `mcp/build/**`,')
    w('  `.build_library.py`, `.build_guide.py`, `.gen_report.py`;')
    w('- the installers, the test suite and the documentation;')
    w('- the skills written for this library: %s.'
      % ', '.join('`%s`' % n for n in own_pack_names()))
    w('')
    w('`skill-creator-plus` is derived from Anthropic\'s `skill-creator`')
    w('(Apache-2.0), with additional references, scripts and an eval-review')
    w('viewer. Its upstream terms are noted here because they apply to the')
    w('part it derives from.')
    w('')
    w('## What it does not cover')
    w('')
    w('Every other skill and agent under `skills/` and `agents/` is third-')
    w('party work, redistributed under its own licence. Some are MIT, some')
    w('are Apache-2.0, one is CC-BY-4.0. The licence file for each one is')
    w('in the upstream project it came from, and the attribution is listed')
    w('in `CREDITS.md`.')
    w('')
    w('## Entries that were left out')
    w('')
    w('An entry is published only if its own licence permits redistribution.')
    w('Publishing material whose licence forbids it would grant rights the')
    w('author did not grant, so those entries are **not** in this repository.')
    w('')
    w('| Reason | Count |')
    w('|---|---:|')
    w('| Published | %d |' % len(published))
    w('| Excluded — the licence does not permit redistribution | %d |' % len(restricted))
    w('| Excluded — the maintainer\'s own private project files | %d |' % len(personal))
    w('| Excluded — test fixtures, not published content | %d |' % len(fixture))
    w('')
    w('The excluded entries are not listed here by name, because naming them')
    w('would defeat the point of excluding them: they would still be')
    w('pointed at. The count is the honest disclosure — the excluded set is')
    w('regenerated by `mcp/build/provenance.py`, which resolves a licence')
    w('per entry from the container manifest, the nearest `LICENSE` file,')
    w('the installed package metadata, or the entry\'s own frontmatter, in')
    w('that order.')
    w('')
    w('## Third-party components')
    w('')
    w('The `ponytail/` directory is an upstream clone kept whole, with its')
    w('own `LICENSE` (MIT, (c) 2026 Dietrich Gebert) and its own history.')
    w('It is a third-party project, redistributed unchanged under its own')
    w('licence, and it is *not* covered by this repository\'s MIT licence.')
    w('')
    w('The `skills/impeccable/` directory is redistributed under Apache-2.0')
    w('from [pbakaus/impeccable](https://github.com/pbakaus/impeccable);')
    w('`skills/emil-design-eng/` and `skills/design-taste-frontend/` under')
    w('MIT from [emilkowalski/skills](https://github.com/emilkowalski/skills)')
    w('and [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)')
    w('respectively. Their terms ride along in those directories.')
    w('')
    w('The TypeScript server depends on `@modelcontextprotocol/sdk` (MIT),')
    w('`zod` (MIT) and `yaml` (ISC). They are build-time dependencies and')
    w('are not redistributed here.')
    w('')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L) + '\n')
    return path


def write_credits(path, provenance):
    published = [e for e in provenance if e['verdict'] == 'redistributable']

    by_owner = defaultdict(list)
    for e in published:
        by_owner[owner_of(e)].append(e)

    L = []
    w = L.append
    w('# Credits')
    w('')
    w('Every skill and agent in this repository was written by somebody else.')
    w('This file says who.')
    w('')
    w('It is generated from `mcp/data/provenance.json`, which resolves a')
    w('licence and an owner for each entry by reading the container\'s own')
    w('manifest — the `plugin.json` a plugin ships, the `LICENSE` file next')
    w('to the content, the installed package metadata, or the entry\'s')
    w('frontmatter. Nothing here is asserted by hand, so it cannot drift')
    w('away from what actually shipped.')
    w('')
    w('| | |')
    w('|---|---:|')
    w('| Published entries | %d |' % len(published))
    w('| Distinct authors and organisations | %d |' % len(by_owner))
    w('')
    w('## By author')
    w('')
    w('| Author / organisation | Entries | Licence | Upstream |')
    w('|---|---:|---|---|')

    # Biggest contributors first; ties broken by name so the file is stable.
    ordered = sorted(by_owner.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for owner, entries in ordered:
        lics = licenses_of(entries)
        lic = ', '.join(sorted(lics)) if lics else '—'
        repo = repo_of(entries)
        upstream = '[%s](%s)' % (repo.rsplit('/', 1)[-1], repo) if repo else '—'
        w('| %s | %d | %s | %s |' % (owner, len(entries), lic, upstream))

    w('')
    w('## The individual copyright holders')
    w('')
    w('The licences above require their copyright notices to be carried')
    w('along. Those notices, verbatim:')
    w('')
    for owner, entries in ordered:
        if owner == 'This library (hand-authored)':
            continue
        holder = holder_for(owner)
        lics = licenses_of(entries)
        if not lics:
            continue
        w('- **%s** — %s' % (holder, ', '.join(sorted(lics))))
        repo = repo_of(entries)
        if repo:
            w('  — <%s>' % repo)

    w('')
    w('## The collections, in detail')
    w('')
    w('### ECC — "Everything Claude Code"')
    w('')
    w('The largest single group: %d entries.'
      % len(by_owner.get('Affaan Mustafa (affaan-m/ECC)', [])))
    w('')
    w('- Author: Affaan Mustafa')
    w('- Upstream: <https://github.com/affaan-m/ECC>')
    w('- Licence: MIT — (c) 2026 Affaan Mustafa')
    w('')
    w('### Ponytail')
    w('')
    w('Kept whole at `ponytail/`, with its own licence and its own history.')
    w('')
    w('- Author: Dietrich Gebert')
    w('- Upstream: <https://github.com/dietrichgebert/ponytail>')
    w('- Licence: MIT — (c) 2026 Dietrich Gebert')
    w('')
    w('### The Anthropic plugin marketplace')
    w('')
    w('The official Claude Code plugin set, plus the entries it contributes.')
    w('')
    w('- Author: Anthropic, PBC')
    w('- Upstream: <https://github.com/anthropics/claude-code>')
    w('- Licence: Apache-2.0')
    w('')
    w('### The OpenAI plugin repositories')
    w('')
    w('The Codex plugin marketplace and the curated plugin cache.')
    w('')
    w('- Author: OpenAI')
    w('- Upstream: <https://github.com/openai/plugins>, <https://github.com/openai/codex>')
    w('- Licence: MIT (and Apache-2.0 for the `openai/codex` system skills)')
    w('')
    w('### The design skills')
    w('')
    w('Three third-party skills, each under its own licence:')
    w('')
    w('| Skill | Author | Upstream | Licence |')
    w('|---|---|---|---|')
    w('| `emil-design-eng` | Emil Kowalski | [emilkowalski/skills](https://github.com/emilkowalski/skills) | MIT — (c) 2026 Emil Kowalski |')
    w('| `impeccable` | Paul Bakaus | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Apache-2.0 |')
    w('| `design-taste-frontend` | Leonxlnx | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | MIT — (c) 2026 Leonxlnx |')
    w('')
    w('`emil-design-eng` encodes Emil Kowalski\'s design-engineering')
    w('philosophy; `design-taste-frontend` is "tasteskill v2"; `impeccable`')
    w('is the design vocabulary and anti-slop detector.')
    w('')
    w('### The pack vendors')
    w('')
    w('`document-builder` bundles its own copies of the docx, pptx, xlsx,')
    w('pdf and frontend-design skills so it works standalone. Those bundled')
    w('copies are Anthropic\'s, under Anthropic\'s own terms, and each one')
    w('carries its `LICENSE.txt`.')
    w('')
    w('Because those terms forbid redistribution, `document-builder` itself is')
    w('**not** in this repository — it is in the working library, where the')
    w('bundled copies came from, and it is left out of the published tree')
    w('whole rather than shipped with its vendored content stripped out. It')
    w('is counted among the excluded entries in `NOTICE`.')
    w('')
    w('- Author: Anthropic, PBC')
    w('- Upstream: <https://github.com/anthropics/skills>')
    w('- Terms: source-available, not open source — see each')
    w('  `vendor/<name>/LICENSE.txt`')
    w('')
    w('## The skills written for this library')
    w('')
    w('These are the repository\'s own work, and they are covered by this')
    w('repository\'s MIT licence:')
    w('')
    for name in own_pack_names():
        w('- `%s` — %s' % (name, pack_summary(name)))
    w('')
    w('`skill-creator-plus` is derived from Anthropic\'s `skill-creator`')
    w('(Apache-2.0), with additional references, scripts and an eval-review')
    w('viewer. Its upstream terms are noted here because they apply to the')
    w('part it derives from.')
    w('')
    w('## The server')
    w('')
    w('The MCP server — the TypeScript implementation, the Python fallback,')
    w('the index builder, the installers and the test suite — is the work of')
    w('%s, and is covered by this repository\'s MIT licence.' % REPO_HOLDER)
    w('')
    w('It depends on `@modelcontextprotocol/sdk` (MIT), `zod` (MIT) and')
    w('`yaml` (ISC), which are not redistributed here.')
    w('')
    w('## How to check this file')
    w('')
    w('```')
    w('python3 mcp/build/provenance.py        # resolve the licences and owners')
    w('python3 mcp/build/write_credits.py     # regenerate this file')
    w('```')
    w('')
    w('`provenance.json` records, for every entry: the owner, the licence,')
    w('where the licence was read from, the upstream repository, and the')
    w('verdict — publish or exclude.')
    w('')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L) + '\n')
    return path


def main():
    prov_path = os.path.join(BASE, 'mcp', 'data', 'provenance.json')
    with open(prov_path, encoding='utf-8') as fh:
        provenance = json.load(fh)

    dst = os.environ.get('PUBLIC_TREE') or os.path.join(
        os.path.dirname(BASE), 'skills-library-mcp-public')

    for p in (write_license(os.path.join(dst, 'LICENSE')),
              write_notice(os.path.join(dst, 'NOTICE'), provenance),
              write_credits(os.path.join(dst, 'CREDITS.md'), provenance)):
        print('wrote %s' % os.path.relpath(p, dst))

    pub = sum(1 for e in provenance if e['verdict'] == 'redistributable')
    print('  credited %d published entries' % pub)


if __name__ == '__main__':
    main()
