# konecty-dev Tasks

**Design**: `.specs/features/konecty-dev/design.md`
**Spec**: `.specs/features/konecty-dev/spec.md`
**Status**: Not started

> Execution decisions: Phase 2 (the reference docs) runs as **parallel Sonnet subagents** — each doc is
> independent once the surface map (design §3) is fixed. No MCPs (native tools only). `skill-creator` used
> in T11 (triggering eval), `copywriting` optional in T2 (description polish).

---

## Testing approach (advisory skill)

`konecty-dev` ships **no scripts** and makes **no live calls** (D1), so the e2e Docker harness and the
shared-files invariant do **not** apply (D8/D11). Verification is proportional:

- **Validate gate (`make validate`)**: `gh skill publish --dry-run` on `konecty-dev` — validates `SKILL.md` against the agentskills.io spec. The one blocking automated gate.
- **Authoring verification**: each code example checked by hand against the pinned SDKs (Python `2.0.3`, TS `1.0.0`) and the REST contract mined in design §3. No CI compile harness (D11).
- **Triggering eval (`skill-creator`)**: confirms the D3 boundary — "build an integration" → konecty-dev; "buscar contatos" → konecty-data.
- **Sanitization grep (gate)**: `grep -ri` over the tracked tree for the known client-name list (kept in `SOURCES.local.md`) returns **zero** matches (D13).
- **Completion gate**: `make check` + `make audit` (intelligence + security), as for any change.

---

## Execution Plan

### Phase 1: Skeleton (Sequential)

```
T1 (scaffold SKILL.md + references/ stubs + surface map frozen)
```

### Phase 2: Reference docs (Parallel — each depends only on T1)

```
        ┌→ T2 SKILL.md (description + trigger table + cascade)   [P]
        ├→ T3 getting-started.md   [P]
        ├→ T4 auth-for-code.md     [P]
T1 ─────┼→ T5 python-sdk.md        [P]
        ├→ T6 typescript-sdk.md    [P]
        ├→ T7 rest-api.md          [P]
        ├→ T8 filters.md           [P]
        ├→ T9 recipes.md           [P]
        └→ T10 hooks.md            [P]
```

### Phase 3: Validation & docs (Sequential)

```
T2..T10 ──→ T11 (triggering eval + cross-link check) ──→ T12 (ADR status + changelog) ──→ T13 (completion gate: validate + sanitization grep + audit)
```

---

## Task Breakdown

### T1: Scaffold the skill + freeze the surface map

**What**: Create `skills/konecty-dev/` with `SKILL.md` (frontmatter placeholder) and `references/` containing all 8 files as stubs whose headings match design §4. Embed the design §3 surface table into `rest-api.md`/SDK stubs as the agreed contract so parallel authors don't diverge.
**Where**: `skills/konecty-dev/SKILL.md`, `skills/konecty-dev/references/{getting-started,auth-for-code,python-sdk,typescript-sdk,rest-api,filters,recipes,hooks}.md`
**Depends on**: None
**Reuses**: `template/SKILL.md`; reference-doc shape from `konecty-data`/`konecty-meta`
**Requirement**: G1–G5, NFR1, NFR2

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `skills/konecty-dev/SKILL.md` exists with placeholder frontmatter and the trigger-table heading
- [ ] All 8 `references/*.md` exist with the section headings from design §4 (no body yet)
- [ ] No `scripts/` folder, no `shared-files.txt` (D8 — verify it stays out of `shared-files.txt` in both other skills)
- [ ] Surface map (design §3) pasted as a comment/section into the SDK + REST stubs as the frozen contract

**Tests**: none
**Gate**: `make lint` (no-op — no scripts) + tree exists
**Commit**: `feat(konecty-dev): scaffold advisory skill + reference stubs`

---

### T2: `SKILL.md` — description, trigger table, decision cascade [P]

**What**: Write the lean router: bilingual `description` (design §6), the trigger→reference table (pt-BR + EN phrases, mirroring existing skills), the SDK→REST cascade (design §5), and prerequisites (a Konecty URL + service-account token).
**Where**: `skills/konecty-dev/SKILL.md`
**Depends on**: T1
**Reuses**: `konecty-data`/`konecty-meta` SKILL.md format; design §5/§6
**Requirement**: G5, D3, D12, NFR1

**Tools**: MCP NONE · Skill `copywriting` (optional, description polish)

**Done when**:
- [ ] `description` < 1024 chars, no angle brackets, bilingual triggers, explicit "Do NOT use" → konecty-data/konecty-meta (D3/D12)
- [ ] Trigger table routes to all 8 references with pt-BR + EN phrases
- [ ] Decision cascade (SDK → native HTTP → REST; hooks aside) printed
- [ ] `SKILL.md` under ~300 lines (NFR1)

**Tests**: none
**Gate**: `make validate`
**Commit**: `feat(konecty-dev): SKILL.md router (description, triggers, cascade)`

---

### T3: `getting-started.md` — track choice + first client [P]

**What**: Track-selection flowchart, install commands (pinned), first client in Python + TS, a `curl` smoke call; link onward.
**Where**: `skills/konecty-dev/references/getting-started.md`
**Depends on**: T1
**Reuses**: design §4.1, §5
**Requirement**: G1, G3

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] Pinned installs (`konecty_sdk_python==2.0.3`, `@konecty/sdk@1.0.0`)
- [ ] First-client snippet (Python sync+async, TS) + one `curl` call, all env-token based
- [ ] Links to auth-for-code.md and the three track docs
- [ ] Examples use generic modules only (D10)

**Tests**: authoring verification vs pinned SDKs
**Gate**: example-review
**Commit**: `docs(konecty-dev): getting-started reference`

---

### T4: `auth-for-code.md` — service-account token + security [P]

**What**: Document the token model and secure handling per design §4.2 / D6.
**Where**: `skills/konecty-dev/references/auth-for-code.md`
**Depends on**: T1
**Reuses**: design §4.2; STATE spike (strict-CORS, raw password)
**Requirement**: G1, D6, NFR5

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `authId` via `POST /rest/auth/login` shown (Python, TS, curl); `authId` = `Authorization` value
- [ ] Env/secret-manager storage, rotation, least-privilege, never-hardcode/commit
- [ ] `~/.konecty/.env` flagged as dev-only shortcut, not production
- [ ] `Sec-Fetch-Site: none` note for `/rest/auth/*`

**Tests**: authoring verification
**Gate**: example-review
**Commit**: `docs(konecty-dev): auth-for-code reference`

---

### T5: `python-sdk.md` — pinned 2.0.3 + gaps [P]

**What**: Curated Python SDK guide per design §4.3, with the "Gaps → REST" section (history, lookup, menu/form/list-view).
**Where**: `skills/konecty-dev/references/python-sdk.md`
**Depends on**: T1
**Reuses**: design §3/§4.3; `konecty-sdk-python/docs/api.md` (pointer only)
**Requirement**: G1, G2, G3, D5, D7

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] Version header + upstream pointer (D7)
- [ ] Client init (sync+async), find/find_one/create/update_one/delete_one, query json/sql, file up/download, streaming — verified vs 2.0.3
- [ ] "Gaps → REST" section links to the matching rest-api.md anchors (D5)
- [ ] Filters delegated to filters.md, auth to auth-for-code.md (no restating)

**Tests**: authoring verification vs 2.0.3
**Gate**: example-review
**Commit**: `docs(konecty-dev): python-sdk reference`

---

### T6: `typescript-sdk.md` — pinned 1.0.0 + gaps [P]

**What**: Curated TS/JS SDK guide per design §4.4, with the "Gaps → REST" for client-level file upload.
**Where**: `skills/konecty-dev/references/typescript-sdk.md`
**Depends on**: T1
**Reuses**: design §3/§4.4; `konecty-sdk/docs/api.md` + `FilesManager.md` (pointer only)
**Requirement**: G1, G2, G3, D5, D7

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] Version header + upstream pointer (D7)
- [ ] Client init `{endpoint, accessKey}`, find/create/update/delete, query json/sql, download, getHistory/getMenu/lookup — verified vs 1.0.0
- [ ] "Gaps → REST": file upload via `FilesManager` or REST (D5)
- [ ] Filters/auth delegated (no restating)

**Tests**: authoring verification vs 1.0.0
**Gate**: example-review
**Commit**: `docs(konecty-dev): typescript-sdk reference`

---

### T7: `rest-api.md` — agnostic complete track [P]

**What**: The complete REST reference per design §4.5, `curl` examples, the no-SDK and SDK-fallback target.
**Where**: `skills/konecty-dev/references/rest-api.md`
**Depends on**: T1
**Reuses**: design §3; server contract mined from `Konecty/src/server/routes/rest/*`
**Requirement**: G2, D4

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] Auth header, `success`/error envelope, status codes documented
- [ ] Data (find GET+POST, by-id, create, update, delete), query (json+sql w/ NDJSON `_meta`), file (upload/download/delete), auth endpoints — each with `curl`
- [ ] Pagination/sorting/field-selection conventions; anchors for the SDK "Gaps → REST" links
- [ ] Links to filters.md

**Tests**: authoring verification vs server contract
**Gate**: example-review
**Commit**: `docs(konecty-dev): rest-api agnostic reference`

---

### T8: `filters.md` — shared filter language [P]

**What**: Single home for the filter language per design §4.6, referenced by all three tracks.
**Where**: `skills/konecty-dev/references/filters.md`
**Depends on**: T1
**Reuses**: `Konecty/src/imports/model/Filter.ts`; konecty-data `find.md` operator list
**Requirement**: G1, D3

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `{match, conditions[{term,operator,value}], filters, textSearch}` documented
- [ ] All operators with one worked example each; nested groups; lookup `term: "field._id"`; cross-module `relations` shape
- [ ] No SDK/auth restating (links out)

**Tests**: authoring verification
**Gate**: example-review
**Commit**: `docs(konecty-dev): filters reference`

---

### T9: `recipes.md` — end-to-end patterns [P]

**What**: Composed patterns per design §4.7 (incremental sync, volume stream export, file attach/replace, cross-module aggregators, retry/backoff/429, KPI/graph/pivot).
**Where**: `skills/konecty-dev/references/recipes.md`
**Depends on**: T1
**Reuses**: design §3/§4.7
**Requirement**: G1, G2

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] ≥5 recipes, each SDK-first with REST fallback noted where relevant
- [ ] Robust-client recipe covers retry/backoff, 429, timeout, error-envelope parsing
- [ ] Generic modules only (D10); links to track docs rather than restating basics

**Tests**: authoring verification
**Gate**: example-review
**Commit**: `docs(konecty-dev): recipes reference`

---

### T10: `hooks.md` — write hook logic [P]

**What**: The 4 hook types per design §4.8 / D9 — purpose, lifecycle, sandbox vars, transaction boundary, 2–3 generic examples; closes pointing to konecty-meta.
**Where**: `skills/konecty-dev/references/hooks.md`
**Depends on**: T1
**Reuses**: `Konecty/src/imports/data/scripts.js`, `docs/{en,pt-BR}/hooks.md`, Konecty ADR-0005; **patterns** (not content) from `reference-metas` per ADR-0005
**Requirement**: G4, D9, D10, D13

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] Each type: field name, when it fires, purpose, variable table, return contract, transaction boundary
- [ ] `node:vm` sandbox note; delete runs none; `changeUser*` only if `changeUserRunHooks===true`
- [ ] Lifecycle diagram (create/update order)
- [ ] 2–3 examples — generic modules, invented logic, **zero** client-derived content (sanitization checklist applied)
- [ ] Closes linking to konecty-meta to validate/version/apply (D9)

**Tests**: authoring verification vs server contract; sanitization checklist
**Gate**: example-review + sanitization
**Commit**: `docs(konecty-dev): hooks reference`

---

### T11: Triggering eval + cross-link check

**What**: Run a triggering eval (skill-creator) for the D3 boundary; verify all cross-links resolve and no doc restates filters/auth.
**Where**: eval artifacts (not shipped); fixes across `skills/konecty-dev/**`
**Depends on**: T2–T10
**Reuses**: `skill-creator` eval workflow
**Requirement**: G5, D3, D11

**Tools**: MCP NONE · Skill `skill-creator`

**Done when**:
- [ ] Eval: "build an integration / use the SDK / write a hook" select konecty-dev; "buscar/criar/listar dados" select konecty-data; schema/metadata select konecty-meta
- [ ] Every `references/` cross-link target exists; filters/auth documented once (DRY check)
- [ ] Any misfires fixed by tightening the description

**Tests**: triggering eval
**Gate**: eval pass
**Commit**: `test(konecty-dev): triggering eval + cross-link fixes`

---

### T12: ADR status + changelog

**What**: Confirm ADR-0005 reflects shipped reality; add the changelog entry (new skill = structural change per the changelog rule).
**Where**: `docs/adr/0005-reference-examples-patterns-not-content.md` (status), `docs/changelog/2026-06-17_konecty-dev-skill.md`, `docs/changelog/README.md`
**Depends on**: T2–T10
**Reuses**: changelog format; ADR-0004 precedent
**Requirement**: repo changelog rule

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] New changelog entry + row in `docs/changelog/README.md`
- [ ] ADR-0005 status accurate
- [ ] `README.md` skills map mentions the third skill (if it enumerates skills)

**Tests**: none
**Gate**: `make check`
**Commit**: `docs(konecty-dev): ADR-0005 + changelog for the new skill`

---

### T13: Completion gate

**What**: Run the full gate before declaring done / opening the PR.
**Where**: whole tree
**Depends on**: T11, T12
**Reuses**: `make validate`, `make check`, `make audit`; sanitization grep (D13)
**Requirement**: G6, D11, D13

**Tools**: MCP NONE · Skill NONE

**Done when**:
- [ ] `make validate` passes on konecty-dev
- [ ] Sanitization: `grep -ri` over tracked tree for the client-name list (from `SOURCES.local.md`) = **0** matches (D13)
- [ ] `make check` + `make audit` (intelligence + security) = no `fail`
- [ ] Branch ready for PR

**Tests**: gate suite
**Gate**: validate + sanitization + audit
**Commit**: (no code) — PR open

---

## Traceability

| Requirement | Tasks |
|-------------|-------|
| G1 (pick track, write code) | T2, T3, T4, T5, T6, T8, T9 |
| G2 (REST first-class + fallback) | T5, T6, T7, T9 |
| G3 (self-contained, pinned) | T3, T5, T6 |
| G4 (hooks) | T10 |
| G5 (boundary/triggers) | T2, T11 |
| G6 (no client leakage) | T1, T10, T13 |
| D5 (gaps→REST) | T5, T6, T7 |
| D8 (out of shared-files) | T1 |
| D9 (hooks cut) | T10 |
| D10/D13 (patterns-not-content) | T10, T13 |
| D11 (verification) | T2(validate), T11(eval), T13(gate) |
| D12 (language) | T2 |
