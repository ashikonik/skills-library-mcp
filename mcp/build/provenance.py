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
  included-with-terms
                    the licence does *not* permit redistribution, but the
                    repository's owner instructed that the entry be shipped
                    anyway. The upstream's terms are quoted verbatim in the
                    NOTICE, so the reader sees exactly what they are.
  restricted        anything else -- Proprietary, UNLICENSED, a LicenseRef,
                    or no licence stated anywhere. Such content cannot be
                    published, because publishing it would grant rights the
                    author did not grant.
  personal          the maintainer's own project files. They leak machine
                    paths and belong to a private repository.
  fixture           a test input that happens to look like a skill. It is
                    never published, whatever its licence says.

The `included-with-terms` verdict is a decision by the repository's
owner, not a licence judgement. It exists because the owner asked for
these entries to be shipped and accepted that this redistributes
material whose terms do not grant it. The verdict records that as an
explicit, attributed exception rather than leaving it implied.

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
from packs import (                    # noqa: E402
    names as pack_names,
    licence_of as pack_licence,
    publishable as pack_publishable,
    packs as pack_records,
)

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
    # `review-agent` ships inside the Codex binary, with no licence file
    # beside it, so the resolver found no terms and called it
    # restricted. The same file is published verbatim in OpenAI's own
    # `codex` repository, which is Apache-2.0 -- `SKILL.md` and
    # `agents/openai.yaml` are byte-identical to the copies under
    # `codex-rs/skills/src/assets/samples/review-agent/`. So the terms
    # are known, and they permit redistribution.
    'review-agent': {
        'license': 'Apache-2.0',
        'owner': 'OpenAI (Codex)',
        'repository': 'https://github.com/openai/codex',
    },
}

# The entries whose terms were investigated and found not to permit
# redistribution, or not to exist at all. Each one gets the reason
# that the investigation actually established, so the NOTICE states a
# finding rather than a shrug. The licence is left as it was found --
# these entries stay excluded either way -- but the reason is recorded
# per entry, which is what `reason_for` falls back to.
EXCLUSION_REASONS = {
    'claude-security': "Anthropic's own LICENSE says the plugin is "
                       "proprietary and that it may not be made available "
                       "to any third party",
    'explore': "Anthropic's own LICENSE says the plugin is proprietary and "
               "that it may not be made available to any third party",
    'patch-generator': "Anthropic's own LICENSE says the plugin is "
                       "proprietary and that it may not be made available "
                       "to any third party",
    'patch-verifier': "Anthropic's own LICENSE says the plugin is "
                       "proprietary and that it may not be made available "
                       "to any third party",
    'scan-inventory': "Anthropic's own LICENSE says the plugin is "
                      "proprietary and that it may not be made available "
                      "to any third party",
    'scan-loader': "Anthropic's own LICENSE says the plugin is proprietary "
                   "and that it may not be made available to any third party",
    'scan-researcher': "Anthropic's own LICENSE says the plugin is "
                        "proprietary and that it may not be made available "
                        "to any third party",
    'scan-verifier': "Anthropic's own LICENSE says the plugin is "
                     "proprietary and that it may not be made available "
                     "to any third party",
    'pylance-docs': "Microsoft's Pylance licence, clause 2(e): you may not "
                    "share, publish, distribute, or lease the software",
    'pylance-python-profiling': "Microsoft's Pylance licence, clause 2(e): "
                                "you may not share, publish, distribute, or "
                                "lease the software",
    'pylance-refactoring': "Microsoft's Pylance licence, clause 2(e): you "
                            "may not share, publish, distribute, or lease "
                            "the software",
    'python-fact-grounded-coding': "Microsoft's Pylance licence, clause "
                                   "2(e): you may not share, publish, "
                                   "distribute, or lease the software",
    'agy-customizations': "Antigravity is proprietary Google software with "
                          "its own terms of service",
    'antigravity-guide': "Antigravity is proprietary Google software with "
                          "its own terms of service",
    'automation': "Antigravity is proprietary Google software with its own "
                  "terms of service",
    'generative_ui': "Antigravity is proprietary Google software with its "
                      "own terms of service",
    'migrate-workflows': "Antigravity is proprietary Google software with "
                          "its own terms of service",
    'permissioned-github': "Antigravity is proprietary Google software with "
                           "its own terms of service",
    'plugin': "Antigravity is proprietary Google software with its own terms "
              "of service",
    'report_researcher': "Antigravity is proprietary Google software with its "
                         "own terms of service",
    'run-workflow': "Antigravity is proprietary Google software with its own "
                    "terms of service",
    'ui-plugin-navigation': "Antigravity is proprietary Google software with "
                            "its own terms of service",
    'plugin-creator': "ships inside the Codex binary and is not published in "
                      "OpenAI's Apache-2.0 codex repository, so no terms "
                      "accompany it",
    'provision-droplet': "the digitalocean/CodexPlugin repository has no "
                         "LICENSE file and its manifest names no licence",
    'magicpath': "the manifest says UNLICENSED and the upstream repository "
                 "has no LICENSE file, so no rights are granted",
    'Ask': "ships in the Copilot Chat extension, not in the MIT-licensed "
           "vscode-copilot-chat repository",
    'Explore': "ships in the Copilot Chat extension, not in the MIT-licensed "
               "vscode-copilot-chat repository",
    'Plan': "ships in the Copilot Chat extension, not in the MIT-licensed "
            "vscode-copilot-chat repository",
    'ecc-coordinator': "an installed opencode agent with no upstream copy on "
                       "the machine, so no terms could be found",
    'document-builder': "this pack vendors Anthropic's document skills, "
                        "whose terms forbid redistribution, so the pack "
                        "cannot be shipped whole",
}

# The terms that could not be established from the tree, checked
# against the upstream by hand. Each of these was investigated; the
# note records what was found, so the next person does not have to
# repeat the search. An entry whose terms forbid redistribution stays
# excluded -- a credits entry cannot turn a prohibition into a
# permission -- and the reason is written down here rather than left
# as a silent gap.
#
# The Anthropic plugin (`claude-security`) carries its own LICENSE,
# which says the plugin "is proprietary to Anthropic, PBC" and that
# "you may not ... distribute, publish, sublicense, sell, or otherwise
# make the Plugin or any modified version of it available to any third
# party". Nine entries are covered by it.
#
# Figma's Developer Terms (`LicenseRef-Figma-Developer-Terms`) cover
# the sixteen `figma-*` entries. They are published by OpenAI but
# written by Figma, and Figma's terms govern them.
#
# The Pylance extension's own licence is a Microsoft Software License
# whose clause 2(e) says "You may not: ... share, publish, distribute,
# or lease the software". The resolver reported it as "other
# (unrecognised)" because the text is not one of the standard licences
# it knows -- the terms are perfectly clear, and they forbid
# redistribution.
#
# Google's Antigravity is proprietary software with its own terms of
# service; the ten entries built into it carry no open licence.
#
# The OpenAI plugin marketplace declares its own terms per plugin.
# `life-science-research`, `codex-security`, `openai-developers`,
# `hex` and `openai-ads-conversions` are "Proprietary"; the
# `openai-templates` and `plugin-management` caches are too. Other
# plugins in the same repository -- `notion`, `remotion`, `github`,
# `gmail` -- are MIT, and the resolver already publishes those.
#
# `plugin-creator` ships inside the Codex binary but is NOT in the
# Apache-2.0 `codex` repository, so the terms cannot be established
# from an upstream that is published.
#
# `MagicPathAI/agent-skills` is a public repository with no LICENSE
# file and a manifest that says "UNLICENSED". No permission is
# granted, so nothing is.
#
# `digitalocean/CodexPlugin` has no LICENSE file and its manifest
# names no licence.
#
# The three Copilot Chat agents (`Ask`, `Explore`, `Plan`) come from
# the installed VS Code extension's global storage. The
# `microsoft/vscode-copilot-chat` repository is MIT, but it does not
# contain these agent definitions -- they ship in the extension, under
# Microsoft's product terms.
#
# `ecc-coordinator` is an installed opencode agent with no upstream
# copy anywhere on the machine, so no terms can be found for it.
#

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
# The list lives in `packs.json`, so that adding a pack is a one-file edit
# rather than a hunt through this resolver.
#
# A pack is excluded from publication when the manifest marks it
# `restricted`: `document-builder` is the maintainer's own work, but it
# vendors Anthropic's docx/pptx/xlsx/pdf skills whose terms forbid
# redistribution, so the pack as a whole cannot be published. Saying so
# is more honest than shipping half of it.
OWN_PACKS = tuple(pack_names())

# The packs that may be published. A pack outside this set is not
# published, whatever its licence says.
PUBLISHABLE_PACKS = set(pack_publishable())

# The packs the manifest marks as restricted, with the reason.
RESTRICTED_PACKS = {
    p['name']: p.get('restricted_reason', 'its licence does not permit '
                     'redistribution')
    for p in pack_records() if p.get('restricted')
}

# The packs the manifest marks as published-under-terms: the owner
# instructed that they ship even though the terms do not grant
# redistribution.
INCLUDED_PACKS = {
    p['name']: p.get('included_with_terms_reason', 'published at the '
                     "owner's instruction, under terms that do not grant "
                     'redistribution')
    for p in pack_records() if p.get('included_with_terms')
}

# Test fixtures, not content. The `plugin-eval` plugin ships example
# plugins under `fixtures/`, and the scanner picks their skills up like
# any other's. They are placeholder skills -- "alpha", "beta",
# "minimal-plugin-skill" -- and publishing them would put three
# meaningless entries in the catalogue and three odd author names in
# the credits. They are excluded for the same reason the personal files
# are: they are not the work anybody shipped.
TEST_FIXTURE_NAMES = ('alpha', 'beta', 'minimal-plugin-skill')
TEST_FIXTURE_PATH = os.path.join('fixtures', '')


# The entries the repository's owner instructed to be published even
# though their terms do not grant redistribution.
#
# This is an explicit, attributed exception, not an oversight: the
# upstream terms were read, they forbid redistribution, and the owner
# asked for the content anyway. The NOTICE quotes each upstream's terms
# so a reader can see exactly what they are, and names the author of
# every entry so the credit is unambiguous.
#
# The list is by *owner*, not by entry, so that adding another skill
# from one of these upstreams does not silently change the licence
# posture of the repository. A new upstream has to be added here
# deliberately.
INCLUDE_WITH_TERMS = {
    # OpenAI's plugin repository declares most of its plugins
    # "Proprietary". The terms are published in the repository's own
    # LICENSE file and forbid redistribution.
    'OpenAI': 'OpenAI declares this plugin proprietary; the repository '
              'LICENSE permits use by the licensee only.',
    # Figma's Developer Terms govern the Figma plugin skills. The terms
    # grant Figma a licence to distribute them as part of the Figma
    # product, not to third parties.
    'Figma': "Figma's Developer Terms govern this work; they grant Figma "
             'a licence to distribute it as part of the Figma product.',
    # Antigravity is proprietary Google software with its own terms of
    # service, and no licence accompanies these entries.
    'Google (Antigravity)': 'Antigravity is proprietary Google software '
                             'with its own terms of service, and no licence '
                             'accompanies these entries.',
    # Anthropic's plugin LICENSE says the plugin is proprietary to
    # Anthropic, PBC, and may not be made available to any third party.
    'Anthropic': "Anthropic's LICENSE says the plugin is proprietary to "
                 'Anthropic, PBC, and may not be made available to any '
                 'third party.',
    # Microsoft's Pylance licence, clause 2(e): you may not share,
    # publish, distribute, or lease the software.
    'Microsoft': "Microsoft's Pylance licence, clause 2(e): you may not "
                 'share, publish, distribute, or lease the software.',
    # These three agents ship in the Copilot Chat extension, not in the
    # MIT-licensed vscode-copilot-chat repository.
    'GitHub (Copilot Chat)': 'ships in the Copilot Chat extension, not in '
                              'the MIT-licensed vscode-copilot-chat '
                              'repository',
    # The manifest says UNLICENSED and the upstream repository has no
    # LICENSE file, so no rights are granted.
    'MagicPathAI': 'the manifest says UNLICENSED and the upstream '
                   'repository has no LICENSE file, so no rights are granted',
    # Ships inside the Codex binary and is not published in OpenAI's
    # Apache-2.0 codex repository, so no terms accompany it.
    'OpenAI (Codex)': 'ships inside the Codex binary and is not published in '
                       "OpenAI's Apache-2.0 codex repository, so no terms "
                       'accompany it',
    # The digitalocean/CodexPlugin repository has no LICENSE file and its
    # manifest names no licence.
    'DigitalOcean': 'the digitalocean/CodexPlugin repository has no LICENSE '
                     'file and its manifest names no licence',
    # An installed opencode agent with no upstream copy on the machine, so
    # no terms could be found.
    'Affaan Mustafa (affaan-m/ECC)': 'an installed opencode agent with no '
                                      'upstream copy on the machine, so no '
                                      'terms could be found',
    # The maintainer's own pack, which vendors Anthropic's document
    # skills under `vendor/`. Their LICENSE says the materials may not be
    # extracted from the Services, copied, or distributed to any third
    # party -- which is precisely what shipping the pack would do. The
    # pack's own work (the SKILL.md and the references) is the
    # maintainer's; the vendored copies are Anthropic's.
    'This library (hand-authored)': "this pack vendors Anthropic's document "
                                    'skills, whose licence forbids '
                                    'extracting them from the Services, '
                                    'copying them, or distributing them to '
                                    'any third party',
}


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


def verdict_for(name, src, lic, owner=None):
    if src.startswith(PERSONAL_ROOTS) and name in PERSONAL_EXCLUDE:
        return 'personal'
    # A fixture is a test input that happens to look like a skill. It
    # is never published, whatever its licence says.
    if TEST_FIXTURE_PATH in src and name in TEST_FIXTURE_NAMES:
        return 'fixture'
    # A pack the manifest marks as restricted cannot ship whole, because
    # something it vendors does not permit redistribution.
    if name in RESTRICTED_PACKS:
        return 'restricted'
    # A pack the manifest marks as included-under-terms ships, but on the
    # owner's instruction rather than on the licence.
    if name in INCLUDED_PACKS:
        return 'included-with-terms'
    if lic is not None and any(lic.startswith(p) for p in PERMISSIVE):
        # The licence permits redistribution. That decides it, whatever
        # the owner is -- an entry whose terms allow redistribution is
        # published on the strength of those terms, not on an exception.
        return 'redistributable'
    # The owner asked for these to be shipped. The terms still do not
    # grant redistribution, so the verdict says so explicitly and the
    # NOTICE quotes them.
    if owner in INCLUDE_WITH_TERMS:
        return 'included-with-terms'
    if lic is None:
        return 'restricted'
    return 'restricted'


# The licences that forbid redistribution outright, as opposed to the
# ones that simply could not be identified. The distinction matters in
# the NOTICE: "we could not find the terms" is a gap in the research,
# and "the terms forbid it" is an answer. Both keep the entry out of
# the tree, but only one of them is a decision.
NON_PERMISSIVE = {
    'Proprietary': 'the upstream declares the work proprietary',
    'UNLICENSED': 'the upstream declares no licence, so grants no rights',
    'LicenseRef-Figma-Developer-Terms':
        "Figma's Developer Terms govern this work",
    'SEE LICENSE IN LICENSE':
        "the upstream's own licence forbids redistribution",
    'other (custom terms)': 'the upstream uses terms of its own',
}


def reason_for(verdict, lic, owner=None, name=None):
    """Why an entry is published or not, in words.

    A verdict of "restricted" is a decision, and the decision should be
    legible: either the upstream's terms forbid redistribution, or the
    terms could not be established. Those are different facts, and a
    reader of the NOTICE is entitled to know which one applies.

    For "included-with-terms" the reason is the upstream's own position,
    quoted rather than summarised: this entry is published despite those
    terms, and the reader is entitled to see them.
    """
    if verdict == 'redistributable':
        return ''
    if verdict == 'fixture':
        return 'a test fixture, not published content'
    if verdict == 'personal':
        return "the maintainer's own file from a private project"
    if verdict == 'included-with-terms':
        # The upstream's terms, as read from the source, and the fact
        # that they do not grant redistribution.
        if name in INCLUDED_PACKS:
            return INCLUDED_PACKS[name]
        detail = INCLUDE_WITH_TERMS.get(owner)
        if detail:
            return detail
        if name in EXCLUSION_REASONS:
            return EXCLUSION_REASONS[name]
        if lic in NON_PERMISSIVE:
            return NON_PERMISSIVE[lic]
        return ('the upstream terms do not grant redistribution, and the '
                'repository owner instructed that this entry be published '
                'anyway')
    # A reason that was established by investigating this particular
    # entry beats a general rule about its licence.
    if name in EXCLUSION_REASONS:
        return EXCLUSION_REASONS[name]
    if lic in NON_PERMISSIVE:
        return NON_PERMISSIVE[lic]
    if owner == 'Google (Antigravity)':
        return ('Antigravity is proprietary software with its own terms '
                'of service, and no licence accompanies these entries')
    if lic:
        return 'the terms could not be established as permitting redistribution'
    return 'no licence was found'


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
                # The maintainer's own pack. The licence comes from the
                # pack's own LICENSE file when it has one -- the file is
                # the author's own statement of terms -- and from the
                # manifest otherwise.
                lic = pack_licence(name) or 'MIT'
                lic_src = ('own work (%s)' % lic) if lic != 'MIT' else 'own work'
                owner = 'This library (hand-authored)'
            verdict = verdict_for(name, src, lic, owner)
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
                'verdict': verdict,
                # Why this entry is not published, in words. The NOTICE
                # prints it, so the reason is a recorded finding rather
                # than a gap somebody has to re-investigate.
                'reason': reason_for(verdict, lic, owner, name),
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
