# LESSONS — auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation — do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 — When enforcement lives server-side (e.g. KonFilter/normalizeKonectyFilter rejecting Mongo-shaped input), do not write an AC claiming the SKILL rejects it 'locally': the skill only catches malformed JSON locally and forwards valid-JSON-but-wrong-shape to be surfaced as a server tool-validation error. State where each validation actually happens.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `konecty-data/spec-authoring` · harmful: 0
- features: find-via-mcp
- evidence: spec.md FMCP-02 + Edge case (sort) (konecty-data/spec-authoring)
- last seen: 2026-07-11T16:42:12Z

## Quarantined (failed when applied — ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
