---
name: konecty-meta-access
description: "Manage Konecty access profile metadata: show access definitions, inspect permissions, set field-level access, configure read/update filters, manage document-level flags. Use when the user wants to create or modify access profiles, set field permissions, add row-level filters, or control menu visibility. Requires admin credentials."
---

# Konecty Meta Access

Manage access-type metadata definitions (permissions, field access, filters, menu control).

## Prerequisites

Requires **admin** credentials from **konecty-session**. User must have `admin: true`.

## Workflow

### 1. Show an access profile

```bash
python3 scripts/meta_access.py show Contact Corretor
python3 scripts/meta_access.py show Contact Default
```

### 2. List field permissions

```bash
python3 scripts/meta_access.py permissions Contact Corretor
```

### 3. Set a field permission

```bash
python3 scripts/meta_access.py set-field Contact Corretor status --create true --read true --update false --delete false
```

### 4. Set a document-level flag

```bash
python3 scripts/meta_access.py set-flag Contact Corretor --isCreatable true --isDeletable false
```

### 5. Upsert full access profile

```bash
python3 scripts/meta_access.py upsert Contact Corretor --file access.json
```

## Key concepts

- `_id` pattern: `{Document}:access:{Name}`
- See [references/access-architecture.md](references/access-architecture.md) for full architecture documentation
- Permission resolution: field-specific override → `fieldDefaults` → document-level flags
- `readFilter` / `updateFilter`: KonFilter auto-injected on all queries for this profile
- `$user` dynamic value resolves to the current user's `_id`
- `hideListsFromMenu` / `hidePivotsFromMenu`: hide specific views from sidebar

## Script reference

See [scripts/meta_access.py](scripts/meta_access.py). Stdlib only.
