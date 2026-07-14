# Meta Sync — repo ↔ database

Synchronize metadata between a filesystem repository and the Konecty database using
`meta_sync_plan` → `meta_sync_apply` on the `konecty-admin` MCP server.

## Repository layout (source of truth)

```
MetaObjects/
  Contact/
    document.json
    list/Default.json
    view/Default.json
    access/Default.json
    pivot/Default.json
    hook/scriptBeforeValidation.js
    hook/validationData.json
    hook/validationScript.js
    hook/scriptAfterSave.js
  Namespace/
    document.json
```

To build sync `items` from a repo: each meta becomes one object with its `_id`
(`Contact`, `Contact:list:Default`, …) and full content; hook files under `hook/`
are injected into the document meta as the corresponding fields
(`scriptBeforeValidation`, `validationData`, …). Validate hook code with
`meta_hook_validate` **before** including it in a sync ([hook.md](hook.md)).

## 1. `meta_sync_plan` — always first

Input: `items` — array of metadata objects, each with a non-empty string `_id`
(extra keys carried as-is). Output: `plan`.

The plan compares incoming items with the database and marks each as **create**
(no meta with that `_id` exists) or **update**. Show the plan to the user —
creates vs updates, and which `_id`s — and get explicit approval.

## 2. `meta_sync_apply` — only after the plan is approved

Input: `items` (the same reviewed items), `autoApprove`. Output: `applied`, `total`.

- The tool **refuses to apply** unless `autoApprove` is `true` — that flag is your
  statement that the user approved the reviewed plan. Never set it without showing
  the plan first.
- Each item **fully replaces** the stored meta with the same `_id` (upsert). Items
  must be complete definitions, never partials.

## 3. Verify

- `meta_doctor_run` after applying ([doctor.md](doctor.md)).
- Spot-check critical documents with `meta_read`.

## Safety notes

- Sync in the **repo → database** direction only when the repo is the agreed source
  of truth; warn the user that database-side edits not present in the repo will be
  overwritten for the synced `_id`s.
- For large syncs, prefer applying in reviewed batches (subset of `items`) so a bad
  definition doesn't ride in with a hundred good ones.
