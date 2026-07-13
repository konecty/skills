# Meta Document — schemas and fields

Manage document-type metadata (fields, labels, events, indexes) with `meta_read` +
`meta_document_upsert` on the `konecty-admin` MCP server.

## Read-before-write (mandatory)

`meta_document_upsert` **replaces the entire document meta**. Editing always means:

1. `meta_read` with `name` = document name → full current meta.
2. Modify the object in memory (add/remove/change a field, event, index…). Keep the
   `fields` **object-map** shape (`{ "fieldName": {...} }`, NOT an array) and keep
   `name` matching each field's key.
3. `meta_document_upsert` with `id` = the document `_id` (e.g. `Contact`) and
   `document` = the **complete** modified meta.
4. `meta_read` again to verify, and offer `meta_doctor_run`.

Common edits:

- **Add a field**: insert a new entry in `fields` with at least `name`, `type`,
  `label` (`{ en, pt_BR }`).
- **Remove a field**: delete its entry from `fields` (confirm with the user — data
  in existing records is not migrated).
- **Change a property**: e.g. `fields.status.isRequired = true` or
  `fields.status.label.en = "Status Name"`.
- **Hooks on the document**: don't edit hook code through a raw document upsert —
  follow [hook.md](hook.md) (`meta_hook_validate` → `meta_hook_upsert`).

---

# Field Architecture Reference

## Field schema

| Property           | Type                                      | Required | Description                                                |
| ------------------ | ----------------------------------------- | -------- | ---------------------------------------------------------- |
| `name`             | string                                    | yes      | Field identifier (must match the key in the `fields` map)  |
| `type`             | string                                    | yes      | Field type (see table below)                               |
| `label`            | `Record<string, string>`                  | no       | Bilingual label `{ en, pt_BR }`                            |
| `isRequired`       | boolean                                   | no       | Mandatory on create/update                                 |
| `isUnique`         | boolean                                   | no       | Uniqueness at database level                               |
| `isSortable`       | boolean                                   | no       | Lists can sort by this field                               |
| `isList`           | boolean                                   | no       | Multi-value field (array)                                  |
| `ignoreHistory`    | boolean                                   | no       | Skip history collection writes                             |
| `document`         | string                                    | no       | Target document (lookup, filter, composite types)          |
| `descriptionFields`| string[]                                  | no       | Target fields shown in lookup display                      |
| `detailFields`     | string[]                                  | no       | Target fields shown in detail view                         |
| `inheritedFields`  | `Array<{ fieldName, inherit }>`           | no       | Fields copied from the lookup target on save               |
| `options`          | `Record<key, { sort?, [lang]: label }>`   | no       | Picklist options (key = stored value)                      |
| `decimalSize` / `minValue` / `maxValue` | number              | no       | Numeric constraints                                        |
| `minSelected` / `maxSelected` | number                        | no       | Multi-picklist selection bounds                            |
| `size` / `sizes`   | number / string[]                         | no       | Text length hint / accepted file sizes                     |
| `renderAs`         | string                                    | no       | UI rendering hint                                          |

## Field types

| Type            | Stored as             | Key properties                                 |
| --------------- | --------------------- | ---------------------------------------------- |
| `text`          | string                | `size`                                         |
| `number`        | number                | `decimalSize`, `minValue`, `maxValue`          |
| `money`         | `{ currency, value }` | `decimalSize`                                  |
| `date` / `dateTime` | ISODate           |                                                |
| `boolean`       | boolean               |                                                |
| `picklist`      | string (or array)     | `options`, `optionsSorter`, `maxSelected`      |
| `lookup`        | `{ _id, … }`          | `document`, `descriptionFields`, `inheritedFields` |
| `email`         | `[{ address }]`       | usually `isList: true`                         |
| `phone`         | `[{ phoneNumber, … }]`| usually `isList: true`                         |
| `address`       | object                |                                                |
| `personName`    | `{ first, last, full }` |                                              |
| `filter`        | internal ref          | `document`                                     |
| `file`          | object                | `sizes`, `wildcard`, `maxSize`                 |
| `composite`     | embedded doc          | `document` (target composite meta)             |
| `geoloc`        | `[lng, lat]`          |                                                |
| `richText`      | string (HTML)         |                                                |
| `encrypted`     | string                | encrypted at rest                              |
| `autoNumber`    | number                | auto-generated                                 |
| `json`          | any                   |                                                |
| `percentage`    | number                | `decimalSize`                                  |
| `objectId`      | string                |                                                |
| `readonly`      | any                   | not settable by users                          |

## Picklist options

Object-map where the key is the stored value:

```json
{
  "Ativo": { "en": "Active", "pt_BR": "Ativo", "sort": 1 },
  "Inativo": { "en": "Inactive", "pt_BR": "Inativo", "sort": 2 }
}
```

Record values must match option keys exactly (case-sensitive).

## Lookup fields

```json
{
  "name": "contact",
  "type": "lookup",
  "document": "Contact",
  "descriptionFields": ["name", "code"],
  "inheritedFields": [
    { "fieldName": "contactName", "inherit": "name.full" }
  ]
}
```

`inheritedFields` denormalize: on save, the value at the target's `inherit` path is
copied into this document's `fieldName`. Propagation on target change is handled by
Konsistent (when enabled), not automatically.

---

# Document Events Reference

Documents can declare an `events` array. After every record save, the EventManager
evaluates conditions and publishes to a RabbitMQ queue or calls a webhook.
**RabbitMQ is never accessed from hooks** — queue/webhook integrations are
declarative via `document.events`.

```json
{
  "name": "sync-postgres",
  "conditions": {
    "all": [
      { "fact": "operation", "operator": "equal", "value": "update" },
      { "fact": "data", "path": "$.status", "operator": "equal", "value": "Ativo" }
    ]
  },
  "event": {
    "type": "queue",
    "resource": "rabbitmq_default",
    "queue": "acme-sync-postgres",
    "sendOriginal": true,
    "sendFull": false
  }
}
```

- **Queue event**: `type: "queue"`, `queue` (name or array), `resource` (key in
  `Namespace.QueueConfig.resources` — the queue name must exist in that resource's
  `queues`), optional `headers`, `sendOriginal`, `sendFull`.
- **Webhook event**: `type: "webhook"`, `url`, optional `method` (default GET),
  `headers`, `sendOriginal`, `sendFull`.
- **Conditions** use json-rules-engine syntax. Facts: `metaName`, `operation`
  (`create`/`update`/`delete`), `data`, `original`, `full`.
- Payload delivered: `{ metaName, operation, data, original?, full? }`.

When adding a queue event, verify the resource/queue exist in the Namespace config
([namespace.md](namespace.md)) — `meta_doctor_run` flags dangling references.
