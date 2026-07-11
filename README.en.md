<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo-horizontal-white.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/logo-horizontal-color.png">
  <img alt="Konecty" src="docs/logo-horizontal-color.png" width="300">
</picture>

# KonectySkills

> **Your AI agent now speaks Konecty.**

Agent Skills that connect AI agents like Claude Code and Cursor directly to the Konecty low-code business platform. Search records, create contacts, manage schemas, and write integrations — all with natural language, no API documentation needed.

[![Known Vulnerabilities](https://snyk.io/test/github/konecty/skills/badge.svg)](https://snyk.io/test/github/konecty/skills)
[![E2E Coverage](https://img.shields.io/badge/e2e_coverage-93%25-22c55e?style=flat-square)](#e2e-testing)
[![agentskills.io](https://img.shields.io/badge/agentskills.io-compatible-6366f1?style=flat-square)](https://agentskills.io)
[![skills.sh](https://img.shields.io/badge/skills.sh-compatible-6366f1?style=flat-square)](https://skills.sh)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue?style=flat-square)](./LICENSE)

**[🇧🇷 Versão em Português →](./README.md)**

---

## Quick Install

One command detects your AI engine, installs all three skills, and sets up your Konecty credentials — you'll be up and running in under two minutes:

```bash
uvx --from git+https://github.com/konecty/skills konecty-skills install
```

**Prerequisites:** Python 3.9+ and `uv` (`pip install uv` or `brew install uv`).

### Installer Commands

| Command | What it does |
|---------|--------------|
| `install` | Detect engines → select skills → download → copy → set up credentials (OTP) → write manifest |
| `configure` | Credentials only: write `~/.konecty/.env` (URL + OTP token) |
| `status` | What is installed, in which engines, and whether credentials are present |
| `update` | Re-fetch skills with SHA-256 protection (never overwrites local edits) |
| `doctor` | Validate installed files vs manifest and test the Konecty connection |
| `uninstall` | Remove installed skills (credentials kept unless `--purge` is passed) |

All commands accept `--yes` / `--engine` / `--scope` / `--url` / `--ref` for non-interactive use (CI/CD, provisioning scripts).

### Install via Marketplace

**[skills.sh](https://skills.sh)**
```bash
npm i -g @agentskill.sh/cli
npx skills add konecty/skills
```

**[OpenClaw (clawhub)](https://clawhub.io)**
```bash
npm i -g clawhub
clawhub skill install konecty-data
clawhub skill install konecty-meta
clawhub skill install konecty-dev
```

**[Hermes (NousResearch)](https://hermes.nousresearch.com)**
```bash
hermes skills tap add konecty/skills
hermes skills install konecty-data
hermes skills install konecty-meta
hermes skills install konecty-dev
```

### Manual Installation

If you prefer to install without the CLI:

```bash
# Clone the repository
git clone https://github.com/konecty/skills
cd skills

# Copy skills to your AI engine
# Claude Code (project-scoped)
cp -r skills/konecty-data  .claude/skills/
cp -r skills/konecty-meta  .claude/skills/
cp -r skills/konecty-dev   .claude/skills/

# Claude Code (global)
cp -r skills/konecty-data  ~/.claude/skills/
cp -r skills/konecty-meta  ~/.claude/skills/
cp -r skills/konecty-dev   ~/.claude/skills/

# Cursor
cp -r skills/konecty-data  .cursor/skills/
cp -r skills/konecty-meta  .cursor/skills/
cp -r skills/konecty-dev   .cursor/skills/
```

---

## The Three Skills

### `konecty-data` — Data Operations

Complete operations on Konecty records: OTP authentication, field discovery, and full CRUD with file management.

| When to use | Example phrases |
|-------------|----------------|
| Authenticate / get token | "log in to Konecty", "authenticate via OTP", "open session" |
| Discover fields and modules | "what fields does the Contact module have?", "list available modules" |
| Search records | "find contacts created today", "filter opportunities by status", "SQL query" |
| Create records | "create contact John Doe", "insert new opportunity", "create activity" |
| Update records | "update status of contact #123", "change email field" |
| Delete records | "delete record #456 from Leads module" |
| File upload | "attach contract.pdf to the record", "upload profile picture" |

**Requires:** credentials in `~/.konecty/.env` (`KONECTY_URL` + `KONECTY_TOKEN`).

---

### `konecty-meta` — Metadata Management *(admin)*

Complete management of platform schemas and configurations: documents, lists, views, access profiles, hooks, namespace config, and repo↔database sync.

| When to use | Example phrases |
|-------------|----------------|
| Inspect schemas | "list documents", "read CRM module metadata", "inspect fields" |
| Manage documents | "add field to module", "create document", "remove field" |
| Configure lists and views | "add column to list", "create form view", "configure layout" |
| Access profiles | "configure read permissions", "manage access profile" |
| Generate hooks | "generate scriptBeforeValidation hook", "create validationScript" |
| Configure Namespace | "configure SMTP", "set up RabbitMQ queue", "update namespace" |
| Validate integrity | "validate metadata", "check integrity", "metadata audit" |
| Sync | "sync metadata to production", "apply schema", "deploy metas" |
| Remove module | "remove complete module", "delete metadata", "remove document meta" |

**Requires:** **admin** credentials in `~/.konecty/.env` (user with `admin: true`).

---

### `konecty-dev` — Code Integration *(advisory)*

Advisory skill for writing code that integrates with Konecty — prioritizing the official SDKs (Python and TypeScript/Node), with the full REST API documented for other languages.

| When to use | Example phrases |
|-------------|----------------|
| Start an integration | "how to connect my app to Konecty?", "which SDK to use?", "first client" |
| Python SDK | "Python example", "use konecty_sdk_python", "Python client" |
| TypeScript/Node SDK | "TypeScript example", "use @konecty/sdk", "Node client" |
| REST API (other languages) | "call API with Go", "Java integration", "HTTP client without SDK" |
| Filters and queries | "how to filter by date?", "search operators", "query with relations" |
| Server-side hooks | "write scriptBeforeValidation", "after-save logic", "validationScript" |
| Recipes and patterns | "pagination", "retry", "incremental sync", "file upload flow" |

**Does not execute live operations** — generates code for you to embed in your application. For immediate operations, use `konecty-data`.

---

## Credentials

### Initial Setup

```bash
# Option 1: via installer (recommended — runs the full OTP flow)
uvx --from git+https://github.com/konecty/skills konecty-skills configure

# Option 2: manual
cp .env.example .env
# Fill in KONECTY_URL and KONECTY_TOKEN
```

The `~/.konecty/.env` file is shared by all skills:

```dotenv
KONECTY_URL=https://your-instance.konecty.com
KONECTY_TOKEN=<authId obtained via OTP login>
```

### Other Credentials

| Credential | When needed | How to obtain |
|------------|-------------|---------------|
| `KONECTY_TOKEN` (admin) | `konecty-meta` | User with `admin: true` in Konecty |
| `SNYK_TOKEN` | Security audit | [app.snyk.io/account](https://app.snyk.io/account) |
| GitHub auth | Publish via `gh skill publish` | `gh auth login` (interactive, once) |
| Socket auth | Supply chain scan | `socket login` (interactive, once) |
| clawhub auth | Publish to OpenClaw | `clawhub login` (interactive, once) |

> The Gen Agent Trust Hub audit is web-only — paste the skill URL at [ai.gendigital.com/agent-trust-hub](https://ai.gendigital.com/agent-trust-hub).

---

## Security

### Audits Performed

| Tool | Result | Last verified | Details |
|------|--------|--------------|---------|
| **Snyk** | live badge | continuous | Badge above reflects the latest scan — [import the repo at snyk.io](https://snyk.io/test/github/konecty/skills) to activate |
| **Gen Agent Trust Hub** | ✅ PASS | 2026-06-17 | No prompt injection, malicious payloads, or critical agent risks |
| **Socket** | ✅ PASS | 2026-06-17 | Clean supply chain — no malicious or compromised dependencies |

> Gen Agent Trust Hub and Socket are manual point-in-time checks (no live badge API). Snyk is the only continuous badge — requires the repo to be imported at [snyk.io](https://snyk.io).

All scripts use **Python stdlib only** — no third-party dependencies, eliminating the largest class of supply-chain risk.

### Reproducing the Audits

```bash
# Gen Agent Trust Hub — web only
# Visit https://ai.gendigital.com/agent-trust-hub and paste the skill URL

# Socket — supply chain
npm i -g @socketsecurity/cli
socket login
socket scan create ./skills/konecty-data
socket scan create ./skills/konecty-meta
socket scan create ./skills/konecty-dev
socket ci

# Snyk Agent Scan
export SNYK_TOKEN=<your-token>
uvx snyk-agent-scan@latest --skills                    # all skills
uvx snyk-agent-scan@latest ./skills/konecty-data       # specific skill
```

---

## E2E Testing

A dockerized test suite boots a disposable Konecty stack and drives all subcommands of both operational skills via a deterministic pseudo-agent.

**Current coverage: 93%** (gate `--fail-under=90`). 472 tests passing + 1 documented xfail.

### Quick Start

```bash
make e2e   # purge → up → wait → coverage gate → purge (always tears down the stack)
```

**Prerequisites:** Docker (for the stack) and `uv` (the suite runs via `uv run`).

### What Gets Tested

| Suite | Description |
|-------|-------------|
| **konecty-data (live)** | Against the public `konecty/konecty:3.8.10` image: auth, modules, find, create, update |
| **konecty-data (mock)** | Paths requiring unpublished endpoints: SQL query, lookup, delete |
| **konecty-meta (mock)** | All 11 subcommands against a faithful mock of the `/api/admin/meta/*` contract |
| **Security suite** | Credential fast-fail, 401 without traceback, delete/upload guards, OTP validation, injection payloads |
| **Intent router** | Deterministic PT/EN phrase → skill-command router (no LLM, zero API cost) |

### Make Targets

| Target | What it does |
|--------|--------------|
| `make e2e` | Full cycle: purge → up → wait → coverage → purge |
| `make e2e-up` | Boot the stack and wait for `/liveness` |
| `make e2e-down` | Stop the stack (keeps volumes) |
| `make e2e-reset` | Stop and **drop volumes** — clean DB + fresh admin on next boot |
| `make e2e-token` | Extract admin token from container logs |
| `make e2e-run` | Run the full suite (without coverage gate) |
| `make e2e-cov` | Run with coverage and the `≥90%` gate |
| `make e2e-sec` | Security suite only |
| `make e2e-infer` | Intent router only |

---

## Repository Structure

```
skills/              # Konecty platform skills (one folder per skill with SKILL.md)
├── konecty-data/    # Data ops: auth, modules, find, create, update, delete, upload
├── konecty-meta/    # Metadata: document, list, view, access, pivot, hook, namespace, sync
└── konecty-dev/     # Advisory: Python/TS SDKs, REST API, hooks, filters, recipes
installer/           # konecty-skills CLI (Python stdlib, uvx entry point)
e2e/                 # Docker Compose stack for tests (MongoDB + RabbitMQ + Konecty)
tests/e2e/           # E2E test suite (pseudo-agent + mocks + suites)
.agents/skills/      # External skills installed via CLI (tracked in skills-lock.json)
.specs/              # SDD specs: project, codebase analysis, feature specs
template/            # Template for creating new skills
spec/                # Agent Skills standard reference
docs/                # Documentation, ADRs, and changelog
```

---

## Development

### Main Commands

```bash
make help            # list all available targets
make setup           # point git at .githooks (run once after cloning)
make check           # offline gate: compile scripts + shared-files guard + installer tests
make lint            # py_compile all skill scripts
make installer-test  # installer unit tests (128 tests, stdlib, offline)
make validate        # gh skill publish --dry-run on skills (validates SKILL.md)
make audit           # codebase-intelligence + codebase-security (PR completion gate)
make e2e             # full E2E cycle
make clean           # remove __pycache__, .coverage, and coverage artifacts
```

### Creating a New Skill

1. Create a folder under `skills/` with a short, lowercase name.
2. Add `SKILL.md` with YAML frontmatter (`name` + `description`) and Markdown instructions.
3. Scripts must use **Python stdlib only** — no external dependencies.
4. Document the change in `docs/changelog/YYYY-MM-DD_slug.md`.

Refer to [template/SKILL.md](./template/SKILL.md) and follow the **skill-creator** workflow.

### Shared-Files Invariant

`scripts/auth.py` and `scripts/modules.py` are **byte-identical** across `konecty-data` and `konecty-meta`. Always edit both sides together — divergence is caught by the pre-commit hook and the `check-shared-files` GitHub Action.

### Completion Gate (before any PR)

```bash
make check   # offline verification
make audit   # intelligence + security (a fail verdict blocks the PR)
```

---

## Publishing to Marketplaces

Use `make publish` to publish all three skills to every marketplace at once, or individual targets per platform:

```bash
# Publish everywhere (after gh auth login + clawhub login)
make publish VERSION=1.2.0 CHANGELOG="What changed"

# By marketplace
make publish-gh       VERSION=1.2.0  # GitHub via gh skill
make publish-clawhub  VERSION=1.2.0 CHANGELOG="Auth fix"
make publish-hermes                  # no extra params needed
```

`VERSION` auto-detects the latest git tag (`git describe --tags`); pass it explicitly to override.

### skills.sh

Skills appear organically on [skills.sh](https://skills.sh) once the repository is public on GitHub with a valid `SKILL.md` — no separate publish step needed. To install:

```bash
npx skills add konecty/skills
```

### GitHub (gh skill)

```bash
gh auth login                           # one-time auth
make publish-gh VERSION=1.2.0           # publishes all three skills
# or manually:
cd skills/konecty-data && gh skill publish --fix
```

### OpenClaw (clawhub)

```bash
npm i -g clawhub
clawhub login                           # one-time auth
make publish-clawhub VERSION=1.2.0 CHANGELOG="Auth fix"
# or manually:
clawhub skill publish ./skills/konecty-data --slug konecty-data --version 1.2.0 --changelog "..."
clawhub skill publish ./skills/konecty-meta --slug konecty-meta --version 1.2.0 --changelog "..."
clawhub skill publish ./skills/konecty-dev  --slug konecty-dev  --version 1.2.0 --changelog "..."
```

### Hermes (NousResearch)

```bash
make publish-hermes                     # uses GitHub as backend
# or manually:
hermes skills publish skills/konecty-data --to github --repo konecty/skills
hermes skills publish skills/konecty-meta --to github --repo konecty/skills
hermes skills publish skills/konecty-dev  --to github --repo konecty/skills
```

### Anthropic/skills and tech-leads-club

Both registries are curated via Pull Request. Fork the repository, add your skill folder, and open a PR.

---

## Documentation

- [Development & contributing](./docs/development.md)
- [Publishing to marketplaces](./docs/publishing.md)
- [Architecture Decision Records (ADR)](./docs/adr/README.md)
- [Changelog](./docs/changelog/README.md)
- [🇧🇷 Versão em Português](./README.md)

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See the [`LICENSE`](./LICENSE) file for the full text.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Built with ❤️ by the [Konecty](https://konecty.com) team.
