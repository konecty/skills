# Tech Stack

**Analyzed:** 2026-05-19

## Core

- Language: Python 3 (stdlib only — no external packages)
- Format: Markdown + YAML frontmatter (Agent Skills spec)
- Package manager: None (no build step; skills are folders)
- Lock file: `skills-lock.json` (tracks installed external skills)

## Runtime

- Python 3 (stdlib modules: `urllib`, `json`, `argparse`, `configparser`, `os`, `sys`, `difflib`)
- No virtual environment, no pip, no requirements.txt

## Frontend

Not applicable — this is an agent skills monorepo, not a web application.

## Backend / API

- API Style: REST (Konecty backend, external service)
- Authentication: OTP two-phase flow (request-otp → verify-otp → persist token)
- Credential store: `~/.konecty/.env` + `~/.konecty/credentials` (ini format)

## Testing

- Unit: None
- Integration: None
- E2E: None
- Manual validation only, via `skill-creator` workflow

## External Services

- Auth: Konecty OTP (email or WhatsApp delivery)
- Metadata: Konecty REST API (`/rest/data/`, `/rest/query/`, `/api/admin/meta/`)
- Security scanning: Snyk Agent Scan (`uvx snyk-agent-scan@latest`)
- Supply chain: Socket (`socket scan`)
- Trust audit: Gen Agent Trust Hub (web-only)
- Publishing: GitHub CLI (`gh skill publish`), OpenClaw (`clawhub`), Hermes (`hermes skills`), skills.sh

## Development Tools

- Version control: Git
- AI agent harness: Claude Code (`.claude/settings.json`, `CLAUDE.md`)
- Skill management CLI: `gh skill`, `npx skills`, `clawhub`, `hermes`
- Code review/planning: tlc-spec-driven + skill-creator (external skills in `.agents/skills/`)
