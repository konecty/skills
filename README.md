# KonectySkills

Repository of **Agent Skills** for Konecty ecosystem. Skills are folders of instructions and resources that AI agents (e.g. Cursor, Claude Code) load dynamically to perform specialized tasks in a repeatable way.

For the Agent Skills standard, see [agentskills.io](https://agentskills.io). This repo is inspired by [anthropics/skills](https://github.com/anthropics/skills).

## Quick install

One command detects your AI engine, installs both skills, and sets up your Konecty credentials — without ever deleting or modifying existing files:

```bash
uvx --from git+https://github.com/konecty/skills konecty-skills install
```

| Command | What it does |
|---------|--------------|
| `install` | Detect engines → select skills → download → copy → set up credentials (OTP) → write manifest |
| `configure` | Credentials only: write `~/.konecty/.env` (URL + OTP token) |
| `status` | What is installed, in which engines, and whether credentials are present |
| `update` | Re-fetch skills with SHA-256 protection (never overwrites local edits) |
| `doctor` | Validate installed files vs manifest and test the Konecty connection |
| `uninstall` | Remove the installed skills (credentials kept unless `--purge`) |

The installer is a stdlib-only Python package in [`installer/`](./installer). All commands accept `--yes`/`--engine`/`--scope`/`--url`/`--ref` for non-interactive use.

## Structure

| Path | Purpose |
|------|---------|
| [./skills](./skills) | Konecty platform skills (each skill in its own folder with `SKILL.md`). |
| [./installer](./installer) | `konecty-skills` CLI installer (Python, stdlib only) — see Quick install above. |
| [./.agents/skills](./.agents/skills) | External skills installed via CLI (managed by `skills-lock.json`). |
| [./template](./template) | Template for creating new skills |
| [./spec](./spec) | Reference to the Agent Skills specification |
| [./docs](./docs) | Project documentation and changelog |

## Creating a skill

1. Copy the [template](./template) folder or create a new folder under `skills/`.
2. Add a `SKILL.md` with YAML frontmatter and instructions:

```markdown
---
name: my-skill-name
description: A clear description of what this skill does and when to use it.
---

# My Skill Name

Instructions the agent will follow when this skill is active.

## Examples
- Example usage 1
- Example usage 2

## Guidelines
- Guideline 1
- Guideline 2
```

**Frontmatter (required):**
- `name` — Unique identifier (lowercase, hyphens for spaces).
- `description` — What the skill does and when the agent should use it.

The rest of the file is Markdown: instructions, examples, and guidelines.

## Using skills in Cursor

Skills in this repo can be installed under `.cursor/skills/` (or your Cursor skills path). Each skill is a folder containing `SKILL.md`; the agent uses the `description` to decide when to load the skill.

## Credentials

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

| Credential | When needed | How to obtain |
|------------|-------------|---------------|
| `KONECTY_URL` + `KONECTY_TOKEN` | Testing skills locally against a Konecty instance | Run the `konecty-session` skill (OTP login) |
| `SNYK_TOKEN` | Security audit before publishing (`uvx snyk-agent-scan@latest --skills`) | [app.snyk.io/account](https://app.snyk.io/account) |
| GitHub auth | Publishing via `gh skill publish` | `gh auth login` (one-time, interactive) |
| clawhub auth | Publishing to OpenClaw | `clawhub login` (one-time, interactive) |
| Socket auth | Supply chain scan via `socket ci` | `socket login` (one-time, interactive) |

> The Gen Agent Trust Hub audit is web-only — paste the skill URL at [ai.gendigital.com/agent-trust-hub](https://ai.gendigital.com/agent-trust-hub).

## End-to-end testing

A self-contained, reproducible harness boots a disposable Konecty stack and drives every subcommand of both skills via a deterministic pseudo-agent.

### Quick start

```bash
make e2e          # self-contained: purge → up → wait → coverage gate → purge (always tears down)
```

**Prerequisites:** Docker (for the stack), `uv` (the suite runs via `uv run --with pytest --with coverage`).

### What gets tested

- **konecty-data (live)** — the subset the public `konecty/konecty:3.8.10` image supports is exercised against a real stack: `auth login-options`, `modules list/fields/search`, `find find` (filter/fields/ndjson), `create create`, `update update` (explicit `--ids`).
- **konecty-data (mock)** — the paths that require `/rest/query/json` with a `relations` array (which the public image rejects) are covered by an in-memory `MockKonecty`: `find query/sql`, `create lookup`, `update patch`, `delete`.
- **konecty-meta (mock)** — the `/api/admin/meta/*` admin API is implemented in Konecty PR [#299](https://github.com/konecty/Konecty/pull/299) (branch `feature/meta-crud-api`) but is not yet in any published image. All 11 subcommands (`read`, `document`, `list`, `view`, `access`, `pivot`, `hook`, `namespace`, `doctor`, `sync`, `remove`) run against a faithful in-memory mock of that contract. Live swap is deferred to when a PR-299 image ships (see `.specs/project/STATE.md` D8).
- **Security suite** (`tests/e2e/test_security.py`) — credential fast-fail, bad-token 401 (no traceback), delete/upload `--confirm` guards, OTP local validation, invalid hook/webhook rejection, token-not-leaked, injection payloads transported as data.
- **Intent router** (`tests/e2e/test_inference.py`) — a deterministic PT/EN phrase → skill-command router (no LLM) validates that common user phrases map to the right subcommand.

Coverage gate: **≥90%** of the skill scripts (`--fail-under=90`). Current result: **93%**. Reports: terminal + HTML (`tests/coverage_html/`) + XML.

### Make targets

| Target | What it does |
|--------|--------------|
| `make e2e` | Self-contained run: purge → up → wait → coverage gate → **purge** (tears down with `down -v` even on failure/interrupt) |
| `make e2e-up` | Boot the stack and wait until `/liveness` is healthy |
| `make e2e-down` | Stop the stack (keeps volumes) |
| `make e2e-reset` | Stop and **drop volumes** — clean DB + fresh admin next boot |
| `make e2e-wait` | Poll `/liveness` until healthy (standalone) |
| `make e2e-token` | Extract admin token from container logs (print only) |
| `make e2e-run` | Run the full suite (live + mock + security + inference) |
| `make e2e-cov` | Run suite with coverage and the ≥90% gate |
| `make e2e-sec` | Run only the security suite |
| `make e2e-infer` | Run only the inference/intent-router suite |

### Stack

`e2e/docker-compose.yml` boots MongoDB (replica set `rs0`) + `mongodb-init` + RabbitMQ + `konecty/konecty:3.8.10` on **alternate ports** (Konecty `:3200`, Mongo `:27117`) so it coexists with a dev Konecty on `:3000`. `make e2e-reset` (`down -v`) gives a clean DB and a fresh admin each round.

For full context and design decisions (D1–D10) see `.specs/features/e2e-harness/` and `.specs/project/STATE.md`.

## Documentation

- [Contributing & development](./docs/development.md)
- [Architecture Decision Records (ADR)](./docs/adr/README.md)
- [Changelog](./docs/changelog/README.md)
