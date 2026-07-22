# Authentication — admin MCP

The admin MCP (`/admin-mcp`, registered as the `konecty-admin` server) requires a
token from a user with `admin: true`, sent through the HTTP `Authorization` header.
Tools are called **without** any token argument.

## OAuth trusted client (ADR-0011) — the only path

Konecty grants the `admin` OAuth scope at consent to **trusted clients** only:

1. The client is provisioned server-side with `trustedFirstParty: true` — only
   possible via the deployment's `OAUTH_CLIENTS_JSON` (never via DCR). The
   default trusted client for admin work is `claude-code-admin`.
2. The client's `allowedScopes` include `admin`.
3. The consenting user has `admin === true`.
4. The user **explicitly selects** `admin` on the consent screen (shown unchecked,
   with a risk warning).

The runtime gate is unchanged: the token must carry the `admin` scope **and** the
user must have `admin === true` — client trust alone never escalates.

Registration uses `--client-id <trusted-client>` / `--callback-port
<registered-port>` on `claude mcp add` (the redirect URI is matched exactly) —
see **konecty-setup** for the command templates and the provisioning recipe
pointers.

## Re-authenticating

If `meta_*` calls start failing with `401`/`UNAUTHORIZED`, the token expired or
was revoked. Reconnect/re-authorize the `konecty-admin` server (in Claude Code,
`/mcp` → reconnect) so the host redoes the OAuth handshake. Admin gating is
enforced server-side: `admin: true` on the user AND `mcpAdminEnabled` on the
namespace (503 when off).

## Errors

| Signal | Meaning | Next step |
|--------|---------|-----------|
| 503 (admin MCP unavailable) | `mcpAdminEnabled` is off | Enable it on the namespace (requires another working admin path) |
| 401 / `UNAUTHORIZED` | OAuth token expired or rejected | Reconnect/re-authorize the `konecty-admin` server |
| 403 / FORBIDDEN on `meta_*` | User is not `admin: true`, or token lacks the `admin` scope | Use an admin user; ensure `admin` was selected at consent |
| Audience mismatch (token accepted nowhere) | Deployment's OAuth audience env vars misaligned with the MCP URL | Server-side fix — align `PLATFORM_MCP_RESOURCE_URL`; konecty-setup's doctor detects it |
