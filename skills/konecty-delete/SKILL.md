---
name: konecty-delete
description: "Deletes a single record in any Konecty module via DELETE /rest/data/:document. Enforces a mandatory safety workflow: preview the record first, then delete one at a time with an explicit --confirm flag. Use when the user wants to delete, remove, or erase a record in Konecty. NEVER delete multiple records in a single operation. NEVER skip the preview step. Requires an active konecty-session."
---

# Konecty Delete

Permanently remove **one** record at a time. Always preview before deleting.

## ⚠️ Irreversibility

Deletion in Konecty archives the record to a `.Trash` collection and **hard-deletes it from the main collection**. It cannot be restored via the standard API.

## Mandatory Safety Rules

1. **One record at a time** — batch deletion is not supported by this skill. Period.
2. **Preview first** — always run `preview` before `delete` to confirm the right record.
3. **Explicit `--confirm`** — the `delete` command is refused without the flag.
4. **Never invent `_updatedAt`** — the script fetches it live; a stale value is rejected server-side.

## Workflow

### Step 1 — Preview the record

```bash
python3 skills/konecty-delete/scripts/delete.py preview <Document> <code or _id>
```

Shows the full record with a warning. Prints the exact `delete` command to run next.

### Step 2 — Delete with confirmation

```bash
python3 skills/konecty-delete/scripts/delete.py delete <Document> <code or _id> --confirm
```

The script fetches the live `_updatedAt`, displays the record one final time, then executes the deletion.

---

## Examples

### Delete a test message

```bash
# Step 1: inspect
python3 skills/konecty-delete/scripts/delete.py preview Message wyLtwR3aRntZ4a2q8

# Step 2: confirm and delete
python3 skills/konecty-delete/scripts/delete.py delete Message wyLtwR3aRntZ4a2q8 --confirm
```

### Delete a contact by code

```bash
python3 skills/konecty-delete/scripts/delete.py preview Contact 16503
python3 skills/konecty-delete/scripts/delete.py delete Contact 16503 --confirm
```

---

## Server-Side Guards (Konecty enforces automatically)

| Guard | Description |
|-------|-------------|
| **Permission** | User must have `isDeletable` access on the module |
| **`_updatedAt` locking** | Must match the live record — stale value = rejection |
| **Foreign key check** | Blocks deletion if other records reference this one |
| **Scope filter** | User can only delete records within their `deleteFilter` scope |

## Common Errors and Actions

| Error | Cause | Action |
|-------|-------|--------|
| `--confirm flag is required` | Flag omitted | Add `--confirm` after reviewing `preview` |
| `There are new version for records: ...` | Record changed after fetch | Run `preview` again to get the latest version |
| `Cannot delete records ... because they are referenced by [Module]` | FK constraint | Remove or update the referencing records first |
| `You don't have permission to delete records` | No `isDeletable` access | Check user permissions or ask an admin |
| `or they don't exists` | Wrong `_id` / outside scope | Verify the record exists via `konecty-find` |

## Script Reference

See [scripts/delete.py](scripts/delete.py). Stdlib only.

```
delete.py preview <Document> <term>           # inspect — no changes
delete.py delete  <Document> <term> --confirm # irreversible deletion
```

`term` is a numeric code or exact `_id`. All subcommands accept `--host` and `--token`.
