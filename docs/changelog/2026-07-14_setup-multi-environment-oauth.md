# 2026-07-14 — konecty-setup: OAuth guidance correct across all Claude Code environments

## What changed

`konecty-setup` no longer implies MCP OAuth login is terminal-only. It now carries an
**OAuth login by environment** matrix and stops dead-ending headless sessions.

- **SKILL.md** — new *OAuth login by environment* section: CLI + desktop app → `/mcp`
  → Authenticate (browser, `http://localhost:PORT/callback`, tokens in OS keychain;
  also via Customize → Connectors); claude.ai web → claude.ai/customize/connectors
  (NOT inside Claude Code); headless / SSH / `claude -p` → `claude mcp login
  <name> --no-browser` paste flow OR the static Bearer-token fallback (works for both
  `konecty` and `konecty-admin`). Desktop app stated explicitly as first-class OAuth.
  The setup agent runs `claude mcp add` itself when it has a shell. When konecty-setup
  runs where no browser can open, it must not dead-end at "use the terminal" — it
  completes registration and offers the desktop/CLI, `--no-browser`, or Bearer path.
  Note that the konecty-crm plugin registers via `claude mcp add`, so `/mcp`
  Authenticate works (unlike plugin-embedded MCP servers). Keeps PR #8's OAuth-primary
  / OTP-or-Bearer-fallback framing.
- **references/troubleshooting.md** — new entries: `/mcp` Authenticate "Unable to
  connect" / "SDK auth failed" → OAuth issuer advertises `127.0.0.1:3000` when the
  deployment set `OAUTH_ISSUER_URL`/`BASE_URL` but not `KONECTY_URL` → set
  `KONECTY_URL` (and/or upgrade to the release with the issuer-consistency fix);
  claude.ai web → authenticate at claude.ai/customize/connectors; headless/no-browser
  → do not say "just use the terminal", give `--no-browser` + Bearer fallback. The
  existing "admin option not showing → trusted client via `OAUTH_CLIENTS_JSON`" entry
  is retained.

Docs-only. No installer/code changes; command templates stay byte-identical to the
`mcp_config` builders.

## Why

The prior guidance treated OAuth as a terminal-only flow, which is wrong for the
desktop app (first-class OAuth) and claude.ai web (authenticated via Connectors, not
inside Claude Code), and dead-ended any headless/`-p`/SSH session at "use the
terminal" despite `--no-browser` and Bearer both working. It also had no mapping for
the live Konecty issuer bug that breaks `/mcp` Authenticate in every environment.

## Spec

`.specs/features/setup-multi-environment-oauth/spec.md`
