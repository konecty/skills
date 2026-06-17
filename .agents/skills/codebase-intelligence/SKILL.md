---
name: codebase-intelligence
description: Run a full static-analysis audit of a repository — dead code, duplication, cyclomatic/cognitive complexity, unused dependencies, architecture-boundary violations, and churn-weighted hotspots — for Python and TypeScript/JavaScript codebases. Emits unified structured JSON (for agents) and a human-readable Markdown report. Use this skill whenever the user asks to audit, analyze, clean up, or refactor a Python or TypeScript/JS codebase; before opening a PR; whenever the user mentions dead code, unused imports, circular imports, slow tests, complex functions, duplicated code, unused dependencies, or asks "what should I refactor first". Works on monorepos with both languages simultaneously.
---

# Codebase Intelligence

Build a project-wide understanding of a Python and/or TypeScript/JavaScript repository instead of checking one file at a time. This skill orchestrates six independent static analyses per language, normalizes their output into a single unified JSON contract, and renders a Markdown report with prioritized findings.

The audience for the JSON output is **another agent** (or this same Claude in a later turn) deciding what to refactor, delete, or review. The audience for the Markdown is a **human reviewer** who wants to know where to spend the next hour.

## Why this skill exists

Linters check files. Type checkers check types. This skill checks the **codebase**: cross-file edges that a single-file tool cannot see.

| Question | Linter alone | This skill |
|---|---|---|
| Unused variable inside a function | ✓ | ✓ |
| Function that nothing in the repo calls | ✗ | ✓ |
| Module imported but never referenced | ✗ | ✓ |
| Circular import between packages | ✗ | ✓ |
| Duplicate logic across files | ✗ | ✓ |
| Dependency in `pyproject.toml` / `package.json` never imported | ✗ | ✓ |
| Layer A importing from layer B against the rules | ✗ | ✓ |
| The single file most likely to break next sprint | ✗ | ✓ |
| All of the above for Python AND TypeScript simultaneously | ✗ | ✓ |

The skill is deterministic, fast, and produces machine-actionable output. It is not an AI assistant — it is the layer an AI assistant calls.

## When to use

Trigger on any of these:

- The user names a repo (Python, TypeScript/JS, or monorepo) and asks for an analysis, audit, review, health check, or cleanup plan
- The user asks "where do I start refactoring", "what's the technical debt", or "is this codebase healthy"
- The user mentions a specific symptom: dead code, unused imports, circular imports, complex functions, duplicated code, unused dependencies, slow tests, tangled architecture
- Before generating a non-trivial refactor PR (run the audit first so the agent acts on facts, not guesses)
- After an agent generates a large patch (run again to detect regressions in complexity and duplication)
- The codebase is a monorepo with both `frontend/` (TypeScript) and `backend/` (Python) — this skill covers both in one pass

Do **not** use for:

- Single-file lint/format tasks (run `ruff` or `eslint` directly)
- Type errors only (use `mypy`, `pyright`, or `tsc --noEmit`)
- Runtime profiling (this skill is static)
- Security scanning (use `bandit` for Python, `npm audit` / `snyk` for JS)

## The six analyses

Each analysis is a separate script. They run independently and write JSON to a staging directory; the aggregator merges them. Both Python and TypeScript share the same six-layer structure, using best-in-class tools for each language.

| Layer | Python tool(s) | TypeScript tool(s) | Catches |
|---|---|---|---|
| 1. Dead code | `vulture` + `ruff` (F-rules) | `knip` | Unused functions, classes, methods, imports, variables, exports, unreachable code |
| 2. Duplication | `pylint --enable=duplicate-code` | `jscpd` | Repeated code blocks across files |
| 3. Complexity | `radon` (cc, mi, hal) + `xenon` | ESLint `complexity` rule (via `@typescript-eslint`) | Cyclomatic complexity, maintainability index, cognitive complexity |
| 4. Dependencies | `deptry` | `knip` (unused/missing deps) | Missing, unused, transitive, dev-in-prod dependencies |
| 5. Boundaries | `import-linter` (or circular fallback) | `dependency-cruiser` | Architecture rule violations, circular imports, forbidden edges |
| 6. Hotspots | `git log` × radon CC | `git log` × ESLint complexity | Churn-weighted complexity — files both actively changing AND high CC |

`vulture`/`knip` and `radon`/`eslint-complexity` cover the bulk of value; the others compound to give the full picture. Running both languages in one pass surfaces cross-language hotspots that would be invisible when auditing each in isolation.

## How to run the audit

The user typically wants one of four flows. Identify which and pick the matching command.

### Flow A — full audit, auto-detect languages (default)

```bash
bash scripts/audit.sh <repo-path>
```

Auto-detects languages by checking for `pyproject.toml`/`setup.py` (Python) and `package.json`/`tsconfig.json` (TypeScript). Output lands in `<repo-path>/.codebase-audit/` by default. Use `--output <dir>` to override.

This runs all six analyses per detected language and writes:
- `.codebase-audit/audit.json` — full unified JSON contract (v2.0 schema)
- `.codebase-audit/audit.md` — human report with explained findings
- `.codebase-audit/raw/*.json` — per-analysis intermediate outputs

The `.codebase-audit/` directory is automatically added to `.gitignore`. Use when the user asks for an overall review or hands over a fresh repo.

### Flow B — PR / changed-files only

```bash
bash scripts/audit.sh <repo-path> --changed-since main
```

Restricts the analysis to files changed since the given ref. Use before opening a PR, or when the user says "just look at what I changed".

### Flow C — single language

```bash
bash scripts/audit.sh <repo-path> --lang python
bash scripts/audit.sh <repo-path> --lang typescript
```

Skips detection and audits only the specified language. Useful in language-specific PRs or when one toolchain is unavailable.

### Flow D — single analysis

When the user only cares about one dimension, run the specific script directly:

```bash
# Python
python scripts/python/dead_code.py <repo-path> --out <out-dir>/raw/py_dead_code.json
python scripts/python/complexity.py <repo-path> --out <out-dir>/raw/py_complexity.json

# TypeScript
node scripts/typescript/dead_code.js --repo <repo-path> --out <out-dir>/raw/ts_dead_code.json
node scripts/typescript/complexity.js --repo <repo-path> --out <out-dir>/raw/ts_complexity.json
```

Then call `python scripts/aggregate.py <out-dir>` to render the report from whatever JSONs exist.

## Setup before first run

### Python tools

```bash
# Recommended: uv (faster, isolated)
uv tool install vulture
uv tool install ruff
uv tool install radon
uv tool install xenon
uv tool install deptry
uv tool install import-linter
uv tool install pylint

# Alternative: single venv
python -m venv ~/.codebase-intelligence/.venv
source ~/.codebase-intelligence/.venv/bin/activate
pip install vulture ruff radon xenon deptry import-linter pylint
```

### TypeScript tools

TypeScript tools use `npx --yes` so **no pre-install is required** — tools download on first run (cached by npm). For faster repeated runs, install globally:

```bash
npm install -g knip jscpd
# dependency-cruiser and ESLint are project-local by convention
```

`audit.sh` checks each tool is available (either global or via `npx`) and prints a clear install hint if something is missing. It does **not** auto-install.

### Verify setup

```bash
bash .agents/skills/codebase-intelligence/scripts/audit.sh /path/to/repo --lang auto --dry-run
```

## Output contract (v2.0 JSON schema)

The JSON the skill emits is the **contract** other agents will consume. Keep its shape stable.

```json
{
  "schema_version": "2.0",
  "repo": {
    "path": "/abs/path/to/repo",
    "head_sha": "abc123...",
    "languages": ["python", "typescript"],
    "analysis_scope": "full"
  },
  "languages": {
    "python": {
      "lang": "python",
      "python_files": 412,
      "python_loc": 38291,
      "summary": {
        "dead_code_count": 47,
        "duplication_clone_groups": 12,
        "duplicated_lines": 980,
        "duplication_rate_pct": 3.1,
        "functions_above_cc_threshold": 9,
        "avg_maintainability_index": 89.4,
        "maintainability_grade": "A",
        "unused_dependencies": 2,
        "missing_dependencies": 0,
        "boundary_violations": 1,
        "circular_import_cycles": 0
      },
      "findings": {
        "dead_code": [],
        "duplication": [],
        "complexity": [],
        "dependencies": [],
        "boundaries": [],
        "hotspots": []
      }
    },
    "typescript": {
      "lang": "typescript",
      "typescript_files": 234,
      "typescript_loc": 18500,
      "summary": {
        "dead_code_count": 5,
        "duplication_clone_groups": 7,
        "duplicated_lines": 320,
        "duplication_rate_pct": 1.8,
        "functions_above_cc_threshold": 3,
        "unused_dependencies": 1,
        "missing_dependencies": 0,
        "boundary_violations": 0,
        "circular_import_cycles": 1
      },
      "findings": {
        "dead_code": [],
        "duplication": [],
        "complexity": [],
        "dependencies": [],
        "boundaries": [],
        "hotspots": []
      }
    }
  },
  "summary": {
    "total_dead_code": 52,
    "total_duplication_clone_groups": 19,
    "total_duplicated_lines": 1300,
    "total_functions_above_cc_threshold": 12,
    "total_boundary_violations": 1,
    "total_circular_cycles": 1,
    "worst_hotspot": {
      "path": "src/billing/engine.py",
      "score": 87.3,
      "lang": "python"
    }
  },
  "verdict": "warn",
  "verdict_reason": "dead_code > 0, unused_dependencies > 0"
}
```

The `verdict` field is computed from configurable thresholds (see `references/interpretation.md`). Default: `fail` if there are missing dependencies, boundary violations, or any function with CC > 25.

### Finding shapes by layer

Each `findings.{layer}` array contains typed objects. The shapes are language-specific but follow shared conventions:

**Dead code (Python):**
```json
{
  "path": "src/utils/legacy.py",
  "line": 142,
  "kind": "unused_function",
  "name": "old_export_csv",
  "confidence": 80,
  "tool": "vulture",
  "action": {"type": "delete", "auto_fixable": false}
}
```

**Dead code (TypeScript):**
```json
{
  "path": "src/utils/legacyHelpers.ts",
  "line": 67,
  "kind": "unused_export",
  "name": "formatLegacyDate",
  "tool": "knip",
  "action": {"type": "delete", "auto_fixable": false}
}
```

**Complexity (Python / TypeScript — same shape):**
```json
{
  "path": "src/billing/engine.ts",
  "function": "computeInvoice",
  "line": 23,
  "cyclomatic": 18,
  "verdict": "above_threshold"
}
```

**Boundaries violation:**
```json
{
  "rule": "no-ui-in-domain",
  "from": "src/domain/OrderModel.ts",
  "to": "src/components/OrderTable.tsx",
  "kind": "boundary_violation",
  "severity": "error"
}
```

## Markdown report structure

The report `audit.md` follows this exact template — keep it stable so humans build muscle memory:

```markdown
# Codebase Audit — <repo-name>

**Verdict:** PASS | WARN | FAIL — <one-line reason>

## At a glance
<table: language | files | LOC | dead code | dup groups | complex fns | violations>

## Top 5 refactor candidates (all languages)
<ranked list across Python + TypeScript hotspots, file:line, score, why>

## Python findings
### Dead code (N items)
### Duplication (N clone groups, X lines)
### Complexity (N functions above threshold)
### Dependencies (N issues)
### Architecture boundaries (N violations)
### Hotspots (top 10)

## TypeScript findings
### Dead code (N items)
### Duplication (N clone groups, X lines)
### Complexity (N functions above threshold)
### Dependencies (N issues)
### Architecture boundaries (N violations)
### Hotspots (top 10)

## Suggested next actions
1. <concrete, sequenced steps, cross-language prioritized>
```

Do not embellish or reorder. Agents and humans should be able to grep this report reliably.

## Reading the output

For deeper guidance on interpreting findings, picking thresholds for a given codebase maturity (greenfield vs legacy), and TypeScript-specific traps (knip false positives, ESLint complexity with React callbacks), read `references/interpretation.md`.

For the underlying tool capabilities, edge cases, and design rationale for the TypeScript tool choices (knip vs ts-prune, dependency-cruiser vs madge, ESLint vs complexity-report), read `references/tools-typescript.md`.

For Python tool details, read the companion skill `python-codebase-intelligence/references/tools.md`.

For config templates — `knip.json`, `.dependency-cruiser.cjs`, `pyproject.toml` blocks for ruff/deptry — see `assets/`.

## Failure modes to handle gracefully

1. **No `pyproject.toml` or `setup.py`** — `deptry` cannot run; skip the Python dependencies layer and log a warning to `summary.warnings`.
2. **No `package.json`** — skip the TypeScript audit entirely for that directory; log a warning.
3. **No `tsconfig.json`** — knip and dependency-cruiser need it. Emit a warning and attempt to proceed with auto-detected TypeScript files; flag results as lower-confidence.
4. **No `.importlinter` config** — Python boundaries layer downgrades to circular-imports-only.
5. **No `.dependency-cruiser.cjs` config** — TypeScript boundaries layer detects circular imports only (no layer-boundary enforcement). Log a note pointing the user to `assets/dependency-cruiser.template.cjs`.
6. **Shallow git clone** — hotspots need history. If `git log` returns fewer than 30 commits, skip hotspots and emit a warning telling the user to run `git fetch --unshallow`.
7. **knip in a monorepo** — knip needs to be pointed at the correct workspace root. If the repo has workspaces, run knip per-workspace and merge results.
8. **Generated files (proto stubs, GraphQL codegen, `.d.ts`)** — add them to knip's `ignore` and jscpd's `--ignore` to avoid noise.

## What this skill is not

- Not a replacement for `mypy` / `pyright` / `tsc --noEmit` — type errors are not its job.
- Not a security scanner — use `bandit` for Python, `npm audit` / `snyk` for JS.
- Not a runtime profiler — static analysis only.
- Not a code formatter — run `ruff format` / `prettier` on their own.
- Not a test runner — run `pytest` / `vitest` on their own.

## Quick sanity check

Before considering the audit complete, verify:

1. `audit.json` is valid JSON (`python -m json.tool < audit.json > /dev/null`)
2. `schema_version` is `"2.0"`
3. `languages` block contains entries for each detected language
4. `summary.total_*` numbers match the sum of per-language counts
5. `verdict` is one of `pass`, `warn`, `fail`
6. The Markdown report has all six "Findings" sections for each language present, even if empty
7. If TypeScript was detected: `raw/ts_dead_code.json` exists and is non-empty

If any check fails, re-run the aggregator and inspect `raw/*.json` for the broken layer.
