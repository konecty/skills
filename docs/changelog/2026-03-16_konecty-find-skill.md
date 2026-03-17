# 2026-03-16 — konecty-find skill

## Summary

Added the `konecty-find` skill: search and query records in any Konecty module via the REST API, with full documentation of filter operators, field-type constraints, dynamic values, and the cross-module query interface.

## Motivation

Agents working with Konecty data need to construct correct search filters and understand which operators are valid for each field type, what dynamic date variables exist, and how to perform cross-module queries with relations and aggregations. Without this skill, agents must re-discover the API structure on every task.

## What Changed

New skill added: `skills/konecty-find/`

| File | Description |
|------|-------------|
| `SKILL.md` | Skill entry point — prerequisites, API overview, quick examples, filter structure summary |
| `scripts/find.py` | CLI script with `find`, `query`, and `sql` subcommands. Stdlib only. |
| `references/filter-operators.md` | Complete KonFilter structure, all 20 operators, operators by field type matrix, compound field paths, dynamic date/user variables, nested filter examples |
| `references/cross-module-query.md` | Full `/rest/query/json` schema, relations, aggregators (count/sum/avg/min/max/first/last/push/addToSet), groupBy, NDJSON response format, SQL interface |

## Technical Impact

- Covers `/rest/data/:document/find` (GET and POST) and `/rest/query/json` (NDJSON streaming)
- Script uses Python stdlib only (no pip dependencies)
- Follows the same credential loading pattern as `konecty-session` and `konecty-modules` (`~/.konecty/.env`)

## External Impact

None. Read-only queries against the Konecty API.

## How to Validate

```bash
# Validate skill structure
python3 agents/skills/skill-creator/scripts/quick_validate.py skills/konecty-find

# Test script help
python3 skills/konecty-find/scripts/find.py --help
python3 skills/konecty-find/scripts/find.py find --help
python3 skills/konecty-find/scripts/find.py query --help
python3 skills/konecty-find/scripts/find.py sql --help
```

## Affected Files

- `skills/konecty-find/SKILL.md` (new)
- `skills/konecty-find/scripts/find.py` (new)
- `skills/konecty-find/references/filter-operators.md` (new)
- `skills/konecty-find/references/cross-module-query.md` (new)
- `docs/changelog/README.md` (updated)

## Migration

None required.
