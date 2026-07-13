# Authentication — admin MCP

The admin MCP (`/admin-mcp`, registered as the `konecty-admin` server) requires a
token from a user with `admin: true`, sent through the HTTP `Authorization` header.
Tools are called **without** any token argument. Two auth paths exist:

## Interim path (today) — Bearer `authTokenId` from OTP

The `konecty-admin` MCP entry is registered with a static header:

```
Authorization: Bearer <authTokenId>
```

where `<authTokenId>` is the session token (`authId`) of an **admin** user obtained
via the OTP flow during setup (the `session_*` tools on the user MCP, or the
installer's admin step — see **konecty-setup**).

Properties and consequences:

- The token expires per the namespace's session policy. When `meta_*` calls start
  failing with `401`/`UNAUTHORIZED`, the token is stale: re-run the setup "fix auth"
  flow — new OTP login → new `authTokenId` → re-register the `konecty-admin` entry
  with the new header. There is nothing this skill can refresh by itself.
- The token belongs to a specific admin user; actions are audited as that user.
- Admin gating is enforced server-side: `admin: true` on the user AND
  `mcpAdminEnabled` on the namespace (503 when off).

## Target path — OAuth trusted client (ADR-0011)

Konecty supports granting the `admin` OAuth scope at consent for **trusted
clients**:

1. The client is provisioned server-side with `trustedFirstParty: true` — only
   possible via the deployment's `OAUTH_CLIENTS_JSON` (never via DCR).
2. The client's `allowedScopes` include `admin`.
3. The consenting user has `admin === true`.
4. The user **explicitly selects** `admin` on the consent screen (shown unchecked,
   with a risk warning).

The runtime gate is unchanged: the token must carry the `admin` scope **and** the
user must have `admin === true` — client trust alone never escalates.

**Switching is re-registration only**: once the deployment provisions the trusted
client, replace the `konecty-admin` entry — `claude mcp remove` + `claude mcp add`
with `--client-id <trusted-client>` and `--callback-port <registered-port>` (the
redirect URI is matched exactly). Nothing else in this skill changes. The
**konecty-setup** skill carries the command templates and the provisioning recipe
pointers.

## Errors

| Signal | Meaning | Next step |
|--------|---------|-----------|
| 503 (admin MCP unavailable) | `mcpAdminEnabled` is off | Enable it on the namespace (requires another working admin path) |
| 401 / `UNAUTHORIZED` | Interim token expired/invalid, or OAuth token rejected | Interim: re-run OTP + re-register header. OAuth: re-authenticate in Claude Code |
| 403 / FORBIDDEN on `meta_*` | User is not `admin: true`, or token lacks the `admin` scope | Use an admin user; on the OAuth path, ensure `admin` was selected at consent |
| Audience mismatch (token accepted nowhere) | Deployment's OAuth audience env vars misaligned with the MCP URL | Server-side fix — align `PLATFORM_MCP_RESOURCE_URL`; konecty-setup's doctor detects it |
