#!/usr/bin/env python3
"""The domain table, extracted verbatim from `.build_guide.py`.

The routing guide prints one domain per skill. The MCP index needs the same
assignment, and the two must never disagree -- a skill the guide files under
"Security" while the index files under "Other" would route differently
depending on which tool answered.

So the table is not copied: it is *imported* from this module, and
`.build_guide.py` imports it from here too. One source of truth.

The matching rule is first-match-wins over the domain order. That is not
incidental -- it is what makes a skill's domain exactly the domain the guide
prints for it, rather than a domain it also happens to match.

Generated from `.build_guide.py` lines 455-646. Do not edit by hand: change
the guide, then re-extract.
"""
import re

DOMAINS = DOMAINS = [
    ('Core engineering practice', ['ask-matt', 'diagnosing-bugs', 'grill-me', 'grilling',
                                   'handoff', '=implement', 'implement-spec', 'pr', 'prototype',
                                   'retro', 'teach', 'to-questionnaire', 'wait-what',
                                   'wayfinder', 'wizard',
                                   'coding-standards', 'codebase-onboarding', 'code-tour',
                                   'codehealth-mcp', 'repo-scan', 'repo-analysis',
                                   'git-workflow', 'github-ops', 'run-pre-commit-checks',
                                   'using-git-worktrees', 'finishing-a-development-branch',
                                   'gateguard', 'search-first', 'error-handling',
                                   'systematic-debugging', 'dependency-management']),
    ('API & integration', ['api-design', 'api-connector-builder', 'mcp-server-patterns',
                           'graphql', 'webhooks', 'integration', 'webhook-security']),
    ('Testing & QA', ['test', 'tdd', 'e2e', 'eval', 'benchmark', 'qa', 'coverage',
                       'verification', 'regression', 'playwright', 'browser-qa', 'fuzzing']),
    ('Security', ['security', 'vuln', 'threat', 'owasp', 'hipaa', 'phi', 'gdpr',
                  'sanitiz', 'secret', 'cve', 'permissioned', 'supply-chain', 'compliance',
                  'customs-trade', 'exploit', 'attack-path', 'pentest', 'sandbox']),
    ('AI & LLM engineering', ['ai-', 'agent', 'llm', 'claude', 'gpt', 'openai', 'anthropic',
                              'prompt', 'rag', 'mcp', 'transformer', 'foundation', 'huggingface',
                              'model', 'finetun', 'inference', 'context-budget', 'token-budget',
                              'cost-aware', 'chat-sdk', 'aiq-', 'vercel-agent', 'machine-learning']),
    ('Data, databases & pipelines', ['sql', 'database', 'schema', 'migration', 'query', 'etl',
                                     'vector', 'embed', 'chunk', 'supabase', 'neon', 'data-',
                                     'dashboard', 'pipeline', 'clickhouse', 'redis', 'mysql',
                                     'postgres', 'prisma', 'jpa', 'exposed']),
    ('DevOps & cloud', ['deploy', 'ci-cd', 'cicd', 'kubernetes', 'docker', 'container',
                        'terraform', 'observab', 'monitor', 'infra', 'provision', 'finishing-a-development-branch',
                        'config-gc', 'sre', 'uptime', 'cloudflare', 'netlify', 'render-',
                        'vercel-', 'wrangler', 'worker', 'airtable', 'serverless']),
    ('Architecture & design', ['domain-modeling', 'codebase-design', 'architect', 'adr',
                                'hexagonal', 'design-system', 'blueprint',
                                'system-design', 'architecture', 'decision-record', 'domain-driven',
                                'clean-architecture', 'microservice', 'event-driven']),
    ('Frontend, UI & accessibility', ['design', 'frontend', 'ui-', 'a11y', 'accessib', 'visual',
                                       'animation', 'motion', 'blender', 'remotion', 'shadcn',
                                       'liquid-glass', 'interface', 'taste', 'geist', 'styling',
                                       'css', 'tailwind']),
    ('Data visualisation', ['visualization', 'visualisation', 'chart', 'd3-', 'canvas2d',
                            'threejs', 'gantt', 'geospatial', 'scrollytelling', 'grammar-of-graphics',
                            'statistical-and', 'node-link', 'dashboard', 'heatmap']),
    ('Backend & API frameworks', ['springboot', 'laravel', 'quarkus', 'django', 'fastapi',
                                  'flask', 'nestjs', 'nuxt', 'dotnet', 'rails', 'laravel-',
                                  'kong', 'grpc', 'graphql']),
    ('Languages & runtimes', ['python', 'typescript', 'javascript', 'react', 'vue', 'angular',
                              'kotlin', 'swift', 'golang', 'rust', 'cpp', 'csharp', 'php',
                              'perl', 'fsharp', 'dart', 'expo', 'bun', 'deno', 'elixir',
                              'haskell', 'lua', 'ruby', 'scala', 'zig', 'solidity',
                              'typer', 'click', 'tyro', 'argparse', 'fire', 'cyclopts']),
    ('Mobile & desktop', ['ios', 'android', 'flutter', 'swiftui', 'mobile', 'desktop',
                           'windows-desktop', 'harmonyos', 'compose', 'react-native', 'expo']),
    ('Documents, writing & content', ['writing-for-agents', 'doc', 'readme', 'write',
                                      'article', 'memo', 'brief',
                                      'report', 'citation', 'cite', 'humanizer', 'latex',
                                      'markdown', 'summar', 'translation', 'visa-doc',
                                      'narrative', 'spec-to-backlog', 'draft-', 'artifact-template',
                                      'knowledge-ops', 'content-engine', 'copywriting']),
    ('Research & analysis', ['research', 'survey', 'study', 'analys', 'literature', 'scholar',
                              'pubmed', 'uspto', 'deep-research', 'scientific', 'taxonomy',
                              'experiment', 'findings', 'citation', 'paper', 'reviewer', 'hypothesis']),
    ('Bioinformatics & life sciences', ['ngs-', 'biom', 'gene', 'genom', 'protein', 'pdb', 'clinvar',
                                        'ensembl', 'uniprot', 'reactome', 'kegg', 'pathway',
                                        'alphafold', 'boltz', 'scrna', 'microbiome', 'proteome',
                                        'ncbi-', 'chembl', 'bindingdb', 'pubchem', 'hmdb',
                                        'biorxiv', 'cellxgene', 'bgee', 'chebi', 'efo-',
                                        'gwas-', 'epigraph', 'eva-', 'metabolights', 'biostudies',
                                        'mgnify', 'gnomad', 'cbioportal', 'encode-', 'quickgo',
                                        'pride-', 'rhea-', 'ipd-', 'finngen', 'ukb-', 'tpmi',
                                        'rxcs-', 'gtex-', 'opentargets', 'civic-', 'gget',
                                        'fund-', 'bull-bear', 'dcf', 'unit-economics']),
    ('Business, finance & product', ['revenue', 'sales', 'crm', 'hubspot', 'invoice', 'billing',
                                     'pricing', 'churn', 'market', 'competitive', 'investor',
                                     'capital', 'working-capital', 'valuation', 'lead', 'deal',
                                     'accounting', 'inventory', 'returns', 'logistics',
                                     'quality-nonconformance', 'tearsheet', 'moody-s',
                                     'chronograph', 'fund-', 'bull-bear']),
    ('Sales, outreach & marketing', ['outreach', 'email', 'slack', 'teams', 'linkedin', 'social',
                                     'seo', 'content', 'ads', 'campaign', 'brand', 'copy',
                                     'newsletter', 'publisher', 'crosspost', 'canva',
                                     'lead-intelligence', 'tiq-', 'wix-', 'shopify-']),
    ('Communication & productivity', ['grill-with-docs', 'notion', 'sharepoint', 'linear',
                                      'jira', 'asana', 'clickup',
                                      'zoom', 'calendar', 'email', 'slack', 'teams', 'todo',
                                      'task', 'meeting', 'minutes', 'gmail', 'drive', 'sheets',
                                      'docs', 'transcribe', 'superhuman', 'magicpath', 'deepnote',
                                      'outlook', 'twilio', 'm5-', 'mech-mu', 'thinking-c']),
    ('Network & infrastructure', ['network', 'bgp', 'vlan', 'wireguard', 'cisco', 'netmiko',
                                  'ssh', 'homelab', 'dns', 'pihole', 'routing', 'firewall',
                                  'connections-optimizer', 'telecom', '5g', 'mimo', 'sdr']),
    ('Game, 3D & video', ['game', '3d', 'three-', 'phaser', 'unity', 'unreal', 'remotion',
                          'video', 'subtitle', 'video-editing', 'heytgen', 'animation',
                          'motion-', 'avatar']),
    ('Skill & agent authoring', ['setup-matt-pocock-skills', 'skill-', 'writing-skills',
                                 'agent-development', 'plugin',
                                 'command-development', 'hook-development', 'hookify',
                                 'prompt-optimizer', 'rules-distill', 'ai-elements', 'scaffold']),
    ('Vendor SaaS APIs', ['twilio-', 'zoom-', 'shopify-', 'netlify-', 'render-', 'vercel-',
                          'stripe', 'circleci', 'hubspot', 'notion-', 'airtable', 'figma-',
                          'slack-', 'teams-', 'outlook-', 'google-calendar', 'google-docs',
                          'google-drive', 'google-sheets', 'google-slides', 'mixpanel', 'posthog',
                          'sentry', 'neon-', 'box-', 'canva-', 'base44', 'openai-ads',
                          'wix-', 'chrome-devtools', 'circleback', 'deepnote', 'gcal',
                                  'gsheets', 'gdrive', 'gmail-', 'linear-', 'asana-',
                                  'clickup-', 'monday', 'loom', 'calendly', 'attio',
                                  'apollo', 'zoominfo', 'zoominfotech', 'clari',
                                  'salesforce', 'hubspot-', 'zapier', 'nango', 'merge',
                                  'segment', 'amplitude', 'mixpanel-', 'intercom', 'zendesk',
                                  'sendgrid', 'mailchimp', 'klaviyo', 'braze', 'iterable',
                                  'customer-io', 'postmark', 'mailgun', 'sesame',
                                  'open-ai', 'anthropic-', 'pinecone', 'weaviate', 'qdrant',
                                  'chroma', 'llamaindex', 'langchain', 'crewai', 'autogen',
                                  'durable', 'wrangler', 'supabase-', 'clerk', 'auth0',
                                  'workos', 'sentry-', 'grafana', 'datadog', 'newrelic']),
    ('Agent orchestration & workflows', ['orch-', 'orchestrat', 'workflow', 'dispatch',
                                         'subagent', 'continuous-learning', 'autonomous',
                                         'dmux', 'council', 'harness', 'swarm', 'multi-agent',
                                         'background', 'cron', 'tmux', 'terminal-ops',
                                         'launch-readiness', 'dynamic-workflow', 'run-workflow',
                                         'migrate-workflows', 'project-flow-ops',
                                         'execution-optimizer', 'plan-orchestrate',
                                         'using-superpowers', 'start', 'initiate', 'template',
                                         'tearsheet', 'agentic-os', 'agentic-engineering',
                                         'intent-driven-development', 'iterative-retrieval']),
    ('Code review & quality', ['code-review', 'reviewer', 'pylance', 'plankton',
                               'plankton-code-quality', 'click-path-audit', 'validation',
                               'triage', 'fix-finding', 'finding-discovery', 'gap-analysis',
                               'investigation-mode', 'vulnerability-writeup', 'production-audit',
                               'risk-analysis-audit', 'risk-analysis', 'precedent-transactions',
                               'explore', 'scribe', 'prodigy']),
    ('Frontend platforms & meta-frameworks', ['nextjs', 'next-forge', 'nuxt', 'vite',
                                              'turbo', 'swr', 'v0', 'workers', 'web-perf',
                                              'searxng', 'geistdocs', 'geist', 'satori',
                                              'impeccable', 'gsap', 'make-interfaces-feel-better',
                                              'hyperframes', 'imagegen', 'ncc', 'playground',
                                              'nanoclaw', 'nemoclaw', 'openclaw', 'flox',
                                              'uncloud', 'yeet', 'brick', 'inflection',
                                              'appkit', 'packaging-notarization', 'swiftpm',
                                              'omniverse', 'vdr-index', 'vdr', 'spacecraft',
                                              'math-olympiad', 'cardputer', 'brighthire',
                                              'catalyst-by-zoho', 'mixpanelyst', 'hisabkora',
                                              'x-api', 'probe-sdk', 'rivet-sdk', 'exa-search',
                                              'ck', 'ucp', 'ucp-', 'ncc', 'santa-method',
                               'tinystruct', 'v0-dev', 'hermes-imports', 'generate-snapshot',
                               'eod-wrapup', 'guidance-tracker', 'morning-briefing',
                               'conversation-intelligence', 'startup', 'project-capability',
                               'product-capability', 'product-lens', 'project-artifact',
                               'project-guidelines', 'env-vars', 'settings-precedence',
                               'smart-file-renaming', 'use-dom', 'window-management',
                               'canonical-decision-ledger', 'recursive-decision-ledger',
                               'launch-readiness', 'santa-method', 'ncc']),
    ('Legacy, migration & cost', ['legacy', 'migrat', 'inherit-legacy', 'harvest-from',
                                  'cost-tracking', 'ecc-tools-cost', 'runtime-cache',
                                  'latency-critical', 'cost-aware', 'strategic-compact',
                                  'workspace-surface', 'cross-platform', 'temporal',
                                  'view-refactor', 'pylance', 'undo', 'upgrade']),
    ('Legal, compliance & policy', ['compliance', 'gdpr', 'hipaa', 'legal', 'contract',
                                    'litigation', 'signing-entitlements', 'safety-guard',
                                    'regulatory', 'attest', 'policy', 'governance']),
    ('Messaging, notifications & scheduling', ['notification', 'unified-notifications',
                                               'messages-ops', 'google-workspace-ops',
                                               'receipts', 'morning-briefing', 'eod-wrapup',
                                               'cron', 'schedule', 'dispatching-parallel',
                                               'production-scheduling', 'metric-pack',
                                               'signing', 'unified']),
    ('Data sources, connectors & research corpus', ['exa-search', 'search-company-knowledge',
                                                    'citations', 'zotero', 'litigation-update',
                                                    'nutrient-document', 'videodb',
                                                    'replayio', 'hf-cli', 'ib-deck',
                                                    'hex', 'eo-browser', 'browser',
                                                    'document-processing', 'search',
                                                    'scraping', 'corpus']),
    ('AI platform toolchains', ['agents-sdk', 'build-chatgpt-app', 'build-mcpb',
                                'chatgpt-app-submission', 'transformers-js', 'agy-',
                                'antigravity', 'dynamo-', 'micro', 'example-command',
                                'ml-adoption-playbook', 'ml-', 'aiq-', 'pytorch-patterns']),
    ('Product, planning & team ops', ['to-spec', 'to-tickets', 'brainstorming',
                                      'executing-plans', 'writing-plans',
                                      'fa-jobs-to-be-done', 'team-builder', 'setup',
                                      'bootstrap', 'canary-watch', 'run-smoke-tests',
                                      'reports-pdfs-and-slide', 'document-quality-check',
                                      'document-builder', 'documentation-lookup',
                                      'documentation-', 'automation-audit-ops',
                                      'automation', 'deployment-patterns', 'observability',
                                      'telemetry', 'github', 'gh-fix-ci', 'gh-address-comments',
                                      'caveman-mode', 'nuxt4-patterns', 'turbopack',
                                      'turborepo', 'java-lsp-tools', 'nodejs-keccak256',
                                      'backend-patterns', 'accessibility']),
    ('Industry verticals & trading', ['carrier-relationship', 'energy-procurement',
                                      'earnings-', 'industry', 'irl-tracker',
                                      'ito-', 'comp-sheet', 'comps', 'payments',
                                      'marketplace', 'cuopt-user-rules', 'evm-token',
                                      'spatial', 'healthcare-cdss', 'healthcare-emr',
                                      'logistics', 'freight', 'trading', 'portfolio']),
    ('ECC meta-guides & fixtures', ['ecc-guide', 'configure-ecc', 'alpha', 'beta']),
    ('Discord channel', ['access', 'configure']),
    ('App auth & content platforms', ['auth', 'cms']),
    ('macOS app development', ['build-run-debug']),
    # Ponytail — upstream collection at `ponytail/`. The keyword matches all 6
    # skill names and nothing else in the library.
    ('Lean code & minimalism', ['ponytail']),
]

def norm(name):
    """Lowercase, with `-`, `_` and `/` turned into spaces."""
    return ' '.join(re.sub(r'[-_/]+', ' ', name.lower()).split())


def hit(name, keys):
    """Word-boundary keyword match.

    Word boundaries matter: `hit('agent-creator', ['agent'])` must not fire
    on a substring in the middle of a longer word, and `hit('test', ['test'])`
    must not fire on `testing-writer` unless the whole word matches.

    A key written as "=name" matches the WHOLE normalised name and
    nothing else. It is the escape for a name that is a word of a
    longer name, where no keyword can tell them apart: the key
    "implement" also matches "figma-implement-motion", because
    collapsing the hyphens gives "figma implement motion".
    """
    n = norm(name)
    for k in keys:
        if k.startswith('='):
            # an exact-name key: the whole normalised name, nothing else
            if n == norm(k[1:]):
                return True
            continue
        kw = ' '.join(re.sub(r'[-_/]+', ' ', k.lower()).split())
        if not kw:
            continue
        pat = (r'(?<![a-z0-9])' + r'\s+'.join(re.escape(w) for w in kw.split())
               + r'(?![a-z0-9])')
        if re.search(pat, n):
            return True
    return False


def assign(names):
    """Map each name to its domain, first match wins.

    Returns (domain_of, ordered_domains). `ordered_domains` preserves the
    table's order and appends "Other / uncategorised" if anything is left
    over, exactly as the guide does.
    """
    domains = list(DOMAINS)
    assigned = set()
    domain_of = {}
    for dom, keys in domains:
        for name in names:
            if name not in assigned and hit(name, keys):
                assigned.add(name)
                domain_of[name] = dom

    leftover = [n for n in names if n not in assigned]
    if leftover:
        domains.append(('Other / uncategorised', []))
        for name in leftover:
            assigned.add(name)
            domain_of[name] = 'Other / uncategorised'
    return domain_of, domains
