# Scripts — Contracts (implementation pending)

Every script: prints JSON to stdout, diagnostics to stderr, exit 0 on success, exit 1 on blocking failure, exit 2 on degraded success (ran, but with gaps — details inside the JSON). All are **stack-agnostic**: they read commands from project docs/config or detect by evidence; they never assume a package manager. Missing optional tooling (gitleaks, coverage) degrades with a recorded note — never a crash.

JSON-heavy logic may be implemented as `python3` invoked from the `.sh` entrypoint (python3 is the only assumed dependency beyond git/bash).

---

## collect-context.sh

**Phase 1.** Usage: `collect-context.sh [--base <branch>] [--pr <number>] [--spec <path>] [--task "<text>"]`
Flags = user-pre-supplied data; whatever is provided is taken as-is, the rest is discovered.

Discovers: diff vs base (git; `gh pr diff` when `--pr` and gh available) · PR/branch metadata · spec dir (`.specs/features/*` fuzzy-matched on branch/feature name, else `.specs/quick/*`) · `.specs/codebase/` doc list · Konecty-hub task (**stub hook**: calls `konecty-task.sh` if present in this dir; integration to be specified later) · stack (prefer STACK.md/TESTING.md; fallback: lockfile/manifest detection — package.json+lock variants, pyproject/uv/requirements, Gemfile, go.mod, Cargo.toml...) · test/coverage commands + threshold (default 80).

**Output:** the `context` object of `review-state.json` (see finding-schema.md) + `"missing": ["diff" | "spec" | "konecty_task" | "codebase_docs" | "test_cmd" | ...]`. The orchestrator's readiness gate classifies `missing[]`; the script never prompts the user itself.

---

## security-scan.sh

**Phase 2, reviewer 1's deterministic layer.** Input: base branch / diff scope.

Layers: (1) secrets — `gitleaks`/`trufflehog` on the diff if installed, else built-in regex set (API keys, tokens, private key blocks, connection strings with passwords); (2) dependency audit — per detected stack (`npm|pnpm|yarn audit`, `pip-audit`, `bundle audit`, `cargo audit`...) when the manifest changed in the diff and the tool exists; (3) lexical patterns on `+` lines — sensitive names in log calls (password|token|secret|cpf|ssn...), raw string concatenation/interpolation into query calls.

**Output:** finding array (`origin: "security"`, `source: "script"`, `confidence: 1.0`) + `"skipped_layers": [...]` for the degraded note passed to the LLM reviewer.

---

## run-tests.sh

**Phase 2, reviewer 3's deterministic layer.** Input: `test_cmd`, `coverage_cmd`, `coverage_threshold` from context.json. If no test command resolved → exit 2 with `"skipped": true` (gate already warned the user).

Does: run suite → each failure = finding (`critical`) · run coverage → below threshold = finding (`warning`, with actual %) · parse coverage report (lcov/cobertura/coverage.py — by stack) and cross new-in-diff functions/handlers against uncovered lines → each uncovered new handler = finding (`critical`, "new handler with zero test coverage").

**Output:** finding array (`origin: "tests"`, `source: "script"`, `confidence: 1.0`) + `coverage_pct` + machine summary for the LLM layer.

---

## consolidate.sh

**Phase 3.** Input: 6 finding arrays + context.json.

Does: validate each finding against the schema (invalid → dropped, logged to stderr) · positional dedup `{file, line ±3}` keeping richer entry + `merged_origins` · assign stable IDs (`SEC|REQ|TST|ARQ|REG|PRF-NNN`, sequential per origin; on re-review cycles, continues numbering — never reuses) · severity grouping/order · gap detection (`git diff --name-only` minus files with findings, excluding lockfiles/configs/pure-type files) · render report skeleton markdown.

**Output:** consolidated finding array (written into review-state.json via review-state.sh) + report markdown path. The orchestrator's polish pass (consolidation.md) runs on top.

---

## review-state.sh

**The state machine.** All mutations of `review-state.json` go through here; the orchestrator and subagents never edit it directly.

```
review-state.sh init <context.json>           # create session state
review-state.sh add <findings.json>           # merge consolidated findings (assigns nothing — IDs come from consolidate)
review-state.sh accept --all | --severity critical,security | --ids SEC-001,ARQ-003
                                              # accepted; everything else open → dismissed
review-state.sh record-fix <corrector-output.json>
                                              # fixed | escalated per finding; logs files_touched
review-state.sh scope                         # → {reviewers_to_rerun, files_to_inspect, findings_in_scope}
                                              #   increments fix_attempts for findings entering re-review;
                                              #   any finding with fix_attempts ≥ 2 still unresolved → status=escalated (frozen), excluded
review-state.sh verify <rereview-output.json> # verified | reopened per finding; fix_induced findings appended with fresh IDs
review-state.sh status                        # human-readable summary; exit 0 if all terminal, exit 3 if work remains
```

Enforced invariants: IDs immutable · `fix_attempts` only increments · frozen findings can never re-enter correction · every mutation appended to `history[]`.

---

## konecty-task.sh (stub)

Placeholder for the Konecty-hub integration. Contract: given the branch/PR, print `{"found": bool, "summary": "...", "criteria": [...]}`. Details to be specified when the integration is designed; until then `collect-context.sh` treats its absence as `konecty_task` missing (critical-class fallback).
