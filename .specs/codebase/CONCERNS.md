# Codebase Concerns

**Analyzed:** 2026-05-19  
**Scope:** 18 production skills, 0 test files, 0 CI workflows

---

## HIGH: No Automated Testing or CI Pipeline

**Evidence:** `find skills/ -name "*test*" -o -name "conftest*"` returns nothing. No `.github/workflows/`. No `pytest.ini`, `tox.ini`, `Makefile`.  
**Risk:** Any skill change can break credential loading, HTTP parsing, or CLI arg parsing without detection. Security audits (Snyk, Socket) are manual and skippable.  
**Fix approach:**
1. Add `pytest` + `pytest-mock` to a dev requirements file
2. Write unit tests for `_load_credentials()` and `_request()` in each script family
3. Add GitHub Actions workflow: lint (flake8/ruff) + `python3 -m py_compile` on all scripts + `gh skill publish --dry-run`
4. Wire Snyk scan into CI (`snyk-agent-scan` on PRs that touch `skills/`)

---

## HIGH: Credential Loading Code Is Duplicated in Every Script

**Evidence:** Every `scripts/*.py` has its own `_load_credentials()` function doing: env var check → `.env` parse → credentials ini parse. Confirmed in `modules.py`, `find.py`, `create.py`, `update.py`, `delete.py`, `upload.py`, and all `meta-*.py` scripts.  
**Risk:** Bug in credential loading must be fixed in 18 places. Already showing divergence: some scripts check `KONECTY_USER_ID`, some don't.  
**Fix approach:**
1. Create `skills/_shared/konecty_util.py` (or `.agents/common/konecty_util.py`)
2. Extract `load_credentials()`, `api_request()`, `parse_api_error()` into it
3. Each script imports from `konecty_util` via relative path
4. Note: if skills are distributed individually (not as a monorepo), shared utilities complicate packaging — evaluate trade-off before implementing

---

## MEDIUM: API Error Response Format Is Not Normalized

**Evidence:** Konecty API returns errors in two formats depending on the endpoint:
- User-level API: `{"success": false, "errors": [{"message": "..."}]}`
- Admin API: `{"success": false, "message": "..."}`
Some scripts check `result.get("errors")`, some check `result.get("message")`. No unified error parser.  
**Risk:** Silent failures if the wrong key is checked; error messages get swallowed.  
**Fix approach:** Extract `_parse_api_error(result)` that handles both shapes. Add to shared utility (see HIGH item above).

---

## MEDIUM: Reference Documentation Organization Is Inconsistent

**Evidence:**
- `skills/konecty-session/reference.md` (top-level, singular)
- `skills/konecty-find/references/filter-operators.md` (subfolder, plural)
- `skills/konecty-meta-hook/references/hook-contracts.md`, `hook-patterns.md`
- Some skills have no `references/` at all

**Risk:** Agents and human contributors don't know where to find or add reference material. SKILL.md links may break if convention changes.  
**Fix approach:** Adopt one convention: `references/` subfolder for all multi-file skills, `references/index.md` as a top-level reference for simple skills. Update `template/SKILL.md` to show this structure.

---

## MEDIUM: `.specs/project/` Files Referenced but Not Created

**Evidence:** `AGENTS.md` mandates `PROJECT.md`, `ROADMAP.md`, and `STATE.md` under `.specs/project/`. Running `ls .specs/project/` returns nothing.  
**Risk:** AI agents working in this repo (including new sessions of Claude Code) will operate without vision/roadmap/state context, leading to inconsistent decisions.  
**Fix approach:** Initialize `.specs/project/` using the `tlc-spec-driven` `initialize project` command. This is quick (~30 min) and the payoff is immediate for all future sessions.

---

## MEDIUM: No Pre-commit Hooks to Protect Credentials

**Evidence:** `.gitignore` has patterns for `.env`, `credentials`, `*.pem`, but no pre-commit hook enforces this. `skills/konecty-session/` has a local `.env` file for session state.  
**Risk:** `git add -A` by a developer or agent could accidentally stage `~/.konecty/.env` or session credentials. No automated guard exists.  
**Fix approach:**
1. Add `.pre-commit-config.yaml` with `detect-secrets` or `gitleaks` scan
2. Or add a simple `pre-commit` shell hook that blocks `.env` and `credentials` files
3. Document in `docs/development.md`

---

## LOW: `template/SKILL.md` Is Too Minimal

**Evidence:** `template/SKILL.md` has only `## Examples` and `## Guidelines` sections. Production skills have `## Prerequisites`, `## API Endpoints`, `## Workflow`, `## Key Concepts`, `## Script Reference`.  
**Risk:** New skill authors produce inconsistent, under-documented skills. AI agents scaffolding new skills lack a clear structural model.  
**Fix approach:** Update `template/SKILL.md` to show the full production structure with placeholder sections. Add a note about the 300-line limit and `references/` folder usage.

---

## LOW: No Skill Deprecation Policy

**Evidence:** No documented process for retiring skills, handling breaking Konecty API changes, or migrating users from deprecated skills.  
**Risk:** As the Konecty API evolves, skills may silently break. No version migration path documented.  
**Fix approach:** Add an ADR documenting: deprecation lifecycle (deprecated → archived → removed), semantic versioning in frontmatter `metadata.version`, changelog entry for deprecations.

---

## LOW: Python CLI Subcommand Structures Are Inconsistent Across Skills

**Evidence:**
- `modules.py` → subcommands: `list`, `fields`, `search`
- `find.py` → subcommands: `find`, `query`, `sql`
- `create.py` → subcommands: `create`, `lookup`
- `sync.py` → subcommands: `plan`, `apply`

No shared CLI framework. Each skill invents its own subcommand names.  
**Risk:** Minor ergonomic inconsistency. Agents must read each SKILL.md carefully; no predictable CLI pattern.  
**Fix approach:** Add a "CLI conventions" section to `docs/development.md` (don't refactor existing scripts). New skills should follow: verb-based subcommands aligned to the skill's operations.

---

## LOW: External Skill Versions Not Pinned to Specific Tags/Commits

**Evidence:** `skills-lock.json` stores `computedHash` but not a version tag or commit SHA for `skill-creator` and `tlc-spec-driven`.  
**Risk:** If the upstream skill repos change their SKILL.md, the installed copy (`.agents/skills/`) becomes stale. No automated update mechanism.  
**Fix approach:** Document update procedure in `docs/development.md`: `gh skill update` or `npx skills update`. Add version tags to `skills-lock.json` when the CLI supports it.

---

## INFO: Changelog Entries Are in Portuguese

**Observation:** All 13 changelog entries and ADRs are in Portuguese (or mixed Portuguese/English). This is intentional — Konecty is a Brazilian product and the team is Portuguese-speaking.  
**Not a concern** — consistent with project context. Worth noting for external contributors.
