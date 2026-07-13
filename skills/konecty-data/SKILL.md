---
name: konecty-data
description: "All Konecty CRM data operations through the Konecty user MCP server: find/search/filter records, cross-module queries and aggregations, create records, update records (fetch-first with _updatedAt), delete records (preview + confirm), upload/download/delete files, session login, and module/field discovery. Use when user wants to: buscar registros, pesquisar, listar, filtrar dados, criar registro, inserir dado, criar contato/oportunidade/atividade, atualizar, editar, modificar registro, deletar, remover, apagar registro, fazer upload, anexar arquivo, enviar imagem, listar módulos, descobrir campos, consultar o CRM, search records, create record, update, delete, upload file, discover fields, query CRM data. Requires the konecty MCP server connected (see konecty-setup). Do NOT use for metadata/schema ops (documents, lists, views, access, hooks, namespace) — use konecty-meta; do NOT use for connecting/configuring the MCP server — use konecty-setup."
---

# Konecty Data

Procedural guide for all Konecty CRM **data** conversations. Execution happens through
Konecty's own MCP tools — this skill teaches which tool to call, in which order, and
which guardrails to respect. It ships no scripts and makes no HTTP calls.

> **Requires the `konecty` MCP server connected** (Konecty user MCP at `<company-url>/mcp`).
> If the tools below are not available, stop and guide the user through the
> **konecty-setup** skill before anything else.

## Authentication

Default path: **OAuth handled natively by Claude Code** — the token travels in the
`Authorization` header automatically. Call every tool **without** an `authTokenId`
argument. Fallback (no OAuth available): OTP login via the `session_*` tools, then pass
the returned `authId` as `authTokenId` on each authenticated call.
See [references/auth.md](references/auth.md).

## Tool inventory (user MCP)

| Group | Tools | Auth |
|-------|-------|------|
| Session | `session_login_options`, `session_request_otp_email`, `session_request_otp_phone`, `session_verify_otp_email`, `session_verify_otp_phone` | public |
| Session | `session_logout` | authenticated |
| Modules | `modules_list`, `modules_fields` | authenticated |
| Field helpers | `field_picklist_options`, `field_lookup_search` | authenticated |
| Filter | `filter_build` | public (no auth) |
| Records | `records_find`, `records_find_by_id`, `records_create`, `records_update`, `records_delete_preview`, `records_delete` | authenticated |
| Query | `query_json`, `query_sql`, `query_pivot`, `query_graph` | authenticated |
| Files | `file_upload`, `file_download`, `file_delete` | authenticated |
| Widgets | `render_records_widget`, `render_record_widget`, `render_record_card`, `render_pivot_widget`, `render_graph_widget`, `render_file_widget` | render-only |

`render_*` widget tools are **host-dependent** (MCP-app resources): treat them as
optional visual enhancements — never make a data flow depend on them.

## Flow → reference map

| User intent (pt-BR / EN) | Flow | Reference |
|--------------------------|------|-----------|
| Listar módulos, descobrir campos, tipos de campo, que campos existem / list modules, discover fields | `modules_list` → `modules_fields` → field helpers | [references/field-discovery.md](references/field-discovery.md) |
| Buscar, pesquisar, listar, filtrar, consultar, agrupar, somar, query SQL / search, filter, aggregate, cross-module query | `filter_build` → `records_find` \| `query_json` \| `query_sql` | [references/find.md](references/find.md) |
| Criar registro, inserir, criar contato/oportunidade/atividade / create record | `modules_fields` → resolve lookups/picklists → `records_create` | [references/create-update.md](references/create-update.md) |
| Atualizar, editar, modificar, alterar status / update record | `records_find_by_id` → `records_update` (with `_updatedAt`) | [references/create-update.md](references/create-update.md) |
| Deletar, remover, apagar, excluir registro / delete record | `records_delete_preview` → **user confirms** → `records_delete` | [references/delete.md](references/delete.md) |
| Upload, anexar arquivo, enviar imagem, baixar anexo / upload, download, delete file | `file_upload` / `file_download` / `file_delete` | [references/files.md](references/files.md) |
| Login, autenticar, sessão expirada / log in, re-authenticate | OAuth (default) or `session_*` OTP fallback | [references/auth.md](references/auth.md) |
| Erro de permissão, acesso negado, indisponível / permission or availability errors | map error → explanation + next step | [references/errors.md](references/errors.md) |

## Query strategy (always)

- **Single-module reads and pagination** → `records_find` (offset pagination: `start` += `limit` while `pagination.hasMore`).
- **Cross-module retrieval or aggregation** → `query_json` (relations/joins, `groupBy`, aggregators). Prefer it over paginating everything with `records_find` when the user wants counts, sums, or summaries.
- **`query_sql` only when the user explicitly asks for SQL.**
- Always use the technical `document` identifier from `modules_list` — never a label or display name.

## Guardrails (non-negotiable)

1. **Filters**: ALWAYS build filters with `filter_build` — Konecty's structured format,
   never Mongo-style maps (`records_find`, `query_pivot`, `query_graph` reject them).
2. **Update**: fetch first (`records_find_by_id`), then `records_update` passing
   `ids: [{ _id, _updatedAt }]` from the live record. Never invent `_updatedAt`.
3. **Delete**: `records_delete_preview` → show the record → **explicit user
   confirmation** → `records_delete` with `confirm`. One record at a time. Irreversible.
4. **Dates**: ISO 8601 with timezone (`"2026-01-01T00:00:00Z"`) — `"2026-01-01"` and
   `"01/01/2026"` are rejected.
5. **Picklists/lookups**: resolve valid values first (`field_picklist_options`,
   `field_lookup_search`) — picklist keys are case-sensitive; lookups take `{ "_id": … }`.
6. **Write failures**: if a write tool returns `insufficient_scope`, the namespace is in
   read-only mode — explain it and stop; do not retry (see errors.md).

## Response channels

Every tool returns `content.text` (readable summary + next steps) and
`structuredContent` (full JSON). Use `structuredContent` for data you will process;
`content.text` already carries next-step guidance.
