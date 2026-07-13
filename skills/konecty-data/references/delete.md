# Delete Records — user MCP

Permanently remove **one** record at a time with `records_delete_preview` →
**explicit user confirmation** → `records_delete`.

## ⚠️ Irreversibility

Deletion archives the record to a `.Trash` collection and **hard-deletes it from the
main collection**. It cannot be restored via the standard API.

## Mandatory safety rules

1. **Preview first** — always call `records_delete_preview` and show the user what
   will be deleted before anything else.
2. **Explicit user confirmation** — after the preview, ask the user to confirm the
   deletion of that specific record. Never infer confirmation from the original
   request ("delete contact X" is a request, not a confirmation of the previewed
   record).
3. **One record at a time** — no batch deletion through this skill. Period.
4. **Never invent `_updatedAt`** — deletion is optimistically locked server-side; a
   stale value is rejected.

## Flow

### Step 1 — `records_delete_preview`

Input: `document`, `recordId`, optional `fields`. Output: `preview`.

Show the previewed record to the user (key identifying fields at minimum) and ask
for confirmation.

### Step 2 — `records_delete` (only after the user confirms)

Input: `document`, `confirm`, `ids`. Output: `deleted`.

The delete tool requires the explicit `confirm` input and the record identification
in `ids` — pass exactly the record that was previewed and confirmed.

## Server-side guards (Konecty enforces automatically)

| Guard | Description |
|-------|-------------|
| Permission | User must have `isDeletable` access on the module |
| Optimistic locking | `_updatedAt` must match the live record |
| Foreign keys | Deletion is blocked if other records reference this one |
| Scope filter | User can only delete records within their `deleteFilter` scope |

## Common errors and actions

| Error | Cause | Action |
|-------|-------|--------|
| Confirmation required | `confirm` missing | Only after explicit user approval, re-call with `confirm` |
| `There are new version for records: ...` | Record changed after preview | Re-run the preview, show it again, re-confirm |
| `Cannot delete records ... referenced by [Module]` | FK constraint | Tell the user which records block it; those must be handled first |
| No permission to delete / record not found | No `isDeletable` access, wrong id, or outside scope | Verify via `records_find`; ask an admin if it's a permission issue |
| `insufficient_scope` | Namespace read-only (`mcpUserWriteEnabled=false`) | Explain read-only mode — see [errors.md](errors.md) |
