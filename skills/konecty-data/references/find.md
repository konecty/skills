# Find & Query — user MCP

Search and query Konecty records with the `konecty` MCP server tools.
Discover modules and fields first when unknown — see [field-discovery.md](field-discovery.md).

## Query strategy — pick the right tool

| Situation | Tool |
|-----------|------|
| Single-module read, list, paginate | `records_find` |
| One specific record by id | `records_find_by_id` |
| Cross-module retrieval (joins), grouping, aggregation | `query_json` |
| Aggregated summaries over large datasets (counts, sums, averages) | `query_json` with `groupBy`/`aggregators` — do NOT paginate everything with `records_find` |
| User explicitly asks for SQL | `query_sql` (only then) |
| Pivot table / chart | `query_pivot` / `query_graph` |

Always use the technical `document` identifier from `modules_list.modules[].document`
— never a module label or display name.

---

## Filters — always via `filter_build`

Konecty uses its own structured filter format — **not** MongoDB syntax. Mongo-style
top-level field maps (e.g. `{ "status": "Ativo" }`) are **rejected** by `records_find`,
`query_pivot`, and `query_graph` with an actionable error.

**Mandatory:** call `filter_build` first:

- Input: `match` (`"and"` | `"or"`), `conditions` as array of
  `{ field, operator, value?, fieldType? }`, optional `textSearch`. No auth needed.
- When `fieldType` is provided (take it from `modules_fields`), the tool validates
  operator compatibility with the field type.
- Output: `filter` / `filterJson` — pass it as `filter` to `records_find`,
  `query_pivot`, or `query_graph`.

Resulting filter shape:

```json
{
  "match": "and",
  "conditions": [
    { "term": "status", "operator": "equals", "value": "Ativo" },
    { "term": "code", "operator": "greater_than", "value": 100 }
  ]
}
```

- `match`: how conditions combine (`"and"` / `"or"`)
- `conditions`: array of `{ term, operator, value }`
- `textSearch`: optional full-text search string (combined with conditions via `match`)
- `filters`: nested sub-groups for complex AND/OR:
  `{ "match": "and", "filters": [{ "match": "or", "conditions": [...] }] }`

### Operators

| Operator | Use for |
|----------|---------|
| `equals` / `not_equals` | Exact match |
| `contains` / `not_contains` | Substring (case-insensitive) |
| `starts_with` / `end_with` | Prefix / suffix |
| `in` / `not_in` | Match/exclude list — value must be an array |
| `greater_than` / `less_than` | Numeric/date comparison |
| `greater_or_equals` / `less_or_equals` | Inclusive comparison |
| `between` | Range — value: `{ "greater_or_equals": ..., "less_or_equals": ... }` |
| `exists` | Field presence — value: `true` or `false` |

For the operator-by-field-type matrix, control fields (`_id`, `_createdAt`, `_user`…),
and picklist/lookup value resolution, see [field-discovery.md](field-discovery.md).

### Field path rules (compound fields)

| Field type | Filter path example | Notes |
|------------|--------------------|-------|
| lookup | `contact._id` | Filter by the related record's `_id` (resolve via `field_lookup_search`) |
| email | `email.address` | Address sub-field |
| money | `value.value` | Numeric part of a money field |
| personName | `name.full` | Full concatenated name |
| address | `address.city` | Sub-field access |

### Dates

Date/dateTime values MUST be ISO 8601 with timezone — e.g. `"2026-03-18T00:00:00Z"`.
`"2026-03-18"` or `"18/03/2026"` are not accepted. Relative asks ("last 3 months")
must be converted to concrete ISO timestamps before filtering.

---

## `records_find` — single-module search

Input: `document`, optional `filter` (from `filter_build`), `sort`, `fields`
(comma-separated), `limit` (default 50), `start` (offset, default 0),
`withDetailFields`. Output: `records`, `total`, `pagination`
(`start`, `limit`, `returned`, `total`, `hasMore`, `nextStart`).

### Pagination protocol (offset-based)

1. First call with the desired `limit` (e.g. 50).
2. Check `total` and `pagination.hasMore`.
3. While `hasMore` is true → call again with `start = previous start + limit`
   (or use `pagination.nextStart`).
4. Stop when `start >= total`.

Example: `total=120, limit=50` → pages at `start=0`, `start=50`, `start=100`.
When `limit > 1000`, sort is forced to `{ _id: 1 }` for stable ordering.

For aggregated data across large datasets, prefer `query_json` with
`groupBy`/`aggregators` instead of paginating all records.

---

## `query_json` — cross-module query and aggregation

Input: a `query` object. Output: `records`, `meta`, `total`.

```json
{
  "document": "Contact",
  "filter": { "match": "and", "conditions": [] },
  "fields": "code,name,status",
  "sort": [{ "property": "_createdAt", "direction": "DESC" }],
  "limit": 1000,
  "start": 0,
  "relations": [],
  "groupBy": ["status"],
  "aggregators": { "total": { "aggregator": "count" } },
  "includeTotal": true,
  "includeMeta": false
}
```

### Relations (joins)

Relations join child modules to the parent. **Each relation must have at least one
aggregator.** Max 10 relations, max nesting depth 2; relation `limit` defaults to
1000 (max 100000).

```json
{
  "document": "Opportunity",
  "lookup": "contact",
  "filter": { "match": "and", "conditions": [{ "term": "status", "operator": "in", "value": ["Nova", "Em Visitacao"] }] },
  "fields": "code,value",
  "aggregators": {
    "activeCount": { "aggregator": "count" },
    "totalValue": { "aggregator": "sum", "field": "value.value" }
  }
}
```

- `lookup`: field in the **child** module pointing to the parent.

### Aggregators

| Aggregator | `field` required? | Description |
|------------|-------------------|-------------|
| `count` | No | Number of records |
| `countDistinct` | Yes | Count of distinct values |
| `sum` / `avg` / `min` / `max` | Yes | Numeric aggregations |
| `first` / `last` / `push` | Optional | First/last/array of records or field values |
| `addToSet` | Yes | Unique values |

For money fields use the sub-path `"fieldName.value"`
(e.g. `{ "aggregator": "sum", "field": "value.value" }`).

### groupBy

Root-level `groupBy` + root-level `aggregators` return one record per unique group:

```json
{ "document": "Contact", "groupBy": ["status"], "aggregators": { "total": { "aggregator": "count" } } }
```

### Example — contacts with opportunity count and revenue

```json
{
  "document": "Contact",
  "fields": "code,name",
  "relations": [
    {
      "document": "Opportunity",
      "lookup": "contact",
      "aggregators": {
        "totalOpportunities": { "aggregator": "count" },
        "totalRevenue": { "aggregator": "sum", "field": "value.value" }
      }
    }
  ]
}
```

Each returned Contact includes `totalOpportunities` and `totalRevenue`.

---

## `query_sql` — only on explicit request

Input: `sql`, optional `includeMeta`, `includeTotal`. Output: `records`, `meta`, `total`.

The SQL is translated to the JSON query internally. Known support: `SELECT` with
aliases, `INNER/LEFT JOIN`, `WHERE` with `AND`/`OR`, `GROUP BY`, `ORDER BY`,
`LIMIT`/`OFFSET`, and `COUNT`/`SUM`/`AVG`/`MIN`/`MAX`. Not supported: `RIGHT/CROSS
JOIN`, CTEs (`WITH`), `UNION`, `HAVING`, subqueries. When a request exceeds this,
use `query_json` instead.

```sql
SELECT ct.code, ct.name, COUNT(o._id) AS deals
FROM Contact ct INNER JOIN Opportunity o ON ct._id = o.contact._id
GROUP BY ct.code, ct.name ORDER BY deals DESC LIMIT 50
```

---

## `query_pivot` / `query_graph`

- `query_pivot`: input `document`, `pivotConfig`, optional filter/sort/fields/limit → output `pivot`.
- `query_graph`: input `document`, `graphConfig`, optional filter/sort/fields/limit → output `graph`.

Same filter rules as `records_find` (use `filter_build`). The matching `render_pivot_widget`
/ `render_graph_widget` tools are host-dependent widgets — optional, never required.
