# Meta Remove — deleting metadata with `meta_delete`

Removing a metadata module means deleting **all** `MetaObjects` rows of that module:
the primary `document`/`composite` meta, every child meta
(`list`/`view`/`pivot`/`card`/`access`), and the hooks on the document.

The admin MCP exposes exactly one deletion tool: **`meta_delete`**.

## `meta_delete` — two-step by design

Input: `id` (the meta `_id`, e.g. `Contact` or `Contact:list:Default`), optional
`confirm`.

1. **Dry-run (no `confirm`)** — deletes nothing. Returns the object summary and its
   **blast radius**: how many data records the module's collection holds, which
   lookup fields in other documents point at it, and which related metas
   (list/view/pivot/access) belong to it. Always run this first and show the result
   to the user.
2. **`confirm: true`** — executes. The object is moved to **`MetaObjects.Trash`**
   (stamped with who deleted it and when — recoverable by ops), never hard-deleted.

Hard rules:

- Only call with `confirm: true` after **explicit user confirmation** of the
  dry-run output. One object per call.
- The **Namespace** object is undeletable — the tool refuses, don't retry.
- Never improvise REST calls or raw database operations for deletion; `meta_delete`
  is the only sanctioned path.

## Full-module removal — order matters

Delete **children → hooks → primary**:

1. Inventory the module: `_id === "<Document>"` plus every `_id` matching
   `"<Document>:"` (list, view, pivot, card, access); `meta_read` on the document
   shows its hooks (`scriptBeforeValidation`, `validationScript`, `scriptAfterSave`,
   `validationData`).
2. `meta_delete` each **child meta** (list → view → pivot → card → access), dry-run
   then confirm, one at a time.
3. Remove **hooks** from the primary document via `meta_document_upsert` (hooks live
   inside the document meta) while it still exists.
4. `meta_delete` the **primary meta** last — its dry-run shows the record count and
   inbound lookups; surface both to the user before confirming. Deleting the primary
   while children exist leaves orphan metas behind (the dry-run lists them).

## Aftercare

- Run `meta_doctor_run` ([doctor.md](doctor.md)) to surface dangling references.
- Check other modules for lookups/filters/`inheritedFields` pointing at the removed
  document and fix them via the regular upsert flows.
- Deleting metadata does **not** delete the module's data collection; what to do
  with existing records is a separate, explicit decision for the admin.
- Recovery: the deleted meta objects sit in `MetaObjects.Trash` with their original
  content under `_originalId` — restoring is an ops task (re-upsert from trash), not
  an MCP tool.
