---
name: konecty-meta-view
description: "Manage Konecty form view metadata: show view definitions, inspect visual tree (visualGroups, visualSymlinks, reverseLookups), upsert views. Use when the user wants to create or modify form layouts, rearrange fields in forms, add visual groups, or configure reverse lookups in views. Requires admin credentials."
---

# Konecty Meta View

Manage view-type (form) metadata definitions (visuals tree, labels, parent inheritance).

## Prerequisites

Requires **admin** credentials from **konecty-session**. User must have `admin: true`.

## Workflow

### 1. Show a view definition

```bash
python3 scripts/meta_view.py show Activity Default
```

### 2. List visuals (flattened)

```bash
python3 scripts/meta_view.py visuals Activity Default
```

### 3. Upsert full view

```bash
python3 scripts/meta_view.py upsert Activity Default --file view.json
```

## Key concepts

- `_id` pattern: `{Document}:view:{Name}`
- `visuals` is a recursive tree of:
  - `visualGroup`: container with required `label` plus optional `style.title`/`style.icon`, nested `visuals[]`
  - `visualSymlink`: references a field; has `fieldName` and optional `style` (readOnlyVersion, renderAs, etc.)
  - `reverseLookup`: shows related records; has `field`, `document`, `list`
- `parent` enables view inheritance between namespaces
- `label` supports `{field}` interpolation for dynamic titles

## Script reference

See [scripts/meta_view.py](scripts/meta_view.py). Stdlib only.
