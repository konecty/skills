# Meta Read — inspecting metadata

Read metadata through the `konecty-admin` MCP server.

## `meta_read`

Input: `name`. Output: `meta` (full metadata object).

Reads a **document** metadata object by its name (e.g. `Contact`, `User`). The
returned meta includes the full `fields` map and any hook code stored on the
document (`scriptBeforeValidation`, `validationScript`, `scriptAfterSave`,
`validationData`).

```json
{ "name": "Contact" }
```

Use it:

- before any `meta_document_upsert` (**read-before-write** — upserts replace the
  whole object);
- to inspect field definitions, picklist options, lookup targets;
- to read hook code before editing it;
- after any upsert, to verify the persisted state.

### Reading child metas (list/view/access/pivot) and Namespace

The admin MCP currently exposes document reads only. For child metas, the current
definition comes from your **metadata repository** (the sync workflow's source of
truth — see [sync.md](sync.md)) or from the state you previously wrote. When neither
is available, ask the user for the current definition before upserting — never guess
and overwrite (upserts are full replacements).

## Meta types and `_id` conventions

All metadata lives in a single `MetaObjects` collection, discriminated by `type`.
The `_id` is what you pass as `id` to the upsert tools.

| Type | `_id` pattern | Example |
|------|--------------|---------|
| `document` | `{Name}` | `Contact` |
| `composite` | `{Name}` | `Education` |
| `list` | `{Doc}:list:{Name}` | `Contact:list:Default` |
| `view` | `{Doc}:view:{Name}` | `Contact:view:Default` |
| `access` | `{Doc}:access:{Name}` | `Contact:access:Corretor` |
| `pivot` | `{Doc}:pivot:{Name}` | `Contact:pivot:Default` |
| `card` | `{Doc}:card:{Name}` | `Opportunity:card:Default` |
| `namespace` | `Namespace` | `Namespace` (singleton) |

---

# Meta Schemas Reference

## document

`_id` pattern: `{DocumentName}` (e.g. `Contact`, `User`)

| Field                      | Type                    | Required | Description                                         |
| -------------------------- | ----------------------- | -------- | --------------------------------------------------- |
| `_id`                      | string                  | yes      | Document name                                       |
| `type`                     | `"document"`            | yes      | Discriminator                                       |
| `name`                     | string                  | yes      | Same as `_id`                                       |
| `label`                    | `{ en, pt_BR }`         | yes      | Bilingual label                                     |
| `plurals`                  | `{ en, pt_BR }`         | yes      | Bilingual plural label                              |
| `icon`                     | string                  | yes      | Icon name                                           |
| `fields`                   | `Record<name, Field>`   | yes      | Object-map of field definitions (NOT an array)       |
| `collection`               | string                  | no       | MongoDB collection name (defaults to `data.{name}`) |
| `group`                    | string                  | no       | Menu group                                          |
| `menuSorter`               | number                  | no       | Menu sort order                                     |
| `description`              | `{ en, pt_BR }`         | no       | Description text                                    |
| `help`                     | `{ en, pt_BR }`         | no       | Help text                                           |
| `access`                   | string                  | no       | Default access profile name                         |
| `relations`                | Relation[]              | no       | Related document definitions                        |
| `indexes`                  | Record<name, Index>     | no       | MongoDB indexes                                     |
| `indexText`                | Record<field, weight>   | no       | Text search index fields                            |
| `events`                   | DocumentEvent[]         | no       | Queue/webhook event declarations                    |
| `scriptBeforeValidation`   | string                  | no       | Hook JS code                                        |
| `validationScript`         | string                  | no       | Hook JS code                                        |
| `scriptAfterSave`          | string                  | no       | Hook JS code                                        |
| `validationData`           | object                  | no       | Hook JSON                                           |

### Minimal example (User)

```json
{
  "_id": "User",
  "type": "document",
  "name": "User",
  "collection": "users",
  "label": { "en": "User", "pt_BR": "Usuário" },
  "plurals": { "en": "Users", "pt_BR": "Usuários" },
  "icon": "user",
  "fields": {
    "active": {
      "type": "boolean", "name": "active",
      "label": { "en": "Active", "pt_BR": "Ativo" },
      "isRequired": true, "isSortable": true, "defaultValue": true
    },
    "code": {
      "type": "autoNumber", "name": "code",
      "label": { "en": "Code", "pt_BR": "Código" },
      "isUnique": true, "isSortable": true
    }
  }
}
```

## list

`_id` pattern: `{Document}:list:{Name}`

| Field            | Type                        | Required | Description                                        |
| ---------------- | --------------------------- | -------- | -------------------------------------------------- |
| `_id`            | string                      | yes      | `{Document}:list:{Name}`                           |
| `type`           | `"list"`                    | yes      | Discriminator                                      |
| `document`       | string                      | yes      | Parent document name                               |
| `name`           | string                      | yes      | List name                                          |
| `label` / `plurals` | `{ en, pt_BR }`          | yes      | Bilingual labels                                   |
| `columns`        | `Record<name, Column>`      | yes      | Object-map of columns (NOT an array)               |
| `sorters`        | `[{ term, direction }]`     | yes      | Default sort order                                 |
| `view`           | string                      | no       | Form view to open on click (default `"Default"`)   |
| `filter`         | KonFilter                   | no       | Default filter (conditions may be an object-map with `editable`/`style`) |
| `refreshRate`    | `{ options, default }`      | yes      | Auto-refresh options (seconds, 0=off)              |
| `rowsPerPage`    | `{ options, default }`      | yes      | Pagination options                                 |
| `loadDataAtOpen` | boolean                     | no       | Load data immediately                              |
| `calendars` / `boards` | arrays                | no       | Calendar / kanban view definitions                 |

Column structure: `{ "code": { "name": "code", "linkField": "code", "visible": true, "minWidth": 60, "sort": 0 } }` —
`linkField` maps to a field in the parent document.

## view (FormSchema)

`_id` pattern: `{Document}:view:{Name}`

| Field       | Type              | Required | Description                              |
| ----------- | ----------------- | -------- | ---------------------------------------- |
| `_id` / `type` / `document` / `name` | — | yes | As above, `type: "view"`             |
| `label` / `plurals` | `{ en, pt_BR }` | yes    | Label supports `{field}` interpolation   |
| `visuals`   | Visual[]          | no       | Recursive visual tree                    |
| `parent`    | string            | no       | Parent view for inheritance              |

Visual tree node types:

- `visualGroup`: container with `label`, optional `style.title`/`style.icon`, nested `visuals[]`
- `visualSymlink`: references a document field; `fieldName` + optional `style` (`readOnlyVersion`, `renderAs`, …)
- `reverseLookup`: shows related records; `field`, `document`, `list`

## pivot

`_id` pattern: `{Document}:pivot:{Name}`

- `rows`: array of row grouping fields (e.g. `_user.group`)
- `columns`: object-map of column fields
- `values`: array of `{ name, linkField, label, aggregator }` — aggregators: `count`, `sum`, `avg`, `min`, `max`
- `filter`, `sorters`, `rowsPerPage`, `refreshRate`: same structures as list

## access

`_id` pattern: `{Document}:access:{Name}` — full schema and resolution logic in
[access.md](access.md).

## namespace

Singleton `_id: "Namespace"`, `type: "namespace"` — full schema in
[namespace.md](namespace.md). Updated via `meta_namespace_update` (patch), not upsert.

## composite

Same schema as `document` but represents embedded sub-documents without their own
collection; referenced via `field.type: "composite"` + `field.document`.

## card

`{Document}:card:{Name}` — compact view definitions for board/kanban modes, similar
to views with a simplified layout.
