# Konecty Meta Document

Manage document-type metadata definitions (fields, labels, events, indexes).

## Prerequisites

Requires **admin** credentials from **konecty-session**. User must have `admin: true`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/meta/:document/document/:document` | GET | Get full document meta |
| `/api/admin/meta/:document/document/:document` | PUT | Upsert document meta |

## Workflow

### 1. Show a document definition

```bash
python3 scripts/meta_document.py show Contact
```

### 2. List fields

```bash
python3 scripts/meta_document.py fields Contact
python3 scripts/meta_document.py fields Contact --format json
```

### 3. Add a field

```bash
python3 scripts/meta_document.py add-field Contact myNewField \
  --type text --label-en "My Field" --label-pt "Meu Campo" --required
```

### 4. Remove a field

```bash
python3 scripts/meta_document.py remove-field Contact myNewField
```

### 5. Update a field property

```bash
python3 scripts/meta_document.py update-field Contact status --set isRequired=true
python3 scripts/meta_document.py update-field Contact status --set 'label.en=Status Name'
```

### 6. Upsert full document

```bash
python3 scripts/meta_document.py upsert Contact --file document.json
```

### 7. List document events

```bash
python3 scripts/meta_document.py events Contact
```

## Key concepts

- `fields` is an **object-map** `{ "fieldName": { ... } }`, not an array
- Field types: text, number, boolean, date, dateTime, picklist, lookup, email, phone, address, personName, money, file, composite, filter, richText, autoNumber, etc.
- See the Field Architecture section below for full field type documentation
- See the Document Events section below for queue/webhook event configuration

## Script reference

See [scripts/meta_document.py](scripts/meta_document.py). Stdlib only.

---

# Field Architecture Reference

## Field Schema

Each document's `fields` property is an **object-map** (not an array):

```json
{
  "fields": {
    "name": { "type": "text", "name": "name", "label": { "en": "Name", "pt_BR": "Nome" }, "isRequired": true },
    "status": { "type": "picklist", "name": "status", "options": { "Ativo": {}, "Inativo": {} } }
  }
}
```

| Property           | Type                                      | Required | Description                                                |
| ------------------ | ----------------------------------------- | -------- | ---------------------------------------------------------- |
| `name`             | string                                    | yes      | Field identifier (must match the key in the `fields` map)  |
| `type`             | string                                    | yes      | Field type (see type table below)                          |
| `label`            | `Record<string, string>`                  | no       | Bilingual label `{ en: "...", pt_BR: "..." }`              |
| `isRequired`       | boolean                                   | no       | Whether the field is mandatory on create/update            |
| `isUnique`         | boolean                                   | no       | Enforces uniqueness at the database level                  |
| `isSortable`       | boolean                                   | no       | Whether lists can sort by this field                       |
| `isList`           | boolean                                   | no       | Field stores an array of values (multi-value)              |
| `ignoreHistory`    | boolean                                   | no       | Skip writing changes to the history collection             |
| `document`         | string                                    | no       | Target document name (for lookup, filter, composite types) |
| `descriptionFields`| string[]                                  | no       | Fields from the target document shown in lookup display    |
| `detailFields`     | string[]                                  | no       | Fields from target document shown in detail/expanded view  |
| `inheritedFields`  | `Array<{ fieldName, inherit }>`           | no       | Fields copied from the lookup target on save               |
| `options`          | `Record<key, { sort?, [lang]: label }>`   | no       | Picklist options (key = stored value)                      |
| `optionsSorter`    | string                                    | no       | Sort mode for picklist options                             |
| `renderAs`         | string                                    | no       | UI rendering hint                                          |
| `decimalSize`      | number                                    | no       | Decimal places for number/money fields                     |
| `minValue`         | number                                    | no       | Minimum accepted value                                     |
| `maxValue`         | number                                    | no       | Maximum accepted value                                     |
| `minSelected`      | number                                    | no       | Minimum selected options (multi-picklist)                  |
| `maxSelected`      | number                                    | no       | Maximum selected options (multi-picklist)                  |
| `size`             | number                                    | no       | Max text length hint                                       |
| `sizes`            | string[]                                  | no       | Accepted image/file sizes                                  |

## Field Types

| Type            | Stored as             | Key properties                                 | Payload format (create/update)          |
| --------------- | --------------------- | ---------------------------------------------- | --------------------------------------- |
| `text`          | string                | `size`                                         | `"value"`                               |
| `number`        | number                | `decimalSize`, `minValue`, `maxValue`          | `123` or `12.5`                         |
| `money`         | `{ currency, value }` | `decimalSize`, `minValue`, `maxValue`          | `{ "currency": "BRL", "value": 100 }`  |
| `date`          | ISODate               |                                                | `"2026-03-16T00:00:00.000Z"`           |
| `dateTime`      | ISODate               |                                                | `"2026-03-16T14:30:00.000Z"`           |
| `boolean`       | boolean               |                                                | `true` or `false`                       |
| `picklist`      | string                | `options`, `optionsSorter`                     | `"Ativo"` (must match option key)       |
| `lookup`        | `{ _id }`             | `document`, `descriptionFields`, `inheritedFields` | `{ "_id": "abc123" }`            |
| `email`         | `[{ address }]`       | `isList: true`                                 | `[{ "address": "a@b.com" }]`           |
| `phone`         | `[{ phoneNumber, ... }]` | `isList: true`                              | `[{ "phoneNumber": "51999..." }]`      |
| `address`       | `{ ... }`             |                                                | `{ "city": "POA", "state": "RS", ... }` |
| `personName`    | `{ first, last }`     |                                                | `{ "first": "João", "last": "Silva" }` |
| `filter`        | internal ref          | `document`                                     | Managed by the system                   |
| `file`          | `{ ... }`             | `sizes`                                        | Managed via upload API                  |
| `composite`     | embedded doc          | `document` (target composite meta)             | Object matching composite schema        |
| `geoloc`        | `[lng, lat]`          |                                                | `[-51.2, -30.0]`                        |
| `richText`      | string (HTML)         |                                                | `"<p>content</p>"`                      |
| `encrypted`     | string                |                                                | `"plaintext"` (encrypted at rest)       |
| `autoNumber`    | number                |                                                | Auto-generated, not set manually        |
| `json`          | any                   |                                                | Any valid JSON                          |
| `percentage`    | number                | `decimalSize`                                  | `0.75` (representing 75%)              |
| `objectId`      | string                |                                                | `"507f1f77bcf86cd799439011"`            |
| `readonly`      | any                   |                                                | Cannot be set by the user               |

## Label — Bilingual

```json
{ "en": "Status", "pt_BR": "Situação" }
```

Labels are `Record<string, string>`. The keys `en` and `pt_BR` are conventional but not enforced by the schema — the `LabelSchema` accepts any string keys.

## Options — Picklist

Options are stored as an object-map where the key is the stored value:

```json
{
  "Ativo": { "en": "Active", "pt_BR": "Ativo", "sort": 1 },
  "Inativo": { "en": "Inactive", "pt_BR": "Inativo", "sort": 2 }
}
```

When creating/updating a record, the value sent must match one of the option keys exactly.

## Lookup — Document Reference

```json
{
  "name": "contact",
  "type": "lookup",
  "document": "Contact",
  "descriptionFields": ["name", "code"],
  "detailFields": ["name", "email", "phone"],
  "inheritedFields": [
    { "fieldName": "contactName", "inherit": "name.full" },
    { "fieldName": "contactEmail", "inherit": "email.0.address" }
  ]
}
```

- `document`: name of the target document in MetaObjects
- `descriptionFields`: fields shown in the lookup dropdown/display
- `detailFields`: fields shown in the expanded detail view
- `inheritedFields`: denormalization — when the lookup is saved, values are copied from the target record into the current record

### inheritedFields resolution

`{ "fieldName": "contactName", "inherit": "name.full" }` means:
- On the current document, the field `contactName` will be filled
- With the value from the lookup target's `name.full` (dot-notation traversal)

This denormalization happens at save time and is not automatically updated if the target record changes (Konsistent handles propagation if enabled).

## How the UI Uses Fields

### useViewConfig — filtering fields by access

1. Loads `docSchema.fields` from Redux metas state
2. Calls `getFieldPermissions(access, field.name)` for each field
3. Keeps only fields where `isReadable === true`
4. Returns filtered `docSchema.fields` and `listSchema.columns`

### useFieldConfig — rendering individual fields

1. Finds the field definition in `docSchema.fields`
2. Resolves `access` via `getAccessFor` + `getFieldPermissions`
3. If `isReadable === false` → returns `null` (field not rendered)
4. Determines `isReadOnly` from multiple sources:
   - `field.type === "readonly"`
   - `field.readonly === true`
   - Form view style `readOnlyVersion === true`
   - `FieldType.input === InputType.ReadOnly`
   - `isUpdatable === false && isCreatable === false`
5. For lookup fields: checks if user has read access to the **target document** — if not, lookup becomes read-only even if the field itself is editable
6. Resolves `options` for picklist fields by mapping option keys from the field definition

### Field type resolution

The UI maps `field.type` to a `FieldType` object using a registry in `components/fieldTypes`. For composite types (composite, filter), the registry entry is a function that receives the target document and view schemas to build the field type dynamically.

---

# Document Events Reference

## Overview

Documents can declare an `events` array in their meta definition. These events are evaluated by the `EventManager` after every record save. If the conditions match, the system publishes a message to a RabbitMQ queue or calls a webhook URL.

**Important:** RabbitMQ queues are NOT accessed inside hooks (`scriptAfterSave`). All queue/webhook integrations are declarative via `document.events`.

## Schema

Each event in the `events` array follows the `DocumentEventSchema`:

```json
{
  "name": "optional-human-readable-name",
  "conditions": {
    "all": [
      { "fact": "operation", "operator": "equal", "value": "update" },
      { "fact": "metaName", "operator": "equal", "value": "Product" }
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

### Event types

**Queue event:**

| Field          | Type                 | Required | Description                                       |
| -------------- | -------------------- | -------- | ------------------------------------------------- |
| `type`         | `"queue"`            | yes      | Event type discriminator                          |
| `queue`        | string or string[]   | yes      | Queue name(s) to publish to                       |
| `resource`     | string               | yes      | Resource name from `Namespace.QueueConfig.resources` |
| `headers`      | Record<string, any>  | no       | Custom headers passed to the queue message        |
| `sendOriginal` | boolean              | no       | Include pre-save record in the payload            |
| `sendFull`     | boolean              | no       | Include full record in the payload                |

**Webhook event:**

| Field          | Type                 | Required | Description                                       |
| -------------- | -------------------- | -------- | ------------------------------------------------- |
| `type`         | `"webhook"`          | yes      | Event type discriminator                          |
| `url`          | string               | yes      | URL to call                                       |
| `method`       | string               | no       | HTTP method (default: `"GET"`)                    |
| `headers`      | Record<string, string> | no     | HTTP headers                                      |
| `sendOriginal` | boolean              | no       | Include pre-save record in the payload            |
| `sendFull`     | boolean              | no       | Include full record in the payload                |

### Conditions

Conditions use [json-rules-engine](https://github.com/CacheControl/json-rules-engine/blob/master/docs/rules.md) syntax.

Available facts:

| Fact        | Type   | Description                                      |
| ----------- | ------ | ------------------------------------------------ |
| `metaName`  | string | Document name (e.g. `"Product"`)                 |
| `operation` | string | `"create"`, `"update"`, or `"delete"`            |
| `data`      | object | The saved record data                            |
| `original`  | object | Pre-save record (available if `sendOriginal`)    |
| `full`      | object | Full record (available if `sendFull`)            |

Condition operators follow json-rules-engine: `equal`, `notEqual`, `in`, `notIn`, `contains`, `doesNotContain`, `lessThan`, `greaterThan`, etc.

**Examples:**

Trigger only on update:
```json
{ "all": [{ "fact": "operation", "operator": "equal", "value": "update" }] }
```

Trigger when status changes to "Ativo":
```json
{
  "all": [
    { "fact": "operation", "operator": "equal", "value": "update" },
    { "fact": "data", "path": "$.status", "operator": "equal", "value": "Ativo" }
  ]
}
```

## How EventManager processes events

1. After a record save, `EventManager.sendEvent(metaName, operation, { data, original, full })` is called
2. All document events are pre-loaded into a `json-rules-engine` instance at startup (and on metadata reload)
3. The engine evaluates all conditions against the facts
4. For each matching event:
   - **Queue:** `queueManager.sendMessage(resource, queueName, eventData, params)` — publishes to the RabbitMQ queue defined in `Namespace.QueueConfig.resources`
   - **Webhook:** `fetch(url, { method, headers, body: JSON.stringify(eventData) })`

## Relationship with Namespace.QueueConfig

The `resource` field in a queue event references a key in `Namespace.QueueConfig.resources`:

```
event.params.resource = "rabbitmq_default"
                          ↓
Namespace.QueueConfig.resources["rabbitmq_default"] = {
  type: "rabbitmq",
  url: "amqp://...",
  queues: [{ name: "acme-sync-postgres" }, ...]
}
```

The queue name in the event must exist in the resource's `queues` array. The `QueueManager` creates the queues on startup based on this configuration.

## Payload sent to queue/webhook

```json
{
  "metaName": "Product",
  "operation": "update",
  "data": { ... saved record ... },
  "original": { ... pre-save record (if sendOriginal) ... },
  "full": { ... full record (if sendFull) ... }
}
```

## In the filesystem repo

Events are part of the `document.json` file:

```json
{
  "_id": "Product",
  "type": "document",
  "fields": { ... },
  "events": [
    {
      "name": "sync-postgres",
      "conditions": { "all": [{ "fact": "operation", "operator": "in", "value": ["create", "update"] }] },
      "event": { "type": "queue", "resource": "rabbitmq_default", "queue": "acme-sync-postgres", "sendOriginal": true }
    }
  ]
}
```
