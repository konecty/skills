---
name: konecty-upload
description: "Upload, list, and delete files in Konecty document fields via the file API. Use this skill whenever the user wants to attach a file to a Konecty record, upload a photo/image to a contact or product, add a PDF or document to an opportunity, send a curriculum to a candidate, manage gallery images for a development or promotion, or attach any binary file to any Konecty module field. Also triggers when the user says 'upload', 'anexar', 'enviar arquivo', 'adicionar imagem', 'attach file', or refers to file-type fields in any document. Automatically reads field constraints (accepted extensions, max size, max file count) from metadata before uploading to catch errors early. Requires an active konecty-session (KONECTY_URL and KONECTY_TOKEN in ~/.konecty/.env or ~/.konecty/credentials)."
---

# Konecty Upload

Upload, list, and delete files attached to document fields in Konecty. Every upload goes through the Konecty file API — never by directly writing to the filesystem.

## Prerequisites

- Active session from **konecty-session**: credentials in `~/.konecty/.env` or `~/.konecty/credentials`.
- The `_id` (or numeric code) of the record you want to attach the file to.
- Know which field accepts the file. Use **konecty-modules** if unsure.

## Endpoints

```
POST   /rest/file/upload/ns/access/:document/:recordId/:fieldName   — upload
DELETE /rest/file/delete/ns/access/:document/:recordId/:fieldName/:fileName — delete
GET    /rest/data/:document/find                                     — list files (via record fetch)
GET    /api/admin/meta/:document/document/:document                  — read field constraints
```

HTTP status is always `200`. Success/failure is in the `success` field.

---

## Workflow

### Step 1 — Inspect the field (recommended before uploading)

Shows accepted file types, maximum size, and max/min file count for the field:

```bash
python3 skills/konecty-upload/scripts/upload.py info <Document> <fieldName>
```

**Example output:**
```
Field: Contact.picture
  type:     file
  isList:   true (accepts multiple files)
  accepted: .jpg, .jpeg, .png
  maxSize:  2048 KB (2.0 MB)
  maxItems: unlimited
  minItems: 0
```

The `wildcard` in Konecty metadata is a regex pattern like `(jpg|jpeg|png)`. Empty wildcard means all types are accepted.

### Step 2 — Upload the file

```bash
python3 skills/konecty-upload/scripts/upload.py upload <Document> <recordId> <fieldName> <localFilePath>
```

The script validates the file against the field constraints (type, size) before sending. If validation fails, it reports clearly what's wrong before making any request.

**Example:**
```bash
python3 skills/konecty-upload/scripts/upload.py upload Contact JeSqMH6mkP5f233Rp picture /tmp/photo.jpg
```

**Successful response:**
```
Uploading: photo.jpg (245.3 KB)
  → Contact/JeSqMH6mkP5f233Rp/picture
Upload successful!
  stored name: a1b2c3d4e5.jpg  (original: photo.jpg)
  size:  245.3 KB
  kind:  image/jpeg
  key:   Contact/JeSqMH6mkP5f233Rp/picture/a1b2c3d4e5.jpg

Access URLs:
  Download:  {KONECTY_URL}/rest/file/Contact/JeSqMH6mkP5f233Rp/picture/a1b2c3d4e5.jpg
  Thumbnail: {KONECTY_URL}/rest/image/thumb/Contact/JeSqMH6mkP5f233Rp/picture/a1b2c3d4e5.jpg
  Full:      {KONECTY_URL}/rest/image/full/Contact/JeSqMH6mkP5f233Rp/picture/a1b2c3d4e5.jpg

Current files in Contact/JeSqMH6mkP5f233Rp/picture (1 file):
  1. a1b2c3d4e5.jpg  (245.3 KB, image/jpeg)
     key: Contact/JeSqMH6mkP5f233Rp/picture/a1b2c3d4e5.jpg

To delete a file, use the 'name' shown above (not the key).
```

The upload endpoint automatically associates the file to the document — **no separate update step is needed**.

> **About stored names**: Konecty computes an MD5 fingerprint of the uploaded content and stores the file with that hash as the filename. The response shows `stored name` (the internal hash-based filename) and `original` (the filename you uploaded). For delete operations, use the `name` shown in the file list — this is what Konecty uses to look up the file in the record.

### Step 3 — List files already in the field

```bash
python3 skills/konecty-upload/scripts/upload.py list <Document> <recordId> <fieldName>
```

### Step 4 — Delete a file

**Two-step safety: preview first, then explicit confirmation.**

```bash
# Step 1: Preview (safe — shows what would be deleted, no action taken)
python3 skills/konecty-upload/scripts/upload.py delete <Document> <recordId> <fieldName> <storedName>

# Step 2: Confirm deletion (ONE file at a time)
python3 skills/konecty-upload/scripts/upload.py delete <Document> <recordId> <fieldName> <storedName> --confirm
```

**Safety guards:**
- Preview mode is always safe — without `--confirm`, nothing is deleted
- Deletes **one file at a time** — requires a separate `--confirm` call per file
- Use the `name` shown in the `upload` output's file list (e.g., `a1b2c3d4e5.jpg`)

To delete multiple files, call the command once per file with `--confirm`.

---

## Field Constraints Reference

File fields in Konecty metadata carry these properties:

| Property | Type | Meaning |
|----------|------|---------|
| `type` | `"file"` | Marks the field as a file field |
| `isList` | boolean | `true` = accepts multiple files; `false` = single file |
| `wildcard` | string | Regex of allowed extensions, e.g. `(jpg\|jpeg\|png)`. Empty = all types. |
| `maxSize` | number | Max file size **in KB**. Absent = no limit (server default: 1 GB). |
| `maxItems` | number | Max number of files when `isList=true`. Absent = unlimited. |
| `minItems` | number | Min files required when `isList=true`. |

**Common wildcard patterns seen in the wild:**

| Pattern | Allowed |
|---------|---------|
| `(jpg\|jpeg\|png)` | Images |
| `(pdf)` | PDF only |
| `(pdf\|jpg\|jpeg\|png)` | Images + PDF |
| `(jpg\|jpeg\|png\|svg)` | Images + SVG |
| `(jpg\|jpeg\|png\|pdf\|txt\|doc\|docx\|csv)` | Images + office documents |
| `(jpg\|jpeg\|png\|pdf\|svg\|mp4)` | Images + PDF + video |
| *(empty)* | All types |

---

## What Happens After Upload

- The file is saved in Konecty's configured storage (filesystem, S3, or proxy).
- For images (JPEG): automatically resized if wider/taller than 3840px, compressed to ~80% quality.
- A thumbnail (200×200 px) is generated automatically for images.
- The file metadata (`key`, `name`, `size`, `kind`, `etag`) is written into the document field immediately.
- For `isList=true` fields, the new file is **appended** to the existing list.
- For `isList=false` fields, the new file **replaces** the existing one.

## File Access URLs

The `upload` command shows ready-to-use URLs. If you need to build them manually:

| Purpose | URL |
|---------|-----|
| Direct download | `{KONECTY_URL}/rest/file/{document}/{recordId}/{fieldName}/{key_basename}` |
| Image thumbnail | `{KONECTY_URL}/rest/image/thumb/{full_key}` |
| Full image | `{KONECTY_URL}/rest/image/full/{full_key}` |

`{key_basename}` = last segment of the `key` field (e.g., `abc123.jpg`). `{full_key}` = the entire `key` value (e.g., `Contact/recordId/picture/abc123.jpg`).

---

## Tips

- When you have the record's numeric code instead of `_id`, pass the code — the API accepts both.
- If the field `isList=false` and already has a file, uploading replaces it.
- If `maxItems` is reached, the server returns an error. Use `upload` (the response shows the current count) to check how many files are there.
- Use `--skip-validation` only if the meta endpoint is unavailable; otherwise let the script pre-validate to get clearer error messages.
- The `list` command requires the file field to be in the user's read access profile. If it shows "field was not returned", run an `upload` instead — the response always shows all current files in the field, regardless of access profile.
- Files are deduplicated by content: uploading the same file twice to a `isList=true` field adds only one entry.
