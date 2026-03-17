---
name: konecty-meta-doctor
description: "Validate Konecty metadata integrity: check for orphan references, missing access profiles, invalid field types, broken lookup targets, queue resource consistency, and other metadata health issues. Use when the user wants to audit metadata quality, find broken references, or validate that metadata is consistent and complete. Requires admin credentials."
---

# Konecty Meta Doctor

Validate the health and integrity of Konecty metadata.

## Prerequisites

Requires **admin** credentials from **konecty-session**. User must have `admin: true`.

## Workflow

### 1. Run full health check

```bash
python3 scripts/meta_doctor.py check
python3 scripts/meta_doctor.py check --format json
```

This command uses backend `POST /api/admin/meta/doctor` as the source of truth.

### 2. Check a specific document

```bash
python3 scripts/meta_doctor.py check --document Contact
```

### 3. Check queue consistency (filtered from backend doctor report)

```bash
python3 scripts/meta_doctor.py check-queues
```

## Checks performed by backend doctor

### Schema and integrity
- Fields reference valid types
- Lookup fields reference existing documents
- InheritedFields reference valid fields on the target document
- Required fields have labels

### Access integrity
- Field overrides reference fields that exist in the parent document

### Queue consistency
- `document.events` queue resources exist in `Namespace.QueueConfig.resources`

### Cross-references
- All metas reference existing parent documents
- Lookup targets reference existing `document/composite` metas
- Hook static checks (syntax, blocked APIs, comments, return requirements)

## Script reference

See [scripts/meta_doctor.py](scripts/meta_doctor.py). Stdlib only.
