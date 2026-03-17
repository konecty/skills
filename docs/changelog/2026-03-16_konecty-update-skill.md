# 2026-03-16 — konecty-update skill

## Summary

Added the `konecty-update` skill: updates records in any Konecty module via `PUT /rest/data/:document`, enforcing the mandatory fetch-first workflow to obtain `_updatedAt` before every update.

## Motivation

Konecty's update API requires `_updatedAt` in the `ids` array as a structural guard against stale writes. Without knowing this, agents invent or omit the field and get rejected. The skill encodes the correct workflow and provides a `patch` shortcut that fetches the record automatically before updating.

## What Changed

New skill: `skills/konecty-update/`

| File | Description |
|------|-------------|
| `SKILL.md` | Entry point — mandatory `_updatedAt` explanation, 2 workflow options (patch vs fetch+update), quick examples, error table |
| `scripts/update.py` | CLI with `fetch` (get `_id`+`_updatedAt`), `update` (explicit PUT), `patch` (fetch + update in one step). Stdlib only. |

## Technical Impact

- Endpoint: `PUT /rest/data/:document` — body: `{ ids: [{_id, _updatedAt}], data: {fields} }`
- Partial updates: only changed fields sent; `null` = `$unset`
- Batch updates: `ids` array supports multiple records
- `_updatedAt` normalized to `{ "$date": "..." }` format automatically by the script
- Same credential loading as all other Konecty skills

## How to Validate

```bash
python3 agents/skills/skill-creator/scripts/quick_validate.py skills/konecty-update

# fetch a record
python3 skills/konecty-update/scripts/update.py fetch Contact 16503

# patch (fetch + update)
python3 skills/konecty-update/scripts/update.py patch Message <_id> --data '{"status":"Enviada"}'
```

## Affected Files

- `skills/konecty-update/SKILL.md` (new)
- `skills/konecty-update/scripts/update.py` (new)
- `docs/changelog/README.md` (updated)

## Migration

None required.
