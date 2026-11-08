#!/usr/bin/env python3
"""Pure lexical search over the library index.

No embeddings, on purpose:

  * the server must start offline, per session, with no model download
  * a lexical scorer can be implemented independently in Python and
    TypeScript and be **required to agree exactly** -- an embedding
    scorer cannot be re-implemented by hand, and model drift would
    silently change results
  * the corpus carries its own supervision: `metadata.promptSignals`
    holds 18 skills' worth of hand-curated activation phrases, and an
    exact hit on one of them beats any fuzzy similarity

Scoring
-------
    idf(t)       = ln(1 + N / df(t))            N = number of entries
    name_exact   = 3.0 * idf(t)   t is a name token
    name_partial = 1.5 * idf(t)   t is a prefix of a name token
    desc_match   = 1.0 * idf(t)   t is a description token
    phrase       = 6.0            a query bigram matches a name bigram
    signal       = 8.0            t is in metadata.promptSignals.phrases
    task_match   = 25.0           the query matches a row of the task index
    task_content = 8.0            the query has the row's content, verb dropped
    task_head    = 16.0           the row's content is the query's HEAD noun
    tier_bias    = +1.0 / +0.25 / 0.0
    agent_bias   = +0.5

The tier bias is multiplied by `(1 - name_exact_hit)`: tiering must never
override a direct name match, it only breaks ties among weak,
description-only matches. The maximum tier bias (1.0) is well below a
single idf contribution (~3.0-6.0), so it cannot reorder a strong match.

Two rules filter the scored entries:

  token coverage -- an entry must match two thirds of the query's
                    *distinctive* tokens, and at least two of them
                    when the query has two or more. A distinctive
                    token is one that appears in fewer than 1.8% of
                    the corpus; a common word like "write" carries no
                    information about which entry the query wants.

  task rows      -- a hand-written row of the task index fires when
                    the query has 60% of the row's tokens (the strict
                    match, full bonus) or all of the row's *content*
                    -- the row's tokens with its leading verb dropped
                    (the content match, smaller bonus). "write a REST
                    API" is the "Build an API" row.

                    A content match whose token is the query's HEAD
                    noun -- the thing the query is *about*, not the
                    context it mentions -- earns more than a plain
                    content match. "write a REST API" is about an API,
                    so the "Build an API" row fires; "add
                    authentication to an api" is about
                    authentication, so the row does not fire and the
                    authentication skill keeps the top slot.

Results are limited three ways, so a query never returns every row:

  1. score threshold -- only `score > 0`; a pure-stopword query returns 0
  2. hard cap -- `limit`, default 10, max 50
  3. relevance floor -- drop hits below `0.25 * topScore`

Tie-break order is fixed, because the TypeScript server must produce the
identical ordering: score desc, tier asc, skill before agent, shorter name
first, then lexicographic name.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(BASE, 'mcp', 'build'))
sys.path.insert(0, os.path.join(BASE, 'mcp', 'python'))

from build_index import tokenize, bigrams, head_tokens, STOPWORDS   # noqa: E402
import protocol   # noqa: E402
import filters    # noqa: E402


DEFAULT_LIMIT = 10
MAX_LIMIT = 50
RELEVANCE_FLOOR = 0.25
# The discount applied to a description match that was found through
# the inflection rule rather than an exact token. See `_inflections`.
MORPH_DISCOUNT = 0.6

WEIGHT_NAME_EXACT = 3.0
WEIGHT_NAME_PARTIAL = 1.5
WEIGHT_DESC = 1.0
WEIGHT_PHRASE = 6.0
WEIGHT_SIGNAL = 8.0
WEIGHT_TASK = 25.0
# A task row can fire two ways, and they are not equally strong.
#
# The strict match -- 60% of the row's own tokens are in the query --
# means the query used the row's words, and earns the full bonus.
#
# The content match -- the row's content is present, verb dropped --
# only means the query named the object. "add authentication to an api"
# contains "api", which fires the "Build an API" row; at the full
# bonus that pushed `twilio-security-api-auth` -- the skill that is
# actually about authentication -- down to fifth. A smaller bonus
# keeps the row's skills in the running without outranking the more
# specific match.
WEIGHT_TASK_CONTENT = 8.0
# A HEAD match -- the row's content token is the query's head noun --
# is stronger evidence than a mere content match, because position
# says what the query is *about*.
#
# "write a REST API" is about an API, so the "Build an API" row fires.
# "add authentication to an api" is about authentication, and "api" is
# only the thing being added to, so the row does not fire and the
# authentication skill keeps the top slot.
WEIGHT_TASK_HEAD = 16.0
# On a HEAD match, the row's FIRST entry earns the row's full bonus
# (`WEIGHT_TASK`), and the alternatives earn the head bonus. The row
# already says which entry it recommends -- `api-design` is listed
# first for "Build an API" -- so this applies the table's own curation
# instead of a new constant.
#
# Why the split matters. The comparison that decides "write a REST
# API" reduces, in closed form, to
#
#     diff = HEAD - PHRASE - 3*idf(rest) + idf(api)
#
# and the idf part is corpus-dependent: `df(rest)` was 20 in one tree
# and 12 in the other, so idf(rest) moved from 4.006 to 4.376 while
# the fixed bonuses stayed put. With one bonus for every member of the
# row the margin was +0.199 locally and -0.810 in the smaller tree --
# the same query, two answers. With the split the margin is +9.2 and
# +8.2, because the curated signal now outweighs the drift in the
# automatic evidence instead of merely competing with it.
WEIGHT_TASK_HEAD_FIRST = WEIGHT_TASK
# A task row's *first* entry is its documented first choice; the rest
# are alternatives. The row's note says so in prose -- "`api-design`
# covers resource naming, ...", "Use the build resolver for the
# language" -- but the scorer cannot read prose, so the order was lost
# and the row's members were ranked only by whatever their names
# happened to score.
#
# A strict match therefore demotes the row's later members by this
# amount. Demoting rather than promoting matters: the relevance floor
# is a fraction of the *top* score, so raising the ceiling can evict a
# weaker but relevant entry from the bottom of the list. Measured over
# the labelled query set, demoting 3.0 lifts rank-1 and rank-3 counts
# while evicting nothing; the content branch is left alone, because a
# content match says the query named the row's object, not that it
# asked for that specific task.
# A task row's *first* entry is its documented first choice; the rest
# are alternatives. The row's note says so in prose -- "`api-design`
# covers resource naming, ...", "Use the build resolver for the
# language" -- but the scorer cannot read prose, so the order was lost
# and the row's members were ranked only by whatever their names
# happened to score.
#
# The row's later members are therefore demoted, by a *fraction* of the
# row's bonus, scaled by how deep they sit in the row. The fraction
# and the cap were measured over the labelled query set; see
# `mcp/scripts/eval_search.py`.
#
# The row's order is the row's curation in *both* branches -- whether
# the query named the row's verb or only its object. "write SQL"
# names the row's object ("sql") but not its verb ("write"), so the
# content branch fires -- and without the demotion
# `database-reviewer` won: the agent is tier 1 while
# `postgres-patterns` is tier 2, so the tier bias and the agent bonus
# together put it ahead of the skills the row had been asked for.
TASK_DEMOTE_FRACTION = 0.6
# The demotion does not keep growing with depth. A row's third or
# fourth member is a real alternative, not a worse version of the
# first, and an unbounded demotion would push it out of the results
# entirely rather than down the list.
TASK_DEMOTE_MAX_DEPTH = 3
# The demotion is also capped in absolute terms.
#
# A pure fraction of the bonus is not enough on its own. The strict
# bonus is 25.0, so a depth-3 member of a long row would give up
# 25.0 * 0.6 * 3 = 45.0 -- more than the whole bonus, which put the
# row's agents at a *negative* score. The row "Fix a failing build"
# lists `error-handling` first and the `build-*-resolver` agents
# fourth, fifth and sixth, and they are exactly what the query wants:
# the agents fell out of the top ten entirely.
#
# The cap says the demotion is a nudge, not a ban. A row's later
# members stay reachable; the row's first choice leads.
TASK_DEMOTE_MAX = 15.0
TIER_BIAS = {1: 1.0, 2: 0.25, 3: 0.0}
AGENT_BIAS = 0.5

# A token is "generic" when it appears in more than this fraction of the
# corpus. Generic tokens are excluded from the token-coverage
# requirement: the requirement exists to stop a single common word from
# matching everything, but it must require the *discriminating* tokens.
#
# "write documentation" is the case that forced this. The rule demanded
# two of the query's two tokens, so `documentation-lookup` and
# `notion-research-documentation` -- whose names contain
# "documentation" -- were dropped for not also containing "write", and
# the only survivor was `mixpanelyst`, which mentions both words in its
# description and nothing else.
#
# 1.8% of the corpus is about 19 documents. A token in 20 or more is
# common enough that requiring it is a filter on luck rather than on
# relevance. The ratio was chosen by measuring, over a labelled query
# set, how many entries each threshold let through and where the
# wanted skill ended up -- see `mcp/scripts/eval_unified.py`.
GENERIC_TOKEN_DF_RATIO = 0.018

# Scores are compared with a tolerance, not with raw float equality.
#
# Two entries that match the same query tokens score the *same* sum, but
# the terms arrive in a different order, so the floating-point addition
# lands on a different last bit. The difference is around 1e-15 -- far
# below anything a reader could call a different score -- but the sort
# compared the raw doubles, so the noise decided the order and the
# documented tie-break (tier, kind, shorter name, name) never ran.
#
# "machine learning model training" is the case that showed it:
# `pytorch-patterns`, `ml-adoption-playbook` and `huggingface-llm-trainer`
# all score 12.7920798526549..., differing by 2e-15, and their order
# changed every time the corpus grew by one entry.
#
# The quantum is 1e-6: a millionth of a point. A real score difference --
# the smallest the weights can produce is an idf step, which is several
# hundredths -- is far above it, so this only groups together scores that
# are the same score.
#
# The scale is an integer so that both engines compute the same key:
# IEEE 754 multiplication is exactly specified, so `score * SCORE_SCALE`
# is bit-identical in Python and JavaScript, and `trunc` is exact.
SCORE_SCALE = 1000000


def score_key(score):
    """The score as an integer, for comparison with a tolerance."""
    return int(math.trunc(score * SCORE_SCALE))


def codepoint_compare(a, b):
    """Compare two strings by unicode code point.

    Python's `str` already compares by code point, so this is the
    identity on ordering -- but it is named, exported and used
    explicitly so that the two implementations state the same rule in
    the same place. The TypeScript side cannot say the same thing: JS's
    `<` compares UTF-16 code units, which orders astral characters
    differently, so it needs an explicit comparator (`codepointCompare`
    in `mcp/src/search.ts`).

    Library names are ASCII today, and the tokenizer only ever emits
    `[a-z0-9]` tokens, so the astral case cannot arise from a real
    search. It is spelled out anyway: a tie-break that silently changes
    its ordering rule is the kind of thing that gets discovered a year
    later, in a diff nobody reads.
    """
    return (a > b) - (a < b)


def _code_point_key(s):
    """The sort key for a code-point ordering.

    Python's `str` comparison is already a code-point comparison, so
    the key is the string itself. It is wrapped in a function so that
    the rule is named at the call site rather than implied by which
    `sorted` overload happens to be used.
    """
    return s


def _phrase_tokens_match(phrase, q_tokens):
    """Do all of the phrase's content words appear in the query?

    The phrase is tokenized with the same tokenizer as the query, so the
    function words inside a phrase ("the page is stuck") drop out and only
    the content words have to be present. The order does not matter:
    "stuck page" and "page stuck" are the same symptom.

    This is deliberately stricter than the substring test. `vercel-cli`
    lists "build failed" among its symptoms, and a query of "fix a
    failing build" contains neither the phrase nor the word "failed" --
    so `vercel-cli` earns no credit for a build failure it cannot fix.
    """
    p_toks = tokenize(phrase)
    if not p_toks:
        return False
    q_set = set(q_tokens)
    return all(t in q_set for t in p_toks)


_MORPH_CACHE = {}


def _inflections(tok):
    """The inflected forms of a token -- what a description may use.

    English spells the same word several ways, and a description that
    says "drafting" does not contain the word "draft". Without this,
    "triage my inbox and draft the replies" missed
    `email-ops`, whose description says "mailbox triage, drafting,
    ...", and "review my code for security problems" missed
    `security-review` for the same reason.

    The rule is deliberately narrow: it adds only the suffixes English
    actually inflects. It is NOT a prefix rule. "late" does not match
    "latency" and "plant" does not match "plantation", because a
    prefix rule matches any word that happens to start the same way,
    and those are coincidences of spelling rather than inflections.

    The TypeScript side has the same function, and the agreement test
    compares the two on every query.
    """
    out = set()
    if tok.endswith('y') and len(tok) > 3:
        out.add(tok[:-1] + 'ies')
    if tok.endswith(('s', 'x', 'z', 'ch', 'sh')) and len(tok) > 3:
        out.add(tok + 'es')
    if len(tok) > 2:
        out.add(tok + 's')
    if len(tok) > 4:
        out.add(tok + 'ing')
        if tok.endswith('e'):
            out.add(tok[:-1] + 'ing')
    out.discard(tok)
    return out


def _inflections_for(tok):
    """`_inflections`, cached. The same token comes up in every query."""
    v = _MORPH_CACHE.get(tok)
    if v is None:
        v = _inflections(tok)
        _MORPH_CACHE[tok] = v
    return v


class SearchIndex:
    """The inverted index over the library, built once at startup."""

    def __init__(self, data):
        self.data = data
        self.entries = list(data['skills']) + list(data['agents'])
        self.n = len(self.entries)
        self.by_id = {e['id']: e for e in self.entries}

        # idf over the whole corpus (skills + agents)
        self.df = {}
        for e in self.entries:
            toks = set(e['tokens']['name']) | set(e['tokens']['desc'])
            for t in toks:
                self.df[t] = self.df.get(t, 0) + 1

        # curated activation phrases, by entry id
        #
        # These are matched as PHRASES, not as loose tokens. The phrases are
        # user-facing symptom descriptions ("the page is stuck", "build
        # failed", "nothing showing"), not skill names. Matching their
        # individual words gave unrelated skills credit for a query --
        # `vercel-cli` lists "build failed" among its symptoms, so it scored
        # highly for "fix a failing build" while having nothing to do with
        # it. A phrase has to appear in the query as a phrase to count.
        self.signals = {}
        for e in self.entries:
            ps = e['frontmatter'].get('prompt_signals') or {}
            phrases = [p.lower().strip() for p in (ps.get('phrases') or [])
                       if p and p.strip()]
            if phrases:
                self.signals[e['id']] = phrases

        # task rows, for the task-shaped query path
        self.tasks = data.get('tasks') or []

        # the task index names skills and agents; map name -> task rows
        self.skill_tasks = {}
        self.agent_tasks = {}
        # ...and, per entry, the position it holds in each row. The
        # table lists its *primary* entry first -- `api-design` for
        # "Build an API", `error-handling` for "Fix a failing build" --
        # and the row's note says which one that is. The position is
        # that curation, made machine-readable.
        #
        # The two columns are numbered independently, so an agent at
        # agent-position 0 is NOT the row's first choice: the row's
        # primary entry is its first *skill*. An agent in the agents
        # column is an additional specialist the note points at --
        # "`database-reviewer` is PostgreSQL-specific: query
        # optimisation, schema design, security." -- and most rows list
        # one. So the agent positions start after the skill positions,
        # and only the first skill holds position 0.
        self.task_positions = {}
        for t in self.tasks:
            skills = t.get('skills') or []
            agents = t.get('agents') or []
            for pos, s in enumerate(skills):
                self.skill_tasks.setdefault(s, []).append(t['task'])
                self.task_positions[(s, t['task'])] = pos
            for pos, a in enumerate(agents):
                self.agent_tasks.setdefault(a, []).append(t['task'])
                self.task_positions[(a, t['task'])] = len(skills) + pos

        # each row's content-token sets, by row text. The builder
        # computes them, so both servers match a row the same way.
        self.task_content = {}
        for t in self.tasks:
            self.task_content[t['task']] = [list(c) for c in (t.get('content') or [])]

        # The filter vocabulary, so a filter argument that names
        # nothing can be reported as an error rather than as an empty
        # result. See `mcp/python/filters.py`.
        self.filter_values = filters.vocabulary(
            self.entries,
            lambda e: e.get('domain'),
            lambda e: e.get('provenance'),
        )

    def idf(self, t):
        return math.log(1.0 + self.n / float(self.df.get(t, 0) or 1))

    def is_generic(self, t):
        """Is this token too common to discriminate?

        A token that appears in more than `GENERIC_TOKEN_DF_RATIO` of the
        corpus carries almost no information about which entry a query
        wants. "write" appears in a few dozen entries; requiring an
        entry to contain it is a filter on luck, not on relevance.
        """
        df = self.df.get(t, 0)
        return df > self.n * GENERIC_TOKEN_DF_RATIO

    def _task_content_matches(self, task, q_tokens, heads=None, e=None):
        """Does the query contain the task row's *content*?

        The row's content is the row's tokens with its leading verb
        dropped -- "Build an API" -> ["api"]. The row may list several
        alternatives ("Write a document / report / deck"), and the row
        fires when the query contains one of them.

        The sets are computed by the index builder and stored in the
        index, so both servers match a row the same way.

        A single content token fires the row when it is *distinctive*
        -- a word like "api" appears in too many entries to identify a
        task on its own -- OR when it is the query's HEAD noun. "write
        a REST API" is about an API, so the "Build an API" row fires
        even though "api" is common. Two or more content tokens have
        to be *all* present. That is what keeps "write tests" from
        reaching "Fix flaky / failing tests": that row's alternatives
        are ["flaky"] and ["failing", "tests"], and the second needs
        both words.

        Returns the bonus to award -- 0 for no match, `WEIGHT_TASK_HEAD`
        for a head match, `WEIGHT_TASK_CONTENT` otherwise.

        `e` is the entry being scored. It is needed because a HEAD
        match splits the bonus by the row's curation: the row's first
        choice earns the row's full bonus, and the alternatives earn
        the head bonus.
        """
        q_set = set(q_tokens)
        if heads is None:
            heads = set()
        best = 0.0
        for content in self.task_content.get(task, ()):
            if not content:
                continue
            if len(content) == 1:
                tok = content[0]
                if tok not in q_set:
                    continue
                if not self.is_generic(tok):
                    best = max(best, WEIGHT_TASK_CONTENT)
                elif tok in heads:
                    best = max(best, self._head_bonus(e, task))
                continue
            if all(t in q_set for t in content):
                best = max(best, WEIGHT_TASK_CONTENT)
        return best

    def _head_bonus(self, e, task):
        """The head bonus, with the row's curation applied.

        The row lists its *primary* entry first and its note says so
        in prose -- "`api-design` covers resource naming, status codes,
        pagination, versioning, rate limits." -- but the scorer cannot
        read prose. So the first choice earns the row's full bonus on a
        head match, and the alternatives earn the smaller head bonus.

        Without this split the curated signal merely competed with the
        automatic evidence, and the competition was decided by the
        corpus: the same query ranked differently in two trees that
        hold the same skills. See `WEIGHT_TASK_HEAD_FIRST`.
        """
        if e is None:
            return WEIGHT_TASK_HEAD
        pos = self.task_positions.get((e['name'], task))
        if pos is None or pos == 0:
            return WEIGHT_TASK_HEAD_FIRST
        return WEIGHT_TASK_HEAD

    def coverage_tokens(self, q_tokens):
        """The query tokens that the coverage rule counts.

        Generic tokens are dropped, and duplicates are collapsed. If
        nothing is left -- a query made entirely of common words -- the
        full token list is used, so the rule still applies to it.
        """
        specific = []
        seen = set()
        for t in q_tokens:
            if t in seen:
                continue
            seen.add(t)
            if not self.is_generic(t):
                specific.append(t)
        return specific if specific else list(dict.fromkeys(q_tokens))

    def __getitem__(self, key):
        """The raw index data, so a caller can reach `skills`, `tasks`,
        `domains` and the rest without a second loader."""
        return self.data[key]

    def get(self, key, default=None):
        """Dict-style read of the raw index data.

        The server treats the index both as a searchable object and as the
        plain document it was built from; this keeps the two views the
        same object rather than two copies that can drift.
        """
        return self.data.get(key, default)

    def keys(self):
        return self.data.keys()

    # ------------------------------------------------------------- scoring
    def score_entry(self, e, q_tokens, q_bigrams, query_lower='', heads=None):
        """(score, matched_on, token_hits, structured) for one entry.

        `token_hits` is the set of *query* tokens this entry matched.
        It is separate from `matched_on`, which also carries the phrases
        and task rows that matched -- the coverage rule below needs to
        count tokens only.

        `structured` is True when the entry matched a curated
        `promptSignals` phrase, a task-index row, or a name bigram.
        Those are authoritative hand-written matches, so the token
        coverage rule does not apply to them.
        """
        score = 0.0
        matched = set()
        token_hits = set()
        structured = False
        name_tokens = e['tokens']['name']
        desc_tokens = set(e['tokens']['desc'])
        name_bigrams = set(e['tokens'].get('name_bigrams') or [])

        name_exact_hit = False
        for t in q_tokens:
            idf = self.idf(t)
            if t in name_tokens:
                score += WEIGHT_NAME_EXACT * idf
                matched.add(t)
                token_hits.add(t)
                name_exact_hit = True
            elif any(nt.startswith(t) for nt in name_tokens if len(nt) > len(t)):
                # The token must be a *prefix* of a name token, not a
                # fragment somewhere inside it.
                #
                # The old rule accepted the token anywhere in the name
                # token, and that matched words by accident: "home" in
                # "homelab", "late" in "template", "translate", and
                # "sql" in "mysql". "write SQL" ranked `mysql-patterns`
                # first because "sql" was found inside "mysql" -- a
                # coincidence of spelling, not evidence -- and
                # "bake sourdough bread at home" matched every
                # `homelab-*` skill on the fragment "home".
                #
                # A prefix is still a partial match: "docker" is a
                # prefix of "dockerfile", "kuber" of "kubernetes", and
                # both are what a caller means when they type them.
                score += WEIGHT_NAME_PARTIAL * idf
                matched.add(t)
                token_hits.add(t)
            if t in desc_tokens:
                score += WEIGHT_DESC * idf
                matched.add(t)
                token_hits.add(t)
            elif any(dt in _inflections_for(t) for dt in desc_tokens):
                # The description uses an inflected form of the query
                # token -- "drafting" for "draft". The match is worth
                # less than an exact one, because it is a guess about
                # the spelling rather than the spelling itself.
                score += WEIGHT_DESC * idf * MORPH_DISCOUNT
                matched.add(t)
                token_hits.add(t)

        for bg in q_bigrams:
            if bg in name_bigrams:
                score += WEIGHT_PHRASE
                matched.add(bg)
                structured = True

        sig = self.signals.get(e['id'])
        if sig:
            # A phrase must appear in the query as a phrase. The curated
            # phrases are symptom descriptions ("the page is stuck"), so a
            # loose word match would credit unrelated skills.
            for p in sig:
                if p in query_lower or _phrase_tokens_match(p, q_tokens):
                    score += WEIGHT_SIGNAL
                    matched.add(p)
                    structured = True
                    break

        # A task-shaped query ("fix a failing build") routes better through
        # the hand-written task index than through any automatic score.
        #
        # The row has to be *substantially* present in the query. An
        # earlier "all but one token" rule was too loose: "fix a failing
        # build" matched the row "Build a dashboard" on the single word
        # "build", which put four dashboard/API builders above
        # `error-handling`. The rule below needs at least 60% of the row's
        # content words, and at least two of them when the row has two or
        # more -- so "my build keeps failing" still finds "Fix a failing
        # build", but "fix a failing build" no longer finds "Build a
        # dashboard".
        #
        # The 60% rule reads the WHOLE row, verb included. The rows are
        # written "<verb> <object>" -- "Build an API" -- so it demanded
        # the query's verb as well as its object, and "write a REST API"
        # never reached the row that names the right skills. The row
        # also fires, for a smaller bonus, when the query contains the
        # row's *content* (the row's verb dropped) -- which is what
        # "write a REST API" has.
        if e['kind'] == 'skill':
            tasks = self.skill_tasks.get(e['name'])
        else:
            tasks = self.agent_tasks.get(e['name'])
        if tasks:
            for task in tasks:
                t_toks = tokenize(task)
                strict = False
                if t_toks:
                    overlap = sum(1 for t in t_toks if t in q_tokens)
                    needed = max(1, -(-len(t_toks) * 6 // 10))   # ceil(60%)
                    if len(t_toks) >= 2:
                        needed = max(2, needed)
                    strict = overlap >= needed
                if strict:
                    score += self._row_bonus(WEIGHT_TASK, e, task)
                    matched.add(task)
                    structured = True
                    break
                bonus = self._task_content_matches(task, q_tokens, heads, e)
                if bonus:
                    # A content match: the query named the row's object,
                    # not the row's verb, so the row has NOT accounted for
                    # the verb. Nothing is suppressed.
                    #
                    # The row's *order* still counts, though. The table
                    # lists a row's members in priority order -- its
                    # skills first, then its agents -- and that order is
                    # the row's curation even when the query named only
                    # the row's object. Without this, "write SQL" ranked
                    # `database-reviewer` first: the agent is tier 1
                    # while `mysql-patterns` is tier 2, so the tier bias
                    # and the agent bonus together put it ahead of the
                    # skills the row had been asked for.
                    #
                    # The demotion is the same gradient the strict branch
                    # uses, and it is gentle: a row's own alternatives
                    # stay reachable, but the row's first choice leads.
                    pos = self.task_positions.get((e['name'], task))
                    if pos is not None and pos > 0:
                        depth = min(pos, TASK_DEMOTE_MAX_DEPTH)
                        demote = min(bonus * TASK_DEMOTE_FRACTION * depth,
                                     TASK_DEMOTE_MAX)
                        bonus = bonus - demote
                    score += bonus
                    matched.add(task)
                    structured = True
                    break

        # Tier bias, suppressed when the name matched exactly.
        bias = TIER_BIAS.get(e.get('tier', 3), 0.0) * (0.0 if name_exact_hit else 1.0)
        score += bias
        if e['kind'] == 'agent':
            score += AGENT_BIAS

        return score, sorted(matched, key=_code_point_key), token_hits, structured

    # -------------------------------------------------------------- search
    def _row_bonus(self, base, e, task):
        """The row's curation, applied to one of its members.

        The task table lists a row's *primary* entry first, and its
        note says which one that is. A later member is an alternative,
        so it is demoted -- the row's first choice is what the row
        recommends, and the scorer cannot read the prose that says so.

        The demotion is a *fraction* of the row's bonus, scaled by the
        member's depth in the row. A flat amount was tried first and
        it did not work: the row "Write SQL / optimise queries" lists
        `postgres-patterns`, `mysql-patterns` and then the agent
        `database-reviewer`, and a flat 3.0 was not enough to stop the
        agent winning "write SQL queries" -- the agent is tier 1 and
        gets the agent bonus, so it led by 0.299.

        Scaling by depth is what makes the demotion match the table.
        The row's first member is its recommendation and keeps the
        full bonus. The second is an alternative and gives up a third
        of the bonus. The third gives up more, and the depth is capped
        so that a row's later members stay reachable rather than being
        pushed out of the results altogether.
        """
        pos = self.task_positions.get((e['name'], task))
        if pos is None or pos == 0:
            return base
        depth = min(pos, TASK_DEMOTE_MAX_DEPTH)
        demote = min(base * TASK_DEMOTE_FRACTION * depth, TASK_DEMOTE_MAX)
        return base - demote

    def search(self, query, limit=DEFAULT_LIMIT, kind=None, tier=None,
               domain=None, source=None, license=None, verdict=None,
               include_body=False, cursor=None):
        q_tokens = tokenize(query)
        if not q_tokens:
            return {'query': query, 'total_matched': 0, 'filtered_out': 0,
                    'returned': 0, 'truncated': False, 'note': '',
                    'results': []}

        # The filter arguments are resolved against the index's
        # vocabulary before anything is scored. A filter that names
        # nothing is an error, not an empty result -- see
        # `mcp/python/filters.py`.
        domain = filters.resolve('domain', domain, self.filter_values['domain'])
        source = filters.resolve('source', source, self.filter_values['source'])
        license = filters.resolve('license', license, self.filter_values['license'])
        verdict = filters.resolve('verdict', verdict, self.filter_values['verdict'])

        q_bigrams = bigrams(q_tokens)
        query_lower = ' '.join((query or '').lower().split())
        # The query's head nouns -- what it is *about*, as opposed to the
        # context it mentions. The task-row rule uses this to tell
        # "write a REST API" (about an API) from "add authentication to
        # an api" (about authentication).
        heads = head_tokens(query)

        scored = []
        for e in self.entries:
            if kind and e['kind'] != kind:
                continue
            if tier is not None and e.get('tier') != tier:
                continue
            if domain and e.get('domain') != domain:
                continue
            # The provenance filters. A caller who needs to know what
            # may be redistributed asks for it here, rather than
            # filtering the results afterwards.
            prov = e.get('provenance') or {}
            if source and prov.get('container') != source:
                continue
            if license and prov.get('license') != license:
                continue
            if verdict and prov.get('verdict') != verdict:
                continue
            s, matched, token_hits, structured = self.score_entry(
                e, q_tokens, q_bigrams, query_lower, heads)
            if s <= 0:
                continue
            # Token coverage. A single generic token is not a match:
            # "how to bake sourdough bread at home" matched
            # `shopify-polaris-app-home` on the word "home", and
            # "quantum chromodynamics lattice simulation" matched
            # `web-game-foundations` on "simulation". An entry has to
            # match at least two thirds of the query's tokens, and at
            # least two when the query has two or more.
            #
            # An entry that matched a curated phrase, a task row or a
            # name bigram is exempt: those are hand-written, and the
            # task row "Review code I did not write" legitimately shares
            # only "code", "not" and "review" with its query.
            #
            # The rule counts only the *discriminating* query tokens.
            # "write documentation" has two tokens, so the rule demanded
            # both -- and `documentation-lookup`, whose name contains
            # "documentation", was dropped for not also containing
            # "write". The subject of the query was the one token that
            # carried the information; the generic verb was noise.
            cov_tokens = self.coverage_tokens(q_tokens)
            if not structured:
                needed = max(1, -(-len(cov_tokens) * 2 // 3))
                if len(cov_tokens) >= 2:
                    needed = max(2, needed)
                # The demand is capped at two tokens.
                #
                # Two thirds of the query's tokens is the right *shape*
                # -- a query that names a subject should be answered by
                # an entry that covers it -- but it is the wrong
                # *magnitude* once the query is longer than the
                # sentence that names the subject. "stop my prose from
                # sounding like a machine wrote it" has five
                # discriminating tokens, so the rule demanded four,
                # and `humanizer` -- which matches "sounding" and
                # "wrote" -- was thrown away for want of two more
                # words that no skill's description contains.
                #
                # Two is the number the rule already insisted on when
                # the query had two or more tokens. Beyond that, the
                # demand grew with the query's length, and length is
                # evidence of nothing.
                needed = min(needed, 2)
                # The hits are counted over *every* query token, not
                # only the ones that survived the generic-token
                # filter.
                #
                # The filter drops the words that appear in too many
                # descriptions -- "audit", "draft", "review". That is
                # right for deciding *how many* tokens the rule should
                # demand, but wrong for deciding which tokens count as
                # evidence: the filtered word is still evidence when
                # the entry matched it. "audit my site against WCAG
                # 2.2" leaves {site, against, wcag} after the filter
                # and demands two of them; `accessibility` matches
                # "wcag" and "audit", but "audit" had been discarded,
                # so the rule demanded "site" and "against" -- words
                # no skill's description contains -- and threw the
                # right answer away.
                hits = sum(1 for t in set(q_tokens) if t in token_hits)
                if hits < needed:
                    continue
                # The evidence rule.
                #
                # An entry that matched only words which carry no
                # information about *which* entry it is, matched
                # nothing real. "my cat knocked over a plant" matched
                # `plant-care` on the word "plant" -- and "plant" is
                # the query's subject, but the *coverage* words are
                # the words that identify the entry, and "plant"
                # identifies none of them.
                #
                # The check has two halves. The entry must have
                # matched at least one word that appears in the
                # corpus at all -- otherwise every word it matched is
                # a coincidence. And it must have matched at least
                # one of the *coverage* words, or at least two words
                # overall: one word in the corpus is not enough on
                # its own, because "write" appears in a few dozen
                # descriptions and matching it says nothing.
                in_corpus = [t for t in token_hits if self.df.get(t, 0) > 0]
                cov_in_corpus = [t for t in cov_tokens
                                 if t in token_hits and self.df.get(t, 0) > 0]
                if not cov_in_corpus and len(in_corpus) < 2:
                    continue
            scored.append((s, e, matched))

        # The fixed tie-break order. The TypeScript server must produce the
        # identical ordering, or the agreement test fails.
        #
        # The score is compared through `score_key`, so that scores which
        # differ only in the last floating-point bit are treated as equal
        # and the tie-break below decides their order.
        scored.sort(key=lambda t: (
            -score_key(t[0]),
            t[1].get('tier', 3),
            0 if t[1]['kind'] == 'skill' else 1,
            len(t[1]['name']),
            t[1]['name'],
        ))
        # The name tie-break above sorts by code point, because Python's
        # `str` comparison is a code-point comparison. The TypeScript
        # side has to say so explicitly -- see `codepoint_compare`
        # above and `codepointCompare` in `mcp/src/search.ts`.

        # The number of entries that matched, before the relevance
        # floor. This is the size of the match set: the entries that
        # passed scoring and the coverage rule. It is *not* the number
        # of results, because the relevance floor then drops the
        # entries whose score is under a quarter of the best one.
        total = len(scored)
        if not scored:
            return {'query': query, 'total_matched': 0, 'filtered_out': 0,
                    'returned': 0, 'truncated': False, 'note': '',
                    'results': []}

        top = scored[0][0]
        floor = top * RELEVANCE_FLOOR
        kept = [t for t in scored if t[0] >= floor]

        # The entries the relevance floor dropped. Reporting this is
        # what makes the four counts tell one story: `total_matched` is
        # the match set, `filtered_out` is what the floor removed from
        # it, and `returned` is what came back. Before this field
        # existed, the floor silently hid entries -- a query reported
        # 52 matches and returned 37 with `truncated: false`, so the
        # caller could not tell that 15 had been dropped.
        filtered_out = total - len(kept)

        limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))

        # Cursor pagination.
        #
        # The cursor names the last entry the client saw, and the page
        # starts after it. The cursor is honoured even if the entry is
        # gone -- then the page starts at the end, and `cursorStale`
        # says so, because a client that silently got an empty page
        # would think it had reached the end of the results.
        start = 0
        cursorStale = False
        if cursor:
            pos = None
            for i, t in enumerate(kept):
                if t[1]['id'] == cursor:
                    pos = i
                    break
            if pos is not None:
                start = pos + 1
            else:
                start = len(kept)
                cursorStale = True

        remaining = len(kept) - start
        truncated = remaining > limit
        shown = kept[start:start + limit]

        results = []
        for s, e, matched in shown:
            prov = e.get('provenance') or {}
            r = {
                'id': e['id'],
                'kind': e['kind'],
                'name': e['name'],
                'title': e.get('title', e['name']),
                'description': e.get('desc', ''),
                'tier': e.get('tier', 3),
                'domain': e.get('domain', ''),
                'score': round(s, 4),
                'matched_on': matched,
                'path': e.get('path', ''),
                'owner': prov.get('owner', ''),
                'license': prov.get('license', ''),
                'verdict': prov.get('verdict', 'unknown'),
            }
            if include_body:
                r['frontmatter'] = e.get('frontmatter', {})
            results.append(r)

        note = ''
        if cursorStale:
            note = ('The cursor no longer points at a result -- the library '
                    'changed. This page is empty.')
        elif truncated:
            note = ('Showing %d of %d matches. Refine the query to narrow it '
                    'down.' % (limit, remaining))
        elif filtered_out > 0:
            note = ('Showing %d of %d matches; %d were below the relevance '
                    'floor.' % (len(kept), total, filtered_out))
        out = {
            'query': query,
            'total_matched': total,
            'filtered_out': filtered_out,
            'returned': len(results),
            'truncated': truncated,
            'note': note,
            'results': results,
        }

        # The cursor for the next page, when there is one. It names the
        # last entry of *this* page, so the next page starts after it --
        # not after an offset, which would skip or repeat entries if the
        # ranking changed between the two calls.
        #
        # The cursor is emitted whenever there is a next page, including
        # on the first one: the first page is where the client gets the
        # cursor it needs.
        if truncated and results:
            out['nextCursor'] = protocol.encode_cursor(results[-1]['id'], query)
        if cursorStale:
            out['cursorStale'] = True
        return out


def load_index(path=None):
    import json
    p = path or os.path.join(BASE, 'mcp', 'data', 'index.json')
    with open(p, encoding='utf-8') as fh:
        return SearchIndex(json.load(fh))


if __name__ == '__main__':
    q = ' '.join(sys.argv[1:]) or 'accessibility audit WCAG'
    idx = load_index()
    out = idx.search(q, limit=10)
    print('%s  (total %d, returned %d)' % (q, out['total_matched'], out['returned']))
    for r in out['results']:
        print('  %-34s %6.2f  tier %d  %s' % (
            r['id'], r['score'], r['tier'], ','.join(r['matched_on'])[:60]))
