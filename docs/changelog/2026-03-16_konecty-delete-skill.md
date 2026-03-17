# 2026-03-16 — konecty-delete skill

## Summary

Added the `konecty-delete` skill: deletes one record at a time in any Konecty module via `DELETE /rest/data/:document`, with multiple safety layers to prevent accidental or inappropriate deletions.

## Motivation

Deletion is irreversible from the API's perspective. A skill without guardrails risks accidental data loss. The skill enforces a strict workflow: preview first, confirm explicitly, one record only.

## What Changed

New skill: `skills/konecty-delete/`

| File | Description |
|------|-------------|
| `SKILL.md` | Entry point — safety rules, mandatory workflow, error table |
| `scripts/delete.py` | CLI with `preview` (inspect only) and `delete` (requires `--confirm`). Stdlib only. |

## Safety Layers

Script-enforced (3):
1. One record at a time — batch deletion intentionally unsupported
2. `preview` subcommand shows the full record before any action
3. `delete` subcommand requires explicit `--confirm` flag; refused without it

Server-enforced by Konecty (5):
1. `isDeletable` permission check
2. `_updatedAt` optimistic locking (real-time — unlike update, not commented out)
3. Foreign key check (blocks if referenced by another module)
4. Scope filter (`deleteFilter` on access config)
5. Record existence check

## How to Validate

```bash
python3 agents/skills/skill-creator/scripts/quick_validate.py skills/konecty-delete

# Guardrail: must be refused
python3 skills/konecty-delete/scripts/delete.py delete Message <id>

# Preview (safe)
python3 skills/konecty-delete/scripts/delete.py preview Message <id>
```

## Affected Files

- `skills/konecty-delete/SKILL.md` (new)
- `skills/konecty-delete/scripts/delete.py` (new)
- `docs/changelog/README.md` (updated)

## Migration

None required.
