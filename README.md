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

## Documentation

- [Contributing & development](./docs/development.md)
- [Architecture Decision Records (ADR)](./docs/adr/README.md)
- [Changelog](./docs/changelog/README.md)
