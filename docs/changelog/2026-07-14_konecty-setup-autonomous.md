# 2026-07-14 — konecty-setup registers MCP autonomously across CLI and app

## Summary

The `konecty-setup` skill now registers the Konecty MCP servers **end-to-end**
in both environments — the `claude` CLI and the Claude desktop app — instead of
dead-ending when the CLI is absent. **OAuth remains the default**; Bearer/OTP
stays a documented fallback only.

## Why

The skill only knew one mechanism: `claude mcp add`. When the `claude` CLI is
missing — the typical case inside the desktop app — it printed commands and told
the user to "run them manually", but the app user has no terminal. So in the
exact place the skill is most needed, it did nothing.

The docs confirm the dead-end is unnecessary: the desktop app **and** the CLI
both read user-scope MCP servers from `~/.claude.json` (honoring
`CLAUDE_CONFIG_DIR`), and user-scope servers there have **no** pending-approval
gate (that gate is only for project `.mcp.json`). So the agent can register the
server by editing that file directly.

## What changed

- **`skills/konecty-setup/SKILL.md`**
  - "Command templates" reworked into **Registration mechanisms** with two
    forms: (A) `claude` CLI commands and (B) config-file JSON entries under the
    top-level `mcpServers` object of `~/.claude.json`. Documented the exact
    schema: every entry MUST carry `"type":"http"`; user = `{"type":"http",
    "url":"<url>/mcp"}`; admin OAuth = `+ "oauth":{"clientId":"claude-code-admin",
    "callbackPort":19819}`; Bearer fallback = `+ "headers":{"Authorization":
    "Bearer <authTokenId>"}`.
  - New **Registration flow (environment-aware, autonomous)**: validate URL →
    `command -v claude` → CLI path (`mcp add`, replace-not-duplicate) or app path
    (safe python3 `~/.claude.json` write) → per-environment finish (CLI first
    tool call / browser; app restart + `/mcp` → Authenticate). Includes a
    ready-to-run stdlib-`json` python3 snippet that treats a missing file as
    `{}`, ensures `mcpServers`, sets one `konecty` entry (replace, never
    duplicate), and writes back with `indent=2` preserving every other key.
  - Honesty caveat encoded: the config-write and the app reading it are
    doc-confirmed; the app `/mcp` → Authenticate browser UX is documented but not
    empirically verified — presented as expected, with Bearer as the
    guaranteed-no-browser alternative.
  - "Flow: first setup / switch company / admin path / fix auth" updated to
    reference the Registration flow instead of numbered CLI templates.
- **`skills/konecty-setup/references/troubleshooting.md`** — new rows: `claude`
  CLI absent (register via config-write, do not tell the user to run commands),
  server not appearing after config-write (restart to load), entry missing
  `type:http`, and app OAuth without a browser (Bearer fallback).

## Spec

`.specs/features/konecty-setup-autonomous/spec.md`
