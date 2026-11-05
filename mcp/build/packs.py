#!/usr/bin/env python3
"""The library's own packs, read from one manifest.

`packs.json` names every hand-authored pack at the library root, with its
licence, its minimum file count, and the prose that the guide and the report
print about it. Five scripts need that information, and they used to each
hardcode their own copy of it -- so a new pack meant editing five places,
and forgetting one meant a pack that was tier 1 but not credited, or
credited but not in the guide.

This module is the single reader. The rules it encodes:

  * **A pack's own LICENSE file wins.** The file is the author's own
    statement of terms; a manifest that disagreed with it would be the
    manifest lying. `skill-creator-plus` is the case that proves it: the
    manifest says Apache-2.0 because the file says so.

  * **A pack with no licence file of its own is this repository's own
    work**, and this repository is MIT.

  * **A pack can be marked `restricted`.** `document-builder` was the
    case: it is the maintainer's own work, but it vendors Anthropic's
    document skills whose terms forbid redistribution. The repository
    owner instructed that it be shipped anyway, so the manifest marks it
    `included_with_terms` instead -- a recorded decision, not an
    oversight. The NOTICE quotes the vendored terms verbatim.

The manifest is read once and cached, because five scripts ask for it in
one build and the file does not change mid-build.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, 'packs.json')

_cache = None


def _load():
    global _cache
    if _cache is None:
        with open(MANIFEST, encoding='utf-8') as fh:
            _cache = json.load(fh)
    return _cache


def packs():
    """Every pack, in manifest order."""
    return list(_load()['packs'])


def names():
    """The pack names, in manifest order."""
    return [p['name'] for p in packs()]


def by_name(name):
    """One pack's record, or None."""
    for p in packs():
        if p['name'] == name:
            return p
    return None


def licence_of(name):
    """The licence a pack is redistributed under.

    A `LICENSE` file inside the pack wins over the manifest, because the
    file is the author's own statement of terms. Otherwise the manifest
    decides.
    """
    rec = by_name(name)
    if rec is None:
        return None
    path = os.path.join(os.path.dirname(HERE), '..', name)
    path = os.path.normpath(path)
    for candidate in ('LICENSE', 'LICENSE.txt', 'LICENSE.md', 'COPYING'):
        p = os.path.join(path, candidate)
        if not os.path.isfile(p):
            continue
        try:
            txt = open(p, encoding='utf-8', errors='replace').read(4000)
        except OSError:
            continue
        low = txt.lower()
        if 'apache license' in low:
            return 'Apache-2.0'
        if 'mit license' in low or 'permission is hereby granted' in low:
            return 'MIT'
        if 'gnu general public' in low:
            return 'GPL'
        if 'mozilla public' in low:
            return 'MPL'
        if 'isc license' in low:
            return 'ISC'
        if 'bsd' in low and 'redistribution' in low:
            return 'BSD'
        return rec.get('license')
    return rec.get('license')


def is_restricted(name):
    """Is this pack excluded from the published tree?

    Two reasons, and they are different:

      * the manifest marks it `restricted` -- its own licence permits
        redistribution, but something it vendors does not;
      * its licence is not one that permits redistribution.

    A pack marked `included_with_terms` is *not* restricted: the owner
    instructed that it be shipped even though the terms do not grant
    redistribution. It is published, and the NOTICE quotes the terms.
    """
    rec = by_name(name)
    if rec is None:
        return False
    if rec.get('restricted'):
        return True
    lic = (licence_of(name) or '').upper()
    return not any(lic.startswith(p) for p in
                   ('MIT', 'APACHE-2.0', 'APACHE', 'BSD', 'ISC', 'MPL', 'CC-BY'))


def included_with_terms():
    """The packs that are published under terms that do not grant
    redistribution, at the owner's instruction."""
    return [p['name'] for p in packs() if p.get('included_with_terms')]


def publishable():
    """The packs that may be published, in manifest order."""
    return [p['name'] for p in packs() if not is_restricted(p['name'])]


if __name__ == '__main__':
    # A quick self-check, so the module can be run standalone.
    for p in packs():
        if p.get('included_with_terms'):
            state = 'INCLUDED (terms)'
        elif is_restricted(p['name']):
            state = 'RESTRICTED'
        else:
            state = 'publishable'
        print('%-22s %-12s min_files=%-4d %s'
              % (p['name'], licence_of(p['name']), p.get('min_files', 1), state))
    print()
    print('%d packs, %d publishable' % (len(packs()), len(publishable())))
