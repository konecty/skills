# 2026-06-17 — `konecty-skills` CLI installer

## Summary

Added a one-command installer for the Konecty Agent Skills, inspired by [Reversa](https://github.com/sandeco/reversa) but adapted to our stdlib-only Python stack. It lives in [`installer/`](../../installer) and is distributed via `uvx`:

```bash
uvx --from git+https://github.com/konecty/skills konecty-skills install
```

## What changed

- **New package `installer/`** — a stdlib-only Python package (`konecty-skills`) with a `pyproject.toml` entry point. No third-party runtime dependencies (NFR1).
- **Six commands**: `install`, `configure`, `status`, `update`, `doctor`, `uninstall`. All accept `--yes`/`--engine`/`--scope`/`--url`/`--ref` for non-interactive use.
- **Engine detection** — installs into `.claude/skills/`, `.agents/skills/`, or `.cursor/skills/` based on signals in the target dir (Reversa's universal-path model); global scope falls back to `~/.claude/skills/`.
- **Runtime skill download** — fetches `skills/konecty-data` + `skills/konecty-meta` from the public GitHub archive tarball (`urllib`+`tarfile`, no `git` binary), with a path-traversal guard and a token fallback for private repos.
- **Credential parametrization** — drives the existing `konecty-data/scripts/auth.py` OTP flow via subprocess (no logic duplication) to write `~/.konecty/.env`.
- **Safety** — never deletes/modifies pre-existing files: entry files (`CLAUDE.md`/`AGENTS.md`) get a marker-delimited idempotent block; a global `~/.konecty/manifest.json` (keyed by install root) records per-file SHA-256 so `update`/`uninstall` preserve local edits.
- **Colored ASCII banner** — KONECTY in ANSI Shadow, one of the 7 globe colors per letter (truecolor; auto-disabled on non-TTY / `NO_COLOR`).
- **Tooling** — `make installer-test` runs the installer unit suite; folded into `make check` (offline gate). The package ships **128 stdlib `unittest` tests** covering every module (network/OTP boundaries mocked).

## Specs

Planned via SDD: `.specs/features/konecty-skills-installer/` (`spec.md`, `design.md`, `tasks.md`). Decisions logged in `.specs/project/STATE.md` (2026-06-17 installer CLI design).
