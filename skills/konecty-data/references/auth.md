# Authentication — user MCP

The `konecty` MCP server is **stateless**: it keeps no MCP conversation auth
session. Every protected call carries its own token.

## OAuth (the only path)

The MCP host (e.g. Claude Code) handles the full OAuth handshake on its own:
browser login + consent on first use, token refresh afterwards. The access
token is sent as an `Authorization: Bearer` header on every call and resolved
server-side.

Call every tool as documented — there is no manual token argument to pass and
nothing to store or manage. Granted scopes are `read` (and `write` when the
namespace enables `mcpUserWriteEnabled`).

## Re-authenticating

If calls start failing with `401` / `UNAUTHORIZED`, the token expired or was
revoked. There is no manual login step: reconnect the MCP server (in Claude
Code, `/mcp` → reconnect/re-authorize `konecty`) so the host redoes the OAuth
handshake. Guide the user via **konecty-setup** ("fix auth") if reconnecting
does not resolve it.

## Admin note

Metadata operations authenticate differently (admin MCP, `konecty-admin`
server) — that is **konecty-meta** territory, not this skill.
