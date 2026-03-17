---
name: konecty-meta-read
description: "Read Konecty metadata: list documents, get document/list/view/access/pivot/hook definitions, inspect meta types. Use when the user wants to see what metadata exists, inspect a document schema, read access profiles, view hook code, or understand metadata structure. Requires admin credentials from konecty-session."
---

# Konecty Meta Read

Read-only access to all Konecty metadata types via the admin API.

## Prerequisites

Requires **admin** credentials from **konecty-session**: `KONECTY_URL` and `KONECTY_TOKEN` in `~/.konecty/.env`.
The authenticated user must have `admin: true`.

## API Endpoints

All endpoints require `Authorization: <KONECTY_TOKEN>` header. All are admin-only.

| Endpoint | Description |
|----------|-------------|
| `GET /api/admin/meta` | List all document/composite metas (summary) |
| `GET /api/admin/meta/:document` | List all meta objects for a document (summary) |
| `GET /api/admin/meta/:document/:type/:name` | Get full meta by type and name |
| `GET /api/admin/meta/:document/hook/:hookName` | Get hook code (JS) or JSON (validationData) |

## Workflow

### 1. List all documents

```bash
python3 scripts/meta_read.py list
python3 scripts/meta_read.py list --format json
```

### 2. Inspect all metas for a document

```bash
python3 scripts/meta_read.py get Contact
```

Returns summary of all metas: document, lists, views, access profiles, pivots, cards.

### 3. Get a specific meta

```bash
python3 scripts/meta_read.py get Contact --type list --name Default
python3 scripts/meta_read.py get Contact --type view --name Default
python3 scripts/meta_read.py get Contact --type access --name Corretor
python3 scripts/meta_read.py get Namespace --type namespace --name Namespace
```

### 4. Read hook code

```bash
python3 scripts/meta_read.py hook Contact scriptBeforeValidation
python3 scripts/meta_read.py hook Product validationData
python3 scripts/meta_read.py hook Contact validationScript
python3 scripts/meta_read.py hook Contact scriptAfterSave
```

### 5. List meta types for a document

```bash
python3 scripts/meta_read.py types Contact
```

Shows all meta types and their IDs grouped by type.

## Meta types

| Type | `_id` pattern | Example |
|------|--------------|---------|
| `document` | `{Name}` | `Contact` |
| `composite` | `{Name}` | `Education` |
| `list` | `{Doc}:list:{Name}` | `Contact:list:Default` |
| `view` | `{Doc}:view:{Name}` | `Contact:view:Default` |
| `access` | `{Doc}:access:{Name}` | `Contact:access:Corretor` |
| `pivot` | `{Doc}:pivot:{Name}` | `Contact:pivot:Default` |
| `card` | `{Doc}:card:{Name}` | `Opportunity:card:Default` |
| `namespace` | `Namespace` | `Namespace` |

## Detailed schema reference

See [references/meta-schemas.md](references/meta-schemas.md) for full schema documentation with annotated examples for each type.

## Script reference

See [scripts/meta_read.py](scripts/meta_read.py). Stdlib only (`urllib`, `json`).

All subcommands accept:
- `--host` — overrides `KONECTY_URL`
- `--token` — overrides `KONECTY_TOKEN`
