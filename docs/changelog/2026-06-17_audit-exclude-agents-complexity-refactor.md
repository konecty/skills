# Changelog: Exclude `.agents/` from audits; refactor critical-complexity functions

## Date

2026-06-17

## Summary

Cleared the completion-gate audits (`codebase-intelligence` + `codebase-security`) of vendored-skill noise and pre-existing complexity debt. The intelligence verdict went from **FAIL → WARN**.

- **`ruff.toml`** (new, repo root): `extend-exclude = [".agents"]`. The `codebase-intelligence` dead-code layer runs `ruff` over the whole repo regardless of scope, so this keeps vendored third-party skills under `.agents/` out of every audit run.
- **`.agents/skills/codebase-intelligence/scripts/audit.sh`** and **`.agents/skills/codebase-security/scripts/audit.sh`**: in `--changed-since` mode, the target file list now drops dot-directory paths (`| grep -vE '(^|/)\.'`), mirroring the exclusion the full-scan branch already applies (`-not -path '*/\.*'`). This removes `.agents/` files (e.g. bandit SAST findings) from the changed-files scope. _Note: these are vendored scripts — a future `skills update` may overwrite them; the repo-root `ruff.toml` covers the persistent dead-code case independently._
- **`skills/konecty-data/scripts/upload.py`**: refactored `cmd_upload` (CC 33 → 6) by extracting `_validate_upload_constraints`, `_extract_stored_metadata`, and `_print_upload_result`.
- **`skills/konecty-meta/scripts/meta_remove.py`**: refactored `cmd_apply` (CC 31 → 11) by extracting `_guard_primary_delete`, `_process_delete_item`, and `_warn_inconsistent_state`. Removed the unused `skipped` counter (dead code) and an unused `name` unpack.
- Ran `ruff check --fix skills/` to clear auto-fixable unused imports/variables.

## Rationale

The PR completion gate (`make audit`) was reporting a `fail` driven entirely by two pre-existing high-complexity functions (CC ≥ 25) and a long tail of findings inside vendored `.agents/` skills that this repo does not own. Refactoring the two functions removes the only blocking findings, and excluding `.agents/` makes the audit reports reflect this repo's own code so the gate stays meaningful. No behavior change in the refactored commands.
