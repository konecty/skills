# Create & Update Records — user MCP

Create and update Konecty records with `records_create` and `records_update`.
Both are **write** tools: if the namespace is read-only (`mcpUserWriteEnabled=false`),
they fail with `insufficient_scope` — see [errors.md](errors.md).

## Create — discover → resolve → create

### 1. Discover the module's fields

Call `modules_fields` with the `document` (see
[field-discovery.md](field-discovery.md)). Note each field's **name**, **type**
(payload format below), picklist options, and lookup target.

### 2. Resolve lookup `_id`s

For every lookup field you want to set, resolve the target record's `_id` with
`field_lookup_search` (input: `document`, `fieldName`, `search`). Use
`{ "_id": "..." }` in the payload — never a label or code.

### 3. Confirm picklist keys

Use `field_picklist_options` — values must exactly match the option **keys**
(case-sensitive).

### 4. `records_create`

Input: `document`, `data`. Output: `records` (the created record with
server-normalized values — defaults applied, computed fields populated).

```json
{
  "document": "Activity",
  "data": {
    "subject": "Ligação de boas-vindas",
    "status": "Realizado",
    "type": "Ligação",
    "contact": { "_id": "JeSqMH6mkP5f233Rp" }
  }
}
```

If the response says a required field is missing (`Field X is required`), add that
field and retry — required fields are enforced at save time, and fields with a
`defaultValue` are populated server-side.

## Field type → payload format

| Field type | Send as | Notes |
|------------|---------|-------|
| `text` / `url` | `"string"` | |
| `richText` | `"<p>HTML</p>"` | Accepts HTML |
| `number` / `percentage` | `123` or `12.5` | |
| `boolean` | `true` / `false` | |
| `date` | `"2026-03-16"` | ISO 8601 |
| `dateTime` | `"2026-03-16T14:00:00.000Z"` | ISO 8601 with time (UTC) |
| `picklist` (single) | `"option_key"` | Exact key from `field_picklist_options` |
| `picklist` (multi) | `["key1", "key2"]` | Array of keys |
| `lookup` / `inheritLookup` | `{ "_id": "record-id" }` | Server fetches description fields |
| `lookup` (clear) | `{}` | Empty object clears the lookup |
| `email` | `{ "address": "a@b.com" }` | |
| `phone` | `{ "countryCode": 55, "phoneNumber": "5511999999999" }` | |
| `personName` | `{ "first": "João", "last": "Silva" }` | Server computes `full` |
| `address` | `{ "country": "BRA", "state": "SP", "city": "...", "place": "...", "number": "..." }` | |
| `money` | `{ "currency": "BRL", "value": 100.0 }` | |
| `geoloc` | `[-51.22, -30.04]` | `[longitude, latitude]` |
| `json` | any object/array | Stored as-is |
| `autoNumber` / `_id` | **do not send** | Generated server-side |

Key rules:

- `null` and `""` in the payload are stripped — same as not sending the field.
- Multi-select picklists with `minSelected > 0` must not receive an empty array.
- Lookup `_id`s are validated — a wrong id returns
  `Record not found for field {name} with _id [...]`.

---

## Update — fetch-first, always

The API requires `_updatedAt` on every update as an **optimistic lock**. A stale or
invented value is rejected. **Never invent or hardcode `_updatedAt`.**

### 1. `records_find_by_id`

Input: `document`, `recordId`, optional `fields`, `withDetailFields`. Output:
`record`. Take the live `_id` and `_updatedAt` (and review current values).

If you only have a human reference (code, name), locate the record first with
`records_find` and confirm with the user when more than one matches.

### 2. `records_update`

Input: `document`, `ids` (array of `{ _id, _updatedAt }`), `data`. Output: `records`.

```json
{
  "document": "Contact",
  "ids": [{ "_id": "JeSqMH6mkP5f233Rp", "_updatedAt": "2026-03-16T10:00:00.000Z" }],
  "data": { "status": "Inativo" }
}
```

- `data` is **partial** — send only the fields to change; others are untouched.
- `null` in `data` **clears** a field.
- `ids` accepts multiple entries for batch updates — each with its own live
  `_updatedAt`.
- Field payload formats are the same as create (table above).

### Lock-conflict recovery

If the update is rejected because the record changed after your fetch (stale
`_updatedAt` / "new version for records"):

1. Re-fetch with `records_find_by_id`.
2. Show the user what changed (their intent vs. the record's current values).
3. Retry **once**, only after the user confirms, with the fresh `_updatedAt`.

Never loop retries silently — a conflict means someone else edited the record.

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Field {name} is required` | Required field missing | Add it and retry |
| id missing `_id`/`_updatedAt` | Fetch-first skipped | `records_find_by_id` first |
| New version for records | Optimistic-lock conflict | Recovery flow above |
| `Record not found for field {name} with _id [...]` | Bad lookup `_id` | Resolve via `field_lookup_search` |
| `Value {x} for field {name} is invalid` | Picklist key mismatch | `field_picklist_options` |
| No permission to create/update field | Access profile restriction | Omit that field; explain to the user |
| `insufficient_scope` | Namespace read-only (`mcpUserWriteEnabled=false`) | Explain, don't retry — [errors.md](errors.md) |
