---
name: konecty-create
description: "Creates records in any Konecty module via POST /rest/data/:document. Guides through the full pre-creation workflow: discovering fields and types with konecty-modules, resolving lookup _ids with the built-in lookup command, checking picklist options, validating required fields, and submitting the payload. Use when the user wants to create a new record, insert data, send a message, add an activity, register a contact, create an opportunity, or create any document in Konecty. Requires an active konecty-session (KONECTY_URL and KONECTY_TOKEN in ~/.konecty/.env or ~/.konecty/credentials)."
---

# Konecty Create

Create records in any Konecty module following a discover → validate → create workflow.

## Prerequisites

- Active session from **konecty-session**: credentials in `~/.konecty/.env` or `~/.konecty/credentials`.
- Module and field knowledge from **konecty-modules** (run it to discover fields before creating).

## API

```
POST /rest/data/:document
Body: flat JSON object with field names as keys
Response: { "success": true, "data": [{ created record }] }
         { "success": false, "errors": [{ "message": "..." }] }
```

HTTP status is always `200`. Success/failure is in the `success` field.

---

## Workflow

### Step 1 — Discover the module's fields

```bash
python3 skills/konecty-modules/scripts/modules.py fields "<Module>"
```

Note the fields you need: their **name** (for the payload key), **type** (determines payload format), **picklist options**, and **lookup target document**.

### Step 2 — Resolve lookup _ids

For every `lookup` or `inheritLookup` field you want to set, find the target record's `_id`:

```bash
# By numeric code
python3 skills/konecty-create/scripts/create.py lookup Contact 16503

# By name / free text
python3 skills/konecty-create/scripts/create.py lookup Campaign "Black Friday"
```

Output shows `_id` and display fields. Use `{ "_id": "..." }` in the payload.

### Step 3 — Check picklist options

The `options:` column in `konecty-modules fields` shows valid keys. Use **exactly** those strings as values.

### Step 4 — Build and submit the payload

```bash
python3 skills/konecty-create/scripts/create.py create <Document> --data '<JSON>'
```

If the API returns `"Field X is required"`, add the missing field and retry.

---

## Quick Examples

### Create a welcome message for a contact

```bash
# Step 1: discover Message fields
python3 skills/konecty-modules/scripts/modules.py fields "Message"

# Step 2: find contact _id by code
python3 skills/konecty-create/scripts/create.py lookup Contact 16503

# Step 3: create the message
python3 skills/konecty-create/scripts/create.py create Message --data '{
  "subject": "Bem-vindo ao Konecty!",
  "body": "<p>Olá! Seja muito bem-vindo(a). Estamos felizes em tê-lo(a) conosco.</p>",
  "contact": { "_id": "JeSqMH6mkP5f233Rp" },
  "status": "Nova",
  "type": "Email"
}'
```

### Create a contact

```bash
python3 skills/konecty-create/scripts/create.py create Contact --data '{
  "name": { "first": "Maria", "last": "Silva" },
  "type": ["client"],
  "email": [{ "address": "maria@example.com" }]
}'
```

### Create an activity

```bash
# Find contact _id first
python3 skills/konecty-create/scripts/create.py lookup Contact 16503

python3 skills/konecty-create/scripts/create.py create Activity --data '{
  "subject": "Ligação de boas-vindas",
  "status": "Realizado",
  "type": "Ligação",
  "contact": { "_id": "JeSqMH6mkP5f233Rp" }
}'
```

---

## Field Type Summary

| Type | Send as |
|------|---------|
| `text` / `richText` | `"string"` — richText accepts HTML |
| `number` / `percentage` | `123` or `12.5` |
| `boolean` | `true` / `false` |
| `date` | `"2026-03-16"` |
| `dateTime` | `"2026-03-16T14:00:00.000Z"` |
| `picklist` (single) | `"option_key"` |
| `picklist` (multi) | `["key1", "key2"]` |
| `lookup` / `inheritLookup` | `{ "_id": "record-id" }` — use `create.py lookup` to find it |
| `email` | `{ "address": "a@b.com" }` |
| `phone` | `{ "countryCode": 55, "phoneNumber": "5511999999999" }` |
| `personName` | `{ "first": "João", "last": "Silva" }` |
| `money` | `{ "currency": "BRL", "value": 100.0 }` |
| `autoNumber` | **do not send** — auto-generated |

For full details and edge cases, see [references/field-types.md](references/field-types.md).

---

## Key Rules

- **`null` and `""`** in payload are stripped — equivalent to not sending the field.
- **Picklist values** must exactly match option keys (case-sensitive). Get them from `konecty-modules fields`.
- **Lookups** require `{ "_id": "..." }`. The server fetches the description fields automatically.
- **Required fields** are enforced by the API. The error `"Field X is required"` tells you exactly what to add.
- **`autoNumber` fields** (`code`) are never sent — generated server-side.
- **`_id`** is never sent — generated server-side.

## Script reference

See [scripts/create.py](scripts/create.py). Stdlib only.

```
create.py create <Document> --data '<JSON>'   # create a record
create.py lookup <Document> <term>            # find _id by code or text
```

All subcommands accept `--host` and `--token` to override credentials.
