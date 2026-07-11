# Changelog: konecty-dev skill

## Date

2026-06-17

## Summary

- Added skill **`konecty-dev`** under `skills/konecty-dev/` — the **third** Konecty skill, and the first **advisory** one (teaches developer-agents to write integration code; ships no scripts and makes no live calls).
- Scope: how to access Konecty from code, **SDK-first** (Python `konecty_sdk_python` 2.0.3, Node/TS `@konecty/sdk` 1.0.0) with the **full REST API** documented as a first-class agnostic track (curl) for languages without an SDK.
- `SKILL.md` (lean router: bilingual description, trigger table, SDK→REST decision cascade) + 8 references: `getting-started`, `auth-for-code`, `python-sdk`, `typescript-sdk`, `rest-api`, `filters`, `recipes`, `hooks`.
- **Out of the `shared-files.txt` invariant** (no `auth.py`/`modules.py`; its auth doc is the service-account/token model, distinct from the OTP flow).
- `hooks.md` documents the runtime contract of the three data hooks (`scriptBeforeValidation`, `validationScript`, `scriptAfterSave`) — variables, lifecycle, transaction boundary — for *writing* the logic; points to `konecty-meta` to version/apply.

## Rationale

`konecty-data`/`konecty-meta` are operational (they run REST calls). There was no skill for developers building and shipping their own integration code. `konecty-dev` fills that gap, preferring the official SDKs and documenting the REST surface for everything else.

## Notes

- Spec/design/tasks: `.specs/features/konecty-dev/`. Sensitive-source policy: `docs/adr/0005-reference-examples-patterns-not-content.md`.
- All examples use generic modules (`Contact`, `Opportunity`, `Product`, `Task`) with invented logic — no client-derived content.
