#!/usr/bin/env python3
"""Build ROUTING_GUIDE.md from .library_data.json.

The guide is a task -> skill/agent lookup. It reads the consolidated library
index and emits:
  1. How to use
  2. Task-type index (the main router)
  3. Language & framework quick index
  4. Skill catalogue by domain (all skills)
  5. Agent catalogue by function (all agents)
  6. Ensemble / workflow patterns
  7. Standalone packs
  8. Quick reference card
"""
import os
import re
import json
import collections
import sys

OUT = os.path.dirname(os.path.abspath(__file__))
# The domain table is shared with the MCP index builder.
sys.path.insert(0, os.path.join(OUT, 'mcp', 'build'))
from domains import DOMAINS, assign as assign_domains
from tasks import TASKS
from packs import packs as pack_records

PACKS = pack_records()
data = json.load(open(os.path.join(OUT, '.library_data.json'), encoding='utf-8'))

SKILLS = data['skills']
AGENTS = data['agents']
EXCLUDED = data['excluded_agents']

BY_SKILL = {s['name']: s for s in SKILLS}
BY_AGENT = {a['name']: a for a in AGENTS}


def sk(name):
    """Reference a skill, verified to exist."""
    return '`skills/%s/`' % name if name in BY_SKILL else None


def ag(name):
    return '`agents/%s.md`' % name if name in BY_AGENT else None


def clip(text, n=150):
    d = ' '.join((text or '').split())
    if len(d) > n:
        d = d[:n - 3].rsplit(' ', 1)[0] + '...'
    return d.replace('|', '\\|')


def norm(name):
    return ' '.join(re.sub(r'[-_/]+', ' ', name.lower()).split())


def hit(name, keys):
    """Word-boundary keyword match (see .gen_report.py for rationale)."""
    n = norm(name)
    for k in keys:
        kw = ' '.join(re.sub(r'[-_/]+', ' ', k.lower()).split())
        if not kw:
            continue
        pat = r'(?<![a-z0-9])' + r'\s+'.join(re.escape(w) for w in kw.split()) + r'(?![a-z0-9])'
        if re.search(pat, n):
            return True
    return False


def pick(cands, keys, limit=4):
    """Pick existing items matching keys, preserving input order."""
    out = []
    for c in cands:
        if c in BY_SKILL or c in BY_AGENT:
            out.append(c)
    return out[:limit]


L = []
w = L.append

w('# Routing Guide — Skills & Agents Library')
w('')
w('**Purpose:** given any task, find the right skill or agent, and know when to use which.')
w('')
w('| | |')
w('|---|---|')
w('| Skills | **%d** — instructions, playbooks and reference material the model follows |' % len(SKILLS))
w('| Agents | **%d** — specialised sub-agents invoked for one bounded role |' % len(AGENTS))
w('| Held aside | %d pipeline-internal agents (see `agents/_agent-specific/`) |' % len(EXCLUDED))
w('| Inventory | `SKILLS_AND_AGENTS_REPORT.md` — full census with sources |')
w('| Machine index | `.library_data.json` |')
w('')
w('---')
w('')

# ------------------------------------------------------------------ 1. how
w('## 1. How to use this guide')
w('')
w('### The decision procedure')
w('')
w('```')
w('1. Read the task.')
w('2. Match it to a task type in §2  ->  get the skill and/or agent.')
w('3. If the task names a language or framework, use §3 first — it is more specific.')
w('4. Open the skill and FOLLOW IT. A skill is instructions, not a suggestion.')
w('5. If the task needs judgement rather than procedure, invoke the agent.')
w('```')
w('')
w('### Skill or agent?')
w('')
w('| | **Skill** | **Agent** |')
w('|---|---|---|')
w('| What it is | A `SKILL.md` you read and follow | A sub-agent you delegate a role to |')
w('| Best for | "How should I do X?" | "Do X and judge the result" |')
w('| You control | Every step | The agent does the work |')
w('| Examples | `api-design`, `tdd-workflow`, `frontend-patterns` | `code-reviewer`, `python-reviewer`, `security-reviewer` |')
w('| Cost | Cheap — inline context | Higher — separate context window |')
w('')
w('**Rule of thumb:** if the task is *"follow these conventions"* use a skill. If the task is')
w('*"review / audit / fix / analyse this thing"* use an agent — most reviewers are marked')
w('*"MUST BE USED for <language> projects"*, which means they are expected to run on every')
w('change in that stack, not on request.')
w('')
w('### Both together')
w('')
w('The strongest pattern available here is **skill for method + agent for judgement**:')
w('')
w('```')
w('Skill:  tdd-workflow          (how to write the test first)')
w('Agent:  python-reviewer       (judges whether the result is right)')
w('```')
w('')

# ------------------------------------------------------- 2. task type index
w('## 2. Task-Type Index — the main router')
w('')
w('Find your task type. Read across for the recommended skill and agent.')
w('')

w('| Task | Skill (how) | Agent (judgement) | Notes |')
w('|---|---|---|---|')
for task, skills, agents, note in TASKS:
    sk_cells = []
    for s in skills:
        if s in BY_SKILL:
            sk_cells.append('`%s`' % s)
    ag_cells = []
    for a in agents:
        if a in BY_AGENT:
            ag_cells.append('`%s`' % a)
    w('| **%s** | %s | %s | %s |' % (
        task,
        ', '.join(sk_cells) if sk_cells else '—',
        ', '.join(ag_cells) if ag_cells else '—',
        note.replace('|', '\\|')))
w('')

# ----------------------------------------------- 3. language quick index
w('## 3. Language & Framework Quick Index')
w('')
w('The highest-frequency lookup. For any change in one of these stacks, the agent column is')
w('usually marked **MUST BE USED** in its own description — meaning it is expected to run on')
w('every change, not on request.')
w('')

STACKS = [
    ('Python', 'python-patterns', 'python-reviewer', 'build-error-resolver', 'python-testing'),
    ('TypeScript / JavaScript', 'coding-standards', 'coding-standards', 'build-error-resolver', 'e2e-testing'),
    ('React / Next.js', 'react-patterns', 'react-reviewer', 'react-build-resolver', 'react-testing'),
    ('Vue / Nuxt', 'vue-patterns', 'vue-reviewer', 'build-error-resolver', '—'),
    ('Angular', 'angular-developer', '—', 'build-error-resolver', '—'),
    ('Node / NestJS', 'nestjs-patterns', '—', 'build-error-resolver', '—'),
    ('Svelte / SvelteKit', '—', '—', 'build-error-resolver', '—'),
    ('Java / Spring Boot', 'springboot-patterns', 'java-reviewer', 'java-build-resolver', 'springboot-tdd'),
    ('Java / Quarkus', 'quarkus-patterns', 'java-reviewer', 'java-build-resolver', 'quarkus-tdd'),
    ('Kotlin / Android', 'kotlin-patterns', 'kotlin-reviewer', 'kotlin-build-resolver', 'kotlin-testing'),
    ('Swift / iOS', 'swiftui-patterns', 'swift-reviewer', 'swift-build-resolver', 'swift-protocol-di-testing'),
    ('Dart / Flutter', 'dart-flutter-patterns', 'flutter-reviewer', 'dart-build-resolver', 'flutter-dart-code-review'),
    ('Go', 'golang-patterns', 'go-reviewer', 'go-build-resolver', 'golang-testing'),
    ('Rust', 'rust-patterns', 'rust-reviewer', 'rust-build-resolver', 'rust-testing'),
    ('C++', 'cpp-coding-standards', 'cpp-reviewer', 'cpp-build-resolver', 'cpp-testing'),
    ('C# / .NET', 'dotnet-patterns', 'csharp-reviewer', 'build-error-resolver', 'csharp-testing'),
    ('PHP / Laravel', 'laravel-patterns', 'php-reviewer', 'build-error-resolver', 'laravel-tdd'),
    ('Ruby on Rails', '—', '—', 'build-error-resolver', '—'),
    ('Perl', 'perl-patterns', '—', 'build-error-resolver', 'perl-testing'),
    ('F#', 'fsharp-testing', 'fsharp-reviewer', 'build-error-resolver', 'fsharp-testing'),
    ('Django', 'django-patterns', 'django-reviewer', 'django-build-resolver', 'django-tdd'),
    ('FastAPI', 'fastapi-patterns', 'fastapi-reviewer', 'build-error-resolver', 'fastapi-patterns'),
    ('Expo / React Native', 'expo-module', 'react-reviewer', 'react-build-resolver', 'expo-module'),
    ('HarmonyOS / ArkTS', '—', 'harmonyos-app-resolver', 'harmonyos-app-resolver', '—'),
    ('SQL / PostgreSQL', 'postgres-patterns', 'database-reviewer', '—', 'postgres-patterns'),
    ('Prisma / ORM', 'prisma-patterns', 'database-reviewer', '—', 'prisma-patterns'),
    ('Bun', 'bun-runtime', 'coding-standards', 'build-error-resolver', 'bun-runtime'),
    ('PyTorch', 'pytorch-patterns', 'mle-reviewer', 'pytorch-build-resolver', 'pytorch-patterns'),
    ('Vite', 'vite-patterns', '—', 'build-error-resolver', 'vite-patterns'),
    ('Next.js', 'nextjs', 'react-reviewer', 'react-build-resolver', 'nextjs-turbopack'),
]

w('| Stack | Patterns skill | Reviewer agent | Build resolver | Testing skill |')
w('|---|---|---|---|---|')
for stack, s, a, b, t in STACKS:
    def cell(x):
        if x == '—':
            return '—'
        return ('`%s`' % x) if x in BY_SKILL or x in BY_AGENT else '—'
    w('| %s | %s | %s | %s | %s |' % (stack, cell(s), cell(a), cell(b), cell(t)))
w('')
w('> A dash means no dedicated skill or agent exists for that stack — fall back to the')
w('> language-agnostic ones (`coding-standards`, `code-reviewer`, `build-error-resolver`)')
w('> or the general `tdd-workflow` / `e2e-testing` skills.')
w('')

# ---------------------------------------------------- 4. skills by domain
w('## 4. Skill Catalogue by Domain')
w('')
w('All %d skills, grouped. The **use when** column is condensed from each skill\'s own' % len(SKILLS))
w('frontmatter description — read that file for the full text.')
w('')

# One shared implementation of the first-match-wins assignment. The guide and
# the index both call it, so a skill's domain is the same in both.
domain_of, DOMAINS = assign_domains([s['name'] for s in SKILLS])

for idx, (dom, keys) in enumerate(DOMAINS, 1):
    items = sorted([s for s in SKILLS if domain_of.get(s['name']) == dom],
                   key=lambda x: x['name'].lower())
    if not items:
        continue
    w('### 4.%d %s — %d skill%s' % (idx, dom, len(items),
                                     '' if len(items) == 1 else 's'))
    w('')
    w('| Skill | Use when |')
    w('|---|---|')
    for s in items:
        d = clip(s['desc'], 135) or '_(no description)_'
        w('| `%s` | %s |' % (s['name'], d))
    w('')

# ---------------------------------------------------- 5. agents by function
w('## 5. Agent Catalogue by Function')
w('')
w('All %d agents. **Model** is the model the definition requests; **Tools** is its' % len(AGENTS))
w('allow-list. Read the agent file before invoking — each carries its own process.')
w('')

FUNC = [
    # Order matters: first match wins, so the most specific groups come first.
    ('Security', lambda a: a['name'] in (
        'security-reviewer', 'security-auditor', 'claude-security', 'opensource-sanitizer',
        'opensource-forker', 'opensource-packager'),
     'Vulnerability detection, adversarial review, orchestrated scanning, release pipeline.'),
    ('GAN harness (build a product)', lambda a: a['name'].startswith('gan-'),
     'A coordinated trio — plan -> generate -> evaluate. Run `gan-planner` first; see §6.'),
    ('Code cleanup & simplification', lambda a: a['name'] in (
        'code-simplifier', 'refactor-cleaner'),
     'Reduce complexity and remove dead code without changing behaviour.'),
    ('Documentation', lambda a: a['name'] in (
        'doc-updater', 'docs-lookup'),
     'Keep docs and codemaps in step with the code.'),
    ('Read-only Q&A', lambda a: a['name'] in ('Ask',),
     'Answers questions about the codebase without changing anything.'),
    ('Build & type-error resolvers', lambda a: a['name'].endswith('-build-resolver')
     or a['name'] == 'build-fix' or a['name'] == 'build-error-resolver'
     or a['name'] == 'harmonyos-app-resolver',
     'Fix compilation, dependency and type errors with minimal diffs. Explicitly forbidden from '
     'making architectural edits.'),
    ('Architecture & planning', lambda a: a['name'] in (
        'architect', 'code-architect', 'ai-architect', 'network-architect', 'a11y-architect',
        'homelab-architect', 'planner', 'Plan', 'architecture-critic', 'scaffolder',
        'uplift-migrator', 'version-delta-analyst', 'code-explorer', 'Explore',
        'legacy-analyst', 'ecc-coordinator'),
     'Design, blueprint, critique and migrate.'),
    ('Research, scoring & outreach', lambda a: a['name'] in (
        'signal-scorer', 'enrichment-agent', 'mutual-mapper', 'outreach-drafter',
        'marketing-agent'),
     'Prospect discovery, enrichment, mutual-connection mapping, personalised outreach.'),
    ('Quality, cleanup & documentation', lambda a: a['name'] in (
        'code-reviewer', 'coding-standards', 'codehealth-mcp', 'silent-failure-hunter',
        'comment-analyzer', 'conversation-analyzer', 'type-design-analyzer', 'pr-test-analyzer',
        'tdd-guide', 'e2e-runner', 'documentation-lookup', 'docs-lookup', 'agent-evaluator',
        'skill-reviewer', 'harness-optimizer', 'loop-operator', 'observer', 'spec-miner',
        'test-engineer', 'business-rules-extractor', 'plugin-validator', 'agent-creator',
        'agent-sdk-verifier-py', 'agent-sdk-verifier-ts'),
     'Review, scoring, cleanup, docs, and the guardrails around autonomous work.'),
    ('Domain specialists', lambda a: a['name'] in (
        'database-reviewer', 'performance-optimizer', 'healthcare-reviewer', 'mle-reviewer',
        'seo-specialist', 'marketing-agent', 'chief-of-staff', 'ctf-flag-finder',
        'network-config-reviewer', 'network-troubleshooter', 'harmonyos-app-resolver',
        'deployment-expert', 'debug', 'maintainer', 'reviewer', 'zoom-integration-reviewer',
        'zoom-oauth-scope-auditor', 'design-parity-review-agent', 'design-system-rules-agent',
        'figma-code-connect-agent', 'figma-implementation-agent'),
     'Vertical expertise: databases, performance, clinical safety, ML systems, SEO, marketing, '
     'networks, deployments, design parity.'),
    ('Code reviewers', lambda a: a['name'].endswith('-reviewer'),
     'Each covers its language\'s idioms, security and performance. Most state *"MUST BE USED '
     'for <language> projects"* — run them on every change in that stack.'),
]

covered = set()
for title, pred, blurb in FUNC:
    # First match wins, so every agent lands in exactly one group and the
    # group counts sum to the total agent count.
    items = sorted([a for a in AGENTS
                    if a['name'] not in covered and pred(a)],
                   key=lambda x: x['name'].lower())
    for a in items:
        covered.add(a['name'])
    if not items:
        continue
    w('### %s — %d agent%s' % (title, len(items),
                                    '' if len(items) == 1 else 's'))
    w('')
    w('%s' % blurb)
    w('')
    w('| Agent | Role | Model | Tools |')
    w('|---|---|---|---|')
    for a in items:
        d = clip(a['desc'], 155) or '_(no description — read the file)_'
        w('| `%s` | %s | %s | %s |' % (a['name'], d, a['model'] or '—',
                                       a['tools'].replace('|', '\\|') or '—'))
    w('')

rest = [a for a in AGENTS if a['name'] not in covered]
if rest:
    w('### Other — %d agent%s' % (len(rest), '' if len(rest) == 1 else 's'))
    w('')
    w('| Agent | Role | Model |')
    w('|---|---|---|')
    for a in sorted(rest, key=lambda x: x['name'].lower()):
        d = clip(a['desc'], 155) or '_(no description — read the file)_'
        w('| `%s` | %s | %s |' % (a['name'], d, a['model'] or '—'))
    w('')

w('### Held aside — %d pipeline-internal agents' % len(EXCLUDED))
w('')
w('These are **dispatch targets, not tools**. Each is invoked by an orchestrating agent and')
w('expects parameters only that parent supplies. Invoking one directly will fail.')
w('')
w('| Agent | Dispatched by | Why not standalone |')
w('|---|---|---|')
for e in sorted(EXCLUDED, key=lambda x: (x['orchestrator'], x['name'])):
    w('| `%s` | %s | %s |' % (e['name'], e['orchestrator'], e['reason']))
w('')
w('Full detail in `agents/_agent-specific/README.md`.')
w('')

# ------------------------------------------------------ 6. ensembles
w('## 6. Ensemble & Workflow Patterns')
w('')
w('Some agents are meant to run as a sequence, not in isolation.')
w('')
w('### The GAN harness — build a product from one line')
w('')
w('```')
w('gan-planner  -> expands the prompt into a product spec (features, sprints, criteria)')
w('gan-generator -> implements against the spec, reads feedback, iterates')
w('gan-evaluator -> tests the live app via Playwright, scores against the rubric')
w('                 ^                                          |')
w('                 +------------------------------------------+')
w('```')
w('')
w('All three run on **opus**. Invoke `gan-planner` first with the one-line prompt.')
w('')
w('### The ECC pipeline — feature from idea to commit')
w('')
w('```')
w('planner -> tdd-guide -> code-reviewer -> security-reviewer -> commit')
w('```')
w('')
w('`ecc-coordinator` runs this whole sequence. Use it when the user asks for "the ECC pipeline"')
w('or `/ecc`.')
w('')
w('### The claude-security pipeline — scan then fix')
w('')
w('```')
w('claude-security (orchestrator)')
w('  ├─ scan-inventory  -> scan-loader -> scan-researcher -> scan-verifier   (read-only)')
w('  └─ patch-generator  -> patch-verifier                                  (write)')
w('```')
w('')
w('The scan phase is read-only; the patch phase writes. Invoke `claude-security` with the repo')
w('root and let it drive. See `agents/_agent-specific/README.md`.')
w('')
w('### The open-source pipeline — ship a repo publicly')
w('')
w('```')
w('opensource-forker    -> copies files, strips secrets, replaces internal refs, cleans history')
w('opensource-sanitizer -> verifies no leaks remain (PASS / FAIL / PASS-WITH-WARNINGS)')
w('opensource-packager  -> CLAUDE.md, setup.sh, README, LICENSE, CONTRIBUTING, issue templates')
w('```')
w('')
w('Run in order. `opensource-sanitizer` is the gate — it must pass before packaging.')
w('')
w('### The skill-creator-plus evaluation loop')
w('')
w('```')
w('comparator -> blind A/B judgement (does not know which skill produced which)')
w('analyzer   -> unblids the result, explains why the winner won')
w('grader     -> scores against the expectations')
w('```')
w('')
w('Driven by `scripts/run_loop.py` inside the `skill-creator-plus` pack. Use it when you want')
w('to know whether a change to a skill actually made it better.')
w('')
w('### Agent creation loop')
w('')
w('```')
w('agent-creator -> generate the agent config')
w('agent-evaluator -> score the output on accuracy, completeness, clarity, actionability, conciseness')
w('skill-reviewer / plugin-validator -> check structure')
w('```')
w('')

# ------------------------------------------------------ 7. standalone packs
w('## 7. The Standalone Packs')
w('')
w('%d hand-authored packs live at the top level of this folder. They are **not** generated'
  % len(PACKS))
w('marketplace content — each has reference files and an enforced workflow, and they are the')
w('highest-quality material in the library.')
w('')
w('| Pack | Path | What it does | Why it is better than the marketplace equivalent |')
w('|---|---|---|---|')
for _p in PACKS:
    w('| `%s` | `%s/` | %s | %s |'
      % (_p['name'], _p['name'], _p.get('detail', _p.get('summary', '')),
         _p.get('why', '—')))
w('')
w('> `humanizer` and `skill-creator-plus` also appear under `skills/` as part of the uniform')
w('> library. The top-level copies are the curated originals — prefer them.')
w('')
w('### Upstream collections')
w('')
w('Unlike the packs above, these are **third-party clones kept whole** — their own `LICENSE`')
w('and their own git history — rather than material written for this library. Their skills are')
w('picked up by the ordinary scanner and appear in `skills/` like everything else.')
w('')
w('| Collection | Path | Upstream | Licence | What it does |')
w('|---|---|---|---|---|')
w('| `ponytail` | `ponytail/` | https://github.com/dietrichgebert/ponytail | MIT | "Lazy senior dev" mode — the 7-rung ladder (does it need to exist → already in this codebase → standard library → native platform feature → installed dependency → can it be one line → otherwise the minimum that works), plus one small test for any non-trivial logic. Never cuts trust-boundary validation, data-loss error handling, security, accessibility or hardware calibration. |')
w('')
w('Ponytail ships 6 skills: `ponytail` (the behaviour mode, with `lite`/`full`/`ultra` levels),')
w('`ponytail-review` (per-change quality review), `ponytail-audit` (repo-wide quality audit),')
w('`ponytail-debt` (harvests `shortcut:` comments into a debt ledger), `ponytail-gain` (a')
w('measured-impact scoreboard) and `ponytail-help` (a quick reference card). They pair with the')
w('review agents in §5 rather than replacing them: let `ponytail-review` find the issues, then')
w('let the language-specific reviewer judge them.')
w('')
w('> `ponytail/AGENTS.md` is the same behaviour as the `ponytail` skill, in the compact')
w('> rules-file form the repo ships for hosts that read project instructions instead of')
w('> skills. It stays in the clone — the library imports skills, not rules files.')
w('')

# ------------------------------------------------------ 8. quick reference
w('## 8. Quick Reference Card')
w('')
w('The ~30 picks that cover most real requests. Reach for these first, then use §2 or §4 to')
w('go deeper.')
w('')
w('| If the task is... | Use this |')
w('|---|---|')
QR = [
    ('writing or changing code in any language', "the stack's reviewer agent (§3) + `skills/coding-standards/` skill"),
    ('reviewing a diff', '`agents/code-reviewer.md`'),
    ('a build is broken', "the stack's build resolver (§3)"),
    ('planning a non-trivial feature', '`agents/planner.md` + `skills/writing-plans/` skill'),
    ('designing a system', '`agents/architect.md` + `skills/architecture-decision-records/` skill'),
    ('writing tests', '`agents/tdd-guide.md` + `skills/tdd-workflow/` skill'),
    ('a security review', '`agents/security-reviewer.md` + `skills/security-review/` skill'),
    ('removing dead code', '`agents/refactor-cleaner.md`'),
    ('the change is over-engineered', '`skills/ponytail/` skill'),
    ('performance is the problem', '`agents/performance-optimizer.md`'),
    ('a document, deck or report', '`document-builder/` pack'),
    ('academic research', '`research-partner/` pack'),
    ('LaTeX will not compile', '`latex-doctor/` pack'),
    ('text sounds like AI', '`humanizer/` pack'),
    ('a database or SQL', '`agents/database-reviewer.md` + `skills/postgres-patterns/` skill'),
    ('deploying', '`agents/deployment-expert.md` + `skills/deployment-patterns/` skill'),
    ('an LLM feature', '`agents/ai-architect.md` + `skills/ai-first-engineering/` skill'),
    ('a prompt is underperforming', '`skills/prompt-optimizer/` skill'),
    ('an autonomous loop is stalling', '`agents/loop-operator.md`'),
    ('building an agent', '`agents/agent-creator.md` + `skills/agent-development/` skill'),
    ('building a skill', '`skill-creator-plus/` pack'),
    ('opening a repo publicly', '`agents/opensource-forker.md` -> `agents/opensource-sanitizer.md` -> `agents/opensource-packager.md`'),
    ('building a UI', '`skills/frontend-patterns/` skill + `agents/a11y-architect.md`'),
    ('email, Slack or Teams triage', '`agents/chief-of-staff.md`'),
    ('a marketing or launch task', '`agents/marketing-agent.md` + `skills/marketing-campaign/` skill'),
    ('lead generation', '`agents/signal-scorer.md` -> `agents/enrichment-agent.md` -> `agents/mutual-mapper.md` -> `agents/outreach-drafter.md`'),
    ('reading an unfamiliar codebase', '`agents/code-explorer.md` + `skills/codebase-onboarding/` skill'),
    ('a modernising migration', '`agents/legacy-analyst.md` -> `agents/business-rules-extractor.md` -> `agents/test-engineer.md` -> `agents/uplift-migrator.md`'),
    ('browser automation', '`skills/agent-browser/` skill'),
    ('network troubleshooting', '`agents/network-troubleshooter.md`'),
    ('bioinformatics data', '`skills/ngs-analysis-router/` skill'),
]
for task, use in QR:
    w('| %s | %s |' % (task, use))
w('')
w('---')
w('')
w('*Generated by `.build_guide.py` from `.library_data.json`. Rebuild with*')
w('*`python3 .build_library.py && python3 .build_guide.py`.*')

path = os.path.join(OUT, 'ROUTING_GUIDE.md')
with open(path, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(L) + '\n')

print('Wrote:', path)
print('lines:', len(L))
print('skills indexed:', len(SKILLS))
print('agents indexed:', len(AGENTS))
