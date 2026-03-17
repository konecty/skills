---
name: konecty-meta-list
description: "Manage Konecty list view metadata: show list definitions, manage columns, filters, sorters, calendars, and boards. Use when the user wants to create or modify list views, change column visibility or order, update default filters, or configure calendar/board views. Requires admin credentials."
---

# Konecty Meta List

Manage list-type metadata definitions (columns, filters, sorters, pagination, calendars, boards).

## Prerequisites

Requires **admin** credentials from **konecty-session**. User must have `admin: true`.

## Workflow

### 1. Show a list definition

```bash
python3 scripts/meta_list.py show Activity Default
python3 scripts/meta_list.py show Contact SavedFilter
```

### 2. List columns

```bash
python3 scripts/meta_list.py columns Activity Default
```

### 3. Add a column

```bash
python3 scripts/meta_list.py add-column Activity Default myField --visible --sort 10 --min-width 120
```

### 4. Remove a column

```bash
python3 scripts/meta_list.py remove-column Activity Default myField
```

### 5. Upsert full list

```bash
python3 scripts/meta_list.py upsert Activity Default --file list.json
```

## Key concepts

- `_id` pattern: `{Document}:list:{Name}`
- `columns` is an **object-map** `{ "columnName": { ... } }`, not an array
- `linkField` maps a column to a field in the parent document
- `filter` uses KonFilter syntax with editable conditions
- `sorters` defines default sort order
- `calendars` and `boards` are optional view mode configurations

## Script reference

See [scripts/meta_list.py](scripts/meta_list.py). Stdlib only.
