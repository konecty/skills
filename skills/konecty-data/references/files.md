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

## `file_upload` — two-step, single-use upload URL

Input: `document`, `recordId`, `fieldName`, `fileName`. Output: `uploadUrl`,
`expiresAt`, `method`, `maxFileSize`.

File **bytes never travel through the MCP**. The tool validates permissions and
returns a **single-use upload URL** (short TTL, default 10 minutes) bound to that
exact record field and file name. Send the bytes to it with an HTTP multipart
POST — the tool response includes a ready-to-run `curl` example:

```bash
curl -X POST -F "file=@/path/to/contract.pdf" "<uploadUrl>"
```

Rules:

1. Run the upload command **immediately** — the URL expires and is invalidated on
   first use (a second POST returns HTTP 410).
2. The stored file name comes from the `fileName` you passed to the tool, not from
   the local file name in the multipart body.
3. After uploading, verify with `records_find_by_id` that the record references the
   file. Konecty stores files under a content-hash name: the upload response shows
   the **stored name** (use it for download/delete) alongside the original name.
   Images are auto-resized/compressed and get a thumbnail.
4. Hosts without an HTTP client (chat-only, no shell) **cannot upload files** —
   state the limitation instead of improvising.

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
