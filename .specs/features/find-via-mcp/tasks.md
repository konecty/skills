# Find via MCP — Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow
and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for
the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user — do not proceed without it.**

---

**Design**: `.specs/features/find-via-mcp/design.md`
**Status**: Draft

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec — confirm before Execute. Guidelines found:
> `AGENTS.md` (stdlib-only, offline `make check`, e2e ≥90% gate), `pytest.ini` (markers `mock`/`live`),
> `.coveragerc` (source = the two skills' `scripts/`, `--fail-under=90`), Makefile e2e targets,
> existing tests `tests/e2e/test_data_mock.py`, `tests/e2e/mock_konecty.py`, `tests/e2e/test_coverage_closers.py`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| `scripts/mcp_client.py` (transport/domain logic) | unit | All branches; 1:1 to spec ACs; every listed edge case (SSE/JSON parse, 3 typed errors, malformed SSE) | `tests/e2e/test_mcp_client.py` (new) | `make e2e-run` (quick: `uv run --with pytest --with coverage python -m pytest tests/e2e/test_mcp_client.py -q`) |
| `scripts/find.py` dispatcher + `_tool_*`/`_adapt_*` (skill script logic) | mock e2e | Happy path + every fallback-matrix row + output parity + malformed-filter reject | `tests/e2e/test_data_mock.py` (extend) | `make e2e-run`; coverage gate `make e2e-cov` |
| `tests/e2e/mock_konecty.py` `/mcp` route (test infra) | none | — (must keep the mock self-test green) | `tests/e2e/mock_konecty.py` | `make e2e-run` |
| `references/find.md`, `SKILL.md` (docs) | none | — (build / cross-link gate only) | `skills/konecty-data/**` | `make check` + `make validate` |

**Coverage gate:** the whole feature must keep total line coverage **≥ 90%** (`make e2e-cov`,
`--fail-under=90`). New `mcp_client.py` and every dispatcher branch are counted.

## Gate Check Commands

> Generated from codebase — confirm before Execute.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After a task with unit/mock tests only | `make check` (offline byte-compile + shared-files guard + installer) **and** the task's targeted `uv run ... pytest <file> -q` |
| Full | After a task that adds mock e2e tests | `make e2e-run` (mock + live-skip + security + inference) |
| Build | After a phase / coverage-sensitive task | `make e2e-cov` (≥90% gate) + `make check` |

---

## Execution Plan

Phases are ordered and run sequentially — each phase completes before the next begins, and tasks within a
phase execute in order.

### Phase 1: MCP client foundation (stdlib, unit-tested standalone)

```
T1 → T2
```

### Phase 2: Test harness + dispatcher + `find` (P1 vertical slice)

```
T3 → T4 → T5 → T6
```

### Phase 3: `query` + `sql` via MCP (P2)

```
T7 → T8
```

### Phase 4: Docs, coverage, gate

```
T9 → T10
```

---

## Task Breakdown

### T1: `mcp_client.py` — SSE parser + typed errors

**What**: Create `scripts/mcp_client.py` with `parse_sse(body: bytes) -> list[dict]` (split `\n\n` frames,
concatenate `data:` lines per frame, JSON-parse each) and the three typed error classes
`McpHttpError(status, body)`, `McpTransportError`, `McpToolError(code, message, details)`.
**Where**: `skills/konecty-data/scripts/mcp_client.py` (new)
**Depends on**: None
**Reuses**: header/error idioms from `skills/konecty-data/scripts/find.py`
**Requirement**: FMCP-17 (SSE parse), FMCP-18 (typed errors)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [x] `parse_sse` extracts the JSON-RPC message from a canned single-frame SSE body and from a multi-frame
      body (priming + result); returns `[]`/raises cleanly on a truncated/malformed frame.
- [x] The three error classes exist; `McpHttpError` carries `.status`.
- [x] Stdlib only (`json`, `urllib`); byte-compiles.
- [x] Unit tests written in `tests/e2e/test_mcp_client.py`: valid single-frame, multi-frame, malformed → error.
- [x] Gate passes: `make check` + `uv run --with pytest --with coverage python -m pytest tests/e2e/test_mcp_client.py -q`
- [x] Test count: ≥4 tests pass (9 pass, no silent deletions).

**Tests**: unit · **Gate**: quick
**Commit**: `feat(konecty-data): add stdlib MCP SSE parser + typed errors`
**Status**: ✅ DONE (077b1e5)

---

### T2: `mcp_client.py` — `call_tool` over stateless Streamable HTTP

**What**: Add `call_tool(base_url, token, name, arguments, *, timeout=30) -> dict` — POST a JSON-RPC 2.0
`tools/call` to `{base_url}/mcp` with headers `Accept: application/json, text/event-stream`,
`Content-Type: application/json`, `Authorization: Bearer <token>`; body
`{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":name,"arguments":{**arguments,"authTokenId":token}}}`;
read the response, parse SSE (or JSON) via T1, and return the tool `result`; raise `McpHttpError` on non-2xx,
`McpTransportError` on connection/timeout/bad-SSE, `McpToolError` on JSON-RPC `error` or `result.isError`.
**Where**: `skills/konecty-data/scripts/mcp_client.py` (modify)
**Depends on**: T1
**Reuses**: `urllib.request` pattern from `find.py:_do_request`
**Requirement**: FMCP-16 (envelope + Accept both + auth header), FMCP-18 (error branching), FMCP-03 (Bearer)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [x] Sends both Accept types, `Bearer` header, and `authTokenId` in arguments (asserted against a canned request).
- [x] Extracts the same `result` object from a 200 SSE body and a 200 JSON body (defensive JSON path).
- [x] 200 with JSON-RPC `error` → `McpToolError`; 200 `result.isError` → `McpToolError`; non-2xx → `McpHttpError(.status)`; `URLError`/timeout → `McpTransportError`.
- [x] Stdlib only; byte-compiles.
- [x] Unit tests in `tests/e2e/test_mcp_client.py` cover all branches (canned SSE/JSON + each error).
- [x] Gate passes: `make check` + `uv run --with pytest --with coverage python -m pytest tests/e2e/test_mcp_client.py -q`
- [x] Test count: ≥6 additional tests pass (11 new).

**Tests**: unit · **Gate**: quick
**Commit**: `feat(konecty-data): add MCP tools/call client (SSE, Bearer, typed errors)`
**Status**: ✅ DONE (711331b)

---

### T3: MockKonecty `/mcp` route (SSE + fault injection)

**What**: Extend `MockKonecty` with a `POST /mcp` route returning an **SSE** `_FakeResponse`
(`content_type="text/event-stream"`) that wraps a `records_find`/`query_json`/`query_sql` result in
`structuredContent`, dispatched by the `params.name`; plus sentinel-driven fault injection
(document/sentinel → `403 mcp_access_denied`, `404`, `429`, or `URLError`) so dispatcher tests can drive each
fallback branch. GET/DELETE `/mcp` → 405.
**Where**: `tests/e2e/mock_konecty.py` (modify)
**Depends on**: T2 (must mirror the client's request/response contract)
**Reuses**: `_FakeResponse`, `_ndjson_response`/`_json_response` helpers, `_match_filter`, `_project`
**Requirement**: test infra for FMCP-01,07,08,09,11,12,13,14

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [x] `POST /mcp` with `records_find` returns a 200 SSE frame whose data is `{"jsonrpc":"2.0","id":1,"result":{"structuredContent":{"records":[...],"total":N,"pagination":{...}}}}`, filtered/projected via the existing helpers.
- [x] `query_json`/`query_sql` return `structuredContent {records, meta, total}`.
- [x] Fault sentinels produce 403/404/429/URLError (+ badsse/toolerror); GET/DELETE → 405.
- [x] The mock self-test and full suite stay green.
- [x] Gate passes: `make e2e-run` (496 passed, 9 skipped).
- [x] Test count: existing suite green + 12 smoke tests asserting the SSE route + faults.

**Tests**: none (test infra) · **Gate**: full
**Commit**: `test(e2e): add MockKonecty /mcp SSE route + fault injection`
**Status**: ✅ DONE (b5f03a5)

---

### T4: Refactor `find.py` — REST bodies become fallbacks

**What**: Rename the current `cmd_find`/`cmd_query`/`cmd_sql` bodies to `_rest_find`/`_rest_query`/`_rest_sql`
(pure move — no behavior change), leaving `cmd_*` as thin shims for now. This isolates the REST path as the
fallback implementation before the dispatcher wraps it.
**Where**: `skills/konecty-data/scripts/find.py` (modify)
**Depends on**: None (independent of T1-T3; scheduled here to precede the dispatcher)
**Reuses**: the existing `cmd_*` implementations verbatim
**Requirement**: enabling (no new AC)

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [x] `_rest_find/_rest_query/_rest_sql` contain the former `cmd_*` logic unchanged.
- [x] All existing `find`/`query`/`sql` mock tests still pass unchanged (behavior identical).
- [x] Byte-compiles; stdlib only.
- [x] Gate passes: `make check` + `make e2e-run` (496 passed).
- [x] Test count: existing data-mock suite green (no deletions).

**Tests**: mock (existing, unchanged) · **Gate**: full
**Commit**: `refactor(konecty-data): extract REST find/query/sql as fallback fns`
**Status**: ✅ DONE (baace3e)

---

### T5: Dispatcher core + fallback matrix

**What**: Add `_mcp_enabled()` (`KONECTY_MCP` env: `1`/unset=on, `0`=off, `only`=strict) + module-level
`_mcp_disabled` flag, and `_dispatch(mcp_call, rest_call)` implementing the matrix: 404→REST silent;
403/429/5xx/conn/timeout/bad-SSE→REST + short notice emitted **first** on stderr; **429 additionally sets
`_mcp_disabled`**; 401→surface auth error (no fallback); `McpToolError`→surface (no fallback); `only`+fail→
surface; MCP+REST both fail→surface REST error, non-zero.
**Where**: `skills/konecty-data/scripts/find.py` (modify)
**Depends on**: T2, T3, T4
**Reuses**: `mcp_client` errors, `_rest_*` from T4
**Requirement**: FMCP-06, FMCP-07, FMCP-08, FMCP-09, FMCP-11, FMCP-12

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [x] Mock tests for each matrix row: 404 (silent fallback), 403 (fallback + notice-first), 429 (fallback + notice + subsequent call skips MCP), 401 (surface, exit≠0, no REST), `McpToolError` (surface, no REST), both-fail (REST error surfaced, exit≠0), `KONECTY_MCP=0` (REST only), `KONECTY_MCP=only`+fail (surface, no fallback).
- [x] Notice text is one short line on stderr, before stdout records; stdout stays a clean records array.
- [x] Gate passes: `make e2e-run` (509 passed).
- [x] Test count: ≥8 new mock tests pass (13 new).

**Tests**: mock · **Gate**: full
**Commit**: `feat(konecty-data): MCP-first dispatcher with REST fallback matrix`
**Status**: ✅ DONE (08885f5)

---

### T6: `find` via `records_find` + output adapter

**What**: Add `_tool_find(args)` (map `document`/`--filter`/`--fields`/`--sort`/`--limit`/`--start` →
`records_find` arguments) and `_adapt_mcp(result)` (`structuredContent.records`→stdout via `_print_results`,
`total`→`# Total/Returned` stderr); wire the `find` subcommand through `_dispatch(_tool_find, _rest_find)`.
**Where**: `skills/konecty-data/scripts/find.py` (modify)
**Depends on**: T5
**Reuses**: `_parse_json_arg`, `_parse_sort`, `_print_results`
**Requirement**: FMCP-01, FMCP-02, FMCP-03, FMCP-04, FMCP-05, FMCP-10

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [x] `find Contact` over the mock hits `records_find`; stdout records + stderr total match the REST path (parity).
- [x] `--filter` passes through as canonical KonFilter; malformed/Mongo JSON is rejected locally before any call.
- [x] `--sort` normalized to `{property, direction:UPPER}`; `--fields` csv; `--limit -1` passed through.
- [x] On MCP 403, `find` still returns records via REST fallback with the notice.
- [x] Gate passes: `make e2e-run` (519 passed).
- [x] Test count: ≥6 new mock tests pass (10 new; realigned 1 stale coverage closer).

**Tests**: mock · **Gate**: full
**Commit**: `feat(konecty-data): route find through MCP records_find`
**Status**: ✅ DONE (aed9756)

---

### T7: `query` via `query_json` + `_meta` reconstruction

**What**: Add `_tool_query(args)` (→ `query_json` with document/filter/relations/limit) and
`_adapt_mcp_query(result)` reconstructing the REST-compatible `_meta` line as
`{"success": true, **meta, "total": total}`; wire `query` through `_dispatch(_tool_query, _rest_query)`.
**Where**: `skills/konecty-data/scripts/find.py` (modify)
**Depends on**: T6
**Reuses**: `_dispatch`, `_adapt_mcp`, `_parse_json_arg`
**Requirement**: FMCP-13, FMCP-15

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `query Contact --relations …` hits `query_json`; rows on stdout match REST; the `_meta` line equals the REST shape (`success`+`total` folded in).
- [ ] Default `--limit 1000` and `--include-meta`/`--no-total` semantics preserved.
- [ ] 403 → REST fallback with notice.
- [ ] Gate passes: `make e2e-run`
- [ ] Test count: ≥4 new mock tests pass.

**Tests**: mock · **Gate**: full
**Commit**: `feat(konecty-data): route query through MCP query_json`

---

### T8: `sql` via `query_sql`

**What**: Add `_tool_sql(args)` (→ `query_sql` with the SQL string + include-meta/total options); wire `sql`
through `_dispatch(_tool_sql, _rest_sql)`, reusing `_adapt_mcp_query` for the `_meta` line.
**Where**: `skills/konecty-data/scripts/find.py` (modify)
**Depends on**: T7
**Reuses**: `_dispatch`, `_adapt_mcp_query`
**Requirement**: FMCP-14, FMCP-15

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `sql "SELECT …"` hits `query_sql`; rows + `_meta` match REST.
- [ ] 403 → REST fallback with notice.
- [ ] Gate passes: `make e2e-run`
- [ ] Test count: ≥3 new mock tests pass.

**Tests**: mock · **Gate**: full
**Commit**: `feat(konecty-data): route sql through MCP query_sql`

---

### T9: Document the MCP path in `references/find.md` (+ SKILL.md pointer)

**What**: Add to `references/find.md`: MCP-first behavior + `Authorization: Bearer` auth, the `KONECTY_MCP`
env (`0`/`only`), the fallback notice, and a **"Known divergences"** section citing ADR-0008 (nested-filter
superset + `KONECTY_MCP=0` workaround) and the operational prerequisite (`mcpRoleIds` allowlist). Add a
one-line pointer in `SKILL.md` if the transport is user-visible.
**Where**: `skills/konecty-data/references/find.md` (modify), `skills/konecty-data/SKILL.md` (maybe)
**Depends on**: T8
**Reuses**: existing `references/find.md` structure
**Requirement**: FMCP-19 (divergence documented), doc for FMCP-08/12 behavior

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] "Known divergences" section documents the nested-filter case + workaround + ADR-0008 link.
- [ ] `KONECTY_MCP` env and Bearer auth documented; operational `mcpRoleIds` prerequisite noted.
- [ ] Gate passes: `make check` + `make validate` (SKILL.md still valid).
- [ ] No broken cross-links.

**Tests**: none (docs) · **Gate**: quick
**Commit**: `docs(konecty-data): document MCP-first find + known divergences`

---

### T10: Coverage gate + changelog + STATE

**What**: Ensure total coverage ≥90% (add coverage-closer tests in `tests/e2e/test_coverage_closers.py` if
any new branch is uncovered); add `docs/changelog/2026-07-11_find-via-mcp-impl.md` + README row; update
`.specs/project/STATE.md` (feature → EXECUTED) and flip requirement statuses in `spec.md`.
**Where**: `tests/e2e/test_coverage_closers.py` (maybe), `docs/changelog/*`, `.specs/**`
**Depends on**: T9
**Reuses**: existing coverage-closer pattern
**Requirement**: all (traceability closure) + repo changelog rule

**Tools**: MCP: NONE · Skill: NONE

**Done when**:
- [ ] `make e2e-cov` passes with `--fail-under=90` (report the actual %).
- [ ] Changelog entry + README row added; STATE updated; spec statuses → Verified.
- [ ] `make check` green; `make audit` shows no new `fail`.
- [ ] Test count: full suite green (report totals).

**Tests**: mock (closers if needed) · **Gate**: build
**Commit**: `chore(konecty-data): coverage gate + changelog + STATE for find-via-mcp`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3 → Phase 4

Phase 1:  T1 ──→ T2
Phase 2:  T3 ──→ T4 ──→ T5 ──→ T6
Phase 3:  T7 ──→ T8
Phase 4:  T9 ──→ T10
```

Execution is strictly sequential — one task at a time, in order.

---

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: SSE parser + error classes | 1 file, 2 cohesive concepts | ✅ Granular |
| T2: call_tool | 1 function | ✅ Granular |
| T3: mock /mcp route | 1 file (test infra) | ✅ Granular |
| T4: extract REST fns | 1 file, mechanical move | ✅ Granular |
| T5: dispatcher + matrix | 1 function + 2 helpers, cohesive | ✅ Granular |
| T6: find via records_find | 2 fns + wiring, one subcommand | ✅ Granular |
| T7: query via query_json | 2 fns + wiring, one subcommand | ✅ Granular |
| T8: sql via query_sql | 1 fn + wiring, one subcommand | ✅ Granular |
| T9: docs | reference + SKILL pointer | ✅ Granular |
| T10: coverage + changelog + STATE | closure task | ✅ Granular (cohesive closure) |

---

## Diagram-Definition Cross-Check

| Task | Depends On (body) | Diagram Shows | Status |
| ---- | ----------------- | ------------- | ------ |
| T1 | None | (start of P1) | ✅ Match |
| T2 | T1 | T1→T2 | ✅ Match |
| T3 | T2 | T2→T3 (P1→P2 boundary) | ✅ Match |
| T4 | None (ordered after T3) | T3→T4 | ✅ Match (no back-edge; sequential) |
| T5 | T2, T3, T4 | T4→T5 (+ P1 T2, T3 upstream) | ✅ Match |
| T6 | T5 | T5→T6 | ✅ Match |
| T7 | T6 | T6→T7 | ✅ Match |
| T8 | T7 | T7→T8 | ✅ Match |
| T9 | T8 | T8→T9 | ✅ Match |
| T10 | T9 | T9→T10 | ✅ Match |

All dependencies point backward or within phase. T4's "None" is a soft ordering (mechanical refactor) placed
before T5 which consumes it — no forward dependency.

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1 | `mcp_client.py` (transport logic) | unit | unit | ✅ OK |
| T2 | `mcp_client.py` (transport logic) | unit | unit | ✅ OK |
| T3 | `mock_konecty.py` (test infra) | none | none | ✅ OK |
| T4 | `find.py` (mechanical move; behavior unchanged) | mock e2e | mock (existing, unchanged) | ✅ OK (no new behavior; existing tests are the guard) |
| T5 | `find.py` dispatcher | mock e2e | mock | ✅ OK |
| T6 | `find.py` find path | mock e2e | mock | ✅ OK |
| T7 | `find.py` query path | mock e2e | mock | ✅ OK |
| T8 | `find.py` sql path | mock e2e | mock | ✅ OK |
| T9 | docs | none | none | ✅ OK |
| T10 | coverage closers + docs | mock (if new branch) | mock | ✅ OK |

No ❌ — safe to present.

---

## Requirement Coverage

| Requirement | Task(s) |
| ----------- | ------- |
| FMCP-01 | T6 | FMCP-02 | T6 | FMCP-03 | T2, T6 | FMCP-04 | T6 | FMCP-05 | T6 |
| FMCP-06 | T5 | FMCP-07 | T5 | FMCP-08 | T5 | FMCP-09 | T5 | FMCP-10 | T6 |
| FMCP-11 | T5 | FMCP-12 | T5 | FMCP-13 | T7 | FMCP-14 | T8 | FMCP-15 | T7, T8 |
| FMCP-16 | T2 | FMCP-17 | T1 | FMCP-18 | T1, T2 | FMCP-19 | T9 |

All 19 requirements mapped. (P3's former FMCP-20 removed in grilling.)
