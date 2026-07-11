# Konecty Find

Search and query records in any Konecty module.

## Prerequisites

Requires credentials from **konecty-session**: `KONECTY_URL` and `KONECTY_TOKEN` in `~/.konecty/.env`.
If not present or expired, ask the user to run `konecty-session` first.

If the module name or field names are unknown, use **konecty-modules** to discover them.

## APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/rest/data/:document/find` | GET / POST | Simple document search |
| `/rest/query/json` | POST | Cross-module query with relations and aggregators |
| `/rest/query/sql` | POST | SQL query (translated to JSON query internally) |

## Transport: MCP-first with automatic REST fallback

`find` / `query` / `sql` issue their reads through the Konecty **User MCP** server first
(`POST /mcp`, stateless Streamable HTTP — the `records_find` / `query_json` / `query_sql` tools),
and fall back to the REST endpoints above automatically. The migration is transparent: the stdout
records array and the `# Total: N  Returned: M` stderr summary are identical on both paths, so
`jq` pipelines are unaffected.

- **Auth** — the same `KONECTY_TOKEN` (`authId`) is reused, sent to `/mcp` as
  `Authorization: Bearer <authId>`. No OAuth, no new login step.
- **Fallback notice** — when a fallback fires, a one-line notice `Busca feita via API direta (REST).`
  is printed **first** on **stderr** (before the records). The happy MCP path is silent. A `404`
  (MCP endpoint absent — older Konecty) falls back **silently**. `401` (bad/expired token) and MCP
  tool-validation errors (bad document / filter / sort) are **surfaced, not** silently retried on REST.
- **`KONECTY_MCP` env var** controls the transport:

  | Value | Behavior |
  |-------|----------|
  | unset / `1` | MCP-first with automatic REST fallback (**default**) |
  | `0` | REST-only — skip MCP entirely (avoids a wasted round-trip where MCP is known-absent, and the nested-filter divergence below) |
  | `only` | MCP with **no** fallback (strict / diagnostic mode) |

### Operational prerequisite (live MCP path)

To exercise the **live** MCP path (not just fallback) the Konecty namespace must have the User MCP
enabled and include the caller's role `_id` in **`mcpRoleIds`** (deny-by-default — an empty list
means every caller gets `403 mcp_access_denied` and transparently falls back to REST). This is a
`konecty-meta namespace` (admin) setting. An unconfigured namespace still works via the REST
fallback, with the notice above.

### Known divergences

- **Nested filters (`filters` nested 2+ levels)** — the MCP `KonFilter` validator silently strips
  `filters` groups nested two or more levels deep, so the **same** `--filter` can return a
  **superset** of records via MCP vs REST, with no error or warning. This is rare (Konecty's own
  `filter_build` never generates such filters; single-level `filters` are identical on both paths).
  **Workaround:** use `KONECTY_MCP=0` (force REST) for deeply nested filters until the Konecty-side
  fix lands. The divergence is accepted and documented rather than worked around in the skill; the
  fix belongs in the server's `KonFilter` schema. See **ADR-0008** (repo
  `docs/adr/0008-known-nested-filter-divergence.md`).

## Script

```bash
python3 scripts/find.py find <Document> [options]    # simple find
python3 scripts/find.py query <Document> [options]   # cross-module JSON query
python3 scripts/find.py sql "<SQL>" [options]         # SQL query
```

All subcommands accept `--host` and `--token` to override credentials, and `--output json|ndjson`.

### `find` options

| Option | Description |
|--------|-------------|
| `--filter '<JSON>'` | KonFilter as JSON string |
| `--fields 'f1,f2'` | Comma-separated field names to return |
| `--sort 'field:asc'` | Sort shorthand or JSON array |
| `--limit N` | Max records (default: 50, -1 for no limit) |
| `--start N` | Offset/skip for pagination (default: 0) |
| `--post` | Force POST even without filter |

### `query` options

Same as `find`, plus:

| Option | Description |
|--------|-------------|
| `--relations '<JSON>'` | Relations array as JSON string |
| `--include-meta` | Request `_meta` line as first NDJSON record |
| `--no-total` | Skip total count calculation (faster) |

---

## Quick Examples

### Simple filter by field value

```bash
python3 scripts/find.py find Contact \
  --filter '{"match":"and","conditions":[{"term":"status","operator":"equals","value":"active"}]}' \
  --fields "code,name,status" --limit 20
```

### Full-text search

```bash
python3 scripts/find.py find Contact \
  --filter '{"match":"and","textSearch":"John Doe"}' \
  --fields "code,name,email"
```

### Date range with dynamic variable

```bash
python3 scripts/find.py find Opportunity \
  --filter '{"match":"and","conditions":[{"term":"createdAt","operator":"between","value":{"greater_or_equals":"$monthsAgo:3","less_or_equals":"$now"}}]}'
```

### Lookup field filter

```bash
python3 scripts/find.py find Opportunity \
  --filter '{"match":"and","conditions":[{"term":"contact._id","operator":"equals","value":"<contactId>"}]}'
```

### Cross-module query with relation aggregation

```bash
python3 scripts/find.py query Contact \
  --fields "code,name" \
  --relations '[{"document":"Opportunity","lookup":"contact","aggregators":{"count":{"aggregator":"count"},"totalValue":{"aggregator":"sum","field":"value.value"}}}]' \
  --limit 100
```

### SQL query

```bash
python3 scripts/find.py sql \
  "SELECT ct.code, ct.name, COUNT(o._id) AS deals FROM Contact ct INNER JOIN Opportunity o ON ct._id = o.contact._id GROUP BY ct.code, ct.name ORDER BY deals DESC LIMIT 50"
```

### Pagination

```bash
# Page 1
python3 scripts/find.py find Contact --limit 50 --start 0
# Page 2
python3 scripts/find.py find Contact --limit 50 --start 50
```

---

## Filter Structure

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

- `match`: `"and"` | `"or"` — how to combine conditions
- `conditions`: array of `{ term, operator, value }` objects
- `textSearch`: full-text search across indexed text fields
- `filters`: nested sub-groups for complex AND/OR combinations
- A condition with `"disabled": true` is ignored at runtime

### Common operators

| Operator | Use for |
|----------|---------|
| `equals` / `not_equals` | Exact match |
| `contains` / `not_contains` | Substring (case-insensitive) |
| `starts_with` / `end_with` | Prefix / suffix |
| `in` / `not_in` | Match/exclude a list — `value` must be an array |
| `greater_than` / `less_than` | Numeric/date comparison |
| `greater_or_equals` / `less_or_equals` | Inclusive numeric/date comparison |
| `between` | Inclusive range — `value: { "greater_or_equals": ..., "less_or_equals": ... }` |
| `exists` | Field presence — `value: true` or `false` |

For the full operator list, field-type matrix, dot-notation for sub-fields, and dynamic date variables (`$now`, `$monthsAgo:N`, `$user`, etc.), see the Filter Operators Reference section below.

---

## Response Format

`/rest/data/:document/find` returns JSON:

```json
{ "success": true, "total": 120, "data": [...] }
```

`/rest/query/json` and `/rest/query/sql` return **NDJSON** (`application/x-ndjson`), one object per line. With `includeMeta: true`, the first line is `{ "_meta": { "success": true, "total": N } }`.

The script prints `# Total: N  Returned: N` to stderr and the data to stdout, making it easy to pipe: `python3 scripts/find.py find Contact | jq .`.

---

## Further Reference

- Filter Operators Reference — Complete operator list, operators by field type, sub-field paths, dynamic values, nested filter examples (see below)
- Cross-Module Query Reference — Full `query/json` schema, relations, aggregators, groupBy, SQL interface (see below)

---

# Konecty Filter Operators Reference

## KonFilter Structure

```json
{
  "match": "and",
  "conditions": [
    { "term": "status", "operator": "equals", "value": "active" },
    { "term": "createdAt", "operator": "greater_than", "value": "$monthsAgo:3" }
  ],
  "textSearch": "optional full-text search string",
  "filters": [
    {
      "match": "or",
      "conditions": [
        { "term": "priority", "operator": "equals", "value": "high" },
        { "term": "priority", "operator": "equals", "value": "urgent" }
      ]
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `match` | `"and"` \| `"or"` | How to combine `conditions` and nested `filters` |
| `conditions` | array or object | Array of `Condition` objects (or keyed object — both are valid) |
| `textSearch` | string | Full-text search across indexed text fields |
| `filters` | array | Nested sub-groups for complex AND/OR logic (each has `match` + `conditions`) |

### Condition

```json
{ "term": "fieldName", "operator": "equals", "value": "someValue" }
```

| Field | Description |
|-------|-------------|
| `term` | Field path. Use dot notation for sub-fields: `email.address`, `name.full`, `lookup._id`, `money.value` |
| `operator` | One of the operators listed below |
| `value` | The comparison value. Type depends on operator and field type |
| `disabled` | If `true`, condition is ignored at runtime (useful for optional filters) |

---

## All Operators

| Operator | MongoDB equivalent | Description |
|----------|--------------------|-------------|
| `equals` | `{ field: value }` | Exact match |
| `not_equals` | `$ne` | Not equal |
| `contains` | `$regex` (case-insensitive, accent-aware) | Substring match |
| `not_contains` | `$not: $regex` | Does not contain substring |
| `starts_with` | `$regex: '^...'` | String starts with value |
| `end_with` | `$regex: '...$'` | String ends with value |
| `in` | `$in` | Value is in array |
| `not_in` | `$nin` | Value is not in array |
| `greater_than` | `$gt` | Strictly greater than |
| `greater_or_equals` | `$gte` | Greater than or equal |
| `less_than` | `$lt` | Strictly less than |
| `less_or_equals` | `$lte` | Less than or equal |
| `between` | `$gte` + `$lte` | Inclusive range (see value format below) |
| `exists` | `$exists` | Field exists (value: `true`) or does not exist (value: `false`) |
| `current_user` | — | Matches documents owned by the authenticated user |
| `not_current_user` | — | Excludes documents owned by the authenticated user |
| `current_user_group` | — | Matches documents belonging to the user's primary group |
| `not_current_user_group` | — | Excludes the user's primary group |
| `current_user_groups` | — | Matches documents in any of the user's secondary groups |

### `between` value format

```json
{
  "term": "createdAt",
  "operator": "between",
  "value": {
    "greater_or_equals": "2024-01-01",
    "less_or_equals": "2024-12-31"
  }
}
```

Both bounds are inclusive. Values can be ISO date strings or dynamic variables (e.g. `$startOfMonth`, `$now`).

### `in` / `not_in` value format

```json
{ "term": "status", "operator": "in", "value": ["active", "pending"] }
```

Value must be an array.

---

## Operators by Field Type

| Field Type | Supported Operators |
|------------|---------------------|
| `text` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `url` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `email` (use `email.address`) | `exists`, `equals`, `not_equals`, `in`, `not_in`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `phone` (use `phone.phoneNumber`) | `exists`, `equals`, `not_equals`, `in`, `not_in`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `personName` (use `name.full`) | `exists`, `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `richText` | `exists`, `contains` |
| `number` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `autoNumber` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `percentage` | `exists`, `equals`, `not_equals`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `money` (use `money.value`) | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `date` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `dateTime` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `boolean` | `exists`, `equals`, `not_equals` |
| `picklist` | `exists`, `equals`, `not_equals`, `in`, `not_in` |
| `lookup` (use `lookup._id`) | `exists`, `equals`, `not_equals`, `in`, `not_in` |
| `ObjectId` | `exists`, `equals`, `not_equals`, `in`, `not_in` |

### Compound field path examples

| Field type | term example | Notes |
|------------|-------------|-------|
| `email` | `email.address` | Access the address sub-field |
| `phone` | `phone.phoneNumber` | Access the phone number sub-field |
| `personName` | `name.full` | Full concatenated name |
| `money` | `value.value` | The numeric part of a money field |
| `lookup` | `contact._id` | The `_id` of the related document |
| `address` | `address.city` | Sub-field access (city, state, country, etc.) |

---

## Dynamic Values

Use these strings as `value` in date/dateTime conditions instead of hard-coded dates.

| Variable | Description |
|----------|-------------|
| `$now` | Current date and time |
| `$today` | Start of today |
| `$yesterday` | Start of yesterday |
| `$startOfWeek` | Start of the current week |
| `$startOfMonth` | Start of the current month |
| `$startOfYear` | Start of the current year |
| `$endOfDay` | End of today |
| `$endOfWeek` | End of the current week |
| `$endOfMonth` | End of the current month |
| `$endOfYear` | End of the current year |
| `$hoursAgo:N` | N hours ago |
| `$hoursFromNow:N` | N hours from now |
| `$daysAgo:N` | N days ago |
| `$daysFromNow:N` | N days from now |
| `$monthsAgo:N` | N months ago |
| `$monthsFromNow:N` | N months from now |

User-context variables (resolved at runtime for the authenticated user):

| Variable | Description |
|----------|-------------|
| `$user` | Current user's `_id` |
| `$group` | Current user's primary group `_id` |
| `$groups` | Array of the user's secondary group `_ids` |
| `$allgroups` | Array of all group `_ids` (primary + secondary) |
| `$user.field` | Access a specific field from the user document (e.g. `$user.branch._id`) |

---

## Nested Filter Examples

### AND + OR combined

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

Means: `status == "active" AND (priority == "high" OR dueDate < today)`

### Lookup field filter

```json
{
  "match": "and",
  "conditions": [
    { "term": "contact._id", "operator": "in", "value": ["<objectId1>", "<objectId2>"] }
  ]
}
```

### Optional / disabled condition

Set `disabled: true` to include the condition in the structure (e.g. stored filters) but ignore it at query time:

```json
{ "term": "status", "operator": "equals", "value": "active", "disabled": true }
```

---

## textSearch

`textSearch` performs full-text search across all indexed text fields of the module. It is combined with `conditions` using the `match` logic.

```json
{
  "match": "and",
  "textSearch": "John Doe",
  "conditions": [
    { "term": "status", "operator": "equals", "value": "active" }
  ]
}
```

---

# Cross-Module Query Reference (`/rest/query/json`)

## Overview

`POST /rest/query/json` returns NDJSON (`application/x-ndjson`), one JSON object per line. It supports:

- Filtering with `KonFilter`
- Joining related documents (`relations`)
- Grouping and aggregation (`groupBy`, `aggregators`)
- Pagination and sorting

## Full Request Schema

```json
{
  "document": "Contact",
  "filter": { "match": "and", "conditions": [...] },
  "fields": "code,name,status",
  "sort": [{ "property": "name", "direction": "ASC" }],
  "limit": 1000,
  "start": 0,
  "relations": [...],
  "groupBy": [],
  "aggregators": {},
  "includeTotal": true,
  "includeMeta": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `document` | string | required | Module/document name (internal name, e.g. `"Contact"`) |
| `filter` | KonFilter | — | Filter conditions (see filter-operators.md) |
| `fields` | string | all fields | Comma-separated field names to return |
| `sort` | array \| string | — | Sort order — see Sort section below |
| `limit` | integer | 1000 | Max primary records. Min: 1, Max: 100,000 |
| `start` | integer | 0 | Offset for pagination |
| `relations` | array | [] | Related documents to join (max 10) |
| `groupBy` | array | [] | Field names to group by |
| `aggregators` | object | {} | Named aggregations on primary document fields |
| `includeTotal` | boolean | true | Whether to compute total record count |
| `includeMeta` | boolean | false | If true, first NDJSON line is a `_meta` object |

### Limits and constants

- `DEFAULT_PRIMARY_LIMIT` = 1000
- `MAX_RELATION_LIMIT` = 100,000
- `MAX_RELATIONS` = 10 (max relations per query)
- `MAX_NESTING_DEPTH` = 2 (relations can have nested relations up to depth 2)

---

## Sort

The `sort` field accepts a JSON array of sort items or a JSON string representation:

```json
[
  { "property": "name", "direction": "ASC" },
  { "property": "createdAt", "direction": "DESC" }
]
```

| Field | Values | Default |
|-------|--------|---------|
| `property` | Field name | required |
| `direction` | `"ASC"` \| `"DESC"` | `"ASC"` |

Special sort key `$textScore` sorts by full-text search relevance score (only when `textSearch` is used).

**Note:** If `limit > 1000`, the sort is forced to `{ _id: 1 }` for performance.

---

## Relations

Each relation joins another document to the primary document.

```json
{
  "document": "Opportunity",
  "lookup": "contact",
  "filter": { "match": "and", "conditions": [...] },
  "fields": "code,name,status,value",
  "sort": [{ "property": "createdAt", "direction": "DESC" }],
  "limit": 1000,
  "start": 0,
  "aggregators": {
    "count": { "aggregator": "count" },
    "totalValue": { "aggregator": "sum", "field": "value.value" }
  },
  "relations": []
}
```

| Field | Type | Description |
|-------|------|-------------|
| `document` | string | Related document name |
| `lookup` | string | Field name on the related document that references the primary (`_id`) |
| `on` | object | Optional explicit join key override: `{ "left": "primaryField", "right": "relatedField" }` |
| `filter` | KonFilter | Optional filter on the related document |
| `fields` | string | Comma-separated fields to return from related records |
| `sort` | array | Sort for related records |
| `limit` | integer | Max related records per primary (default: 1000, max: 100,000) |
| `start` | integer | Offset for related records |
| `aggregators` | object | Named aggregations on related document fields |
| `relations` | array | Nested relations (max nesting depth: 2) |

### Join key (`lookup` vs `on`)

- **`lookup`** — the most common case: specify the field name on the related document that stores the reference to the primary document's `_id`. Example: `"lookup": "contact"` means `Opportunity.contact._id == Contact._id`.
- **`on`** — explicit override: `{ "left": "primaryField._id", "right": "relatedField._id" }`.

---

## Aggregators

Aggregators compute summary values over the records in a document (primary or related).

```json
"aggregators": {
  "myAggName": { "aggregator": "count" },
  "totalRevenue": { "aggregator": "sum", "field": "revenue.value" },
  "avgScore": { "aggregator": "avg", "field": "score" }
}
```

| Aggregator | `field` required | Description |
|------------|-----------------|-------------|
| `count` | No | Count of records |
| `countDistinct` | Yes | Count of distinct values of `field` |
| `sum` | Yes | Sum of `field` values |
| `avg` | Yes | Average of `field` values |
| `min` | Yes | Minimum `field` value |
| `max` | Yes | Maximum `field` value |
| `first` | Yes | First value of `field` |
| `last` | Yes | Last value of `field` |
| `push` | Yes | Array of all `field` values |
| `addToSet` | Yes | Array of distinct `field` values |

Aggregation results are merged into each row at the key name. Example output for an `Opportunity` relation with `{ "count": { "aggregator": "count" } }`:

```json
{
  "_id": "...",
  "name": "Acme Corp",
  "Opportunity": [{ "_id": "...", "name": "Deal 1" }],
  "Opportunity_count": 5
}
```

---

## GroupBy

Specify field names to group primary records:

```json
"groupBy": ["status", "priority"]
```

When `groupBy` is non-empty, results are grouped by those fields. Aggregators are applied per group.

---

## Response Format

Responses are NDJSON (`application/x-ndjson`): one JSON object per line.

### Without `includeMeta` (default)

```ndjson
{"_id":"...","name":"Alice","code":1001}
{"_id":"...","name":"Bob","code":1002}
```

The `X-Total-Count` HTTP header contains the total count (when `includeTotal: true`).

### With `includeMeta: true`

First line is the `_meta` object:

```ndjson
{"_meta":{"success":true,"total":120}}
{"_id":"...","name":"Alice","code":1001}
{"_id":"...","name":"Bob","code":1002}
```

---

## SQL Interface (`/rest/query/sql`)

`POST /rest/query/sql` accepts a SQL `SELECT` statement and translates it to the JSON query format internally.

```json
{
  "sql": "SELECT ct.code, ct.name, COUNT(o._id) AS activeOpportunities FROM Contact ct INNER JOIN Opportunity o ON ct._id = o.contact._id WHERE ct.status = 'active' GROUP BY ct.code, ct.name ORDER BY ct.name ASC LIMIT 100",
  "includeTotal": true,
  "includeMeta": false
}
```

### SQL → Konecty operator mapping

| SQL | Konecty |
|-----|---------|
| `=` | `equals` |
| `!=` / `<>` | `not_equals` |
| `<` | `less_than` |
| `>` | `greater_than` |
| `<=` | `less_or_equals` |
| `>=` | `greater_or_equals` |
| `IN (...)` | `in` |
| `NOT IN (...)` | `not_in` |
| `LIKE '%...'` | `contains` |
| `IS NULL` | `equals` (null) |
| `IS NOT NULL` | `not_equals` (null) |

### Supported SQL features

- `SELECT` with aliases
- `INNER JOIN` and `LEFT JOIN`
- `WHERE` with `AND` / `OR`
- `GROUP BY`
- `ORDER BY`
- `LIMIT` / `OFFSET`
- Aggregate functions: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`

### Not supported

- `RIGHT JOIN`, `CROSS JOIN`
- `WITH` (CTE)
- `UNION`
- `HAVING`
- Subqueries

---

## Complete Example

Find all active contacts with their open opportunity count and total value:

```bash
python3 scripts/find.py query Contact \
  --filter '{"match":"and","conditions":[{"term":"status","operator":"equals","value":"active"}]}' \
  --fields "code,name,email" \
  --sort "name:asc" \
  --limit 100 \
  --relations '[{
    "document": "Opportunity",
    "lookup": "contact",
    "filter": {"match":"and","conditions":[{"term":"status","operator":"not_equals","value":"closed"}]},
    "aggregators": {
      "count": {"aggregator": "count"},
      "totalValue": {"aggregator": "sum", "field": "value.value"}
    }
  }]' \
  --include-meta
```
