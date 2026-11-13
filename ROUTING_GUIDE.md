# Routing Guide — Skills & Agents Library

**Purpose:** given any task, find the right skill or agent, and know when to use which.

| | |
|---|---|
| Skills | **1032** — instructions, playbooks and reference material the model follows |
| Agents | **115** — specialised sub-agents invoked for one bounded role |
| Held aside | 14 pipeline-internal agents (see `agents/_agent-specific/`) |
| Inventory | `SKILLS_AND_AGENTS_REPORT.md` — full census with sources |
| Machine index | `.library_data.json` |

---

## 1. How to use this guide

### The decision procedure

```
1. Read the task.
2. Match it to a task type in §2  ->  get the skill and/or agent.
3. If the task names a language or framework, use §3 first — it is more specific.
4. Open the skill and FOLLOW IT. A skill is instructions, not a suggestion.
5. If the task needs judgement rather than procedure, invoke the agent.
```

### Skill or agent?

| | **Skill** | **Agent** |
|---|---|---|
| What it is | A `SKILL.md` you read and follow | A sub-agent you delegate a role to |
| Best for | "How should I do X?" | "Do X and judge the result" |
| You control | Every step | The agent does the work |
| Examples | `api-design`, `tdd-workflow`, `frontend-patterns` | `code-reviewer`, `python-reviewer`, `security-reviewer` |
| Cost | Cheap — inline context | Higher — separate context window |

**Rule of thumb:** if the task is *"follow these conventions"* use a skill. If the task is
*"review / audit / fix / analyse this thing"* use an agent — most reviewers are marked
*"MUST BE USED for <language> projects"*, which means they are expected to run on every
change in that stack, not on request.

### Both together

The strongest pattern available here is **skill for method + agent for judgement**:

```
Skill:  tdd-workflow          (how to write the test first)
Agent:  python-reviewer       (judges whether the result is right)
```

## 2. Task-Type Index — the main router

Find your task type. Read across for the recommended skill and agent.

| Task | Skill (how) | Agent (judgement) | Notes |
|---|---|---|---|
| **Write new code** | `api-design`, `coding-standards`, `python-patterns`, `react-patterns`, `backend-patterns` | `code-architect`, `planner` | Skill gives the conventions; the architect/planner agent shapes the feature first. |
| **Review code I did not write** | `code-review`, `codebase-onboarding` | `code-reviewer`, `code-explorer` | Reviewer agent is the default. The generic `code-reviewer` covers any language; |
| **Fix a failing build** | `error-handling`, `systematic-debugging`, `build-run-debug` | `build-error-resolver`, `react-build-resolver`, `java-build-resolver` | Use the build resolver for the language. It makes minimal diffs and no refactors. |
| **Debug a runtime bug** | `systematic-debugging`, `debug-failing-test`, `test-triage` | `debug`, `silent-failure-hunter` | `systematic-debugging` for method; `debug` is the Java-specific VS Code agent. |
| **Refactor / simplify** | `coding-standards`, `codehealth-mcp` | `refactor-cleaner` | The `refactor-cleaner` agent runs knip/depcheck/ts-prune to find dead code. |
| **Stop over-engineering** | `ponytail` | `architecture-critic` | `ponytail` applies a 7-rung ladder — does it need to exist, is it already here, stdlib, native, a dependency, one line, else the minimum that works — and never cuts security, validation or accessibility. |
| **Review a change for quality** | `ponytail-review` | `code-reviewer` | `ponytail-review` reads the connected code, not just the diff, and explains each finding in plain English. |
| **Audit a whole repo for quality** | `ponytail-audit`, `ponytail-review` | `security-auditor` | `ponytail-audit` is the repo-wide pass; `ponytail-review` is per-change. |
| **Remove dead code** | `codehealth-mcp`, `repo-scan` | `silent-failure-hunter` | Always pair with `silent-failure-hunter` — dead code often hid a swallowed error. |
| **Design an architecture** | `architecture-decision-records`, `hexagonal-architecture`, `design-system`, `blueprint`, `intent-driven-development` | `architect`, `code-architect`, `architecture-critic` | Plan first, then implement. `architecture-critic` challenges over-engineering. |
| **Plan a feature** | `plan-orchestrate`, `writing-plans`, `executing-plans`, `spec-to-backlog` | `planner`, `Plan`, `code-architect` | Use `planner` for complex features and refactors; it is marked PROACTIVE. `Plan` is the read-only Copilot-Chat variant. |
| **Ask a question about the code** | `codebase-onboarding`, `code-tour` | `Ask`, `code-explorer`, `Explore` | `Ask` and `Explore` are read-only — they answer without changing anything. Use `Explore` instead of chaining many search/read calls. |
| **Set up a new project** | `git-workflow`, `project-flow-ops`, `bootstrap`, `setup` | `scaffolder` | `scaffolder` writes the skeleton, domain model, API stubs and acceptance tests. |
| **Write tests** | `tdd-workflow`, `test-driven-development`, `python-testing`, `golang-testing`, `springboot-tdd`, `django-tdd`, `laravel-tdd`, `quarkus-tdd`, `cpp-testing`, `csharp-testing`, `dart-flutter-patterns`, `react-testing` | `tdd-guide`, `pr-test-analyzer` | `tdd-guide` enforces write-tests-first and 80%+ coverage. |
| **Fix flaky / failing tests** | `debug-failing-test`, `test-triage`, `e2e-testing` | `pr-test-analyzer`, `e2e-runner` | `e2e-runner` quarantines flaky tests and uploads artifacts. |
| **Run end-to-end tests** | `e2e-testing`, `browser-qa`, `run-e2e-tests`, `agent-browser-verify` | `e2e-runner` | `agent-browser-verify` does a quick visual gut-check after a dev server starts. |
| **Ship to production** | `deployment-patterns`, `deployments-cicd`, `finishing-a-development-branch` | `deployment-expert` | `deployment-expert` covers preview URLs, promotions, rollbacks, env vars, domains. |
| **Set up CI/CD** | `deployments-cicd`, `expo-cicd-workflows`, `circleci-config` | `deployment-expert` | Pick the vendor skill — CircleCI, Expo, Render, Netlify, Vercel all have one. |
| **Containerise** | `docker-patterns` | — | Skill only. |
| **Infrastructure / Kubernetes** | `kubernetes-patterns`, `deployments-cicd` | `architect` | Note: there is no dedicated Kubernetes agent — use `architect`. |
| **Manage a database** | `postgres-patterns`, `mysql-patterns`, `database-migrations`, `prisma-patterns`, `clickhouse-io`, `redis-patterns`, `jpa-patterns` | `database-reviewer` | `database-reviewer` is PostgreSQL-specific: query optimisation, schema design, security. |
| **Write SQL / optimise queries** | `postgres-patterns`, `mysql-patterns` | `database-reviewer` |  |
| **Design a data pipeline** | `data-throughput-accelerator`, `research-ops`, `recsys-pipeline-architect`, `data-scraper-agent` | — | Note: `data-scraper-agent` is a skill, not an agent — it collects the data rather than designing the pipeline. |
| **Analyse data / visualise** | `data-visualization`, `d3-data-visualization`, `canvas2d-data-visualization`, `threejs-data-visualization`, `statistical-and-uncertainty-visualization`, `grammar-of-graphics-and-declarative-visualization`, `dashboards-and-real-time-visualization` | `performance-optimizer` | There are ~15 visualisation skills — see §4 for the full list. |
| **Build a dashboard** | `dashboard-builder`, `dashboard-expert`, `artifact-template-analytics-dashboard` | — |  |
| **Build a web frontend** | `frontend-patterns`, `frontend-design`, `frontend-design-direction`, `design-system`, `ui-demo`, `frontend-app-builder`, `make-interfaces-feel-better` | `a11y-architect` | `a11y-architect` covers WCAG 2.2 and should be consulted for any UI component. |
| **Write a React app** | `react-patterns`, `react-performance`, `react-best-practices`, `nextjs-turbopack`, `shadcn` | `react-reviewer`, `react-build-resolver` | Use `react-reviewer` for any `.tsx`/`.jsx` change — it is marked MUST BE USED. |
| **Write a Vue app** | `vue-patterns`, `ui-to-vue`, `vite-patterns` | `vue-reviewer` |  |
| **Build a mobile app** | `swiftui-patterns`, `swift-concurrency-6-2`, `kotlin-patterns`, `android-clean-architecture`, `flutter-dart-code-review` | `flutter-reviewer`, `kotlin-reviewer`, `swift-reviewer` | Note: there is no native SwiftUI reviewer — use `swift-reviewer` (general Swift). |
| **Build a CLI** | `typer`, `coding-standards` | — | `typer` covers the Typer framework — typing, CLI structure, and version-current patterns. |
| **Build an API** | `api-design`, `api-connector-builder`, `mcp-server-patterns` | `database-reviewer` | `api-design` covers resource naming, status codes, pagination, versioning, rate limits. |
| **Build an MCP server** | `mcp-server-patterns`, `build-mcp-server`, `building-mcp-server-on-cloudflare` | — |  |
| **Build an AI / LLM app** | `ai-first-engineering`, `ai-sdk`, `chat-sdk`, `agents-sdk`, `mcp-server-patterns` | `ai-architect`, `agent-creator` | `ai-architect` chooses between AI SDK patterns, providers, agents, workflows, MCP. |
| **Write a prompt / agent harness** | `prompt-optimizer`, `agent-harness-construction`, `agentic-engineering`, `context-budget`, `token-budget-advisor` | `agent-creator`, `agent-evaluator`, `harness-optimizer` | `agent-creator` generates the agent config; `agent-evaluator` scores the output. |
| **Reduce cost / latency of LLM calls** | `cost-aware-llm-pipeline`, `cost-tracking`, `context-budget`, `token-budget-advisor`, `latency-critical-systems` | `harness-optimizer` |  |
| **Run an autonomous loop** | `autonomous-loops`, `continuous-agent-loop`, `continuous-learning` | `loop-operator`, `observer` | `loop-operator` monitors progress and intervenes when loops stall. |
| **Secure a codebase** | `security-review`, `security-scan`, `deep-security-scan`, `threat-model`, `attack-path-analysis`, `supply-chain` | `security-reviewer`, `security-auditor` | `security-reviewer` flags secrets, SSRF, injection, unsafe crypto, OWASP Top 10. |
| **Prepare a codebase for open source** | `opensource-pipeline` | `opensource-forker`, `opensource-sanitizer`, `opensource-packager` | Three-stage pipeline: fork -> sanitize -> package. Run it in order. |
| **Research a topic** | `deep-research`, `research-ops`, `literature-review`, `research-router-skill`, `market-research`, `research-partner` | — | For academic work prefer the hand-authored `research-partner` pack (§7). |
| **Write a document / report / deck** | `document-builder`, `article-writing`, `competitive-report-structure`, `documentation-lookup` | `docs-lookup` | Prefer the hand-authored `document-builder` pack — it enforces spec-then-verify. |
| **Write LaTeX** | `latex-doctor` | — | Only one LaTeX skill — it is comprehensive. |
| **Make text sound human** | `humanizer` | — | Prefer the hand-authored `humanizer` pack. |
| **Write / edit prose** | `writing-skills`, `caveman-mode`, `brand-voice` | — | `caveman-mode` is a style override, not a writing aid. |
| **Update documentation** | `documentation-lookup` | `docs-lookup` | `docs-lookup` pulls current docs via Context7 MCP. |
| **Handle email / Slack / Teams** | `email-ops`, `messages-ops`, `slack-reply-drafting`, `teams-reply-drafting`, `gmail-inbox-triage` | `chief-of-staff` | `chief-of-staff` triages across email, Slack, LINE and Messenger into 4 tiers. |
| **Manage a calendar** | `google-calendar-meeting-prep`, `outlook-calendar-meeting-prep` | — | Both Google and Outlook variants exist. |
| **Manage a knowledge base** | `knowledge-ops`, `notion-knowledge-capture` | — |  |
| **Market a product** | `marketing-campaign`, `content-engine`, `brand-discovery`, `brand-voice`, `competitive-platform-analysis`, `social-publisher`, `crosspost` | `marketing-agent`, `seo-specialist` | `marketing-agent` handles campaign planning through content calendars. |
| **Do SEO** | `seo` | `seo-specialist` |  |
| **Generate leads / outreach** | `lead-intelligence`, `social-graph-ranker`, `investor-outreach` | `signal-scorer`, `enrichment-agent`, `mutual-mapper`, `outreach-drafter` | Four-stage: score -> enrich -> map mutuals -> draft outreach. |
| **Do finance / valuation** | `unit-economics`, `capital-allocation`, `dcf`, `working-capital`, `returns-reverse-logistics`, `bull-bear`, `fund-comparison` | — |  |
| **Work with a vendor API** | `twilio-send-message`, `zoom-meeting-sdk-web`, `shopify-liquid`, `figma-design-to-code`, `netlify-deploy`, `render-deploy`, `vercel-cli`, `stripe-best-practices`, `airtable-overview`, `hubspot`, `notion-meeting-intelligence`, `circleci-cli` | `zoom-integration-reviewer`, `zoom-oauth-scope-auditor` | ~200 vendor skills — see §4 for the full vendor list. |
| **Optimise performance** | `web-perf`, `react-performance`, `pylance-python-profiling`, `swiftui-performance-audit`, `android-performance` | `performance-optimizer` | `web-perf` measures Core Web Vitals for any site; the others are platform-specific. `performance-optimizer` covers bottlenecks, bundle size, memory leaks, render cost. |
| **Improve accessibility** | `accessibility`, `frontend-a11y`, `accessibility-and-inclusive-visualization` | `a11y-architect` |  |
| **Manage CI quality gates** | `run-pre-commit-checks`, `run-smoke-tests`, `run-integration-tests` | `code-reviewer` | The VS Code Python extension ships several run-* skills worth reusing. |
| **Use git properly** | `git-workflow`, `using-git-worktrees`, `finishing-a-development-branch`, `github-ops`, `gh-fix-ci`, `gh-address-comments`, `permissioned-github` | — |  |
| **Change a dependency** | — | `dependency-lockfile-custodian` | No skill covers dependency hygiene. The custodian edits the manifest, regenerates the lockfile, and reports a manifest/lockfile mismatch as a failure. |
| **Handle a PR** | `requesting-code-review`, `receiving-code-review` | `pr-test-analyzer`, `code-reviewer` |  |
| **Work with a monorepo** | `turborepo`, `turbopack`, `workspace-surface-audit` | — |  |
| **Do ML / MLOps** | `mle-workflow`, `pytorch-patterns`, `recsys-pipeline-architect`, `ml-adoption-playbook`, `foundation-models-on-device` | `mle-reviewer` | `mle-reviewer` covers data contracts, reproducibility, offline/online eval, monitoring. |
| **Work with healthcare data** | `healthcare-phi-compliance`, `hipaa-compliance`, `healthcare-cdss-patterns`, `healthcare-emr-patterns`, `healthcare-eval-harness` | `healthcare-reviewer` | `healthcare-reviewer` covers clinical safety, CDSS accuracy, PHI compliance. |
| **Do bioinformatics / NGS** | `ngs-analysis-router`, `ngs-bulk-rnaseq`, `ngs-fastq-qc`, `ngs-dna-variant-calling`, `ncbi-entrez-skill` | — | Use `ngs-analysis-router` first — it routes to the right pipeline skill. |
| **Work with protein structure** | `alphafold-skill`, `boltz-protein-design`, `boltz-structure-and-binding` | — |  |
| **Query a biomedical DB** | `pubchem-pug-skill`, `chembl-skill`, `bindingdb-skill`, `ncbi-blast-skill`, `uniprot-skill`, `clinvar-variation-skill` | — | ~45 database skills — see §4. |
| **Build a network / homelab** | `homelab-network-setup`, `homelab-network-readiness`, `homelab-vlan-segmentation`, `homelab-wireguard-vpn`, `cisco-ios-patterns`, `netmiko-ssh-automation` | `homelab-architect`, `network-architect`, `network-troubleshooter`, `network-config-reviewer` | `network-troubleshooter` is read-only and OSI-layered. |
| **Automate the browser** | `agent-browser`, `agent-browser-verify`, `browser-qa` | — |  |
| **Build a game / 3D** | `web-game-foundations`, `game-studio`, `three-webgl-game`, `phaser-2d-game`, `react-three-fiber-game`, `motion-foundations` | — |  |
| **Make a video** | `remotion-video-creation`, `video-editing`, `heygen-video`, `heygen-avatar` | — |  |
| **Create a skill** | `skill-creator`, `writing-skills`, `skill-development`, `skill-creator-plus` | `agent-creator`, `skill-reviewer` | Prefer the hand-authored `skill-creator-plus` pack (§7) — it has an eval harness. |
| **Create an agent** | `agent-development`, `command-development`, `hook-development` | `agent-creator`, `agent-evaluator` |  |
| **Create a plugin** | `plugin-structure`, `plugin-creator` | `plugin-validator` |  |
| **Add a skill or agent to this library** | `skill-library-adder` | `skill-reviewer` | The `skill-library-adder` pack (§7) — where the file goes, what the scanner accepts, and the licence and publish rules. |
| **Migrate a legacy codebase** | `codebase-onboarding`, `repo-scan`, `upgrade-stripe` | `legacy-analyst`, `business-rules-extractor`, `test-engineer`, `uplift-migrator`, `version-delta-analyst` | The modernisation pipeline: analyse -> extract rules -> pin tests -> migrate. |
| **Write an MCP tool / connector** | `api-connector-builder`, `mcp-server-patterns` | — |  |
| **Plan a launch / campaign** | `marketing-campaign`, `investor-materials` | `marketing-agent` | The 18 `artifact-template-*` skills are ready-made document templates. |

## 3. Language & Framework Quick Index

The highest-frequency lookup. For any change in one of these stacks, the agent column is
usually marked **MUST BE USED** in its own description — meaning it is expected to run on
every change, not on request.

| Stack | Patterns skill | Reviewer agent | Build resolver | Testing skill |
|---|---|---|---|---|
| Python | `python-patterns` | `python-reviewer` | `build-error-resolver` | `python-testing` |
| TypeScript / JavaScript | `coding-standards` | `coding-standards` | `build-error-resolver` | `e2e-testing` |
| React / Next.js | `react-patterns` | `react-reviewer` | `react-build-resolver` | `react-testing` |
| Vue / Nuxt | `vue-patterns` | `vue-reviewer` | `build-error-resolver` | — |
| Angular | `angular-developer` | — | `build-error-resolver` | — |
| Node / NestJS | `nestjs-patterns` | — | `build-error-resolver` | — |
| Svelte / SvelteKit | — | — | `build-error-resolver` | — |
| Java / Spring Boot | `springboot-patterns` | `java-reviewer` | `java-build-resolver` | `springboot-tdd` |
| Java / Quarkus | `quarkus-patterns` | `java-reviewer` | `java-build-resolver` | `quarkus-tdd` |
| Kotlin / Android | `kotlin-patterns` | `kotlin-reviewer` | `kotlin-build-resolver` | `kotlin-testing` |
| Swift / iOS | `swiftui-patterns` | `swift-reviewer` | `swift-build-resolver` | `swift-protocol-di-testing` |
| Dart / Flutter | `dart-flutter-patterns` | `flutter-reviewer` | `dart-build-resolver` | `flutter-dart-code-review` |
| Go | `golang-patterns` | `go-reviewer` | `go-build-resolver` | `golang-testing` |
| Rust | `rust-patterns` | `rust-reviewer` | `rust-build-resolver` | `rust-testing` |
| C++ | `cpp-coding-standards` | `cpp-reviewer` | `cpp-build-resolver` | `cpp-testing` |
| C# / .NET | `dotnet-patterns` | `csharp-reviewer` | `build-error-resolver` | `csharp-testing` |
| PHP / Laravel | `laravel-patterns` | `php-reviewer` | `build-error-resolver` | `laravel-tdd` |
| Ruby on Rails | — | — | `build-error-resolver` | — |
| Perl | `perl-patterns` | — | `build-error-resolver` | `perl-testing` |
| F# | `fsharp-testing` | `fsharp-reviewer` | `build-error-resolver` | `fsharp-testing` |
| Django | `django-patterns` | `django-reviewer` | `django-build-resolver` | `django-tdd` |
| FastAPI | `fastapi-patterns` | `fastapi-reviewer` | `build-error-resolver` | `fastapi-patterns` |
| Expo / React Native | `expo-module` | `react-reviewer` | `react-build-resolver` | `expo-module` |
| HarmonyOS / ArkTS | — | `harmonyos-app-resolver` | `harmonyos-app-resolver` | — |
| SQL / PostgreSQL | `postgres-patterns` | `database-reviewer` | — | `postgres-patterns` |
| Prisma / ORM | `prisma-patterns` | `database-reviewer` | — | `prisma-patterns` |
| Bun | `bun-runtime` | `coding-standards` | `build-error-resolver` | `bun-runtime` |
| PyTorch | `pytorch-patterns` | `mle-reviewer` | `pytorch-build-resolver` | `pytorch-patterns` |
| Vite | `vite-patterns` | — | `build-error-resolver` | `vite-patterns` |
| Next.js | `nextjs` | `react-reviewer` | `react-build-resolver` | `nextjs-turbopack` |

> A dash means no dedicated skill or agent exists for that stack — fall back to the
> language-agnostic ones (`coding-standards`, `code-reviewer`, `build-error-resolver`)
> or the general `tdd-workflow` / `e2e-testing` skills.

## 4. Skill Catalogue by Domain

All 1032 skills, grouped. The **use when** column is condensed from each skill's own
frontmatter description — read that file for the full text.

### 4.1 Core engineering practice — 31 skills

| Skill | Use when |
|---|---|
| `ask-matt` | Ask which skill or flow fits your situation. A router over the skills in this repo. |
| `code-tour` | Create CodeTour `.tour` files — persona-targeted, step-by-step walkthroughs with real file and line anchors. Use for onboarding... |
| `codebase-onboarding` | Analyze an unfamiliar codebase and generate a structured onboarding guide with architecture map, key entry points, conventions, and... |
| `codehealth-mcp` | Real-time structural Code Health via CodeScene MCP — review before edits, verify score deltas after changes, gate commits and PRs.... |
| `coding-standards` | Baseline cross-project coding conventions for naming, readability, immutability, and code-quality review. Use detailed frontend or... |
| `cpp-coding-standards` | C++ coding standards based on the C++ Core Guidelines (isocpp.github.io). Use when writing, reviewing, or refactoring C++ code to... |
| `diagnosing-bugs` | Diagnosis loop for hard bugs and performance regressions. Use when the user says "diagnose"/"debug this", or reports something... |
| `error-handling` | Patterns for robust error handling across TypeScript, Python, and Go. Covers typed errors, error boundaries, retries, circuit... |
| `finishing-a-development-branch` | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides completion of... |
| `gateguard` | Fact-forcing gate that blocks Edit/Write/Bash (including MultiEdit) and demands concrete investigation (importers, data schemas,... |
| `git-workflow` | Git workflow patterns including branching strategies, commit conventions, merge vs rebase, conflict resolution, and collaborative... |
| `github-ops` | GitHub repository operations, automation, and management. Issue triage, PR management, CI/CD operations, release management, and... |
| `grill-me` | A relentless interview to sharpen a plan or design. |
| `grilling` | Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any... |
| `handoff` | Compact the current conversation into a handoff document for another agent to pick up. |
| `implement` | Implement a piece of work based on a spec or set of tickets. |
| `implement-spec` | Implement the result of /to-spec and /to-tickets in code. |
| `java-coding-standards` | Java coding standards for Spring Boot and Quarkus services: naming, immutability, Optional usage, streams, exceptions, generics,... |
| `pr` | Use when writing a PR body. |
| `prototype` | Build a throwaway prototype to answer a design question. Use when the user wants to sanity-check whether a state model or logic... |
| `repo-scan` | Cross-stack source code asset audit — classifies every file, detects embedded third-party libraries, and delivers actionable... |
| `retro` | Conduct a retrospective on a coding session. |
| `run-pre-commit-checks` | Run the mandatory pre-commit checks before committing code. Includes lint, type checking, and unit tests. MUST be run before every... |
| `search-first` | Research-before-coding workflow. Search for existing tools, libraries, and patterns before writing custom code. Systematizes the... |
| `systematic-debugging` | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes |
| `teach` | Teach the user a new skill or concept, within this workspace. |
| `to-questionnaire` | Turn a decision you can't fully answer into a questionnaire for someone else to fill in. |
| `using-git-worktrees` | Use when starting feature work that needs isolation from current workspace or before executing implementation plans - ensures an... |
| `wait-what` | Stop. That last message did not land: re-pitch it. |
| `wayfinder` | Plan a huge chunk of work (more than one agent session can hold) as a shared map of decision tickets on your issue tracker, and... |
| `wizard` | Generate an interactive bash wizard that walks a human through steps only they can perform. Use when provisioning infrastructure,... |

### 4.2 API & integration — 14 skills

| Skill | Use when |
|---|---|
| `api-connector-builder` | Build a new API connector or provider by matching the target repo's existing integration pattern exactly. Use when adding one more... |
| `api-design` | REST API design patterns including resource naming, status codes, pagination, filtering, error responses, versioning, and rate... |
| `build-zoom-phone-integration` | Use when building Phone. |
| `debug-zoom-integration` | Use when isolating failures. |
| `gnomad-graphql-skill` | Submit compact gnomAD GraphQL requests for frequency, gene constraint, and variant context queries. Use when a user wants concise... |
| `jira-integration` | Use this skill when retrieving Jira tickets, analyzing requirements, updating ticket status, adding comments, or transitioning... |
| `mcp-integration` | This skill should be used when the user asks to "add MCP server", "integrate MCP", "configure MCP in plugin", "use .mcp.json", "set... |
| `mcp-server-patterns` | Build MCP servers with Node/TypeScript SDK — tools, resources, prompts, Zod validation, stdio vs Streamable HTTP. Use Context7 or... |
| `plan-zoom-integration` | Use when planning Zoom integrations. |
| `run-integration-tests` | Run integration tests to verify that extension components work together correctly. Use this after modifying component interactions... |
| `setup-zoom-webhooks` | Use when building Zoom webhooks. |
| `shopify-storefront-graphql` | Use for custom storefronts requiring direct GraphQL queries/mutations for data fetching and cart operations. Choose this when you... |
| `twilio-messaging-webhooks` | Receive and respond to inbound messages and track outbound delivery status via Twilio webhooks — across SMS, MMS, WhatsApp, and... |
| `twilio-sendgrid-webhooks` | Track email delivery and engagement via SendGrid Event Webhooks. Covers all 11 event types (delivery + engagement), webhook handler... |

### 4.3 Testing & QA — 32 skills

| Skill | Use when |
|---|---|
| `agent-eval` | Head-to-head comparison of coding agents (Claude Code, Aider, Codex, etc.) on custom tasks with pass rate, cost, time, and... |
| `ai-regression-testing` | Regression testing strategies for AI-assisted development. Sandbox-mode API testing without database dependencies, automated... |
| `android-emulator-qa` | Use when validating Android feature flows in an emulator with adb-driven launch, input, UI-tree inspection, screenshots, and logcat... |
| `benchmark` | Use this skill to measure performance baselines, detect regressions before/after PRs, and compare stack alternatives. |
| `benchmark-methodology` | Use after competitive-platform-analysis has produced a tiered competitor set. Scores each competitor across nine weighted... |
| `benchmark-optimization-loop` | Use when the user asks to make something faster, try many variants, run recursive optimization, benchmark latency/throughput/cost,... |
| `browser-qa` | Use this skill to automate visual testing and UI interaction verification using browser automation after deploying features. |
| `bulk-qa-answers` | Bulk Q&A Answers skill for Datasite deal rooms. Use this skill whenever a sell-side deal team wants to answer multiple buyer... |
| `debug-failing-test` | Debug a failing test using an iterative logging approach, then clean up and document the learning. |
| `django-tdd` | Django testing strategies with pytest-django, TDD methodology, factory_boy, mocking, coverage, and testing Django REST Framework APIs. |
| `django-verification` | Verification loop for Django projects: migrations, linting, tests with coverage, security scans, and deployment readiness checks... |
| `e2e-testing` | Playwright E2E testing patterns, Page Object Model, configuration, CI/CD integration, artifact management, and flaky test strategies. |
| `eval-harness` | Formal evaluation framework for Claude Code sessions implementing eval-driven development (EDD) principles |
| `healthcare-eval-harness` | Patient safety evaluation harness for healthcare application deployments. Automated test suites for CDSS accuracy, PHI exposure,... |
| `laravel-tdd` | Laravel testing strategies with PHPUnit, Pest, model factories, HTTP tests, Sanctum authentication testing, mocking, and coverage. |
| `laravel-verification` | Verification loop for Laravel projects: env checks, linting, static analysis, tests with coverage, security scans, and deployment... |
| `plugin-eval` | Help engineers evaluate a local skill or plugin, explain why it scored that way, show what to fix first, measure real token usage,... |
| `quarkus-tdd` | Test-driven development for Quarkus 3.x LTS using JUnit 5, Mockito, REST Assured, Camel testing, and JaCoCo. Use when adding... |
| `quarkus-verification` | Verification loop for Quarkus projects: build, static analysis, tests with coverage, security scans, native compilation, and diff... |
| `replay-qa-api` | Use when calling Replay QA's REST API directly from Codex. Covers bearer-token setup, Replay recording prerequisites, project... |
| `run-e2e-tests` | Run E2E tests to verify complete user workflows like environment discovery, creation, and selection. Use this before releases or... |
| `springboot-tdd` | Test-driven development for Spring Boot using JUnit 5, Mockito, MockMvc, Testcontainers, and JaCoCo. Use when adding features,... |
| `springboot-verification` | Verification loop for Spring Boot projects: build, static analysis, tests with coverage, security scans, and diff review before... |
| `tdd` | Test-driven development. Use when the user wants to build features or fix bugs test-first, mentions "red-green-refactor", or wants... |
| `tdd-workflow` | Use this skill when writing new features, fixing bugs, or refactoring code. Enforces test-driven development with 80%+ coverage... |
| `test-driven-development` | Use when implementing any feature or bugfix, before writing implementation code |
| `test-triage` | Triage macOS tests across Xcode and SwiftPM. Use when narrowing failures, explaining assertions or crashes, or separating setup... |
| `twilio-identity-verification-advisor` | Planning skill for identity verification and fraud prevention. Qualifies the developer's needs across authentication method,... |
| `verification` | Full-story verification — infers what the user is building, then verifies the complete flow end-to-end: browser → API → data →... |
| `verification-before-completion` | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification... |
| `verification-loop` | A comprehensive verification system for Claude Code sessions. |
| `windows-desktop-e2e` | E2E testing for Windows native desktop apps (WPF, WinForms, Win32/MFC, Qt) using pywinauto and Windows UI Automation. |

### 4.4 Security — 29 skills

| Skill | Use when |
|---|---|
| `attack-path-analysis` | Use when Codex is already in the attack-path-analysis phase of a security scan or the user explicitly asks to trace a security... |
| `claude-security` | The Claude Security menu — pick a job: scan the codebase (the whole repository or a scoped part of it), scan changes (this branch's... |
| `customs-trade-compliance` | Codified expertise for customs documentation, tariff classification, duty optimization, restricted party screening, and regulatory... |
| `deep-security-scan` | Use when the user asks for a deep, exhaustive, multi-pass, or variance-reducing repository-wide or scoped-path Codex Security scan.... |
| `defi-amm-security` | Security checklist for Solidity AMM contracts, liquidity pools, and swap flows. Covers reentrancy, CEI ordering, donation or... |
| `django-security` | Django security best practices, authentication, authorization, CSRF protection, SQL injection prevention, XSS prevention, and... |
| `healthcare-phi-compliance` | Protected Health Information (PHI) and Personally Identifiable Information (PII) compliance patterns for healthcare applications.... |
| `hipaa-compliance` | HIPAA-specific entrypoint for healthcare privacy and security work. Use when a task is explicitly framed around HIPAA, PHI... |
| `laravel-security` | Laravel security best practices — authentication, authorization, Eloquent safety, CSRF, XSS prevention, API security, and secure... |
| `llm-trading-agent-security` | Security patterns for autonomous trading agents with wallet or transaction authority. Covers prompt injection, spend limits,... |
| `perl-security` | Comprehensive Perl security covering taint mode, input validation, safe process execution, DBI parameterized queries, web security... |
| `permissioned-github` | Guidelines for interacting with GitHub and request permissions from the user when commands fail due to restrictions in the agent... |
| `propose-security-hardening` | Develop evidence-backed structural and architectural security hardening proposals from vulnerability disclosures, supplied... |
| `quarkus-security` | Quarkus Security best practices for authentication, authorization, JWT/OIDC, RBAC, input validation, CSRF, secrets management, and... |
| `sandbox-sdk` | Build sandboxed applications for secure code execution. Load when building AI code execution, code interpreters, CI/CD systems,... |
| `security-bounty-hunter` | Hunt for exploitable, bounty-worthy security issues in repositories. Focuses on remotely reachable vulnerabilities that qualify for... |
| `security-diff-scan` | Use when the user asks for a security review of a pull request, commit, branch diff, working-tree patch, or other Git-backed change... |
| `security-review` | Use this skill when adding authentication, handling user input, working with secrets, creating API endpoints, or implementing... |
| `security-scan` | Scan your Claude Code configuration (.claude/ directory) for security vulnerabilities, misconfigurations, and injection risks using... |
| `springboot-security` | Spring Security best practices for authn/authz, validation, CSRF, secrets, headers, rate limiting, and dependency security in Java... |
| `supply-chain` | Interactive supply chain dashboard mapping suppliers, customers, and financial interdependencies |
| `threat-model` | Use when Codex is already in the threat-modeling phase of a security scan, the user explicitly invokes $threat-model, or the user... |
| `twilio-compliance-onboarding` | Registrations required BEFORE Twilio traffic works. Covers messaging programs (A2P 10DLC, toll-free verification, WhatsApp WABA,... |
| `twilio-compliance-traffic` | Rules you must follow for Twilio messaging and voice traffic. Covers TCPA (consent tiers, quiet hours, DNC), GDPR (EU consent,... |
| `twilio-regulatory-compliance-bundles` | Manage regulatory compliance for international phone numbers. Covers what bundles are, which countries require them, how to create... |
| `twilio-security-api-auth` | Choose the right Twilio authentication method and implement it correctly. Covers Auth Token (testing only), API Keys (production... |
| `twilio-security-compliance-hipaa` | Configure Twilio accounts for HIPAA compliance. Covers BAA requirements, HIPAA Project designation (self-service and support),... |
| `twilio-security-hardening` | Secure Twilio applications against common attacks. Covers credential management (API keys vs auth tokens), request validation... |
| `vercel-sandbox` | Vercel Sandbox guidance — ephemeral Firecracker microVMs for running untrusted code safely. Supports AI agents, code generation,... |

### 4.5 AI & LLM engineering — 69 skills

| Skill | Use when |
|---|---|
| `agent-architecture-audit` | Full-stack diagnostic for agent and LLM applications. Audits the 12-layer agent stack for wrapper regression, memory pollution,... |
| `agent-browser` | Browser automation CLI for AI agents. Use when the user needs to interact with websites, verify dev server output, test web apps,... |
| `agent-browser-verify` | Automated browser verification for dev servers. Triggers when a dev server starts to run a visual gut-check with agent-browser —... |
| `agent-development` | This skill should be used when the user asks to "create an agent", "add an agent", "write a subagent", "agent frontmatter", "when... |
| `agent-harness-construction` | Design and optimize AI agent action spaces, tool definitions, and observation formatting for higher completion rates. |
| `agent-introspection-debugging` | Structured self-debugging workflow for AI agent failures using capture, diagnosis, contained recovery, and introspection reports. |
| `agent-payment-x402` | Add x402 payment execution to AI agents with per-task budgets, spending controls, and non-custodial wallets. Supports Base through... |
| `agent-self-evaluation` | Use after completing any non-trivial task. The agent self-rates its output on 5 axes — accuracy, completeness, clarity,... |
| `agent-slide-decks` | Build slide decks programmatically — Marp, Slidev, reveal.js, python-pptx and HTML/CSS frameworks — with layouts, speaker notes,... |
| `agent-sort` | Build an evidence-backed ECC install plan for a specific repo by sorting skills, commands, rules, hooks, and extras into DAILY vs... |
| `ai-elements` | AI Elements component library guidance — pre-built React components for AI interfaces built on shadcn/ui. Use when building chat... |
| `ai-first-engineering` | Engineering operating model for teams where AI agents generate a large share of implementation output. |
| `ai-gateway` | Vercel AI Gateway expert guidance. Use when configuring model routing, provider failover, cost tracking, or managing multiple AI... |
| `ai-generation-persistence` | AI generation persistence patterns — unique IDs, addressable URLs, database storage, and cost tracking for every LLM generation |
| `ai-sdk` | Vercel AI SDK expert guidance. Use when building AI-powered features — chat interfaces, text generation, structured output, tool... |
| `aiq-deploy` | Use when asked to install, deploy, run, validate, troubleshoot, or stop NVIDIA AI-Q Blueprint infrastructure. |
| `aiq-research` | Use when asked to run deep research or AI-Q research through a reachable NVIDIA AI-Q Blueprint backend. |
| `autonomous-agent-harness` | Transform Claude Code into a fully autonomous agent system with persistent memory, scheduled operations, computer use, and task... |
| `build-mcp-app` | This skill should be used when the user wants to build an "MCP app", add "interactive UI" or "widgets" to an MCP server, "render... |
| `build-mcp-server` | This skill should be used when the user asks to "build an MCP server", "create an MCP", "make an MCP integration", "wrap an API for... |
| `build-model` | Build a multi-tab Excel financial model |
| `build-zoom-virtual-agent` | Use when using Virtual Agent. |
| `building-ai-agent-on-cloudflare` | Builds AI agents on Cloudflare using the Agents SDK with state management, real-time WebSockets, scheduled tasks, tool integration,... |
| `building-mcp-server-on-cloudflare` | Builds remote MCP (Model Context Protocol) servers on Cloudflare Workers with tools, OAuth authentication, and production... |
| `chat-sdk` | Vercel Chat SDK expert guidance. Use when building multi-platform chat bots — Slack, Telegram, Microsoft Teams, Discord, Google... |
| `claude-automation-recommender` | Analyze a codebase and recommend Claude Code automations (hooks, subagents, skills, plugins, MCP servers). Use when user asks for... |
| `claude-devfleet` | Orchestrate multi-agent coding tasks via Claude DevFleet — plan projects, dispatch parallel agents in isolated worktrees, monitor... |
| `claude-md-improver` | Audit and improve CLAUDE.md files in repositories. Use when user asks to check, audit, update, improve, or fix CLAUDE.md files.... |
| `context-budget` | Audits Claude Code context window consumption across agents, skills, MCP servers, and rules. Identifies bloat, redundant... |
| `continuous-agent-loop` | Patterns for continuous autonomous agent loops with quality gates, evals, and recovery controls. |
| `cost-aware-llm-pipeline` | Cost optimization patterns for LLM API usage — model routing by task complexity, budget tracking, retry logic, and prompt caching. |
| `data-scraper-agent` | Build a fully automated AI-powered data collection agent for any public source — job boards, prices, news, GitHub, sports,... |
| `enterprise-agent-ops` | Operate long-lived agent workloads with observability, security boundaries, and lifecycle management. |
| `everything-claude-code` | Development conventions and patterns for everything-claude-code. JavaScript project with conventional commits. |
| `everything-claude-code-conventions` | Development conventions and patterns for everything-claude-code. JavaScript project with conventional commits. |
| `fal-ai-media` | Unified media generation via fal.ai MCP — image, video, and audio. Covers text-to-image (Nano Banana), text/image-to-video... |
| `foundation-models-on-device` | Apple FoundationModels framework for on-device LLM — text generation, guided generation with @Generable, tool calling, and snapshot... |
| `huggingface-community-evals` | Run evaluations for Hugging Face Hub models using inspect-ai and lighteval on local hardware. Use for backend selection, local GPU... |
| `huggingface-datasets` | Use this skill for Hugging Face Dataset Viewer API workflows that fetch subset/split metadata, paginate rows, search text, apply... |
| `huggingface-gradio` | Build Gradio web UIs and demos in Python. Use when creating or editing Gradio apps, components, event listeners, layouts, or chatbots. |
| `huggingface-jobs` | This skill should be used when users want to run any workload on Hugging Face Jobs infrastructure. Covers UV scripts, Docker-based... |
| `huggingface-llm-trainer` | This skill should be used when users want to train or fine-tune language models using TRL (Transformer Reinforcement Learning) on... |
| `huggingface-paper-publisher` | Publish and manage research papers on Hugging Face Hub. Supports creating paper pages, linking papers to models/datasets, claiming... |
| `huggingface-papers` | Look up and read Hugging Face paper pages in markdown, and use the papers API for structured metadata such as authors, linked... |
| `huggingface-trackio` | Track and visualize ML training experiments with Trackio. Use when logging metrics during training (Python API), firing alerts for... |
| `huggingface-vision-trainer` | Trains and fine-tunes vision models for object detection (D-FINE, RT-DETR v2, DETR, YOLOS), image classification (timm models —... |
| `ios-debugger-agent` | Build, run, and debug iOS apps on Simulator with XcodeBuildMCP. Use when launching an app, inspecting simulator UI or logs, or... |
| `ito-data-atlas-agent` | Design background Data Atlas style agents for Itô basket research, market discovery, parameter drafting, and human-in-the-loop... |
| `moody-s-explore-mcp` | Discover and safely explore Moody's MCP tools. Use when the user wants to see what Moody's data is available, verify MCP... |
| `netlify-ai-gateway` | Guide for using Netlify AI Gateway to access AI models. Use when adding AI capabilities or selecting/changing AI models. Must be... |
| `openai-ads-conversions-setup` | Guide Codex through instrumenting or extending repositories with OpenAI Ads Measurement Pixel and optional Conversions API (CAPI).... |
| `openai-api-troubleshooting` | Use when an OpenAI API request fails and Codex needs to classify the likely cause, explain the next step, and route to the right... |
| `openai-docs` | Use for Codex models/pricing, scheduled tasks, skills, settings, setup, troubleshooting, customization, automations, and... |
| `openai-platform-api-key` | Use when Codex is asked to build, run, test, debug, or configure an OpenAI-backed or provider-unspecified AI app, UI, script, CLI,... |
| `physical-ai-infrastructure-setup-and-resilient-scaling` | Use when the user wants to set up, scale, validate, or harden NVIDIA physical AI infrastructure for synthetic data generation... |
| `physical-ai-neural-reconstruction` | Router for NVIDIA NuRec/NRE: USDZ rendering, NCore conversion, 3DGS, gRPC sensor sim, PhysicalAI HF datasets. Do NOT use for... |
| `prompt-optimizer` | Analyze raw prompts, identify intent and gaps, match ECC components (skills/commands/agents/hooks), and output a ready-to-paste... |
| `regex-vs-llm-structured-text` | Decision framework for choosing between regex and LLM when parsing structured text — start with regex, add LLM only for... |
| `render-mcp` | Connects and configures the Render MCP server for AI coding tools—setup per tool (Cursor, Claude Code, Codex), authentication,... |
| `review-agent` | Perform a read-only, defect-first review of a specified code change and return every actionable finding. Use when another agent... |
| `team-agent-orchestration` | Run team-based orchestration for agent squads using work items, ownership, agent Kanban, merge gates, and control pane handoffs. |
| `token-budget-advisor` | Offers the user an informed choice about how much response depth to consume before answering. Use this skill when the user... |
| `twilio-agent-augmentation-architect` | Planning skill for augmenting human agents with real-time AI intelligence. Qualifies the developer's use case across coaching,... |
| `twilio-agent-connect` | Use when building or integrating Twilio Agent Connect (TAC) to connect third-party LLM agent runtimes with Twilio Voice, Messaging,... |
| `twilio-ai-agent-architect` | Planning skill for AI-powered conversational agents. Qualifies the developer's use case across outcome sophistication, entry point,... |
| `vercel-agent` | Vercel Agent guidance — AI-powered code review, incident investigation, and SDK installation. Automates PR analysis and anomaly... |
| `zoom-virtual-agent-android` | Zoom Virtual Agent Android integration via WebView. Use for Java/Kotlin bridge callbacks, native URL handling, support_handoff... |
| `zoom-virtual-agent-ios` | Zoom Virtual Agent iOS integration via WKWebView. Use for Swift/Objective-C script injection, message handlers, support_handoff... |
| `zoom-virtual-agent-web` | Zoom Virtual Agent SDK for web embeds. Use for campaign or entry ID chat launch, event-driven controls, user context updates, and... |

### 4.6 Data, databases & pipelines — 51 skills

| Skill | Use when |
|---|---|
| `artifact-template-analytics-dashboard` | Create a spreadsheet using the Analytics Dashboard template and its retained reference file. Use when the user selects or names... |
| `artifact-template-sales-pipeline` | Create a spreadsheet using the Sales Pipeline template and its retained reference file. Use when the user selects or names Sales... |
| `canvas2d-data-visualization` | Render data visualizations with Canvas2D. Use when the visualization needs high mark counts, fast redraws, immediate-mode... |
| `chunk` | Use CircleCI Chunk for AI-assisted CI/CD work through either the Chunk web UI or the chunk-cli. Trigger this skill when users ask... |
| `clickhouse-io` | ClickHouse database patterns, query optimization, analytics, and data engineering best practices for high-performance analytical... |
| `d3-data-visualization` | Build custom data visualizations with D3. Use when the user needs SVG or DOM-based charts, rich annotation, domain-native... |
| `dashboard-builder` | Build monitoring dashboards that answer real operator questions for Grafana, SigNoz, and similar platforms. Use when turning... |
| `dashboard-expert` | Full CRUD and analysis for Mixpanel dashboards. Use when the user asks to build, create, analyze, read, understand, explain,... |
| `data-throughput-accelerator` | Use when large data ingestion, backfill, export, ETL, warehouse loading, manifest catch-up, or table synchronization needs to... |
| `data-visualization` | Route web data visualization work. Use when the user needs chart choice, visual critique, dashboards, maps or geospatial views,... |
| `database-migrations` | Database migration best practices for schema changes, data migrations, rollbacks, and zero-downtime deployments across PostgreSQL,... |
| `deepnote-data-execution` | Use when running Deepnote notebooks, inspecting notebook inputs, reviewing integration references and cached table structure,... |
| `hubspot-crm-data-hygiene` | Use when auditing HubSpot data quality for missing fields, stale records, duplicates, associations, owners, or cleanup tasks. |
| `hubspot-pipeline-health` | Use when reviewing HubSpot pipeline health, forecasts, stale deals, slipping close dates, or open deal risks. |
| `jpa-patterns` | JPA/Hibernate patterns for entity design, relationships, query optimization, transactions, auditing, indexing, pagination, and... |
| `kotlin-exposed-patterns` | JetBrains Exposed ORM patterns including DSL queries, DAO pattern, transactions, HikariCP connection pooling, Flyway migrations,... |
| `media-transcode-pipeline` | Transcode and package video, audio and images for every platform — H.264/H.265/AV1 and VP9 encodes, bitrate ladders, loudness... |
| `mysql-patterns` | MySQL and MariaDB schema, query, indexing, transaction, replication, and connection-pool patterns for production backends. |
| `native-data-fetching` | Use when implementing or debugging ANY network request, API call, or data fetching. Covers fetch API, React Query, SWR, error... |
| `neon-postgres` | Guides and best practices for working with Neon Serverless Postgres. Covers getting started, local development with Neon, choosing... |
| `neon-postgres-egress-optimizer` | Diagnose and fix excessive Postgres egress (network data transfer) in a codebase. Use when a user mentions high database bills,... |
| `opensource-pipeline` | Open-source pipeline: fork, sanitize, and package private projects for safe public release. Chains 3 agents (forker, sanitizer,... |
| `orch-pipeline` | Shared orchestration engine for the orch-* skill family. Defines the gated Research-Plan-TDD-Review-Commit pipeline, the size... |
| `postgres-patterns` | PostgreSQL database patterns for query optimization, schema design, indexing, and security. Quick reference for common patterns,... |
| `prisma-cli` | Prisma ORM CLI commands reference covering init, generate, migrate, db, dev, complete, studio, validate, format, debug, and mcp.... |
| `prisma-client-api` | Prisma Client API reference covering model queries, filters, operators, and client methods. Use when writing database queries,... |
| `prisma-compute` | Prisma Compute deployment and hosting guide. Use whenever the user mentions Prisma Compute, `prisma.compute.ts`,... |
| `prisma-database-setup` | Guides for configuring Prisma with different database providers (PostgreSQL, MySQL, SQLite, MongoDB, etc.). Use when setting up a... |
| `prisma-driver-adapter-implementation` | Required reference for Prisma ORM 7 SQL driver adapter work. Use when implementing or modifying adapters, adding database drivers,... |
| `prisma-mongodb-upgrade` | Decision and migration guide for Prisma ORM MongoDB projects on v6, which have no upgrade path to v7. Use when a MongoDB project... |
| `prisma-patterns` | Prisma ORM patterns for TypeScript backends — schema design, query optimization, transactions, pagination, and critical traps like... |
| `prisma-postgres` | Prisma Postgres setup and operations guidance across Console, create-db CLI, Management API, and Management API SDK. Use when... |
| `prisma-postgres-setup` | Set up a new Prisma Postgres database and connect it to a local project using the Management API. Use when asked to "set up a... |
| `prisma-upgrade-v7` | Complete migration guide from Prisma ORM v6 to v7 covering all breaking changes. Use when upgrading Prisma versions, encountering... |
| `pubmed-database` | Direct PubMed and NCBI E-utilities search workflows for biomedical literature, MeSH queries, PMID lookup, citation retrieval, and... |
| `ralphinho-rfc-pipeline` | RFC-driven multi-agent DAG execution pattern with quality gates, merge queues, and work unit orchestration. |
| `react-and-nextjs-data-visualization` | Integrate data visualizations into React and Next.js applications. Use when the user needs chart components, UML-like or... |
| `recsys-pipeline-architect` | Design composable recommendation, ranking, and feed pipelines using the six-stage Source→Hydrator→Filter→Scorer→Selector→SideEffect... |
| `redis-patterns` | Redis data structure patterns, caching strategies, distributed locks, rate limiting, pub/sub, and connection management for... |
| `render-postgres` | Sets up and optimizes Managed PostgreSQL on Render—connection strings (internal vs external), creation constraints, storage... |
| `scrollytelling-and-parallax-data-visualization` | Design and implement parallax scrolling and scrollytelling data visualizations. Use when the user asks for parallax scrolling,... |
| `shopify-custom-data` | MUST be used first when prompts mention Metafields or Metaobjects. Use Metafields and Metaobjects to model and store custom data... |
| `shorts-reels-pipeline` | End-to-end pipeline for producing short-form vertical video (YouTube Shorts, TikTok, Instagram Reels) locally and with AI. Covers... |
| `sprite-pipeline` | Generate and normalize 2D sprite animations. Use when the user asks for full-strip generation from approved source frames,... |
| `supabase` | Use when doing ANY task involving Supabase. Triggers: Supabase products (Database, Auth, Edge Functions, Realtime, Storage,... |
| `supabase-postgres-best-practices` | Postgres performance optimization and best practices from Supabase. Use this skill when writing, reviewing, or optimizing Postgres... |
| `testing-data-visualizations` | Test data visualizations and dashboards. Use when the user needs chart or diagram test strategy, screenshot or image diff testing,... |
| `threejs-data-visualization` | Render WebGL-accelerated data visualizations with Three.js, raw WebGL, deck.gl, luma.gl, PixiJS, Sigma.js, Plotly WebGL traces,... |
| `typescript-data-visualization-engineering` | Build typed data visualizations in TypeScript. Use when the user wants TypeScript visualization code, typed data models, browser... |
| `uspto-database` | USPTO patent and trademark data workflow for official record lookup, PatentSearch queries, TSDR checks, assignment data, and... |
| `web-3d-asset-pipeline` | Prepare and optimize browser-game 3D assets. Use when the user asks for GLB or glTF shipping work, including Blender cleanup and... |

### 4.7 DevOps & cloud — 52 skills

| Skill | Use when |
|---|---|
| `airtable-cli` | Lists bases, reads and writes records, manages tables and fields, filters and searches data in Airtable via the `airtable-mcp` CLI.... |
| `airtable-filters` | Use this skill when the user wants to find, filter, or narrow down Airtable records by field values, even when they don't... |
| `airtable-overview` | Explains what Airtable is and how data is structured — bases, tables, fields, records, views, automations, and interfaces. Use when... |
| `cloudflare` | Comprehensive Cloudflare platform skill covering Workers, Pages, storage (KV, D1, R2), AI (Workers AI, Vectorize, Agents SDK),... |
| `config-gc` | Garbage collection for your Claude Code configuration. Periodically scans ~/.claude (skills, memory, hooks, permissions, MCP... |
| `deployments-cicd` | Vercel deployment and CI/CD expert guidance. Use when deploying, promoting, rolling back, inspecting deployments, building with... |
| `docker-patterns` | Docker and Docker Compose patterns for local development, container security, networking, volume strategies, and multi-service... |
| `expo-cicd-workflows` | Helps understand and write EAS workflow YAML files for Expo projects. Use this skill when the user asks about CI/CD or workflows in... |
| `json-render` | AI chat response rendering guidance — handling UIMessage parts, tool call displays, streaming states, and structured data... |
| `kubernetes-patterns` | Kubernetes workload patterns, resource management, RBAC, probes, autoscaling, ConfigMap/Secret handling, and kubectl debugging for... |
| `netlify-blobs` | Guide for using Netlify Blobs object storage. Use when storing files, images, documents, or simple key-value data without a full... |
| `netlify-caching` | Guide for controlling caching on Netlify's CDN. Use when configuring cache headers, setting up stale-while-revalidate, implementing... |
| `netlify-cli-and-deploy` | Guide for using the Netlify CLI and deploying sites. Use when installing the CLI, linking sites, deploying (Git-based or manual),... |
| `netlify-config` | Reference for netlify.toml configuration. Use when configuring build settings, redirects, rewrites, headers, deploy contexts,... |
| `netlify-deploy` | Deploy projects to Netlify with the Netlify CLI. Use when the user wants to link a repo, validate deploy settings, run a deploy, or... |
| `netlify-edge-functions` | Guide for writing Netlify Edge Functions. Use when building middleware, geolocation-based logic, request/response manipulation,... |
| `netlify-forms` | Guide for using Netlify Forms for HTML form handling. Use when adding contact forms, feedback forms, file upload forms, or any form... |
| `netlify-frameworks` | Guide for deploying web frameworks on Netlify. Use when setting up a framework project (Vite/React, Astro, TanStack Start, Next.js,... |
| `netlify-functions` | Guide for writing Netlify serverless functions. Use when creating API endpoints, background processing, scheduled tasks, or any... |
| `netlify-identity` | Use when the task involves authentication, user signups, logins, password recovery, OAuth providers, role-based access control, or... |
| `netlify-image-cdn` | Guide for using Netlify Image CDN for image optimization and transformation. Use when serving optimized images, creating responsive... |
| `provision-droplet` | Use when the user wants to spin up / create / launch / provision a DigitalOcean droplet (or "a remote dev box on DO") and connect... |
| `render-background-workers` | Sets up and configures background workers on Render for queue-based job processing. Use when the user needs to process async jobs,... |
| `render-blueprints` | Authors and validates render.yaml Blueprints for Render infrastructure. Use when the user needs to write or edit a render.yaml,... |
| `render-cli` | Installs and uses the Render CLI for deploys, logs, SSH, psql, Blueprint validation, and automation. Use when the user needs to run... |
| `render-cron-jobs` | Configures and troubleshoots scheduled tasks on Render using cron job services. Use when the user needs to run something on a... |
| `render-debug` | Debug failed Render deployments by analyzing logs, metrics, and database state. Identifies errors (missing env vars, port binding,... |
| `render-deploy` | Deploy applications to Render by analyzing codebases, generating render.yaml Blueprints, and providing Dashboard deeplinks. Use... |
| `render-disks` | Attaches and manages persistent disks on Render services—mount paths, sizing, snapshots, file transfers, and single-instance... |
| `render-docker` | Builds and deploys Docker containers on Render—Dockerfiles, multi-stage builds, Blueprint Docker fields, private registries, layer... |
| `render-domains` | Configures custom domains and TLS certificates on Render—DNS setup, CNAME records, apex domains, wildcard domains, and certificate... |
| `render-env-vars` | Configures environment variables, secrets, and env groups on Render. Use when the user needs to set env vars, wire secrets between... |
| `render-keyvalue` | Provisions and configures Render Key Value (Redis-compatible Valkey 8) instances for caching, session storage, and job queues. Use... |
| `render-migrate-from-heroku` | Migrate from Heroku to Render by reading local project files and generating equivalent Render services. Triggers: any mention of... |
| `render-monitor` | Monitor Render services in real-time. Check health, performance metrics, logs, and resource usage. Use when users want to check... |
| `render-networking` | Connects Render services over the private network—internal DNS, service discovery, and cross-service communication. Use when the... |
| `render-private-services` | Configures Render private services—internal-only apps that accept traffic exclusively from other Render services over the private... |
| `render-scaling` | Scales Render services—configures autoscaling targets, chooses instance types, sets manual instance counts, and optimizes cost. Use... |
| `render-static-sites` | Deploys and configures static sites on Render's global CDN—build commands, publish paths, SPA routing, redirects, custom headers,... |
| `render-web-services` | Configures Render web services—port binding, TLS, health checks, custom domains, auto-deploy, PR previews, persistent disks, and... |
| `render-workflows` | Sets up, develops, tests, and deploys Render Workflows. Covers first-time scaffolding (via CLI or manual), SDK installation (Python... |
| `sign-in-with-vercel` | Sign in with Vercel guidance — OAuth 2.0/OIDC identity provider for user authentication via Vercel accounts. Use when implementing... |
| `swarm_monitor` | ONLY for the native-swarm worker whose brief says it is the monitor. On a timer, it checks whether the whole swarm has stalled and... |
| `vercel-api` | Vercel app and REST API expert guidance. Use when the agent needs live access to Vercel projects, deployments, environment... |
| `vercel-cli` | Vercel CLI expert guidance. Use when deploying, managing environment variables, linking projects, viewing logs, managing domains,... |
| `vercel-firewall` | Vercel Firewall and security expert guidance. Use when configuring DDoS protection, WAF rules, rate limiting, bot filtering, IP... |
| `vercel-flags` | Vercel Flags guidance — feature flags platform with unified dashboard, Flags Explorer, gradual rollouts, A/B testing, and provider... |
| `vercel-functions` | Vercel Functions expert guidance — Serverless Functions, Edge Functions, Fluid Compute, streaming, Cron Jobs, and runtime... |
| `vercel-queues` | Vercel Queues guidance (public beta) — durable event streaming with topics, consumer groups, retries, and delayed delivery.... |
| `vercel-services` | Vercel Services — deploy multiple services within a single Vercel project. Use for monorepo layouts or when combining a backend... |
| `vercel-storage` | Vercel storage expert guidance — Blob, Edge Config, and Marketplace storage (Neon Postgres, Upstash Redis). Use when choosing,... |
| `wrangler` | Cloudflare Workers CLI for deploying, developing, and managing Workers, KV, R2, D1, Vectorize, Hyperdrive, Workers AI, Containers,... |

### 4.8 Architecture & design — 13 skills

| Skill | Use when |
|---|---|
| `android-clean-architecture` | Clean Architecture patterns for Android and Kotlin Multiplatform projects — module structure, dependency rules, UseCases,... |
| `architecture-decision-records` | Capture architectural decisions made during Claude Code sessions as structured ADRs. Auto-detects decision moments, records... |
| `artifact-template-system-design` | Create a document using the System Design template and its retained reference file. Use when the user selects or names System... |
| `blueprint` | Turn a one-line objective into a step-by-step construction plan for multi-session, multi-agent engineering projects. Each step has... |
| `codebase-design` | Shared vocabulary for designing deep modules. Use when the user wants to design or improve a module's interface, find deepening... |
| `design-system` | Use this skill to generate or audit design systems, check visual consistency, and review PRs that touch styling. |
| `domain-modeling` | Build and sharpen a project's domain model. Use when discussing codebase terminology, writing or editing a GLOSSARY.md, or... |
| `hexagonal-architecture` | Design, implement, and refactor Ports & Adapters systems with clear domain boundaries, dependency inversion, and testable use-case... |
| `improve-codebase-architecture` | Scan a codebase for deepening opportunities, present them as a visual HTML report, then grill through whichever one you pick. |
| `twilio-customer-support-architect` | Planning skill for building customer service and support systems. Qualifies the developer's needs across the support ladder... |
| `twilio-webhook-architecture` | Design, secure, and operate Twilio webhook endpoints. Covers inbound event handling, status callbacks, signature validation,... |
| `uml-and-software-architecture-visualization` | Design, critique, read, write, render, and implement UML and UML-like software diagrams. Use when the user mentions UML, sequence... |
| `wix-design-system` | Wix Design System component reference. Use when building UI with @wix/design-system, choosing components, checking props and... |

### 4.9 Frontend, UI & accessibility — 44 skills

| Skill | Use when |
|---|---|
| `artifact-template-design-report` | Create a document using the Design Report template and its retained reference file. Use when the user selects or names Design... |
| `blender-3d-content` | Create 3D content in Blender headlessly — product renders, animations, scene composition, exports to glTF/FBX/USD, and rendering... |
| `blender-motion-state-inspection` | Use this skill when inspecting Blender characters, rigs, poses, animation retargeting, ground contact, facing direction, or... |
| `boltz-protein-design` | Design new protein binders with Boltz. Use when generating protein, peptide, antibody, nanobody, or custom binder candidates for a... |
| `boltz-small-molecule-design` | Design new small-molecule binders with Boltz. Use when generating novel ligands or hits for a target without a fixed compound... |
| `building-native-ui` | Complete guide for building beautiful apps with Expo Router. Covers fundamentals, styling, components, navigation, animations,... |
| `canva-translate-design` | Translate the text in a Canva design into another language while preserving the original layout as much as possible. Use when the... |
| `design-taste-frontend` | tasteskill v2, the anti-slop frontend skill. Art direction for websites, distilled from a study of 247 curated gallery sites (One... |
| `emil-design-eng` | This skill encodes Emil Kowalski's philosophy on UI polish, component design, animation decisions, and the invisible details that... |
| `expo-tailwind-setup` | Set up Tailwind CSS v4 in Expo with react-native-css and NativeWind v5 for universal styling |
| `expo-ui-jetpack-compose` | `@expo/ui/jetpack-compose` package lets you use Jetpack Compose Views and modifiers in your app. |
| `expo-ui-swift-ui` | `@expo/ui/swift-ui` package lets you use SwiftUI Views and modifiers in your app. |
| `figma-design-to-code` | Use this skill when implementing a Figma design as code (design → code) — the read-FROM-Figma direction. Triggers: 'implement this... |
| `figma-generate-design` | Use this skill alongside figma-use when the task involves translating an application page, view, or multi-section layout into... |
| `figma-implement-motion` | Translates Figma motion and animations into production-ready application code. Use when implementing animation/motion from a Figma... |
| `figma-use-motion` | Motion / animation context for the `use_figma` MCP tool — animating Figma nodes via manual keyframes, animation styles, easing, and... |
| `frontend-a11y` | Accessibility patterns for React and Next.js — semantic HTML, ARIA attributes, form labeling, keyboard navigation, focus... |
| `frontend-app-builder` | Use for new frontend applications, dashboards, games, creative websites, hero sections, and visually driven UI from scratch, or... |
| `frontend-design` | Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic... |
| `frontend-design-direction` | Set an ECC-specific frontend design direction for production UI work. Use when building or improving websites, dashboards,... |
| `frontend-patterns` | Frontend development patterns for React, Next.js, state management, performance optimization, and UI best practices. |
| `frontend-slides` | Create stunning, animation-rich HTML presentations from scratch or by converting PowerPoint files. Use when the user wants to build... |
| `frontend-testing-debugging` | Use when testing, debugging, or making targeted improvements to rendered frontend apps through the Build Web Apps or web dev... |
| `game-ui-frontend` | Design UI surfaces for browser games. Use when the user asks for HUDs, menus, overlays, responsive layouts, or visual direction... |
| `geist` | Expert guidance for Geist, Vercel's default typography system and font family for precise Next.js interfaces. Use when configuring... |
| `generative_ui` | How to render rich interactive HTML widgets inline in the chat or as standalone artifacts. Use this skill when you want to show the... |
| `liquid-glass` | Implement and review macOS SwiftUI Liquid Glass UI. Use when adopting system glass, removing conflicting custom chrome, or building... |
| `liquid-glass-design` | iOS 26 Liquid Glass design system — dynamic glass material with blur, reflection, and interactive morphing for SwiftUI, UIKit, and... |
| `motion-advanced` | Advanced motion patterns for React / Next.js — drag & drop, gestures, text animations, SVG path drawing, custom hooks, imperative... |
| `motion-foundations` | Motion tokens, spring presets, performance rules, device adaptation, accessibility enforcement, and SSR safety for React / Next.js... |
| `motion-patterns` | Production-ready animation patterns for React / Next.js — button, modal, toast, stagger, page transitions, exit animations, scroll,... |
| `motion-ui` | Production-ready UI motion system for React/Next.js. Use when implementing animations, transitions, or motion patterns. |
| `network-interface-health` | Diagnose interface errors, drops, CRCs, duplex mismatches, flapping, speed negotiation issues, and counter trends on routers,... |
| `remotion-best-practices` | Best practices for Remotion - Video creation in React |
| `remotion-video-creation` | Best practices for Remotion - Video creation in React. 29 domain-specific rules covering 3D, animations, audio, captions, charts,... |
| `shadcn` | Manages shadcn components and projects — adding, searching, fixing, debugging, styling, and composing UI. Provides project context,... |
| `shopify-pos-ui` | Build retail point-of-sale applications using Shopify's POS UI components. These components provide a consistent and familiar... |
| `swiftui-liquid-glass` | Implement and review iOS 26+ SwiftUI Liquid Glass UI. Use when adopting Liquid Glass or checking its correctness, performance, and... |
| `swiftui-ui-patterns` | Build and refactor SwiftUI UI with component patterns and examples. Use when shaping navigation, state, layouts, controls, or... |
| `taste` | A creative-direction (taste) layer for music videos and short-form edits in the angelcore / cloud-trance / hyperpop visual family.... |
| `ui-demo` | Record polished UI demo videos using Playwright. Use when the user asks to create a demo, walkthrough, screen recording, or... |
| `ui-plugin-navigation` | Discover UI plugin panels relevant to the current task and surface a one-click pill in chat to open (toggle) them in the side pane.... |
| `ui-to-vue` | Use when the user has UI screenshots or design exports that need batch conversion into Vue 3 components, especially with Vant,... |
| `ui-toolkit` | Use when using Zoom UI Toolkit. |

### 4.10 Data visualisation — 8 skills

| Skill | Use when |
|---|---|
| `accessibility-and-inclusive-visualization` | Make data visualizations accessible and inclusive. Use when the user needs chart or diagram accessibility guidance, text... |
| `dashboards-and-real-time-visualization` | Design dashboards and live visualization systems. Use when the user needs monitoring views, streaming charts, coordinated... |
| `gantt-chart-visualization` | Design, critique, route, and implement Gantt charts and schedule visualizations. Use when the user mentions Gantt charts, project... |
| `geospatial-and-cartographic-visualization` | Design geospatial and cartographic visualizations. Use when the user needs help deciding whether to use a map, choosing projections... |
| `grammar-of-graphics-and-declarative-visualization` | Build data visualizations with declarative grammars. Use when the user needs Vega-Lite, Vega, Observable Plot, or... |
| `node-link-and-diagram-layout` | Choose and apply automatic layout strategies for node-link diagrams and connected-node visuals. Use when the user asks how to... |
| `statistical-and-uncertainty-visualization` | Design statistically honest and uncertainty-aware visualizations. Use when the user needs help showing distributions, intervals,... |
| `visualization-strategy-and-critique` | Choose, lay out, critique, and explain data visualizations. Use when the user asks what visualization fits a dataset or goal, how a... |

### 4.11 Backend & API frameworks — 9 skills

| Skill | Use when |
|---|---|
| `django-celery` | Django + Celery async task patterns — configuration, task design, beat scheduling, retries, canvas workflows, monitoring, and... |
| `django-patterns` | Django architecture patterns, REST API design with DRF, ORM best practices, caching, signals, middleware, and production-grade... |
| `dotnet-patterns` | Idiomatic C# and .NET patterns, conventions, dependency injection, async/await, and best practices for building robust,... |
| `fastapi-patterns` | FastAPI patterns for async APIs, dependency injection, Pydantic request and response models, OpenAPI docs, tests, security, and... |
| `laravel-patterns` | Laravel architecture patterns, routing/controllers, Eloquent ORM, service layers, queues, events, caching, and API resources for... |
| `laravel-plugin-discovery` | Discover and evaluate Laravel packages via LaraPlugins.io MCP. Use when the user wants to find plugins, check package health, or... |
| `nestjs-patterns` | NestJS architecture patterns for modules, controllers, providers, DTO validation, guards, interceptors, config, and... |
| `quarkus-patterns` | Quarkus 3.x LTS architecture patterns with Camel for messaging, RESTful API design, CDI services, data access with Panache, and... |
| `springboot-patterns` | Spring Boot architecture patterns, REST API design, layered services, data access, caching, async processing, and logging. Use for... |

### 4.12 Languages & runtimes — 42 skills

| Skill | Use when |
|---|---|
| `angular-developer` | Generates Angular code and provides architectural guidance. Trigger when creating projects, components, or services, or for best... |
| `bun-runtime` | Bun as runtime, package manager, bundler, and test runner. When to choose Bun vs Node, migration notes, and Vercel support. |
| `click-path-audit` | Trace every user-facing button/touchpoint through its full state change sequence to find bugs where functions individually work but... |
| `codex-expo-run-actions` | Wire Expo projects into the Codex app with project-local run scripts and .codex/environments/environment.toml actions. Use when the... |
| `cpp-testing` | Use only when writing/updating/fixing C++ tests, configuring GoogleTest/CTest, diagnosing failing or flaky tests, or adding... |
| `csharp-testing` | C# and .NET testing patterns with xUnit, FluentAssertions, mocking, integration tests, and test organization best practices. |
| `dart-flutter-patterns` | Production-ready Dart and Flutter patterns covering null safety, immutable state, async composition, widget architecture, popular... |
| `expo-api-routes` | Guidelines for creating API routes in Expo Router with EAS Hosting |
| `expo-deployment` | Deploying Expo apps to iOS App Store, Android Play Store, web hosting, and API routes |
| `expo-dev-client` | Build and distribute Expo development clients locally or via TestFlight |
| `expo-module` | Guide for writing Expo native modules and views using the Expo Modules API (Swift, Kotlin, TypeScript). Covers module definition... |
| `flutter-dart-code-review` | Library-agnostic Flutter/Dart code review checklist covering widget best practices, state management patterns (BLoC, Riverpod,... |
| `fsharp-testing` | F# testing patterns with xUnit, FsUnit, Unquote, FsCheck property-based testing, integration tests, and test organization best... |
| `generating-python-installer` | Commercial-grade Python installer expert for Windows: Nuitka extreme compilation, dist slimming, DLL footprint analysis, and Inno... |
| `golang-patterns` | Go-specific design patterns and best practices including functional options, small interfaces, dependency injection, concurrency... |
| `golang-testing` | Go testing best practices including table-driven tests, test helpers, benchmarking, race detection, coverage analysis, and... |
| `kotlin-coroutines-flows` | Kotlin Coroutines and Flow patterns for Android and KMP — structured concurrency, Flow operators, StateFlow, error handling, and... |
| `kotlin-ktor-patterns` | Ktor server patterns including routing DSL, plugins, authentication, Koin DI, kotlinx.serialization, WebSockets, and... |
| `kotlin-patterns` | Idiomatic Kotlin patterns, best practices, and conventions for building robust, efficient, and maintainable Kotlin applications... |
| `kotlin-testing` | Kotlin testing patterns with Kotest, MockK, coroutine testing, property-based testing, and Kover coverage. Follows TDD methodology... |
| `perl-patterns` | Modern Perl 5.36+ idioms, best practices, and conventions for building robust, maintainable Perl applications. |
| `perl-testing` | Perl testing patterns using Test2::V0, Test::More, prove runner, mocking, coverage with Devel::Cover, and TDD methodology. |
| `pylance-python-profiling` | Use when the user wants to profile Python code with Pylance: capture CPU time (Tachyon), trace calls (sys.monitoring), or memory... |
| `python-fact-grounded-coding` | Use when the user explicitly asks for the Python fact-grounded coding skill, or when a Python coding, debugging, explanation, or... |
| `python-manager-discovery` | Environment manager-specific discovery patterns and known issues. Use when working on or reviewing environment discovery code for... |
| `python-patterns` | Python-specific design patterns and best practices including protocols, dataclasses, context managers, decorators, async/await,... |
| `python-testing` | Python testing best practices using pytest including fixtures, parametrization, mocking, coverage analysis, async testing, and test... |
| `react-best-practices` | React and Next.js performance optimization guidelines from Vercel Engineering. This skill should be used when writing, reviewing,... |
| `react-patterns` | React 18/19 patterns including hooks discipline, server/client component boundaries, Suspense + error boundaries, form actions,... |
| `react-performance` | React and Next.js performance optimization patterns adapted from Vercel Engineering's React Best Practices... |
| `react-testing` | React component testing with React Testing Library, Vitest/Jest, MSW for network mocking, accessibility assertions with axe, and... |
| `react-three-fiber-game` | Build React-hosted 3D browser games with React Three Fiber. Use when the user wants pmndrs-based scene composition, shared React... |
| `rust-patterns` | Idiomatic Rust patterns, ownership, error handling, traits, concurrency, and best practices for building safe, performant applications. |
| `rust-testing` | Rust testing patterns including unit tests, integration tests, async testing, property-based testing, mocking, and coverage.... |
| `swift-actor-persistence` | Thread-safe data persistence in Swift using actors — in-memory cache with file-backed storage, eliminating data races by design. |
| `swift-concurrency-6-2` | Swift 6.2 Approachable Concurrency — single-threaded by default, @concurrent for explicit background offloading, isolated... |
| `swift-protocol-di-testing` | Protocol-based dependency injection for testable Swift code — mock file system, network, and external APIs using focused protocols... |
| `typer` | Typer best practices and conventions. Use when working with Typer CLIs. Keeps Typer code clean and up to date with the latest... |
| `upgrading-expo` | Guidelines for upgrading Expo SDK versions and fixing dependency issues |
| `vue-patterns` | Vue.js 3 Composition API patterns, component architecture, reactivity best practices, Pinia state management, Vue Router... |
| `zoom-meeting-sdk-react-native` | Zoom Meeting SDK for React Native. Use when embedding Zoom meetings in React Native iOS/Android apps with... |
| `zoom-video-sdk-react-native` | Zoom Video SDK for React Native. Use when building custom mobile video session experiences with @zoom/react-native-videosdk, event... |

### 4.13 Mobile & desktop — 19 skills

| Skill | Use when |
|---|---|
| `android-performance` | Gather and interpret Android performance evidence on an adb target using Simpleperf CPU profiles, Perfetto or Compose traces,... |
| `cisco-ios-patterns` | Cisco IOS and IOS-XE review patterns for show commands, config hierarchy, wildcard masks, ACL placement, interface hygiene, and... |
| `compose-multiplatform-patterns` | Compose Multiplatform and Jetpack Compose patterns for KMP projects — state management, navigation, theming, performance, and... |
| `figma-swiftui` | SwiftUI ↔ Figma translation. Use whenever the user mentions Swift, SwiftUI, iOS, iPhone, or iPad — in EITHER direction —... |
| `ios-app-intents` | Design App Intents, app entities, and App Shortcuts for iOS system surfaces. Use when exposing app actions or content to Shortcuts,... |
| `ios-ettrace-performance` | Capture and interpret iOS Simulator ETTrace profiles. Use when profiling launch or runtime latency, comparing traces, or finding... |
| `ios-icon-gen` | Generate iOS app icons as PNG imagesets for Xcode asset catalogs from SF Symbols (5000+ Apple-native) or Iconify API (275k+ open... |
| `ios-memgraph-leaks` | Capture and inspect iOS leaks and memgraphs. Use when debugging leaked objects, retain cycles, memory growth, or before/after leak... |
| `ios-simulator-browser` | Mirror an iOS Simulator into the Codex in-app browser and render SwiftUI previews from importable Swift packages in that simulator... |
| `swiftui-patterns` | SwiftUI architecture patterns, state management with @Observable, view composition, navigation, performance optimization, and... |
| `swiftui-performance-audit` | Audit SwiftUI runtime performance from code first. Use when diagnosing slow rendering, janky scrolling, expensive updates, or... |
| `swiftui-view-refactor` | Refactor SwiftUI view files into stable, testable structure. Use when splitting large views, tightening data flow, or cleaning... |
| `zoom-contact-center-android` | Zoom Contact Center SDK for Android. Use for native Android chat/video/ZVA/scheduled callback integrations, campaign mode, service... |
| `zoom-contact-center-ios` | Zoom Contact Center SDK for iOS. Use for native iOS chat/video/ZVA/scheduled callback integrations, app lifecycle bridging, rejoin... |
| `zoom-meeting-sdk-android` | Zoom Meeting SDK for Android native apps. Use when embedding Zoom meetings in Android with default/custom UI, PKCE + SDK auth,... |
| `zoom-meeting-sdk-ios` | Zoom Meeting SDK for iOS native apps. Use when embedding Zoom meetings in iOS with default/custom UI, PKCE + SDK auth, host start... |
| `zoom-video-sdk-android` | Zoom Video SDK for Android native apps. Use when building custom Android video experiences with full UI control, session tokens,... |
| `zoom-video-sdk-flutter` | Zoom Video SDK for Flutter. Use when building custom video session apps in Flutter with flutter_zoom_videosdk, event-driven... |
| `zoom-video-sdk-ios` | Zoom Video SDK for iOS native apps. Use when building custom iOS video sessions with full UI control, token-based session auth, and... |

### 4.14 Documents, writing & content — 38 skills

| Skill | Use when |
|---|---|
| `article-writing` | Write articles, guides, blog posts, tutorials, newsletter issues, and other long-form content in a distinctive voice derived from... |
| `artifact-template-business-review` | Create a presentation using the Business Review template and its retained reference file. Use when the user selects or names... |
| `artifact-template-experiment-analysis` | Create a document using the Experiment Analysis template and its retained reference file. Use when the user selects or names... |
| `artifact-template-financial-budget` | Create a spreadsheet using the Financial Budget template and its retained reference file. Use when the user selects or names... |
| `artifact-template-investment-committee-memo` | Create a document using the Investment Committee Memo template and its retained reference file. Use when the user selects or names... |
| `artifact-template-legal-memorandum` | Create a document using the Legal Memorandum template and its retained reference file. Use when the user selects or names Legal... |
| `artifact-template-market-trends-report` | Create a presentation using the Market Trends Report template and its retained reference file. Use when the user selects or names... |
| `artifact-template-minimal-letterhead` | Create a document using the Minimal Letterhead template and its retained reference file. Use when the user selects or names Minimal... |
| `artifact-template-operating-calendar` | Create a spreadsheet using the Operating Calendar template and its retained reference file. Use when the user selects or names... |
| `artifact-template-operating-review` | Create a presentation using the Operating Review template and its retained reference file. Use when the user selects or names... |
| `artifact-template-project-kickoff` | Create a presentation using the Project Kickoff template and its retained reference file. Use when the user selects or names... |
| `artifact-template-project-tracker` | Create a spreadsheet using the Project Tracker template and its retained reference file. Use when the user selects or names Project... |
| `artifact-template-simple-dark-mode` | Create a presentation using the Simple Dark Mode template and its retained reference file. Use when the user selects or names... |
| `artifact-template-simple-light-mode` | Create a presentation using the Simple Light Mode template and its retained reference file. Use when the user selects or names... |
| `artifact-template-strategy-memorandum` | Create a document using the Strategy Memorandum template and its retained reference file. Use when the user selects or names... |
| `artifact-template-team-alignment` | Create a presentation using the Team Alignment template and its retained reference file. Use when the user selects or names Team... |
| `artifact-template-three-statement-forecast` | Create a spreadsheet using the Three-Statement Forecast template and its retained reference file. Use when the user selects or... |
| `batch-draft-writer` | Drafts multiple email replies or follow-ups in batch using the Superhuman Mail MCP server — processing your inbox in bulk rather... |
| `cite-check` | Cite-checks a brief, motion, or memo (PDF/Word): verifies each cited case is real, supports the proposition, is good law, and... |
| `competitive-report-structure` | Use after benchmark-methodology has produced scored competitor profile cards. Assembles findings into a decision-grade report:... |
| `content-engine` | Create platform-native content systems for X, LinkedIn, TikTok, YouTube, newsletters, and repurposed multi-platform campaigns. Use... |
| `draft-brief` | Drafts court filings — motions, memoranda of law, appellate briefs — as court-ready .docx, with Midpage research behind every... |
| `draft-long-form-memo` | Writes a formal objective legal research memo (Questions Presented, Brief Answers, Facts, IRAC Discussion, Conclusion) as a .docx.... |
| `generate-status-report` | Generate project status reports from Jira issues and publish to Confluence. When an agent needs to: (1) Create a status report for... |
| `google-calendar-daily-brief` | Build polished one-day Google Calendar briefs. Use when the user asks for today, tomorrow, or a specific date summary with an... |
| `humanizer` | Rewrites text to sound like a real person wrote it — not an AI. Use this skill any time the user asks to humanize, de-AI, rewrite,... |
| `knowledge-ops` | Knowledge base management, ingestion, sync, and retrieval across multiple storage layers (local files, MCP memory, vector stores,... |
| `latex-doctor` | Diagnose, fix, and write LaTeX for any IDE — Overleaf, TeXstudio, VS Code + LaTeX Workshop, Vim/Emacs, command-line... |
| `moody-s-earnings-brief` | Produce an Earnings Call Summary HTML report for 2–5 companies using Moody's GenAI MCP tools. Use this skill whenever the user asks... |
| `moody-s-issuer-brief` | Produce a comprehensive Issuer Brief HTML report for a company using Moody's GenAI MCP tools. Use this skill whenever the user asks... |
| `moody-s-sector-brief` | Produce a Sector Brief HTML report for any industry sector using Moody's GenAI MCP tools and web research. Use this skill whenever... |
| `outlook-calendar-daily-brief` | Build polished one-day Outlook Calendar briefs. Use when the user asks for today, tomorrow, or a specific date summary with an... |
| `session-report` | Generate an explorable HTML report of Claude Code session usage (tokens, cache, subagents, skills, expensive prompts) from... |
| `sharepoint-shared-doc-maintenance` | Maintain shared SharePoint strategy, roadmap, planning, or status documents from changing source documents. Use when the user wants... |
| `spec-to-backlog` | Automatically convert Confluence specification documents into structured Jira backlogs with Epics and implementation tickets. When... |
| `video-translation-dubbing` | Translate and dub video — transcribe, translate subtitles and dialogue, synthesize localized speech, align it to the original lip... |
| `visa-doc-translate` | Translate visa application documents (images) to English and create a bilingual PDF with original and translation |
| `writing-for-agents` | Writing documents for agents. Use when creating or editing skills, or modifying AGENTS.md or CLAUDE.md. |

### 4.15 Research & analysis — 12 skills

| Skill | Use when |
|---|---|
| `deep-research` | Multi-source deep research using firecrawl and exa MCPs. Searches the web, synthesizes findings, and delivers cited reports with... |
| `literature-review` | Systematic literature-review workflow for academic, biomedical, technical, and scientific topics, including search planning, source... |
| `market-research` | Conduct market research, competitive analysis, investor due diligence, and industry intelligence with source attribution and... |
| `notion-research-documentation` | Research across Notion and synthesize into structured documentation; use when gathering info from multiple Notion sources to... |
| `prediction-market-oracle-research` | Research prediction markets as data sources or oracle signals for products, agents, dashboards, and corporate decision... |
| `research` | Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the repo. Use when the... |
| `research-note` | Generate a professional Word document research note |
| `research-ops` | Evidence-first current-state research workflow for ECC. Use when the user wants fresh facts, comparisons, enrichment, or a... |
| `research-partner` | Rigorous research support - structured literature reviews, taxonomy construction, constructive critique of papers, multi-stance... |
| `research-router-skill` | Route broad or ambiguous life-sciences research requests to the right skills, normalize core entities, optionally parallelize... |
| `scholar-evaluation` | Structured scholarly-work evaluation for papers, proposals, literature reviews, methods sections, evidence quality, citation... |
| `track-findings` | Track validated Codex Security findings in Linear, Jira, GitHub issues, or draft GitHub security advisories. Use it for one finding... |

### 4.16 Bioinformatics & life sciences — 71 skills

| Skill | Use when |
|---|---|
| `alphafold-skill` | Submit compact AlphaFold Protein Structure Database API requests for prediction, UniProt summary, sequence summary, and annotation... |
| `bgee-skill` | Submit compact Bgee SPARQL requests for healthy wild-type expression metadata and ontology-aware lookup patterns. Use when a user... |
| `bindingdb-skill` | Submit compact BindingDB REST API requests for ligand-target binding lookups by PDB, UniProt, or similarity search. Use when a user... |
| `biorxiv-skill` | Submit compact bioRxiv and medRxiv API requests for details, publication-linkage, and DOI lookups. Use when a user wants concise... |
| `biostudies-arrayexpress-skill` | Submit compact BioStudies and ArrayExpress API requests for free-text search and accession-based study retrieval. Use when a user... |
| `boltz-check-status` | Boltz job status and result recovery. Use when listing jobs, checking progress, resuming downloads, recovering results, or... |
| `boltz-cli-setup` | Boltz CLI setup and auth. Use when installing, updating, verifying, or authenticating `boltz-api`, or fixing missing CLI, PATH,... |
| `boltz-protein-screen` | Screen existing protein binders with Boltz. Use when ranking a supplied protein, peptide, antibody, nanobody, or binder library... |
| `boltz-small-molecule-adme` | Predict Tier-1 ADME/ADMET for small molecules with Boltz from bare SMILES — no target, no docking. Use when the user wants... |
| `boltz-small-molecule-screen` | Screen existing small-molecule libraries with Boltz. Use when docking, scoring, or ranking a supplied SMILES or compound library... |
| `boltz-structure-and-binding` | Predict structures and binding for one defined complex with Boltz. Use when folding a protein, RNA, DNA, or ligand complex, docking... |
| `bull-bear` | Bull/bear/base case scenario framework for a given company |
| `cbioportal-skill` | Submit compact cBioPortal API requests for studies, molecular profiles, mutations, clinical data, and samples. Use when a user... |
| `cellxgene-skill` | Submit compact CELLxGENE Discover API requests for public collection and dataset metadata. Use when a user wants concise... |
| `chebi-skill` | Submit compact ChEBI 2.0 API requests for chemical search, compound lookup, ontology traversal, and structure metadata. Use when a... |
| `chembl-skill` | Submit compact ChEMBL API requests for activity, molecule, target, mechanism, and text-search endpoints. Use when a user wants... |
| `civic-skill` | Submit compact CIViC GraphQL requests for cancer variant interpretation schema inspection and targeted evidence retrieval. Use when... |
| `clinvar-variation-skill` | Submit compact ClinVar Clinical Tables and NCBI Variation requests for search, VCV, RCV, SCV, and RefSNP lookups. Use when a user... |
| `dcf` | Discounted cash flow valuation with sensitivity analysis |
| `efo-ontology-skill` | Submit compact EFO OLS4 requests for search, term lookup, children, and descendants. Use when a user wants concise EFO resolution... |
| `encode-skill` | Submit compact ENCODE REST API requests for object lookups, portal-style search, and metadata retrieval. Use when a user wants... |
| `ensembl-skill` | Submit compact Ensembl REST API requests for lookup, overlap, cross-reference, and variation endpoints. Use when a user wants... |
| `eva-skill` | Submit compact EVA REST requests for species metadata and archived variant lookups. Use when a user wants concise European... |
| `finngen-phewas-skill` | Fetch compact FinnGen PheWAS summaries for single variants by accepting rsID, GRCh37, or GRCh38 input and resolving to the required... |
| `fund-comparison` | Use when comparing 2 to 4 funds or ETFs with Morningstar ratings, returns, risk, and holdings data. |
| `fund-screener` | Use when screening funds or ETFs by Morningstar category, ratings, fees, assets, returns, or risk. |
| `fund-summarizer` | Use when summarizing a fund or ETF with Morningstar ratings, returns, risk, holdings, fees, and caveats. |
| `genebass-gene-burden-skill` | Submit compact Genebass gene burden requests for one Ensembl gene ID and one burden set. Use when a user wants concise Genebass... |
| `gget` | gget CLI and Python workflow for quick genomic database queries, sequence lookup, BLAST-style searches, enrichment checks, and... |
| `gtex-eqtl-skill` | Fetch GTEx single-tissue eQTL associations from one variant input by accepting rsID, GRCh37, or GRCh38 input and resolving to the... |
| `gwas-catalog-skill` | Submit compact GWAS Catalog REST API v2 requests for studies, associations, SNPs, EFO traits, genes, publications, loci, and... |
| `hmdb-skill` | Submit compact HMDB search requests for metabolites, proteins, diseases, and pathways. Use when a user wants concise HMDB summaries |
| `human-protein-atlas-skill` | Submit compact Human Protein Atlas requests for gene JSON, search downloads, and page-level tissue or cell-line lookups. Use when a... |
| `ipd-skill` | Submit compact IPD REST requests for HLA allele and cell-level metadata using the public IPD query API. Use when a user wants... |
| `locus-to-gene-mapper-skill` | Map GWAS loci to ranked candidate genes using a deterministic multi-skill chain (EFO -> GWAS -> coordinates -> Open Targets... |
| `metabolights-skill` | Submit compact MetaboLights requests for study discovery and study-level metabolomics metadata. Use when a user wants concise... |
| `mgnify-skill` | Submit compact MGnify API requests for microbiome studies, samples, and biome metadata. Use when a user wants concise MGnify summaries |
| `ncbi-blast-skill` | Submit, poll, and summarize NCBI BLAST Common URL API jobs (Blast.cgi) for nucleotide or protein sequences. Use when a user wants... |
| `ncbi-clinicaltables-skill` | Submit compact Clinical Tables NCBI Gene requests for human gene lookup, pagination, and field selection. Use when a user wants... |
| `ncbi-datasets-skill` | Submit compact NCBI Datasets v2 requests for assembly, genome, taxonomy, and related metadata endpoints. Use when a user wants... |
| `ncbi-entrez-skill` | Submit compact NCBI Entrez E-Utilities requests for PubMed, Gene, Protein, Nucleotide, PMC metadata, and GEO metadata workflows.... |
| `ncbi-pmc-skill` | Submit compact NCBI PMC Open Access requests for article/file availability metadata. Use when a user wants concise PMC Open Access... |
| `ngs-amplicon-microbiome` | Kick off public 16S, 18S, ITS, COI, or other marker-gene amplicon microbiome workflows using nf-core/ampliseq, QIIME2, DADA2, and... |
| `ngs-analysis-router` | Route BCL, FASTQ, BAM/CRAM, count-matrix, or VCF sequencing requests to the right public NGS analysis skill and ask only the... |
| `ngs-atacseq-peaks-qc` | Run or plan ATAC-seq QC, alignment, TSS enrichment, fragment-size, blacklist, peak-calling, consensus peak, and differential... |
| `ngs-bcl-to-fastq` | Validate Illumina BCL run folders and sample sheets, plan demultiplexing, review index/UMI/lane choices, run BCL-to-FASTQ... |
| `ngs-bulk-rnaseq` | Dispatch bulk RNA-seq requests to FASTQ-to-count QC or count-matrix differential-expression skills using nf-core/rnaseq, STAR,... |
| `ngs-bulk-rnaseq-counts-qc` | Run or plan bulk RNA-seq FASTQ-to-count processing with sample-sheet, strandedness, genome annotation, alignment or... |
| `ngs-bulk-rnaseq-differential-expression` | Run or plan bulk RNA-seq differential-expression analysis from count matrices with replicate, design formula, contrast, batch,... |
| `ngs-chip-cutrun-peaks-qc` | Run or plan ChIP-seq, CUT&RUN, or CUT&Tag QC, control handling, spike-in, peak calling, broad-vs-narrow target selection,... |
| `ngs-dna-germline-variants` | Run or plan deep germline WGS, WES, targeted-panel, cohort, or trio variant-calling workflows with reference-build, known-sites,... |
| `ngs-dna-somatic-variants` | Run or plan tumor-normal, tumor-only, WGS, WES, or cancer-panel somatic variant workflows with pairing, contamination,... |
| `ngs-dna-umi-panel-variants` | Run or plan targeted DNA panel variant workflows that use UMIs, duplex consensus reads, molecular barcodes, low-frequency calling,... |
| `ngs-dna-variant-calling` | Dispatch WGS, WES, or targeted DNA variant requests to germline, somatic, or UMI-panel skills, then plan public nf-core/sarek,... |
| `ngs-epigenomics-peaks` | Dispatch ATAC-seq, ChIP-seq, CUT&RUN, or CUT&Tag requests to assay-specific QC, alignment, signal-track, peak-calling, consensus,... |
| `ngs-fastq-qc` | Validate FASTQ inputs, run local FastQC/MultiQC QC, interpret QC signals, and optionally execute fastp or Cutadapt trimming... |
| `ngs-runtime-env` | Check whether public NGS tools and packages already exist before downloading, installing, or running a sequencing pipeline. |
| `ngs-scrna-seq` | Route single-cell or single-nucleus RNA-seq FASTQs to public count-generation workflows and defer post-count matrix QC, annotation,... |
| `ngs-shotgun-metagenomics` | Kick off public shotgun metagenomics QC, host-depletion, taxonomic profiling, and functional profiling workflows using... |
| `opentargets-skill` | Submit compact Open Targets Platform GraphQL requests for target, disease, drug, variant, study, and search data, including... |
| `pride-skill` | Submit compact PRIDE Archive API requests for proteomics project discovery and project-level metadata. Use when a user wants... |
| `pubchem-pug-skill` | Submit compact PubChem PUG REST requests for compound properties, descriptions, assay summaries, and substance metadata. Use when a... |
| `quickgo-skill` | Submit compact QuickGO requests for GO terms, annotations, and ontology traversal. Use when a user wants concise QuickGO summaries |
| `rcsb-pdb-skill` | Submit compact RCSB PDB requests for core metadata, Search API queries, and FASTA downloads. Use when a user wants concise RCSB... |
| `reactome-skill` | Submit compact Reactome ContentService requests for pathway, event, participant, search, and diagram-related data. Use when a user... |
| `rhea-skill` | Submit compact Rhea reaction search requests for biochemical reactions and reaction IDs. Use when a user wants concise Rhea summaries |
| `scrna-seq-qc` | Process, quality-control, annotate, and visualize single-cell or single-nucleus RNA-seq datasets across tissues and species. Use... |
| `tpmi-phewas-skill` | Fetch compact TPMI PheWAS summaries for single variants by accepting rsID, GRCh37, or GRCh38 input and resolving to the required... |
| `ukb-topmed-phewas-skill` | Fetch compact UKB-TOPMed PheWAS summaries for single variants by accepting rsID, GRCh37, or GRCh38 input and resolving to the... |
| `uniprot-skill` | Submit compact UniProt REST API requests for UniProtKB, UniRef, UniParc, and FASTA stream endpoints. Use when a user wants concise... |
| `unit-economics` | Bottoms-up unit economics decomposition for any public company |

### 4.17 Business, finance & product — 24 skills

| Skill | Use when |
|---|---|
| `capital-allocation` | Deep dive into capital deployment, buybacks, dividends, and shareholder yield |
| `chronograph-cashflow-forecast` | Forecast private capital cashflows for existing portfolios using Chronograph MCP data and a Takahashi-Alexander style model. Use... |
| `chronograph-gp-meeting-prep` | Prepare an LP to meet with their fund manager (GP): review the fund's latest reporting, surface what changed since last period, and... |
| `chronograph-portfolio-company-one-pager` | GP platform one-pager and investor report generator for private equity portfolio companies. Use this skill whenever a user asks to... |
| `competitive-platform-analysis` | Use when scoping a competitive landscape — identifying, categorising, and score-filtering a competitor set before any benchmarking... |
| `customer-billing-ops` | Operate customer billing workflows such as subscriptions, refunds, churn triage, billing-portal recovery, and plan analysis using... |
| `deal-tracker` | Builds a relationship or deal summary using the Superhuman Mail MCP server — pulling together all email history, read receipts, and... |
| `finance-billing-ops` | Evidence-first revenue, pricing, refunds, team-billing, and billing-model truth workflow for ECC. Use when the user wants a sales... |
| `hubspot` | Use when working with HubSpot CRM records to search, summarize, create, update, associate, or analyze objects and properties. |
| `hubspot-customer-prep` | Use when preparing HubSpot customer briefs for meetings, renewals, QBRs, sales calls, escalations, handoffs, or follow-ups. |
| `inventory-demand-planning` | Codified expertise for demand forecasting, safety stock optimization, replenishment planning, and promotional lift estimation at... |
| `investor-materials` | Create and update pitch decks, one-pagers, investor memos, accelerator applications, financial models, and fundraising materials.... |
| `investor-outreach` | Draft cold emails, warm intro blurbs, follow-ups, update emails, and investor communications for fundraising. Use when the user... |
| `ito-market-intelligence` | Research prediction-market events, venues, underliers, liquidity, and news context for Itô basket workflows. Use for read-only... |
| `lead-intelligence` | AI-native lead intelligence and outreach pipeline. Replaces Apollo, Clay, and ZoomInfo with agent-powered signal scoring, mutual... |
| `logistics-exception-management` | Codified expertise for handling freight exceptions, shipment delays, damages, losses, and carrier disputes. Informed by logistics... |
| `moody-s-company-analysis` | Use when the user asks for Moody's company profiles, ownership, ratings, credit opinions, financial statements, filings, peers,... |
| `moody-s-peer-analysis` | Produce a Peer Analysis HTML report for a target company and its credit peers using Moody's GenAI MCP tools. Use this skill... |
| `moody-s-rating-analysis` | Produce a Rating Pitch Report for a company using Moody's GenAI MCP tools, delivered as a self-contained HTML file saved to disk.... |
| `prediction-market-risk-review` | Review prediction-market, basket, oracle, and trading-agent workflows for compliance, safety, data-quality, privacy, and execution... |
| `quality-nonconformance` | Codified expertise for quality control, non-conformance investigation, root cause analysis, corrective action, and supplier quality... |
| `returns-reverse-logistics` | Codified expertise for returns authorization, receipt and inspection, disposition decisions, refund processing, fraud detection,... |
| `tearsheet` | Quick one-page company overview and snapshot |
| `working-capital` | Cash conversion cycle, earnings quality, and working capital deep-dive |

### 4.18 Sales, outreach & marketing — 57 skills

| Skill | Use when |
|---|---|
| `box-content-api` | Build and troubleshoot Box integrations for uploads, folders, folder listings, downloads and previews, shared links,... |
| `brand-discovery` | Use when a brand needs to discover or articulate its identity through structured multi-session interviews. Covers purpose,... |
| `brand-voice` | Build a source-derived writing style profile from real posts, essays, launch notes, docs, or site copy, then reuse that profile... |
| `canva-branded-presentation` | Create on-brand Canva presentations from a brief, outline, existing Canva doc, or design link. Use when the user wants a branded... |
| `canva-resize-for-all-social-media` | Resize a Canva design into standard social media formats and prepare export-ready results. Use when the user wants one Canva design... |
| `content-hash-cache-pattern` | Cache expensive file processing results using SHA-256 content hashes — path-independent, auto-invalidating, with service layer... |
| `crosspost` | Multi-platform content distribution across X, LinkedIn, Threads, and Bluesky. Adapts content per platform using content-engine... |
| `email` | Email sending integration guidance — Resend (native Vercel Marketplace) with React Email templates. Covers API setup, transactional... |
| `email-ops` | Evidence-first mailbox triage, drafting, send verification, and sent-mail-safe follow-up workflow for ECC. Use when the user wants... |
| `marketing-campaign` | End-to-end marketing campaign planning and execution. Covers audience research, positioning, campaign angle definition, landing... |
| `outlook-email` | Triage Outlook mail, extract tasks, clean up subscriptions, draft responses, and route shared mailbox work. Use when the user asks... |
| `outlook-email-inbox-triage` | Triage an Outlook inbox into actionable buckets such as urgent, needs reply soon, waiting, and FYI using connected Outlook data.... |
| `outlook-email-reply-drafting` | Draft Outlook email replies safely from connected mailbox context. Use when the user wants to reply to a thread, decide whether to... |
| `outlook-email-shared-mailboxes` | Work with delegated or shared Outlook Email mailboxes. Use when the user explicitly wants to read another mailbox, send from or on... |
| `outlook-email-subscription-cleanup` | Clean up Outlook newsletters and recurring subscription email safely. Use when the user wants to unsubscribe, separate newsletters... |
| `outlook-email-task-extraction` | Extract action items, deadlines, commitments, and owners from Outlook email threads and mailbox searches. Use when the user wants a... |
| `seo` | Audit, plan, and implement SEO improvements across technical SEO, on-page optimization, structured data, Core Web Vitals, and... |
| `shopify-admin` | Write or explain **Admin GraphQL** queries and mutations for apps and integrations that extend the Shopify admin. Use when the user... |
| `shopify-app-store-review` | Run a pre-submission compliance check against your Shopify app's codebase. Reviews App Store requirements and surfaces likely... |
| `shopify-customer` | The Customer Account API allows customers to access their own data including orders, payment methods, and addresses. |
| `shopify-dev` | Search Shopify developer documentation across all APIs. Use only when no API-specific skill applies. |
| `shopify-functions` | Shopify Functions allow developers to customize the backend logic that powers parts of Shopify. Available APIs: Discount, Cart and... |
| `shopify-hydrogen` | Hydrogen storefront implementation cookbooks. Some of the available recipes are: B2B Commerce, Bundles, Combined Listings, Custom... |
| `shopify-liquid` | Liquid is an open-source templating language created by Shopify. It is the backbone of Shopify themes and is used to load dynamic... |
| `shopify-onboarding-dev` | Get started building on Shopify. Use when a developer asks to build an app, build a theme, create a dev store, set up a partner... |
| `shopify-onboarding-merchant` | Set up and connect a Shopify store from your AI assistant. Use when the user wants to: set up my Shopify store, connect my store,... |
| `shopify-partner` | The Partner API lets you programmatically access data about your Partner Dashboard, including your apps, themes, and affiliate... |
| `shopify-payments-apps` | The Payments Apps API enables payment providers to integrate their payment solutions with Shopify's checkout. |
| `shopify-polaris-admin-extensions` | Add custom actions and blocks from your app at contextually relevant spots throughout the Shopify Admin. Admin UI Extensions also... |
| `shopify-polaris-app-home` | Build your app's primary user interface embedded in the Shopify admin. If the prompt just mentions `Polaris` and you can't tell... |
| `shopify-polaris-checkout-extensions` | Build custom functionality that merchants can install at defined points in the checkout flow, including product information,... |
| `shopify-polaris-customer-account-extensions` | Build custom functionality that merchants can install at defined points on the Order index, Order status, and Profile pages in... |
| `shopify-use-shopify-cli` | Choose when the user needs **Shopify CLI** to run or fix something now: validate app or extension config on disk... |
| `slack` | Read Slack context, route to the right Slack workflow, and prepare or perform Slack writes that match the user's intent. |
| `slack-channel-summarization` | Summarize activity from one Slack channel and return a concise recap, post-ready update, or summary doc. |
| `slack-daily-digest` | Create a daily Slack digest from selected channels or topics. Use when the user asks for a daily Slack recap or summary of today's... |
| `slack-notification-triage` | Triage recent Slack activity into a priority queue or task list for the user. |
| `slack-outgoing-message` | Primary skill for composing, drafting, or refining any outbound Slack content. Use this whenever the task will require using... |
| `slack-reply-drafting` | Draft Slack replies from available context. Use when the user wants help finding messages that likely need a response and preparing... |
| `social-graph-ranker` | Weighted social-graph ranking for warm intro discovery, bridge scoring, and network gap analysis across X and LinkedIn. Use when... |
| `social-publish-scheduling` | Plan, schedule, and publish social media content across platforms — content calendars, per-platform formatting, hashtag and... |
| `social-publisher` | Agent-driven scheduling and publishing of social media posts across 13 platforms via SocialClaw. Use when the user wants to publish... |
| `teams` | Search through Microsoft Teams chats or channels, triage unread or recent activity, draft follow-ups, and manage Planner tasks... |
| `teams-channel-summarization` | Summarize activity from one Microsoft Teams channel or one scoped Teams conversation and return a concise recap or post-ready... |
| `teams-daily-digest` | Create a daily Microsoft Teams digest from selected chats, channels, or workstreams. Use when the user asks for a daily Teams recap... |
| `teams-messages` | Compose, route, draft, or send Microsoft Teams messages with exact destination resolution, real user mentions, and Teams-native DM... |
| `teams-notification-triage` | Triage recent Microsoft Teams activity into a priority queue or task list for the user. |
| `teams-planner-task-management` | Review and manage Microsoft Planner tasks from Teams workflows. Use when the user wants to inspect plans or buckets, create tasks... |
| `teams-reply-drafting` | Draft Microsoft Teams replies from available context. Use when the user wants help finding messages that likely need a response and... |
| `twilio-content-template-builder` | Create, manage, and send message templates using Twilio's Content API. Covers template creation for WhatsApp, SMS, RCS, and MMS;... |
| `twilio-email-deliverability-advisor` | Deliverability advisor for the Twilio Email API specifically. Use ONLY when the developer explicitly mentions Twilio Email,... |
| `twilio-email-send` | Use when the caller has Twilio credentials (Account SID + Auth Token or API Key SID + Secret) and needs to send email via... |
| `twilio-sendgrid-email-send` | Send transactional and bulk email via the SendGrid v3 Mail Send API. Covers single sends, personalized batch sends with dynamic... |
| `twilio-sendgrid-email-settings` | Configure SendGrid dynamic templates (Handlebars), tracking settings (opens, clicks, subscriptions), link branding for custom... |
| `wix-app` | Build and review Wix CLI app extensions — dashboard pages, modals, plugins, menu plugins, custom element widgets, Editor React... |
| `wix-headless` | Build a complete Wix Managed Headless site from a single prompt, OR connect an existing project (HTML/JSX/Vite app, Claude Design... |
| `wix-manage` | Wix business solution management recipes — REST API operations for configuring and managing Wix business solutions. Routes to:... |

### 4.19 Communication & productivity — 102 skills

| Skill | Use when |
|---|---|
| `build-zoom-bot` | Use when building bots. |
| `build-zoom-contact-center-app` | Use when using Contact Center. |
| `build-zoom-meeting-app` | Use when embedding meetings. |
| `build-zoom-meeting-sdk-app` | Use when using Meeting SDK. |
| `build-zoom-rest-api-app` | Use when calling REST APIs. |
| `build-zoom-team-chat-app` | Use when building Team Chat. |
| `build-zoom-video-sdk-app` | Use when using Video SDK. |
| `capture-tasks-from-meeting-notes` | Analyze meeting notes to find action items and create Jira tasks for assigned work. When an agent needs to: (1) Create Jira tasks... |
| `choose-zoom-approach` | Use when choosing architecture. |
| `debug-zoom` | Use when debugging issues. |
| `deepnote` | Use when a task mentions Deepnote, the connected Deepnote app, Deepnote OAuth connection, Deepnote docs, projects, workspaces,... |
| `deepnote-links` | Use when a task asks for Deepnote URLs, links, project links, notebook links, workspace links, share links, UTM/campaign links, or... |
| `deepnote-notebook-editing` | Use when creating Deepnote projects or notebooks, adding or updating blocks or cells, moving existing blocks, scaffolding notebook... |
| `deepnote-notebooks` | Use when reading, reviewing, inspecting, or reasoning about hosted Deepnote notebooks, blocks, inputs, SQL, Python, or notebook... |
| `gmail` | Manage Gmail inbox triage, mailbox search, thread summaries, action extraction, reply drafting, and email forwarding through... |
| `gmail-inbox-triage` | Triage a Gmail inbox into actionable buckets such as urgent, needs reply soon, waiting, and FYI using connected Gmail data. Use... |
| `google-calendar` | Manage scheduling and conflicts in connected Google Calendar data. Use when the user wants to inspect calendars, compare... |
| `google-calendar-free-up-time` | Find ways to open up meaningful free time in a connected Google Calendar. Use when the user wants to clear up their day, make room... |
| `google-calendar-group-scheduler` | Find and rank good meeting times for multiple people using connected Google Calendar data. Use when the user wants to schedule a... |
| `google-calendar-meeting-prep` | Build a practical meeting prep brief from a connected Google Calendar event and its nearby context. Use when the user wants to... |
| `google-docs` | Connector-first Google Docs creation and editing in local Codex plugin sessions, with direct native create and batchUpdate... |
| `google-drive` | Use connected Google Drive as the single entrypoint for Drive, Docs, Sheets, and Slides work. Use when the user wants to find,... |
| `google-drive-comments` | Write, reply to, and resolve Google Drive comments on Docs, Sheets, Slides, and Drive files with evidence-backed location context.... |
| `google-sheets` | Analyze and edit connected Google Sheets with range precision. Use when the user wants to create Google Sheets, find a spreadsheet,... |
| `grill-with-docs` | A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go. |
| `linear` | Manage issues, projects & team workflows in Linear. Use when the user wants to read, create or updates tickets in Linear. |
| `m5-onboard` | End-to-end onboarding for a freshly-plugged-in M5Stack ESP32 device (Cardputer, Cardputer-Adv, Core, CoreS3, Stick) — detect on... |
| `magicpath` | Use when the user mentions MagicPath, designs, UI components, themes, canvas selections, or repo-to-canvas UI work; run... |
| `meeting-scheduler` | Handles end-to-end meeting scheduling using the Superhuman Mail MCP server — from finding available times to sending the invite or... |
| `notion-knowledge-capture` | Capture conversations and decisions into structured Notion pages; use when turning chats/notes into wiki entries, how-tos,... |
| `notion-meeting-intelligence` | Prepare meeting materials with Notion context and Codex research; use when gathering context, drafting agendas/pre-reads, and... |
| `notion-spec-to-implementation` | Turn Notion specs into implementation plans, tasks, and progress tracking; use when implementing PRDs/feature specs and creating... |
| `outlook-calendar` | Handle Outlook Calendar workflows, including delegated/shared calendar writes. Use when the user asks for schedule understanding,... |
| `outlook-calendar-free-up-time` | Find ways to open up meaningful free time in Outlook Calendar. Use when the user wants to clear part of their schedule, make room... |
| `outlook-calendar-group-scheduler` | Find and rank good meeting times for several people using Outlook Calendar data. Use when the user wants to schedule a meeting,... |
| `outlook-calendar-meeting-prep` | Build a practical meeting prep brief from an Outlook Calendar event and its nearby Microsoft context. Use when the user wants to... |
| `outlook-calendar-shared-calendars` | Safely write to delegated or shared Outlook calendars. Use when the user explicitly wants to create, update, respond to, cancel,... |
| `plan-zoom-product` | Use when choosing products. |
| `pylance-docs` | Use when the user explicitly asks for the Pylance docs skill, or when an answer depends on current official Pylance documentation... |
| `setup-zoom-oauth` | Use when setting up OAuth. |
| `setup-zoom-websockets` | Use when building Zoom WebSockets. |
| `sharepoint` | Inspect Microsoft SharePoint context, discover the right site or library, and prepare safe changes. Use when the user wants site,... |
| `sharepoint-powerpoint` | Create, edit, restyle, and review PowerPoint `.pptx` files fetched from SharePoint, with emphasis on style preservation, slide... |
| `sharepoint-site-discovery` | Resolve the right SharePoint site, library, and folder before file work. Use when the user needs to find the right site context,... |
| `sharepoint-spreadsheet-formula-builder` | Design, repair, and roll out formulas in SharePoint-hosted workbooks with connector-aware retrieval, validation, and upload... |
| `sharepoint-spreadsheets` | Edit SharePoint-hosted spreadsheet files while preserving workbook structure, formulas, and formatting. Use when the user wants to... |
| `sharepoint-word-docs` | Edit SharePoint-hosted Word `.docx` files while preserving document structure and styling. Use when the user wants to update a real... |
| `superhuman-mail` | Use Superhuman Mail MCP for email and calendar workflows such as searching inboxes, reading threads, drafting or sending mail,... |
| `twilio-account-setup` | Create and configure a Twilio account from scratch. Covers free trial signup, trial limitations, getting credentials (Account SID... |
| `twilio-call-recordings` | Record Twilio voice calls correctly. Covers the critical distinction between Record verb (voicemail) and Dial record (call... |
| `twilio-cli-reference` | Twilio CLI reference for managing Twilio resources from the terminal. Covers installation, credential profiles, phone number... |
| `twilio-conference-calls` | Build multi-party calls using Twilio Conference. Covers warm transfer, cold transfer, coaching (whisper), hold vs mute, participant... |
| `twilio-conversation-orchestrator` | Configure automatic conversation capture and routing with Twilio Conversation Orchestrator. Covers Configuration creation, channel... |
| `twilio-conversations-classic-api` | Build multi-channel messaging experiences using Twilio Conversations (classic) API. Covers creating conversations, adding... |
| `twilio-customer-memory` | Store and retrieve customer context using Twilio Conversation Memory. Covers Memory Store provisioning, profile management, traits,... |
| `twilio-debugging-observability` | Debug Twilio integrations and set up production observability. Covers the Console Debugger, Monitor Alerts API, Event Streams for... |
| `twilio-enterprise-knowledge` | Add knowledge retrieval to AI agents using Twilio's Enterprise Knowledge product. Enterprise Knowledge is a centralized, searchable... |
| `twilio-iam-auth-setup` | Set up and manage Twilio authentication credentials: Auth Tokens, API keys (Standard, Main, Restricted), Access Tokens for... |
| `twilio-isv-sms-best-practices` | Best practices for ISVs (Independent Software Vendors) building SMS features into multi-tenant SaaS platforms using Twilio. Covers... |
| `twilio-lookup-phone-intelligence` | Look up phone number intelligence via Twilio Lookup v2 API. Covers number validation, line type detection (mobile/landline/VoIP),... |
| `twilio-marketing-promotions-advisor` | Planning skill for marketing and promotional messaging. Qualifies the developer's campaign needs across channel selection,... |
| `twilio-messaging-channel-advisor` | Planning skill that helps the developer pick the right Twilio messaging channel — SMS, MMS, RCS, or WhatsApp — for a given use... |
| `twilio-messaging-overview` | Twilio Messaging channel overview and onboarding guide. Covers all channels (SMS, WhatsApp, RCS, Facebook Messenger), the unified... |
| `twilio-messaging-services` | Create and configure Twilio Messaging Services for production messaging. Covers sender pools, geo-match, sticky sender, message... |
| `twilio-notifications-alerts-advisor` | Planning skill for transactional notifications, alerts, and reminders. Qualifies the developer's needs across urgency, channel... |
| `twilio-numbers-senders` | Choose the right Twilio number type and sender BEFORE building. Covers phone numbers (local, toll-free, short code, mobile),... |
| `twilio-organizations-setup` | Set up and manage Twilio Organizations for centralized account and user governance. Covers the Organization > Account > Subaccount... |
| `twilio-rcs-messaging` | Send RCS Business Messages via Twilio. Covers compliance onboarding (7-part US process), sender profile setup, sending rich cards... |
| `twilio-reliability-patterns` | Handle rate limits, retries, and failures when building on Twilio at scale. Covers 429 exponential backoff with jitter, per-number... |
| `twilio-send-message` | Send messages via Twilio's Programmable Messaging API across all channels — SMS, MMS, RCS, and WhatsApp. Covers text messages,... |
| `twilio-sendgrid-account-setup` | Set up a SendGrid account for email delivery. Covers API key creation (SG.-prefix), domain authentication (DKIM/SPF via CNAME... |
| `twilio-sendgrid-deliverability-advisor` | Diagnostic and advisory skill for email deliverability problems. Use when a developer asks why emails are going to spam, not... |
| `twilio-sendgrid-engagement-quality` | Monitor email program health with SendGrid Engagement Quality (SEQ) scores. Covers the SEQ API endpoints, the 5 scoring metrics... |
| `twilio-sendgrid-inbound-parse` | Receive inbound email via SendGrid Inbound Parse webhook. Covers MX record setup, parsed vs raw mode, handling attachments, and... |
| `twilio-sendgrid-suppressions` | Manage SendGrid email suppressions: bounces, blocks, spam reports, invalid emails, global unsubscribes, and ASM suppression groups.... |
| `twilio-sms-send-message` | SMS and MMS deep-dive reference. Covers SMS-specific error codes, message filtering troubleshooting ("Messages Being Filtered or... |
| `twilio-taskrouter-routing` | Route tasks to agents using Twilio TaskRouter. Covers Workers, Task Queues, Workflows, Reservations, skills-based routing, and... |
| `twilio-verify-send-otp` | Send and verify one-time passcodes (OTPs) via Twilio Verify over SMS, RCS, voice, email, or WhatsApp. Covers creating a Verify... |
| `twilio-voice-conversation-relay` | Build AI-powered voice agents using Twilio ConversationRelay. Handles real-time speech recognition (ASR), text-to-speech (TTS), and... |
| `twilio-voice-outbound-calls` | Make outbound phone calls via Twilio's Programmable Voice REST API. Covers the full voice platform: calls.create(), answering... |
| `twilio-voice-twiml` | Build voice call logic using TwiML (Twilio Markup Language). Covers the core verbs (Say, Play, Gather, Dial, Record, Conference),... |
| `twilio-whatsapp-manage-senders` | Create, configure, and manage WhatsApp Business senders via Twilio's Channels Senders API. Covers programmatic sender registration,... |
| `twilio-whatsapp-send-message` | WhatsApp messaging deep-dive reference. Covers the 24-hour service window rules (free-form vs template mode), sandbox setup for... |
| `zoom-apps-sdk` | Use when using Apps SDK. |
| `zoom-cobrowse-sdk` | Use when using Cobrowse. |
| `zoom-contact-center-web` | Zoom Contact Center SDK for Web. Use for web chat/video/campaign embeds, engagement event handling, app-context integrations, and... |
| `zoom-general` | Use when comparing products. |
| `zoom-meeting-sdk-electron` | Zoom Meeting SDK for Electron desktop applications. Use when embedding Zoom meetings in an Electron app with the Node addon... |
| `zoom-meeting-sdk-linux` | Zoom Meeting SDK for Linux - C++ headless meeting bots with raw audio/video access, transcription, recording, and AI integration... |
| `zoom-meeting-sdk-macos` | Zoom Meeting SDK for macOS native apps. Use when embedding Zoom meetings in macOS with default/custom UI, PKCE + SDK auth, host... |
| `zoom-meeting-sdk-unreal` | Zoom Meeting SDK for Unreal Engine wrapper integrations. Use when building Unreal projects that embed Zoom meetings with C++ and... |
| `zoom-meeting-sdk-web` | Zoom Meeting SDK for Web - Embed Zoom meeting capabilities into web applications. Two integration options: Client View (full-page,... |
| `zoom-meeting-sdk-web-client-view` | Zoom Meeting SDK Web - Client View. Full-page Zoom meeting experience with the familiar Zoom interface. Uses ZoomMtg global... |
| `zoom-meeting-sdk-web-component-view` | Zoom Meeting SDK Web - Component View. Embeddable Zoom meeting components with Promise-based API for flexible integration. Ideal... |
| `zoom-meeting-sdk-windows` | Zoom Meeting SDK for Windows - Native C++ SDK for embedding Zoom meetings into Windows desktop applications. Supports custom UI... |
| `zoom-oauth` | Use when implementing OAuth. |
| `zoom-rtms` | Use when using RTMS. |
| `zoom-video-sdk-linux` | Zoom Video SDK for Linux - C++ headless bots, raw audio/video capture/injection, Qt/GTK integration, Docker support |
| `zoom-video-sdk-macos` | Zoom Video SDK for macOS native desktop apps. Use when building custom macOS video sessions with native UI control, tokenized join,... |
| `zoom-video-sdk-unity` | Zoom Video SDK for Unity wrapper integrations. Use when building custom Unity-based video session experiences and mapping Unity... |
| `zoom-video-sdk-web` | Zoom Video SDK for Web - JavaScript/TypeScript integration for browser-based video sessions, real-time communication, screen... |
| `zoom-video-sdk-windows` | Zoom Video SDK for Windows - C++ integration for video sessions, raw audio/video capture, screen sharing, recording, and real-time... |

### 4.20 Network & infrastructure — 10 skills

| Skill | Use when |
|---|---|
| `connections-optimizer` | Reorganize the user's X and LinkedIn network with review-first pruning, add/follow recommendations, and channel-specific warm... |
| `homelab-network-readiness` | Readiness checklist for homelab VLAN segmentation, local DNS filtering, and WireGuard-style remote access before changing router,... |
| `homelab-network-setup` | Practical home and homelab network planning for gateways, switches, access points, IP ranges, DHCP reservations, DNS, cabling, and... |
| `homelab-pihole-dns` | Pi-hole installation, blocklist management, DNS-over-HTTPS setup, DHCP integration, local DNS records, and troubleshooting broken... |
| `homelab-vlan-segmentation` | Segmenting home networks into VLANs for IoT, guest, trusted, and server traffic using UniFi, pfSense/OPNsense, and MikroTik —... |
| `homelab-wireguard-vpn` | WireGuard VPN server setup, peer configuration, key generation, split tunneling vs full tunnel routing, and remote access to a home... |
| `netmiko-ssh-automation` | Safe Python Netmiko patterns for read-only collection, bounded batch SSH, TextFSM parsing, guarded config changes, timeouts, and... |
| `network-bgp-diagnostics` | Diagnostics-only BGP troubleshooting patterns for neighbor state, route exchange, prefix policy, AS path inspection, and safe... |
| `network-config-validation` | Pre-deployment checks for router and switch configuration, including dangerous commands, duplicate addresses, subnet overlaps,... |
| `routing-middleware` | Vercel Routing Middleware guidance — request interception before cache, rewrites, redirects, personalization. Works with any... |

### 4.21 Game, 3D & video — 15 skills

| Skill | Use when |
|---|---|
| `comfyui-video-workflows` | Build and run ComfyUI workflows for video generation and animation, including Wan and LTX-Video model wrappers, graph structure,... |
| `game-playtest` | Run browser-game playtests and frontend QA. Use when the user asks for smoke tests, screenshot-based verification, browser... |
| `game-studio` | Route early browser-game work. Use when the user needs stack selection and workflow planning across design, implementation, assets,... |
| `heygen-avatar` | Create a persistent HeyGen avatar — a reusable face + voice identity for the agent, the user, or any named character — powered by... |
| `heygen-video` | Generate HeyGen presenter videos via the v3 Video Agent pipeline — handles Frame Check (aspect ratio correction), prompt... |
| `manim-video` | Build reusable Manim explainers for technical concepts, graphs, system diagrams, and product walkthroughs, then hand off to the... |
| `phaser-2d-game` | Implement 2D browser games with Phaser. Use when the user wants a Phaser, TypeScript, and Vite stack for scenes, gameplay systems,... |
| `subtitle-generation` | Generate, time, and burn-in subtitles and captions using local open-source tools — whisper.cpp and faster-whisper for... |
| `text-to-video-local` | Generate video from text or image prompts using local, open-source models — Wan2.2, HunyuanVideo, LTX-Video, CogVideoX, Mochi, and... |
| `three-webgl-game` | Implement browser-game runtimes with plain Three.js. Use when the user wants imperative scene control in TypeScript or Vite with... |
| `tts-to-video` | Compose a complete video from a script by generating a voiceover with local TTS, timing visuals to the audio, and assembling the... |
| `video-background-removal` | Remove or replace backgrounds in video footage using local open-source tools — rembg with video support, MediaPipe Selfie... |
| `video-editing` | AI-assisted video editing workflows for cutting, structuring, and augmenting real footage. Covers the full pipeline from raw... |
| `video-upscale-interpolate` | Upscale video resolution and increase frame rate using local open-source tools — Real-ESRGAN, video2x, Waifu2x, and RIFE frame... |
| `web-game-foundations` | Set browser-game architecture before implementation. Use when the user needs engine choice, simulation and render boundaries, input... |

### 4.22 Skill & agent authoring — 34 skills

| Skill | Use when |
|---|---|
| `biobankjapan-phewas-skill` | Fetch compact BioBank Japan PheWAS summaries for single variants by accepting rsID, GRCh38, or GRCh37 input and resolving to the... |
| `clinicaltrials-skill` | Submit compact ClinicalTrials.gov API v2 requests for study search, metadata, enums, search areas, and field statistics. Use when a... |
| `command-development` | This skill should be used when the user asks to "create a slash command", "add a command", "write a custom command", "define... |
| `epigraphdb-skill` | Submit compact EpiGraphDB API requests for ontology, literature, MR, gene-drug, and support-path evidence. Use when a user wants... |
| `eqtl-catalogue-skill` | Submit compact eQTL Catalogue API requests for association retrieval and documented metadata endpoints. Use when a user wants... |
| `evaluate-plugin` | Evaluate a local Codex plugin in engineer-friendly language. Use when the user says "evaluate this plugin", "audit this plugin",... |
| `evaluate-skill` | Evaluate a local Codex skill in engineer-friendly terms. Use when the user says "evaluate this skill", "give me an analysis of the... |
| `example-skill` | This skill should be used when the user asks to "demonstrate skills", "show skill format", "create a skill template", or discusses... |
| `hook-development` | This skill should be used when the user asks to "create a hook", "add a PreToolUse/PostToolUse/Stop hook", "validate tool use",... |
| `hookify-rules` | This skill should be used when the user asks to create a hookify rule, write a hook rule, configure hookify, add a hookify rule, or... |
| `improve-skill` | Turn plugin-eval findings into a concrete rewrite brief for a Codex skill. Use when the user already evaluated a skill and now... |
| `minimal-plugin-skill` | Minimal plugin skill fixture. Use when a test needs a valid plugin skill. |
| `minimal-skill` | Minimal example skill for plugin-eval tests. Use when the user wants a compact demonstration of a well-structured skill. |
| `pharmgkb-skill` | Submit compact PharmGKB API requests for genes, variants, clinical annotations, dosing guidelines, and search. Use when a user... |
| `plugin` | How to manage and create plugins — namespaced bundles of skills, agents, rules, MCP servers and hooks that install, enable and... |
| `plugin-creator` | Create and scaffold plugin directories for Codex with a required `.codex-plugin/plugin.json`, optional plugin folders/files, valid... |
| `plugin-management` | Discover and suggest relevant plugins, inspect app permissions and dependencies, and manage plugin connections or removal. Use when... |
| `plugin-settings` | This skill should be used when the user asks about "plugin settings", "store plugin configuration", "user-configurable plugin",... |
| `plugin-structure` | This skill should be used when the user asks to "create a plugin", "scaffold a plugin", "understand plugin structure", "organize... |
| `proteomexchange-skill` | Submit compact ProteomeXchange PROXI requests for datasets, libraries, peptidoforms, proteins, PSMs, spectra, and USI examples. Use... |
| `rnacentral-skill` | Submit compact RNAcentral API requests for RNA entry browsing, single-entry lookup, and cross-reference retrieval. Use when a user... |
| `rules-distill` | Scan skills to extract cross-cutting principles and distill them into rules — append, revise, or create new rule files |
| `setup-matt-pocock-skills` | Configure this repo for the engineering skills: set up its issue tracker, triage label vocabulary, and domain doc layout. Run once... |
| `skill-comply` | Visualize whether skills, rules, and agent definitions are actually followed — auto-generates scenarios at 3 prompt strictness... |
| `skill-creator` | Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a skill from... |
| `skill-creator-plus` | Create new skills, modify and improve existing skills, and measure skill performance. Use this whenever a user wants to build a... |
| `skill-development` | This skill should be used when the user wants to "create a skill", "add a skill to plugin", "write a new skill", "improve skill... |
| `skill-installer` | Install Codex skills into $CODEX_HOME/skills from a curated list or a GitHub repo path. Use when a user asks to list installable... |
| `skill-library-adder` | Adds a new skill or a new agent to this library and to the MCP server that serves it. Use this whenever the user wants to add an... |
| `skill-scout` | Search existing local, marketplace, GitHub, and web skill sources before creating a new skill. Use when the user wants to create,... |
| `skill-stocktake` | Use when auditing Claude skills and commands for quality. Supports Quick Scan (changed skills only) and Full Stocktake modes with... |
| `string-skill` | Submit compact STRING API requests for network, interaction partner, and enrichment endpoints. Use when a user wants concise STRING... |
| `writing-hookify-rules` | This skill should be used when the user asks to "create a hookify rule", "write a hook rule", "configure hookify", "add a hookify... |
| `writing-skills` | Use when creating new skills, editing existing skills, or verifying skills work before deployment |

### 4.23 Vendor SaaS APIs — 21 skills

| Skill | Use when |
|---|---|
| `base44-cli` | The base44 CLI is used for EVERYTHING related to base44 projects: resource configuration (entities, backend functions, ai agents),... |
| `base44-sdk` | The base44 SDK is the library to communicate with base44 services. In projects, you use it to communicate with remote resources... |
| `base44-troubleshooter` | Troubleshoot production issues using backend function logs. Use when investigating app errors, debugging function calls, or... |
| `circleci-builds` | Diagnose and fix failing CircleCI builds quickly and safely. Use when users ask to investigate failed CircleCI jobs, triage flaky... |
| `circleci-cli` | Operate and troubleshoot CircleCI using the CircleCI CLI. Use when users ask to authenticate CLI access, inspect... |
| `circleci-config` | Optimize CircleCI configuration for speed, reliability, and maintainability. Use when users ask to improve `.circleci/config.yml`,... |
| `durable-objects` | Create and review Cloudflare Durable Objects. Use when building stateful coordination (chat rooms, multiplayer games, booking... |
| `figma-code-connect` | Creates and maintains Figma Code Connect template files that map Figma components to code snippets. Use when the user mentions Code... |
| `figma-create-new-file` | **MANDATORY prerequisite** — you MUST invoke this skill BEFORE every `create_new_file` tool call. NEVER call `create_new_file`... |
| `figma-generate-diagram` | MANDATORY prerequisite — load this skill BEFORE every `generate_diagram` tool call. NEVER call `generate_diagram` directly without... |
| `figma-generate-library` | Build or update a professional-grade design system in Figma from a codebase. Use when the user wants to create variables/tokens,... |
| `figma-use` | **MANDATORY prerequisite** — you MUST invoke this skill BEFORE every `use_figma` tool call. NEVER call `use_figma` directly without... |
| `figma-use-figjam` | This skill helps agents use Figma's use_figma MCP tool in the FigJam context. Can be used alongside figma-use which has... |
| `figma-use-slides` | This skill helps agents use Figma's use_figma MCP tool in the Slides context. Can be used alongside figma-use which has... |
| `google-slides` | Google Slides work for finding, reading, summarizing, creating, importing, template following, visual cleanup, source-deck... |
| `mixpanel-auth` | Manage Mixpanel Headless authentication: check session state, list/add/use accounts, run OAuth login, switch projects/workspaces,... |
| `mixpanel-headless-setup` | This skill installs mixpanel_headless, pandas, numpy, matplotlib, seaborn, networkx, anytree, scipy (and pyarrow on Python 3.11+),... |
| `posthog` | Analyze product data and manage product tooling in PostHog. Use when the user wants product analytics or insights, HogQL/SQL... |
| `sentry` | Use when the user asks to inspect Sentry issues or events, summarize recent production errors, or pull basic Sentry health data via... |
| `stripe-best-practices` | Guides Stripe integration decisions — API selection (Checkout Sessions vs PaymentIntents), Connect platform setup (Accounts v2,... |
| `upgrade-stripe` | Guide for upgrading Stripe API versions and SDKs |

### 4.24 Agent orchestration & workflows — 34 skills

| Skill | Use when |
|---|---|
| `agentic-engineering` | Operate as an agentic engineer using eval-first execution, decomposition, and cost-aware model routing. Use when AI agents perform... |
| `agentic-os` | Build persistent multi-agent operating systems on Claude Code. Covers kernel architecture, specialist agents, slash commands,... |
| `autonomous-loops` | Patterns and architectures for autonomous Claude Code loops — from simple sequential pipelines to RFC-driven multi-agent DAG systems. |
| `background-removal-segmentation` | Remove backgrounds from images and segment subjects using local open-source tools — rembg with BiRefNet and U²-Net models, IOPaint... |
| `continuous-learning` | [DEPRECATED - use continuous-learning-v2] Legacy v1 stop-hook skill extractor. v2 is a strict superset with instinct-based,... |
| `continuous-learning-v2` | Instinct-based learning system that observes sessions via hooks, creates atomic instincts with confidence scoring, and evolves them... |
| `council` | Convene a four-voice council for ambiguous decisions, tradeoffs, and go/no-go calls. Use when multiple valid paths exist and you... |
| `cron-jobs` | Vercel Cron Jobs configuration and best practices. Use when adding, editing, or debugging scheduled tasks in vercel.json. |
| `dmux-workflows` | Multi-agent orchestration using dmux (tmux pane manager for AI agents). Patterns for parallel agent workflows across Claude Code,... |
| `dynamic-workflow-mode` | Design task-local harnesses, eval gates, and reusable skill extraction for Claude dynamic workflow mode and other adaptive agent... |
| `gan-style-harness` | GAN-inspired Generator-Evaluator agent harness for building high-quality applications autonomously. Based on Anthropic's March 2026... |
| `initiate` | Initiate coverage — generate both research note (HTML) and Excel model (.xlsx) |
| `intent-driven-development` | Turn ambiguous or high-impact product and engineering changes into scoped, verifiable acceptance criteria before or alongside... |
| `iterative-retrieval` | Pattern for progressively refining context retrieval to solve the subagent context problem |
| `launch-readiness-orchestrator` | Launch Readiness Orchestrator skill for Datasite deal rooms. Use this skill whenever a deal team wants a single pre-go-live... |
| `migrate-workflows` | Automatically migrate legacy workflows to modern skills across global and workspace configurations. Scans for existing workflows,... |
| `mle-workflow` | Production machine-learning engineering workflow for data contracts, reproducible training, model evaluation, deployment,... |
| `orch-add-feature` | Orchestrate building a brand-new feature end to end — research, plan, TDD implementation, review, and gated commit — by delegating... |
| `orch-build-mvp` | Orchestrate bootstrapping a working MVP from a design or spec document — ingest the doc, plan thin vertical slices, scaffold the... |
| `orch-change-feature` | Orchestrate altering an existing, working feature to new desired behavior — update its tests to the new spec, change the... |
| `orch-fix-defect` | Orchestrate fixing a bug — reproduce it as a failing regression test, fix to green, review, and gated commit — by delegating each... |
| `orch-refine-code` | Orchestrate a behavior-preserving refactor — confirm tests are green, restructure without changing behavior, keep tests green,... |
| `parallel-execution-optimizer` | Use when the user wants a task done much faster through parallel work, concurrent agents, batched tool calls, isolated worktrees,... |
| `plan-orchestrate` | Read a plan document, decompose it into steps, design a per-step agent chain from the ECC catalogue, and emit ready-to-paste... |
| `project-flow-ops` | Operate execution flow across GitHub and Linear by triaging issues and pull requests, linking active work, and keeping GitHub... |
| `run-workflow` | How to write and run a dynamic workflow script with the `run_workflow` tool: a Python script that orchestrates many agents with... |
| `start` | Use when starting Zoom work. |
| `subagent-driven-development` | Use when executing implementation plans with independent tasks in the current session |
| `swarm` | Run a swarm: several agents working in parallel on one task, each in its own conversation, collaborating through a shared message... |
| `swarm_narrator` | ONLY for the native-swarm worker whose brief says it is the narrator. It watches the board and keeps the user's Overview (view.json... |
| `template` | Canonical rules and HTML/CSS contract for the page chrome (head boilerplate, cover, table of contents, section block,... |
| `terminal-ops` | Evidence-first repo execution workflow for ECC. Use when the user wants a command run, a repo checked, a CI failure debugged, or a... |
| `using-superpowers` | Use when starting any conversation - establishes how to find and use skills, requiring Skill tool invocation before ANY response... |
| `workflow` | Vercel Workflow DevKit (WDK) expert guidance. Use when building durable workflows, long-running tasks, API routes or agents that... |

### 4.25 Code review & quality — 19 skills

| Skill | Use when |
|---|---|
| `code-review` | Reviews code changes using CodeRabbit AI. Use when user asks for code review, PR feedback, code quality checks, security issues, or... |
| `finding-discovery` | Use when Codex is already in the finding-discovery phase of a security scan or the user explicitly asks to discover candidate... |
| `fix-finding` | Use when the user explicitly asks to fix and verify a validated or plausible security finding. Do not use as the primary trigger... |
| `gap-analysis` | Data Room Gap Analysis skill for Datasite deal rooms. Use this skill whenever a sell-side deal team wants to audit what is missing,... |
| `investigation-mode` | Orchestrated debugging coordinator. Triggers on frustration signals (stuck, hung, broken, waiting) and systematically triages:... |
| `mattpocock-code-review` | Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes: Standards (does the code follow this... |
| `plankton-code-quality` | Write-time code quality enforcement using Plankton — auto-formatting, linting, and Claude-powered fixes on every file edit via hooks. |
| `precedent-transactions` | Precedent M&A transactions analysis with deal multiples and acquisition history |
| `production-audit` | Local-evidence production readiness audit for shipped apps, pre-launch reviews, post-merge checks, and "what breaks in prod?"... |
| `pylance-refactoring` | Use when the user explicitly asks for the Pylance refactoring skill, or when they want named automated Python refactorings applied... |
| `receiving-code-review` | Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically... |
| `requesting-code-review` | Use when completing tasks, implementing major features, or before merging to verify work meets requirements |
| `risk-analysis-audit` | Risk Analysis Audit skill for Datasite deal rooms. Use this skill whenever a sell-side deal team wants to audit, review, or flag... |
| `scribe` | Use when using Scribe. |
| `triage` | Move issues and external PRs through a state machine of triage roles, categorise, verify, grill if needed, and write agent-ready... |
| `triage-finding` | Use when the user supplies or imports existing security findings, vulnerability reports, or security/vulnerability Jira/Linear... |
| `triage-issue` | Intelligently triage bug reports and error messages by searching for duplicates in Jira and offering to create new issues or add... |
| `validation` | Use when Codex is already in the validation phase of a security scan or the user explicitly asks to determine whether one or more... |
| `vulnerability-writeup` | Write up vulnerabilities from disclosure documents, rough notes, supplied findings, PoCs, source code, or Codex Security scan... |

### 4.26 Frontend platforms & meta-frameworks — 64 skills

| Skill | Use when |
|---|---|
| `appkit-interop` | Bridge macOS SwiftUI into AppKit narrowly. Use when implementing representables, reaching NSWindow or panels, handling menus, or... |
| `brighthire` | Use BrightHire tools when a user asks about BrightHire interview intelligence, calls, candidates, roles, scorecards, transcripts,... |
| `cardputer-buddy` | Iterate on the Cardputer-Adv MicroPython app bundle (Claude Buddy, Snake, Hello) after the device is already provisioned via... |
| `catalyst-by-zoho` | Expert coding assistant for Catalyst by Zoho — full-stack serverless cloud platform. Trigger on any mention of Catalyst, zcatalyst,... |
| `ck` | Persistent per-project memory for Claude Code. Auto-loads project context on session start, tracks sessions with git activity, and... |
| `conversation-intelligence` | Twilio Conversation Intelligence development guide. Use when building real-time or post-call conversation analysis, language... |
| `env-vars` | Vercel environment variable expert guidance. Use when working with .env files, vercel env commands, OIDC tokens, or managing... |
| `eod-wrapup` | Generates an end-of-day wrap-up using the Superhuman Mail MCP server — identifies open loops, unanswered emails, and action items... |
| `exa-search` | Neural search via Exa MCP for web, code, and company research. Use when the user needs web search, code examples, company intel,... |
| `flox-environments` | Create reproducible, cross-platform (macOS/Linux) development environments with Flox, a declarative Nix-based environment manager.... |
| `geistdocs` | Expert guidance for Geistdocs, Vercel's documentation template built with Next.js and Fumadocs — MDX authoring, configuration, AI... |
| `generate-snapshot` | Generate a codebase health snapshot for technical debt tracking and planning. Analyzes git history, code complexity, debt markers,... |
| `gsap` | GSAP animation reference for HyperFrames. Covers gsap.to(), from(), fromTo(), easing, stagger, defaults, timelines... |
| `guidance-tracker` | Track management guidance accuracy over time for a given company |
| `hermes-imports` | Convert local Hermes operator workflows into sanitized ECC skills and release-pack artifacts. Use when preparing a Hermes workflow... |
| `hisabkora-context` | Compact project summary for HisabKora (Bangla personal-finance tracker). Use when a new session asks "what is this project?", when... |
| `hyperframes` | Create video compositions, animations, title cards, overlays, captions, voiceovers, audio-reactive visuals, and scene transitions... |
| `hyperframes-cli` | HyperFrames CLI tool — hyperframes init, lint, inspect, preview, render, transcribe, tts, doctor, browser, info, upgrade,... |
| `hyperframes-registry` | Install and wire registry blocks and components into HyperFrames compositions. Use when running hyperframes add, installing a block... |
| `imagegen` | Generate or edit raster images when the task benefits from AI-created bitmap visuals such as photos, illustrations, textures,... |
| `impeccable` | Use when the user wants to design, redesign, shape, critique, audit, polish, simplify, harden, animate, or otherwise improve a... |
| `inflection` | Auto-detect biggest acceleration/deceleration inflections across all metrics |
| `make-interfaces-feel-better` | Apply concrete design-engineering details that make interfaces feel polished. Use when reviewing or improving UI spacing,... |
| `math-olympiad` | Solve competition math problems (IMO, Putnam, USAMO, AIME) with adversarial verification that catches the errors self-verification... |
| `mixpanelyst` | This skill should be used when the user asks about Mixpanel product analytics, event data, funnel analysis, retention curves,... |
| `morning-briefing` | Generates a morning briefing that triages your inbox and previews your day using the Superhuman Mail MCP server — acting as an AI... |
| `nanoclaw-repl` | Operate and extend NanoClaw v2, ECC's zero-dependency session-aware REPL built on claude -p. |
| `ncc` | Expert guidance for @vercel/ncc — a simple CLI for compiling Node.js modules into a single file with all dependencies included. Use... |
| `nemoclaw-user-get-started` | Installs NemoClaw, launches a sandbox, and runs the first agent prompt. Use when onboarding, installing, or launching a NemoClaw... |
| `next-forge` | next-forge expert guidance — production-grade Turborepo monorepo SaaS starter by Vercel. Use when working in a next-forge project,... |
| `nextjs` | Next.js App Router expert guidance. Use when building, debugging, or architecting Next.js applications — routing, Server... |
| `nextjs-turbopack` | Next.js 16+ and Turbopack — incremental bundling, FS caching, dev speed, and when to use Turbopack vs webpack. |
| `omniverse-cad-to-simready` | Coordinate the end-to-end CAD/source-asset to SimReady workflow. Use for broad requests such as CAD to SimReady, source asset to... |
| `omniverse-realtime-viewer` | Use as the top-level router for Omniverse Realtime Viewer USD app requests and focused viewer reference documents. |
| `omniverse-usd-performance-tuning` | Top-level workflow skill for USD performance diagnosis and optimization. Use for slow loading, high memory, low FPS, or 'optimize... |
| `openclaw-persona-forge` | 为 OpenClaw AI Agent 锻造完整的龙虾灵魂方案。根据用户偏好或随机抽卡， 输出身份定位、灵魂描述(SOUL.md)、角色化底线规则、名字和头像生图提示词。 如当前环境提供已审核的生图 skill，可自动生成统一风格头像图片。... |
| `packaging-notarization` | Prepare macOS packaging and notarization workflows. Use when archiving apps, validating bundles, or explaining distribution-only... |
| `playground` | Creates interactive HTML playgrounds — self-contained single-file explorers that let users configure something visually through... |
| `probe-sdk` | Use when using Probe SDK. |
| `product-capability` | Translate PRD intent, roadmap asks, or product discussions into an implementation-ready capability plan that exposes constraints,... |
| `product-lens` | Use this skill to validate the "why" before building, run product diagnostics, and pressure-test product direction before the... |
| `project-artifact` | Generate and publish a project status artifact — an opinionated, tabbed status page for a project too big for one update (overview... |
| `project-guidelines-example` | これはプロジェクト固有のスキルの例です。自分のプロジェクトのテンプレートとして使用してください。 |
| `recursive-decision-ledger` | Use when the user asks for repeated rollouts, marked decision processes, high-dimensional search, stochastic optimization,... |
| `rivet-sdk` | Use when using Rivet SDK. |
| `santa-method` | Multi-agent adversarial verification with convergence loop. Two independent review agents must both pass before output ships. |
| `satori` | Expert guidance for Satori — Vercel's library that converts HTML and CSS to SVG, commonly used to generate dynamic OG images for... |
| `settings-precedence` | VS Code settings precedence rules and common pitfalls. Essential for any code that reads or writes settings. Covers... |
| `smart-file-renaming` | Smart File Renaming skill for Datasite deal rooms. Use this skill whenever a deal team wants to standardise document names, clean... |
| `swiftpm-macos` | Build, run, and test SwiftPM macOS packages and executables. Use when the repo is package-first or has no Xcode project. |
| `swr` | SWR data-fetching expert guidance. Use when building React apps with client-side data fetching, caching, revalidation, mutations,... |
| `tinystruct-patterns` | Expert guidance for developing with the tinystruct Java framework. Use when working on the tinystruct codebase or any project built... |
| `ucp` | Use when the user wants to use the UCP CLI to find, compare, buy, or track products from online merchants, or to set up and... |
| `uncloud` | Use when managing an Uncloud cluster — deploying services, configuring Caddy ingress, adding static proxy routes for non-cluster... |
| `use-dom` | Use Expo DOM components to run web code in a webview on native and as-is on web. Migrate web code to native incrementally. |
| `v0-dev` | v0 by Vercel expert guidance. Use when discussing AI code generation, generating UI components from prompts, v0 CLI usage, v0... |
| `vdr-index-setup` | VDR Index Setup skill for Datasite deal rooms. Use this skill whenever a user wants to create, propose, design, or set up a Virtual... |
| `vite-patterns` | Vite build tool patterns including config, plugins, HMR, env variables, proxy setup, SSR, library mode, dependency pre-bundling,... |
| `web-perf` | Analyzes web performance using Chrome DevTools MCP. Measures Core Web Vitals (FCP, LCP, TBT, CLS, Speed Index), identifies... |
| `website-to-hyperframes` | Capture a website and create a HyperFrames video from it. Use when: (1) a user provides a URL and wants a video, (2) someone says... |
| `window-management` | Customize macOS SwiftUI windows and scene behavior. Use when tuning window chrome, drag regions, placement, restoration, launch... |
| `workers-best-practices` | Reviews and authors Cloudflare Workers code against production best practices. Load when writing new Workers, reviewing Worker... |
| `x-api` | X/Twitter API integration for posting tweets, threads, reading timelines, search, and analytics. Covers OAuth auth patterns, rate... |
| `yeet` | Publish local changes to GitHub by confirming scope, committing intentionally, pushing the branch, and opening a draft PR through... |

### 4.27 Legacy, migration & cost — 11 skills

| Skill | Use when |
|---|---|
| `cost-tracking` | Track and report Claude Code token usage, spending, and budgets from the local ECC cost-tracker metrics log. Use when the user asks... |
| `cross-platform-paths` | Critical patterns for cross-platform path handling in this VS Code extension. Windows vs POSIX path bugs are the #1 source of... |
| `ecc-tools-cost-audit` | Evidence-first ECC Tools burn and billing audit workflow. Use when investigating runaway PR creation, quota bypass, premium-model... |
| `harvest-from-ecc` | Idempotent re-sync of agents, skills, and commands from the ECC repository into this project's .agents/ directory. Appends a line... |
| `inherit-legacy-style` | Legacy-project style inheritance skill. Use when the user types /inherit-legacy-style, or when onboarding an AI coding agent onto a... |
| `latency-critical-systems` | Use for latency-sensitive systems such as realtime dashboards, market data, streaming agents, execution gateways, queues, caches,... |
| `runtime-cache` | Vercel Runtime Cache API guidance — ephemeral per-region key-value cache with tag-based invalidation. Shared across Functions,... |
| `strategic-compact` | Suggests manual context compaction at logical intervals to preserve context through task phases rather than arbitrary auto-compaction. |
| `temporal-developer` | Develop, debug, and manage Temporal applications across Python, TypeScript, Go, and Java. Use when the user is building workflows,... |
| `view-refactor` | Refactor macOS SwiftUI views and scenes into stable structure. Use when splitting large views, tightening scene state, or narrowing... |
| `workspace-surface-audit` | Audit the active repo, MCP servers, plugins, connectors, env surfaces, and harness setup, then recommend the highest-value... |

### 4.28 Legal, compliance & policy — 3 skills

| Skill | Use when |
|---|---|
| `litigation-update-post` | Writes public-facing litigation updates — blog posts, client alerts, LinkedIn/X posts — on a federal case or legal development. Use... |
| `safety-guard` | Use this skill to prevent destructive operations when working on production systems or running agents autonomously. |
| `signing-entitlements` | Inspect macOS signing, entitlements, and Gatekeeper issues. Use when diagnosing code signing, sandbox, hardened runtime, or trust... |

### 4.29 Messaging, notifications & scheduling — 7 skills

| Skill | Use when |
|---|---|
| `dispatching-parallel-agents` | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies |
| `google-workspace-ops` | Operate across Google Drive, Docs, Sheets, and Slides as one workflow surface for plans, trackers, decks, and shared documents. Use... |
| `messages-ops` | Evidence-first live messaging workflow for ECC. Use when the user wants to read texts or DMs, recover a recent one-time code,... |
| `metric-pack-designer` | Design custom metric packs for plugin-eval so teams can add local evaluation rubrics that emit schema-compatible checks and... |
| `production-scheduling` | Codified expertise for production scheduling, job sequencing, line balancing, changeover optimization, and bottleneck resolution in... |
| `receipts` | Generate a personal Claude Code usage & impact report ("receipts") from this machine's local session transcripts — for justifying... |
| `unified-notifications-ops` | Operate notifications as one ECC-native workflow across GitHub, Linear, desktop alerts, hooks, and connected communication... |

### 4.30 Data sources, connectors & research corpus — 9 skills

| Skill | Use when |
|---|---|
| `citations` | Canonical rules and HTML/CSS contract for inline `[n]` citation references, end-of-document Citations blocks, and optional... |
| `hex` | Search Hex projects and ask Hex Threads questions. Use when the user explicitly references Hex, Hex projects, Hex dashboards, Hex... |
| `hf-cli` | Hugging Face Hub CLI (`hf`) for downloading, uploading, and managing repositories, models, datasets, and Spaces on the Hugging Face... |
| `ib-deck` | Generate an institutional-grade investment banking pitch deck (HTML) |
| `nutrient-document-processing` | Process, convert, OCR, extract, redact, sign, and fill documents using the Nutrient DWS API. Works with PDFs, DOCX, XLSX, PPTX,... |
| `replayio` | Use when you need to record or inspect an agent browser run in Replay, test a local app with the host agent browser using Replay... |
| `search-company-knowledge` | Search across company knowledge bases (Confluence, Jira, internal docs) to find and explain internal concepts, processes, and... |
| `videodb` | See, Understand, Act on video and audio. See- ingest from local files, URLs, RTSP/live feeds, or live record desktop; return... |
| `Zotero` | Use Zotero Desktop from Codex to enable/probe the local API, search a local Zotero library, list items/collections/tags, export... |

### 4.31 AI platform toolchains — 13 skills

| Skill | Use when |
|---|---|
| `agents-sdk` | Build AI agents on Cloudflare Workers using the Agents SDK. Load when creating stateful agents, durable workflows, real-time... |
| `agy-customizations` | Comprehensive guide and reference for the Antigravity Customization System. Use to explain how customizations work, their loading... |
| `antigravity-guide` | Provides a comprehensive guide, quick reference, and sitemap for Google Antigravity (AGY), including the Antigravity CLI (agy),... |
| `build-chatgpt-app` | Build, scaffold, refactor, and troubleshoot ChatGPT Apps SDK applications that combine an MCP server and widget UI. Use when Codex... |
| `build-mcpb` | This skill should be used when the user wants to "package an MCP server", "bundle an MCP", "make an MCPB", "ship a local MCP... |
| `chatgpt-app-submission` | Inspect a ChatGPT Apps MCP server codebase and generate chatgpt-app-submission.json with app info suggestions, tool hint... |
| `dynamo-interconnect-check` | Validate that a Dynamo deployment's NIXL/UCX/NCCL interconnect is ready for disaggregated serving over RDMA/NVLink. Use after... |
| `dynamo-router-starter` | Start or patch Dynamo router modes and run router endpoint smoke checks. Use for round-robin, KV-aware, least-loaded, or... |
| `example-command` | An example user-invoked skill that demonstrates frontmatter options and the skills/<name>/SKILL.md layout |
| `micro` | Expert guidance for micro — asynchronous HTTP microservices framework by Vercel. Use when building lightweight HTTP servers, API... |
| `ml-adoption-playbook` | End-to-end methodology for AI agents and software engineers to add machine learning algorithms to existing non-ML codebases. Covers... |
| `pytorch-patterns` | PyTorch deep learning patterns and best practices for building robust, efficient, and reproducible training pipelines, model... |
| `transformers-js` | Use Transformers.js to run state-of-the-art machine learning models directly in JavaScript/TypeScript. Supports NLP (text... |

### 4.32 Product, planning & team ops — 31 skills

| Skill | Use when |
|---|---|
| `accessibility` | Design, implement, and audit inclusive digital products using WCAG 2.2 Level AA standards. Use this skill to generate semantic ARIA... |
| `automation` | Interactive guide to design and create a scheduled background automation. Use this skill when the user wants to create an automated... |
| `automation-audit-ops` | Evidence-first automation inventory and overlap audit workflow for ECC. Use when the user wants to know which jobs, hooks,... |
| `backend-patterns` | Backend architecture patterns, API design, database optimization, and server-side best practices for Node.js, Express, and Next.js... |
| `bootstrap` | Project bootstrapping orchestrator for repos that depend on Vercel-linked resources (databases, auth, and managed integrations).... |
| `brainstorming` | You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior.... |
| `canary-watch` | Use this skill to monitor and verify a deployed URL after releases — checks HTTP endpoints, SSE streams, static assets, console... |
| `caveman-mode` | Forces all thinking and replies into blunt, stripped-down caveman speech. Use this skill for the ENTIRE conversation once invoked,... |
| `deployment-patterns` | Deployment workflows, CI/CD pipeline patterns, Docker containerization, health checks, rollback strategies, and production... |
| `document-builder` | Produce finished documents - Word (.docx), PowerPoint (.pptx), Excel (.xlsx), PDF, and markdown - with diagrams, charts, and other... |
| `document-quality-check` | Document Quality Check skill for Datasite deal rooms. Use this skill whenever a deal team wants to audit document quality before... |
| `documentation-lookup` | Use up-to-date library and framework docs via Context7 MCP instead of training data. Activates for setup questions, API references,... |
| `executing-plans` | Use when you have a written implementation plan to execute in a separate session with review checkpoints |
| `fa-jobs-to-be-done` | Use when the user asks for D&B Finance Analytics workflows such as customer onboarding, credit decisioning, credit limit... |
| `gh-address-comments` | Address actionable GitHub pull request review feedback. Use when the user wants to inspect unresolved review threads, requested... |
| `gh-fix-ci` | Use when a user asks to debug or fix failing GitHub PR checks that run in GitHub Actions. Use the GitHub app from this plugin for... |
| `github` | Triage and orient GitHub repository, pull request, and issue work through the connected GitHub app. Use when the user asks for... |
| `java-lsp-tools` | Compiler-accurate Java symbol navigation via the Java Language Server. Use lsp_java_findSymbol for Java identifiers and... |
| `nodejs-keccak256` | Prevent Ethereum hashing bugs in JavaScript and TypeScript. Node's sha3-256 is NIST SHA3, not Ethereum Keccak-256, and silently... |
| `nuxt4-patterns` | Nuxt 4 app patterns for hydration safety, performance, route rules, lazy loading, and SSR-safe data fetching with useFetch and... |
| `observability` | Vercel Observability expert guidance — Drains (logs, traces, speed insights, web analytics), Web Analytics, Speed Insights, runtime... |
| `reports-pdfs-and-slide-automation` | Lay out and export data-rich reports and documents. Use when the user needs report structure, figure packaging, PDFs, PowerPoint or... |
| `run-smoke-tests` | Run smoke tests to verify extension functionality in a real VS Code environment. Use this when checking if basic features work... |
| `setup` | Verify Daloopa MCP connection and show available skills |
| `team-builder` | Interactive agent picker for composing and dispatching parallel teams |
| `telemetry` | Add and verify lightweight macOS runtime telemetry. Use when wiring Logger events or inspecting logs for windows, sidebars, menus,... |
| `to-spec` | Turn the current conversation into a spec and publish it to the project issue tracker: no interview, just synthesis of what you've... |
| `to-tickets` | Break a plan, spec, or the current conversation into a set of tracer-bullet tickets, each declaring its blocking edges, published... |
| `turbopack` | Turbopack expert guidance. Use when configuring the Next.js bundler, optimizing HMR, debugging build issues, or understanding the... |
| `turborepo` | Turborepo expert guidance. Use when setting up or optimizing monorepo builds, configuring task caching, remote caching, parallel... |
| `writing-plans` | Use when you have a spec or requirements for a multi-step task, before touching code |

### 4.33 Industry verticals & trading — 17 skills

| Skill | Use when |
|---|---|
| `carrier-relationship-management` | Codified expertise for managing carrier portfolios, negotiating freight rates, tracking carrier performance, allocating freight,... |
| `comp-sheet` | Build an industry comp sheet Excel model with deep operational KPIs |
| `comps` | Trading comparables analysis with peer multiples and implied valuation |
| `cuopt-user-rules` | Base rules for end users calling NVIDIA cuOpt (routing/LP/MILP/QP/install/server). Not for cuOpt internals — use cuopt-developer... |
| `earnings-flash` | Rapid first-read earnings flash for a given company |
| `earnings-prep` | Pre-earnings preparation report for the night before a company reports |
| `earnings-review` | Full earnings analysis with guidance tracking for a given company |
| `energy-procurement` | Codified expertise for electricity and gas procurement, tariff optimization, demand charge management, renewable PPA evaluation,... |
| `evm-token-decimals` | Prevent silent decimal mismatch bugs across EVM chains. Covers runtime decimal lookup, chain-aware caching, bridged-token precision... |
| `healthcare-cdss-patterns` | Clinical Decision Support System (CDSS) development patterns. Drug interaction checking, dose validation, clinical scoring (NEWS2,... |
| `healthcare-emr-patterns` | EMR/EHR development patterns for healthcare applications. Clinical safety, encounter workflows, prescription generation, clinical... |
| `industry` | Cross-company industry comparison across multiple tickers |
| `irl-tracker` | Information Request List (IRL) Tracker skill for Datasite deal rooms. Use this skill whenever a deal team wants to compare VDR... |
| `ito-basket-compare` | Compare Itô prediction-market baskets against a user's knowledge base, portfolio notes, financial context, watchlist, or research... |
| `ito-trade-planner` | Build a non-advisory prediction-market trade planning worksheet for Itô or venue workflows. Use to inspect venues, underliers,... |
| `marketplace` | Vercel Marketplace expert guidance — discovering, installing, and building integrations, auto-provisioned environment variables,... |
| `payments` | Stripe payments integration guidance — native Vercel Marketplace setup, checkout sessions, webhook handling, subscription billing,... |

### 4.34 ECC meta-guides & fixtures — 4 skills

| Skill | Use when |
|---|---|
| `alpha` | Alpha fixture skill. Use when plugin-eval tests need one of two bundled skills. |
| `beta` | Beta fixture skill. Use when plugin-eval tests need the second bundled skill. |
| `configure-ecc` | Interactive installer for Everything Claude Code — guides users through selecting and installing skills and rules to user-level or... |
| `ecc-guide` | Guide users through ECC's current agents, skills, commands, hooks, rules, install profiles, and project onboarding by reading the... |

### 4.35 Discord channel — 2 skills

| Skill | Use when |
|---|---|
| `access` | Manage Discord channel access — approve pairings, edit allowlists, set DM/group policy. Use when the user asks to pair, approve... |
| `configure` | Set up the Discord channel — save the bot token and review access policy. Use when the user pastes a Discord bot token, asks to... |

### 4.36 App auth & content platforms — 2 skills

| Skill | Use when |
|---|---|
| `auth` | Authentication integration guidance — Clerk (native Vercel Marketplace), Descope, and Auth0 setup for Next.js applications. Covers... |
| `cms` | Headless CMS integration guidance — Sanity (native Vercel Marketplace), Contentful, DatoCMS, Storyblok, and Builder.io. Covers... |

### 4.37 macOS app development — 1 skill

| Skill | Use when |
|---|---|
| `build-run-debug` | Build, run, and debug macOS apps with shell-first Xcode and Swift workflows. Use when launching apps or diagnosing build, startup,... |

### 4.38 Lean code & minimalism — 6 skills

| Skill | Use when |
|---|---|
| `ponytail` | Lazy senior dev mode: the smallest change that fully solves the task, and a reply a busy human understands in one read. Use on any... |
| `ponytail-audit` | Quality audit of a whole repo: bugs, security holes, what breaks under real load, risky code without tests, slow paths, and what to... |
| `ponytail-debt` | List every `shortcut:` comment (and older `ponytail:` ones) as a debt ledger. One-shot report, changes nothing. Use for "ponytail... |
| `ponytail-gain` | Show ponytail's measured savings (code, cost, speed) from the benchmark. One-shot display. Use for /ponytail-gain, "what does... |
| `ponytail-help` | Quick reference for ponytail levels, skills and commands. One-shot display. Use for /ponytail-help, "ponytail help", "how do I use... |
| `ponytail-review` | Quality review of a change: is the logic right, is it safe, does it hold under real load, is risky code tested, is it fast enough,... |

### 4.39 Other / uncategorised — 12 skills

| Skill | Use when |
|---|---|
| `audio-separation` | Split audio into stems — vocals, drums, bass, other — with local open-source tools like Demucs and Spleeter, for remixing, sample... |
| `comfyui-image-workflows` | Build and run ComfyUI workflows for image generation and editing — SDXL, SD 1.5, Flux, ControlNet, IPAdapter, inpainting,... |
| `diagram-generation` | Generate technical and explanatory diagrams — flowcharts, sequence diagrams, architecture diagrams, ERDs, class diagrams and... |
| `lip-sync` | Sync mouth movement to audio in video using local open-source models — MuseTalk, LatentSync, Wav2Lip, and VideoRetalking — with... |
| `local-diffusion-suite` | Choose and run local open-source image generation tools — AUTOMATIC1111 WebUI, Forge, InvokeAI, Fooocus, Diffusers, and Flux — with... |
| `local-tts-engines` | Generate speech locally with open-source TTS engines — Piper, Coqui XTTS, Kokoro, Bark, VoxCPM, CosyVoice, Qwen3-TTS, Dia, ChatTTS,... |
| `long-to-short-repurpose` | Extract short-form clips from long-form video — detecting highlight moments, scoring for virality, generating vertical reframing... |
| `music-generation` | Generate music, sound effects, and ambient audio locally with open-source models — AudioCraft MusicGen and AudioGen, ACE-Step, YuE,... |
| `script-and-story-editing` | Edits scripts, storyboards, voiceover copy, and narrative structure — shaping a draft for a specific format and audience without... |
| `stock-media-sourcing` | Find and download royalty-free stock photos, video, and music for content production — Pexels, Pixabay, Unsplash, Wikimedia... |
| `thumbnail-generator` | Generate thumbnails for videos and articles that get clicked — local image generation for the base image, compositing text overlays... |
| `voice-cloning-rvc` | Clone and convert voices locally with open-source tools — GPT-SoVITS for zero-shot cloning, RVC for voice conversion with training,... |

## 5. Agent Catalogue by Function

All 115 agents. **Model** is the model the definition requests; **Tools** is its
allow-list. Read the agent file before invoking — each carries its own process.

### Security — 6 agents

Vulnerability detection, adversarial review, orchestrated scanning, release pipeline.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `claude-security` | The dedicated Claude Security orchestrator. Hand it an unattended job — "fully scan this repository and patch what you find; I understand it will use a... | inherit | Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion, Workflow, Workflow(claude-security:scan), TaskCreate, TaskGet, TaskList, TaskUpdate, TaskOutput, TaskStop, Agent(claude-security:scan-inventory, claude-security:scan-researcher, claude-security:scan-verifier, claude-security:scan-loader, claude-security:patch-generator, claude-security:patch-verifier, claude-security:explore) |
| `opensource-forker` | Fork any project for open-sourcing. Copies files, strips secrets and credentials (20+ patterns), replaces internal references with placeholders,... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `opensource-packager` | Generate complete open-source packaging for a sanitized project. Produces CLAUDE.md, setup.sh, README.md, LICENSE, CONTRIBUTING.md, and GitHub issue... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `opensource-sanitizer` | Verify an open-source fork is fully sanitized before release. Scans for leaked secrets, PII, internal references, and dangerous files using 20+ regex... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `security-auditor` | Adversarial security reviewer — OWASP Top 10, CWE, dependency CVEs, secrets, injection. Use for security debt scanning and pre-modernization hardening. | — | Read, Glob, Grep, Bash |
| `security-reviewer` | Security vulnerability detection and remediation specialist. Use PROACTIVELY after writing code that handles user input, authentication, API endpoints,... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |

### GAN harness (build a product) — 3 agents

A coordinated trio — plan -> generate -> evaluate. Run `gan-planner` first; see §6.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `gan-evaluator` | GAN Harness — Evaluator agent. Tests the live running application via Playwright, scores against rubric, and provides actionable feedback to the Generator. | opus | ["Read", "Write", "Bash", "Grep", "Glob"] |
| `gan-generator` | GAN Harness — Generator agent. Implements features according to the spec, reads evaluator feedback, and iterates until quality threshold is met. | opus | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `gan-planner` | GAN Harness — Planner agent. Expands a one-line prompt into a full product specification with features, sprints, evaluation criteria, and design direction. | opus | ["Read", "Write", "Grep", "Glob"] |

### Code cleanup & simplification — 2 agents

Reduce complexity and remove dead code without changing behaviour.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `code-simplifier` | Simplifies and refines code for clarity, consistency, and maintainability while preserving all functionality. Focuses on recently modified code unless... | opus | — |
| `refactor-cleaner` | Dead code cleanup and consolidation specialist. Use PROACTIVELY for removing unused code, duplicates, and refactoring. Runs analysis tools (knip,... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |

### Documentation — 2 agents

Keep docs and codemaps in step with the code.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `doc-updater` | Documentation and codemap specialist. Use PROACTIVELY for updating codemaps and documentation. Runs /update-codemaps and /update-docs, generates... | haiku | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `docs-lookup` | When the user asks how to use a library, framework, or API or needs up-to-date code examples, use Context7 MCP to fetch current documentation and... | sonnet | ["Read", "Grep", "mcp__context7__resolve-library-id", "mcp__context7__query-docs"] |

### Read-only Q&A — 1 agent

Answers questions about the codebase without changing anything.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `Ask` | Answers questions without making changes | — | ['search', 'read', 'web', 'vscode/memory', 'github/issue_read', 'github.vscode-pull-request-github/issue_fetch', 'github.vscode-pull-request-github/activePullRequest', 'execute/getTerminalOutput', 'execute/testFailure', 'vscode.mermaid-markdown-features/renderMermaidDiagram', 'vscode/askQuestions'] |

### Build & type-error resolvers — 12 agents

Fix compilation, dependency and type errors with minimal diffs. Explicitly forbidden from making architectural edits.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `build-error-resolver` | Build and TypeScript error resolution specialist. Use PROACTIVELY when build fails or type errors occur. Fixes build/type errors only with minimal... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `cpp-build-resolver` | C++ build, CMake, and compilation error resolution specialist. Fixes build errors, linker issues, and template errors with minimal changes. Use when... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `dart-build-resolver` | Dart/Flutter build, analysis, and dependency error resolution specialist. Fixes `dart analyze` errors, Flutter compilation failures, pub dependency... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `django-build-resolver` | Django/Python build, migration, and dependency error resolution specialist. Fixes pip/Poetry errors, migration conflicts, import errors, Django... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `go-build-resolver` | Go build, vet, and compilation error resolution specialist. Fixes build errors, go vet issues, and linter warnings with minimal changes. Use when Go... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `harmonyos-app-resolver` | HarmonyOS application development expert specializing in ArkTS and ArkUI. Reviews code for V2 state management compliance, Navigation routing patterns,... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `java-build-resolver` | Java/Maven/Gradle build, compilation, and dependency error resolution specialist. Automatically detects Spring Boot or Quarkus and applies... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `kotlin-build-resolver` | Kotlin/Gradle build, compilation, and dependency error resolution specialist. Fixes build errors, Kotlin compiler errors, and Gradle issues with... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `pytorch-build-resolver` | PyTorch runtime, CUDA, and training error resolution specialist. Fixes tensor shape mismatches, device errors, gradient issues, DataLoader problems,... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `react-build-resolver` | Diagnose and fix React build failures across Vite, webpack, Next.js, CRA, Parcel, esbuild, and Bun. Handles JSX/TSX compile errors, hydration... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `rust-build-resolver` | Rust build, compilation, and dependency error resolution specialist. Fixes cargo build errors, borrow checker issues, and Cargo.toml problems with... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `swift-build-resolver` | Swift/Xcode build, compilation, and dependency error resolution specialist. Fixes swift build errors, Xcode build failures, SPM dependency issues, and... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |

### Architecture & planning — 16 agents

Design, blueprint, critique and migrate.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `a11y-architect` | Accessibility Architect specializing in WCAG 2.2 compliance for Web and Native platforms. Use PROACTIVELY when designing UI components, establishing... | sonnet | ["Read", "Write", "Edit", "Grep", "Glob"] |
| `ai-architect` | Specializes in architecting AI-powered applications on Vercel — choosing between AI SDK patterns, configuring providers, building agents, setting up... | — | — |
| `architect` | Software architecture specialist for system design, scalability, and technical decision-making. Use PROACTIVELY when planning new features, refactoring... | opus | ["Read", "Grep", "Glob"] |
| `architecture-critic` | Reviews proposed target architectures and transformed code against modern best practice. Adversarial — looks for over-engineering, missed requirements,... | — | Read, Glob, Grep, Bash |
| `code-architect` | Designs feature architectures by analyzing existing codebase patterns and conventions, then providing comprehensive implementation blueprints with... | sonnet | Glob, Grep, LS, Read, NotebookRead, WebFetch, TodoWrite, WebSearch, KillShell, BashOutput |
| `code-explorer` | Deeply analyzes existing codebase features by tracing execution paths, mapping architecture layers, understanding patterns and abstractions, and... | sonnet | Glob, Grep, LS, Read, NotebookRead, WebFetch, TodoWrite, WebSearch, KillShell, BashOutput |
| `ecc-coordinator` | ECC pipeline coordinator. Runs the full Plan → Build(TDD) → Verify → Review → Commit workflow for a feature, delegating to planner, tdd-guide,... | — | — |
| `Explore` | Fast read-only codebase exploration and Q&A subagent. Prefer over manually chaining multiple search and file-reading operations to avoid cluttering the... | ['Claude Haiku 4.5 (copilot)', 'Gemini 3 Flash (Preview) (copilot)', 'Auto (copilot)'] | ['search', 'read', 'web', 'vscode/memory', 'github/issue_read', 'github.vscode-pull-request-github/issue_fetch', 'github.vscode-pull-request-github/activePullRequest', 'execute/getTerminalOutput', 'execute/testFailure'] |
| `homelab-architect` | Designs home and small-lab network plans from hardware inventory, goals, and operator experience level, with safe staged changes and rollback guidance. | sonnet | ["Read", "Grep"] |
| `legacy-analyst` | Deep-reads legacy codebases (COBOL, Java, .NET, Node, anything) to build structural and behavioral understanding. Use for discovery, dependency... | — | Read, Glob, Grep, Bash |
| `network-architect` | Designs enterprise or multi-site network architecture from requirements, using existing network skills for focused routing, validation, automation, and... | sonnet | ["Read", "Grep"] |
| `Plan` | Researches and outlines multi-step plans | — | ['search', 'read', 'web', 'vscode/memory', 'github/issue_read', 'github.vscode-pull-request-github/issue_fetch', 'github.vscode-pull-request-github/activePullRequest', 'execute/getTerminalOutput', 'execute/testFailure', 'vscode/askQuestions', 'agent'] |
| `planner` | Expert planning specialist for complex features and refactoring. Use PROACTIVELY when users request feature implementation, architectural changes, or... | opus | ["Read", "Grep", "Glob"] |
| `scaffolder` | Scaffolds one service of a reimagined system from the approved architecture and spec — project skeleton, domain model, API stubs, executable acceptance... | — | Read, Glob, Grep, Write, Edit, Bash |
| `uplift-migrator` | Migrates ONE project/module of an in-flight same-stack version uplift by applying a proven pilot playbook — minimal diff, then runs that unit's real... | — | Read, Glob, Grep, Write, Edit, Bash |
| `version-delta-analyst` | Identifies the breaking changes between two versions of the SAME stack (e.g. .NET Framework 4.8 → .NET 8, Java 8 → 17/21, Spring Boot 2 → 3) that... | — | Read, Glob, Grep, Bash |

### Research, scoring & outreach — 5 agents

Prospect discovery, enrichment, mutual-connection mapping, personalised outreach.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `enrichment-agent` | Pulls detailed profile, company, and activity data for qualified leads. Enriches prospects with recent news, funding data, content interests, and... | sonnet | - Bash |
| `marketing-agent` | Marketing strategist and copywriter for campaign planning, audience research, positioning, copy creation, and content review. Covers landing pages,... | sonnet | ["Read", "Grep", "Glob", "WebSearch", "WebFetch"] |
| `mutual-mapper` | Maps the user's social graph (X following, LinkedIn connections) against scored prospects to find mutual connections and rank them by introduction... | sonnet | - Bash |
| `outreach-drafter` | Generates personalized outreach messages for qualified leads. Creates warm intro requests, cold emails, X DMs, and follow-up sequences using enriched... | sonnet | - Read |
| `signal-scorer` | Searches and ranks prospects by relevance signals across X, Exa, and LinkedIn. Assigns weighted scores based on role, industry, activity, influence,... | sonnet | - Bash |

### Quality, cleanup & documentation — 20 agents

Review, scoring, cleanup, docs, and the guardrails around autonomous work.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `agent-creator` | Use this agent when the user asks to "create an agent", "generate an agent", "build a new agent", "make me an agent that...", or describes agent... | sonnet | ["Write", "Read"] |
| `agent-evaluator` | Evaluates agent output against 5-axis quality rubric (accuracy, completeness, clarity, actionability, conciseness). Use after any non-trivial task when... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `agent-sdk-verifier-py` | Use this agent to verify that a Python Agent SDK application is properly configured, follows SDK best practices and documentation recommendations, and... | sonnet | — |
| `agent-sdk-verifier-ts` | Use this agent to verify that a TypeScript Agent SDK application is properly configured, follows SDK best practices and documentation recommendations,... | sonnet | — |
| `business-rules-extractor` | Mines domain logic, calculations, validations, and policies from legacy code into testable Given/When/Then specifications. Use when you need to... | — | Read, Glob, Grep, Bash |
| `code-reviewer` | Reviews code for bugs, logic errors, security vulnerabilities, code quality issues, and adherence to project conventions, using confidence-based... | sonnet | Glob, Grep, LS, Read, NotebookRead, WebFetch, TodoWrite, WebSearch, KillShell, BashOutput |
| `comment-analyzer` | Use this agent when you need to analyze code comments for accuracy, completeness, and long-term maintainability. This includes (1) after generating... | inherit | — |
| `conversation-analyzer` | Use this agent when analyzing conversation transcripts to find behaviors worth preventing with hooks. Typical triggers include the /hookify command... | inherit | ["Read", "Grep"] |
| `e2e-runner` | End-to-end testing specialist using Vercel Agent Browser (preferred) with Playwright fallback. Use PROACTIVELY for generating, maintaining, and running... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `harness-optimizer` | Analyze and improve the local agent harness configuration for reliability, cost, and throughput. | sonnet | ["Read", "Grep", "Glob", "Bash", "Edit"] |
| `loop-operator` | Operate autonomous agent loops, monitor progress, and intervene safely when loops stall. | sonnet | ["Read", "Grep", "Glob", "Bash", "Edit"] |
| `observer` | Background agent that analyzes session observations to detect patterns and create instincts. Uses Haiku for cost-efficiency. v2.1 adds project-scoped... | haiku | — |
| `plugin-validator` | Use this agent when the user asks to "validate my plugin", "check plugin structure", "verify plugin is correct", "validate plugin.json", "check plugin... | inherit | ["Read", "Grep", "Glob", "Bash"] |
| `pr-test-analyzer` | Use this agent when you need to review a pull request for test coverage quality and completeness. This agent should be invoked after a PR is created or... | inherit | — |
| `silent-failure-hunter` | Use this agent when reviewing code changes in a pull request to identify silent failures, inadequate error handling, and inappropriate fallback... | inherit | — |
| `skill-reviewer` | Use this agent when the user has created or modified a skill and needs quality review, asks to "review my skill", "check skill quality", "improve skill... | inherit | ["Read", "Grep", "Glob"] |
| `spec-miner` | Extracts behavioral specs from existing codebases for OpenSpec. Produces flat Requirement and Invariant blocks with structured metadata (entities,... | opus | ["Read", "Grep", "Glob", "Bash", "Write"] |
| `tdd-guide` | Test-Driven Development specialist enforcing write-tests-first methodology. Use PROACTIVELY when writing new features, fixing bugs, or refactoring... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep"] |
| `test-engineer` | Writes characterization, contract, and equivalence tests that pin down legacy behavior so transformation can be proven correct. Use before any rewrite. | — | Read, Write, Edit, Glob, Grep, Bash |
| `type-design-analyzer` | Use this agent when you need expert analysis of type design in your codebase. Specifically use it (1) when introducing a new type to ensure it follows... | inherit | — |

### Domain specialists — 19 agents

Vertical expertise: databases, performance, clinical safety, ML systems, SEO, marketing, networks, deployments, design parity.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `chief-of-staff` | Personal communication chief of staff that triages email, Slack, LINE, and Messenger. Classifies messages into 4 tiers... | opus | ["Read", "Grep", "Glob", "Bash", "Edit", "Write"] |
| `ctf-flag-finder` | CTF (Capture The Flag) challenge solver optimized for finding hidden flags. Use PROACTIVELY whenever the user mentions CTF, capture the flag, a CTF... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebFetch"] |
| `database-reviewer` | PostgreSQL database specialist for query optimization, schema design, security, and performance. Use PROACTIVELY when writing SQL, creating migrations,... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `debug` | An expert Java debugging assistant that uses hypothesis-driven debugging to find root causes systematically | — | ['execute/getTerminalOutput', 'execute/runInTerminal', 'read/problems', 'read/readFile', 'read/terminalLastCommand', 'search', 'vscjava.vscode-java-debug/debugJavaApplication', 'vscjava.vscode-java-debug/setJavaBreakpoint', 'vscjava.vscode-java-debug/debugStepOperation', 'vscjava.vscode-java-debug/getDebugVariables', 'vscjava.vscode-java-debug/getDebugStackTrace', 'vscjava.vscode-java-debug/evaluateDebugExpression', 'vscjava.vscode-java-debug/getDebugThreads', 'vscjava.vscode-java-debug/removeJavaBreakpoints', 'vscjava.vscode-java-debug/stopDebugSession', 'vscjava.vscode-java-debug/getDebugSessionInfo'] |
| `deployment-expert` | Specializes in Vercel deployment strategies, CI/CD pipelines, preview URLs, production promotions, rollbacks, environment variables, and domain... | — | — |
| `design-parity-review-agent` | You are the Design Parity Review Agent for this plugin. | — | — |
| `design-system-rules-agent` | You are the Design System Rules Agent for the Figma plugin. | — | — |
| `figma-code-connect-agent` | You are the Figma Code Connect Agent for this plugin. | — | — |
| `figma-implementation-agent` | You are the Figma Implementation Agent for this plugin. | — | — |
| `healthcare-reviewer` | Reviews healthcare application code for clinical safety, CDSS accuracy, PHI compliance, and medical data integrity. Specialized for EMR/EHR, clinical... | opus | ["Read", "Grep", "Glob"] |
| `maintainer` | Project maintainer for vscode-python-environments. Drives planning from codebase snapshots and open issues, implements TypeScript/Node.js changes,... | — | [ |
| `mle-reviewer` | Production machine-learning engineering reviewer for data contracts, feature pipelines, training reproducibility, offline/online evaluation, model... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `network-config-reviewer` | Reviews router and switch configurations for security, correctness, stale references, risky change-window commands, and missing operational guardrails. | sonnet | ["Read", "Grep"] |
| `network-troubleshooter` | Diagnoses network connectivity, routing, DNS, interface, and policy symptoms with a read-only OSI-layer workflow and evidence-backed root cause summary. | sonnet | ["Read", "Bash", "Grep"] |
| `performance-optimizer` | Performance analysis and optimization specialist. Use PROACTIVELY for identifying bottlenecks, optimizing slow code, reducing bundle sizes, and... | sonnet | ["Read", "Write", "Edit", "Bash", "Grep", "Glob"] |
| `reviewer` | Deep code reviewer for vscode-python-environments. Catches cross-platform bugs, terminal activation issues, settings precedence problems, environment... | — | [ |
| `seo-specialist` | SEO specialist for technical SEO audits, on-page optimization, structured data, Core Web Vitals, and content/keyword mapping. Use for site audits, meta... | sonnet | ["Read", "Grep", "Glob", "WebSearch", "WebFetch"] |
| `zoom-integration-reviewer` | You are the Zoom Integration Reviewer for this plugin. | — | — |
| `zoom-oauth-scope-auditor` | You are the Zoom OAuth Scope Auditor for this plugin. | — | — |

### Code reviewers — 16 agents

Each covers its language's idioms, security and performance. Most state *"MUST BE USED for <language> projects"* — run them on every change in that stack.

| Agent | Role | Model | Tools |
|---|---|---|---|
| `cpp-reviewer` | Expert C++ code reviewer specializing in memory safety, modern C++ idioms, concurrency, and performance. Use for all C++ code changes. MUST BE USED for... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `csharp-reviewer` | Expert C# code reviewer specializing in .NET conventions, async patterns, security, nullable reference types, and performance. Use for all C# code... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `django-reviewer` | Expert Django code reviewer specializing in ORM correctness, DRF patterns, migration safety, security misconfigurations, and production-grade Django... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `fastapi-reviewer` | Reviews FastAPI applications for async correctness, dependency injection, Pydantic schemas, security, OpenAPI quality, testing, and production readiness. | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `flutter-reviewer` | Flutter and Dart code reviewer. Reviews Flutter code for widget best practices, state management patterns, Dart idioms, performance pitfalls,... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `fsharp-reviewer` | Expert F# code reviewer specializing in functional idioms, type safety, pattern matching, computation expressions, and performance. Use for all F# code... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `go-reviewer` | Expert Go code reviewer specializing in idiomatic Go, concurrency patterns, error handling, and performance. Use for all Go code changes. MUST BE USED... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `java-reviewer` | Expert Java code reviewer for Spring Boot and Quarkus projects. Automatically detects the framework and applies the appropriate review rules. Covers... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `kotlin-reviewer` | Kotlin and Android/KMP code reviewer. Reviews Kotlin code for idiomatic patterns, coroutine safety, Compose best practices, clean architecture... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `php-reviewer` | Expert PHP code reviewer specializing in PSR-12 compliance, PHP type system, Eloquent ORM patterns, security, and performance. Use for all PHP code... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `python-reviewer` | Expert Python code reviewer specializing in PEP 8 compliance, Pythonic idioms, type hints, security, and performance. Use for all Python code changes.... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `react-reviewer` | Expert React/JSX code reviewer specializing in hook correctness, render performance, server/client component boundaries, accessibility, and... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `rust-reviewer` | Expert Rust code reviewer specializing in ownership, lifetimes, error handling, unsafe usage, and idiomatic patterns. Use for all Rust code changes.... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `swift-reviewer` | Expert Swift code reviewer specializing in protocol-oriented design, value semantics, ARC memory management, Swift Concurrency, and idiomatic patterns.... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `typescript-reviewer` | Expert TypeScript/JavaScript code reviewer specializing in type safety, async correctness, Node/web security, and idiomatic patterns. Use for all... | sonnet | ["Read", "Grep", "Glob", "Bash"] |
| `vue-reviewer` | Expert Vue.js code reviewer specializing in Composition API correctness, reactivity pitfalls, component architecture, template security, and... | sonnet | ["Read", "Grep", "Glob", "Bash"] |

### Other — 13 agents

| Agent | Role | Model |
|---|---|---|
| `cinematic-video-editor` | Video editor for narrative and cinematic work — assembly, pacing, transitions, colour grading, sound design, and final delivery. Use for story edits,... | sonnet |
| `comfyui-workflow-builder` | ComfyUI workflow builder — constructing graph JSON for image and video generation, wiring checkpoints, samplers, ControlNet, IP-Adapter, LoRAs, VAEs,... | sonnet |
| `dependency-lockfile-custodian` | Adds, upgrades, or removes a dependency the way the ecosystem expects — edits package.json, pyproject.toml, Cargo.toml, or go.mod and regenerates... | sonnet |
| `image-art-director` | Image art director for generating and refining AI images — prompt construction, model and checkpoint selection, style consistency across a set,... | sonnet |
| `lip-sync-technician` | Lip-sync technician for driving mouth movement from a replacement audio track — MuseTalk, LatentSync, Wav2Lip, VideoRetalking, and SadTalker, with... | sonnet |
| `media-pipeline-engineer` | Media pipeline engineer — building reproducible ffmpeg-based pipelines that ingest, transcode, normalise, caption, and deliver video and audio for... | sonnet |
| `script-and-story-editor` | Script and story editor — shaping a script for voiceover, tightening a long piece into a short, building narrative structure, writing hooks and titles,... | sonnet |
| `seo-content-strategist` | SEO content strategist — keyword research and mapping, content briefs, topical clustering, on-page optimisation, internal linking, and content refresh... | sonnet |
| `short-form-producer` | Short-form video producer for vertical clips — finding the hook, writing the script, cutting the footage, reframing to 9:16, adding captions, and... | sonnet |
| `social-publish-manager` | Social publish manager — building a content calendar, adapting one idea per platform, writing platform-native copy and hashtag sets, tagging links with... | sonnet |
| `stock-media-researcher` | Stock media researcher — sourcing royalty-free photos, video, and music from Pexels, Unsplash, Wikimedia Commons, Internet Archive, and Pixabay, with... | sonnet |
| `thumbnail-designer` | Thumbnail designer — generating, compositing, and testing thumbnails for video, articles, and social posts, with legible typography, contrast testing,... | sonnet |
| `voice-and-sound-designer` | Voice and sound designer — selecting a TTS engine, writing for the ear, cloning and converting voices, designing a soundscape with generated music and... | sonnet |

### Held aside — 14 pipeline-internal agents

These are **dispatch targets, not tools**. Each is invoked by an orchestrating agent and
expects parameters only that parent supplies. Invoking one directly will fail.

| Agent | Dispatched by | Why not standalone |
|---|---|---|
| `report_researcher` | Gemini Antigravity | hidden background sub-agent |
| `documentation-writer` | VS Code Python extension | extension-internal agent |
| `explore` | claude-security | dispatched by researcher/verifier/patch agents |
| `patch-generator` | claude-security | fix job — dispatched by the fix job |
| `patch-verifier` | claude-security | fix job — dispatched by the fix job |
| `scan-inventory` | claude-security | scan pipeline — dispatched by the scan job |
| `scan-loader` | claude-security | scan pipeline — dispatched by the scan job |
| `scan-researcher` | claude-security | scan pipeline — dispatched by the scan job |
| `scan-verifier` | claude-security | scan pipeline — dispatched by the scan job |
| `logs-reader` | osmo-cli | spawned by the main OSMO agent |
| `workflow-expert` | osmo-cli | spawned by the main OSMO agent |
| `analyzer` | skill-creator-plus | eval loop — internal post-hoc analyzer |
| `comparator` | skill-creator-plus | eval loop — internal blind comparator |
| `grader` | skill-creator-plus | eval loop — internal grader |

Full detail in `agents/_agent-specific/README.md`.

## 6. Ensemble & Workflow Patterns

Some agents are meant to run as a sequence, not in isolation.

### The GAN harness — build a product from one line

```
gan-planner  -> expands the prompt into a product spec (features, sprints, criteria)
gan-generator -> implements against the spec, reads feedback, iterates
gan-evaluator -> tests the live app via Playwright, scores against the rubric
                 ^                                          |
                 +------------------------------------------+
```

All three run on **opus**. Invoke `gan-planner` first with the one-line prompt.

### The ECC pipeline — feature from idea to commit

```
planner -> tdd-guide -> code-reviewer -> security-reviewer -> commit
```

`ecc-coordinator` runs this whole sequence. Use it when the user asks for "the ECC pipeline"
or `/ecc`.

### The claude-security pipeline — scan then fix

```
claude-security (orchestrator)
  ├─ scan-inventory  -> scan-loader -> scan-researcher -> scan-verifier   (read-only)
  └─ patch-generator  -> patch-verifier                                  (write)
```

The scan phase is read-only; the patch phase writes. Invoke `claude-security` with the repo
root and let it drive. See `agents/_agent-specific/README.md`.

### The open-source pipeline — ship a repo publicly

```
opensource-forker    -> copies files, strips secrets, replaces internal refs, cleans history
opensource-sanitizer -> verifies no leaks remain (PASS / FAIL / PASS-WITH-WARNINGS)
opensource-packager  -> CLAUDE.md, setup.sh, README, LICENSE, CONTRIBUTING, issue templates
```

Run in order. `opensource-sanitizer` is the gate — it must pass before packaging.

### The skill-creator-plus evaluation loop

```
comparator -> blind A/B judgement (does not know which skill produced which)
analyzer   -> unblids the result, explains why the winner won
grader     -> scores against the expectations
```

Driven by `scripts/run_loop.py` inside the `skill-creator-plus` pack. Use it when you want
to know whether a change to a skill actually made it better.

### Agent creation loop

```
agent-creator -> generate the agent config
agent-evaluator -> score the output on accuracy, completeness, clarity, actionability, conciseness
skill-reviewer / plugin-validator -> check structure
```

## 7. The Standalone Packs

7 hand-authored packs live at the top level of this folder. They are **not** generated
marketplace content — each has reference files and an enforced workflow, and they are the
highest-quality material in the library.

| Pack | Path | What it does | Why it is better than the marketplace equivalent |
|---|---|---|---|
| `caveman-mode` | `caveman-mode/` | Forces all thinking and replies into blunt, stripped-down caveman speech for the entire conversation. Short words, broken grammar, no filler or hedging -- while keeping technical accuracy, code, numbers and file paths 100% exact. | No equivalent exists. Style override, not a workflow. |
| `document-builder` | `document-builder/` | Three-layer pipeline (SPECIFY -> BUILD -> VERIFY) for producing finished `.docx` / `.pptx` / `.xlsx` / PDF / markdown deliverables with diagrams and charts. Mandatory spec interview, strict source fidelity (no invented facts), drift control across long documents, sanity-check pass before delivery. Bundles its own vendored docx/pptx/xlsx/pdf/frontend-design skills under `vendor/` so it works standalone. | The marketplace `artifact-template-*` skills give you a template; this gives you a *process* with a mandatory verification pass. |
| `humanizer` | `humanizer/` | Rewrites text so it reads as genuinely human rather than AI. Built on Wikipedia *Signs of AI Writing* plus community-compiled word-frequency and structural pattern lists. Ships `references/banned-words.md` (exhaustive word/phrase ban list) and `references/pattern-details.md` (structural, grammatical and tonal patterns with severity ratings). | No equivalent. Ships `banned-words.md` + `pattern-details.md`. |
| `latex-doctor` | `latex-doctor/` | Diagnoses, fixes and writes LaTeX for any IDE or engine (Overleaf, TeXstudio, VS Code + LaTeX Workshop, Vim/Emacs, pdflatex/xelatex/lualatex). Covers compilation errors, missing packages, font issues, BibTeX/BibLaTeX, cross-references, overfull/underfull hbox, float placement, table formatting, math typesetting, and any document class (article, report, book, memoir, thesis). Reference files: `errors.md`, `packages.md`, `bibliography.md`, `math-and-symbols.md`. | The only LaTeX skill in the library, and it is comprehensive. |
| `research-partner` | `research-partner/` | Rigorous academic research support: a mandatory intake interview before any deliverable, a written scope contract requiring explicit approval, structured literature reviews, taxonomy construction, constructive critique of papers, multi-stance deep dives, and comparison tables. Enforces evidence discipline -- never states an unverified finding, labels provenance (`[from the uploaded PDF]`, `[recalled -- worth verifying]`, `[my inference]`), never invents a citation. | The marketplace `deep-research` skill has no intake contract and no provenance labelling. |
| `skill-creator-plus` | `skill-creator-plus/` | Skill authoring with a built-in evaluation harness. Ships 3 sub-agents (`analyzer.md`, `comparator.md`, `grader.md`), an HTML eval-review viewer under `assets/eval_review.html`, and scripts for the improvement loop (`run_loop.py`), description optimisation (`improve_description.py`) and packaging (`package_skill.py`). Reference files: `schemas.md`, `environments.md`, `authoring-checklist.md`, `description-optimization.md`. | `skill-creator` in the library is a barebones generator with no eval loop. |
| `skill-library-adder` | `skill-library-adder/` | The end-to-end procedure for adding an entry to this library: where a skill directory or an agent file must live so the scanner picks it up, the frontmatter each kind needs, the agent-detection rules (the >= 200-character rule, the `AGENT_SUFFIX` list and the marker keys), how to register an own pack so it is credited as this repository's work, how to route the new entry through the task table and the domain table so search finds it, and the publish sequence -- provenance, licence gate, credits, leak gate. Ships `scripts/add_entry.py`, which performs the mechanical part: it scaffolds the directory, writes a valid `SKILL.md` or agent frontmatter, and reports what still has to be done by hand. | The library has ~1000 skills and ~100 agents, and every one of them had to be placed by hand against a scanner with several non-obvious rules. This is the procedure that made each addition a one-step task instead of a rebuild-and-guess cycle. |

> `humanizer` and `skill-creator-plus` also appear under `skills/` as part of the uniform
> library. The top-level copies are the curated originals — prefer them.

### Upstream collections

Unlike the packs above, these are **third-party clones kept whole** — their own `LICENSE`
and their own git history — rather than material written for this library. Their skills are
picked up by the ordinary scanner and appear in `skills/` like everything else.

| Collection | Path | Upstream | Licence | What it does |
|---|---|---|---|---|
| `ponytail` | `ponytail/` | https://github.com/dietrichgebert/ponytail | MIT | "Lazy senior dev" mode — the 7-rung ladder (does it need to exist → already in this codebase → standard library → native platform feature → installed dependency → can it be one line → otherwise the minimum that works), plus one small test for any non-trivial logic. Never cuts trust-boundary validation, data-loss error handling, security, accessibility or hardware calibration. |

Ponytail ships 6 skills: `ponytail` (the behaviour mode, with `lite`/`full`/`ultra` levels),
`ponytail-review` (per-change quality review), `ponytail-audit` (repo-wide quality audit),
`ponytail-debt` (harvests `shortcut:` comments into a debt ledger), `ponytail-gain` (a
measured-impact scoreboard) and `ponytail-help` (a quick reference card). They pair with the
review agents in §5 rather than replacing them: let `ponytail-review` find the issues, then
let the language-specific reviewer judge them.

> `ponytail/AGENTS.md` is the same behaviour as the `ponytail` skill, in the compact
> rules-file form the repo ships for hosts that read project instructions instead of
> skills. It stays in the clone — the library imports skills, not rules files.

## 8. Quick Reference Card

The ~30 picks that cover most real requests. Reach for these first, then use §2 or §4 to
go deeper.

| If the task is... | Use this |
|---|---|
| writing or changing code in any language | the stack's reviewer agent (§3) + `skills/coding-standards/` skill |
| reviewing a diff | `agents/code-reviewer.md` |
| a build is broken | the stack's build resolver (§3) |
| planning a non-trivial feature | `agents/planner.md` + `skills/writing-plans/` skill |
| designing a system | `agents/architect.md` + `skills/architecture-decision-records/` skill |
| writing tests | `agents/tdd-guide.md` + `skills/tdd-workflow/` skill |
| a security review | `agents/security-reviewer.md` + `skills/security-review/` skill |
| removing dead code | `agents/refactor-cleaner.md` |
| the change is over-engineered | `skills/ponytail/` skill |
| performance is the problem | `agents/performance-optimizer.md` |
| a document, deck or report | `document-builder/` pack |
| academic research | `research-partner/` pack |
| LaTeX will not compile | `latex-doctor/` pack |
| text sounds like AI | `humanizer/` pack |
| a database or SQL | `agents/database-reviewer.md` + `skills/postgres-patterns/` skill |
| deploying | `agents/deployment-expert.md` + `skills/deployment-patterns/` skill |
| an LLM feature | `agents/ai-architect.md` + `skills/ai-first-engineering/` skill |
| a prompt is underperforming | `skills/prompt-optimizer/` skill |
| an autonomous loop is stalling | `agents/loop-operator.md` |
| building an agent | `agents/agent-creator.md` + `skills/agent-development/` skill |
| building a skill | `skill-creator-plus/` pack |
| opening a repo publicly | `agents/opensource-forker.md` -> `agents/opensource-sanitizer.md` -> `agents/opensource-packager.md` |
| building a UI | `skills/frontend-patterns/` skill + `agents/a11y-architect.md` |
| email, Slack or Teams triage | `agents/chief-of-staff.md` |
| a marketing or launch task | `agents/marketing-agent.md` + `skills/marketing-campaign/` skill |
| lead generation | `agents/signal-scorer.md` -> `agents/enrichment-agent.md` -> `agents/mutual-mapper.md` -> `agents/outreach-drafter.md` |
| reading an unfamiliar codebase | `agents/code-explorer.md` + `skills/codebase-onboarding/` skill |
| a modernising migration | `agents/legacy-analyst.md` -> `agents/business-rules-extractor.md` -> `agents/test-engineer.md` -> `agents/uplift-migrator.md` |
| browser automation | `skills/agent-browser/` skill |
| network troubleshooting | `agents/network-troubleshooter.md` |
| bioinformatics data | `skills/ngs-analysis-router/` skill |

---

*Generated by `.build_guide.py` from `.library_data.json`. Rebuild with*
*`python3 .build_library.py && python3 .build_guide.py`.*
