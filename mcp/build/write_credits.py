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
    packs as pack_records,
)
from provenance import TERMS_QUOTES    # noqa: E402


def own_pack_names():
    """The library's own packs, in manifest order.

    Read from the manifest rather than written out here, so that adding a
    pack credits it without editing this file -- and so that the credits
    can never list a pack the library does not have.
    """
    return list(pack_publishable())


def included_pack_names():
    """The own packs that are published under terms that do not grant
    redistribution.

    These are the maintainer's own work, but something they vendor does
    not permit redistribution -- so they are listed separately, under the
    owner's instruction, rather than under the MIT licence that covers
    the rest of the repository's own work.
    """
    return [p['name'] for p in pack_records()
            if p.get('included_with_terms')]


# The packs published under terms, as a set, for the checks below.
INCLUDED_PACK_NAMES = set(included_pack_names())


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

This licence covers this repository's own work: the MCP server, the
index builder, the installers, the tests, the documentation, and the
skills written for this library. It does NOT cover the third-party
skills and agents bundled under `skills/` and `agents/` -- they keep
the terms their authors gave them, and some of them are here under
terms that do not grant redistribution. See `NOTICE` for the full
position and `CREDITS.md` for the attribution.

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


def _upstream_link(entry):
    """A link to where an entry came from, when it is known.

    The repository URL is preferred: it is where the work lives, and it
    is where somebody can go to get it. The plain URL is the fallback,
    and an entry with neither gets no link at all rather than a broken
    one.
    """
    repo = entry.get('repository')
    url = entry.get('url')
    if repo:
        if repo.startswith('http'):
            return repo
        return 'https://github.com/%s' % repo
    return url or ''


# Where a container's own marketplace lives, when the entry's own
# manifest names no repository of its own.
#
# The `repository` field records the *container* a plugin came from --
# OpenAI's `plugins` repo ships the Figma plugin, so Figma's entries
# carry OpenAI's URL. That is where the file was found, but it is not
# where the work came from, and a credits entry pointing there sends
# the reader to the wrong author. The author's own home is the honest
# link, so the container is only used when the author has no upstream
# of their own.
CONTAINER_HOMES = {
    'marketplace:claude-plugins-official':
        'https://github.com/anthropics/skills',
    'marketplace:claude-code': 'https://github.com/anthropics/claude-code',
    'codex-system': 'https://github.com/openai/codex',
    'gemini-antigravity': 'https://antigravity.google',
    'vscode-copilot-chat': 'https://github.com/microsoft/vscode-copilot-chat',
    'openai': 'https://github.com/openai/plugins',
}

# The owners whose work is not at a GitHub URL at all.
OWNER_HOMES = {
    'Figma': 'https://www.figma.com',
    'OpenAI': 'https://github.com/openai/plugins',
    'OpenAI (Codex)': 'https://github.com/openai/codex',
    'Anthropic': 'https://github.com/anthropics/skills',
    'Google (Antigravity)': 'https://antigravity.google',
    'Microsoft': 'https://github.com/microsoft',
    'GitHub (Copilot Chat)': 'https://github.com/microsoft/vscode-copilot-chat',
    'MagicPathAI': 'https://www.magicpath.ai',
    'DigitalOcean': 'https://www.digitalocean.com',
}


def _upstream_label(entry):
    """(label, url) for where an entry came from.

    The link has to point at the *author's* work, not at the container
    the file was found in. OpenAI's `plugins` repository is where the
    Figma plugin was found; Figma wrote it, and Figma's own terms
    govern it -- so the reader is sent to Figma.
    """
    owner = owner_of(entry)
    container = entry.get('container') or ''
    repo = entry.get('repository')

    # The author's own home wins over any repository the entry carries,
    # because a repository named in a plugin manifest is usually the
    # *publisher's* repository, not the author's. Figma's plugin is
    # distributed through OpenAI's `plugins` repo and names it, but
    # Figma wrote it.
    home = OWNER_HOMES.get(owner)
    if home:
        return (owner, home)

    # An entry with no owner of its own falls back to its container's
    # home, and then to the repository its manifest named.
    if owner == 'Unknown':
        home = CONTAINER_HOMES.get(container)
        if home:
            return (container, home)

    if repo:
        return (repo.rstrip('/').split('/')[-1], _upstream_link(entry))

    url = entry.get('url')
    if url:
        return (owner if owner != 'Unknown' else 'upstream', url)

    return (owner if owner != 'Unknown' else '—', None)


def _licence_label(entry):
    """The licence, in the words the upstream used."""
    lic = entry.get('license')
    if lic:
        return lic
    if entry.get('license_source'):
        return 'not stated (%s)' % entry['license_source']
    return 'not stated'


def write_excluded_list(w, restricted, personal, fixture):
    """Name every excluded entry, with its author and its licence.

    The point of a credits file is that somebody can find the author of
    every piece of work in the project. An entry that is not shipped is
    still somebody's work, and the honest way to record it is to name
    it, attribute it, and say where it lives -- not to leave a hole in
    the catalogue that nobody can account for.

    Nothing is redistributed by this list. It is metadata: a name, an
    author, a licence, a URL.
    """
    groups = [
        ('Licence does not permit redistribution', restricted,
         'These entries are **not** in this repository. Their terms do '
         'not permit redistribution, and a credits entry cannot turn '
         'a prohibition into a permission. Each one is listed here so '
         'the work is accounted for and its author credited; to use '
         'one, go to its upstream.'),
        ("The maintainer's own private project files", personal,
         'These are the maintainer\'s own files, from personal projects '
         'that are not published work. They are not in this repository, '
         'and they are listed here only so the count reconciles.'),
        ('Test fixtures, not published content', fixture,
         'Placeholder entries that ship inside a plugin\'s `fixtures/` '
         'directory. The scanner picks them up like any other skill; '
         'they are not content, and they are not published.'),
    ]
    groups = [g for g in groups if g[1]]

    for title, entries, blurb in groups:
        if not entries:
            continue
        w('### %s (%d)' % (title, len(entries)))
        w('')
        w(blurb)
        w('')
        w('| Entry | Kind | Author | Licence | Why it is not published | Upstream |')
        w('|---|---|---|---|---|---|')
        for e in sorted(entries, key=lambda x: (owner_of(x).lower(), x['name'])):
            label, link = _upstream_label(e)
            upstream = ('[%s](%s)' % (label, link) if link else label)
            w('| `%s` | %s | %s | %s | %s | %s |'
              % (e['name'], e.get('kind', 'skill'), owner_of(e),
                 _licence_label(e), e.get('reason', 'not published'),
                 upstream))
        w('')


def write_notice(path, provenance):
    published = [e for e in provenance if e['verdict'] == 'redistributable']
    terms = [e for e in provenance if e['verdict'] == 'included-with-terms']
    restricted = [e for e in provenance if e['verdict'] == 'restricted']
    personal = [e for e in provenance if e['verdict'] == 'personal']
    fixture = [e for e in provenance if e['verdict'] == 'fixture']

    L = []
    w = L.append
    w('NOTICE')
    w('')
    w('This repository bundles content that is **not** covered by this')
    w("repository's own MIT licence. Each bundled skill and agent keeps the")
    w('licence its author gave it, and the complete attribution is in')
    w('`CREDITS.md`.')
    w('')
    w('**Some of the bundled content is here under terms that do not grant')
    w('redistribution.** Those entries are listed, with the upstream\'s own')
    w('terms quoted, in [Entries published under terms that do not permit')
    w('redistribution](#entries-published-under-terms-that-do-not-permit-redistribution)')
    w('below. The repository\'s owner instructed that they be included; the')
    w('upstreams did not grant the right. The position is stated here so')
    w('that it is on the record rather than implied.')
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
      % ', '.join('`%s`' % n for n in own_pack_names()
                  if n not in INCLUDED_PACK_NAMES))
    w('')
    w('`document-builder` is the exception among the library\'s own packs: it')
    w('is the maintainer\'s work, but it vendors Anthropic\'s document skills')
    w('under `vendor/`, whose terms forbid redistributing them. It is')
    w('published at the owner\'s instruction and listed in the section')
    w('below, and the vendored copies remain Anthropic\'s.')
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
    w('are Apache-2.0, one is CC-BY-4.0, and %d are under terms that do not'
      % len(terms))
    w('permit redistribution — see the section below. The licence file for')
    w('each one is in the upstream project it came from, and the')
    w('attribution is listed in `CREDITS.md`.')
    w('')
    w('## Entries published under terms that do not permit redistribution')
    w('')
    w('These %d entries are in this repository because the repository\'s'
      % len(terms))
    w('owner instructed that they be included. Their upstream terms do not')
    w('grant redistribution, and shipping them redistributes material whose')
    w('authors did not agree to that. They are listed here, in full, so')
    w('that the position is explicit rather than buried.')
    w('')
    terms_by_owner = defaultdict(list)
    for e in terms:
        terms_by_owner[owner_of(e)].append(e)
    for owner in sorted(terms_by_owner,
                        key=lambda o: (-len(terms_by_owner[o]), o)):
        entries = terms_by_owner[owner]
        w('### %s — %d %s'
          % (owner, len(entries), 'entry' if len(entries) == 1 else 'entries'))
        w('')
        detail = _terms_detail(entries).rstrip('.')
        detail = detail[0].upper() + detail[1:] if detail else detail
        w('%s.' % detail)
        w('')
        w('| Entry | Kind | Licence |')
        w('|---|---|---|')
        for e in sorted(entries, key=lambda x: x['name']):
            w('| `%s` | %s | %s |'
              % (e['name'], e.get('kind', 'skill'), _licence_label(e)))
        w('')
        # Where the upstream published terms a reader can check, quote
        # them. A paraphrase is a claim about the terms; a quotation is
        # the terms, and the reader can go and look.
        quote = TERMS_QUOTES.get(owner)
        if quote:
            # The source line already ends in a colon; adding another
            # would print `marketplace::`.
            w(quote[0] if quote[0].endswith(':') else '%s:' % quote[0])
            w('')
            for line in quote[1:]:
                w(line)
            w('')
    w('That is the plain text of the terms, and publishing the pack does')
    w('the thing it forbids. The pack is included because the owner asked')
    w('for it; the vendored copies remain Anthropic\'s.')
    w('')
    w('## Entries that were left out')
    w('')
    w('| Reason | Count |')
    w('|---|---:|')
    w('| Published — the licence permits redistribution | %d |' % len(published))
    w('| Published — the owner\'s instruction; the terms do not permit it | %d |'
      % len(terms))
    w('| Excluded — the maintainer\'s own private project files | %d |' % len(personal))
    w('| Excluded — test fixtures, not published content | %d |' % len(fixture))
    w('')
    if restricted:
        w('%d entries are excluded because their licence does not permit'
          % len(restricted))
        w('redistribution and the owner did not instruct otherwise. They')
        w('are named below, with their author, their licence and where they')
        w('came from. Naming an entry here attributes it; it does not')
        w('redistribute it.')
    else:
        w('No entry is excluded on licence grounds. The entries that are not')
        w('here are the maintainer\'s own private project files and the')
        w('test fixtures, both listed below.')
    w('')
    w('The lists are generated from the same provenance table that decides')
    w('what is published, by `mcp/build/provenance.py`, which resolves a')
    w('licence per entry from the container manifest, the nearest `LICENSE`')
    w('file, the installed package metadata, or the entry\'s own')
    w('frontmatter, in that order. It cannot drift from what actually')
    w('shipped.')
    w('')
    write_excluded_list(w, restricted, personal, fixture)
    w('## Third-party components')
    w('')
    w('The `ponytail/` directory is an upstream clone kept whole, with its')
    w('own `LICENSE` (MIT, (c) 2026 Dietrich Gebert) and its own history.')
    w('It is a third-party project, redistributed unchanged under its own')
    w('licence, and it is *not* covered by this repository\'s MIT licence.')
    w('')
    w('The `mattpocock-skills/` directory is a second upstream clone, kept')
    w('whole, with its own `LICENSE` (MIT, (c) 2026 Matt Pocock). It is a')
    w('third-party project, redistributed under its own licence, and it is')
    w('*not* covered by this repository\'s MIT licence. Its `UPSTREAM.md`')
    w('records the commit it is pinned to and the two changes made to the')
    w('clone, both of which the upstream itself sanctions.')
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


def _terms_detail(entries):
    """The upstream terms for one author's entries, as a sentence.

    Two entries from one upstream share one set of terms, so the terms
    are printed once per upstream rather than once per entry -- the
    table below already says which entries each applies to.
    """
    from provenance import INCLUDE_WITH_TERMS
    owner = owner_of(entries[0])
    detail = INCLUDE_WITH_TERMS.get(owner)
    if detail:
        return detail
    # A per-entry reason that was established by investigating that
    # entry beats the general rule.
    for e in entries:
        if e.get('reason'):
            return e['reason']
    return 'published at the owner\'s instruction'


def write_credits(path, provenance):
    published = [e for e in provenance
                 if e['verdict'] in ('redistributable', 'included-with-terms')]

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
    terms_owners = {owner_of(e) for e in provenance
                     if e['verdict'] == 'included-with-terms'}
    for owner, entries in ordered:
        lics = licenses_of(entries)
        lic = ', '.join(sorted(lics)) if lics else '—'
        repo = repo_of(entries)
        upstream = '[%s](%s)' % (repo.rsplit('/', 1)[-1], repo) if repo else '—'
        # An author with entries under terms that do not grant
        # redistribution gets a marker, so the row is not read as "all of
        # this author's entries are here on a permissive licence".
        note = ' *(some under terms)*' if owner in terms_owners else ''
        w('| %s%s | %d | %s | %s |' % (owner, note, len(entries), lic, upstream))

    # The entries published under terms that do not grant redistribution,
    # listed by author, so the credit for them is as explicit as the
    # credit for everything else.
    terms_entries = [e for e in provenance
                     if e['verdict'] == 'included-with-terms']
    if terms_entries:
        w('')
        w('### The entries published under terms that do not grant')
        w('redistribution')
        w('')
        w('These %d %s here at the repository owner\'s instruction.'
          % (len(terms_entries),
             'entry is' if len(terms_entries) == 1 else 'entries are'))
        w('Their upstream terms do not grant redistribution. `NOTICE` lists')
        w('them all and quotes the terms; this is the credit.')
        w('')
        terms_by_owner = defaultdict(list)
        for e in terms_entries:
            terms_by_owner[owner_of(e)].append(e)
        for owner in sorted(terms_by_owner,
                            key=lambda o: (-len(terms_by_owner[o]), o)):
            entries = terms_by_owner[owner]
            w('**%s** — %d %s'
              % (owner, len(entries),
                 'entry' if len(entries) == 1 else 'entries'))
            w('')
            for e in sorted(entries, key=lambda x: x['name']):
                label, link = _upstream_label(e)
                upstream = ('[%s](%s)' % (label, link) if link else label)
                w('- `%s` (%s) — %s — %s'
                  % (e['name'], e.get('kind', 'skill'),
                     _licence_label(e), upstream))
            w('')

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
    w('### Matt Pocock\'s skills')
    w('')
    w('Kept whole at `mattpocock-skills/`, with its own licence. The upstream')
    w('ships 27 of its 39 skills in its own plugin; this repository ships')
    w('the same 27.')
    w('')
    w('- Author: Matt Pocock')
    w('- Upstream: <https://github.com/mattpocock/skills>')
    w('- Licence: MIT — (c) 2026 Matt Pocock')
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
    w('Because those terms forbid redistribution, `document-builder` is')
    w('published under the owner\'s instruction rather than on the strength')
    w('of a licence. It is listed among the entries whose terms do not grant')
    w('redistribution in `NOTICE`, with the vendored terms quoted there.')
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
        if name in INCLUDED_PACK_NAMES:
            continue
        w('- `%s` — %s' % (name, pack_summary(name)))
    w('')
    w('`skill-creator-plus` is derived from Anthropic\'s `skill-creator`')
    w('(Apache-2.0), with additional references, scripts and an eval-review')
    w('viewer. Its upstream terms are noted here because they apply to the')
    w('part it derives from.')
    w('')
    for name in own_pack_names():
        if name not in INCLUDED_PACK_NAMES:
            continue
        w('`%s` is the repository\'s own work too, but it vendors' % name)
        w('material whose terms do not grant redistribution, so it is not')
        w('covered by the MIT licence above. It is published at the')
        w('owner\'s instruction and listed in `NOTICE` among the entries')
        w('whose terms do not permit redistribution, with the vendored')
        w('terms quoted there.')
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
    w('## Every published entry')
    w('')
    w('The complete list: every entry this repository publishes, who wrote')
    w('it, under what terms, and where it came from. The counts above')
    w('summarise it; this is the attribution itself.')
    w('')
    w('| Entry | Kind | Author | Terms | Upstream |')
    w('|---|---|---|---|---|')
    for e in sorted(published, key=lambda x: (x.get('kind', 'skill'),
                                               x['name'])):
        label, link = _upstream_label(e)
        upstream = ('[%s](%s)' % (label, link) if link else label)
        w('| `%s` | %s | %s | %s | %s |'
          % (e['name'], e.get('kind', 'skill'), owner_of(e),
             _licence_label(e), upstream))
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
    # The tree the files are written *into* is the tree the provenance is
    # read *from*. In the local library that is the local table, with the
    # machine's absolute paths; in the published tree it is the published
    # table, which has the container labels instead. Either way the file
    # describes the tree it sits in -- which is the whole point of
    # generating it from the table rather than writing it by hand.
    dst = os.environ.get('PUBLIC_TREE') or os.path.join(
        os.path.dirname(BASE), 'skills-library-mcp-public')

    prov_path = os.path.join(dst, 'mcp', 'data', 'provenance.json')
    if not os.path.isfile(prov_path):
        prov_path = os.path.join(BASE, 'mcp', 'data', 'provenance.json')
    with open(prov_path, encoding='utf-8') as fh:
        provenance = json.load(fh)

    for p in (write_license(os.path.join(dst, 'LICENSE')),
              write_notice(os.path.join(dst, 'NOTICE'), provenance),
              write_credits(os.path.join(dst, 'CREDITS.md'), provenance)):
        print('wrote %s' % os.path.relpath(p, dst))

    pub = sum(1 for e in provenance
              if e['verdict'] in ('redistributable', 'included-with-terms'))
    print('  credited %d published entries' % pub)


if __name__ == '__main__':
    main()
