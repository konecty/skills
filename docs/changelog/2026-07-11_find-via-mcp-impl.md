# Changelog: find-via-mcp implementation (konecty-data search over User MCP)

## Date

2026-07-11

## Summary

Implemented the `find-via-mcp` feature: `konecty-data`'s `find` / `query` / `sql` now read through the
Konecty **User MCP** server (`POST /mcp`, stateless Streamable HTTP) with automatic REST fallback,
stdlib only. Delivered across 10 atomic tasks (T1–T10) on `feat/find-via-mcp`.

- **New `skills/konecty-data/scripts/mcp_client.py`** — a minimal stdlib MCP-over-HTTP client: a bare
  JSON-RPC 2.0 `tools/call` (no `initialize` handshake), `Accept: application/json, text/event-stream`,
  `Authorization: Bearer <authId>`, an SSE parser (`parse_sse`, with a defensive plain-JSON path), and
  three typed errors — `McpHttpError(.status)`, `McpTransportError`, `McpToolError` — so callers branch
  surface-vs-fallback.
- **`find.py` dispatcher (`_dispatch`) + fallback matrix** — MCP-first with `KONECTY_MCP` env switch
  (`1`/unset = MCP-first, `0` = REST-only, `only` = strict/no-fallback). Matrix: 404 → REST silent;
  403/429/5xx/conn/timeout/bad-SSE → REST + one-line stderr notice emitted first (`Busca feita via API
  direta (REST).`); 429 additionally disables MCP for the rest of the process; 401 and tool-validation
  errors are surfaced (no fallback); both-fail surfaces the REST error.
- **`find` → `records_find`**, **`query` → `query_json`**, **`sql` → `query_sql`** — CLI args mapped to
  tool inputs; the REST bodies became `_rest_find`/`_rest_query`/`_rest_sql` fallbacks (nothing deleted).
  Output adapters preserve the stdout records array + `# Total: N  Returned: M` stderr summary;
  `_reconstruct_query_meta` re-adds `success` and folds `total` back into the bare MCP `meta` so
  `query`/`sql` output stays byte-compatible with REST.
- **Test harness** — `MockKonecty` gained a `POST /mcp` SSE route with fault injection (403/404/429/500,
  URLError, malformed SSE, tool-error); new unit suite `tests/e2e/test_mcp_client.py`; dispatcher +
  find/query/sql mock e2e in `test_data_mock.py`; coverage closers in `test_coverage_closers.py`.
- **Docs** — `references/find.md` gained a "Transport: MCP-first with automatic REST fallback" section
  (Bearer auth, `KONECTY_MCP` env, fallback notice, `mcpRoleIds` prerequisite, and a "Known divergences"
  section citing ADR-0008 for the nested-filter superset + `KONECTY_MCP=0` workaround); `SKILL.md` gained
  a one-line transport pointer.

## Rationale

Konecty's User MCP tools call the same in-process `find()`/`crossModuleQuery()` as the legacy REST
endpoints, but with filter discipline (`KonFilter`), a normalized pagination envelope, and a supported
forward path. Routing the skill's search onto that maintained interface — while degrading cleanly to REST
where MCP is absent or the caller's role is not allow-listed — keeps the migration non-regressive. Auth
reuses the existing `authId` as `Bearer` (ADR-0006); MCP-first + fallback is ADR-0007; the accepted,
documented nested-filter divergence is ADR-0008.

## Notes

- Stdlib only (`urllib`, `json`); `mcp_client.py` is **not** a shared file (konecty-data-only until
  admin-mcp needs it — design decision, avoids the byte-identical burden prematurely).
- Verification: `make check` green; full e2e suite **541 passed, 9 skipped** (live suite skipped — stack
  down); coverage **93%** (`--fail-under=90`).
- Companion server-side fix for ADR-0008 lives in the Konecty repo at
  `.specs/quick/002-mcp-nested-filter-divergence/TASK.md` (test-first).
