# Find via MCP — Specification

## Problem Statement

The `konecty-data` skill's search surface (`find.py` → `find` / `query` / `sql`) talks to the
legacy REST endpoints (`/rest/data/:document/find`, `/rest/query/json`, `/rest/query/sql`). Konecty
now ships a first-class **User MCP** server (`POST /mcp`, stateless Streamable HTTP) whose
`records_find` / `query_json` / `query_sql` tools call the *same* internal `find()`/`crossModuleQuery()`
functions in-process — with filter discipline (`KonFilter`), a normalized pagination envelope, and a
supported forward path. We want the skill's search to speak MCP so it rides the platform's intended,
maintained interface, while staying resilient on environments where MCP is unavailable or the caller's
role is not yet allow-listed.

## Goals

- [ ] `find` / `query` / `sql` subcommands issue their reads through the User MCP tools
      (`records_find`, `query_json`, `query_sql`) over `POST /mcp` using stdlib only.
- [ ] Authenticate with the **existing legacy token** (`KONECTY_TOKEN` from `~/.konecty/.env`) sent as
      `Authorization: Bearer <authId>` — no OAuth flow introduced.
- [ ] **Automatic REST fallback**: when MCP is absent, unauthorized-by-allowlist, or unreachable, the
      command transparently falls back to the current REST path and still returns results, emitting a
      one-line notice.
- [ ] Preserve the existing **stdout output contract** (records array on stdout, summary/notices on
      stderr) so downstream `jq` pipelines keep working.
- [ ] The MCP client is protocol-complete enough to call complementary tools/resources on demand
      (`records_find_by_id`, widget resource-links) without exposing them as new subcommands.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| OAuth 2.1 authorization-code / PKCE / dynamic client registration | Legacy token already authenticates to `/mcp`; no `client_credentials` grant exists, so OAuth would force an interactive browser flow — rejected by user decision. |
| Migrating `create` / `update` / `delete` / `upload` to MCP | Scope is the search surface only (find/query/sql); other data ops stay on REST. |
| Admin MCP (`/admin-mcp`) and any `konecty-meta` change | This feature touches `konecty-data` search only. |
| Exposing `records_find_by_id`, `render_records_widget`, pivot/graph as skill subcommands | Separate feature. |
| Any follow-up-tool / widget handling (`records_find_by_id`, `render_records_widget`, `ui://widget/*`) | **Cut after grilling (ADR — YAGNI).** A headless CLI that emits records to stdout never receives a response that *requires* a follow-up: `records_find` already returns full records in `structuredContent.records`, and widgets are tools a *conversational* agent chooses to call — the server never asks the client to call them. The MCP client is a generic `tools/call` caller but the skill only ever invokes `records_find` / `query_json` / `query_sql` and reads only `structuredContent`; anything else in a response is ignored by construction. |
| Changing `~/.konecty/.env` format or the OTP session flow (`auth.py`) | Auth acquisition is unchanged; only how the token is *presented* to `/mcp` changes. |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Auth header format on `/mcp` | `Authorization: Bearer <authId>` | Verified in `user/server.ts:31-44`: server strips optional `Bearer `; both raw and Bearer resolve identically. Bearer is MCP-idiomatic. | y |
| Compat strategy | MCP-first with automatic REST fallback | User decision. Covers old Konecty (no `/mcp`) and non-allow-listed roles. | y |
| Behavior on 403 (`mcp_access_denied` / `insufficient_scope`) | Fall back to REST **and** emit a one-line stderr notice that direct (REST) search is being used | User decision. | y |
| Filter construction | Build the canonical `KonFilter` shape (`{match, conditions[], textSearch?}`) **locally in Python**; do NOT make an extra `filter_build` tool round-trip | `records_find.filter` is `z.unknown()` validated downstream by `KonFilter`/`normalizeKonectyFilter`; the canonical shape is simple and already documented in `references/find.md`. Avoids a second network hop per search. **Design spike must confirm a locally-built filter passes `normalizeKonectyFilter`.** | n (design spike) |
| Stateless transport handshake | **SPIKE**: determine whether a single `POST /mcp` must carry `initialize`+`initialized`+`tools/call` batched, or whether stateless mode accepts a bare `tools/call`. Client implementation follows the spike result. | Server creates a fresh `McpServer` per POST (`transport.ts:44-62`); an `initialize` in a prior POST does not persist. | n (design spike) |
| Response encoding | **SPIKE**: confirm required `Accept` header (`application/json, text/event-stream`) and whether the reply is SSE (`text/event-stream`) or plain JSON; client must parse whichever the server returns. | Streamable HTTP SDK commonly requires both Accept types and may stream SSE frames. | n (design spike) |
| Timeout / retry policy | Single MCP attempt with a bounded connect+read timeout (default 30s, overridable); on failure, exactly one REST fallback attempt — no retry storms | Keeps a CLI call deterministic and fast; fallback already covers the failure. | y (default) |
| Nested-filter divergence (5b) | Send nested filters to MCP unchanged; **document the divergence prominently** (`references/find.md` "Known divergences") and fix it Konecty-side, not in the skill | Grilling decision + ADR-0008. MCP's `KonFilter` zod-strips `filters` nested 2+ levels → returns a superset vs REST, silently. Rare (filter_build never generates it); putting server-bug knowledge in the skill is the wrong layer. Guidance: use `KONECTY_MCP=0` for deep filters until the Konecty fix lands. | y |
| Transport observability | Notice **only on fallback**, as a short sentence emitted **first** (stderr, before records), e.g. `Busca feita via API direta (REST).` Happy MCP path is silent. | Grilling decision. Keeps stdout a clean records array for `jq` while making a fallback visible up-front. | y |
| Rate-limit (429) handling | On the first `429`, fall back **and disable MCP for the rest of the process** — subsequent calls go straight to REST (one notice, not one per page) | Grilling decision + ADR-0007. MCP User rate limit is 60/min per token; deep pagination would otherwise 429+notice every page after the 60th. Per-process (each CLI run is a fresh process). | y |
| `withDetailFields` | Not exposed as a new CLI flag in this feature; default (omitted) | Preserves current `find` surface; can be added later. | y |
| Output contract | records array (MCP `structuredContent.records`, or REST `data`) to stdout; `# Total / Returned` + fallback notice to stderr | Matches current `find.py` behavior so pipelines are unaffected. | y |
| mcpUserWriteEnabled / write scope | Irrelevant — all three subcommands are read-only (`READ_ONLY` annotation on `records_find`); only `read` scope needed | Search never writes. | y |

**Open questions:** none — all resolved or logged above. The two SPIKE rows are design-phase
investigations with a defined resolution path, not unresolved product ambiguity.

---

## User Stories

### P1: Search a single module through `records_find` ⭐ MVP

**User Story**: As a user of the `konecty-data` skill, I want `find <Document>` to retrieve records
through the Konecty User MCP so that search rides the platform's maintained interface, while still
returning the same output shape I pipe into `jq`.

**Why P1**: This is the core migration and the vertical slice — auth + protocol client + fallback +
output contract all exercised by one command.

**Acceptance Criteria**:

1. WHEN `find <Document>` runs with a reachable, allow-listed MCP THEN the skill SHALL call the
   `records_find` tool over `POST /mcp` and print the returned records array to stdout as the current
   command does (pretty JSON by default, NDJSON with `--output ndjson`).
2. WHEN a `--filter` is supplied THEN the skill SHALL send it to `records_find` as a canonical
   `KonFilter` object (`{match, conditions[], textSearch?}`), passing it through unchanged.
   WHEN the `--filter` value is **not valid JSON** THEN the skill SHALL reject it locally with a clear
   error before any network call. (A *valid-JSON but Mongo-shaped* filter is forwarded and rejected
   **server-side** by `normalizeKonectyFilter` — surfaced as a tool-validation error, no REST fallback;
   the skill does not attempt to detect Mongo shape locally.)
3. WHEN the MCP request carries the auth token THEN it SHALL be sent as
   `Authorization: Bearer <KONECTY_TOKEN>`.
4. WHEN `records_find` returns THEN the skill SHALL print `# Total: N  Returned: M` to **stderr**
   (from the MCP `pagination.total` / returned count) and the records to **stdout**.
5. WHEN `--limit` / `--start` / `--fields` / `--sort` are given THEN they SHALL map to the
   `records_find` `limit` / `start` / `fields` (csv) / `sort` (`[{property, direction}]`) inputs, with
   the current defaults (`limit=50`, `start=0`).

**Independent Test**: Point the skill at a mock `/mcp` that implements `records_find`; run
`find Contact --filter '{...}'`; assert stdout equals the mock's records and stderr shows the total.

---

### P1: Authenticate to `/mcp` with the legacy token ⭐ MVP

**User Story**: As an already-authenticated user, I want the skill to reuse my existing
`~/.konecty/.env` token for MCP so that no new login/OAuth step is required.

**Why P1**: Without working auth the MCP path is inert; the whole point is zero new credential burden.

**Acceptance Criteria**:

1. WHEN credentials are loaded THEN the skill SHALL read `KONECTY_URL` + `KONECTY_TOKEN` via the
   existing precedence (env → `~/.konecty/.env` → `~/.konecty/credentials`) unchanged.
2. WHEN credentials are missing THEN the skill SHALL exit non-zero with the current clear
   missing-credential message before attempting MCP or REST.
3. WHEN the MCP returns `401 unauthorized` (bad/expired token, not an allowlist issue) THEN the skill
   SHALL surface an auth error advising re-login — it SHALL NOT silently fall back (a bad token would
   fail REST too).

**Independent Test**: Run with no token → asserts the missing-credential exit; run against a mock that
401s → asserts an auth-error message and non-zero exit.

---

### P1: Automatic REST fallback with notice ⭐ MVP

**User Story**: As a user on an environment where MCP is unavailable or my role isn't allow-listed, I
want search to keep working via REST so that the migration never regresses my ability to find records.

**Why P1**: Fallback is the safety net that makes MCP-first shippable without breaking anyone.

**Acceptance Criteria**:

1. WHEN `POST /mcp` returns `404` (endpoint absent — old Konecty) THEN the skill SHALL retry the
   request against the current REST endpoint and return its result **silently** (no notice — MCP is
   expected to be absent there).
2. WHEN `POST /mcp` returns `403` (`mcp_access_denied` / `insufficient_scope`), `429`, `5xx`, or fails
   with a connection error / timeout / DNS failure / malformed SSE THEN the skill SHALL fall back to
   REST **and** emit a short notice **first** on stderr, before the records, e.g.
   `Busca feita via API direta (REST).`
3. WHEN the MCP path succeeds THEN the skill SHALL emit **no** transport notice (happy path is silent).
4. WHEN `POST /mcp` returns `429` THEN in addition to falling back, the skill SHALL **disable MCP for
   the remainder of the process** so subsequent calls (e.g. pagination pages) go straight to REST —
   one notice, not one per page.
5. WHEN a fallback occurs THEN the stdout records output SHALL be identical in shape to the MCP path
   (records array), so downstream `jq` consumers are unaffected by which transport served the request.
6. WHEN both MCP and the REST fallback fail THEN the skill SHALL exit non-zero surfacing the REST
   error (the actionable one), not swallow it.

**Independent Test**: Mock `/mcp` to 404/403/refuse-connection; assert REST endpoint is called and the
correct stderr notice (or silent, for 404) appears; assert exit code and stdout.

---

### P2: Cross-module `query` and raw `sql` through MCP tools

**User Story**: As a user, I want `query <Document> --relations …` and `sql "<SELECT …>"` to run
through the `query_json` / `query_sql` MCP tools so that cross-module and SQL search share the same
MCP path and fallback as `find`.

**Why P2**: Same migration pattern, but `find` proves the slice first; query/sql reuse the client +
fallback machinery.

**Acceptance Criteria**:

1. WHEN `query <Document>` runs THEN the skill SHALL call `query_json` with the document, filter,
   relations, and paging inputs, preserving the current default `--limit 1000` and total behavior.
2. WHEN `sql "<SELECT …>"` runs THEN the skill SHALL call `query_sql` with the SQL string and
   `include-meta` / total options preserved.
3. WHEN `query` / `sql` hit an MCP-unavailable / 403 / error condition THEN they SHALL fall back to
   `/rest/query/json` / `/rest/query/sql` with the same notice policy as P1.
4. WHEN `query_json` / `query_sql` return NDJSON-equivalent rows THEN the skill SHALL preserve the
   current `_meta`-line separation and stdout row output.

**Independent Test**: Mock `query_json` / `query_sql`; run `query` and `sql`; assert MCP tool called,
output rows match, and 403 triggers REST fallback.

---

### P2: Stateless MCP protocol client (stdlib)

**User Story**: As the skill author, I want a small, correct MCP-over-HTTP client in stdlib so that
tool calls succeed against the stateless Streamable-HTTP server regardless of SSE vs JSON responses.

**Why P2**: Enabling infrastructure for P1/P2 stories; isolated so it can be unit-tested directly.

**Acceptance Criteria**:

1. WHEN the client issues a `tools/call` THEN it SHALL send the JSON-RPC 2.0 envelope with
   `Accept: application/json, text/event-stream` (both required — 406 otherwise, **spike-confirmed**),
   `Content-Type: application/json`, and `Authorization: Bearer <token>`.
2. WHEN the server replies THEN the client SHALL parse the **SSE** stream (`text/event-stream`) — Konecty
   runs the transport without `enableJsonResponse`, so the reply is always SSE (**spike-confirmed**) — and
   extract the JSON-RPC result. It SHALL also accept a plain `application/json` body (defensive) so a future
   JSON-mode server still works.
3. WHEN issuing `tools/call` THEN the client SHALL send it **directly, with no `initialize` handshake** —
   the stateless server dispatches by method name and a batched handshake is rejected (**spike-confirmed**).
4. WHEN the response carries a JSON-RPC `error` or a `result.isError` THEN the client SHALL raise
   `McpToolError`; WHEN the HTTP status is non-2xx THEN `McpHttpError` (carrying `.status`); WHEN the
   connection/stream fails THEN `McpTransportError` — so callers branch surface-vs-fallback correctly.

**Independent Test**: Feed the client canned SSE (and JSON) bytes; assert it extracts the same result
object; assert `error`/`isError` → `McpToolError`, non-2xx → `McpHttpError`, conn-drop → `McpTransportError`.

---

### ~~P3: Handle complementary tools/resources on demand~~ — CUT (grilling, YAGNI)

**Removed after grilling.** The search path never receives a response that *requires* a follow-up tool
call or widget render: `records_find` returns full records in `structuredContent.records`; widgets are
tools a conversational agent *chooses* to call, never something the server asks the client to call. The
MCP client is a generic `tools/call` caller (it *can* call any tool), but the skill only ever invokes
`records_find` / `query_json` / `query_sql` and reads only `structuredContent` — any widget-link or extra
`content` block in a response is ignored by construction, not by a dedicated code path. Recorded in the
Out of Scope table.

---

## Edge Cases

- WHEN `document` is a human label instead of its technical name (e.g. "Contato" vs "Contact") THEN
  `records_find` returns `buildInvalidDocumentError`; the skill SHALL surface that (a **tool validation
  error → no fallback**, per the matrix — a bad identifier must not be masked by REST). Note: the module
  *name* the skill passes today (`Contact`) IS the accepted identifier on both paths — verified identical.
- WHEN `--sort` uses the CLI shorthand (`field:asc,other:desc`) THEN `_parse_sort` normalizes it to
  `{property, direction:UPPER}` before sending. A raw Mongo-style JSON sort (`{"field":-1}`) is **not**
  normalized locally — it is forwarded and rejected server-side (surfaced, safe). Local Mongo-sort
  detection is intentionally out of scope.
- WHEN the MCP rate limit (`429`) is hit THEN the skill SHALL fall back to REST **and disable MCP for the
  rest of the process** (see P1 fallback AC-4).
- WHEN `--filter` has `filters` nested 2+ levels THEN the skill SHALL send it to MCP unchanged; the MCP may
  return a **superset** of records (known divergence, ADR-0008) — documented, fixed Konecty-side, mitigated
  by `KONECTY_MCP=0`.
- WHEN `--limit -1` (no limit) is used THEN the skill SHALL pass `-1` through to `records_find` unchanged —
  verified identical to REST (`find()` treats `-1` as no-limit on both paths).
- WHEN the SSE stream is truncated / malformed THEN the client SHALL treat it as an MCP transport failure
  and fall back to REST.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| FMCP-01 | P1: records_find search | Execute | Implemented (T6) |
| FMCP-02 | P1: local canonical filter build + reject malformed | Execute | Implemented (T6) |
| FMCP-03 | P1: Bearer legacy-token auth | Execute | Implemented (T2, T6) |
| FMCP-04 | P1: stdout/stderr output contract preserved | Execute | Implemented (T6) |
| FMCP-05 | P1: CLI arg → records_find input mapping | Execute | Implemented (T6) |
| FMCP-06 | P1: missing-credential + 401 auth error (no silent fallback) | Execute | Implemented (T5) |
| FMCP-07 | P1: fallback on 404 (silent) | Execute | Implemented (T5) |
| FMCP-08 | P1: fallback on 403/429/5xx/conn/timeout/bad-SSE with short notice emitted first | Execute | Implemented (T5) |
| FMCP-09 | P1: happy MCP path emits no transport notice | Execute | Implemented (T5) |
| FMCP-10 | P1: fallback output shape identical to MCP | Execute | Implemented (T6) |
| FMCP-11 | P1: both-fail surfaces REST error, non-zero exit | Execute | Implemented (T5) |
| FMCP-12 | P1: 429 disables MCP for the rest of the process | Execute | Implemented (T5) |
| FMCP-13 | P2: query → query_json with fallback | Execute | Implemented (T7) |
| FMCP-14 | P2: sql → query_sql with fallback | Execute | Implemented (T8) |
| FMCP-15 | P2: query/sql `_meta` reconstructed (re-add success+total to MCP `meta`) | Execute | Implemented (T7, T8) |
| FMCP-16 | P2: JSON-RPC envelope + required Accept (both types) + auth header | Execute | Implemented (T2) |
| FMCP-17 | P2: SSE response parsing (Konecty runs SSE, not JSON mode) | Execute | Implemented (T1) |
| FMCP-18 | P2: typed error for JSON-RPC error vs HTTP failure vs transport failure | Execute | Implemented (T1, T2) |
| FMCP-19 | Cross: nested-filter divergence documented (ADR-0008), sent unchanged | Execute | Implemented (T9) |

**Coverage:** 19 total, 0 mapped to tasks yet, 0 unmapped. (P3 removed; FMCP-17 simplified — spike
resolved: no `initialize` handshake, response is always SSE.)

---

## Success Criteria

- [ ] `find` / `query` / `sql` return correct results through MCP against a live/mocked MCP, byte-for-byte
      compatible stdout with the pre-migration output.
- [ ] With MCP disabled (404) or role not allow-listed (403), the same commands still succeed via REST,
      with the specified stderr notice on 403.
- [ ] No new pip dependency; `make check` (offline gate) passes and stays stdlib-only.
- [ ] e2e coverage stays ≥ 90%; new MCP client + fallback paths are covered by the harness
      (mock `/mcp` for both SSE and JSON responses + fallback branches).
- [ ] OAuth is not introduced; only the token-presentation format changes to `Bearer`.
