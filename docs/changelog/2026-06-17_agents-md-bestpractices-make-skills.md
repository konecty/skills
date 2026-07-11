# Changelog: AGENTS.md best-practices, Makefile targets, marketing skills

## Date

2026-06-17

## Summary

Aligned repo conventions with the patterns from the company-brain `AGENTS.md` and expanded tooling.

- **`AGENTS.md`** (and its `CLAUDE.md` symlink):
  - Added a **`## Read first`** section pointing agents at `README.md`, `.specs/project/STATE.md`, `.specs/codebase/`, `template/SKILL.md` + `spec/`, and the in-flight feature specs.
  - Added a **`## Commands`** cheat-sheet mapping every `make` target to its purpose and prerequisites.
  - Expanded **`## Workflow`**: `grill-with-docs` as the pre-planning clarify step, and `codebase-intelligence` + `codebase-security` as the **completion gate** before declaring done / opening a PR. Added an "Available skills" table.
  - Added the **Shared-files invariant** under Architecture: gated files in `shared-files.txt` must stay byte-identical across `konecty-data` and `konecty-meta` (enforced by pre-commit + GitHub Action).
- **`Makefile`**: expanded from the single `setup` target to a self-documenting set — `help`, `setup`, `lint`, `shared-check`, `validate`, `test`, `test-cov`, `audit`, `check`, `clean`.
- **`.agents/skills/`**: vendored four marketing/copywriting skills from `coreyhaines31/marketingskills` — `copywriting`, `content-strategy`, `marketing-ideas`, `marketing-psychology`. Added lock entries for these plus the previously-untracked `codebase-intelligence` and `codebase-security` to `skills-lock.json`.

## Rationale

The repo had a strong SDD pipeline but no orientation layer (where to start reading) and only one `make` target. Borrowing company-brain's `Read first` / `Commands` / completion-gate conventions makes the repo self-navigable for agents, and the marketing/copywriting skills support publishing the skills to marketplaces.
