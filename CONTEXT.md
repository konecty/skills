# KonectySkills — Domain Language

Glossary for the KonectySkills repo. Pins the vocabulary that is easy to confuse when
skills talk to the Konecty platform — especially auth credentials and the MCP surfaces.
This is a glossary, not a spec: it defines what terms *mean*, never how anything is built.

## Auth & credentials

**authId**:
The opaque session token a user receives after logging in (OTP or password). This is the
single credential all skills store and send. In `~/.konecty/.env` it is `KONECTY_TOKEN`; in
MCP tool arguments it is `authTokenId`; in an HTTP header it is the `Bearer` value. All the
same string.
_Avoid_: "session token", "auth token", "API key", "authTokenId", "KONECTY_TOKEN" as if they
were different things — they are one authId wearing different clothes.

**First-party credential**:
An `authId` presented directly to Konecty. Konecty treats it as fully trusted — implicit
full scopes (`read`+`write`), subject only to namespace policy. This is what the skills use.
_Avoid_: "service account" (Konecty has no client-credentials grant), "API token".

**OAuth access token**:
A *different*, short-lived opaque token minted by the OAuth 2.1 authorization-code + PKCE
flow, carrying explicit scopes. Exists in Konecty but the skills do **not** use it.
_Avoid_: conflating with `authId` — an OAuth token is scoped and interactive to obtain; an
authId is not.

## MCP surfaces

**User MCP**:
The Konecty MCP server for data operations, served at `POST /mcp`. Read/write of records
(`records_find`, `query_json`, `query_sql`, create/update/…). What the search skills target.
_Avoid_: "the MCP" unqualified when the distinction from Admin MCP matters.

**Admin MCP**:
The separate MCP server for metadata/administration, served at `POST /admin-mcp`. Requires
the `admin` scope and `user.admin === true`. Out of scope for the search skills.

**Role allowlist** (`mcpRoleIds`):
The namespace setting that gates MCP access: a user's role `_id` must be listed, or every MCP
call returns `403 mcp_access_denied`. Deny-by-default — an empty/absent list denies everyone.
_Avoid_: "MCP permission", "MCP scope" (scopes are a different, orthogonal gate).

## Search & querying

**Search**:
The skill's read surface — the `find`, `query`, and `sql` subcommands of `konecty-data`.
Collectively "search", regardless of whether served by an MCP tool or the REST fallback.
_Avoid_: "query" as the umbrella term (here `query` is one specific subcommand: cross-module).

**KonFilter**:
Konecty's canonical filter shape: `{ match: 'and'|'or', conditions: [{ term, operator, value }],
filters?, textSearch? }`. What `find`'s `--filter` already takes and what the MCP validates.
_Avoid_: "Mongo filter" / "query object" — a raw `{ field: value }` map is **not** a KonFilter
and is rejected by the MCP.

**Transport**:
Which path served a given search: the **MCP transport** (`POST /mcp`, JSON-RPC over Streamable
HTTP) or the **REST transport** (`/rest/data/:document/find`, `/rest/query/*`). Same search
intent, two transports.
_Avoid_: "endpoint" when you mean the choice between the two paths.

**Fallback**:
Automatically re-running the *same search intent* on the REST transport after the MCP transport
is unavailable (endpoint absent, role not allow-listed, rate-limited, or unreachable). Exactly
one retry on the other transport — never a loop, never a partial merge.
_Avoid_: "retry" (a retry repeats the same transport; a fallback switches transport).
