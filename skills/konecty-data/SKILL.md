---
name: konecty-data
description: "All Konecty data operations: find/search/filter records, create records, update records (fetch-first with _updatedAt), delete records, upload/list/delete files, authenticate via OTP, and discover module fields and types. Use when user wants to: buscar registros, pesquisar, listar, filtrar dados, criar registro, inserir dado, criar contato/oportunidade/atividade, atualizar, editar, modificar registro, deletar, remover, apagar registro, fazer upload, anexar arquivo, enviar imagem, fazer login no Konecty, autenticar via OTP, listar módulos, descobrir campos, search records, create record, update, delete, upload file, log in to Konecty, authenticate, discover fields. Requires active session (KONECTY_URL and KONECTY_TOKEN in ~/.konecty/.env). Do NOT use for metadata/schema ops (documents, lists, views, access, hooks, namespace) — use konecty-meta for those."
---

# Konecty Data

All Konecty data operations in one skill: authentication, field discovery, and full CRUD + file management.

## Prerequisites

All operations require credentials in `~/.konecty/.env`:

```
KONECTY_URL=https://<host>
KONECTY_TOKEN=<authId>
```

If credentials are missing or expired, use the OTP auth flow first — see [references/auth.md](references/auth.md).

## Commands

| Trigger Pattern | Reference |
|----------------|-----------|
| Log in, authenticate, OTP login, get token, fazer login, autenticar, abrir sessão, obter token Konecty | [references/auth.md](references/auth.md) |
| List modules, discover fields, what fields exist, listar módulos, descobrir campos, tipos de campo | [references/field-discovery.md](references/field-discovery.md) |
| Find records, search, list, filter, query, SQL, buscar registros, pesquisar, listar, filtrar, query SQL | [references/find.md](references/find.md) |
| Create record, insert, add, criar registro, inserir dado, criar contato, criar oportunidade, criar atividade | [references/create.md](references/create.md) |
| Update record, edit, modify, change, atualizar registro, editar, modificar campo, alterar status | [references/update.md](references/update.md) |
| Delete record, remove, erase, deletar registro, remover registro, apagar, excluir registro | [references/delete.md](references/delete.md) |
| Upload file, attach file, send image, fazer upload, anexar arquivo, enviar imagem, upload foto | [references/upload.md](references/upload.md) |

> **Transport note:** `find` / `query` / `sql` read through the Konecty **User MCP** (`POST /mcp`,
> `Authorization: Bearer`) with automatic REST fallback and a `KONECTY_MCP` env switch
> (`0` = REST-only, `only` = strict). Transparent by default — see [references/find.md](references/find.md).

## Shared files (gated)

`scripts/auth.py` and `scripts/modules.py` are byte-identical with `konecty-meta`. A pre-commit hook and GitHub Action enforce this — changes must be applied to both skills simultaneously. See `shared-files.txt` for the full manifest.
