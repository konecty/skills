---
name: konecty-meta-sync
description: "Synchronize Konecty metadata between a filesystem repository and the database: plan changes (terraform-style diff), apply selectively, pull from production to repo. Use when the user wants to deploy metadata from a repository to production, compare repo vs database state, pull current metadata to a repository, or selectively apply metadata changes. Requires admin credentials."
---

# Konecty Meta Sync

Synchronize metadata between a filesystem repository and the Konecty database.

## Prerequisites

Requires **admin** credentials from **konecty-session**. User must have `admin: true`.
Requires a metadata repository with the standard structure:

```
MetaObjects/
  Contact/
    document.json
    list/Default.json
    view/Default.json
    access/Default.json
    access/Corretor.json
    pivot/Default.json
    hook/scriptBeforeValidation.js
    hook/validationData.json
    hook/validationScript.js
    hook/scriptAfterSave.js
  Namespace/
    document.json
```

## Workflow

### 1. Plan (preview changes — ALWAYS run first)

```bash
python3 scripts/meta_sync.py plan --from repo --to prod --repo /path/to/metas
python3 scripts/meta_sync.py plan --from prod --to repo --repo /path/to/metas
```

Shows a diff of changes that would be applied. No changes are made.

### 2. Apply (execute changes with confirmation)

```bash
python3 scripts/meta_sync.py apply --from repo --to prod --repo /path/to/metas
```

Interactive confirmation: shows each change and asks for approval.

```bash
python3 scripts/meta_sync.py apply --from repo --to prod --repo /path/to/metas --auto-approve
```

Non-interactive: applies all changes (for CI/CD).

```bash
python3 scripts/meta_sync.py apply --from repo --to prod --repo /path/to/metas --only Contact Contact:list:Default
```

Selective: applies only the specified metas.

### 3. Diff (single item comparison)

```bash
python3 scripts/meta_sync.py diff --repo /path/to/metas --meta-id Contact
python3 scripts/meta_sync.py diff --repo /path/to/metas --meta-id "Contact:list:Default"
```

### 4. Pull (fetch from prod to repo)

```bash
python3 scripts/meta_sync.py pull --repo /path/to/metas --document Contact
python3 scripts/meta_sync.py pull --repo /path/to/metas --all
```

## Direction model

- `--from repo --to prod`: Repository is source of truth, push to database
- `--from prod --to repo`: Database is source of truth, pull to repository

## Key concepts

- Hooks (.js/.json files) in `hook/` subdirectory are injected into the document meta
- Namespace is synced as `MetaObjects/Namespace/document.json`
- The `--only` flag allows selective application from a plan
- The `--auto-approve` flag skips interactive confirmation (for CI/CD)
- After applying changes, a reload (`POST /api/admin/meta/reload`) is triggered automatically

## Script reference

See [scripts/meta_sync.py](scripts/meta_sync.py). Stdlib only.
