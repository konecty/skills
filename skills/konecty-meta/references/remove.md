# Meta Remove — full-module deletion (MCP gap)

Removing a metadata module means deleting **all** `MetaObjects` rows of that module:
the primary `document`/`composite` meta, every child meta
(`list`/`view`/`pivot`/`card`/`access`), and the hooks on the document.

## ⚠️ The admin MCP has NO deletion tool

The `konecty-admin` MCP server exposes read/upsert/validate/sync tools only — there
is **no `meta_*_delete` tool**. This is a known gap; exposing a safe module-deletion
tool upstream in Konecty is a deferred feature request.

**Hard rule for the agent:** do NOT work around the gap. Never improvise REST calls,
raw database operations, or any other executable path to delete metadata. Upserting
an "emptied" meta object is also not deletion — don't do that either. When asked to
remove a module, explain the gap and hand the user the safe manual procedure below.

## Safe manual path (performed by a human Konecty administrator)

The deletion itself is done by a human admin using Konecty's own administrative
tooling (outside this skill). What this skill contributes is the **correct order and
checks** — share them with the admin:

### 1. Inventory the module first

Enumerate every meta belonging to the module: `_id === "<Document>"` plus every
`_id` matching `"<Document>:"` (list, view, pivot, card, access), and the hooks
present on the document meta (`meta_read` on the document shows
`scriptBeforeValidation`, `validationScript`, `scriptAfterSave`, `validationData`).

### 2. Delete in this order — children → hooks → primary

1. **Child metas**: `list` → `view` → `pivot` → `card` → `access`.
2. **Hooks** on the primary document (while the document row still exists).
3. **Primary meta** (`document` or `composite`) — last, and only after confirming
   no child metas remain. Deleting the primary while children exist leaves orphan
   metas behind.

One item at a time, with explicit confirmation per step — this is irreversible.

### 3. Aftercare

- Reload metadata (Konecty picks up metadata changes on its admin reload cycle).
- Run `meta_doctor_run` ([doctor.md](doctor.md)) to surface dangling references.
- Check other modules for lookups/filters/`inheritedFields` pointing at the removed
  document and fix them via the regular upsert flows.
- Note: deleting metadata does not delete the module's **data collection**; what to
  do with existing records is a separate, explicit decision for the admin.

## What the agent CAN still do

- Produce the inventory and the ordered deletion checklist (via `meta_read` and the
  metadata repo) for the admin to execute.
- After the admin confirms the removal, run `meta_doctor_run` and help repair any
  references the doctor flags.
