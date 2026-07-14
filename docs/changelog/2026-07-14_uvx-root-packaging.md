# uvx root packaging fix

**Date:** 2026-07-14
**Type:** fix (repo structure)

## Problem

The documented one-liner failed on a fresh machine:

```
uvx --from git+https://github.com/konecty/skills konecty-skills install
× Failed to resolve `--with` requirement
╰─▶ ... does not appear to be a Python project, as neither `pyproject.toml` nor `setup.py` are present
```

`uv` resolves `--from git+…` against the **repo root**, but the packaging metadata lived only in `installer/pyproject.toml`. The pretty command shipped in both READMEs had never been exercised end-to-end from git.

## Change

- `pyproject.toml` moved from `installer/` to the **repo root** (single source of truth), with `tool.hatch.build.targets.wheel.packages = ["installer/src/konecty_skills"]` — the package source stays where it was; only the metadata moved.
- `readme` points to `installer/README.md`; description/keywords refreshed for the 4-skill MCP-first package; version bumped to `0.1.1`.
- `installer/pyproject.toml` removed (avoids version drift between two metadata files).

## Verification

- `uvx --refresh --from <repo root> konecty-skills --help` builds the wheel and runs the CLI.
- `make check` green (py_compile + 211 installer tests) — tests never depended on packaging (`PYTHONPATH=src`).
