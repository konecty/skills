# Feature: konecty-setup OAuth guidance correct across all Claude Code environments

**Size:** Medium · **Flow:** Specify (brief) → Execute
**Stacks on:** PR #8 (`feat/admin-oauth-default`) — OAuth-primary admin path. Merge #8 first.

## Problem

`konecty-setup` describes the MCP OAuth login as if it were terminal-only ("browser
opens on first tool call / `/mcp` in Claude Code"). That is wrong for two real
environments and dead-ends in a third:

- **Desktop app** is a first-class OAuth environment (`/mcp` → Authenticate, or
  Customize → Connectors), not just the CLI — the skill never says so.
- **claude.ai web** does NOT authenticate MCP inside Claude Code at all; the user
  adds/authenticates the server at claude.ai/customize/connectors.
- **Headless / SSH / `claude -p` / no browser**: the skill offers no path, so an
  agent running there dead-ends at "use the terminal" — even though `--no-browser`
  paste and a static Bearer-token fallback both work.

Separately, a live Konecty issuer bug (`fix/oauth-issuer-consistency`) makes `/mcp`
Authenticate fail with "Unable to connect" / "SDK auth failed" in EVERY environment
when the deployment sets `OAUTH_ISSUER_URL`/`BASE_URL` but not `KONECTY_URL` — the
troubleshooting matrix does not map that symptom.

## Goal

OAuth guidance presents an accurate per-environment matrix, never implies
terminal-only, never dead-ends in a headless session, and maps the issuer-bug
symptom to its remediation. Keep PR #8's OAuth-primary / OTP-or-Bearer-fallback
framing intact.

## Acceptance Criteria

1. **AC1 — environment matrix.** SKILL.md SHALL present a matrix: CLI + desktop app
   → `/mcp` Authenticate (browser, `http://localhost:PORT/callback`, tokens in OS
   keychain), also via Customize → Connectors; claude.ai web →
   claude.ai/customize/connectors (NOT inside Claude Code); headless →
   `--no-browser` paste OR Bearer-token fallback. Desktop app stated explicitly as
   first-class OAuth (not terminal-only).

2. **AC2 — headless no dead-end.** WHEN konecty-setup runs where no browser can open
   THEN it SHALL still run `claude mcp add` and offer: finish auth by opening the
   same project in the desktop app/CLI and `/mcp` → Authenticate, OR use
   `claude mcp login <name> --no-browser` (paste redirect, needs a TTY, e.g.
   `ssh -t`), OR the static Bearer-token fallback (works for `konecty` and
   `konecty-admin`). It SHALL NOT tell the user to "just use the terminal".

3. **AC3 — agent runs registration.** SKILL.md SHALL state that when the setup agent
   has a shell it runs `claude mcp add` itself, leaving the user only the browser
   Authenticate + consent step.

4. **AC4 — plugin note.** SKILL.md SHALL note the konecty-crm plugin ships skills
   only and registers the MCP server via `claude mcp add`, so `/mcp` Authenticate
   works (unlike plugin-embedded MCP servers).

5. **AC5 — issuer-bug troubleshooting.** troubleshooting.md SHALL map "Authenticate
   / `/mcp` fails with 'Unable to connect' / 'SDK auth failed'" to the issuer bug →
   the deployment must set `KONECTY_URL` (and/or upgrade to the release with the
   issuer-consistency fix). No invented version numbers.

6. **AC6 — web + headless troubleshooting entries.** troubleshooting.md SHALL add a
   web (claude.ai/customize/connectors) entry and a headless entry (no "just use the
   terminal"; `--no-browser` + Bearer fallback). The existing "admin option not
   showing → trusted client via `OAUTH_CLIENTS_JSON`" entry SHALL be kept.

## Scope / decisions

- Docs-only: no installer/code changes. Command templates stay byte-identical to the
  `mcp_config` builders and PR #8's SKILL.md templates.
- `description` edited only if needed for accurate triggers; minimal, <1024 chars,
  no XML brackets, bilingual.

## Non-goals

- Fixing the Konecty issuer bug itself (upstream `fix/oauth-issuer-consistency`).
- Touching `README.md` (owned by a parallel change).
- Installer/`mcp_config` changes.
