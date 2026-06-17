# Interpreting the audit

How to read the JSON and Markdown outputs for Python and TypeScript codebases, prioritize findings across languages, and avoid the common traps.

---

## 1. Verdict semantics

`pass | warn | fail` is computed from configurable thresholds. Defaults:

| Verdict | Trigger |
|---|---|
| `fail` | Missing dependencies, architecture boundary violations (severity `error`), or any function with CC ≥ 25 |
| `warn` | Dead code present, duplication > 5%, unused dependencies, CC ≥ 10, circular imports, boundary warnings |
| `pass` | None of the above |

A `pass` does **not** mean the code is perfect — it means there's nothing the audit considers immediately blocking. A `warn` is the normal state of a healthy production codebase; treat it as a checklist, not an alarm.

A `fail` should block the merge.

The `verdict_reason` field gives a one-line explanation:

```json
{
  "verdict": "warn",
  "verdict_reason": "dead_code > 0, unused_dependencies > 0 (python: 2, typescript: 1)"
}
```

---

## 2. Fix priority order (cross-language)

Address findings in this sequence regardless of language:

1. **Missing dependencies** — these break clean installs. Fix in the same commit that introduced them. (Python: deptry DEP001; TypeScript: knip unlisted-dependencies)
2. **Architecture boundary violations (error severity)** — these compound. A `domain → infrastructure` import today becomes ten next quarter. (Python: import-linter; TypeScript: dependency-cruiser `severity: "error"` rules)
3. **Circular imports** — these often hide design smells. Resolving them usually requires extracting a shared types module. Apply to the language where they appear; if present in both, fix the deeper cycle first.
4. **Critical complexity (CC ≥ 25)** — refactor the worst function in the file at the top of the cross-language hotspot list. Don't tackle all complex functions; focus on the ones with the highest hotspot score (change frequently AND complex).
5. **Dead code** — fast wins. Auto-fix Python (`ruff --fix`) and TypeScript unused imports first; then review the longer vulture/knip lists manually.
6. **Unused dependencies** — bundle these into the dead-code cleanup commit. Smaller `pyproject.toml` / `package.json` = faster CI. (Python: deptry DEP002; TypeScript: knip unused deps)
7. **Boundary warnings (warn severity)** — these are worth addressing in the next refactor sprint, not immediately.
8. **Duplication** — the slowest to fix. Worth tackling for clone groups ≥ 30 lines across 3+ files; smaller ones are usually not worth the abstraction cost.

---

## 3. TypeScript-specific thresholds

### Complexity

Same thresholds as Python:
- `CC_WARN = 10` — ESLint `complexity` rule set to warn
- `CC_FAIL = 25` — functions at or above this level are critical

These are the defaults; see Section 5 for tuning guidance.

### Duplication

- Warn if `jscpd statistics.total.percentage > 5`
- Fail if `jscpd statistics.total.percentage > 15` (configurable)

### Architecture boundaries

- `severity: "error"` violations → `verdict = fail`
- `severity: "warn"` violations → `verdict = warn`
- No config present → circular imports only; note in `summary.warnings`

### Dead code

knip findings do not have a numeric threshold — any unused export or unused dependency is flagged. The skill maps:
- `> 0` unused dependencies → `warn`
- `> 0` files entirely unused → `warn`
- `> 10` unused exports → `warn` (configurable; small numbers are often false positives in framework projects)

---

## 4. Python threshold tuning

### Greenfield project (< 6 months old)

Tighten everything. Defects compound fastest in young codebases.

- `CC_WARN = 7`, `CC_FAIL = 15`
- Treat any duplication as warn-worthy
- Boundary violations should be `fail` from day one

### Mature legacy codebase

Loosen FAIL thresholds initially, then tighten as you clean up. Use baselines.

- Save a baseline: `bash scripts/audit.sh . --output baseline/` and commit `baseline/audit.json`
- Modify CI to diff against the baseline — fail only on **new** findings, not historical debt
- This is the "baseline-then-improve" pattern that import-linter and ruff both support natively

### Library / package

- Boundary violations matter less (single root package usually)
- Dead-code thresholds should be stricter — a public library can't afford dead exports because users may rely on them
- Use vulture with `--min-confidence 100` and treat every finding as a question to answer

---

## 5. TypeScript threshold tuning

### Greenfield project

Same pattern as Python: tighten early, fail on boundary violations from day one.

```json
{
  "thresholds": {
    "cc_warn": 7,
    "cc_fail": 15,
    "duplication_warn_pct": 3.0
  },
  "verdict": {
    "fail_on_boundary_violations": true,
    "fail_on_circular_imports": true
  }
}
```

### React/Vite frontend (this project)

React codebases with hooks and event handlers systematically inflate CC. Recommended starting thresholds:

- `CC_WARN = 12` (slightly looser than default to accommodate hook compositions)
- `CC_FAIL = 25` (keep this; truly critical complexity)
- Duplication: exclude `src/**/*.stories.tsx` and `src/**/*.test.tsx`

### Monorepo with shared packages

If the repo has internal packages in `packages/`, knip needs to be configured per-workspace. Set `ignoreExportsUsedInFile: false` for library packages (they have external consumers) and `true` for application packages (exports are internal).

### Legacy TypeScript migration (from JavaScript)

When a repo is being migrated from JS to TS, expect many knip findings for files not yet covered by `tsconfig.json`. Use `--skip dead_code` until the migration is complete.

---

## 6. Key traps for TypeScript

**Trap 1: knip cannot see dynamic imports.**

knip treats `import(computedPath)` as opaque. Any module reachable only via a dynamic import will be flagged as unused. Common in:
- Route-based code splitting (`React.lazy(() => import('./pages/Admin'))`)
- Plugin registries that load modules by name
- Vite/Webpack virtual modules

Mitigation: add dynamically imported files to `entry` in `knip.json`, or add the directory to `ignore` if it's entirely dynamic.

**Trap 2: ESLint complexity inflated by framework callbacks.**

React event handlers, Promise chains, and array method callbacks add to CC even when the logic is simple. Example:

```typescript
// CC = 7 (not truly complex)
const handleSubmit = async (e: FormEvent) => {
  e.preventDefault();
  if (!formData.name) return;           // +1
  if (!formData.email) return;          // +1
  try {
    const result = await submit(formData);
    if (result.ok) {                    // +1
      onSuccess();
    } else {
      onError(result.error ?? 'Unknown'); // +1 (??)
    }
  } catch (err) {                       // +1
    onError(String(err));
  }
};
```

Use `// eslint-disable-next-line complexity` sparingly for well-understood handlers. Document why. Alternatively, use `@typescript-eslint/cognitive-complexity` which scores nesting depth rather than raw branch count — it handles this pattern better.

**Trap 3: dependency-cruiser without config detects only circular imports.**

Running `depcruise --no-config src/` will find cycles but not layer violations. For this project's layered architecture (domain / services / API / components / pages), you must have a `.dependency-cruiser.cjs` config with explicit rules. Copy from `assets/dependency-cruiser.template.cjs` and adapt layer names.

**Trap 4: jscpd will flag generated files.**

Protocol Buffer stubs, GraphQL codegen (`src/__generated__/`), Prisma client, and migration files contain highly repetitive patterns that jscpd will flag. These are not worth DRY-ing up.

Always add generated directories to `--ignore`:

```bash
jscpd src/ --ignore "src/__generated__/**,src/migrations/**,**/*.d.ts"
```

**Trap 5: knip false positives with `export default` in index files.**

Barrel files (`index.ts`) that re-export everything from subdirectories can cause knip to miss some references. If a barrel file re-exports 20 symbols and only 15 are used, knip should flag 5 — but if the barrel uses `export * from './module'`, some cases are missed in knip v5. Use named exports in barrel files when possible.

**Trap 6: ESLint complexity counts optional chaining as branches.**

`foo?.bar?.baz` adds +2 to CC (one `?.` per chain link). In TypeScript codebases that lean heavily on optional chaining for null safety, this can inflate scores substantially. There is no perfect solution; treat it as noise if the optional chains are guard patterns rather than true branch logic.

---

## 7. JSON contract usage for agents

For agentic consumers, the canonical entry points into `audit.json` are:

```jsonc
audit.json
├── summary                    // cross-language dashboard — read this first
├── verdict                    // "pass" | "warn" | "fail" — the gate decision
├── verdict_reason             // one-line explanation
├── languages.python           // Python-specific block (if present)
│   ├── summary                // Python-only counts
│   └── findings.{layer}       // Python findings, drill in as needed
└── languages.typescript       // TypeScript-specific block (if present)
    ├── summary                // TypeScript-only counts
    └── findings.{layer}       // TypeScript findings, drill in as needed
```

Typical agent pattern:

```python
with open("audit.json") as f:
    audit = json.load(f)

# Gate decision
verdict = audit["verdict"]
if verdict == "fail":
    surface(audit["verdict_reason"])
    surface(get_fail_findings(audit))
    return

# Context for next step
if verdict == "warn":
    context = summarize_warnings(audit["summary"])
    # Proceed but include warnings as context for the refactor agent
```

Cross-language iteration:

```python
for lang, lang_data in audit.get("languages", {}).items():
    for finding in lang_data["findings"].get("dead_code", []):
        # Each finding has `path`, `line`, `name`, `tool`
        queue_for_review(finding, lang=lang)
```

The `worst_hotspot` field in `summary` gives the single most urgent refactor target without requiring the agent to iterate all hotspots:

```python
hotspot = audit["summary"]["worst_hotspot"]
# {"path": "src/billing/engine.py", "score": 87.3, "lang": "python"}
```

---

## 8. When to re-run the audit

- **Before opening a non-trivial PR** — use `--changed-since main` to limit noise
- **Weekly on `main`** — track trends in `summary` over time
- **After a large refactor** — verify the refactor actually reduced complexity
- **When onboarding to a new codebase** — full audit gives a 5-minute orientation across both languages
- **After dependency updates** — unused deps often appear after major version upgrades

A monthly diff of the `summary` block is a lightweight way to track codebase health without dashboard infrastructure:

```bash
# Save current summary
jq .summary .codebase-audit/audit.json > /tmp/summary-$(date +%Y-%m).json

# Compare with last month
diff /tmp/summary-2025-05.json /tmp/summary-$(date +%Y-%m).json
```
