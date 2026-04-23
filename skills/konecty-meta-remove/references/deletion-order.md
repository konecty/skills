# Deletion order (module teardown)

A **module** is the set of `MetaObjects` rows returned by `GET /api/admin/meta/:document` for that document name (`_id === document` or `_id` matching `^document:`).

## Business rule

Removing a module means deleting **all** of those rows. Do not delete only the `document` / `composite` row while `list`, `view`, `access`, `pivot`, `card`, or `namespace` metas for the same prefix still exist.

## Execution order (script queue)

1. **Child metas** — every meta that is not the primary for this module, ordered by `type` then `_id`:
   - `list` → `view` → `pivot` → `card` → `access` → `namespace` (stable tie-break: `_id` string).
2. **Hooks on the primary document** — for each of `scriptBeforeValidation`, `validationScript`, `scriptAfterSave`, `validationData` present on the full document payload: `DELETE /api/admin/meta/:document/hook/:hookName` (document row must still exist).
3. **Primary meta** — last: `DELETE /api/admin/meta/:document/document` or `.../:document/composite`.

## Mapping `_id` → HTTP `DELETE`

| Shape | Example `_id` | `DELETE` path under `/api/admin/meta` |
|-------|-----------------|----------------------------------------|
| Primary document | `Contact` (type `document`) | `/Contact/document` |
| Primary composite | `Foo` (type `composite`) | `/Foo/composite` |
| Named meta | `Contact:list:Default` | `/Contact/list/Default` |
| Namespace row | `Namespace:namespace:Namespace` | `/Namespace/namespace/Namespace` |
| Hook (not a row) | — | `/Contact/hook/scriptBeforeValidation` |

Two-segment deletes are only valid for `document` and `composite` primaries (see Konecty `admin/meta` routes).

## Apply-time guard

Before the primary `DELETE`, the script re-fetches the module list. If any child meta is still present, the operator must type `DELETE PRIMARY ANYWAY` to proceed; otherwise the primary step is skipped to avoid orphan list/view/access metas.

## Aftercare

- `POST /api/admin/meta/reload` after any successful delete batch (script does this).
- Run **`konecty-meta-doctor`** and grep other metas for lookups/references to the removed module.
