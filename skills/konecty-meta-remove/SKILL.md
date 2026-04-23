---
name: konecty-meta-remove
description: "Removes a full Konecty metadata module from MetaObjects (lists, views, access, pivot, card, hooks on the document, then document/composite) via admin HTTP API with mandatory per-step confirmation. Use when retiring a document module from the tenant, cleaning NotificationPreferences-style metas, or ensuring no orphan list/view/access remain. Not for business records — use konecty-delete for /rest/data. Requires admin credentials."
---

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

See [scripts/meta_remove.py](scripts/meta_remove.py) (stdlib only) and [references/deletion-order.md](references/deletion-order.md).
