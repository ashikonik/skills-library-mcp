#!/usr/bin/env python3
"""Validating the filters a caller passes to `search_library`.

A filter that names nothing is an error, not an empty result.

`domain: "Not A Domain"` used to answer `total_matched: 0`, which is
indistinguishable from "your query matched nothing". The caller has no
way to tell a typo from a genuinely empty library, and the most likely
explanation -- a misspelled or shortened domain -- goes undiagnosed.

So the filter values are checked against the index before the search
runs. A value that names no entry raises `FilterError`, and the error
names the valid values nearest to what was asked for.

The check is deliberately forgiving about *how* the value is written:

  * the match is case-insensitive -- "DevOps & cloud" and "devops &
    cloud" are the same domain;
  * an unambiguous prefix resolves -- "DevOps" is the only domain that
    starts with "devops", so it resolves to "DevOps & cloud";
  * a substring resolves when it is unique -- "cloud" is inside exactly
    one domain name.

What it will not do is guess. "data" is a prefix of several domains and
a substring of several more; it is ambiguous, and the error says so
rather than picking one.

The TypeScript side has the same module (`mcp/src/filters.ts`), and the
agreement test compares the two on every filter value in the index.
"""

import json


def _quote(value):
    """A value, quoted for the error message.

    The TypeScript side quotes with `JSON.stringify`, so this does the
    same: the two engines must produce the *same* message, and a
    message that differs only in its punctuation is still a message
    that differs.
    """
    return json.dumps(value, ensure_ascii=False)


class FilterError(Exception):
    """A filter argument that names nothing in the index.

    The server turns this into a tool error, so the caller sees the
    message rather than a silent empty result.

    It is deliberately *not* a `ToolError`: the two modules must not
    depend on each other, and the server catches this one by name and
    turns it into a tool error there.
    """

    def __init__(self, filter_name, value, valid, near):
        self.filter_name = filter_name
        self.value = value
        self.valid = valid
        self.near = near
        msg = 'Unknown %s %s.' % (filter_name, _quote(value))
        if near:
            msg += " Did you mean: %s?" % ', '.join(_quote(n) for n in near)
        else:
            msg += " Valid values are: %s." % ', '.join(_quote(v) for v in valid)
        super().__init__(msg)


# How many suggestions an error names. Enough to be useful, few enough
# to read.
NEAR_LIMIT = 5


def _normalise(value):
    """The comparison form of a filter value.

    Case is folded and the surrounding whitespace is dropped. Nothing
    else is changed: "Apache-2.0" and "apache-2.0" are the same
    licence, but "Apache 2.0" is not, and pretending otherwise would
    hide a real mistake.
    """
    return ' '.join((value or '').strip().lower().split())


def _distance(a, b):
    """The edit distance between two strings, as an integer.

    Levenshtein, with the usual unit costs. It is used only to rank
    the suggestions, so an exact value does not matter -- what matters
    is that the ranking is the same in both implementations, which it
    is, because the rule is stated here once and mirrored there.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(
                previous[j] + 1,          # deletion
                current[j - 1] + 1,       # insertion
                previous[j - 1] + (ca != cb),  # substitution
            ))
        previous = current
    return previous[len(b)]


def nearest(value, valid, limit=NEAR_LIMIT):
    """The values closest to `value`, nearest first.

    Ranking is by shared words, then by edit distance, then by the
    value itself.

    Shared words come first because a filter value is a *name*, and
    names are made of words. "Not A Domain" is not one character away
    from any domain -- it is two words away -- so edit distance alone
    ranks it randomly among forty equally-distant candidates. But it
    shares the word "domain" with several of them, and those are the
    ones the caller meant.

    The edit distance still matters, for the case where no word is
    shared: a typo in one word of a multi-word name.

    The tie-break on the value matters too: two suggestions at the same
    rank must come out in the same order in both engines, and neither
    engine's sort is stable in the same way.
    """
    want = _normalise(value)
    want_words = set(want.split())
    scored = []
    for v in valid:
        norm = _normalise(v)
        shared = len(want_words & set(norm.split()))
        d = _distance(want, norm)
        scored.append((-shared, d, v))
    scored.sort()
    return [v for _, _, v in scored[:limit]]


def resolve(filter_name, value, valid):
    """Resolve a filter value against the vocabulary `valid`.

    Returns the canonical value -- one of the strings in `valid` -- or
    raises `FilterError`.

    The resolution order is:

      1. an exact match, ignoring case and surrounding whitespace;
      2. a unique prefix -- "DevOps" -> "DevOps & cloud";
      3. a unique substring -- "cloud" -> "DevOps & cloud".

    A prefix or substring that matches more than one value is
    ambiguous, and is an error: the caller asked for something the
    library cannot answer unambiguously, and the error names the
    candidates.
    """
    if value is None:
        return None
    raw = ' '.join((value or '').strip().split())
    if not raw:
        # An empty filter is no filter.
        return None

    # 1. exact, ignoring case
    folded = raw.lower()
    for v in valid:
        if v.lower() == folded:
            return v

    # 2. a unique prefix
    prefixed = [v for v in valid if v.lower().startswith(folded)]
    if len(prefixed) == 1:
        return prefixed[0]
    if len(prefixed) > 1:
        raise FilterError(filter_name, raw, valid, sorted(prefixed))

    # 3. a unique substring
    contained = [v for v in valid if folded in v.lower()]
    if len(contained) == 1:
        return contained[0]
    if len(contained) > 1:
        raise FilterError(filter_name, raw, valid, sorted(contained))

    # Nothing matched at all. Suggest the nearest valid values.
    raise FilterError(filter_name, raw, valid, nearest(raw, valid))


def vocabulary(entries, domain_of, provenance_of):
    """The filter vocabulary of an index, as `{filter: [values]}`.

    `domain_of` and `provenance_of` read the two fields the filters
    read, so the vocabulary cannot drift from the data.
    """
    domains = set()
    sources = set()
    licenses = set()
    verdicts = set()
    for e in entries:
        d = domain_of(e)
        if d:
            domains.add(d)
        p = provenance_of(e) or {}
        s = p.get('container')
        if s:
            sources.add(s)
        lic = p.get('license')
        if lic:
            licenses.add(lic)
        v = p.get('verdict')
        if v:
            verdicts.add(v)
    return {
        'domain': sorted(domains),
        'source': sorted(sources),
        'license': sorted(licenses),
        'verdict': sorted(verdicts),
    }
