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
