# Konecty Skills Consolidation — Tasks

**Spec**: `.specs/features/konecty-skills-consolidation/spec.md`
**Status**: Draft

---

## Execution Plan

### Phase 1: Skill Scaffolding (Parallel)

```
T1 [P] ─┐
         ├─→ Phase 2
T2 [P] ─┘
```

### Phase 2: Scripts Migration (Partially Parallel)

```
T1 ──→ T3 [P] ─┐
T1 ──→ T4 [P]  │
T2 ──→ T5 [P]  ├─→ T6 ──→ Phase 3
T3, T2 ──────→ T6
```

### Phase 3: References Migration (Partially Parallel)

```
T1 ──→ T7 [P] ─┐
T1 ──→ T8 [P]  │
T2 ──→ T9 [P]  ├─→ T10 ──→ Phase 4
T7, T2 ──────→ T10
```

### Phase 4: Shared-Files Manifest

```
T7, T10 ──→ T11 ──→ Phase 5
```

### Phase 5: Enforcement Automation (Parallel)

```
T11 ──→ T12 [P] ─┐
T11 ──→ T13 [P]  ├─→ Phase 6
T11 ──→ T14 [P] ─┘
```

### Phase 6: Migration Audit

```
T1…T14 ──→ T15 ──→ Phase 7
```

### Phase 7: Cleanup

```
T15 ──→ T16
```

---

## Task Breakdown

### T1: Create `skills/konecty-data/SKILL.md` [P]

**What**: New file — frontmatter with description ≤1 024 chars, `## Commands` routing table covering all 7 operations (auth, field-discovery, find, create, update, delete, upload) with PT-BR and EN trigger patterns and `references/<op>.md` links.
**Where**: `skills/konecty-data/SKILL.md`
**Depends on**: None
**Reuses**: `template/SKILL.md`; existing SKILL.md descriptions from konecty-session, konecty-find, konecty-create, konecty-update, konecty-delete, konecty-upload
**Requirement**: CONS-01, CONS-06

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Frontmatter `name: konecty-data`, `description` present and ≤1 024 characters
- [ ] `description` semantically covers: find, create, update, delete, upload, auth (OTP), field discovery
- [ ] `## Commands` table present with `Trigger Pattern | Reference` columns
- [ ] All 7 operations have PT-BR and EN trigger patterns
- [ ] All reference paths point to `references/<op>.md` under konecty-data
- [ ] Gate: `gh skill publish --dry-run` passes (or validates frontmatter manually if gh skill unavailable)

**Tests**: none
**Gate**: skill validation
**Commit**: `feat(konecty-data): add SKILL.md with routing table (CONS-01, CONS-06)`

---

### T2: Create `skills/konecty-meta/SKILL.md` [P]

**What**: New file — frontmatter with description ≤1 024 chars, `## Commands` routing table covering all 11 meta operations (read, document, list, view, access, pivot, hook, namespace, doctor, sync, remove) + auth + field-discovery, with PT-BR and EN triggers.
**Where**: `skills/konecty-meta/SKILL.md`
**Depends on**: None
**Reuses**: `template/SKILL.md`; existing SKILL.md descriptions from all 11 konecty-meta-* skills
**Requirement**: CONS-02, CONS-06

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Frontmatter `name: konecty-meta`, `description` present and ≤1 024 characters
- [ ] `description` semantically covers all 11 meta operations + auth + field discovery
- [ ] `## Commands` table present with `Trigger Pattern | Reference` columns
- [ ] All 13 entries (11 ops + auth + field-discovery) have PT-BR and EN trigger patterns
- [ ] All reference paths point to `references/<op>.md` under konecty-meta
- [ ] Gate: `gh skill publish --dry-run` passes (or validates frontmatter manually if gh skill unavailable)

**Tests**: none
**Gate**: skill validation
**Commit**: `feat(konecty-meta): add SKILL.md with routing table (CONS-02, CONS-06)`

---

### T3: Create shared gated scripts in `konecty-data/scripts/` [P]

**What**: Create two gated scripts in konecty-data — `auth.py` (verbatim copy of `konecty-session/scripts/login.py`) and `modules.py` (verbatim copy of `konecty-modules/scripts/modules.py`). These will be enforced identical in konecty-meta via T6.
**Where**: `skills/konecty-data/scripts/auth.py`, `skills/konecty-data/scripts/modules.py`
**Depends on**: T1 (konecty-data folder created by T1)
**Reuses**: `skills/konecty-session/scripts/login.py`, `skills/konecty-modules/scripts/modules.py`
**Requirement**: CONS-01, CONS-03

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `auth.py` is byte-for-byte identical to `konecty-session/scripts/login.py` (verify: `diff`)
- [ ] `modules.py` is byte-for-byte identical to `konecty-modules/scripts/modules.py` (verify: `diff`)
- [ ] Gate: `python3 -m py_compile skills/konecty-data/scripts/auth.py` exits 0
- [ ] Gate: `python3 -m py_compile skills/konecty-data/scripts/modules.py` exits 0

**Tests**: none
**Gate**: syntax check
**Commit**: `feat(konecty-data): add shared gated scripts auth.py and modules.py (CONS-01, CONS-03)`

---

### T4: Copy data-specific scripts into `konecty-data/scripts/` [P]

**What**: Verbatim copy of 5 Python scripts from their individual skill directories into konecty-data.
**Where**: `skills/konecty-data/scripts/{find,create,update,delete,upload}.py`
**Depends on**: T1
**Reuses**:
- `skills/konecty-find/scripts/find.py`
- `skills/konecty-create/scripts/create.py`
- `skills/konecty-update/scripts/update.py`
- `skills/konecty-delete/scripts/delete.py`
- `skills/konecty-upload/scripts/upload.py`
**Requirement**: CONS-01

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Each of the 5 scripts is byte-for-byte identical to its source (verify: `diff` each pair)
- [ ] Gate: `python3 -m py_compile` on each of the 5 scripts exits 0
- [ ] 5 files present: `find.py`, `create.py`, `update.py`, `delete.py`, `upload.py`

**Tests**: none
**Gate**: syntax check
**Commit**: `feat(konecty-data): add data operation scripts (CONS-01)`

---

### T5: Copy meta-specific scripts into `konecty-meta/scripts/` [P]

**What**: Verbatim copy of 11 Python scripts from individual konecty-meta-* skill directories into konecty-meta.
**Where**: `skills/konecty-meta/scripts/meta_{read,document,list,view,access,pivot,hook,namespace,doctor,sync,remove}.py`
**Depends on**: T2
**Reuses**:
- `skills/konecty-meta-read/scripts/meta_read.py`
- `skills/konecty-meta-document/scripts/meta_document.py`
- `skills/konecty-meta-list/scripts/meta_list.py`
- `skills/konecty-meta-view/scripts/meta_view.py`
- `skills/konecty-meta-access/scripts/meta_access.py`
- `skills/konecty-meta-pivot/scripts/meta_pivot.py`
- `skills/konecty-meta-hook/scripts/meta_hook.py`
- `skills/konecty-meta-namespace/scripts/meta_namespace.py`
- `skills/konecty-meta-doctor/scripts/meta_doctor.py`
- `skills/konecty-meta-sync/scripts/meta_sync.py`
- `skills/konecty-meta-remove/scripts/meta_remove.py`
**Requirement**: CONS-02

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Each of the 11 scripts is byte-for-byte identical to its source (verify: `diff` each pair)
- [ ] Gate: `python3 -m py_compile` on each of the 11 scripts exits 0
- [ ] 11 files present (all `meta_*.py`)

**Tests**: none
**Gate**: syntax check
**Commit**: `feat(konecty-meta): add meta operation scripts (CONS-02)`

---

### T6: Copy shared gated scripts into `konecty-meta/scripts/`

**What**: Copy `auth.py` and `modules.py` from `konecty-data/scripts/` into `konecty-meta/scripts/` — must be byte-identical so the pre-commit gate (T12) doesn't block.
**Where**: `skills/konecty-meta/scripts/auth.py`, `skills/konecty-meta/scripts/modules.py`
**Depends on**: T2, T3
**Reuses**: `skills/konecty-data/scripts/auth.py`, `skills/konecty-data/scripts/modules.py`
**Requirement**: CONS-03

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `diff skills/konecty-data/scripts/auth.py skills/konecty-meta/scripts/auth.py` → empty (identical)
- [ ] `diff skills/konecty-data/scripts/modules.py skills/konecty-meta/scripts/modules.py` → empty (identical)
- [ ] Gate: `python3 -m py_compile` on both exits 0

**Tests**: none
**Gate**: syntax check + diff
**Commit**: `feat(konecty-meta): add shared gated scripts auth.py and modules.py (CONS-03)`

---

### T7: Create gated reference files in `konecty-data/references/` [P]

**What**: Create two gated markdown reference files. `auth.md` — verbatim from `konecty-session/reference.md`. `field-discovery.md` — extract field-discovery instructions from `konecty-modules/SKILL.md`.
**Where**: `skills/konecty-data/references/auth.md`, `skills/konecty-data/references/field-discovery.md`
**Depends on**: T1
**Reuses**: `skills/konecty-session/reference.md`, `skills/konecty-modules/SKILL.md`
**Requirement**: CONS-01, CONS-03

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `auth.md` contains the full OTP flow instructions from konecty-session/reference.md
- [ ] `field-discovery.md` contains field-discovery guidance from konecty-modules/SKILL.md
- [ ] Both files are readable markdown (no broken links to removed sub-references)

**Tests**: none
**Gate**: manual review
**Commit**: `feat(konecty-data): add gated reference files auth.md and field-discovery.md (CONS-01, CONS-03)`

---

### T8: Create operation reference files in `konecty-data/references/` [P]

**What**: Create 5 markdown operation reference files, consolidating sub-references inline.
- `find.md` ← konecty-find SKILL.md instructions + `cross-module-query.md` + `filter-operators.md` inlined as sections
- `create.md` ← konecty-create SKILL.md instructions + `konecty-modules/references/field-types.md` inlined
- `update.md` ← konecty-update SKILL.md instructions (verbatim)
- `delete.md` ← konecty-delete SKILL.md instructions (verbatim)
- `upload.md` ← konecty-upload SKILL.md instructions (verbatim)
**Where**: `skills/konecty-data/references/{find,create,update,delete,upload}.md`
**Depends on**: T1
**Reuses**:
- `skills/konecty-find/{SKILL.md,references/cross-module-query.md,references/filter-operators.md}`
- `skills/konecty-create/SKILL.md`, `skills/konecty-modules/references/field-types.md`
- `skills/konecty-update/SKILL.md`, `skills/konecty-delete/SKILL.md`, `skills/konecty-upload/SKILL.md`
**Requirement**: CONS-01

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] 5 reference files created
- [ ] `find.md` contains cross-module-query and filter-operators as inline sections (no external links to removed files)
- [ ] `create.md` contains field-types as inline section
- [ ] `update.md`, `delete.md`, `upload.md` contain full instructions from their source SKILL.md
- [ ] No broken cross-references in any of the 5 files

**Tests**: none
**Gate**: manual review
**Commit**: `feat(konecty-data): add operation reference files (CONS-01)`

---

### T9: Create operation reference files in `konecty-meta/references/` [P]

**What**: Create 11 markdown operation reference files, consolidating sub-references inline.
- `read.md` ← konecty-meta-read SKILL.md + `references/meta-schemas.md` inlined
- `document.md` ← konecty-meta-document SKILL.md + `field-architecture.md` + `document-events.md` inlined
- `list.md` ← konecty-meta-list SKILL.md (verbatim)
- `view.md` ← konecty-meta-view SKILL.md (verbatim)
- `access.md` ← konecty-meta-access SKILL.md + `access-architecture.md` inlined
- `pivot.md` ← konecty-meta-pivot SKILL.md (verbatim)
- `hook.md` ← konecty-meta-hook SKILL.md + `hook-contracts.md` + `hook-patterns.md` inlined
- `namespace.md` ← konecty-meta-namespace SKILL.md + `namespace-schema.md` inlined
- `doctor.md` ← konecty-meta-doctor SKILL.md (verbatim)
- `sync.md` ← konecty-meta-sync SKILL.md (verbatim)
- `remove.md` ← konecty-meta-remove SKILL.md + `deletion-order.md` inlined
**Where**: `skills/konecty-meta/references/{read,document,list,view,access,pivot,hook,namespace,doctor,sync,remove}.md`
**Depends on**: T2
**Reuses**: SKILL.md and references/ from all 11 konecty-meta-* skills
**Requirement**: CONS-02

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] All 11 reference files created
- [ ] Files with sub-references (`read`, `document`, `access`, `hook`, `namespace`, `remove`) inline their sub-reference content as sections
- [ ] Files without sub-references (`list`, `view`, `pivot`, `doctor`, `sync`) contain full instructions from source SKILL.md
- [ ] No broken cross-references in any of the 11 files

**Tests**: none
**Gate**: manual review
**Commit**: `feat(konecty-meta): add operation reference files (CONS-02)`

---

### T10: Create gated reference files in `konecty-meta/references/`

**What**: Copy `auth.md` and `field-discovery.md` from `konecty-data/references/` into `konecty-meta/references/` — must be byte-identical.
**Where**: `skills/konecty-meta/references/auth.md`, `skills/konecty-meta/references/field-discovery.md`
**Depends on**: T2, T7
**Reuses**: `skills/konecty-data/references/auth.md`, `skills/konecty-data/references/field-discovery.md`
**Requirement**: CONS-03

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `diff skills/konecty-data/references/auth.md skills/konecty-meta/references/auth.md` → empty
- [ ] `diff skills/konecty-data/references/field-discovery.md skills/konecty-meta/references/field-discovery.md` → empty

**Tests**: none
**Gate**: diff
**Commit**: `feat(konecty-meta): add gated reference files auth.md and field-discovery.md (CONS-03)`

---

### T11: Create `shared-files.txt` in both skills

**What**: Create the manifest file that lists all gated (shared) files. Must be identical in both skills. Content:
```
scripts/auth.py
scripts/modules.py
references/auth.md
references/field-discovery.md
```
**Where**: `skills/konecty-data/shared-files.txt`, `skills/konecty-meta/shared-files.txt`
**Depends on**: T7, T10 (gated files must exist before being listed)
**Requirement**: CONS-03, CONS-05

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `shared-files.txt` exists in both skill directories with identical content (4 lines)
- [ ] Every path listed in `shared-files.txt` actually exists in both `konecty-data/` and `konecty-meta/`
- [ ] `diff skills/konecty-data/shared-files.txt skills/konecty-meta/shared-files.txt` → empty

**Tests**: none
**Gate**: diff + existence check
**Commit**: `feat(shared): add shared-files.txt manifest to both skills (CONS-03)`

---

### T12: Create `.githooks/pre-commit` hook [P]

**What**: Shell script that reads `skills/konecty-data/shared-files.txt` and for each listed path compares SHA256 between `konecty-data/<path>` and `konecty-meta/<path>`. Blocks commit if any pair differs, printing which file diverged.
**Where**: `.githooks/pre-commit` (new file, executable)
**Depends on**: T11
**Requirement**: CONS-03, CONS-05

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `.githooks/pre-commit` exists and is executable (`chmod +x`)
- [ ] Script reads `skills/konecty-data/shared-files.txt` (not hardcoded paths)
- [ ] When files differ: exits non-zero with message naming the diverging file
- [ ] When files are identical: exits 0 silently
- [ ] When `konecty-meta/` doesn't exist (one skill absent): exits 0 — not an error (CONS-03 edge case)
- [ ] When a listed file doesn't exist in one skill: exits non-zero with message
- [ ] Manual test: modify `konecty-data/scripts/auth.py` temporarily and run `.githooks/pre-commit` directly — must exit non-zero

**Tests**: none
**Gate**: manual execution
**Commit**: `feat(hooks): add pre-commit shared-files divergence guard (CONS-03, CONS-05)`

---

### T13: Create `.github/workflows/check-shared-files.yml` [P]

**What**: GitHub Actions workflow that triggers on push and pull_request. Compares SHA256 of all files listed in `shared-files.txt` between `konecty-data/` and `konecty-meta/`. Fails the check if any pair diverges.
**Where**: `.github/workflows/check-shared-files.yml`
**Depends on**: T11
**Requirement**: CONS-03

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Workflow triggers on `push` and `pull_request`
- [ ] Uses bash to read `shared-files.txt` and compare SHAs (no external actions for the comparison)
- [ ] On divergence: step fails and prints which file differs
- [ ] On missing file in one skill: step fails with clear message
- [ ] On absent `konecty-meta/` directory: step is skipped (not a failure)
- [ ] Valid YAML (verify: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/check-shared-files.yml'))"`)

**Tests**: none
**Gate**: YAML validation
**Commit**: `feat(ci): add GH Action for shared-files divergence check (CONS-03)`

---

### T14: Create `Makefile` with `make setup` target [P]

**What**: New `Makefile` at repo root with a `setup` target that runs `git config core.hooksPath .githooks`. Must be idempotent.
**Where**: `Makefile`
**Depends on**: T11
**Requirement**: CONS-05

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `Makefile` exists at repo root
- [ ] `make setup` runs `git config core.hooksPath .githooks` and exits 0
- [ ] Running `make setup` twice in a row exits 0 both times (idempotent)
- [ ] Manual test: `make setup && git config --get core.hooksPath` → prints `.githooks`

**Tests**: none
**Gate**: manual execution
**Commit**: `feat(make): add Makefile with setup target for git hooks (CONS-05)`

---

### T15: Migration audit — 1:1 coverage verification

**What**: Verify every operation from the 18 original skills is reachable via `konecty-data` or `konecty-meta`. Produce an audit table in this file under `## Audit Results`.
**Where**: This file (update `## Audit Results` section below)
**Depends on**: T1–T14 (all files must exist)
**Requirement**: CONS-01, CONS-02, CONS-04

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Audit table lists all 18 original skills and their mapped operation in the new skills
- [ ] Every skill has a `✅ Covered` or `❌ Missing` status
- [ ] Zero `❌ Missing` entries
- [ ] All reference file paths in the audit table exist on disk (verified with `ls`)
- [ ] All script paths in the audit table exist on disk (verified with `ls`)
- [ ] Auth + field-discovery are confirmed reachable in both `konecty-data` and `konecty-meta`

**Tests**: none
**Gate**: audit table all ✅
**Commit**: `docs(audit): add migration audit results (CONS-04)`

---

### T16: Delete 18 legacy skills + update CLAUDE.md

**What**: Atomic deletion of all 18 legacy skill directories + update `CLAUDE.md` skills map section to reference `konecty-data` and `konecty-meta` instead of the 18 individual skills.
**Where**: `skills/konecty-{session,modules,find,create,update,delete,upload,meta-read,meta-document,meta-list,meta-view,meta-access,meta-pivot,meta-hook,meta-namespace,meta-doctor,meta-sync,meta-remove}/` (delete) + `CLAUDE.md` (edit)
**Depends on**: T15 (audit must be all ✅ before any deletion)
**Requirement**: CONS-04

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `ls skills/` shows exactly `konecty-data/` and `konecty-meta/` (and nothing else)
- [ ] `CLAUDE.md` Skills map section references `konecty-data` and `konecty-meta`
- [ ] `CLAUDE.md` API surface table updated to match the 2-skill architecture
- [ ] All 18 old directories removed (no dangling references in CLAUDE.md)
- [ ] `make setup && .githooks/pre-commit` exits 0 on the clean state

**Tests**: none
**Gate**: `ls skills/` + manual pre-commit run
**Commit**: `chore: delete 18 legacy skills, update CLAUDE.md skills map (CONS-04)`

---

## Parallel Execution Map

```
Phase 1 (Parallel):
  T1 [P], T2 [P]

Phase 2 (Partially parallel — after Phase 1):
  T1 done → T3 [P], T4 [P]  (launch together)
  T2 done → T5 [P]           (launch together with T3, T4)
  T3+T2 done → T6            (sequential — must match T3)

Phase 3 (Partially parallel — after Phase 2):
  T1 done → T7 [P], T8 [P]  (can overlap Phase 2 once T1 is done)
  T2 done → T9 [P]           (same)
  T7+T2 done → T10           (sequential — must match T7)

Phase 4 (Sequential):
  T7+T10 done → T11

Phase 5 (Parallel — after T11):
  T12 [P], T13 [P], T14 [P]

Phase 6 (Sequential):
  All done → T15

Phase 7 (Sequential):
  T15 all ✅ → T16
```

---

## Task Granularity Check

| Task | Scope | Status |
|------|-------|--------|
| T1: konecty-data SKILL.md | 1 file | ✅ Granular |
| T2: konecty-meta SKILL.md | 1 file | ✅ Granular |
| T3: shared scripts in konecty-data | 2 cohesive files (both gated) | ✅ Granular |
| T4: data scripts in konecty-data | 5 verbatim-copy files, same operation type | ⚠️ OK — batch copy, no logic change |
| T5: meta scripts in konecty-meta | 11 verbatim-copy files, same operation type | ⚠️ OK — batch copy, no logic change |
| T6: shared scripts in konecty-meta | 2 cohesive files (gated copy from T3) | ✅ Granular |
| T7: gated refs in konecty-data | 2 cohesive files (both gated) | ✅ Granular |
| T8: operation refs in konecty-data | 5 files, same consolidation pattern | ⚠️ OK — batch consolidation |
| T9: operation refs in konecty-meta | 11 files, same consolidation pattern | ⚠️ OK — batch consolidation |
| T10: gated refs in konecty-meta | 2 cohesive files (gated copy from T7) | ✅ Granular |
| T11: shared-files.txt in both | 2 identical files | ✅ Granular |
| T12: .githooks/pre-commit | 1 file | ✅ Granular |
| T13: check-shared-files.yml | 1 file | ✅ Granular |
| T14: Makefile | 1 file | ✅ Granular |
| T15: migration audit | 1 logical operation (produce audit table) | ✅ Granular |
| T16: delete 18 dirs + update CLAUDE.md | 1 atomic commit, bounded scope | ✅ Granular |

**Note on ⚠️ tasks**: T4, T5, T8, T9 batch multiple files of the same type. Each file within is a straight copy (T4, T5) or a same-pattern consolidation (T8, T9). Splitting further would produce 28 additional micro-tasks with no meaningful isolation gain — the batch is cohesive and testable as a unit.

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
|------|------------------------|---------------|--------|
| T1 | None | — | ✅ Match |
| T2 | None | — | ✅ Match |
| T3 | T1 | T1 → T3 | ✅ Match |
| T4 | T1 | T1 → T4 | ✅ Match |
| T5 | T2 | T2 → T5 | ✅ Match |
| T6 | T2, T3 | T3+T2 → T6 | ✅ Match |
| T7 | T1 | T1 → T7 | ✅ Match |
| T8 | T1 | T1 → T8 | ✅ Match |
| T9 | T2 | T2 → T9 | ✅ Match |
| T10 | T2, T7 | T7+T2 → T10 | ✅ Match |
| T11 | T7, T10 | T7+T10 → T11 | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | T11 | T11 → T13 | ✅ Match |
| T14 | T11 | T11 → T14 | ✅ Match |
| T15 | T1–T14 | All → T15 | ✅ Match |
| T16 | T15 | T15 → T16 | ✅ Match |

No parallel tasks depend on each other within the same phase. ✅

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
|------|------------------------------|-----------------|-----------|--------|
| T1 | SKILL.md frontmatter | schema validation (gh skill --dry-run) | skill validation gate | ✅ OK |
| T2 | SKILL.md frontmatter | schema validation | skill validation gate | ✅ OK |
| T3 | Python scripts | none (no automated tests) | none | ✅ OK |
| T4 | Python scripts | none | none | ✅ OK |
| T5 | Python scripts | none | none | ✅ OK |
| T6 | Python scripts | none | none | ✅ OK |
| T7 | Markdown reference files | none | none (manual review) | ✅ OK |
| T8 | Markdown reference files | none | none (manual review) | ✅ OK |
| T9 | Markdown reference files | none | none (manual review) | ✅ OK |
| T10 | Markdown reference files | none | none | ✅ OK |
| T11 | shared-files.txt | none | none (diff gate) | ✅ OK |
| T12 | Shell script (hook) | none | none (manual execution) | ✅ OK |
| T13 | GitHub Actions YAML | none | none (YAML validation) | ✅ OK |
| T14 | Makefile | none | none (manual execution) | ✅ OK |
| T15 | Audit table (markdown) | none | none | ✅ OK |
| T16 | File deletions + CLAUDE.md edit | none | none | ✅ OK |

All tasks pass test co-location validation. ✅

---

## Audit Results

_Populated by T15 — 2026-05-19. All 18 original skills covered. Zero missing entries._

| Original Skill | Operation | Covered By | Reference File | Script | Status |
|----------------|-----------|------------|----------------|--------|--------|
| konecty-session | auth (OTP flow) | konecty-data, konecty-meta | references/auth.md [GATED] | scripts/auth.py [GATED] | ✅ Covered |
| konecty-modules | field discovery | konecty-data, konecty-meta | references/field-discovery.md [GATED] | scripts/modules.py [GATED] | ✅ Covered |
| konecty-find | find / search / SQL | konecty-data | references/find.md | scripts/find.py | ✅ Covered |
| konecty-create | create records | konecty-data | references/create.md | scripts/create.py | ✅ Covered |
| konecty-update | update records | konecty-data | references/update.md | scripts/update.py | ✅ Covered |
| konecty-delete | delete records | konecty-data | references/delete.md | scripts/delete.py | ✅ Covered |
| konecty-upload | file upload/list/delete | konecty-data | references/upload.md | scripts/upload.py | ✅ Covered |
| konecty-meta-read | read any MetaObject | konecty-meta | references/read.md | scripts/meta_read.py | ✅ Covered |
| konecty-meta-document | CRUD document schema | konecty-meta | references/document.md | scripts/meta_document.py | ✅ Covered |
| konecty-meta-list | CRUD list metas | konecty-meta | references/list.md | scripts/meta_list.py | ✅ Covered |
| konecty-meta-view | CRUD view/FormSchema | konecty-meta | references/view.md | scripts/meta_view.py | ✅ Covered |
| konecty-meta-access | CRUD access profiles | konecty-meta | references/access.md | scripts/meta_access.py | ✅ Covered |
| konecty-meta-pivot | CRUD pivot metas | konecty-meta | references/pivot.md | scripts/meta_pivot.py | ✅ Covered |
| konecty-meta-hook | generate/manage hooks | konecty-meta | references/hook.md | scripts/meta_hook.py | ✅ Covered |
| konecty-meta-namespace | tenant global config | konecty-meta | references/namespace.md | scripts/meta_namespace.py | ✅ Covered |
| konecty-meta-doctor | validate meta integrity | konecty-meta | references/doctor.md | scripts/meta_doctor.py | ✅ Covered |
| konecty-meta-sync | sync repo ↔ database | konecty-meta | references/sync.md | scripts/meta_sync.py | ✅ Covered |
| konecty-meta-remove | full-module deletion | konecty-meta | references/remove.md | scripts/meta_remove.py | ✅ Covered |
