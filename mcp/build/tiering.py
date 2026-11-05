#!/usr/bin/env python3
"""Tier assignment — the only place tier numbers are computed.

Tiers are a **ranking bias, never a filter**. Every skill and every agent
stays searchable and reachable; the tier only nudges the ordering when
several entries score similarly.

    tier 1  the hand-authored packs + all the agents
    tier 2  skills whose first matching domain is one of the 10 core domains
    tier 3  everything else

The tier-2 set is computed with **first-match-wins** over the domain table,
not "matches any of the 10". That distinction matters: "any match" yields
291 skills, and a skill would then carry a different domain in the index
than the one the routing guide prints for it. First-match-wins yields 269 and
the domain always agrees with the guide.

The 10 core domains, in the guide's own order and spelling. These names are
the guide's, verbatim -- a typo here would silently change which skills are
tier 2.

    Core engineering practice, API & integration, Testing & QA, Security,
    Data, databases & pipelines, DevOps & cloud, Architecture & design,
    Backend & API frameworks, Code review & quality, Frontend, UI & accessibility
"""
import sys

from domains import assign
from packs import names as pack_names

# The packs: hand-authored, self-contained, and the first thing to reach for.
#
# The list comes from the manifest rather than from a literal here, so that
# adding a pack is a one-file edit. A literal in this module meant that a
# new pack was tier 3 unless someone remembered this file -- and a pack
# that is not tier 1 is not the first thing to reach for.
PACKS = tuple(pack_names())

# The 10 domains whose skills are tier 2. Order matches the guide.
CORE_DOMAINS = (
    'Core engineering practice',
    'API & integration',
    'Testing & QA',
    'Security',
    'Data, databases & pipelines',
    'DevOps & cloud',
    'Architecture & design',
    'Backend & API frameworks',
    'Code review & quality',
    'Frontend, UI & accessibility',
)


def assign_tiers(skill_names, agent_names):
    """Return (tier_of, domain_of) for every skill and agent.

    `tier_of` maps a (kind, name) pair to 1, 2 or 3. The kind is part of the
    key because `claude-security` is BOTH a skill and an agent, and the two
    have different tiers -- the agent is tier 1, the skill is not a pack.

    `domain_of` maps a skill name to its domain. Agents have no domain.
    """
    domain_of, _ = assign(list(skill_names))

    tier_of = {}
    for name in skill_names:
        if name in PACKS:
            tier_of[('skill', name)] = 1
        elif domain_of.get(name) in CORE_DOMAINS:
            tier_of[('skill', name)] = 2
        else:
            tier_of[('skill', name)] = 3
    for name in agent_names:
        tier_of[('agent', name)] = 1
    return tier_of, domain_of


if __name__ == '__main__':
    # A quick self-check, so the module can be run standalone.
    import json
    import os

    base = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    data = json.load(open(os.path.join(base, '.library_data.json'),
                          encoding='utf-8'))
    skills = [s['name'] for s in data['skills']]
    agents = [a['name'] for a in data['agents']]
    tiers, domains = assign_tiers(skills, agents)

    counts = {1: 0, 2: 0, 3: 0}
    for s in skills:
        counts[tiers[('skill', s)]] += 1
    print('skills: %d   agents: %d' % (len(skills), len(agents)))
    print('skill tiers: %s' % counts)
    print('tier 1 skills: %s' % sorted(n for n in skills if tiers[('skill', n)] == 1))
    print('tier 2 count: %d' % counts[2])
    print('tier 3 count: %d' % counts[3])
