# Files — upload, download, delete — user MCP

Manage files attached to record fields with `file_upload`, `file_download`, and
`file_delete`. `file_upload` and `file_delete` are **write/destructive** tools —
in read-only namespaces (`mcpUserWriteEnabled=false`) they fail with
`insufficient_scope` (see [errors.md](errors.md)).

## Before uploading

- Identify the target record (`records_find` / `records_find_by_id`) — you need its
  `_id` (`recordId`).
- Identify the **file field** with `modules_fields` (type `file`). File fields carry
  constraints in the metadata:

| Property | Meaning |
|----------|---------|
| `isList` | `true` = multiple files (new upload **appends**); `false` = single file (new upload **replaces**) |
| `wildcard` | Regex of allowed extensions, e.g. `(jpg\|jpeg\|png)`. Empty = all types |
| `maxSize` | Max file size in **KB** |
| `maxItems` / `minItems` | File count limits when `isList=true` |

If the file the user wants to send violates these constraints, say so before calling
the tool.

## `file_upload`

Input: `document`, `recordId`, `fieldName`, `file`. Output: `file`.

The upload associates the file to the record field immediately — no separate update
step. Konecty stores files under a content-hash name: the response's file metadata
shows the **stored name** (use it for download/delete) alongside the original name.
Images are auto-resized/compressed and get a thumbnail; duplicate content in a list
field is deduplicated.

## `file_download`

Input: `document`, `recordId`, `fieldName`, `fileName`. Output: `fileUrl`, `fileName`.

Give the user the returned `fileUrl`. `fileName` is the stored name from the record's
file field (check the record via `records_find_by_id` when unsure which files exist).

## `file_delete`

Input: `document`, `recordId`, `fieldName`, `fileName`, `confirm`. Output: `file`.

Safety rules (same spirit as record deletion):

1. List/confirm the exact file with the user first (record fetch shows the field's
   current files).
2. Only call with `confirm` after **explicit user confirmation**.
3. One file per call — repeat per file when the user asked for several, confirming
   each.

## Rendering (optional)

`render_file_widget` (input `fileUrl`, optional `fileName`) displays a file preview
widget. It is **host-dependent** (MCP-app resource) — use it only as a visual extra;
never make the upload/download flow depend on it.
