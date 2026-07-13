# Meta View — form layouts

Manage view (form) metas with `meta_view_upsert` on the `konecty-admin` MCP server.

## Tool

`meta_view_upsert` — input: `id` (`{Document}:view:{Name}`, e.g.
`Activity:view:Default`), `view` (the **complete** view meta). Output: `result`.

**Full-replace semantics**: send the whole definition; start from the current one
(see [read.md](read.md)).

## Structure essentials

- `_id` = same as `id`; `type: "view"`; `document`; `name`; bilingual
  `label`/`plurals` — `label` supports `{field}` interpolation for dynamic titles
  (e.g. `"{code}: {type} - {subject}"`).
- `visuals` is a **recursive tree**:
  - `visualGroup` — container: required `label`, optional `style.title` /
    `style.icon`, nested `visuals[]`.
  - `visualSymlink` — renders a document field: `fieldName` + optional `style`
    (`readOnlyVersion`, `renderAs`, …). The field must exist in the parent
    document's `fields`.
  - `reverseLookup` — related records section: `field` (lookup on the related
    document), `document`, `list`.
- `parent`: optional view inheritance.

## Example fragment

```json
{
  "type": "visualGroup",
  "label": { "en": "Information", "pt_BR": "Informações" },
  "style": { "icon": "info-sign", "title": { "en": "Information", "pt_BR": "Informações" } },
  "visuals": [
    { "type": "visualSymlink", "style": { "readOnlyVersion": true }, "fieldName": "code" },
    { "type": "visualSymlink", "fieldName": "subject" }
  ]
}
```
