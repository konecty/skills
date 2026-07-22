---
name: konecty-meta
description: "All Konecty metadata operations through the Konecty admin MCP server: read/inspect MetaObjects, manage document schemas and fields, manage list/view/access/pivot metas, validate and generate hook code, manage Namespace config (SMTP/RabbitMQ/storage/MCP flags), validate metadata integrity, and sync metadata repo↔database. Use when: ler metadados, inspecionar esquema, gerenciar campos, adicionar campo, criar lista/view, configurar perfil de acesso, gerar hook, configurar Namespace/SMTP/fila RabbitMQ, habilitar MCP, validar integridade meta, sincronizar metas, remover módulo meta, read metadata, manage schema, add fields, manage list view access pivot, generate hook, configure namespace, enable MCP flags, validate metadata, sync metadata, remove meta module. Requires the konecty-admin MCP server connected and an admin user (admin: true). Do NOT use for data record ops (find/create/update/delete/upload) — use konecty-data; do NOT use for MCP server setup — use konecty-setup."
---

# Konecty Meta

Procedural guide for all Konecty **metadata** administration. Execution happens
through Konecty's admin MCP tools (`meta_*`) — this skill teaches which tool to call,
with which payload shape, and which guardrails to respect. It ships no scripts and
makes no HTTP calls.

> **Requires the `konecty-admin` MCP server connected** (Konecty admin MCP at
> `<company-url>/admin-mcp`) and a user with `admin: true`. If the `meta_*` tools are
> not available, stop and guide the user through the **konecty-setup** skill.

## Authentication

**OAuth via a trusted client only** (ADR-0011): Konecty grants the `admin` OAuth
scope at consent to clients provisioned server-side with `OAUTH_CLIENTS_JSON`
(e.g. `claude-code-admin`) — only for users with `admin: true`, shown unchecked
with a risk warning that must be explicitly selected. See **konecty-setup** for
registering the `konecty-admin` server with a trusted client.

Tools are called **without** any token argument — auth travels in the HTTP
header, resolved by the MCP host. See [references/auth.md](references/auth.md).

## Tool inventory (admin MCP — 13 tools)

| Tool | Input | Purpose |
|------|-------|---------|
| `meta_read` | `name` | Read a document metadata object by name |
| `meta_document_upsert` | `id`, `document` | Create/update a document schema |
| `meta_list_upsert` | `id`, `list` | Create/update a list meta |
| `meta_view_upsert` | `id`, `view` | Create/update a view (form) meta |
| `meta_access_upsert` | `id`, `access` | Create/update an access profile |
| `meta_pivot_upsert` | `id`, `pivot` | Create/update a pivot meta |
| `meta_hook_validate` | `script` | Validate hook code **before** saving |
| `meta_hook_upsert` | `id`, `hook` | Persist hook metadata (validate first!) |
| `meta_delete` | `id`, `confirm` | Delete a meta object (dry-run without `confirm`; moves to trash) |
| `meta_namespace_update` | `patch` | Patch the Namespace singleton (incl. MCP flags) |
| `meta_doctor_run` | — | Run metadata integrity checks |
| `meta_sync_plan` | `items` | Plan a repo↔database metadata sync |
| `meta_sync_apply` | `items`, `autoApprove` | Apply a reviewed sync plan |

## Flow → reference map

| User intent (pt-BR / EN) | Reference |
|--------------------------|-----------|
| Ler metadados, inspecionar esquema, listar metas / read metadata, inspect schema | [references/read.md](references/read.md) |
| Gerenciar documento, adicionar/remover campo, editar schema / manage document schema, add fields | [references/document.md](references/document.md) |
| Gerenciar lista, adicionar coluna / manage list, columns | [references/list.md](references/list.md) |
| Gerenciar formulário/view, visual groups / manage form view | [references/view.md](references/view.md) |
| Perfil de acesso, permissões, filtros de leitura / access profiles, permissions | [references/access.md](references/access.md) |
| Relatório pivot, agregações / pivot reports | [references/pivot.md](references/pivot.md) |
| Gerar/validar hook, scriptBeforeValidation, validationScript / hooks | [references/hook.md](references/hook.md) |
| Namespace, SMTP, RabbitMQ, habilitar MCP, modo somente leitura / namespace config, MCP flags | [references/namespace.md](references/namespace.md) |
| Validar integridade, auditoria de metadados / validate metadata | [references/doctor.md](references/doctor.md) |
| Sincronizar metas, deploy de schema / sync metadata repo↔db | [references/sync.md](references/sync.md) |
| Remover módulo meta, excluir documento meta / remove meta module | [references/remove.md](references/remove.md) — **destructive, read first** |
| Descobrir campos de dados / data-side field discovery | [references/field-discovery.md](references/field-discovery.md) |

## Guardrails (non-negotiable)

1. **Upserts replace the whole meta object.** Always read the current state first
   (`meta_read` for documents; your metadata repo for child metas) and send the
   **complete** definition — a partial payload erases what you omit. Exception:
   `meta_namespace_update` is a real patch.
2. **Hooks**: `meta_hook_validate` **before** `meta_hook_upsert`, always. No
   `require`/`import`, no comments in hook source ([hook.md](references/hook.md)).
3. **Sync**: `meta_sync_plan` first; review with the user; only then
   `meta_sync_apply` with `autoApprove: true` — the tool refuses to apply without it.
4. **Deletion is two-step.** `meta_delete` without `confirm` is a dry-run showing
   the blast radius; only call with `confirm: true` after explicit user approval.
   Deleted objects go to `MetaObjects.Trash` (ops-recoverable); the Namespace
   object is undeletable. Full-module removal order and aftercare:
   [references/remove.md](references/remove.md).
5. **`_id` conventions**: `Contact` (document), `Contact:list:Default`,
   `Contact:view:Default`, `Contact:access:Corretor`, `Contact:pivot:Default`,
   `Namespace` (singleton). The upsert `id` argument is this `_id`.
6. After metadata changes, offer `meta_doctor_run` to check integrity.
