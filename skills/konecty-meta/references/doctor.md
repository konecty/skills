# Meta Doctor — metadata integrity

Validate metadata health with `meta_doctor_run` on the `konecty-admin` MCP server.

## Tool

`meta_doctor_run` — input: none. Output: `issues` (array of `{ id, message }`),
`total` (number of metadata documents checked).

## When to run

- After any metadata change (document/list/view/access/pivot upsert, hook change,
  sync apply) — offer it proactively.
- When the user reports odd behavior that smells like broken metadata (fields not
  rendering, events not firing, lookup errors).
- Before/after a module teardown ([remove.md](remove.md)).

## Handling the report

- **No issues**: report "integrity check passed, N metas checked".
- **Issues found**: list them and, for each, fix through the corresponding tool —
  document/field problems via `meta_document_upsert`
  ([document.md](document.md)), child metas via their upserts, dangling queue
  references via the Namespace ([namespace.md](namespace.md)). Re-run
  `meta_doctor_run` after fixing to confirm.

Integrity concerns the doctor covers include invalid/missing meta ids, missing
`type`/`name` discriminators, and cross-reference consistency of the metadata set.
