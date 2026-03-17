# 2026-03-16 — konecty-create skill

## Summary

Added the `konecty-create` skill: creates records in any Konecty module via `POST /rest/data/:document`, with full documentation of the pre-creation workflow (field discovery, lookup resolution, picklist validation, required field handling).

## Motivation

Agents need to create records in Konecty without re-discovering the API contract each time. Common tasks — creating messages, contacts, activities, opportunities — require knowing field types, valid picklist keys, and how to resolve lookup `_id`s before submitting. This skill encodes that workflow.

## What Changed

New skill added: `skills/konecty-create/`

| File | Description |
|------|-------------|
| `SKILL.md` | Entry point — 4-step workflow, quick examples, field type summary, key rules |
| `scripts/create.py` | CLI with `create` (POST record) and `lookup` (resolve _id by code or text) subcommands. Stdlib only. |
| `references/field-types.md` | Full type→payload table, picklist rules, lookup rules, required field strategy, common error messages |

## Technical Impact

- Endpoint: `POST /rest/data/:document` (body: flat JSON, response: `{ success, data: [record] }`)
- `lookup` subcommand uses `POST /rest/query/json` for consistent resolution
- Same credential loading as all other Konecty skills
- No pip dependencies — stdlib only

## How to Validate

```bash
# Validate skill structure
python3 agents/skills/skill-creator/scripts/quick_validate.py skills/konecty-create

# Resolve a lookup _id
python3 skills/konecty-create/scripts/create.py lookup Contact 16503

# Create a message (requires active session)
python3 skills/konecty-create/scripts/create.py create Message --data '{"subject":"Test","body":"<p>Hello</p>","status":"Nova","type":"Email","contact":{"_id":"JeSqMH6mkP5f233Rp"}}'
```

## Affected Files

- `skills/konecty-create/SKILL.md` (new)
- `skills/konecty-create/scripts/create.py` (new)
- `skills/konecty-create/references/field-types.md` (new)
- `docs/changelog/README.md` (updated)

## Migration

None required.
