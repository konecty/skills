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
