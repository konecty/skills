# Konecty Filter Operators Reference

## KonFilter Structure

```json
{
  "match": "and",
  "conditions": [
    { "term": "status", "operator": "equals", "value": "active" },
    { "term": "createdAt", "operator": "greater_than", "value": "$monthsAgo:3" }
  ],
  "textSearch": "optional full-text search string",
  "filters": [
    {
      "match": "or",
      "conditions": [
        { "term": "priority", "operator": "equals", "value": "high" },
        { "term": "priority", "operator": "equals", "value": "urgent" }
      ]
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `match` | `"and"` \| `"or"` | How to combine `conditions` and nested `filters` |
| `conditions` | array or object | Array of `Condition` objects (or keyed object — both are valid) |
| `textSearch` | string | Full-text search across indexed text fields |
| `filters` | array | Nested sub-groups for complex AND/OR logic (each has `match` + `conditions`) |

### Condition

```json
{ "term": "fieldName", "operator": "equals", "value": "someValue" }
```

| Field | Description |
|-------|-------------|
| `term` | Field path. Use dot notation for sub-fields: `email.address`, `name.full`, `lookup._id`, `money.value` |
| `operator` | One of the operators listed below |
| `value` | The comparison value. Type depends on operator and field type |
| `disabled` | If `true`, condition is ignored at runtime (useful for optional filters) |

---

## All Operators

| Operator | MongoDB equivalent | Description |
|----------|--------------------|-------------|
| `equals` | `{ field: value }` | Exact match |
| `not_equals` | `$ne` | Not equal |
| `contains` | `$regex` (case-insensitive, accent-aware) | Substring match |
| `not_contains` | `$not: $regex` | Does not contain substring |
| `starts_with` | `$regex: '^...'` | String starts with value |
| `end_with` | `$regex: '...$'` | String ends with value |
| `in` | `$in` | Value is in array |
| `not_in` | `$nin` | Value is not in array |
| `greater_than` | `$gt` | Strictly greater than |
| `greater_or_equals` | `$gte` | Greater than or equal |
| `less_than` | `$lt` | Strictly less than |
| `less_or_equals` | `$lte` | Less than or equal |
| `between` | `$gte` + `$lte` | Inclusive range (see value format below) |
| `exists` | `$exists` | Field exists (value: `true`) or does not exist (value: `false`) |
| `current_user` | — | Matches documents owned by the authenticated user |
| `not_current_user` | — | Excludes documents owned by the authenticated user |
| `current_user_group` | — | Matches documents belonging to the user's primary group |
| `not_current_user_group` | — | Excludes the user's primary group |
| `current_user_groups` | — | Matches documents in any of the user's secondary groups |

### `between` value format

```json
{
  "term": "createdAt",
  "operator": "between",
  "value": {
    "greater_or_equals": "2024-01-01",
    "less_or_equals": "2024-12-31"
  }
}
```

Both bounds are inclusive. Values can be ISO date strings or dynamic variables (e.g. `$startOfMonth`, `$now`).

### `in` / `not_in` value format

```json
{ "term": "status", "operator": "in", "value": ["active", "pending"] }
```

Value must be an array.

---

## Operators by Field Type

| Field Type | Supported Operators |
|------------|---------------------|
| `text` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `url` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `email` (use `email.address`) | `exists`, `equals`, `not_equals`, `in`, `not_in`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `phone` (use `phone.phoneNumber`) | `exists`, `equals`, `not_equals`, `in`, `not_in`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `personName` (use `name.full`) | `exists`, `equals`, `not_equals`, `contains`, `not_contains`, `starts_with`, `end_with` |
| `richText` | `exists`, `contains` |
| `number` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `autoNumber` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `percentage` | `exists`, `equals`, `not_equals`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `money` (use `money.value`) | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `date` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `dateTime` | `exists`, `equals`, `not_equals`, `in`, `not_in`, `less_than`, `greater_than`, `less_or_equals`, `greater_or_equals`, `between` |
| `boolean` | `exists`, `equals`, `not_equals` |
| `picklist` | `exists`, `equals`, `not_equals`, `in`, `not_in` |
| `lookup` (use `lookup._id`) | `exists`, `equals`, `not_equals`, `in`, `not_in` |
| `ObjectId` | `exists`, `equals`, `not_equals`, `in`, `not_in` |

### Compound field path examples

| Field type | term example | Notes |
|------------|-------------|-------|
| `email` | `email.address` | Access the address sub-field |
| `phone` | `phone.phoneNumber` | Access the phone number sub-field |
| `personName` | `name.full` | Full concatenated name |
| `money` | `value.value` | The numeric part of a money field |
| `lookup` | `contact._id` | The `_id` of the related document |
| `address` | `address.city` | Sub-field access (city, state, country, etc.) |

---

## Dynamic Values

Use these strings as `value` in date/dateTime conditions instead of hard-coded dates.

| Variable | Description |
|----------|-------------|
| `$now` | Current date and time |
| `$today` | Start of today |
| `$yesterday` | Start of yesterday |
| `$startOfWeek` | Start of the current week |
| `$startOfMonth` | Start of the current month |
| `$startOfYear` | Start of the current year |
| `$endOfDay` | End of today |
| `$endOfWeek` | End of the current week |
| `$endOfMonth` | End of the current month |
| `$endOfYear` | End of the current year |
| `$hoursAgo:N` | N hours ago |
| `$hoursFromNow:N` | N hours from now |
| `$daysAgo:N` | N days ago |
| `$daysFromNow:N` | N days from now |
| `$monthsAgo:N` | N months ago |
| `$monthsFromNow:N` | N months from now |

User-context variables (resolved at runtime for the authenticated user):

| Variable | Description |
|----------|-------------|
| `$user` | Current user's `_id` |
| `$group` | Current user's primary group `_id` |
| `$groups` | Array of the user's secondary group `_ids` |
| `$allgroups` | Array of all group `_ids` (primary + secondary) |
| `$user.field` | Access a specific field from the user document (e.g. `$user.branch._id`) |

---

## Nested Filter Examples

### AND + OR combined

```json
{
  "match": "and",
  "conditions": [
    { "term": "status", "operator": "equals", "value": "active" }
  ],
  "filters": [
    {
      "match": "or",
      "conditions": [
        { "term": "priority", "operator": "equals", "value": "high" },
        { "term": "dueDate", "operator": "less_than", "value": "$today" }
      ]
    }
  ]
}
```

Means: `status == "active" AND (priority == "high" OR dueDate < today)`

### Lookup field filter

```json
{
  "match": "and",
  "conditions": [
    { "term": "contact._id", "operator": "in", "value": ["<objectId1>", "<objectId2>"] }
  ]
}
```

### Optional / disabled condition

Set `disabled: true` to include the condition in the structure (e.g. stored filters) but ignore it at query time:

```json
{ "term": "status", "operator": "equals", "value": "active", "disabled": true }
```

---

## textSearch

`textSearch` performs full-text search across all indexed text fields of the module. It is combined with `conditions` using the `match` logic.

```json
{
  "match": "and",
  "textSearch": "John Doe",
  "conditions": [
    { "term": "status", "operator": "equals", "value": "active" }
  ]
}
```
