# Field Discovery — modules, fields, and valid filter values

Discover which modules exist, their fields/types, and the valid values to filter or
write with — all through the `konecty` MCP server.

## Discovery sequence

```
modules_list → modules_fields → field_picklist_options / field_lookup_search → filter_build
```

### 1. `modules_list`

Input: none (auth via header). Output: `modules`, `usageHint`, `queryStrategyHint`,
`moduleIdentifiers`.

Use it to resolve the user's term ("contatos", "oportunidades") to the technical
`document` identifier (`Contact`, `Opportunity`). **Never use a module label/display
name as the document identifier — always the technical `document`.** If the user's
term is ambiguous, list the closest candidates and ask.

### 2. `modules_fields`

Input: `document`. Output: `module` (including document normalization info when
applicable) and `controlFields` (system field metadata with type, filterPath, and
validOperators).

For each field note: **name** (payload/filter key), **type** (determines value
format and valid operators), and for special types:

- **picklist** fields have embedded options → confirm keys with `field_picklist_options`.
- **lookup** fields point at a related module → resolve `_id`s with `field_lookup_search`.

### 3a. `field_picklist_options`

Input: `document`, `fieldName`. Output: `document`, `fieldName`, `fieldLabel`,
`options` (array of `{ key, sort?, pt_BR?, en? }`).

Returns the **valid option keys** for a picklist. Use before filtering or writing —
keys are case-sensitive and must match exactly (labels shown to the user may differ
from the stored key).

### 3b. `field_lookup_search`

Input: `document`, `fieldName`, `search`, optional `limit`. Output: `document`,
`fieldName`, `relatedDocument`, `descriptionFields`, `records`, `total`.

Searches related records to resolve a lookup `_id` before filtering
(`term: "contact._id"`) or writing (`{ "_id": "..." }`).

### 4. `filter_build`

Feed what you learned into `filter_build` — pass each condition's `fieldType` from
`modules_fields` so operator compatibility is validated. See
[find.md](find.md) for the full filter format.

## Control / system fields

Every module has system-managed control fields (prefixed `_`), present in all records
and usable in filters and sorts. `modules_fields` returns this metadata in
`controlFields`.

| Field | Type | Filter path | Valid operators | Value format |
|-------|------|-------------|-----------------|--------------|
| `_id` | ObjectId | `_id` | equals, not_equals, in, not_in, exists | String |
| `_createdAt` | dateTime | `_createdAt` | equals, not_equals, greater_than, less_than, greater_or_equals, less_or_equals, between, exists | ISO 8601 (`"2026-03-18T00:00:00Z"`) |
| `_updatedAt` | dateTime | `_updatedAt` | (same as `_createdAt`) | ISO 8601 |
| `_user` | lookup (User[]) | `_user._id` | equals, not_equals, in, not_in, exists | User `_id` string. Also supports `current_user` operator (no value) |
| `_createdBy` | lookup (User) | `_createdBy._id` | equals, not_equals, in, not_in, exists | User `_id` string |
| `_updatedBy` | lookup (User) | `_updatedBy._id` | equals, not_equals, in, not_in, exists | User `_id` string |

**Dates**: date/dateTime values MUST always be ISO 8601 with timezone
(`"2026-01-01T00:00:00Z"`). `"2026-01-01"` or `"01/01/2026"` are not accepted.

## Operators by field type

| Field type | Operators |
|------------|-----------|
| picklist | `exists`, `equals`, `not_equals`, `in`, `not_in` |
| lookup | `exists` |
| lookup._id | `exists`, `equals`, `not_equals`, `in`, `not_in` |
| text, url, email.address | `exists`, `equals`, `not_equals`, `in`, `not_in`, `contains`, `not_contains`, `starts_with`, `end_with` |
| number, date, dateTime | `exists`, `equals`, `not_equals`, `in`, `not_in`, `greater_than`, `less_than`, `greater_or_equals`, `less_or_equals`, `between` |
| boolean | `exists`, `equals`, `not_equals` |

### Lookup filter example

```json
{ "match": "and", "conditions": [{ "term": "supplier._id", "operator": "equals", "value": "<contact_id>" }] }
```

Resolve `<contact_id>` first with `field_lookup_search`.
