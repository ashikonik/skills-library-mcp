#!/usr/bin/env python3
"""Agent Skills conformance: the rules, and the five exceptions.

The Skills extension serves this library's skills to MCP clients, and
the Agent Skills specification -- the format the extension is built on
-- has rules about what a skill's `name` and `description` may be:

  * `name` is 1-64 characters, lowercase letters, digits and hyphens
    only, no leading, trailing or doubled hyphen, and it **matches the
    name of the directory the skill lives in**;
  * `description` is 1-1024 characters;
  * `compatibility` is at most 500 characters.

Most of this library's skills satisfy all of that. A few do not, and
they fall into two kinds:

  * a `name` that breaks the rule -- an uppercase letter, an
    underscore -- which is *adapted* to a conforming name;
  * a `description` longer than 1,024 characters, which is *truncated*
    at a word boundary.

**The set of exceptions is data, not a constant.** The library grows,
and a new skill whose name breaks the rules becomes another
exception. So nothing here lists them: `conform_name` adapts any name
that does not conform, and the index records every adaptation it made.
The two names that could not be adapted mechanically -- `Zotero` and
`generative_ui`, whose adapted forms are conventional rather than
mechanical -- are named explicitly below; everything else is handled by
the general rule.

  ==========  ==================================  ====================
  skill       problem                             fix
  ==========  ==================================  ====================
  Zotero      uppercase `name`                    `zotero`
  generative_ui  underscore in `name`             `generative-ui`
  ==========  ==================================  ====================

**The vendored files are not edited.** They are third-party content
that must stay byte-identical to its upstream, and a patch applied here
would be lost the next time the library is re-scanned -- or worse, would
silently diverge from what the user actually installed.

So the fix lives *in the index*. The served skill carries a conforming
`name` and description; the file on disk keeps its own. The index
records both (`frontmatter.name` is the file's, `skills.name` is the
served one) and records that an override happened, so a caller can see
that the name it got is not the name in the file.

Two rules keep this honest:

  * The override is **only** applied where the file does not conform.
    A conforming skill is served exactly as it is on disk.
  * The override is **recorded**, never silent. `skills.json` carries
    `name_override` and `description_truncated`, and the servers report
    them, so a client can tell that the name it is looking at was
    adapted rather than read.

The truncation of a long description cuts it at a word boundary and
appends an ellipsis, so the served description stays readable and
still says what the skill is for.
"""
import re

# The Agent Skills naming rule: lowercase, digits and hyphens, no
# leading, trailing or doubled hyphen.
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

# The limits from the specification.
NAME_MAX = 64
DESCRIPTION_MAX = 1024
COMPATIBILITY_MAX = 500

# The two names that need adapting, and what they become. The directory
# is renamed in the served URI too, because the specification requires
# the final path segment to match the name -- and the directory
# `skills/Zotero` is itself the thing that cannot be renamed on disk.
#
# The value is the served name; the *directory* keeps its own name, and
# the servers resolve the URI through the index rather than through the
# filesystem path, so the mismatch is invisible to a client.
NAME_OVERRIDES = {
    'Zotero': 'zotero',
    'generative_ui': 'generative-ui',
}

# The skills whose description is too long to serve as one. The value
# is how many characters to keep; the rest is cut at a word boundary.
DESCRIPTION_LIMITS = {
    'heygen-video': 1000,
    'heygen-avatar': 1000,
    'twilio-enterprise-knowledge': 1000,
}


def is_valid_name(name):
    """Does `name` satisfy the Agent Skills naming rule?"""
    if not isinstance(name, str):
        return False
    if not 1 <= len(name) <= NAME_MAX:
        return False
    return bool(NAME_RE.match(name))


def is_valid_description(description):
    """Is `description` within the length the specification allows?"""
    if not isinstance(description, str):
        return False
    return 1 <= len(description) <= DESCRIPTION_MAX


def truncate_description(description, limit=DESCRIPTION_MAX):
    """Cut a long description at a word boundary.

    The cut keeps the description readable: it does not end mid-word,
    and it says that it was cut rather than pretending it is complete.
    """
    if not isinstance(description, str):
        return description, False
    if len(description) <= limit:
        return description, False
    cut = description[:limit]
    space = cut.rfind(' ')
    if space > limit // 2:
        cut = cut[:space]
    return cut.rstrip() + '...', True


def conform_name(name):
    """The name to serve for `name`.

    A conforming name is served unchanged. A non-conforming one is
    adapted: lowercased, and any run of characters that is not a letter
    or digit becomes a single hyphen. That turns `generative_ui` into
    `generative-ui` and `Zotero` into `zotero` without a table -- the
    table above is only for the cases where the automatic rule would
    give a different answer.

    The result is checked against the rule; if it still does not
    conform, it is truncated and re-checked, because a name that does
    not conform is a name a client cannot use as a directory.
    """
    if is_valid_name(name):
        return name, False
    if name in NAME_OVERRIDES:
        return NAME_OVERRIDES[name], True
    adapted = re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-')
    adapted = re.sub(r'-{2,}', '-', adapted)
    if len(adapted) > NAME_MAX:
        adapted = adapted[:NAME_MAX].rstrip('-')
    if not adapted:
        # A name with nothing usable in it still needs one.
        return 'skill', True
    return adapted, True


def conform_description(description, name=None):
    """The description to serve for `description`.

    A description within the limit is served unchanged. A long one is
    cut at a word boundary. The cut is recorded, because a client that
    compares the served description with the file's would otherwise see
    a mismatch it could not explain.
    """
    limit = DESCRIPTION_LIMITS.get(name, DESCRIPTION_MAX)
    return truncate_description(description, limit)


def check(name, description, compatibility=''):
    """The conformance report for one skill.

    Returns a dict with the served values and a list of the rules the
    skill broke. An empty `problems` list means the skill is served
    exactly as it is on disk.
    """
    served_name, renamed = conform_name(name)
    served_description, truncated = conform_description(description, name)

    problems = []
    if not is_valid_name(name):
        problems.append('name')
    if not is_valid_description(description):
        problems.append('description')
    if isinstance(compatibility, str) and len(compatibility) > COMPATIBILITY_MAX:
        problems.append('compatibility')

    return {
        'name': served_name,
        'description': served_description,
        'problems': problems,
        'name_override': renamed or None,
        'description_truncated': truncated or None,
    }
