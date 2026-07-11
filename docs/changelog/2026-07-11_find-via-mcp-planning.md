# Changelog: find-via-mcp planning (glossary + ADRs)

## Date

2026-07-11

## Summary

- Added **`CONTEXT.md`** at the repo root — a domain-language glossary (first for this repo). Pins the
  vocabulary that is easy to confuse when skills talk to Konecty: `authId` vs OAuth access token,
  first-party credential, **User MCP** vs **Admin MCP**, role allowlist (`mcpRoleIds`), KonFilter,
  Transport, and Fallback.
- Added three ADRs for the planned `find-via-mcp` feature (migrate `konecty-data` search to the Konecty
  User MCP):
  - **`docs/adr/0006`** — MCP auth uses the first-party `authId` as `Authorization: Bearer`, **not** OAuth
    (no `client_credentials` grant; OAuth is interactive; the legacy token already authenticates to `/mcp`).
  - **`docs/adr/0007`** — search is **MCP-first with automatic REST fallback** (namespace `mcpRoleIds`
    allowlist makes fallback essential; verified live 403 on an unconfigured namespace).
  - **`docs/adr/0008`** — a **known MCP filter divergence** (nested `filters` 2+ levels are silently
    zod-stripped → superset vs REST) is accepted + documented; the fix is Konecty-side.
- Updated `docs/adr/README.md` index (added 0005–0008).
- Feature spec + design written and **grilled** (`grill-with-docs`): `.specs/features/find-via-mcp/{spec,design}.md`.
  Grilling cut the P3 (records_find_by_id/widgets = YAGNI for a headless CLI), added transport
  observability + 429-disables-MCP + nested-filter handling, and verified MCP↔REST parity
  (document-id/`withDetailFields`/`getTotal`/`limit=-1` IDENTICAL).

## Rationale

Konecty shipped first-class MCP servers whose `records_find`/`query_json`/`query_sql` call the same
internals as the REST endpoints. Migrating `konecty-data` search onto that maintained interface is a
Large SDD feature; its auth model, compat strategy, and a real silent-divergence risk are architectural
decisions worth recording before any code. This entry covers the planning artifacts; implementation
(new `scripts/mcp_client.py` + dispatcher + e2e mock) lands in a later change.

## Notes

- Companion doc in the Konecty repo: `.specs/quick/002-mcp-nested-filter-divergence/TASK.md` (the
  server-side fix for ADR-0008, test-first).
- Live finding: logging in to `brain-konecty.konecty.dev` needs an `Origin` header + `password_SHA256`;
  its `/mcp` 403s (`mcp_access_denied`) until an admin adds the role to `mcpRoleIds`.
- No skill scripts changed yet; `make check` green (143 tests).
