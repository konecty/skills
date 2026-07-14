# Feature: autonomous MCP registration across CLI and app

**Size:** Medium · **Flow:** Specify (brief) → Execute

## Problem

`konecty-setup` only knows one registration mechanism: shelling out to
`claude mcp add`. When the `claude` CLI is absent — the typical case inside the
**Claude desktop app** — the skill dead-ends: it prints commands and tells the
user to "run them manually", but the app user has no terminal to run them in.
So in the exact environment where the skill is most needed, it does nothing.

The docs are clear that this dead-end is unnecessary: the desktop app **and**
the CLI both read user-scope MCP servers from `~/.claude.json` (honoring
`CLAUDE_CONFIG_DIR`), and user-scope servers there have **no** pending-approval
gate (that gate is only for project `.mcp.json`). So the agent can register the
server by editing that file directly — no CLI required.

## Goal

Rewrite the registration flow so the **agent** does the work end-to-end,
choosing the mechanism by environment, with **OAuth as the default** in both:

- CLI available → `claude mcp add ... --scope user` (replace-not-duplicate).
- CLI absent (app) → the agent safely edits `~/.claude.json` itself.

Bearer/OTP stays a documented fallback only (older Konecty / no-browser),
never the default.

## Acceptance Criteria

1. **AC1 — URL resolve + validate.** WHEN a URL is given THEN the skill SHALL
   normalize to `https://host` (strip path/trailing slash) and probe
   `GET <url>/.well-known/oauth-protected-resource` (expect 200 JSON; `resource`
   should equal `<url>/mcp`; warn on issuer host ≠ company host or localhost),
   aborting cleanly on unreachable / 404 (no MCP).

2. **AC2 — environment detection.** WHEN registering THEN the skill SHALL run
   `command -v claude` and branch: CLI present → `claude mcp add`; CLI absent →
   direct `~/.claude.json` edit. Neither branch is a dead-end.

3. **AC3 — autonomous config-write (app path).** WHEN the CLI is absent THEN the
   agent SHALL edit `~/.claude.json` (or `$CLAUDE_CONFIG_DIR/.claude.json`) via a
   stdlib-`json` python3 procedure that: treats a missing file as `{}`, ensures a
   top-level `mcpServers` dict, sets `mcpServers["konecty"]` to the exact entry,
   replaces (never duplicates) an existing entry, and writes back with
   `indent=2` **preserving every other key**. NEVER overwrites the whole file.

4. **AC4 — OAuth is the default everywhere.** The user server entry SHALL be a
   plain `{"type":"http","url":"<url>/mcp"}` (DCR OAuth). The admin server (only
   for admins who want it) SHALL carry the `oauth` block
   (`clientId: "claude-code-admin"`, `callbackPort: 19819`). Bearer/OTP is a
   labeled fallback only.

5. **AC5 — per-environment finish steps.** CLI: first tool call (or `/mcp` →
   Authenticate) opens the browser. App: the user RESTARTS the app (config read
   on startup — no hot-reload), then `/mcp` → `konecty` → Authenticate. Restart +
   the consent click are the only manual steps.

6. **AC6 — no-clobber safety + honesty.** The config-write MUST NOT touch other
   keys or duplicate entries. The skill MUST present the app OAuth finish as the
   documented/expected flow WITHOUT claiming it is empirically verified, and MUST
   name the Bearer fallback as the guaranteed-no-browser alternative.

## Out of scope

- No Python code changes (this is markdown skill guidance the agent executes).
- Installer command builders (`mcp_config.py`) stay as-is; SKILL.md CLI templates
  stay consistent with them.

## Verification

`make check` (offline: byte-compile + shared-files guard + installer tests) and
`make validate` (`gh skill publish --dry-run`).
