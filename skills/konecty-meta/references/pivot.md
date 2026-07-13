# Meta Pivot — report definitions

Manage pivot metas with `meta_pivot_upsert` on the `konecty-admin` MCP server.

## Tool

`meta_pivot_upsert` — input: `id` (`{Document}:pivot:{Name}`, e.g.
`Activity:pivot:Default`), `pivot` (the **complete** pivot meta). Output: `result`.

**Full-replace semantics**: send the whole definition; start from the current one
(see [read.md](read.md)).

## Structure essentials

- `_id` = same as `id`; `type: "pivot"`; `document`; `name`; bilingual
  `label`/`plurals`.
- `rows`: array of row grouping fields —
  `{ "name": "_user.group", "linkField": "_user.group", "visible": true, "label": {...} }`.
- `columns`: **object-map** of column fields (same shape as list columns).
- `values`: array of aggregated values —
  `{ "name": "code", "linkField": "code", "visible": true, "label": {...}, "aggregator": "count" }`.
  Aggregators: `count`, `sum`, `avg`, `min`, `max`.
- `filter`, `sorters`, `rowsPerPage`, `refreshRate`: same structures as list metas
  ([list.md](list.md)).
