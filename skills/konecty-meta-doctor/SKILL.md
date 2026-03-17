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

### 2. Check a specific document

```bash
python3 scripts/meta_doctor.py check --document Contact
```

### 3. Check queue consistency

```bash
python3 scripts/meta_doctor.py check-queues
```

## Checks performed

### Document integrity
- Fields reference valid types
- Lookup fields reference existing documents
- InheritedFields reference valid fields on the target document
- Required fields have labels

### List integrity
- Columns reference fields that exist in the parent document
- View reference exists

### View integrity
- VisualSymlink fieldNames exist in the parent document
- ReverseLookup targets exist

### Access integrity
- Field overrides reference fields that exist in the parent document
- ReadFilter/updateFilter conditions reference valid fields

### Queue consistency
- `document.events` queue resources exist in `Namespace.QueueConfig.resources`
- Queue names referenced in events exist in the resource's queue list

### Cross-references
- All metas reference existing parent documents
- Default access profiles exist

## Script reference

See [scripts/meta_doctor.py](scripts/meta_doctor.py). Stdlib only.
