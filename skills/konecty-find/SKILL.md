---
name: konecty-find
description: Searches and queries records in Konecty modules using the REST API. Supports simple document find (/rest/data/:document/find with GET or POST), cross-module JSON queries with relations and aggregators (/rest/query/json), and SQL queries (/rest/query/sql). Use when the user wants to search, list, filter, or query records in any Konecty module; needs to filter by field values (equals, contains, between, greater_than, in, exists, etc.); wants to join related documents and aggregate data (count, sum, avg); or needs pagination and sorting. Requires an active konecty-session (KONECTY_URL and KONECTY_TOKEN in ~/.konecty/.env). For unknown modules or field names, use konecty-modules first.
---

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

For the full operator list, field-type matrix, dot-notation for sub-fields, and dynamic date variables (`$now`, `$monthsAgo:N`, `$user`, etc.), see [references/filter-operators.md](references/filter-operators.md).

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

- [references/filter-operators.md](references/filter-operators.md) — Complete operator list, operators by field type, sub-field paths, dynamic values, nested filter examples
- [references/cross-module-query.md](references/cross-module-query.md) — Full `query/json` schema, relations, aggregators, groupBy, SQL interface
