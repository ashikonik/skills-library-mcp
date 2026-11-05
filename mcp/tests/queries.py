#!/usr/bin/env python3
"""The golden query set.

60 queries covering the parts of the library that are easiest to get
wrong:

  * the hand-authored packs
  * the ten tier-2 domains
  * the two agents whose frontmatter is not valid YAML
  * the 17 skills the YAML fix changed
  * the 18 skills carrying curated `promptSignals`
  * task-shaped queries, which route through the task index
  * multi-word technical queries
  * three queries with no library match, which must return nothing

The last group matters as much as the first: a scorer that returns
*something* for every query is not a scorer, it is a shuffle. Both
servers must return an empty list for these three.

This list is shared by `test_agreement.py` (Python vs TypeScript) and
`test_search.ts` (the TypeScript golden replay). It lives in Python
because the Python file is the one both can read without a build step.
"""

# The hand-authored packs.
PACK_QUERIES = [
    'caveman mode lazy senior developer',
    'build a document from a template',
    'humanize this text make it sound less robotic',
    'fix my latex document errors',
    'research partner literature review',
    'create a new skill',
    'add a skill to the library',
]

# The ten core domains.
DOMAIN_QUERIES = [
    'core engineering practice standards',
    'api and integration design',
    'testing and qa automation',
    'security review vulnerability',
    'data database pipeline',
    'devops and cloud deployment',
    'architecture and design patterns',
    'backend api framework',
    'code review and quality',
    'frontend ui accessibility',
]

# The two agents whose frontmatter is not valid YAML.
YAML_BROKEN_QUERIES = [
    'explore the codebase agent',
    'silent failure hunter agent',
]

# The 17 skills the YAML frontmatter fix changed. The fix restored
# descriptions that had been truncated, so a query naming the skill's
# actual subject must find it.
YAML_FIXED_QUERIES = [
    'competition math olympiad proof',
    'improve accessibility wcag',
    'python testing patterns pytest',
    'typescript type safety',
    'docker container deployment',
    'kubernetes cluster operations',
    'database query optimization',
    'authentication oauth jwt',
    'react component patterns',
    'writing technical documentation',
    'debugging production incident',
    'code refactoring large codebase',
    'git version control workflow',
    'rest graphql api endpoint',
    'machine learning model training',
    'data visualization charts',
    'ci cd pipeline automation',
]

# The skills carrying curated promptSignals -- symptom descriptions.
SIGNAL_QUERIES = [
    'the page is stuck',
    'nothing showing on screen',
    'build failed with no error message',
    'the deploy never finishes',
    'my changes were not saved',
    'it hangs on startup',
    'the screen is blank',
    'it crashes when i open it',
]

# Task-shaped queries, which route through the hand-written task index.
TASK_QUERIES = [
    'fix a failing build',
    'review code i did not write',
    'write a new feature',
    'debug a failing test',
    'set up continuous integration',
    'refactor legacy code',
    'add authentication to an api',
    'improve performance of a slow query',
    'migrate to a new framework',
    'ship a release',
]

# Multi-word technical queries.
TECHNICAL_QUERIES = [
    'useEffect react hook dependency array',
    'kafka consumer group rebalancing',
    'terraform module state locking',
    'postgres index bloat vacuum',
    'grpc streaming backpressure',
    'webpack code splitting lazy load',
    'numpy vectorized computation',
    'redis cache invalidation strategy',
    'websocket reconnection backoff',
    'aws lambda cold start',
]

# A skill's own name.
NAME_QUERIES = [
    'tdd-workflow',
    'code-review',
    'api-design',
    'document-builder',
    'math-olympiad',
    'security-review',
    'prompt-optimizer',
    'mcp-server-patterns',
]

# Queries with no library match. Both servers must return [].
NO_MATCH_QUERIES = [
    'zzzzqqqq nonexistent gibberish token',
    'quantum chromodynamics lattice simulation',
    'how to bake sourdough bread at home',
]

GOLDEN_QUERIES = (
    PACK_QUERIES
    + DOMAIN_QUERIES
    + YAML_BROKEN_QUERIES
    + YAML_FIXED_QUERIES
    + SIGNAL_QUERIES
    + TASK_QUERIES
    + TECHNICAL_QUERIES
    + NAME_QUERIES
    + NO_MATCH_QUERIES
)

if __name__ == '__main__':
    print('%d golden queries' % len(GOLDEN_QUERIES))
    for group, qs in (
        ('packs', PACK_QUERIES),
        ('domains', DOMAIN_QUERIES),
        ('yaml-broken', YAML_BROKEN_QUERIES),
        ('yaml-fixed', YAML_FIXED_QUERIES),
        ('signals', SIGNAL_QUERIES),
        ('tasks', TASK_QUERIES),
        ('technical', TECHNICAL_QUERIES),
        ('names', NAME_QUERIES),
        ('no-match', NO_MATCH_QUERIES),
    ):
        print('  %-14s %d' % (group, len(qs)))
