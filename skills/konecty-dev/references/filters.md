# Konecty Filter & Query Language Reference

Single authoritative reference for `KonFilter` — the filter/query language used across the Python SDK, TypeScript SDK, and REST API. All three link here; do not duplicate this content in those docs.

---

## 1. Filter Structure

A filter is a plain JSON object (`KonFilter`) with the following shape:

```json
{
  "match": "and",
  "conditions": [
    { "term": "status", "operator": "equals", "value": "active" }
  ],
  "textSearch": "optional full-text string",
  "filters": [
    { "match": "or", "conditions": [...] }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `match` | `"and"` \| `"or"` | yes | How to combine `conditions` entries and nested `filters` groups |
| `conditions` | array or keyed object of `Condition` | no | Individual field comparisons |
| `textSearch` | string | no | Full-text search across all indexed text fields; combined with `conditions` via `match` |
| `filters` | array of sub-groups | no | Nested AND/OR groups; each entry has `match` + `conditions` of its own |

### Condition shape

```json
{ "term": "fieldName", "operator": "equals", "value": "someValue" }
```

| Field | Description |
|-------|-------------|
| `term` | Field path. Use dot notation for sub-fields (see section 3). |
| `operator` | One of the operator strings listed in section 2. |
| `value` | Comparison value. Type depends on operator and field type. Optional/nullable for some operators. |
| `disabled` | If `true`, the condition is included in the structure but ignored at query time. Useful for storing optional filters. |

---

## 2. Operators

The complete operator list, verified from `src/imports/model/Filter.ts` (operator strings are stored as plain strings at the Zod layer; the canonical list below is drawn from the runtime implementation and the existing skill reference).

| Operator | Value format | Example |
|----------|-------------|---------|
| `equals` | scalar | `{"term":"status","operator":"equals","value":"active"}` |
| `not_equals` | scalar | `{"term":"status","operator":"not_equals","value":"closed"}` |
| `contains` | string | `{"term":"name.full","operator":"contains","value":"silva"}` |
| `not_contains` | string | `{"term":"name.full","operator":"not_contains","value":"test"}` |
| `starts_with` | string | `{"term":"email.address","operator":"starts_with","value":"admin"}` |
| `end_with` | string | `{"term":"email.address","operator":"end_with","value":".com"}` |
| `in` | array | `{"term":"status","operator":"in","value":["active","pending"]}` |
| `not_in` | array | `{"term":"status","operator":"not_in","value":["deleted","archived"]}` |
| `greater_than` | scalar or dynamic variable | `{"term":"createdAt","operator":"greater_than","value":"$monthsAgo:3"}` |
| `greater_or_equals` | scalar or dynamic variable | `{"term":"score","operator":"greater_or_equals","value":80}` |
| `less_than` | scalar or dynamic variable | `{"term":"dueDate","operator":"less_than","value":"$today"}` |
| `less_or_equals` | scalar or dynamic variable | `{"term":"price.value","operator":"less_or_equals","value":5000}` |
| `between` | object with `greater_or_equals` + `less_or_equals` keys | See below |
| `exists` | boolean | `{"term":"phone","operator":"exists","value":true}` |
| `current_user` | — (no value needed) | `{"term":"_user._id","operator":"current_user"}` |
| `not_current_user` | — | `{"term":"_user._id","operator":"not_current_user"}` |
| `current_user_group` | — | `{"term":"_user.group._id","operator":"current_user_group"}` |
| `not_current_user_group` | — | `{"term":"_user.group._id","operator":"not_current_user_group"}` |
| `current_user_groups` | — | `{"term":"_user.group._id","operator":"current_user_groups"}` |

### `between` value format

Both bounds are inclusive. Values may be ISO date strings, numbers, or dynamic variables.

```json
{
  "term": "createdAt",
  "operator": "between",
  "value": {
    "greater_or_equals": "$startOfMonth",
    "less_or_equals": "$endOfMonth"
  }
}
```

### Operators by field type

| Field type | Supported operators |
|------------|---------------------|
| `text`, `url` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `email` (use `email.address`) | same as text |
| `phone` (use `phone.phoneNumber`) | same as text |
| `personName` (use `name.full`) | `exists`, `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `richText` | `exists`, `contains` |
| `number`, `autoNumber` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `percentage`, `money` (use `money.value`) | same as number |
| `date`, `dateTime` | same as number (values are ISO strings or dynamic variables) |
| `boolean` | `exists`, `equals`, `not_equals` |
| `picklist` | `exists`, `equals`, `not_equals`, `in`, `not_in` |
| `lookup` (use `lookup._id`) | `exists`, `equals`, `not_equals`, `in`, `not_in` |
| `ObjectId` | `exists`, `equals`, `not_equals`, `in`, `not_in` |

---

## 3. Field Terms and Dot Notation

Simple fields are referenced by name. Compound types and lookups require a sub-field path:

| Field type | `term` example | Notes |
|------------|----------------|-------|
| Simple text | `status` | Direct field name |
| `email` | `email.address` | Sub-field of the email type |
| `phone` | `phone.phoneNumber` | Sub-field of the phone type |
| `personName` | `name.full` | Concatenated full name |
| `money` | `value.value` | Numeric part of the money type |
| `lookup` | `contact._id` | `_id` of the linked document |
| `address` | `address.city` | Any address sub-field (city, state, country, …) |

---

## 4. Dynamic Date Values

Use these strings as `value` in `date` / `dateTime` conditions instead of hard-coded timestamps.

| Variable | Description |
|----------|-------------|
| `$now` | Current date and time |
| `$today` | Start of today |
| `$yesterday` | Start of yesterday |
| `$startOfWeek` / `$endOfWeek` | Start / end of the current week |
| `$startOfMonth` / `$endOfMonth` | Start / end of the current month |
| `$startOfYear` / `$endOfYear` | Start / end of the current year |
| `$endOfDay` | End of today |
| `$hoursAgo:N` / `$hoursFromNow:N` | N hours ago / from now |
| `$daysAgo:N` / `$daysFromNow:N` | N days ago / from now |
| `$monthsAgo:N` / `$monthsFromNow:N` | N months ago / from now |

User-context variables (resolved per authenticated user at runtime):

| Variable | Description |
|----------|-------------|
| `$user` | Authenticated user's `_id` |
| `$group` | User's primary group `_id` |
| `$groups` | Array of secondary group `_ids` |
| `$allgroups` | All group `_ids` (primary + secondary) |
| `$user.field` | Specific field from the user document (e.g. `$user.branch._id`) |

---

## 5. Nested Filter Groups

Use `filters` to combine AND and OR logic at different levels.

```json
{
  "match": "and",
  "conditions": [
    { "term": "status", "operator": "equals", "value": "active" }
  ],
  "filters": [
    {
      "match": "or",
      "conditions": [
        { "term": "priority", "operator": "equals", "value": "high" },
        { "term": "dueDate", "operator": "less_than", "value": "$today" }
      ]
    }
  ]
}
```

Reads as: `status == "active" AND (priority == "high" OR dueDate < today)`.

Nesting is supported to arbitrary depth inside `filters`. Each nested group may omit `match` (defaults to the outer group's logic in practice, but always set it explicitly for clarity).

---

## 6. Cross-Module Relations (`/rest/query/json`)

The `POST /rest/query/json` endpoint extends a standard find call with a `relations` array. Each relation joins another module via an inferred lookup field and computes aggregators server-side.

### Relation shape

```json
{
  "document": "Opportunity",
  "lookup": "contact",
  "filter": { "match": "and", "conditions": [...] },
  "fields": "code,status,value",
  "sort": [{ "property": "createdAt", "direction": "DESC" }],
  "limit": 100,
  "aggregators": {
    "count":      { "aggregator": "count" },
    "totalValue": { "aggregator": "sum",  "field": "value.value" },
    "recent":     { "aggregator": "push", "field": "status" }
  },
  "relations": []
}
```

| Field | Description |
|-------|-------------|
| `document` | Related module name |
| `lookup` | Field name on the related document that holds the reference to the primary document's `_id`. Example: `"lookup": "contact"` means `Opportunity.contact._id == Contact._id` |
| `on` | Optional explicit join override: `{ "left": "primaryField._id", "right": "relatedField._id" }` |
| `filter` | `KonFilter` applied to the related document (same syntax as a top-level filter) |
| `fields` | Comma-separated fields to return from each related record |
| `sort` | Sort order for related records (critical for `first` / `last` aggregators) |
| `limit` | Max related records per primary record (default: 1000, max: 100 000) |
| `aggregators` | Named aggregations: output key → `{ aggregator, field? }` |
| `relations` | Nested sub-relations (max nesting depth: 2) |

### Aggregators

| Aggregator | `field` required | Returns |
|------------|-----------------|---------|
| `count` | no | `number` — count of matching related records |
| `sum` | yes | `number` — sum of numeric field |
| `avg` | yes | `number` — average of numeric field |
| `min` | yes | `any` — minimum value |
| `max` | yes | `any` — maximum value |
| `first` | optional | First record or field value (per `sort`) |
| `last` | optional | Last record or field value (per `sort`) |
| `push` | optional | Array of all records or field values |
| `addToSet` | yes | Array of distinct field values |

Aggregator results are merged into each primary record at the key name. Example: `"count": { "aggregator": "count" }` → the key `count` is added to each primary record with the total related record count.

### Full cross-module query example

```json
{
  "document": "Contact",
  "filter": {
    "match": "and",
    "conditions": [{ "term": "status", "operator": "equals", "value": "active" }]
  },
  "fields": "code,name",
  "limit": 100,
  "relations": [
    {
      "document": "Opportunity",
      "lookup": "contact",
      "filter": {
        "match": "and",
        "conditions": [{ "term": "status", "operator": "not_equals", "value": "closed" }]
      },
      "aggregators": {
        "openDeals":   { "aggregator": "count" },
        "totalValue":  { "aggregator": "sum", "field": "value.value" }
      }
    }
  ]
}
```

Returns NDJSON: one JSON object per line, each Contact record augmented with `openDeals` and `totalValue`.

---

## 7. Using Filters Across Tracks

The same `KonFilter` JSON is passed identically in all three tracks. Refer to the linked docs for SDK-specific wrapping — do not duplicate filter syntax there.

**Python SDK (`konecty-data` skill)** — pass as `--filter` argument or the `filter` key in a script call:
```bash
python3 scripts/find.py find Contact \
  --filter '{"match":"and","conditions":[{"term":"status","operator":"equals","value":"active"}]}'
```
Full reference: `skills/konecty-data/references/find.md`

**TypeScript / REST `find`** — pass as the `filter` query-string parameter (GET) or body field (POST) to `/rest/data/:document/find`:
```http
POST /rest/data/Contact/find
Authorization: <token>
Content-Type: application/json

{"filter":{"match":"and","conditions":[{"term":"status","operator":"equals","value":"active"}]},"limit":50}
```
Full reference: `docs/en/api.md`

**REST cross-module query** — embed the same object as the `filter` field in the `POST /rest/query/json` body (and in any `relations[].filter`):
```json
{ "document": "Contact", "filter": { "match": "and", "conditions": [...] }, "relations": [...] }
```
Full cross-module schema: `docs/en/rfc/0001-cross-module-query-api.md`
