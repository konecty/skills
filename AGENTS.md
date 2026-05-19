# AGENTS.md

Guidance for AI coding agents working in this repository.

## Spec-Driven Development (SDD) — mandatory

This repo follows **Spec-Driven Development** via the [`tlc-spec-driven`](.agents/skills/tlc-spec-driven/SKILL.md) skill. Every non-trivial change must go through the SDD pipeline before any code or file is created.

### Pipeline

```
SPECIFY → DESIGN → TASKS → EXECUTE
required   opt*    opt*    required
* auto-skipped when scope doesn't need it
```

| Scope | Rule |
|-------|------|
| **Small** — ≤3 files, one-sentence scope | Quick Mode: describe → implement → verify → commit |
| **Medium** — clear feature, <10 tasks | Specify (brief) → Execute |
| **Large / Complex** | Full Specify → Design → Tasks → Execute |

### Specs directory

All specs live in `.specs/` (never inside `skills/` or `docs/`):

```
.specs/
├── project/
│   ├── PROJECT.md      # vision & goals for this repo
│   ├── ROADMAP.md      # planned skills and milestones
│   └── STATE.md        # decisions, blockers, deferred ideas
├── codebase/           # brownfield analysis (created once, kept updated)
└── features/
    └── <feature>/
        ├── spec.md     # requirements with traceable IDs
        ├── design.md   # architecture (Large/Complex only)
        └── tasks.md    # atomic tasks with verification (Large/Complex only)
```

### Rules

- **Never implement without a spec** for Medium/Large/Complex scope — write `spec.md` first.
- Quick Mode is the only exception: bug fixes, config tweaks, single-file changes.
- Each task in `tasks.md` maps to **one atomic commit**; commit message must reference the task ID.
- If execution reveals >5 steps that weren't in the task plan, stop and update `tasks.md` before continuing.
- Keep `STATE.md` updated with every session: decisions made, blockers found, deferred ideas.

## Workflow

- When creating or improving a skill, follow the **skill-creator** workflow: Draft → Test → Review → Iterate → Optimize → Package. The full workflow is at `.agents/skills/skill-creator/SKILL.md`.
- Never mark a task complete without verifying the skill works end-to-end (credentials present, script runs, output is correct).
- If something is ambiguous (module name, field name, API shape), use `konecty-modules` or `konecty-meta-read` to discover before guessing.

## Repository

**KonectySkills** is a monorepo of [Agent Skills](https://agentskills.io) that give AI agents the ability to interact with the Konecty low-code platform. There is no build step — each skill is a folder with a `SKILL.md` and optional Python scripts (stdlib only, no external dependencies).

```
skills/              # Konecty platform skills (one folder per skill)
.agents/skills/      # External skills installed via CLI (tracked in skills-lock.json)
.specs/              # SDD specs: project, codebase analysis, feature specs
template/            # SKILL.md template for new skills
spec/                # Agent Skills standard reference
docs/adr/            # Architecture Decision Records
docs/changelog/      # Per-change changelog entries
```

## Publishing to Marketplaces

### GitHub CLI (gh skill) — validates against agentskills.io spec
```bash
gh skill publish --dry-run   # validate without publishing
gh skill publish --fix       # auto-fix metadata issues and publish
gh skill search <query>      # discover skills on GitHub
```

### skills.sh — telemetry-based discovery (no explicit publish command)
```bash
npm i -g @agentskill.sh/cli
npx skills init my-skill     # scaffold from template
npx skills add owner/repo    # install from GitHub
npx skills list              # list installed skills
```
Skills appear on skills.sh organically as people install them. To "publish": push a public GitHub repo with a valid `SKILL.md` and share the install command.

### OpenClaw (clawhub) — explicit publish command
```bash
npm i -g clawhub
clawhub login
clawhub skill publish ./skills/<skill-name> \
  --slug konecty-<skill-name> \
  --version 1.0.0 \
  --changelog "Initial release"
clawhub skill publish ./skills/<skill-name> \
  --slug konecty-<skill-name> \
  --version 1.1.0 \
  --changelog "What changed"
```
ClawHub runs VirusTotal scans on every publish. Declared env vars and binaries must match exactly what the code uses.

### Hermes (NousResearch) — tap-based, no central registry
```bash
hermes skills publish skills/<skill-name> --to github --repo owner/repo
# Others install via:
hermes skills tap add owner/repo
hermes skills install <skill-id>
```

### Anthropic/skills and tech-leads-club — PR-based (curated)
Both registries require a pull request. Fork the repo, add your skill folder, open a PR. CI handles validation and release.

## Security Audits

Run before publishing to any marketplace.

```bash
# Snyk Agent Scan — detects prompt injection, credential issues, malicious payloads
export SNYK_TOKEN=<token>           # from app.snyk.io/account
uvx snyk-agent-scan@latest --skills                    # scan all skills
uvx snyk-agent-scan@latest ./skills/<skill-name>       # scan one skill

# Socket — supply chain security (npm dependencies inside scripts)
npm i -g @socketsecurity/cli
socket login
socket scan create ./skills/<skill-name>
socket ci                                              # CI mode: fails if unhealthy

# Gen Agent Trust Hub — web-only, no CLI
# Paste the skill URL at https://ai.gendigital.com/agent-trust-hub
# Returns: Safe / Low Risk / High Risk / Critical Risk
```

## Architecture

### Credential model

All skills share a single credential store at `~/.konecty/.env`:

```
KONECTY_URL=https://<host>
KONECTY_TOKEN=<authId>
```

`konecty-session` is the auth foundation — it performs the OTP two-phase flow (request-otp → verify-otp) and writes these files. Every other skill reads them at startup and fails fast with a clear message when they are missing or the API returns 401.

### API surface

| Prefix | Who uses it | Auth level |
|--------|-------------|------------|
| `/rest/data/:document/` | konecty-find, create, update, delete | user token |
| `/rest/query/json`, `/rest/query/sql` | konecty-find (cross-module) | user token |
| `/rest/file/` | konecty-upload | user token |
| `/rest/query/explorer/modules` | konecty-modules | user token |
| `/api/admin/meta/*` | all `konecty-meta-*` skills | admin token |

### Skills map

```
konecty-session      ← prerequisite for all others
konecty-modules      ← discover document/field names
konecty-find         ← search, filter, paginate, SQL
konecty-create       ← create records
konecty-update       ← update records (fetch-first: requires _updatedAt)
konecty-delete       ← delete one record at a time with confirmation guardrail
konecty-upload       ← attach/list/delete files on record fields

konecty-meta-read    ← read any MetaObject (all types)
konecty-meta-document ← CRUD document schema and fields
konecty-meta-list    ← CRUD list metas (columns, filters, sorters)
konecty-meta-view    ← CRUD view/FormSchema metas
konecty-meta-access  ← CRUD access profiles and permission filters
konecty-meta-pivot   ← CRUD pivot metas
konecty-meta-hook    ← generate and manage hook code (4 hook types)
konecty-meta-namespace ← tenant global config
konecty-meta-doctor  ← validate metadata integrity (uses backend doctor endpoint)
konecty-meta-sync    ← sync repo ↔ database (plan/apply)
konecty-meta-remove  ← interactive full-module deletion (children → hooks → document)
```

All meta is stored in a single `MetaObjects` collection, discriminated by a `type` field. The meta skills are intentionally split (not monolithic) to avoid token overload when only one concern is active.

## Skill format and quality standards

Every `SKILL.md` requires:

```markdown
---
name: konecty-my-skill   # lowercase, hyphens
description: <what it does> + Use when ... + Do NOT use for ...
---
```

The `description` field drives automatic skill selection — it must include:
- **What** the skill does
- **Use when** — exact phrases a user would say (including Portuguese equivalents for Konecty skills)
- **Do NOT use for** — negative triggers to prevent overlap with similar skills
- Keep under 1 024 characters; no XML angle brackets

Scripts must use **Python stdlib only** (no pip installs). Keep `SKILL.md` under ~300 lines; move reference material to `references/`.

## Changelog rule

Any change to repo structure, skill conventions, template, or `agents/skills/` requires:
1. `docs/changelog/YYYY-MM-DD_<slug>.md` — new entry
2. `docs/changelog/README.md` — new row in the table

Editing only a `SKILL.md`'s instruction content does not require a changelog entry. Architectural decisions go in `docs/adr/####-title.md`.
