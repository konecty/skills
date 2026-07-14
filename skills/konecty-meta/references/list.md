# Meta List — columns, filters, sorters

Manage list metas with `meta_list_upsert` on the `konecty-admin` MCP server.

## Tool

`meta_list_upsert` — input: `id` (`{Document}:list:{Name}`, e.g.
`Activity:list:Default`), `list` (the **complete** list meta). Output: `result`.

**Full-replace semantics**: the payload replaces the stored meta entirely. Start
from the current definition (metadata repo, previous read, or user-provided — see
[read.md](read.md)), apply the change, send the whole object.

## Structure essentials

- `_id` = the same value as `id`; `type: "list"`; `document` = parent document;
  `name` = list name; bilingual `label`/`plurals`.
- `columns` is an **object-map** `{ "columnName": { ... } }`, not an array:

```json
"columns": {
  "code":   { "name": "code", "linkField": "code", "visible": true, "minWidth": 60, "sort": 0 },
  "status": { "name": "status", "linkField": "status", "visible": true, "minWidth": 100, "sort": 1 }
}
```

- `linkField` maps the column to a field in the parent document — the field must
  exist there (check via `meta_read` of the document).
- `sorters`: default sort, `[{ "term": "code", "direction": "desc" }]`.
- `filter`: KonFilter; list filters may use an object-map of conditions with UI
  extras (`editable`, `style`, `sort`).
- `refreshRate` / `rowsPerPage`: `{ "options": [...], "default": N }`.
- Optional: `view` (form opened on click), `loadDataAtOpen`, `calendars`, `boards`.

## Typical edits

- **Add a column**: add an entry to `columns` with `name`, `linkField`, `visible`,
  `sort` (display order), optional `minWidth`/`style`.
- **Remove a column**: delete the entry.
- **Change default filter/sort**: edit `filter` / `sorters`.

Full schema table: [read.md](read.md#list).
