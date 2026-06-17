# Codebase Intelligence Skill

> Polyglot static-analysis harness for Python and TypeScript/JavaScript repositories.
> Emits unified JSON + Markdown reports. Designed to be the "truth layer" an AI agent calls before generating refactors.

## Table of Contents

1. [What it does](#1-what-it-does)
2. [Supported languages and tooling](#2-supported-languages-and-tooling)
3. [Architecture](#3-architecture)
4. [Setup](#4-setup)
5. [Usage](#5-usage)
6. [Output formats](#6-output-formats)
7. [Interpreting results](#7-interpreting-results)
8. [Configuration](#8-configuration)
9. [How we got here: research and design decisions](#9-how-we-got-here-research-and-design-decisions)
10. [Extending the skill](#10-extending-the-skill)
11. [Limitations](#11-limitations)

---

## 1. What it does

This skill orchestrates six categories of static analysis against a codebase and produces two artifacts:

1. **`audit.json`** — A structured JSON contract (schema v2.0) that another agent can consume to decide what to refactor, what to delete, or what to block a merge on.
2. **`audit.md`** — A human-readable Markdown report with prioritized findings, ranked hotspots, and concrete next actions.

The six analysis layers are:

| Layer | What it finds |
|---|---|
| Dead code | Functions, classes, exports, and imports that nothing references |
| Duplication | Repeated code blocks across files (clone detection) |
| Complexity | Functions with high cyclomatic complexity, poor maintainability |
| Dependencies | Unused, missing, transitive, and misplaced package dependencies |
| Boundaries | Circular imports, layer-architecture rule violations |
| Hotspots | Files that are both frequently changed AND highly complex (the real risk) |

The unique value over running each tool separately:

- **Cross-file perspective** — linters see within a file; this skill sees across the whole codebase graph.
- **Unified JSON output** — one contract, one verdict, one report regardless of language mix.
- **Cross-language hotspot ranking** — in a monorepo with Python and TypeScript, the skill produces a single ranked list of "where to start" across both languages.
- **Machine-actionable** — the JSON schema is designed so an orchestrating agent can gate decisions on `verdict` and drill into `findings.{layer}` without further parsing.

---

## 2. Supported languages and tooling

### Python

| Layer | Tool | Notes |
|---|---|---|
| Dead code | `vulture` + `ruff` (F-rules) | vulture: unused defs; ruff: unused imports/vars (auto-fixable) |
| Duplication | `pylint` (`duplicate-code` / R0801) | structural clones after stripping comments |
| Complexity | `radon` (cc, mi, hal) + `xenon` | CC, maintainability index, Halstead; xenon enforces thresholds |
| Dependencies | `deptry` | 5 error classes (missing, unused, transitive, dev-in-prod, stdlib mismatch) |
| Boundaries | `import-linter` + circular fallback | contract-based layers; built-in SCC detector always on |
| Hotspots | `git log` × radon CC | `log(1 + commits_90d) × max_CC` score |

### TypeScript / JavaScript

| Layer | Tool | Notes |
|---|---|---|
| Dead code | `knip` | mark-and-sweep from entrypoints; catches unused exports, deps, files |
| Duplication | `jscpd` | CLI clone detector; 150+ languages, polyglot-safe |
| Complexity | ESLint `complexity` rule | `@typescript-eslint/parser`; no project eslint config needed (run in isolation) |
| Dependencies | `knip` | reuses the same knip run as dead code; no extra pass needed |
| Boundaries | `dependency-cruiser` | circular imports + configurable layer rules |
| Hotspots | `git log` × ESLint CC | same formula as Python; uses per-function CC from ESLint output |

### Python ↔ TypeScript tool mapping

| Dimension | Python | TypeScript |
|---|---|---|
| Dead code (definitions) | `vulture` | `knip` |
| Dead code (imports) | `ruff` F401 | `knip` (unused imports) |
| Unused dependencies | `deptry` DEP002 | `knip` (unused deps) |
| Missing dependencies | `deptry` DEP001 | `knip` (missing deps) |
| Complexity | `radon` + `xenon` | ESLint `complexity` |
| Architecture boundaries | `import-linter` | `dependency-cruiser` |
| Duplication | `pylint` R0801 | `jscpd` |
| Hotspots | `git log` × radon | `git log` × ESLint |

---

## 3. Architecture

```
scripts/
  audit.sh                  # orchestrator: detects languages, runs layers, calls aggregator
  aggregate.py              # merges raw/*.json into audit.json + audit.md
  python/
    dead_code.py            # vulture + ruff
    duplication.py          # pylint R0801
    complexity.py           # radon + xenon
    dependencies.py         # deptry
    boundaries.py           # import-linter + SCC fallback
    hotspots.py             # git log × radon
  typescript/
    dead_code.js            # knip --reporter json
    duplication.js          # jscpd --reporters json
    complexity.js           # eslint --format json (complexity rule)
    dependencies.js         # reuses knip_raw.json from dead_code run
    boundaries.js           # depcruise --output-type json
    hotspots.js             # git log × eslint CC results
assets/
  knip.template.json        # knip config template for TypeScript projects
  dependency-cruiser.template.cjs  # depcruise config template (layered React/TS)
  vulture_whitelist.py      # Python dynamic-dispatch whitelist
  pyproject_audit.toml      # ruff/deptry config blocks
  importlinter.template.ini # import-linter contract template
references/
  tools-typescript.md       # TS tool capabilities, caveats, design rationale
  interpretation.md         # how to read findings for both languages
```

Each script follows the same interface contract:
- Takes `--repo <path>` and `--out <path>` arguments
- Writes a JSON file with `{lang, layer, findings, counts, warnings}` shape
- Exits 0 on success (even if findings exist — findings are not errors)
- Exits 1 only on tooling failure (tool missing, parse error)

The aggregator (`aggregate.py`) reads all `raw/*.json` files, merges them into the v2.0 schema, computes the cross-language `summary` block, applies verdict thresholds, and renders the Markdown report.

---

## 4. Setup

### Python tools

Install once in an isolated environment so they do not pollute the target project:

```bash
# Recommended: uv (faster, parallel install)
uv tool install vulture
uv tool install ruff
uv tool install radon
uv tool install xenon
uv tool install deptry
uv tool install import-linter
uv tool install pylint
```

Or with a venv:

```bash
python -m venv ~/.codebase-intelligence/.venv
source ~/.codebase-intelligence/.venv/bin/activate
pip install vulture ruff radon xenon deptry import-linter pylint
```

### TypeScript tools

TypeScript tools use `npx --yes` so **no pre-install is required** — npm downloads and caches tools on first run. For faster repeated runs, install globally:

```bash
npm install -g knip jscpd
```

`dependency-cruiser` and ESLint are typically project-local. The skill falls back to `npx` for both if not installed globally.

### Verify setup

```bash
bash .agents/skills/codebase-intelligence/scripts/audit.sh /path/to/repo --dry-run
```

This checks all tools for the detected languages and prints their versions without running any analysis.

---

## 5. Usage

### Full audit (auto-detect languages)

```bash
bash scripts/audit.sh /path/to/repo
```

Output in `/path/to/repo/.codebase-audit/`.

### Single language

```bash
# Python only
bash scripts/audit.sh /path/to/repo --lang python

# TypeScript only
bash scripts/audit.sh /path/to/repo --lang typescript
```

### PR audit (changed files only)

```bash
bash scripts/audit.sh /path/to/repo --changed-since main
```

Limits analysis to files touched since the given ref. Faster and less noisy for pre-merge checks.

### Skip a layer

```bash
bash scripts/audit.sh /path/to/repo --skip duplication
bash scripts/audit.sh /path/to/repo --skip boundaries,hotspots
```

### Custom output directory

```bash
bash scripts/audit.sh /path/to/repo --output /tmp/my-audit
```

### Single language scripts directly

Run a specific layer and feed the result to the aggregator:

```bash
# TypeScript dead code
node scripts/typescript/dead_code.js --repo /path/to/repo --out /tmp/audit/raw/ts_dead_code.json

# Python complexity
python scripts/python/complexity.py /path/to/repo --out /tmp/audit/raw/py_complexity.json

# Aggregate whatever JSONs exist
python scripts/aggregate.py /tmp/audit
```

### Monorepo with workspaces

For repos where TypeScript and Python live in separate directories:

```bash
bash scripts/audit.sh /path/to/monorepo \
  --python-root backend/ \
  --typescript-root frontend/
```

---

## 6. Output formats

### Directory structure

```
.codebase-audit/
  audit.json          # full v2.0 contract
  audit.md            # human report
  raw/
    py_dead_code.json
    py_duplication.json
    py_complexity.json
    py_dependencies.json
    py_boundaries.json
    py_hotspots.json
    ts_dead_code.json
    ts_duplication.json
    ts_complexity.json
    ts_dependencies.json
    ts_boundaries.json
    ts_hotspots.json
    knip_raw.json       # cached knip output (reused by ts_dependencies.js)
```

### JSON contract (v2.0)

Top-level structure:

```json
{
  "schema_version": "2.0",
  "repo": {
    "path": "/abs/path",
    "head_sha": "abc123",
    "languages": ["python", "typescript"],
    "analysis_scope": "full"
  },
  "languages": {
    "python": { "lang": "python", "summary": {}, "findings": {} },
    "typescript": { "lang": "typescript", "summary": {}, "findings": {} }
  },
  "summary": {
    "total_dead_code": 52,
    "total_duplication_clone_groups": 19,
    "worst_hotspot": { "path": "...", "score": 87.3, "lang": "python" }
  },
  "verdict": "warn",
  "verdict_reason": "..."
}
```

See `SKILL.md` for the full schema with finding shapes per layer.

### Markdown report

Sections in fixed order:

1. Verdict banner + one-line reason
2. "At a glance" table (per language: files, LOC, finding counts)
3. Top 5 refactor candidates (cross-language ranked hotspot list)
4. Python findings (six subsections)
5. TypeScript findings (six subsections)
6. Suggested next actions (numbered, concrete, sequenced)

---

## 7. Interpreting results

See `references/interpretation.md` for full guidance. Summary:

| Verdict | Meaning | Action |
|---|---|---|
| `pass` | Nothing blocking; normal state for greenfield | Proceed; bookmark the report |
| `warn` | Normal state for healthy production codebase | Treat as checklist, not alarm |
| `fail` | Something should block the merge | Surface to reviewer before merging |

Default fail triggers: missing dependencies, architecture boundary violations, any function with CC ≥ 25.

Default warn triggers: dead code present, duplication > 5%, unused dependencies, circular imports, CC ≥ 10.

---

## 8. Configuration

### Per-project configuration files

The skill looks for configuration files in the repo root:

| File | Tool | Purpose |
|---|---|---|
| `knip.json` or `knip.config.ts` | knip | Entry points, ignore patterns, framework presets |
| `.dependency-cruiser.cjs` | dependency-cruiser | Layer rules, forbidden edges |
| `.importlinter` | import-linter | Python layer contracts |
| `pyproject.toml` `[tool.ruff]` block | ruff | Python lint config |
| `pyproject.toml` `[tool.deptry]` block | deptry | Dependency ignore lists |

If a config file is absent, the skill runs the tool with safe defaults and logs a note in `summary.warnings`.

### Templates

Copy from `assets/` to your repo root:

```bash
cp .agents/skills/codebase-intelligence/assets/knip.template.json your-project/knip.json
cp .agents/skills/codebase-intelligence/assets/dependency-cruiser.template.cjs your-project/.dependency-cruiser.cjs
```

Then edit to match your actual entry points and layer structure.

### Threshold tuning

Thresholds are configured as environment variables or via a `.codebase-intelligence.toml` file:

```toml
[thresholds]
cc_warn = 10
cc_fail = 25
duplication_warn_pct = 5.0
duplication_fail_pct = 15.0

[verdict]
fail_on_boundary_violations = true
fail_on_missing_deps = true
fail_on_circular_imports = false
```

---

## 9. How we got here: research and design decisions

### 9.1 The problem

Linters check individual files. Type checkers check types. Formatters check style. None of them check the **codebase as a system**: the cross-file dependency graph, the churn-weighted risk surface, the duplicated logic that drifts apart over time, or the package dependency set that has grown stale.

This project is a monorepo with:
- `backend/` — Python FastAPI service consuming Konecty data
- `frontend/` — TypeScript React SPA with Vite
- `services/` — Python RabbitMQ consumers

Running separate audits for Python and TypeScript produced disjoint reports. A developer trying to decide "where to spend the next hour" would have to mentally merge three reports across two languages. The cross-language hotspot list — the single most actionable output — was impossible to compute from separate runs.

The goal was a unified harness: one command, one JSON, one report, both languages.

### 9.2 Research: Fallow

The initial research direction was [fallow](https://github.com/fallow-rs/fallow), a Rust-based codebase intelligence tool for TypeScript/JavaScript.

Fallow's design is excellent and directly inspired this skill's six-layer architecture:

- Six analyses in a single pass: dead code, duplication, complexity, circular deps, architecture boundaries, PR risk
- Multiple output formats: JSON (`CheckOutput`), SARIF, CodeClimate, Markdown, LSP diagnostics, MCP server
- Production-ready: MIT license, GitHub Action, VS Code extension, used in its own CI
- TypeScript-first: understands imports, re-exports, barrel files, and dynamic patterns

**Why fallow was not adopted as the primary engine:**

1. **Rust toolchain required** — the target environment has Node.js and Python but not Rust. Distributing a Rust binary or requiring `cargo install` raises the setup bar for contributors.
2. **No Python support** — fallow is TypeScript/JS only; a separate harness was needed for Python regardless.
3. **Composability** — the individual Node tools (knip, jscpd, ESLint, dependency-cruiser) are maintained independently by large communities, have their own plugin ecosystems, and can be upgraded separately. Fallow wraps some of these but also reimplements others.

Fallow remains an attractive future option as a **fast-path engine** for the TypeScript layer when a Rust toolchain is available (`--engine fallow` is planned as a future flag). When it lands, the JSON output would be adapted to the v2.0 schema by a thin adapter in `scripts/typescript/fallow_adapter.js`.

### 9.3 Research: TypeScript/JS tool landscape

The full evaluation matrix:

| Tool | Category | Status | Selected? | Reason |
|---|---|---|---|---|
| **knip** | Dead code + unused deps | Active, v5+ | Yes | Best-in-class; mark-and-sweep from entrypoints; supersedes ts-prune |
| ts-prune | Dead code | Maintenance mode | No | Knip is strictly better; ts-prune author recommends knip |
| **jscpd** | Duplication | Active | Yes | Only reliable CLI duplication detector; polyglot (150+ langs) |
| **ESLint complexity** | Complexity | Stable (built-in) | Yes | Already in most projects; TS-aware via @typescript-eslint; zero-config mode possible |
| complexity-report | Complexity | Unmaintained (2018) | No | Last release 2018; doesn't understand modern TS syntax |
| **dependency-cruiser** | Boundaries | Active | Yes | Most powerful circular/boundary checker for JS/TS; JSON output; configurable rules |
| madge | Boundaries | Active | No | Visualization-focused, not analysis-focused; no boundary rule engine |
| eslint-plugin-import | Boundaries | Active | Partial | Useful but redundant alongside dependency-cruiser for boundary work |
| eslint-plugin-boundaries | Boundaries | Active | Config-heavy | Good alternative to depcruise; requires per-project config; depcruise simpler to bootstrap |
| SonarQube | All | Active | No | Server infrastructure required; overkill for local/CI use |

**knip selection rationale:**

knip performs a whole-program dead code analysis by starting from configured entrypoints and doing a mark-and-sweep through the module graph. It understands:
- TypeScript re-exports and barrel files
- Framework-specific entrypoints (Next.js pages, Vite config, Vitest config, Astro, Remix, etc.)
- `package.json` `exports`, `main`, `bin` fields
- Unused devDependencies separate from unused production dependencies

This is fundamentally better than ts-prune's approach (scan for exported symbols that are never imported) because ts-prune treats each file in isolation and cannot distinguish "exported but only used internally" from "exported but truly dead".

**jscpd selection rationale:**

jscpd is the only mature CLI tool that:
1. Works across 150+ languages (so the same tool covers Python AND TypeScript in one pass)
2. Produces structured JSON output
3. Has configurable minimum clone size and token thresholds
4. Handles comment stripping, blank line normalization

`pylint duplicate-code` was initially used for Python duplication. After selecting jscpd for TypeScript, using jscpd for both languages was considered. The decision to keep pylint for Python was: pylint is already a required tool for Python dead code analysis, so adding jscpd as another dependency for a capability that's already covered is not justified. Python uses pylint; TypeScript uses jscpd.

**ESLint complexity selection rationale:**

ESLint's built-in `complexity` rule (and `@typescript-eslint` extensions for cognitive complexity) was chosen over complexity-report because:
- complexity-report is unmaintained (last release 2018) and does not parse modern TypeScript syntax correctly
- ESLint is already in virtually every TypeScript project
- The `--no-eslintrc` flag (replaced by `--no-eslint-ignore` + `--config` in ESLint 9+) allows running just the complexity rule without the project's existing ESLint config, enabling zero-config bootstrapping

**dependency-cruiser selection rationale:**

dependency-cruiser builds a full module dependency graph and can enforce rules as code (`.dependency-cruiser.cjs`). Key advantages:
- Can enforce layer constraints (e.g., "domain must not import from infrastructure")
- Detects circular imports by default even without a config file
- JSON output that maps directly to the `findings.boundaries` schema
- Understands TypeScript path aliases and `baseUrl`
- Well-maintained (2024 active) with TypeScript support

madge was rejected because its primary output is a visualization (SVG/DOT), not a machine-readable rule violation list.

### 9.4 Design decisions

**Unified JSON schema v2.0**

The Python-only skill used schema v1.0 with a flat `findings` block. v2.0 adds a `languages` namespace:

```json
{
  "languages": {
    "python": { "summary": {}, "findings": {} },
    "typescript": { "summary": {}, "findings": {} }
  },
  "summary": { /* cross-language aggregation */ },
  "verdict": "warn"
}
```

This structure lets consumers handle mixed repos with `languages.python` and `languages.typescript` blocks, while still getting a single top-level `verdict` for CI gating. The `summary` block aggregates across languages so a consumer that only cares about "is this repo healthy overall" reads just three fields.

**Output directory renamed from `.python-audit/` to `.codebase-audit/`**

The Python-only skill wrote to `.python-audit/`. The polyglot skill writes to `.codebase-audit/` to reflect its scope and avoid confusion in monorepos where both might coexist.

**TypeScript tools use `npx --yes` — no pre-install required**

Python tools require explicit installation (`uv tool install`) because they run in an isolated environment and pip packages don't distribute binaries. Node packages via `npx` are self-contained and npm caches them locally, making `npx --yes knip` effectively instant after the first run. This reduces setup friction for TypeScript-only repos.

**knip run once, output cached to `knip_raw.json`**

knip covers both dead code AND unused dependencies in a single analysis pass. Running it twice (once for each layer) would double the runtime for larger repos. The dead_code.js script writes `knip_raw.json`; the dependencies.js script reads it instead of re-running knip. The aggregator validates `knip_raw.json` exists before calling dependencies.js.

**Cross-language hotspot score**

The hotspot score formula is identical for both languages:

```
score = log(1 + commits_in_last_90_days) * max_cyclomatic_complexity_in_file
```

Because the formula and window are the same, scores are directly comparable across Python and TypeScript files. The aggregator sorts all hotspots (both languages) into a single ranked list. The `lang` field on each hotspot record lets consumers filter if needed.

**Fallow as optional fast-path alternative**

Fallow's 2024 architecture is impressive and may outperform the 4-tool TypeScript combo on larger codebases (single-pass vs. four sequential passes). The skill is designed to accommodate a `--engine fallow` flag that would:
1. Check if `fallow` binary is on PATH
2. Run `fallow check --output json .`
3. Adapt fallow's `CheckOutput` JSON to the v2.0 schema via `scripts/typescript/fallow_adapter.js`
4. Skip the 4-tool pipeline

This is deferred to a future iteration.

### 9.5 Alternatives considered and rejected

| Alternative | Why rejected |
|---|---|
| **SonarQube** | Requires running a server; overkill for local/CI developer workflow |
| **ESLint alone** | No cross-file dead code detection, no dependency management; single-file perspective |
| **Fallow alone** | Rust binary required; no Python support |
| **jscpd for Python too** | pylint is already required; two duplication tools for two languages is cleaner |
| **madge for boundaries** | Visualization-only; no rule enforcement, no JSON violation list |
| **ts-prune** | In maintenance mode; knip is strictly more capable and its own author recommends migrating |
| **complexity-report** | Last release 2018; TypeScript syntax support broken |
| **Two separate skills (python-only + ts-only)** | Cross-language hotspot ranking is impossible; monorepo users would need two commands and manual merging |

---

## 10. Extending the skill

### Adding a 7th layer (e.g., type coverage)

1. Create `scripts/typescript/type_coverage.js` or `scripts/python/type_coverage.py` following the standard interface: `--repo <path>`, `--out <path>`, writes `{lang, layer, findings, counts, warnings}`.
2. Add a line to `audit.sh`: `run_layer ts_type_coverage scripts/typescript/type_coverage.js`.
3. Update `aggregate.py` to read `raw/ts_type_coverage.json` and include counts in the summary.
4. Add a new section to `render_markdown` in the same style as the existing six.

Keep each layer self-contained and crash-resistant. `audit.sh` writes `.err` files but does not abort if a layer fails.

### Adding a new language (e.g., Go, Rust)

1. Create `scripts/go/` directory with scripts for each layer.
2. Add language detection to `audit.sh` (detect `go.mod`).
3. Add `"go"` to the `languages` namespace in the v2.0 schema.
4. Update `aggregate.py` to handle the new language block.

### Integrating runtime data (coverage overlay)

The fallow project layers V8/Istanbul coverage data on top of static analysis to mark hot paths and cold-deletable code. The Python equivalent is `coverage.py`'s JSON output. A future `scripts/overlay/runtime_coverage.js` (for JS/TS Istanbul data) and `scripts/overlay/runtime_coverage.py` (for Python coverage.py) can ingest coverage JSON and add a `runtime_coverage` block to findings. The v2.0 schema is designed to accommodate this: per-finding `runtime_hit` and `last_hit_date` fields can be added without breaking the schema.

---

## 11. Limitations

### knip limitations

- Cannot follow dynamic `import()` calls, `require()` with computed paths, or `eval`
- `export default` re-exports are sometimes missed in barrel files
- Monorepo workspace support requires careful `knip.json` configuration
- Framework presets reduce false positives but require the correct preset to be specified

### ESLint complexity limitations

- Cyclomatic complexity counts every branch (ternary, logical `&&`/`||`, optional chaining `?.`)
- React event handlers and Promise chains inflate CC artificially — a `handleClick` with 3 conditions may score CC=5
- Cognitive complexity (via `@typescript-eslint/no-misleading-character-class` plugin) is more accurate but requires a separate install

### dependency-cruiser limitations

- Without a `.dependency-cruiser.cjs` config, only detects circular imports (no layer-boundary enforcement)
- TypeScript path aliases must be configured in both `tsconfig.json` and `.dependency-cruiser.cjs`
- Very large codebases (>1000 files) can be slow; use `--include-only` to limit scope

### jscpd limitations

- Will flag generated files (proto stubs, GraphQL codegen, `.d.ts` files) unless excluded
- Min-token threshold (`--min-tokens 50`) may miss short but significant clones
- Does not understand semantic equivalence — two functions that do the same thing with different variable names will not be detected

### Git history limitations

- Hotspot analysis requires unshallow git history; shallow clones (GitHub Actions default) need `fetch-depth: 0`
- Renamed files appear as separate file paths in git log; hotspot scores will undercount churn for frequently renamed files
- Very new repos (< 30 commits) produce noisy hotspot signals

### General

- All analysis is static; runtime-only behavior (dynamic dispatch, late binding, eval) is invisible
- The `verdict` thresholds are tuned for a "healthy production codebase" baseline; greenfield and legacy codebases should adjust thresholds (see `references/interpretation.md`)
- The skill does not auto-fix anything; it only reports. Apply fixes manually or via `ruff --fix` / targeted ESLint `--fix` for the auto-fixable subset
