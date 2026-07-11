---
name: konecty-meta
description: "All Konecty metadata operations: read/inspect MetaObjects, manage document schemas and fields, manage list/view/access/pivot metas, generate hook code (scriptBeforeValidation/validationScript/scriptAfterSave/validationData), manage Namespace config (SMTP/RabbitMQ/storage), validate metadata integrity, sync metadata repo↔database, remove full metadata modules. Use when: ler metadados, listar documentos, inspecionar esquema, gerenciar campos, adicionar campo, criar lista/view, configurar perfil de acesso, gerar hook, configurar Namespace/SMTP/fila RabbitMQ, validar integridade meta, sincronizar metas, remover módulo meta, read metadata, manage schema, add fields, manage list view access pivot, generate hook, configure namespace smtp queue, validate metadata, sync metadata repo to prod, remove meta module. Requires admin credentials (admin: true). Do NOT use for data record ops (find/create/update/delete/upload) — use konecty-data instead."
---

# Konecty Meta

All Konecty metadata operations in one skill: authentication, field discovery, and full metadata management across all 11 meta types.

## Prerequisites

Requires **admin** credentials in `~/.konecty/.env`:

```
KONECTY_URL=https://<host>
KONECTY_TOKEN=<authId>  # user must have admin: true
```

If credentials are missing or expired, use the OTP auth flow first — see [references/auth.md](references/auth.md).

## Commands

| Trigger Pattern | Reference |
|----------------|-----------|
| Log in, authenticate, OTP login, get token, fazer login, autenticar, abrir sessão, obter token Konecty | [references/auth.md](references/auth.md) |
| List modules, discover fields, listar módulos, descobrir campos, que campos tem, tipos de campo | [references/field-discovery.md](references/field-discovery.md) |
| Read metadata, list documents, inspect meta, ler metadados, listar documentos meta, inspecionar esquema | [references/read.md](references/read.md) |
| Manage document schema, add/remove fields, gerenciar documento, adicionar campo, remover campo, editar schema | [references/document.md](references/document.md) |
| Manage list meta, add column, configure list view, gerenciar lista, adicionar coluna, configurar lista | [references/list.md](references/list.md) |
| Manage view/form layout, gerenciar formulário, configurar view, layout de formulário, visual groups | [references/view.md](references/view.md) |
| Manage access profile, set permissions, gerenciar perfil de acesso, permissões de campo, filtro de leitura | [references/access.md](references/access.md) |
| Manage pivot/report, configurar relatório pivot, gerenciar pivot, definir agregações | [references/pivot.md](references/pivot.md) |
| Generate hook, manage hook code, gerar hook, gerenciar hook, criar scriptBeforeValidation, validationScript | [references/hook.md](references/hook.md) |
| Configure namespace, SMTP, RabbitMQ, configurar namespace, configurar servidor de email, fila RabbitMQ | [references/namespace.md](references/namespace.md) |
| Validate metadata, check integrity, validar metadados, checar integridade, auditoria de metadados | [references/doctor.md](references/doctor.md) |
| Sync metadata, deploy metas, push to prod, sincronizar metadados, aplicar metas, deploy schema | [references/sync.md](references/sync.md) |
| Remove metadata module, delete meta, remover módulo meta, deletar metadado, excluir documento meta | [references/remove.md](references/remove.md) |

## Shared files (gated)

`scripts/auth.py` and `scripts/modules.py` are byte-identical with `konecty-data`. A pre-commit hook and GitHub Action enforce this — changes must be applied to both skills simultaneously. See `shared-files.txt` for the full manifest.
