# Meta Access — permission profiles

Manage access profiles with `meta_access_upsert` on the `konecty-admin` MCP server.

## Tool

`meta_access_upsert` — input: `id` (`{Document}:access:{Name}`, e.g.
`Contact:access:Corretor`), `access` (the **complete** access meta). Output: `result`.

**Full-replace semantics**: a partial payload erases permissions you omit. Start
from the current definition (metadata repo or user-provided — see
[read.md](read.md)), change only what was asked, send the whole object. Permission
changes are security-sensitive — restate to the user exactly what will change before
upserting.

## MetaAccess schema

| Field              | Type                                             | Required | Description                                        |
| ------------------ | ------------------------------------------------ | -------- | -------------------------------------------------- |
| `_id`              | string                                           | yes      | `{Document}:access:{Name}`                         |
| `document`         | string                                           | yes      | Document this access applies to                    |
| `name`             | string                                           | yes      | Profile name                                       |
| `type`             | `"access"`                                       | yes      | Discriminator                                      |
| `isReadable` / `isCreatable` / `isUpdatable` / `isDeletable` | boolean | no | Document-level operation gates            |
| `fieldDefaults`    | `{ isReadable, isCreatable, isUpdatable, isDeletable }` | yes | Default permission for fields not listed in `fields` |
| `fields`           | `Record<fieldName, FieldAccess>`                 | yes      | Per-field overrides                                |
| `changeUser`       | boolean                                          | no       | Can reassign `_user` on a record                   |
| `readFilter` / `updateFilter` | KonFilter                             | no       | Auto-injected filter on all reads / updates        |
| `changeUserFilter` | KonFilter                                        | no       | Filter applied when changing record owner          |
| `replaceUser`      | boolean                                          | no       | Replace `_user` with current user on update        |
| `hideListsFromMenu` / `hidePivotsFromMenu` | string[]                | no       | Views hidden from the sidebar                      |
| `export` / `exportLarge` | `Record<format, context[]>`                | no       | Allowed export formats                             |
| `label`            | `{ en, pt_BR }`                                  | no       | Bilingual label                                    |

### FieldAccess structure

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

Each operation key can carry `allow: boolean` and/or `condition: KonCondition`
(evaluated at runtime against the record — row-level field visibility).

### readFilter / updateFilter

```json
{
  "match": "or",
  "conditions": [
    { "term": "_user._id", "value": "$user", "operator": "equals" },
    { "term": "type", "value": ["Construtora"], "operator": "in" }
  ]
}
```

Dynamic values: `$user` (current user `_id`), `$group` (user's group). The backend
merges this filter into every query for the document/user combination.

## Resolution logic (how Konecty applies profiles)

**Profile resolution** (`getAccessFor`): `user.access[documentName]` → falls back to
`user.access.defaults` → `"Default"`. `false` denies; names resolve to
`{Document}:access:{name}` then `Default:access:{name}`; first match wins; no match
denies.

**Field permission resolution** — 5 layers:

1. Start all-true.
2. `fields[fieldName].{OP}.allow` when defined.
3. Otherwise `fieldDefaults` (`isDeletable` always comes from `fieldDefaults`).
4. Document-level flags are a **hard ceiling** — `isUpdatable !== true` at document
   level forces every field non-updatable regardless of overrides.
5. Result `{ isReadable, isCreatable, isUpdatable, isDeletable }`.

Backend enforcement: unreadable fields are stripped from every read (`_id` always
preserved); `readFilter`/`updateFilter` are injected into every query.

## Real-world example

```json
{
  "_id": "Contact:access:Corretor",
  "document": "Contact",
  "name": "Corretor",
  "type": "access",
  "isCreatable": true, "isReadable": true, "isUpdatable": true, "isDeletable": false,
  "changeUser": true, "replaceUser": true,
  "fieldDefaults": { "isReadable": true, "isCreatable": true, "isUpdatable": true, "isDeletable": false },
  "fields": {
    "activeOpportunities": {
      "CREATE": { "allow": false }, "READ": { "allow": true },
      "UPDATE": { "allow": false }, "DELETE": { "allow": false }
    }
  },
  "readFilter": {
    "match": "or",
    "conditions": [
      { "term": "_user._id", "value": "$user", "operator": "equals" },
      { "term": "type", "value": ["Construtora"], "operator": "in" }
    ]
  },
  "hideListsFromMenu": ["CustomerJourney", "SavedFilter"]
}
```

Reading it: Corretor creates/reads/updates but never deletes Contacts; all fields
default open except `activeOpportunities` (read-only); sees only own contacts or
type "Construtora"; some lists hidden from the menu.
