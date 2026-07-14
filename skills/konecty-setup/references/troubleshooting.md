# Troubleshooting — Konecty MCP setup

Diagnose in this order: URL → MCP exposure → registration → auth → enablement.
Report the **specific cause** and remediation; never a generic "connection failed",
never improvised HTTP retries.

## Matrix

| Signal | What it means | Tell the user | Remediation |
|--------|---------------|---------------|-------------|
| URL unreachable (DNS/timeout/connection refused) | Wrong URL, VPN required, or server down | "Não consegui alcançar essa URL." | Confirm the exact company URL (and VPN if applicable); retry validation before registering anything. |
| `http://` URL | MCP setup requires TLS | "A URL precisa ser https." | Ask for the https address; only proceed with http for explicitly local/dev hosts. |
| **Well-known 404** — `GET <url>/.well-known/oauth-protected-resource` not found | Old Konecty without MCP support | "Seu Konecty ainda não expõe MCP." | Ask the company to upgrade Konecty, or pin the last script-based release tag of this skills package. Do not register the servers. |
| **Audience mismatch** — well-known 200 but `resource` ≠ `<url>/mcp`, or OAuth login succeeds and every `/mcp` call is rejected (invalid token/audience) | Deployment misconfiguration: `PLATFORM_MCP_RESOURCE_URL` (OAuth resource metadata) does not match the MCP URL | "O login funciona mas o servidor recusa o token — é configuração do servidor, não do seu acesso." | Server-side fix: align `PLATFORM_MCP_RESOURCE_URL` with the public MCP URL. The installer's `doctor` and the setup probe both detect this. |
| **503 — `mcp_disabled`** on `/mcp` | Namespace flag `mcpUserEnabled` is off | "O MCP está desativado neste Konecty." | A Konecty admin enables `mcpUserEnabled` on the namespace (via konecty-meta / admin MCP). |
| **503** on `/admin-mcp` | Namespace flag `mcpAdminEnabled` is off | "O MCP administrativo está desativado." | A Konecty admin enables `mcpAdminEnabled` (requires another working admin path). |
| **403 — `mcp_access_denied`** | User's role is not in `mcpRoleIds`. The list is **deny-by-default**: empty/absent means nobody has access | "Seu perfil ainda não está liberado para usar o MCP." | Admin adds the user's role `_id` to the namespace `mcpRoleIds`. |
| **`insufficient_scope`** on write tools | Read-only mode: `mcpUserWriteEnabled` absent or `false` strips the `write` scope | "Este ambiente está em modo somente leitura via MCP." | Reads keep working. Admin sets `mcpUserWriteEnabled: true` to allow writes. Do not retry the write. |
| **401 / UNAUTHORIZED** on `konecty` tools | OAuth access token expired/invalid and refresh failed | "Sua sessão expirou — é preciso entrar de novo." | Re-authenticate in Claude Code (reconnect the `konecty` server → browser login). |
| **401 / UNAUTHORIZED** on `konecty-admin` tools (interim path) | The Bearer `authTokenId` expired or was revoked | "O token de admin expirou." | Re-run the admin OTP flow → new `authTokenId` → `claude mcp remove --scope user konecty-admin` → re-add with the new header (SKILL.md, *fix auth*). |
| **Consent screen missing** — browser OAuth redirect dead-ends / blank page | The deployment does not host the consent SPA (`KONECTY_UI_URL` / `UI_PROXY` unset) | "A tela de login/consentimento não está publicada nesse servidor." | Server-side: the deployment must configure the Konecty UI (consent SPA). Until then, use the OTP paths (`session_*` tools; interim admin header). |
| **Admin option not showing at consent** (OAuth admin path) | The OAuth client is not a trusted client with `admin` allowed, or the user is not `admin: true`. DCR-registered clients are never trusted | "O escopo admin só aparece para clientes confiáveis e usuários admin." | The deployment seeds a trusted client via `OAUTH_CLIENTS_JSON` (`trustedFirstParty: true`, `admin` in `allowedScopes`, exact localhost redirect) — recipe in Konecty `docs/en/mcp.md` (Admin MCP via OAuth section). Then register with `--client-id`/`--callback-port`. Interim: keep the Bearer-header path. |
| **Duplicate `konecty*` entries** in `claude mcp list` | A previous setup was not removed before re-adding | — | `claude mcp remove --scope user <name>` for each duplicate, then a single fresh `add`. Replace, never duplicate. |
| **Consent denied** (`access_denied`) | The user declined the OAuth consent | "Sem o consentimento o acesso não é liberado." | Re-run the login and approve; only approve scopes the user is comfortable with. |
| **`claude` CLI absent** (`command -v claude` non-zero — typical in the desktop app) | No CLI to run `claude mcp add` | — (do not tell the user to "run commands manually") | The agent registers autonomously: edit `~/.claude.json` (or `$CLAUDE_CONFIG_DIR/.claude.json`) with the safe python3 write in SKILL.md (*Registration flow*, step 3), setting one `mcpServers.konecty` HTTP entry and preserving every other key. |
| **Server not appearing after config-write** (app) | Config is read on startup; there is no documented hot-reload | "Reinicie o app para carregar o servidor." | Restart the app, then `/mcp` → `konecty` → Authenticate. Restart + the consent click are the only manual steps. |
| **Entry rejected / not loaded** — a `mcpServers` entry has `url` but no `type` | Invalid schema: an HTTP entry MUST declare `"type":"http"` | "A entrada precisa de `\"type\":\"http\"`." | Fix the entry to `{"type":"http","url":"<url>/mcp"}` (the python3 write in SKILL.md always sets `type`). |
| **App OAuth won't complete** (no browser / headless-like app session) | The `/mcp` → Authenticate UX can't run | "Sem navegador, use o token Bearer." | Use the Bearer fallback: `konecty-admin` (or the user entry) with `headers: {"Authorization":"Bearer <authTokenId>"}` from an admin OTP login. OAuth stays the default when a browser is available. |

## Notes

- OAuth access tokens last ~1h; Claude Code refreshes them automatically (refresh
  token ~30d). Only a failed refresh needs a manual re-login.
- Enablement flags (`mcpUserEnabled`, `mcpAdminEnabled`, `mcpRoleIds`,
  `mcpUserWriteEnabled`) live on the Namespace and are changed via the admin MCP
  (konecty-meta, `meta_namespace_update`) — this skill only explains them.
- Data-operation errors (filters, locks, field permissions) are konecty-data
  territory: see that skill's `references/errors.md`.
