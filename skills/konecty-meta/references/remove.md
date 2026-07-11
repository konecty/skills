# Konecty Meta Remove

Permanently remove **metadata** (`MetaObjects` definitions) for a document module. This is **not** [`konecty-delete`](../konecty-delete/SKILL.md) (which deletes **records** in `/rest/data`).

## Prerequisites

- **Admin** session from **konecty-session** (`KONECTY_URL`, `KONECTY_TOKEN` in env or `~/.konecty/.env`).
- Konecty exposes `GET` / `DELETE` under `/api/admin/meta/*` (same stack as [`konecty-meta-sync`](../konecty-meta-sync/SKILL.md)).

## Mandatory rule: remove the whole module

Never delete only the primary `document` / `composite` row while **list**, **view**, **access**, **pivot**, **card**, or **namespace** metas (same module prefix) still exist, and never skip **hooks** on that document before removing the document meta.

1. Run **`plan`** — it lists every meta and the exact deletion queue (children → hooks → primary).
2. Run **`apply`** — walks that queue with **one confirmation per step** (TTY). Optional **`--yes`** skips prompts when the operator explicitly requests non-interactive removal (e.g. from automation); it **aborts on the first failed DELETE** and still **refuses** deleting the primary while child metas remain. Agents must **not** use `--yes` unless the human ordered that exact non-interactive run in the same conversation.
3. After successful deletes, the script calls **`POST /api/admin/meta/reload`**.

If the user refuses some steps, the script warns about **leftover metas** or **orphan document** and does not silently continue to a dangerous state without an extra explicit prompt for the primary meta.

## Agent rules

- **Never** call `DELETE` on the document meta alone if the plan still shows child metas for that module.
- **Never** bypass interactive confirmation except when the human explicitly asked for `apply --document … --yes` in the same turn; otherwise the human runs `apply` in a terminal and confirms each step.
- Run **`konecty-meta-doctor`** / manual review after removal if other modules referenced this document.

## Workflow

### 1. Plan (always first)

```bash
python3 scripts/meta_remove.py plan --document NotificationPreferences
```

Prints all metas returned by `GET /api/admin/meta/:document`, hook steps inferred from the full document payload, counts by type, and the **ordered** deletion queue.

### 2. Apply (interactive module removal)

```bash
python3 scripts/meta_remove.py apply --document NotificationPreferences
```

For each queue entry, prompts `[y/N]` unless **`--yes`** was passed. Before deleting the primary meta, the script re-checks the server and may require typing `DELETE PRIMARY ANYWAY` if children were skipped but still exist (not applicable when every child delete succeeded).

### 3. Single meta (optional, still interactive)

```bash
python3 scripts/meta_remove.py delete --meta-id "Contact:list:OldList"
```

One `DELETE` after confirmation. Use for odd one-offs **outside** a full module teardown, not as a shortcut to avoid removing related metas when retiring a module.

## Script reference

See [scripts/meta_remove.py](scripts/meta_remove.py) (stdlib only) and the Deletion Order section below.

---

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
