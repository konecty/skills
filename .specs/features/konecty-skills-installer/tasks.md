# Konecty Skills Installer (CLI) Tasks

**Design**: `.specs/features/konecty-skills-installer/design.md`
**Spec**: `.specs/features/konecty-skills-installer/spec.md`
**Status**: In Progress

> Execution decisions: Phase 2 (T2–T7) runs as parallel Sonnet subagents; no MCPs (stdlib + native tools only); `copywriting` optional in T14, `verify` optional in T15.

---

## Testing approach (installer subtree)

The repo's `TESTING.md` matrix requires **unit** tests for Python scripts, CLI arg parsing, and credential loading; **integration** for live Konecty API. The installer is stdlib-only (NFR1), so:

- **Unit gate (`quick`)**: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .) -v` — stdlib `unittest`, no new deps. Network (`fetcher`) and OTP (`credentials`) are tested with mocked `urllib`/`subprocess`.
- **Build gate (`build`)**: `uvx --from ./installer konecty-skills --help` — proves the package builds and the entry point resolves.
- **Integration (manual / `full`)**: real tarball download + live OTP against a dev Konecty — covered in T15 (validate), not a blocking unit gate. Mirrors the e2e-harness direction (live branches exercised manually, local logic unit-tested).

---

## Execution Plan

### Phase 1: Foundation (Sequential)

```
T1 (scaffold)
```

### Phase 2: Leaf modules (Parallel — depend only on T1)

```
        ┌→ T2 banner   [P]
        ├→ T3 engines   [P]
T1 ─────┼→ T4 manifest  [P]
        ├→ T5 ui        [P]
        ├→ T6 fetcher   [P]
        └→ T7 credentials [P]
```

### Phase 3: Installer core (Sequential — shares manifest/engines)

```
T3, T4 ──→ T8 (install + merge entry) ──→ T9 (update + uninstall)
```

### Phase 4: CLI wiring (Sequential — all edit cli.py)

```
T2..T8 ──→ T10 install cmd ──→ T11 configure ──→ T12 status+doctor ──→ T13 update+uninstall
```

### Phase 5: Docs & validation (Sequential)

```
T10..T13 ──→ T14 (docs+changelog) ──→ T15 (manual validate)
```

---

## Task Breakdown

### T1: Scaffold `installer/` package

**What**: Create the packaged CLI skeleton: `pyproject.toml` + src layout + empty module stubs + argparse dispatcher that prints help.
**Where**: `installer/pyproject.toml`, `installer/src/konecty_skills/__init__.py`, `installer/src/konecty_skills/cli.py`, stubs for `banner|ui|engines|fetcher|manifest|installer|credentials.py`, `installer/tests/__init__.py`
**Depends on**: None
**Reuses**: skill `pyproject` conventions (stdlib-only)
**Requirement**: NFR1

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `pyproject.toml` declares `name="konecty-skills"`, `requires-python>=3.9`, `dependencies=[]`, `[project.scripts] konecty-skills="konecty_skills.cli:main"`
- [ ] `cli.main(argv)` parses subcommands `install|configure|status|update|doctor|uninstall` + global flags (`--yes`,`--engine`,`--scope`,`--url`,`--ref`) and returns an int
- [ ] Each subcommand dispatches to a stub returning exit 0 (wired in later tasks)
- [ ] Build gate passes: `uvx --from ./installer konecty-skills --help`
- [ ] Test count: 0 (scaffold)

**Tests**: none
**Gate**: build
**Commit**: `feat(installer): scaffold konecty-skills CLI package`

---

### T2: `banner.py` — colored ASCII banner [P]

**What**: Port the validated prototype: 7-letter ANSI-Shadow KONECTY banner, 7 globe colors, TTY/`NO_COLOR` aware.
**Where**: `installer/src/konecty_skills/banner.py`, `installer/tests/test_banner.py`
**Depends on**: T1
**Reuses**: `/tmp/konecty-banner/banner.py` (prototype)
**Requirement**: spec "banner colorido"; NFR5 (non-TTY)

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `render(color=True)` returns text containing all 7 letterforms; `render(color=False)` emits no ANSI escapes
- [ ] `print_banner()` auto-disables color when not a TTY or `NO_COLOR` is set
- [ ] Unit tests: color-on contains `\033[38;2;`, color-off does not, "BUSINESS PLATFORM" present
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥3 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): KONECTY truecolor banner`

---

### T3: `engines.py` — detection + path resolution [P]

**What**: Detect engines in a target dir and resolve skills-destination / entry-file paths per the design table.
**Where**: `installer/src/konecty_skills/engines.py`, `installer/tests/test_engines.py`
**Depends on**: T1
**Reuses**: design detection table
**Requirement**: INSTALL-AC1, AC2, AC3; Q3

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `detect(root)` returns engines for `.claude/`|`CLAUDE.md` → claude, `AGENTS.md`|`.agents/` → agents, `.cursor/` → cursor
- [ ] `dest_path(engine, root, scope)` returns project (`./.claude/skills` etc.) and global (`~/.claude/skills`) paths
- [ ] `entry_file(engine, root)` returns `CLAUDE.md`/`AGENTS.md` or None
- [ ] Unit tests use tmp dirs with each signal; empty dir → [] (global fallback handled by caller)
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥4 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): engine detection and path resolution`

---

### T4: `manifest.py` — model, hashing, conflict diff [P]

**What**: Global manifest (`~/.konecty/manifest.json`) keyed by install root; sha256 hashing; locally-modified detection.
**Where**: `installer/src/konecty_skills/manifest.py`, `installer/tests/test_manifest.py`
**Depends on**: T1
**Reuses**: stdlib `hashlib`/`json`
**Requirement**: INSTALL-AC5; UPD-AC2,AC3; NFR2,NFR3

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `load()`/`save()` round-trip the `{schema, installations:{<root>:{...}}}` model
- [ ] `hash_file(path)` returns sha256 hex
- [ ] `diff(installation, dest)` returns files whose on-disk hash ≠ recorded hash
- [ ] Unit tests: round-trip, hash stability, conflict detected on modified file, missing file handled
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥4 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): manifest model with sha256 conflict detection`

---

### T5: `ui.py` — prompts, status lines, `--yes` [P]

**What**: Centralized interaction layer; honors non-interactive mode.
**Where**: `installer/src/konecty_skills/ui.py`, `installer/tests/test_ui.py`
**Depends on**: T1
**Reuses**: `banner` color helpers (import-safe; no circular dep — banner has no ui import)
**Requirement**: NFR5

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `confirm(prompt, default, assume_yes)` returns default when `assume_yes`; parses y/n otherwise
- [ ] `select(items, preselected, assume_yes)` returns preselected when `assume_yes`
- [ ] `ask(prompt, default)` returns default on empty input
- [ ] `step/ok/warn/err` print prefixed status lines
- [ ] Unit tests monkeypatch `input` for interactive paths and assert assume_yes shortcuts
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥4 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): interactive UI layer with non-interactive mode`

---

### T6: `fetcher.py` — tarball download + skill extraction [P]

**What**: Download the repo archive and extract only `skills/konecty-data` + `skills/konecty-meta` to a temp dir.
**Where**: `installer/src/konecty_skills/fetcher.py`, `installer/tests/test_fetcher.py`
**Depends on**: T1
**Reuses**: stdlib `urllib.request`/`tarfile`/`tempfile`
**Requirement**: INSTALL-AC4; Q1

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `fetch_skills(ref="main", token=None)` GETs `https://github.com/konecty/skills/archive/refs/heads/{ref}.tar.gz`, extracts the two skill folders, returns `{tmp_dir, skills_root, ref, commit}`
- [ ] Path-traversal guard on tar members (no extraction outside tmp)
- [ ] On 401/404 + token present → retry `api.github.com/.../tarball/{ref}` with `Authorization`
- [ ] Raises `FetchError` on failure (no FS mutation outside tmp)
- [ ] Unit tests build an in-memory tar fixture and patch `urllib` to return it; assert both skills extracted, traversal rejected, `FetchError` on HTTP error
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥4 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): fetch skills tarball from GitHub archive`

---

### T7: `credentials.py` — URL prompt + OTP via auth.py subprocess [P]

**What**: URL validation, current-env read, and OTP orchestration delegating to the installed `auth.py`.
**Where**: `installer/src/konecty_skills/credentials.py`, `installer/tests/test_credentials.py`
**Depends on**: T1
**Reuses**: `skills/konecty-data/scripts/auth.py` (subprocess); `ensure_env_file` transitively
**Requirement**: CRED-AC1..AC6; D3

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `current_env()` reads `~/.konecty/.env` → `{url, token}` (or empty)
- [ ] `prompt_url(default)` validates scheme+host via `urllib.parse`
- [ ] `run_otp(url, auth_py, identifier)` runs `request-otp` then `verify-otp` via `subprocess`; non-zero exit → returns False without raising
- [ ] `write_url_only(url)` writes just `KONECTY_URL` with `0o600`
- [ ] Unit tests patch `subprocess.run` (success + failure exit codes) and assert no exceptions escape; URL validation accepts/rejects samples
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥4 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): credential setup via OTP subprocess`

---

### T8: `installer.py` — install copy + idempotent entry-file merge

**What**: Copy skills into engine paths (temp→atomic replace) and merge a marker-delimited block into entry files; record hashes via manifest.
**Where**: `installer/src/konecty_skills/installer.py`, `installer/tests/test_installer.py`
**Depends on**: T3, T4
**Reuses**: `engines` (paths), `manifest` (hash/save), stdlib `shutil`
**Requirement**: INSTALL-AC4,AC5,AC6; NFR2,NFR3,NFR4

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `install(skills_root, engines, scope, manifest)` copies both skills into each engine dest and returns an `InstallReport`
- [ ] `merge_entry_block(entry_file)` inserts/replaces only between `<!-- konecty-skills:start -->`/`<!-- konecty-skills:end -->`; content outside markers untouched; re-run is idempotent
- [ ] Manifest written after copy with per-file sha256
- [ ] Shared files (`shared-files.txt`) copied byte-identical (NFR4) — asserted in test
- [ ] Unit tests: copy into tmp engine dirs, idempotent merge (run twice → identical), pre-existing entry-file content preserved
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥5 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): copy skills and merge entry-file block`

---

### T9: `installer.py` — safe update + uninstall

**What**: Update skips locally-modified files (reports conflicts); uninstall removes only manifest-tracked files, preserves `.env` unless `--purge`.
**Where**: `installer/src/konecty_skills/installer.py` (extend), `installer/tests/test_installer.py` (extend)
**Depends on**: T8, T4
**Reuses**: `manifest.diff`
**Requirement**: UPD-AC2,AC3,AC4; DOC-AC2,AC3

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `update(...)` re-copies only files whose disk hash == recorded hash; modified files preserved and returned as `Conflict`s; manifest re-hashed for updated files
- [ ] `uninstall(installation, purge)` removes only listed files; confirms on modified; leaves `~/.konecty/.env` unless `purge`
- [ ] Unit tests: edit a file → update preserves it + reports conflict; uninstall removes tracked files only; untracked sibling file survives
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥4 new tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): safe update and uninstall with conflict guards`

---

### T10: CLI `install` command wiring

**What**: Wire the full install flow into `cli.py`: banner → detect → select → fetch → copy → manifest → credentials.
**Where**: `installer/src/konecty_skills/cli.py`, `installer/tests/test_cli_install.py`
**Depends on**: T2, T3, T4, T5, T6, T7, T8
**Reuses**: all phase-2/3 modules
**Requirement**: INSTALL-AC1..AC6; CRED-AC1..AC4; NFR5

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `konecty-skills install --yes --engine claude --scope project --url <u>` runs end-to-end with `fetcher`/`credentials` patched, producing skill dirs + manifest entry
- [ ] No-engine-detected path falls back to prompting/global per design
- [ ] Unit test drives `main(["install","--yes",...])` against a tmp CWD with `fetcher.fetch_skills` and OTP subprocess patched; asserts files + manifest
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥3 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): wire install command end-to-end`

---

### T11: CLI `configure` command

**What**: Credentials-only entry: URL prompt + OTP (or URL-only), no skill copy.
**Where**: `installer/src/konecty_skills/cli.py` (extend), `installer/tests/test_cli_configure.py`
**Depends on**: T7, T10
**Reuses**: `credentials`
**Requirement**: CRED-AC1..AC6

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `konecty-skills configure --url <u>` runs OTP flow (patched) and writes `.env`; existing `.env` triggers confirm (AC5)
- [ ] Unit test asserts confirm-on-existing and URL-only fallback
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥2 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): configure command for credentials`

---

### T12: CLI `status` + `doctor` commands

**What**: `status` reports installations/credentials; `doctor` validates files vs manifest + probes Konecty health/token.
**Where**: `installer/src/konecty_skills/cli.py` (extend), `installer/tests/test_cli_status.py`
**Depends on**: T4, T9, T10
**Reuses**: `manifest.diff`, `credentials.current_env`, stdlib `urllib` for health probe
**Requirement**: UPD-AC1; DOC-AC1

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `status` lists installations for CWD (`--all` lists every root), engines, source ref, and credential presence
- [ ] `doctor` reports manifest-vs-disk diffs and a health/token check (network patched in test)
- [ ] Unit tests assert status output and doctor diff detection
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥3 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): status and doctor commands`

---

### T13: CLI `update` + `uninstall` commands

**What**: Wire `installer.update`/`installer.uninstall` into the CLI with confirmation + `--purge`.
**Where**: `installer/src/konecty_skills/cli.py` (extend), `installer/tests/test_cli_lifecycle.py`
**Depends on**: T9, T10
**Reuses**: `installer.update/uninstall`, `fetcher`
**Requirement**: UPD-AC2..AC4; DOC-AC2,AC3

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `update` re-fetches and applies safe update; `uninstall [--purge]` removes tracked files
- [ ] Unit tests drive both against a tmp install with patched fetcher
- [ ] Gate passes: `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Test count: ≥2 tests pass

**Tests**: unit
**Gate**: quick
**Commit**: `feat(installer): update and uninstall commands`

---

### T14: Docs, Makefile target, changelog

**What**: Document the installer (README install command, AGENTS.md note), add `make installer-test`, and a changelog entry (repo-structure change).
**Where**: `README.md`, `AGENTS.md`, `Makefile`, `docs/changelog/2026-06-17_installer-cli.md`, `docs/changelog/README.md`
**Depends on**: T10, T11, T12, T13
**Reuses**: existing Makefile patterns
**Requirement**: spec Goals (one-command install); Changelog rule

**Tools**: MCP NONE · Skill `copywriting` (optional, for the README install blurb)

**Done when**:
- [ ] README documents `uvx --from git+https://github.com/konecty/skills konecty-skills install` + the 6 commands
- [ ] `make installer-test` runs `(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)`
- [ ] Changelog entry added + README table row (per Changelog rule)
- [ ] Gate passes: `make installer-test` and `make check`
- [ ] Test count: full installer suite green

**Tests**: none (docs)
**Gate**: full
**Commit**: `docs(installer): document uvx install flow and add make target`

---

### T15: Manual end-to-end validation (live)

**What**: Validate the real flow: `uvx --from ./installer konecty-skills install` into a temp project, real tarball fetch, live OTP against a dev Konecty, `doctor` green; record results.
**Where**: `.specs/features/konecty-skills-installer/SUMMARY.md`
**Depends on**: T14
**Reuses**: dev Konecty (`:3000`), `~/.konecty/.env`
**Requirement**: INSTALL + CRED + DOC acceptance "Independent Test"s

**Tools**: MCP NONE · Skill `verify` (optional)

**Done when**:
- [ ] Fresh temp dir with `.claude/` → install copies both skills; manifest written
- [ ] Live OTP writes valid `~/.konecty/.env`; `doctor` reports connection OK
- [ ] `update` preserves a hand-edited SKILL.md and reports the conflict
- [ ] Cursor path verified or `cursor` engine deferred (design open item)
- [ ] Results recorded in SUMMARY.md (PASS/FAIL/SKIP per AC)

**Tests**: integration (manual)
**Gate**: full
**Commit**: `test(installer): record manual e2e validation summary`

---

## Pre-Approval Validation

### Check 1 — Task Granularity

| Task | Scope | Status |
|------|-------|--------|
| T1 scaffold | 1 package skeleton | ✅ |
| T2 banner | 1 module + tests | ✅ |
| T3 engines | 1 module + tests | ✅ |
| T4 manifest | 1 module + tests | ✅ |
| T5 ui | 1 module + tests | ✅ |
| T6 fetcher | 1 module + tests | ✅ |
| T7 credentials | 1 module + tests | ✅ |
| T8 installer install/merge | 1 module (2 cohesive fns) + tests | ✅ |
| T9 installer update/uninstall | same module, distinct concern | ✅ (cohesive) |
| T10 cli install | 1 command | ✅ |
| T11 cli configure | 1 command | ✅ |
| T12 cli status+doctor | 2 read-only cmds, 1 file | ✅ (cohesive) |
| T13 cli update+uninstall | 2 lifecycle cmds, 1 file | ✅ (cohesive) |
| T14 docs | docs+make+changelog | ✅ (one deliverable: "ship docs") |
| T15 validate | manual UAT | ✅ |

### Check 2 — Diagram ↔ Definition Cross-Check

| Task | Depends on (body) | Diagram arrows | Status |
|------|-------------------|----------------|--------|
| T1 | None | (root) | ✅ |
| T2 | T1 | T1→T2 | ✅ |
| T3 | T1 | T1→T3 | ✅ |
| T4 | T1 | T1→T4 | ✅ |
| T5 | T1 | T1→T5 | ✅ |
| T6 | T1 | T1→T6 | ✅ |
| T7 | T1 | T1→T7 | ✅ |
| T8 | T3, T4 | T3,T4→T8 | ✅ |
| T9 | T8, T4 | T8→T9 (T4 via T8) | ✅ |
| T10 | T2,T3,T4,T5,T6,T7,T8 | T2..T8→T10 | ✅ |
| T11 | T7, T10 | T10→T11 | ✅ |
| T12 | T4, T9, T10 | T11→T12 (chain) | ✅ |
| T13 | T9, T10 | T12→T13 (chain) | ✅ |
| T14 | T10..T13 | T13→T14 | ✅ |
| T15 | T14 | T14→T15 | ✅ |

CLI tasks T10–T13 form a sequential chain (all edit `cli.py` → no `[P]`), consistent with the Phase-4 diagram.

### Check 3 — Test Co-location Validation

| Task | Code layer | Matrix requires | Task says | Status |
|------|-----------|-----------------|-----------|--------|
| T1 | package scaffold | none | none | ✅ |
| T2 | Python module | unit | unit | ✅ |
| T3 | Python module | unit | unit | ✅ |
| T4 | credential/manifest logic | unit | unit | ✅ |
| T5 | Python module | unit | unit | ✅ |
| T6 | Python module | unit (net mocked) | unit | ✅ |
| T7 | credential loading | unit | unit | ✅ |
| T8 | Python module | unit | unit | ✅ |
| T9 | Python module | unit | unit | ✅ |
| T10 | CLI arg parsing | unit | unit | ✅ |
| T11 | CLI arg parsing | unit | unit | ✅ |
| T12 | CLI + API probe | unit (net mocked) | unit | ✅ |
| T13 | CLI arg parsing | unit | unit | ✅ |
| T14 | docs | none | none | ✅ |
| T15 | live API integration | integration | integration (manual) | ✅ |

All checks pass. Live integration (real download + OTP) is intentionally concentrated in T15 — unit tasks mock those boundaries, consistent with the e2e-harness decision (D4) that network/OTP branches are exercised manually while local logic is unit-tested.

---

## Parallel Execution Map

```
Phase 1: T1
Phase 2 (after T1):  T2 [P]  T3 [P]  T4 [P]  T5 [P]  T6 [P]  T7 [P]
Phase 3 (after T3,T4):  T8 → T9
Phase 4 (after T2..T8):  T10 → T11 → T12 → T13   (sequential: shared cli.py)
Phase 5 (after T13):  T14 → T15
```

Parallel-safety: T2–T7 are separate modules with separate test files writing to isolated tmp dirs (stdlib `unittest`, parallel-safe). T8/T9 share `installer.py`; T10–T13 share `cli.py` → sequential.
