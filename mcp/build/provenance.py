#!/usr/bin/env python3
"""Resolve the licence and owner of every entry in the library.

Each skill came from somewhere with its own licence. Publishing them
under one licence without saying whose they are would be wrong, so this
resolves a licence per entry by, in order:

  1. the container's own manifest -- `license` in `plugin.json`. The Codex
     plugin cache and the plugin temp directory both carry one per plugin,
     and the manifest is the authoritative statement of provenance.
  2. the nearest LICENSE file walking up from the entry's own directory.
  3. a `licenses/` entry inside a sibling `*.dist-info` (an installed
     Python package).
  4. the entry's own frontmatter `license` field.

The result is a redistribution verdict per entry:

  redistributable   the licence permits redistribution -- MIT, Apache-2.0,
                    BSD, ISC, MPL, CC-BY. Its terms ride along in the
                    repository's NOTICE and CREDITS.
  restricted        anything else -- Proprietary, UNLICENSED, a LicenseRef,
                    or no licence stated anywhere. Such content cannot be
                    published, because publishing it would grant rights the
                    author did not grant.
  personal          the maintainer's own project files. They leak machine
                    paths and belong to a private repository.

This is a *derived* artifact, like the index: it is rebuilt from the
library tree, and nothing at runtime depends on it.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
HOME = os.path.expanduser('~')

sys.path.insert(0, HERE)
from build_index import yaml_frontmatter  # noqa: E402

PLUG = os.path.join(HOME, '.codex/.tmp/plugins/plugins')
CACHE = os.path.join(HOME, '.codex/plugins/cache')
MKT = os.path.join(HOME, '.claude/plugins/marketplaces')

# A licence that permits redistribution. GPL is deliberately absent: it is
# copyleft, and a copyleft skill cannot be redistributed inside an MIT
# repository without the whole repository becoming GPL.
PERMISSIVE = ('MIT', 'Apache-2.0', 'Apache', 'BSD', 'ISC', 'MPL', 'CC-BY')

# The maintainer's own projects. Within them, two files are the maintainer's
# own work and leak machine paths; the rest are third-party content (Prisma,
# impeccable) that merely happens to sit in a personal directory.
PERSONAL_ROOTS = (
    os.path.join(HOME, 'Projects', 'CSE412'),
    os.path.join(HOME, 'Projects', 'HisabKora'),
    os.path.join(HOME, 'Projects', 'birthday'),
)
PERSONAL_EXCLUDE = ('hisabkora-context', 'harvest-from-ecc')

# Content that lives inside a personal project directory but is *not* the
# maintainer's own work -- it is an upstream project that happens to sit
# there. The licence resolver cannot see these: there is no manifest and
# no LICENSE file beside them, only the upstream's own licence. So the
# licence and the owner are declared here, with the upstream they come
# from.
#
# `design-taste-frontend` and `emil-design-eng` are snapshots of two MIT
# upstream skills; `impeccable` is Apache-2.0 and says so in its own
# frontmatter.
DECLARED = {
    'design-taste-frontend': {
        'license': 'MIT',
        'owner': 'Leonxlnx',
        'repository': 'https://github.com/Leonxlnx/taste-skill',
    },
    'emil-design-eng': {
        'license': 'MIT',
        'owner': 'Emil Kowalski',
        'repository': 'https://github.com/emilkowalski/skills',
    },
    'impeccable': {
        'license': 'Apache-2.0',
        'owner': 'Paul Bakaus',
        'repository': 'https://github.com/pbakaus/impeccable',
    },
}

# The `ponytail/` directory is an upstream clone, kept whole. Its skills
# are copied into `skills/` by the ordinary scanner, which records the
# clone as the source -- so the licence resolver reads the clone's own
# MIT licence but has no author for it, and falls back to the container.
# The author is known: the clone's `LICENSE` says so.
PONYTAIL_SKILLS = (
    'ponytail', 'ponytail-audit', 'ponytail-debt', 'ponytail-gain',
    'ponytail-help', 'ponytail-review',
)
PONYTAIL = {
    'license': 'MIT',
    'owner': 'Dietrich Gebert',
    'repository': 'https://github.com/dietrichgebert/ponytail',
}

# The maintainer's own packs. They carry no licence file of their own --
# they predate the licence decision -- so the licence resolver finds
# nothing and calls them "restricted". They are the maintainer's own
# work, and this repository is MIT, so they are MIT.
#
# `document-builder` is NOT in this list: it bundles Anthropic's docx,
# pptx, xlsx and pdf skills, whose terms forbid redistribution. It cannot
# be published, and saying so is more honest than shipping half of it.
OWN_PACKS = ('caveman-mode', 'humanizer', 'latex-doctor', 'research-partner')

# Test fixtures, not content. The `plugin-eval` plugin ships example
# plugins under `fixtures/`, and the scanner picks their skills up like
# any other's. They are placeholder skills -- "alpha", "beta",
# "minimal-plugin-skill" -- and publishing them would put three
# meaningless entries in the catalogue and three odd author names in
# the credits. They are excluded for the same reason the personal files
# are: they are not the work anybody shipped.
TEST_FIXTURE_NAMES = ('alpha', 'beta', 'minimal-plugin-skill')
TEST_FIXTURE_PATH = os.path.join('fixtures', '')


def classify_text(t):
    """The SPDX-ish name of the licence in a licence file."""
    t = t.lower()
    if 'apache license' in t:
        return 'Apache-2.0'
    if 'mit license' in t or 'permission is hereby granted, free of charge' in t:
        return 'MIT'
    if 'gnu general public' in t:
        return 'GPL'
    if 'mozilla public' in t:
        return 'MPL'
    if 'isc license' in t:
        return 'ISC'
    if 'bsd' in t and 'redistribution' in t:
        return 'BSD'
    if 'creative commons' in t or 'cc-by' in t:
        return 'CC-BY-4.0'
    if 'copyright' in t and 'warranty' in t:
        return 'other (custom terms)'
    return 'other (unrecognised)'


def nearest_license(start):
    """Nearest LICENSE file walking up from the entry's own directory.

    The walk starts at `start` itself: a skill that carries its own
    LICENSE.txt is licensed by it, and starting at the parent would miss
    exactly that file.
    """
    d0 = start.rstrip('/')
    if not os.path.isdir(d0):
        d0 = os.path.dirname(d0)
    for _ in range(9):
        for name in ('LICENSE', 'LICENSE.txt', 'LICENSE.md', 'LICENSE-MIT',
                     'LICENSE-APACHE', 'license.txt', 'COPYING', 'NOTICE'):
            p = os.path.join(d0, name)
            if os.path.isfile(p):
                try:
                    txt = open(p, encoding='utf-8', errors='replace').read(4000)
                except OSError:
                    continue
                return classify_text(txt), p
        parent = os.path.dirname(d0)
        if parent == d0:
            break
        d0 = parent
    return None, None


def dist_info_license(start):
    """Licence from a sibling *.dist-info (an installed Python package).

    An installed package's metadata directory sits *beside* the package,
    not inside it, so the walk goes up from the package and then down into
    `*.dist-info/licenses/`. The `License-Expression` in METADATA is used
    when there is no licence file.
    """
    d = start.rstrip('/')
    for _ in range(4):
        parent = os.path.dirname(d)
        if parent == d:
            break
        for di in glob.glob(os.path.join(parent, '*.dist-info')):
            for f in glob.glob(os.path.join(di, 'licenses', 'LICENSE*')):
                try:
                    txt = open(f, encoding='utf-8', errors='replace').read(4000)
                except OSError:
                    continue
                return classify_text(txt), f
            meta = os.path.join(di, 'METADATA')
            if os.path.isfile(meta):
                try:
                    for line in open(meta, encoding='utf-8',
                                     errors='replace'):
                        if line.startswith('License-Expression:'):
                            return line.split(':', 1)[1].strip(), meta
                except OSError:
                    pass
        d = parent
    return None, None


def frontmatter_license(rec, kind):
    rel = (rec['path'].rstrip('/') + '/SKILL.md') if kind == 'skill' else rec['path']
    p = os.path.join(BASE, rel)
    if not os.path.isfile(p):
        return None
    meta, ok, err, text, raw = yaml_frontmatter(p)
    if meta and meta.get('license'):
        return str(meta['license'])
    return None


def load_manifests(root):
    """Every plugin manifest under root, keyed by the plugin's own path.

    `glob` is not used: `**` does not traverse dot-directories, and the
    manifest lives in `.codex-plugin/` -- so glob would find nothing and
    every plugin would look unlicensed.

    The key is the plugin's *own* directory -- the one holding
    `.codex-plugin/` or `.claude-plugin/` -- not the top-level
    directory of the tree. That distinction is the whole point: one
    marketplace holds dozens of plugins, each with its own author and
    its own licence, and keying by the tree's root collapses them into
    whichever manifest the walk happened to reach first. That is not a
    hypothetical -- it credited 51 Anthropic skills to "Asana", because
    the marketplace's `asana` plugin was found first.

    The key is the absolute path, so a caller resolves it by walking
    up from the source path, and the *nearest* manifest wins.
    """
    out = {}
    if not os.path.isdir(root):
        return out
    for dp, dn, fn in os.walk(root):
        if 'plugin.json' in fn:
            p = os.path.join(dp, 'plugin.json')
            try:
                j = json.load(open(p, encoding='utf-8'))
            except Exception:
                continue
            # `dp` is the directory holding the manifest; its parent is
            # the plugin's own directory.
            out[os.path.dirname(dp)] = j
    return out


def load_marketplace(root):
    """A marketplace's own metadata, or None.

    A marketplace is not a plugin: it is a *directory of* plugins, some
    written by the marketplace's owner and some contributed from
    outside. The marketplace's own `marketplace.json` names its owner,
    and its `LICENSE` is the terms every plugin inside it inherits
    unless the plugin says otherwise.

    So a plugin without an author of its own is credited to the
    marketplace's owner, and takes the marketplace's licence.
    """
    if not os.path.isdir(root):
        return None
    meta = {}
    for name in ('marketplace.json',):
        for p in (os.path.join(root, '.claude-plugin', name),
                  os.path.join(root, name)):
            if os.path.isfile(p):
                try:
                    j = json.load(open(p, encoding='utf-8'))
                except Exception:
                    continue
                meta.update(j)
                break
    lic = None
    lic_path = None
    for name in ('LICENSE', 'LICENSE.txt', 'LICENSE.md'):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            try:
                txt = open(p, encoding='utf-8', errors='replace').read(4000)
            except OSError:
                continue
            lic = classify_text(txt)
            lic_path = p
            break
    meta['license'] = lic
    meta['license_path'] = lic_path
    return meta or None


def nearest_manifest(mans, src):
    """The manifest of the plugin that owns `src`, or None.

    The source path is walked upwards and the first plugin directory
    that matches wins. Walking up rather than guessing the depth is
    what makes this work across three different layouts: a flat
    plugin directory, a versioned cache (`<plugin>/<version>/`), and a
    marketplace that nests plugins two levels down.
    """
    d = os.path.dirname(src.rstrip('/'))
    for _ in range(9):
        if d in mans:
            return mans[d]
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def plugin_name(mans, src):
    """The plugin's own directory name, for the container label."""
    d = os.path.dirname(src.rstrip('/'))
    for _ in range(9):
        if d in mans:
            return os.path.basename(d)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


PLUG_MANS = load_manifests(PLUG)
CACHE_MANS = load_manifests(CACHE)
MKT_MANS = load_manifests(MKT)

# The marketplaces' own metadata, keyed by their directory name.
MKT_META = {}
if os.path.isdir(MKT):
    for name in os.listdir(MKT):
        meta = load_marketplace(os.path.join(MKT, name))
        if meta:
            MKT_META[name] = meta


def describe(src):
    """(owner, repository, url, licence, licence_source, container)."""
    owner = repo = url = lic = lic_src = None
    container = None
    mkt = None

    if src.startswith(PLUG):
        container = 'plugin:' + (plugin_name(PLUG_MANS, src) or '?')
        man = nearest_manifest(PLUG_MANS, src)
    elif src.startswith(CACHE):
        container = 'codex-cache:' + (plugin_name(CACHE_MANS, src) or '?')
        man = nearest_manifest(CACHE_MANS, src)
    elif src.startswith(MKT):
        p = src[len(MKT):].lstrip('/').split('/')[0]
        container = 'marketplace:' + p
        mkt = MKT_META.get(p)
        man = nearest_manifest(MKT_MANS, src)
    else:
        man = None

    if man is not None:
        lic = man.get('license')
        lic_src = 'manifest'
        au = man.get('author') or {}
        if isinstance(au, str):
            au = {'name': au}
        owner = au.get('name') or container
        url = au.get('url') or man.get('homepage')
        repo = man.get('repository')

    # A plugin that names no author belongs to whoever owns the
    # marketplace it sits in, and takes the marketplace's licence. The
    # marketplace's own `marketplace.json` says who that is -- for
    # Anthropic's directory, "Anthropic" -- and the directory's LICENSE
    # says under what terms.
    if mkt is not None:
        if owner in (None, container):
            mo = mkt.get('owner') or {}
            if isinstance(mo, str):
                mo = {'name': mo}
            owner = mo.get('name') or owner
        if not lic and mkt.get('license'):
            lic = mkt['license']
            lic_src = 'marketplace licence'

    # the containers that are not plugin manifests
    if owner is None:
        if src.startswith(os.path.join(HOME, 'Projects', 'ECC')):
            container, owner = 'ecc', 'Affaan Mustafa (affaan-m/ECC)'
            repo = 'https://github.com/affaan-m/ECC'
        elif src.startswith(os.path.join(HOME, 'Projects', 'Skills_n_Agents')):
            container, owner = 'this-library', 'This library (hand-authored)'
        elif src.startswith(os.path.join(HOME, 'Projects', 'CSE412')):
            container, owner = 'cse412', 'Prisma (prisma/prisma)'
            repo = 'https://github.com/prisma/prisma'
        elif src.startswith(os.path.join(HOME, 'Projects', 'HisabKora')):
            container, owner = 'hisabkora', 'This library (hand-authored)'
        elif src.startswith(os.path.join(HOME, 'Projects', 'birthday')):
            container, owner = 'birthday', 'This library (hand-authored)'
        elif src.startswith(os.path.join(HOME, '.config', 'Code')):
            container = 'vscode-copilot-chat'
            owner, repo = 'GitHub (Copilot Chat)', \
                'https://github.com/microsoft/vscode-copilot-chat'
        elif src.startswith(os.path.join(HOME, '.cache')):
            container = 'uv-cache'
            owner, repo = 'Sebastián Ramírez (fastapi/typer)', \
                'https://github.com/fastapi/typer'
        elif src.startswith(os.path.join(HOME, '.codex')):
            container = 'codex-system'
            owner, repo = 'OpenAI (Codex)', 'https://github.com/openai/codex'
        elif src.startswith(os.path.join(HOME, '.gemini')):
            container, owner = 'gemini-antigravity', 'Google (Antigravity)'
        elif src.startswith(os.path.join(HOME, '.config/opencode')):
            container = 'opencode-installed'
            owner, repo = 'Affaan Mustafa (affaan-m/ECC)', \
                'https://github.com/affaan-m/ECC'
        elif src.startswith(os.path.join(HOME, '.config/ecc')):
            container = 'ecc-installed'
            owner, repo = 'Affaan Mustafa (affaan-m/ECC)', \
                'https://github.com/affaan-m/ECC'
        elif src.startswith(os.path.join(HOME, '.claude')):
            container, owner = 'claude-installed', 'Anthropic (Claude Code)'
        elif src.startswith(os.path.join(HOME, '.vscode/extensions')):
            container, owner = 'vscode-extension', 'Microsoft'
        elif src.startswith(os.path.join(HOME, 'Projects')):
            proj = src.split('/Projects/')[1].split('/')[0]
            container, owner = 'local-project:' + proj, 'Local project: ' + proj

    if lic is None:
        lic, path = nearest_license(src)
        if lic:
            lic_src = 'license file'
    if lic is None:
        lic, path = dist_info_license(src)
        if lic:
            lic_src = 'dist-info'
    return owner, repo, url, lic, lic_src, container


def verdict_for(name, src, lic):
    if src.startswith(PERSONAL_ROOTS) and name in PERSONAL_EXCLUDE:
        return 'personal'
    # A fixture is a test input that happens to look like a skill. It
    # is never published, whatever its licence says.
    if TEST_FIXTURE_PATH in src and name in TEST_FIXTURE_NAMES:
        return 'fixture'
    if lic is None:
        return 'restricted'
    if any(lic.startswith(p) for p in PERMISSIVE):
        return 'redistributable'
    return 'restricted'


def resolve(library_data=None):
    """The full per-entry provenance table."""
    if library_data is None:
        with open(os.path.join(BASE, '.library_data.json'), encoding='utf-8') as fh:
            library_data = json.load(fh)

    out = []
    for kind, key in (('skill', 'skills'), ('agent', 'agents'),
                      ('held_aside', 'excluded_agents')):
        for rec in library_data.get(key) or []:
            name = rec.get('name', '')
            src = rec.get('source') or ''
            owner, repo, url, lic, lic_src, container = describe(src)
            if lic is None:
                lic = frontmatter_license(rec, kind)
                if lic:
                    lic_src = 'frontmatter'
            # A declared upstream overrides the guess: the content is
            # somebody else's, and the licence and the owner are theirs.
            declared = DECLARED.get(name)
            if declared:
                lic = declared['license']
                lic_src = 'declared upstream'
                owner = declared['owner']
                repo = declared.get('repository') or repo
            elif name in PONYTAIL_SKILLS:
                # The upstream clone, kept whole. Its own LICENSE names
                # the author, so the credit goes to them and not to the
                # maintainer who happens to have cloned it.
                lic = PONYTAIL['license']
                lic_src = 'upstream clone'
                owner = PONYTAIL['owner']
                repo = PONYTAIL['repository']
                container = 'ponytail-clone'
            elif name in OWN_PACKS:
                # The maintainer's own pack: MIT, like the repository.
                lic = 'MIT'
                lic_src = 'own work'
                owner = 'This library (hand-authored)'
            out.append({
                'kind': 'agent' if kind == 'held_aside' else kind,
                'held_aside': kind == 'held_aside',
                'name': name,
                'path': rec.get('path'),
                'source': src,
                'owner': owner,
                'license': lic,
                'license_source': lic_src,
                'repository': repo,
                'url': url,
                'container': container,
                'verdict': verdict_for(name, src, lic),
            })
    return out


def main():
    rows = resolve()
    out_path = os.path.join(BASE, 'mcp', 'data', 'provenance.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(rows, fh, indent=2, sort_keys=True, ensure_ascii=False)
        fh.write('\n')

    import collections
    verdicts = collections.Counter(r['verdict'] for r in rows)
    print('provenance: %d entries' % len(rows))
    for k, c in verdicts.most_common():
        print('  %5d  %s' % (c, k))
    print('  -> %s' % out_path)


if __name__ == '__main__':
    main()
