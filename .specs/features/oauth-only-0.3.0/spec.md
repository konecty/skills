# Spec — OAuth-only skills, OTP purge, release 0.3.0

**Scope:** Medium (docs + installer code + release).
**Branch:** `feat/oauth-only-0.3.0`.
**Upstream context:** Konecty ADR-0020 removed the `session_*` OTP tools from the Platform MCP; the OAuth admin path via trusted clients (ADR-0011/0012) is live. Two Konecty features land new tool contracts this cycle: `file_upload` → single-use upload URL (`.specs/features/mcp-file-upload-url/spec.md` in the Konecty repo) and `meta_delete` + metadata trash (`.specs/features/admin-mcp-meta-delete/spec.md`).

## Problem Statement

The public skills still document OTP as a fallback — pointing at `session_*` tools that **no longer exist** (konecty-data) and teaching the `authTokenId` interim path that ADR-0020 forbids in public docs (konecty-meta). Decision (grill 2026-07-22): **total purge** — OAuth via MCP is the only documented path, in the skills and in the installer.

## Requirements (traceable)

### AC-1 — OTP purge in skills (konecty-data, konecty-meta, konecty-setup)
- Remove every OTP instruction and every `authTokenId` mention from `SKILL.md` and `references/` of the three skills (konecty-dev is out of scope — it documents server-side service-account auth, not interactive MCP auth).
- Known hotspots: `konecty-data/SKILL.md:20,28,51`, `konecty-data/references/auth.md` (whole OTP fallback section), `konecty-data/references/errors.md:14`, `konecty-meta/SKILL.md:21`, `konecty-meta/references/auth.md`, `konecty-setup/SKILL.md:174-225`, `konecty-setup/references/troubleshooting.md:20-28`.
- Troubleshooting rewritten: "no consent SPA / no browser" now points to backend upgrade or trusted-client provisioning (`OAUTH_CLIENTS_JSON`), never OTP.
- `konecty-meta/references/namespace.md` keeps `otpConfig` (server config of the Konecty UI login, not an MCP auth path) — clarify wording if ambiguous.
- Historical changelogs stay untouched (record, not instruction).

### AC-2 — OTP purge in installer
- Remove the `--admin-auth otp` branch and the OTP credential flow from `installer/` (cli, credentials, engines as applicable); OAuth trusted-client is the only admin path.
- Update installer tests; `make installer-test` green.
- Breaking change: recorded in changelog entry and release notes.

### AC-3 — Document the new Konecty tool contracts
- `konecty-data`: `file_upload` documented as single-use upload URL flow (tool returns URL + curl instructions; bytes never through the model; chat-only hosts cannot upload — stated limitation).
- `konecty-meta`: `meta_delete` documented (dry-run without `confirm` incl. blast-radius, `confirm: true` deletes, object goes to `MetaObjects.Trash`, namespace object undeletable).
- These sections land only after the Konecty contracts are frozen (specs above); the purge (AC-1/AC-2) does not wait for them.

### AC-4 — Release 0.3.0
- Bump `pyproject.toml`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` to 0.3.0; changelog entry per repo rule.
- `make check` and `make validate` green.

### AC-5 — Plugin validation + publish (end of cycle)
- Empirically validate `/plugin marketplace add konecty/skills` → install in a real Claude Code session (the repo records this was never tested end-to-end).
- Run `make publish` (gh/agentskills.io, clawhub, hermes) for 0.3.0.
- Curated marketplaces (anthropics/skills, tech-leads-club) are **out of scope** this cycle (external PR processes).

## Out of Scope

| Item | Reason |
| --- | --- |
| konecty-dev changes | Server-side auth path, no interactive OTP (user decision) |
| Removing OTP from the Konecty backend UI login | OTP remains a Konecty UI login method (ADR-0020) — only MCP/skills docs drop it |
| Curated marketplace submissions | External PR timeline, separate task |
