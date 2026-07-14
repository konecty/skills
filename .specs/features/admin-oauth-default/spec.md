# Feature: admin MCP access defaults to OAuth (trusted client)

**Size:** Medium · **Flow:** Specify (brief) → Execute

## Problem

The `konecty-skills` installer and the `konecty-setup` skill still lead with the
interim OTP admin path (`build_add_admin_token`, Bearer `authTokenId`) even
though OAuth admin is now the supported mechanism upstream (Konecty PR #453 +
consent UI ui#46). OTP means a second, redundant login and a long-lived bearer
token stored in an MCP header. OAuth admin — via a trusted first-party client
seeded per-deployment through `OAUTH_CLIENTS_JSON` (`trustedFirstParty: true`,
`admin` in `allowedScopes`) — needs no stored token: the `admin` scope is
grantable at the browser consent on first use.

## Goal

OAuth is the **default** admin path; OTP is an explicit "legacy / older Konecty"
fallback. Both the installer's `install` command and the `konecty-setup`
SKILL.md lead with OAuth.

## Acceptance Criteria

1. **AC1 — OAuth is default.** WHEN the user opts into admin setup THEN the
   installer SHALL default to the OAuth trusted-client path, prompting for
   `client_id` (default `claude-code-admin`) and `callback_port` (default
   `19819`), and register `konecty-admin` via `mcp_config.build_add_admin_oauth`.

2. **AC2 — OTP fallback unchanged.** WHEN the user chooses the fallback (or
   passes `--admin-auth otp`) THEN the existing OTP → Bearer flow
   (`credentials.otp_login` + `build_add_admin_token` + `~/.konecty/.env`) SHALL
   run unchanged.

3. **AC3 — first-use guidance.** WHEN OAuth admin is registered THEN the
   installer SHALL tell the user the admin login happens on first use (`/mcp` →
   `konecty-admin` → Authenticate) AND that it requires a trusted client seeded
   on the server, pointing to konecty-setup troubleshooting if the `admin`
   option does not appear at consent.

4. **AC4 — CLI-absent parity (MCPF-21).** WHEN the `claude` CLI is absent THEN
   the printable-command fallback SHALL show the OAuth `claude mcp add` command.

5. **AC5 — skill reorder.** `konecty-setup` SKILL.md "Flow: admin path" SHALL be
   reordered so OAuth is **primary** and OTP is the labeled fallback; command
   templates stay byte-identical to the `mcp_config` builders.

## Scope / decisions

- `--admin-auth {oauth,otp}` optional arg on `install` (default `oauth`) for
  scriptable installs; the admin step remains interactive-only, so under `--yes`
  admin is skipped entirely (current behavior preserved).
- The trusted client is provisioned per-deployment (config-only, no default
  seeded by us). Documented example values: `client_id=claude-code-admin`,
  `callback_port=19819`.
- Claude Code OAuth callback is exactly `http://localhost:<port>/callback`;
  `--callback-port` fixes the port and must match a registered redirectUri.
- `credentials.otp_login` and `build_add_admin_token` are retained for the
  fallback — not deleted.

## Non-goals

- Seeding a default trusted client.
- Changing `cmd_configure` (interim OTP admin-token command) — out of scope.
- Touching `README.md` (owned by a parallel change).
