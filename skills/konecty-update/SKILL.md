---
name: konecty-update
description: "Updates records in any Konecty module via PUT /rest/data/:document. Enforces the mandatory pre-update fetch workflow: always fetch the current record first to obtain its _updatedAt (optimistic locking guard), then PUT with ids=[{_id, _updatedAt}] and data={changed fields}. Use when the user wants to update, edit, change, or modify any record in Konecty. Requires an active konecty-session. Use konecty-modules to discover field names and types before updating."
---

# Konecty Update

Update records in any Konecty module. **Always fetch first** to obtain `_updatedAt`.

## Prerequisites

- Active session from **konecty-session** (`~/.konecty/.env` or `~/.konecty/credentials`).
- Field knowledge from **konecty-modules** when updating unfamiliar modules.

## Why _updatedAt is mandatory

The Konecty API requires `_updatedAt` in every update call as an optimistic locking guard. Sending a stale or invented value is rejected with:

```
[Module] Each id must contain an string field named _id an date field named _updatedAt
```

**Never invent or hardcode `_updatedAt`** — always fetch the current record first.

## API

```
PUT /rest/data/:document
Body: { "ids": [{ "_id": "...", "_updatedAt": "ISO string or {$date:...}" }],
        "data": { ...only the fields you want to change... } }
Response: { "success": true, "data": [{ full updated record }] }
```

- `ids`: array — supports batch updates (multiple records in one call)
- `data`: partial — only changed fields; unmentioned fields are untouched
- `null` in `data` **clears** a field (`$unset`)

---

## Workflow

### Option A — convenience: `patch` (fetch + update in one step)

```bash
python3 skills/konecty-update/scripts/update.py patch <Document> <code or _id> \
  --data '<changed fields JSON>'
```

The script fetches the record automatically, prints the `_id` and `_updatedAt` found, then performs the update.

### Option B — explicit: `fetch` then `update` (full control)

```bash
# Step 1: fetch to obtain _id and _updatedAt
python3 skills/konecty-update/scripts/update.py fetch <Document> <code or _id>

# Step 2: update with the values from Step 1
python3 skills/konecty-update/scripts/update.py update <Document> \
  --ids '[{"_id":"...","_updatedAt":"..."}]' \
  --data '<changed fields JSON>'
```

Use Option B when you want to review current values before updating, or for batch updates.

---

## Quick Examples

### Update a contact's status

```bash
python3 skills/konecty-update/scripts/update.py patch Contact 16503 \
  --data '{"status": "Inativo"}'
```

### Update a job vacancy's name

```bash
# First, fetch to confirm the record and get _updatedAt
python3 skills/konecty-update/scripts/update.py fetch Job 60074

# Then update
python3 skills/konecty-update/scripts/update.py update Job \
  --ids '[{"_id":"<id from fetch>","_updatedAt":"<_updatedAt from fetch>"}]' \
  --data '{"name": "PROFESSOR TUTOR | Novo Título"}'
```

### Update a message status to "Enviada"

```bash
python3 skills/konecty-update/scripts/update.py patch Message wyLtwR3aRntZ4a2q8 \
  --data '{"status": "Enviada"}'
```

### Clear an optional field (set to null)

```bash
python3 skills/konecty-update/scripts/update.py patch Contact 16503 \
  --data '{"notes": null}'
```

### Batch update multiple records

```bash
# Fetch both records first, then update in one call
python3 skills/konecty-update/scripts/update.py update Contact \
  --ids '[{"_id":"id1","_updatedAt":"2026-03-16T10:00:00Z"},{"_id":"id2","_updatedAt":"2026-03-16T11:00:00Z"}]' \
  --data '{"status": "Inativo"}'
```

---

## Field Rules (same as create)

| Type | Send as |
|------|---------|
| `text` / `richText` | `"string"` |
| `number` / `boolean` / `date` / `dateTime` | native JSON type |
| `picklist` (single) | `"option_key"` |
| `picklist` (multi) | `["key1", "key2"]` |
| `lookup` | `{ "_id": "record-id" }` |
| Clear a field | `null` |

For the full type reference, see [`konecty-create/references/field-types.md`](../konecty-create/references/field-types.md).

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Each id must contain an string field named _id an date field named _updatedAt` | `_updatedAt` missing or wrong type | Run `fetch` first; never hardcode |
| `Payload must contain an array of ids with at least one item` | `ids` is empty or not an array | Pass at least one `{_id, _updatedAt}` entry |
| `Data must have at least one field` | `data` is empty | Add at least one field to update |
| `You don't have permission to update field <name>` | Field not updatable by current user | Omit that field |
| `Record not found for field <name>` | Lookup `_id` doesn't exist | Verify with `konecty-create lookup` |
| `Value <x> for field <name> is invalid` | Picklist value not in options | Check valid options with `konecty-modules fields` |

## Script reference

See [scripts/update.py](scripts/update.py). Stdlib only.

```
update.py fetch  <Document> <term>                      # get _id and _updatedAt
update.py update <Document> --ids '<JSON>' --data '<JSON>'  # explicit PUT
update.py patch  <Document> <term> --data '<JSON>'      # fetch + update shortcut
```

All subcommands accept `--host` and `--token` to override credentials.
