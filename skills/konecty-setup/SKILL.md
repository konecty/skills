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

# Admin MCP — default path (OAuth trusted client; browser login on first use)
claude mcp add --transport http --scope user konecty-admin <url>/admin-mcp --client-id <trusted-client-id> --callback-port <port>

# Admin MCP — fallback path (Bearer authTokenId from an admin OTP login; legacy / older Konecty)
claude mcp add --transport http --scope user konecty-admin <url>/admin-mcp --header "Authorization: Bearer <authTokenId>"

# Removal (always before re-adding — replace, never duplicate)
claude mcp remove --scope user konecty
claude mcp remove --scope user konecty-admin
```

Server names are fixed: `konecty` and `konecty-admin`. Registration is always
`--scope user` — the CRM follows the person across projects.

**When you (the setup agent) have a shell, run `claude mcp add` yourself** with the
URL the user gave — do not just print it. Registration is fully automatable; the one
unavoidable human step is clicking **Authenticate** and approving consent in the
browser (see *OAuth login by environment*).

**If the `claude` CLI is not available** in the current environment, do not fail:
print the exact commands above (with values filled in) for the user to run manually.

The **konecty-crm plugin ships skills only** and registers the MCP server through a
normal `claude mcp add`, so `/mcp` → Authenticate works for it. (Plugin-*embedded*
MCP servers cannot be `/mcp`-authenticated — that is not our case; do not tell users
to look for a plugin auth UI.)

## OAuth login by environment (not terminal-only)

OAuth login is done differently per environment. **The desktop app is a first-class
OAuth environment, not terminal-only.** Pick the row that matches where the session
runs:

| Environment | How the user authenticates |
|-------------|----------------------------|
| **CLI** and **desktop app** | In-app: `/mcp` → select the server → **Authenticate** → browser opens (callback `http://localhost:PORT/callback`). Also reachable via **Customize → Connectors**. Tokens are stored in the OS keychain. |
| **claude.ai (web)** | NOT inside Claude Code. The user adds/authenticates the server at **claude.ai/customize/connectors**; it then appears in Claude Code sessions (manage/view with `/mcp`). |
| **Headless / SSH / `claude -p` / no browser** | Either (a) `claude mcp login <name> --no-browser` — prints an auth URL to open on a machine with a browser, then paste the redirect back (needs an interactive TTY, e.g. `ssh -t`); or (b) the **Bearer-token fallback** — register with `--header "Authorization: Bearer <authTokenId>"` (authTokenId from the Konecty OTP flow), which bypasses the browser entirely and works for BOTH `konecty` and `konecty-admin`; or (c) `headersHelper` in `.mcp.json` for rotating tokens. |

**If konecty-setup itself is running where no browser can open** (headless / `-p` /
SSH without a display): do **not** dead-end at "use the terminal". Instead: (i) still
complete the `claude mcp add` registration, then (ii) tell the user they can finish
auth by opening the **same project in the desktop app or CLI** and running `/mcp` →
**Authenticate**, OR use the `--no-browser` paste flow, OR the Bearer-token fallback
above. Never leave the user without a path.

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
3. Walk the user through the OAuth login using the row for their environment (see
   *OAuth login by environment*): in the CLI/desktop app it is `/mcp` → Authenticate
   (browser); on claude.ai web it is claude.ai/customize/connectors; headless uses
   `--no-browser` or the Bearer fallback. On the consent screen the user approves the
   requested scopes (`read`, and `write` when the namespace enables writes). Claude
   Code stores and refreshes the token automatically.
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
- **Admin MCP (OAuth, default)**: 401/UNAUTHORIZED on `meta_*` tools →
  re-authenticate in Claude Code (`/mcp` → `konecty-admin` → reconnect, browser
  login again). Nothing to reconfigure.
- **Admin MCP (OTP fallback token)**: 401 on `meta_*` tools when using the
  Bearer path → the `authTokenId` expired. Re-run the admin OTP path below and
  re-register the `konecty-admin` entry (remove + add with the fresh token).

## Flow: admin path

**Default (OAuth trusted client)** — no stored token; the `admin` scope is
granted at the browser consent on first use:

1. The user must be a Konecty admin (`admin: true`).
2. The deployment must seed a trusted first-party client via `OAUTH_CLIENTS_JSON`
   (`trustedFirstParty: true` and `admin` in `allowedScopes`; recipe in
   Konecty's `docs/en/mcp.md`). Its registered redirect URI must be exactly
   `http://localhost:<port>/callback`.
3. Register the admin server with template 2 (`--client-id` + `--callback-port`,
   the port matching the client's registered redirect port). Documented example
   values: client id `claude-code-admin`, callback port `19819`. Remove any
   existing `konecty-admin` entry first. (The installer's `konecty-skills
   install` admin step does the same by default.)
4. Login happens on **first use**, per the *OAuth login by environment* matrix
   (CLI/desktop app: `/mcp` → pick `konecty-admin` → Authenticate → browser;
   web: claude.ai/customize/connectors; headless: `--no-browser` or Bearer). At
   consent, `admin` appears **unchecked with a warning** and only for users with
   `admin: true`. Approve it. Nothing is stored on disk — Claude Code holds and
   refreshes the token.
5. If the `admin` option does not appear at consent, the trusted client is not
   seeded (or the user is not an admin) — see
   [references/troubleshooting.md](references/troubleshooting.md).

**Fallback (interim OTP → Bearer)** — for older Konecty without the trusted
client, or when explicitly requested (`konecty-skills install --admin-auth otp`):

1. The user must be a Konecty admin (`admin: true`).
2. Run the OTP flow with the `session_*` tools on the **user MCP** (`konecty`
   server): `session_login_options` → `session_request_otp_email` /
   `session_request_otp_phone` → ask the user for the code →
   `session_verify_otp_email` / `session_verify_otp_phone` → returns `authId`.
3. Register the admin server with template 3, using `authId` as `<authTokenId>`.
   Remove any existing `konecty-admin` entry first.
4. Never echo or store the OTP code; the token lives only in the MCP entry header.

## Troubleshooting

Every connection/permission error has a specific cause and remediation — see the
full matrix in [references/troubleshooting.md](references/troubleshooting.md)
(MCP disabled, role not allowlisted, read-only mode, audience mismatch, consent
screen missing, admin option not showing).
