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

## Registration mechanisms (single source of truth)

There are two ways to register the user-scope servers; the agent picks by
environment (see *Registration flow*). `<url>` is the normalized base URL (see
*URL validation*). Server names are fixed: `konecty` and `konecty-admin`.
Registration is always **user scope** — the CRM follows the person across
projects. **OAuth is the default in both mechanisms**; Bearer/OTP is a fallback
only (legacy / no-browser).

### A. `claude` CLI commands (when the CLI is available)

These are exactly the commands the `konecty-skills` installer runs.

```bash
# User MCP (data + OAuth login)
claude mcp add --transport http --scope user konecty <url>/mcp

# Admin MCP — default (OAuth trusted client; browser login on first use)
claude mcp add --transport http --scope user konecty-admin <url>/admin-mcp --client-id claude-code-admin --callback-port 19819

# Admin MCP — fallback (Bearer authTokenId from an admin OTP login; legacy Konecty)
claude mcp add --transport http --scope user konecty-admin <url>/admin-mcp --header "Authorization: Bearer <authTokenId>"

# add-json alternative (same entry as the JSON below)
claude mcp add-json konecty '{"type":"http","url":"<url>/mcp"}'

# Removal (always before re-adding — replace, never duplicate)
claude mcp remove --scope user konecty
claude mcp remove --scope user konecty-admin
```

### B. Config-file entries (when the CLI is absent — the desktop app)

User-scope servers live under the top-level `mcpServers` object in
`~/.claude.json` (config home is `$CLAUDE_CONFIG_DIR/.claude.json` when
`CLAUDE_CONFIG_DIR` is set, else `~/.claude.json`). **Both the CLI and the
desktop app read this file**, and user-scope servers here have **no**
pending-approval gate (that gate is only for project `.mcp.json`).

Every entry MUST have `"type":"http"` — an entry with `url` but no `type` is an
error.

```jsonc
// User MCP (OAuth default, DCR)
"konecty": {"type":"http","url":"<url>/mcp"}

// Admin MCP (OAuth trusted client) — admins only
"konecty-admin": {"type":"http","url":"<url>/admin-mcp","oauth":{"clientId":"claude-code-admin","callbackPort":19819}}

// Bearer fallback (NOT default — legacy / no-browser)
"konecty-admin": {"type":"http","url":"<url>/admin-mcp","headers":{"Authorization":"Bearer <authTokenId>"}}
```

## Registration flow (environment-aware, autonomous)

The agent registers the servers **end-to-end**. Never dead-end by printing
commands for the user to run.

### 1. Validate the URL (see *URL validation*) — abort cleanly if it fails.

### 2. Detect the environment

```bash
command -v claude
```

- **Exit 0 (CLI available)** → use mechanism **A**. Replace-not-duplicate: if an
  entry already exists (`claude mcp list`), `claude mcp remove --scope user
  <name>` first, then add.
- **Non-zero (CLI absent — the app)** → use mechanism **B**: the agent edits
  `~/.claude.json` itself with the python3 procedure below. Do NOT dead-end.

### 3. Write the config safely (app path)

Substitute the real `<url>`, then run. This reads the file (missing → `{}`),
ensures `mcpServers`, sets exactly one `konecty` entry (replacing any existing —
never duplicating), and writes back with `indent=2` **preserving every other
key**. It NEVER overwrites the whole file and NEVER touches other keys.

```python
python3 - <<'PY'
import json, os
home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~")
path = os.path.join(home, ".claude.json")
try:
    with open(path) as f:
        cfg = json.load(f)
except FileNotFoundError:
    cfg = {}
cfg.setdefault("mcpServers", {})
# User MCP — OAuth default (DCR). Replace, never duplicate.
cfg["mcpServers"]["konecty"] = {"type": "http", "url": "<url>/mcp"}
# Admin MCP (admins only, if they want metadata ops) — OAuth trusted client.
# Uncomment to add it:
# cfg["mcpServers"]["konecty-admin"] = {
#     "type": "http", "url": "<url>/admin-mcp",
#     "oauth": {"clientId": "claude-code-admin", "callbackPort": 19819}}
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
print("wrote", path)
PY
```

### 4. Finish (by environment)

- **CLI**: the first `konecty` tool call (or `/mcp` → `konecty` → Authenticate)
  opens the browser for OAuth login. Claude Code stores and refreshes the token.
- **App**: tell the user to **restart the app** — config is read on startup and
  there is no documented hot-reload — then `/mcp` → `konecty` → **Authenticate**
  opens the browser. The restart and that one consent click are the only manual
  steps (consent is human-by-design).

  *Honesty caveat:* the app config-write and the app reading `~/.claude.json` are
  doc-confirmed. The app `/mcp` → Authenticate browser UX is the documented
  OAuth mechanism but **not yet empirically verified by us** — present it as the
  expected flow. If OAuth can't be completed (no browser), the **Bearer
  fallback** (mechanism B admin entry / `headers` on the user entry) is the
  guaranteed-no-browser alternative.

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
2. Register the user MCP via the **Registration flow** — detect the environment
   and use mechanism A (CLI) or B (app config-write). Replace any old `konecty`
   entry first, never duplicate.
3. Finish the OAuth login per environment (Registration flow step 4): CLI opens
   the browser on first tool call (or `/mcp` → Authenticate); the app needs a
   restart then `/mcp` → `konecty` → Authenticate. At consent the requested
   scopes (`read`, and `write` when the namespace enables writes) are listed →
   approve. Claude Code stores and refreshes the token automatically.
4. Verify: call a cheap tool (e.g. `modules_list`) and confirm it answers.
5. Offer the admin path (below) only if the user is a Konecty admin and wants
   metadata operations (konecty-meta).

## Flow: switch company URL ("trocar de empresa")

Replace, never duplicate:

1. Validate the new URL.
2. Re-register `konecty` for the new URL via the Registration flow (CLI: `remove`
   then add; app: the python3 write overwrites the single `konecty` entry).
3. If `konecty-admin` is registered, re-register it for the new URL the same way —
   the old admin token belongs to the old company; a **new OAuth consent** (or
   OTP login on the fallback path) against the new URL is required.
4. Browser OAuth will re-run on first use (app: after restart) — that is expected.

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
3. Register the `konecty-admin` server via the Registration flow's OAuth admin
   form — CLI: the `--client-id claude-code-admin --callback-port 19819` command;
   app: the commented `konecty-admin` block in the python3 write, with the
   `oauth` `{clientId, callbackPort}` object. The port must match the client's
   registered redirect port. Remove/replace any existing `konecty-admin` entry
   first. (The installer's `konecty-skills install` admin step does the same by
   default.)
4. Login happens on **first use**: `/mcp` in Claude Code → pick `konecty-admin`
   → Authenticate → the browser opens. At consent, `admin` appears **unchecked
   with a warning** and only for users with `admin: true`. Approve it. Nothing
   is stored on disk — Claude Code holds and refreshes the token.
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
3. Register the admin server with the Bearer form, using `authId` as
   `<authTokenId>` — CLI: the `--header "Authorization: Bearer ..."` command;
   app: the Bearer-fallback JSON entry (`headers` object). Remove/replace any
   existing `konecty-admin` entry first.
4. Never echo or store the OTP code; the token lives only in the MCP entry header.

## Troubleshooting

Every connection/permission error has a specific cause and remediation — see the
full matrix in [references/troubleshooting.md](references/troubleshooting.md)
(MCP disabled, role not allowlisted, read-only mode, audience mismatch, consent
screen missing, admin option not showing).
