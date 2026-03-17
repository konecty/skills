# MetaAccess — Architecture Reference

## MetaAccess Schema

Every access profile is a `MetaObjects` document with `type: "access"`.

`_id` pattern: `{Document}:access:{Name}` (e.g. `Contact:access:Corretor`)

| Field              | Type                                             | Required | Description                                        |
| ------------------ | ------------------------------------------------ | -------- | -------------------------------------------------- |
| `_id`              | string                                           | yes      | `{Document}:access:{Name}`                         |
| `document`         | string                                           | yes      | Document this access applies to                    |
| `name`             | string                                           | yes      | Human-readable profile name                        |
| `type`             | `"access"`                                       | yes      | Discriminator                                      |
| `isReadable`       | boolean                                          | no       | Document-level: can read records at all?           |
| `isCreatable`      | boolean                                          | no       | Document-level: can create records?                |
| `isUpdatable`      | boolean                                          | no       | Document-level: can update records?                |
| `isDeletable`      | boolean                                          | no       | Document-level: can delete records?                |
| `fieldDefaults`    | `{ isReadable, isCreatable, isUpdatable, isDeletable }` | yes | Default permission for all fields not listed in `fields` |
| `fields`           | `Record<fieldName, FieldAccess>`                 | yes      | Per-field overrides (see below)                    |
| `changeUser`       | boolean                                          | no       | Can this profile reassign `_user` on a record?     |
| `readFilter`       | KonFilter with optional `allow`                  | no       | Auto-injected filter on all reads                  |
| `updateFilter`     | KonFilter with optional `allow`                  | no       | Auto-injected filter on all updates                |
| `changeUserFilter` | KonFilter                                        | no       | Filter applied when changing record owner           |
| `replaceUser`      | boolean                                          | no       | Replace `_user` with current user on update        |
| `hideListsFromMenu`  | string[]                                       | no       | List names hidden from sidebar menu                |
| `hidePivotsFromMenu` | string[]                                       | no       | Pivot names hidden from sidebar menu               |
| `menuSorter`       | number or Record<string, number>                 | no       | Override sidebar sort order                        |
| `export`           | `Record<format, context[]>`                      | no       | Allowed export formats (e.g. `{ html: ["view","list"] }`) |
| `exportLarge`      | `Record<format, context[]>`                      | no       | Allowed large export formats                       |
| `namespace`        | string[]                                         | no       | Namespace(s) this profile belongs to               |
| `label`            | `{ en, pt_BR }`                                  | no       | Bilingual label                                    |

### FieldAccess structure

Each entry in `fields` is a map of operation to permission:

```json
{
  "activeOpportunities": {
    "CREATE": { "allow": false },
    "READ":   { "allow": true },
    "UPDATE": { "allow": false },
    "DELETE": { "allow": false }
  }
}
```

Each operation key (`CREATE`, `READ`, `UPDATE`, `DELETE`) can have:
- `allow: boolean` — explicit grant/deny
- `condition: KonCondition` — conditional permission evaluated at runtime against the record

### KonFilter in readFilter / updateFilter

```json
{
  "match": "or",
  "conditions": [
    { "term": "_user._id", "value": "$user", "operator": "equals" },
    { "term": "type", "value": ["Construtora"], "operator": "in" }
  ]
}
```

Dynamic values: `$user` (current user `_id`), `$group` (current user group).

## Access Resolution — Step by Step

The function `getAccessFor(documentName, user)` resolves which access profile applies:

```
1. user.access is null?
   → set user.access = { defaults: "Default" }

2. user.access.defaults is null?
   → set user.access.defaults = "Default"

3. user.access[documentName] is null?
   → set it to user.access.defaults

4. accessName = user.access[documentName]
   → if false:  DENY (return false)
   → if true:   use user.access.defaults

5. accessName is string or string[]:
   → normalize to array
   → for each name: try MetaObject.Access["{Document}:access:{name}"]
   → if not found: try MetaObject.Access["Default:access:{name}"]
   → first match wins → return MetaAccess
   → no match: DENY (return false)
```

## Field Permission Resolution — 5 Layers

The function `getFieldPermissions(metaAccess, fieldName)` resolves per-field permissions:

```
1. Start with all permissions = true

2. Check fields[fieldName].{OP}.allow
   → if defined: use it
   → if not defined: fall through to step 3

3. Use fieldDefaults.{isUpdatable|isCreatable|isReadable}
   (isDeletable always comes from fieldDefaults, never per-field)

4. Apply document-level override:
   → if metaAccess.isUpdatable !== true → isUpdatable = false
   → if metaAccess.isCreatable !== true → isCreatable = false
   → if metaAccess.isDeletable !== true → isDeletable = false
   → if metaAccess.isReadable  !== true → isReadable  = false

5. Result: { isUpdatable, isCreatable, isDeletable, isReadable }
```

Document-level flags (layer 4) act as a hard ceiling — if `isUpdatable` is `false` at the document level, no field can be updatable regardless of `fieldDefaults` or per-field overrides.

## Conditional Field Access

When `fields[fieldName].{OP}.condition` is defined, the condition is evaluated against the current record at runtime using `filterConditionToFn`. If the condition evaluates to `false`, the field is treated as not having that permission for the current record.

This enables row-level field visibility: a field may be readable in general but hidden for specific records based on their data.

## Backend Enforcement

### removeUnauthorizedDataForRead

Called before returning data to the client. For each field in the result:
1. Get `getFieldPermissions` → if `isReadable !== true` → strip field
2. Get `getFieldConditions` → if `READ` condition exists → evaluate against the record → strip if `false`

Only `_id` is always preserved.

### readFilter / updateFilter injection

When `metaAccess.readFilter` is defined, the backend merges it into every MongoDB query for that document/user combination. The user can only see records matching the filter. Same logic for `updateFilter` on write operations.

### checkMetaOperation

Separate from data access. Controls who can create/update/delete **metadata** (not data records). Uses `user.access.meta` (not `user.access[document]`). The new admin-only API endpoints bypass this entirely by checking `user.admin === true`.

## UI Consumption

### useViewConfig (list/form rendering)

1. Loads `docSchema`, `listSchema`, `formSchema`, `cardSchema` from Redux `metas` state
2. Calls `getAccessFor(document, userData, metas)` to resolve the user's access profile
3. Filters `docSchema.fields` to keep only fields where `getFieldPermissions → isReadable === true`
4. Filters `listSchema.columns` to keep only columns where `getFieldPermissions(column.linkField) → isReadable === true`
5. Returns schemas with only readable fields/columns

### useFieldConfig (individual field rendering)

1. Calls `getAccessFor` then `getFieldPermissions` for the field
2. If `isReadable === false` → returns `null` (field not rendered at all)
3. Determines `isReadOnly`:
   - `field.type === "readonly"` or `field.readonly === true`
   - `style.readOnlyVersion === true` (from form view visual)
   - `fieldType.input === InputType.ReadOnly`
   - `isUpdatable === false && isCreatable === false`
4. Special case for lookup fields: if field is readable and editable, checks if the user has read access to the **target document** — if not, lookup becomes read-only

## Real-World Example

`Contact:access:Corretor` (foxter-metas):

```json
{
  "_id": "Contact:access:Corretor",
  "document": "Contact",
  "name": "Corretor",
  "type": "access",
  "isCreatable": true,
  "isDeletable": false,
  "isReadable": true,
  "isUpdatable": true,
  "changeUser": true,
  "replaceUser": true,
  "fieldDefaults": {
    "isUpdatable": true,
    "isReadable": true,
    "isDeletable": false,
    "isCreatable": true
  },
  "fields": {
    "activeOpportunities": {
      "CREATE": { "allow": false },
      "READ": { "allow": true },
      "UPDATE": { "allow": false },
      "DELETE": { "allow": false }
    }
  },
  "readFilter": {
    "match": "or",
    "conditions": [
      { "term": "_user._id", "value": "$user", "operator": "equals" },
      { "term": "type", "value": ["Construtora"], "operator": "in" }
    ]
  },
  "changeUserFilter": {
    "match": "or",
    "conditions": [
      { "term": "_user._id", "value": "$user", "operator": "equals" }
    ]
  },
  "export": { "html": ["view","list","pivot"], "pdf": ["view","list","pivot"] },
  "hideListsFromMenu": ["CustomerJourney", "SavedFilter"],
  "hidePivotsFromMenu": ["Default", "CustomerJourney", "SavedFilter"]
}
```

Reading this profile:
- Corretor can create, read, and update Contact records, but not delete
- All fields are readable and updatable by default (`fieldDefaults`)
- `activeOpportunities` is explicitly read-only (CREATE/UPDATE/DELETE denied)
- `readFilter` restricts visibility: Corretor sees only their own contacts (`_user._id = $user`) OR contacts of type "Construtora"
- `changeUser` + `changeUserFilter`: can reassign ownership only on their own contacts
- Some lists and pivots are hidden from the sidebar menu
