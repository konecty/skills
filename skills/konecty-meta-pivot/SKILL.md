---
name: konecty-meta-pivot
description: "Manage Konecty pivot/report metadata: show pivot definitions, inspect rows/columns/values configuration, upsert pivots. Use when the user wants to create or modify pivot tables, configure row groupings, column fields, value aggregators, or default filters. Requires admin credentials."
---

# Konecty Meta Pivot

Manage pivot-type metadata definitions (rows, columns, values, aggregators, filters).

## Prerequisites

Requires **admin** credentials from **konecty-session**. User must have `admin: true`.

## Workflow

### 1. Show a pivot definition

```bash
python3 scripts/meta_pivot.py show Activity Default
```

### 2. Upsert full pivot

```bash
python3 scripts/meta_pivot.py upsert Activity Default --file pivot.json
```

## Key concepts

- `_id` pattern: `{Document}:pivot:{Name}`
- `rows`: array of row grouping fields (e.g. `_user.group`, `_user`)
- `columns`: object-map of column fields
- `values`: array of aggregated value definitions with `aggregator` (count, sum, avg, min, max)
- `filter`, `sorters`, `rowsPerPage`, `refreshRate`: same structure as list metas

## Script reference

See [scripts/meta_pivot.py](scripts/meta_pivot.py). Stdlib only.
