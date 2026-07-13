# AGENTS.md

Guidance for AI coding agents working in this repository.

> This file is `AGENTS.md`; `CLAUDE.md` is a symlink to it. Edit `AGENTS.md`.

## Language

Respond to the user in **pt-BR** (Brazilian Portuguese). Code, identifiers, file contents, and SKILL.md/reference docs follow their own conventions (English where the codebase already uses English); only the conversational replies are in pt-BR.

## Read first

- `README.md` — what the repo is, how the skills install, the four-skill layout.
- `.specs/project/STATE.md` — decision log and the *why* behind them. Source of truth; update it when a decision changes instead of re-explaining in code or commits. _(Create it on the next session if absent.)_
- `.specs/codebase/` — brownfield analysis: `STACK.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `STRUCTURE.md`, `TESTING.md`, `INTEGRATIONS.md`, `CONCERNS.md`. Read `CONCERNS.md` before touching anything flagged risky.
- `template/SKILL.md` + `spec/` — the SKILL.md format and the Agent Skills standard. Read before creating or editing a skill.
- `.specs/features/<feature>/` — `spec.md` / `tasks.md` for whatever feature is in flight.

## Commands

`make help` lists every target. The ones you'll use:

- `make setup` — point git at `.githooks` (run once after cloning; idempotent).
- `make check` — **offline gate**: `py_compile` (installer + e2e Python) + the installer unit tests. No live server needed; run before every commit.
- `make lint` — `py_compile` all repo Python (stdlib syntax check; prunes `e2e/.konecty-src`).
- `make installer-test` — run the `konecty-skills` installer unit tests (`installer/`, stdlib only, offline).
- `make validate` — `gh skill publish --dry-run` on all 4 skills (validates SKILL.md against the agentskills.io spec).
- `make e2e` — **full clean e2e cycle**: purge → build image from the local Konecty worktree → up → wait → bootstrap namespace MCP flags → suites → purge. The harness lives in `e2e/` (Docker stack + bootstrap scripts) and `tests/e2e/` (stdlib MCP client + pytest suites); runs via `uv`. Needs Docker, Node 24 + Yarn, and `../Konecty` cloned.
  - `make e2e-src` — create the `e2e/.konecty-src` worktree and build `dist/`.
  - `make e2e-up` / `e2e-down` / `e2e-reset` — build+start / stop / drop-volumes the disposable Konecty stack (`:3200`). **Recreating the konecty container without `e2e-reset` loses the admin password** (logged only on first boot).
  - `make e2e-token` — extract admin token from container logs (print only).
  - `make e2e-run` (alias `make test`) — run the suites (smoke + user + admin + oauth) against a running stack.
- `make audit` — `codebase-intelligence` + `codebase-security` audits (the PR completion gate — see *Workflow*).
- `make clean` — remove `__pycache__` and pytest caches.

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

- **Clarify before planning with `grill-with-docs`** whenever a request is medium-to-complex or ambiguous. It stress-tests the plan against the domain (`.specs/` + `CONCERNS.md`) and sharpens terminology before any file is written. Resolve ambiguity here, not mid-implementation.
- When creating or improving a skill, follow the **skill-creator** workflow: Draft → Test → Review → Iterate → Optimize → Package. The full workflow is at `.agents/skills/skill-creator/SKILL.md`.
- Never mark a task complete without verifying the skill works end-to-end (MCP server connected, the documented tool sequence produces the correct output — the e2e suites are the reference).
- If something is ambiguous (module name, field name, tool shape), discover via the Konecty MCP tools (`modules_list`/`modules_fields` on `konecty`, `meta_read` on `konecty-admin`) before guessing.
- **Completion gate — run before declaring a task done or opening a PR:** `make check` (offline syntax + installer tests) **and** `make audit`, which runs both audits:
  - `bash .agents/skills/codebase-intelligence/scripts/audit.sh . --changed-since main` — code health: no new dead code, duplication, complexity, or boundary violations.
  - `bash .agents/skills/codebase-security/scripts/audit.sh . --changed-since main` — security: no secrets, high-severity SAST findings, vulnerable/malicious deps, or exposed config. A `fail` verdict blocks the PR.

### Available skills (`.agents/skills/`, tracked in `skills-lock.json`)

| Skill | Use for |
|-------|---------|
| `tlc-spec-driven` | Spec → design → tasks → execute (mandatory pipeline) |
| `skill-creator` | Authoring/optimizing a skill |
| `grill-with-docs`, `grill-me` | Stress-testing a plan before building |
| `codebase-intelligence`, `codebase-security` | The completion-gate audits |
| `copywriting` | Marketplace listings, skill descriptions, README/landing copy |
| `content-strategy` | Planning docs/blog/launch content for the skills |
| `marketing-ideas`, `marketing-psychology` | Growth and positioning when promoting the skills |

## Repository

**KonectySkills** is a monorepo of [Agent Skills](https://agentskills.io) that give AI agents the ability to interact with the Konecty low-code platform. The skills are **MCP-first procedural guides**: execution happens on Konecty's own MCP servers (`/mcp`, `/admin-mcp`); each skill is a folder with a `SKILL.md` + `references/` and ships **no HTTP-calling scripts**. If a capability is missing from the MCP, the gap becomes an upstream Konecty feature — never a local workaround (see the MCP-first ADR).

```
skills/              # The 4 skills (SKILL.md + references/ per skill; no scripts)
installer/           # konecty-skills CLI installer (Python pkg, stdlib only; uvx entry point)
e2e/                 # Docker stack: Konecty built from ../Konecty worktree + MCP bootstrap
tests/e2e/           # MCP e2e suites (stdlib JSON-RPC client + pytest)
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

### Auth model (MCP-first)

- **User MCP (`konecty` → `<url>/mcp`)**: OAuth handled natively by Claude Code (DCR → authorize + PKCE → token in the browser). Tools are called **without** `authTokenId` — the token travels in the `Authorization` header. Fallback: OTP via the `session_*` tools + per-tool `authTokenId` argument.
- **Admin MCP (`konecty-admin` → `<url>/admin-mcp`), interim**: admin OTP login → `authTokenId` registered as an `Authorization: Bearer` header on the MCP entry. `~/.konecty/.env` now stores **only** this interim admin token (written by the installer's `configure`).
- **Admin MCP, target**: OAuth `admin` scope for trusted clients (provisioned via `OAUTH_CLIENTS_JSON`; konecty/Konecty#453). Switching is a re-registration only.
- Namespace gates (deny-by-default): `mcpUserEnabled`, `mcpAdminEnabled`, `mcpRoleIds`, `mcpUserWriteEnabled` (read-only MCP unless true).

### MCP tool surface (execution layer — lives in Konecty, not here)

| Server | Tools | Who guides |
|--------|-------|------------|
| `/mcp` (user) | `session_*`, `modules_*`, `field_*`, `filter_build`, `records_*`, `query_*`, `file_*`, `render_*` | konecty-data |
| `/admin-mcp` (admin) | `meta_read`, `meta_{document,list,view,access,pivot}_upsert`, `meta_hook_validate/upsert`, `meta_namespace_update`, `meta_doctor_run`, `meta_sync_plan/apply` | konecty-meta |

The consumer contract is `../Konecty/docs/en/mcp.md` — skills condense it, never contradict it.

### Skills map

```
konecty-data   ← CRM data conversations over the user MCP:
                   field discovery (modules_list → modules_fields → field helpers)
                   find/query (filter_build → records_find | query_json | query_sql)
                   create; update (fetch-first with _updatedAt)
                   delete (records_delete_preview → explicit confirm → records_delete)
                   files (file_upload/download/delete)
                   auth + error mapping (references/auth.md, errors.md)

konecty-meta   ← metadata administration over the admin MCP:
                   read, document/list/view/access/pivot upserts (FULL-REPLACE —
                   always read-modify-write), hook (validate BEFORE upsert),
                   namespace (incl. MCP flags), doctor, sync (plan → apply),
                   remove (documented MCP gap — manual path only)

konecty-setup  ← conversational setup: URL validate, claude mcp add/remove
                   templates, OAuth walkthrough, admin OTP path, troubleshooting

konecty-dev    ← advisory: integration code (SDKs, REST), unaffected by transport
```

All meta is stored in a single `MetaObjects` collection, discriminated by a `type` field.

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

Skills ship **no HTTP-calling scripts** — they are procedural guides over the Konecty MCP tools. Repo tooling (installer, e2e) uses **Python stdlib only** (no pip installs). Keep `SKILL.md` under ~300 lines; move reference material to `references/`.

## Changelog rule

Any change to repo structure, skill conventions, template, or `agents/skills/` requires:
1. `docs/changelog/YYYY-MM-DD_<slug>.md` — new entry
2. `docs/changelog/README.md` — new row in the table

Editing only a `SKILL.md`'s instruction content does not require a changelog entry. Architectural decisions go in `docs/adr/####-title.md`.
