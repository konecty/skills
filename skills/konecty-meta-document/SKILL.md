---
name: konecty-meta-document
description: "Manage Konecty document metadata: show document definitions, list fields, add/remove/update fields, manage document events (queue/webhook). Use when the user wants to create or modify a document schema, add fields, manage field properties, or configure document-level events for queue/webhook integration. Requires admin credentials."
---

# Konecty Meta Document

Manage document-type metadata definitions (fields, labels, events, indexes).

## Prerequisites

Requires **admin** credentials from **konecty-session**. User must have `admin: true`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/meta/:document/document/:document` | GET | Get full document meta |
| `/api/admin/meta/:document/document/:document` | PUT | Upsert document meta |

## Workflow

### 1. Show a document definition

```bash
python3 scripts/meta_document.py show Contact
```

### 2. List fields

```bash
python3 scripts/meta_document.py fields Contact
python3 scripts/meta_document.py fields Contact --format json
```

### 3. Add a field

```bash
python3 scripts/meta_document.py add-field Contact myNewField \
  --type text --label-en "My Field" --label-pt "Meu Campo" --required
```

### 4. Remove a field

```bash
python3 scripts/meta_document.py remove-field Contact myNewField
```

### 5. Update a field property

```bash
python3 scripts/meta_document.py update-field Contact status --set isRequired=true
python3 scripts/meta_document.py update-field Contact status --set 'label.en=Status Name'
```

### 6. Upsert full document

```bash
python3 scripts/meta_document.py upsert Contact --file document.json
```

### 7. List document events

```bash
python3 scripts/meta_document.py events Contact
```

## Key concepts

- `fields` is an **object-map** `{ "fieldName": { ... } }`, not an array
- Field types: text, number, boolean, date, dateTime, picklist, lookup, email, phone, address, personName, money, file, composite, filter, richText, autoNumber, etc.
- See [references/field-architecture.md](references/field-architecture.md) for full field type documentation
- See [references/document-events.md](references/document-events.md) for queue/webhook event configuration

## Script reference

See [scripts/meta_document.py](scripts/meta_document.py). Stdlib only.
