---
name: konecty-setup
description: "Setup and troubleshooting for the Konecty MCP connection in Claude Code: register or replace the konecty and konecty-admin MCP servers for a company URL, guide the browser OAuth login, run the admin token path (interim OTP), and diagnose connection, login, and permission errors. Use when: configurar konecty, conectar meu crm, trocar de empresa, mudar a URL do konecty, problema de login no konecty, problema de permissão no konecty, refazer login, configurar acesso admin, set up konecty, connect my CRM, switch company URL, fix konecty login, re-authenticate, MCP connection or enablement errors. Do NOT use for data record operations (find/create/update/delete/upload) — use konecty-data; do NOT use for metadata/schema administration (documents, lists, views, access, hooks, namespace) — use konecty-meta."
---

# Konecty Setup

Conversational setup for the Konecty MCP servers in Claude Code. Konecty exposes two
MCP endpoints per deployment: the **user MCP** at `<url>/mcp` (data operations,
OAuth login) and the **admin MCP** at `<url>/admin-mcp` (metadata, admin users only).
This skill registers them, switches them to a new company URL, fixes authentication,
and troubleshoots enablement — it never makes improvised HTTP calls to Konecty.

## Command templates (single source of truth)

These are exactly the commands the `konecty-skills` installer runs. `<url>` is the
normalized company base URL (see *URL validation*).

```bash
# User MCP (data + OAuth login)
claude mcp add --transport http --scope user konecty <url>/mcp

# Admin MCP — interim path (Bearer authTokenId from an admin OTP login)
claude mcp add --transport http --scope user konecty-admin <url>/admin-mcp --header "Authorization: Bearer <authTokenId>"

# Admin MCP — OAuth target path (once the deployment seeds a trusted client)
claude mcp add --transport http --scope user konecty-admin <url>/admin-mcp --client-id <trusted-client-id> --callback-port <port>

# Removal (always before re-adding — replace, never duplicate)
claude mcp remove --scope user konecty
claude mcp remove --scope user konecty-admin
```

Server names are fixed: `konecty` and `konecty-admin`. Registration is always
`--scope user` — the CRM follows the person across projects.

**If the `claude` CLI is not available** in the current environment, do not fail:
print the exact commands above (with values filled in) for the user to run manually.

## URL validation (before any registration)

1. Ask the user for their company's Konecty URL if not already known.
2. **https only** — reject `http://` with a clear message (exception: explicitly
   local/dev hosts the user insists on).
3. **Normalize**: strip any trailing slash and any path — the base URL is scheme +
   host (+ port). `https://acme.konecty.com/` → `https://acme.konecty.com`.
4. **Probe**: `GET <url>/.well-known/oauth-protected-resource` must return **200**
   with a JSON body.
   - **404** → this Konecty does not expose MCP: "Seu Konecty ainda não expõe MCP —
     peça um upgrade do servidor, ou use a última versão deste pacote baseada em
     scripts (tag da release anterior à MCP-first)." Stop — do not register anything.
   - The JSON's `resource` field should equal `<url>/mcp`. A mismatch means the
     deployment's OAuth audience is misconfigured (`PLATFORM_MCP_RESOURCE_URL`):
     warn the user now — login would succeed but every MCP call would be rejected.
     See [references/troubleshooting.md](references/troubleshooting.md).

## Flow: first setup

1. Validate the URL (above).
2. Register the user MCP (template 1). If an old `konecty` entry exists
   (`claude mcp list`), remove it first.
3. Walk the user through the browser OAuth login: on the first tool call (or via
   `/mcp` in Claude Code) the browser opens → log into Konecty → the consent screen
   lists the requested scopes (`read`, and `write` when the namespace enables
   writes) → approve. Claude Code stores and refreshes the token automatically.
4. Verify: call a cheap tool (e.g. `modules_list`) and confirm it answers.
5. Offer the admin path (below) only if the user is a Konecty admin and wants
   metadata operations (konecty-meta).

## Flow: switch company URL ("trocar de empresa")

Replace, never duplicate:

1. Validate the new URL.
2. `claude mcp remove --scope user konecty` → re-add with the new URL.
3. If `konecty-admin` is registered, remove it too and re-add it for the new URL —
   the old admin token belongs to the old company; a **new OTP login** (or OAuth
   consent) against the new URL is required.
4. Browser OAuth will re-run on first use — that is expected.

## Flow: fix auth (re-login)

- **User MCP (OAuth)**: 401/UNAUTHORIZED on `konecty` tools → re-authenticate in
  Claude Code (`/mcp` → reconnect, browser login again). Nothing to reconfigure.
- **Admin MCP (interim token)**: 401 on `meta_*` tools → the `authTokenId` expired.
  Re-run the admin OTP path below and re-register the `konecty-admin` entry
  (remove + add with the fresh token).

## Flow: admin path

**Interim (today)** — Bearer `authTokenId` from an admin OTP login:

1. The user must be a Konecty admin (`admin: true`).
2. Run the OTP flow with the `session_*` tools on the **user MCP** (`konecty`
   server): `session_login_options` → `session_request_otp_email` /
   `session_request_otp_phone` → ask the user for the code →
   `session_verify_otp_email` / `session_verify_otp_phone` → returns `authId`.
   (The installer's `konecty-skills install` admin step does the same.)
3. Register the admin server with template 2, using `authId` as `<authTokenId>`.
   Remove any existing `konecty-admin` entry first.
4. Never echo or store the OTP code; the token lives only in the MCP entry header.

**Target (OAuth)** — once the deployment seeds a trusted client
(`OAUTH_CLIENTS_JSON` with `trustedFirstParty: true` and `admin` in
`allowedScopes`; recipe in Konecty's `docs/en/mcp.md`): switching is
re-registration only — remove `konecty-admin` and re-add with template 3
(`--client-id` + `--callback-port`, matching the client's registered redirect
port). At consent, `admin` appears **unchecked with a warning** and only for
users with `admin: true`. Nothing else changes.

## Troubleshooting

Every connection/permission error has a specific cause and remediation — see the
full matrix in [references/troubleshooting.md](references/troubleshooting.md)
(MCP disabled, role not allowlisted, read-only mode, audience mismatch, consent
screen missing, admin option not showing).
