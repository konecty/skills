# konecty-modules skill

**Date:** 2026-03-16

## Summary

New skill `konecty-modules` that lists Konecty modules accessible to the current session and retrieves fields, types, and labels for any given module.

## Motivation

Agents need to discover what modules exist in a Konecty instance and understand their field schemas to construct queries, forms, or integrations. Without this skill, the agent would have to re-discover the API each time.

## What changed

- `skills/konecty-modules/SKILL.md` — skill definition with API reference, usage workflow, and fuzzy-match documentation
- `skills/konecty-modules/scripts/modules.py` — Python stdlib script with subcommands: `list`, `fields <module>`, `search <keyword>`

## Technical impact

- Uses `GET /rest/query/explorer/modules?lang=<lang>` — returns only modules the authenticated user can read, with fields filtered by field-level permissions.
- Authentication via `Authorization: <KONECTY_TOKEN>` header, loaded from `~/.konecty/.env` (shared with `konecty-session`).
- Fuzzy matching via `difflib.SequenceMatcher` — supports Portuguese names, partial names, internal names.

## How to validate

```bash
source ~/.konecty/.env
python3 skills/konecty-modules/scripts/modules.py list
python3 skills/konecty-modules/scripts/modules.py fields "contato"
python3 skills/konecty-modules/scripts/modules.py search "camp"
```

## Files affected

- `skills/konecty-modules/SKILL.md` (new)
- `skills/konecty-modules/scripts/modules.py` (new)
- `docs/changelog/README.md` (updated)
- `docs/changelog/2026-03-16_konecty-modules-skill.md` (new)

## Migration

None required.
