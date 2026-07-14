# 2026-07-14 — admin MCP access defaults to OAuth trusted client

## Summary

The `konecty-skills` installer and the `konecty-setup` skill now lead with the
**OAuth trusted-client** path for admin MCP access. The interim OTP → Bearer
`authTokenId` path is demoted to an explicit fallback for older Konecty
deployments (or when requested with `--admin-auth otp`).

## Why

OAuth admin is now the supported mechanism upstream (Konecty PR #453 + consent
UI ui#46): with a trusted first-party client seeded per-deployment via
`OAUTH_CLIENTS_JSON` (`trustedFirstParty: true`, `admin` in `allowedScopes`) and
an admin user, the `admin` scope is grantable at the browser consent on first
use. OTP meant a second, redundant login and a long-lived bearer token stored in
an MCP header.

## What changed

- **`installer/src/konecty_skills/cli.py`**
  - Admin block in `cmd_install` now chooses OAuth (default) vs OTP.
  - New `--admin-auth {oauth,otp}` flag on `install` (default `oauth`) for
    scriptable installs.
  - OAuth branch prompts for `client_id` (default `claude-code-admin`) and
    `callback_port` (default `19819`), registers `konecty-admin` via
    `mcp_config.build_add_admin_oauth`, and explains that browser login happens
    on first use and requires a server-seeded trusted client.
  - OTP branch (`credentials.otp_login` + `build_add_admin_token` + `.env`) is
    unchanged. `--yes` still skips the interactive admin step entirely.
- **`skills/konecty-setup/SKILL.md`** — "Flow: admin path" reordered so OAuth is
  primary and OTP is the labeled fallback; command templates stay byte-identical
  to the `mcp_config` builders.
- **Tests** — `installer/tests/test_cli_install.py`: OAuth-default path,
  prompted `client_id`/`port`, CLI-absent OAuth command (MCPF-21 parity),
  `--admin-auth otp` selects OTP (+ OTP-failure skip), and `--yes` admin-skip
  preserved.

## Spec

`.specs/features/admin-oauth-default/spec.md`
