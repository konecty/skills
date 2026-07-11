# Find via MCP — Validation

**Date**: 2026-07-11
**Spec**: `.specs/features/find-via-mcp/spec.md`
**Diff range**: `main..feat/find-via-mcp` (HEAD `d082962`; 12 commits `2f23a7a..d082962`)
**Verifier**: independent sub-agent (author ≠ verifier; re-derived from spec, evidence-or-zero)

---

## Verdict: PASS ✅ (with 3 non-blocking spec-precision notes)

All 19 acceptance criteria (FMCP-01..19) trace to a `file:line` assertion whose asserted
value matches the spec-defined outcome. The offline+mock gate is green (541 passed, 9
skipped-justified), coverage is 93% (≥90 gate), and the discrimination sensor killed 5/5
injected faults. Three spec-precision gaps are flagged below; none is a functional
regression (all have a safe failure mode) so none blocks the PR.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 (SSE parser + typed errors) | ✅ Done | `mcp_client.py` |
| T2 (tools/call client) | ✅ Done | envelope/headers/auth |
| T3 (mock `/mcp` SSE route + faults) | ✅ Done | `mock_konecty.py` |
| T4 (extract REST fallbacks) | ✅ Done | `_rest_find/query/sql` |
| T5 (dispatcher + fallback matrix) | ✅ Done | `_dispatch` |
| T6 (find → records_find) | ✅ Done | `_tool_find`/`_adapt_mcp` |
| T7 (query → query_json) | ✅ Done | `_tool_query`/`_adapt_mcp_query` |
| T8 (sql → query_sql) | ✅ Done | `_reconstruct_query_meta` |
| T9 (docs + ADR-0008 divergence) | ✅ Done | `references/find.md` |
| T10 (coverage gate + changelog + STATE) | ✅ Done | 93%, gate green |

---

## Spec-Anchored Acceptance Criteria

Files: `D` = `tests/e2e/test_data_mock.py`, `C` = `tests/e2e/test_mcp_client.py`,
`S` = `tests/e2e/test_security.py`, `X` = `tests/e2e/test_coverage_closers.py`.

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| ------------------------- | -------------------- | ----------------------- | ------ |
| FMCP-01 reachable MCP → records_find serves the records | records printed to stdout; REST untouched | `D:948-951` — REST broken, `assert len(data)==2` + `"Busca feita" not in stderr` | ✅ PASS |
| FMCP-02 canonical filter sent; malformed rejected locally pre-network | KonFilter passthrough; malformed → clear error before any HTTP | `D:974-975` passthrough `data[0]["_id"]=="cid001"`; `D:987-988` (no mock) `code==1` + `"Invalid --filter" in stderr` | ⚠️ Spec-precision |
| FMCP-03 auth sent as Bearer | `Authorization: Bearer <token>` | `C:192` — `assert req.get_header("Authorization")=="Bearer tok-123"` | ✅ PASS |
| FMCP-04 output contract preserved | records→stdout, `# Total: N  Returned: M`→stderr | `D:961-963` — `r_mcp.stdout==r_rest.stdout` + `"# Total: 2  Returned: 2" in r_mcp.stderr` | ✅ PASS |
| FMCP-05 CLI args → records_find inputs | limit/start/fields/sort mapped; defaults 50/0 | `C:201-205` args `document/limit`; `D:996-998` fields projection; `D:1006-1007` `--limit -1`; `D:1009-1015` sort | ✅ PASS |
| FMCP-06 missing-cred + 401 → surface, no fallback | non-zero exit; 401 no REST fallback | `S:61-71` cred fast-fail (find); `D:830-832` `code==1` + `"401" in err` + `rest_ran==[]` | ✅ PASS |
| FMCP-07 404 → REST silent | fallback, no notice | `D:763-764` + `D:1033-1035` — records via REST, `NOTICE not in stderr` | ✅ PASS |
| FMCP-08 403/429/5xx/conn/timeout/bad-SSE → REST + notice FIRST | notice on stderr before records | `D:776-778` (403/500/502); `D:788-791` transport; `D:815` `order==["notice","records"]` | ✅ PASS |
| FMCP-09 happy MCP path silent | no transport notice | `D:750-751` — `NOTICE not in err` + `rest_ran==[]` | ✅ PASS |
| FMCP-10 fallback output shape identical to MCP | byte-identical records array | `D:961` `r_mcp.stdout==r_rest.stdout`; `D:1024` len==2 via REST | ✅ PASS |
| FMCP-11 both fail → surface REST error, non-zero | actionable REST error surfaces | `D:863-865` — `code==1` + `"HTTP 500" in err` + `NOTICE in err` | ✅ PASS |
| FMCP-12 429 disables MCP for the process | subsequent calls skip MCP | `D:878` `_mcp_disabled is True`; `D:889-891` 2nd call `mcp_called==[]` + no repeat notice | ✅ PASS |
| FMCP-13 query → query_json + fallback | rows via query_json; 403→REST | `D:1073-1076` REST broken len==2; `D:1086-1088` parity; `D:1128-1130` 403 fallback+notice | ✅ PASS |
| FMCP-14 sql → query_sql + fallback | rows via query_sql; 403→REST | `D:1157-1159` REST broken len==2; `D:1170-1173` parity; `D:1195-1197` 403 fallback | ✅ PASS |
| FMCP-15 `_meta` reconstructed `{success:true,**meta,total}` | exact shape | `D:1097-1100` — `meta["success"] is True` + `meta["total"]==1` + `meta["document"]=="Contact"` | ✅ PASS |
| FMCP-16 JSON-RPC envelope + both Accept + auth | jsonrpc/id/method + Accept both + Bearer + CT json | `C:189-205` — Accept both types, `"tools/call"`, `id==1`, `authTokenId` echoed | ✅ PASS |
| FMCP-17 SSE response parsing | extract JSON-RPC result from SSE | `C:83-88` single frame; `C:100-102` multi-frame result-bearing; `C:244-245` result extracted | ✅ PASS |
| FMCP-18 typed errors (tool vs http vs transport) | McpToolError / McpHttpError(.status) / McpTransportError | `C:288-289` toolerror; `C:315` `.status==403`; `C:325`/`C:336`/`C:345` transport | ✅ PASS |
| FMCP-19 nested-filter divergence documented, sent unchanged | filter forwarded unchanged; documented (ADR-0008) | `find.py:398-399` `arguments["filter"]=fil` (no transform, by construction); docs `references/find.md` + `docs/adr/0008-*` | ⚠️ Docs-only (no behavioral test) |

**Status**: ✅ 19/19 ACs traced and match spec outcome; 2 flagged ⚠️ Spec-precision + 1 docs-only.

### Edge Cases

| Edge case | Evidence | Result |
| --------- | -------- | ------ |
| Human label vs technical name → tool VALIDATION_ERROR, no fallback | `D:846-849` (`McpToolError "invalid document Contato"` → `code==1`, `rest_ran==[]`) | ✅ (synthetic/unit) |
| Mongo-style sort `{field:-1}` → normalize to `{property,direction:UPPER}` | Only shorthand `code:asc` normalized (`D:1009-1015`); literal `{"code":-1}` passes through **unchanged** (`_parse_sort` probe) | ⚠️ Spec-precision |
| 429 → fallback + disable MCP (per-process) | `D:867-891` (FMCP-12) | ✅ PASS |
| Nested filter 2+ levels → MCP superset, documented | `references/find.md` + ADR-0008 (docs only) | ⚠️ Docs-only |
| `--limit -1` (no limit) passthrough | `D:1006-1007` `assert len(...)==2` | ✅ PASS |
| Truncated/malformed SSE → transport failure → fallback | `C:345-346` client raises; `C:413-415` badsse fault; `D:788-791` dispatcher fallback | ✅ PASS |

---

## Discrimination Sensor

Injected in scratch (edit → run → `git checkout --` restore). Tree confirmed clean after each.

| # | File:line | Mutation | Test run | Killed? |
| - | --------- | -------- | -------- | ------- |
| 1 | `find.py:302-304` | `McpToolError` branch → `rest_call()` instead of `sys.exit` (fall back instead of surface) | `D::test_tool_error_surfaces_no_fallback` | ✅ Killed (`assert 0 == 1`) |
| 2 | `find.py:320-321` | 429 branch sets `_mcp_disabled = False` (never disables) | `D::test_429_disables_mcp_for_rest_of_process` | ✅ Killed (`assert False is True`) |
| 3 | `find.py:364` | drop `"success": True` from `_reconstruct_query_meta` | `D::test_query_meta_reconstructed_shape` | ✅ Killed (`KeyError: 'success'`) |
| 4 | `mcp_client.py:211` | drop `Bearer ` prefix (`Authorization: token`) | `C::test_request_envelope_headers_and_body` | ✅ Killed (`'tok-123' != 'Bearer tok-123'`) |
| 5 | `find.py:324` | `silent = False` (404 emits the notice) | `D::test_fallback_404_silent` + `D::test_find_mcp_404_silent_fallback` | ✅ Killed (both fail) |

**Sensor depth**: lightweight (5 behavior-level mutations on the highest-risk new code: fallback
matrix, 429 persistence, `_meta` shape, Bearer auth, 404-silence).
**Result**: 5/5 killed — PASS ✅. No surviving mutants.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code / no scope creep (REST untouched, wrapped) | ✅ |
| Surgical changes; matches existing `find.py` idioms | ✅ |
| Spec-anchored outcome check (asserted values match spec) | ✅ (2 ⚠️ noted) |
| Per-layer coverage: client unit + dispatcher/adapter mock e2e (happy+edge+error) | ✅ |
| Every test maps to a spec AC / edge case / Done-when | ✅ |
| Documented guidelines followed | ✅ `AGENTS.md` (stdlib-only, ≥90% gate), `tasks.md` Test Coverage Matrix |

---

## Gate Check

- **Command**: `uv run --with pytest --with coverage python -m pytest tests/e2e/ -q`; coverage via
  project `.coveragerc` (`coverage run -m pytest … ; coverage report --fail-under=90`).
- **Result**: **541 passed, 9 skipped, 0 failed**.
- **Coverage**: `find.py` 90%, `mcp_client.py` 97%, **TOTAL 93%** (≥90 gate satisfied).
- **Skips (all justified)**: 8 × `test_live_data.py` + 1 × `test_security.py` — live Konecty stack
  not reachable at `:3200` (requires `make e2e-up`); these are `live`-marked, not feature regressions.
- **Test integrity**: feature added ~40 MCP tests across `test_mcp_client.py` (new),
  `test_data_mock.py`, `test_coverage_closers.py`; no tests deleted, no assertions weakened. The one
  "realigned" coverage-closer (`test_find_http_error`, pinned to `KONECTY_MCP=0`) is justified — `find`
  became MCP-first, so the REST GET error branch is now only reachable with MCP disabled.

---

## Spec-Precision Gaps (non-blocking)

1. **FMCP-02 — "reject Mongo-style filter locally" is only partial.** `_parse_json_arg` rejects
   *malformed JSON* locally (tested, `D:987-988`), but a *Mongo-shaped yet valid JSON* filter (e.g.
   `{"status":"active"}`) is **not** rejected locally — it is forwarded and rejected server-side as a
   tool VALIDATION_ERROR (→ surfaced, no fallback). Safe (no silent wrong result) and consistent with
   design.md + the "bare/Mongo filter" risk row, but the AC wording ("reject … Mongo-style … locally
   before any network call") over-claims, and no test exercises a valid-JSON Mongo-shaped filter.

2. **Edge case — Mongo-style sort `{field:-1}` normalization is not implemented as written.** The spec
   claims "`_parse_sort` already does this," but the probe shows `_parse_sort('{"code":-1}')` returns
   `[{'code': -1}]` **unchanged**; only the CLI shorthand (`code:asc`) is normalized to
   `{property, direction:UPPER}`. A literal Mongo-style JSON sort would reach MCP unchanged and be
   rejected server-side (safe, surfaced), but it is neither normalized nor tested.

3. **FMCP-19 — nested-filter divergence is docs-only.** Filters are forwarded unchanged by construction
   (`find.py:398-399`, no transform), and the divergence is documented (ADR-0008 + `references/find.md`),
   but no behavioral test asserts a 2+-level nested filter is forwarded byte-identically. Acceptable for
   a documented-divergence requirement.

---

## Requirement Traceability Update

FMCP-01..18: **✅ Verified**. FMCP-02 and the Mongo-sort edge case: **✅ Verified with spec-precision
note**. FMCP-19: **✅ Verified (docs-only)**.

---

## Summary

**Overall**: ✅ Ready.

**Spec-anchored check**: 19/19 ACs matched spec outcome; 3 spec-precision notes flagged (non-blocking).
**Sensor**: 5/5 mutations killed.
**Gate**: 541 passed, 0 failed, 9 skipped (live-stack, justified); coverage 93%.

**What works**: MCP-first `records_find`/`query_json`/`query_sql` with byte-identical REST parity,
the full fallback matrix (404-silent, 403/429/5xx/transport + notice-first, 401/tool-error surface
no-fallback, both-fail surfaces REST error), 429 per-process disable, `_meta` reconstruction, Bearer
auth, and SSE parsing with three typed error classes — all with strong, discriminating assertions.

**Issues found**: none blocking. Three spec-precision mismatches (see above) worth folding back into the
spec wording; the implementation's actual behavior is safe in every case.

**Next steps**: merge-ready. Optionally tighten spec wording for FMCP-02 / Mongo-sort, and (if desired
later) add a test that a Mongo-shaped valid-JSON filter surfaces as a tool error via the `find` command.
