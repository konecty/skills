# TypeScript/JavaScript Analysis Tools

Detailed notes on each tool the codebase-intelligence skill uses for TypeScript/JavaScript, what each tool can and cannot detect, how its output is structured, and the rationale for selecting it over alternatives.

## Python ↔ TypeScript tool mapping

| Dimension | Python | TypeScript |
|---|---|---|
| Dead code (definitions) | `vulture` | `knip` |
| Dead code (imports) | `ruff` F401 | `knip` (unused imports) |
| Unused dependencies | `deptry` DEP002 | `knip` (unused deps) |
| Missing dependencies | `deptry` DEP001 | `knip` (missing deps) |
| Cyclomatic complexity | `radon` + `xenon` | ESLint `complexity` rule |
| Maintainability index | `radon mi` | (no direct equivalent; use CC as proxy) |
| Architecture boundaries | `import-linter` | `dependency-cruiser` |
| Duplication | `pylint` R0801 | `jscpd` |
| Hotspots | `git log` × radon CC | `git log` × ESLint CC output |

---

## knip (dead code + unused dependencies)

**Version:** v5+ (API changed significantly from v2; ensure v5+ is used)

**What it does:**

knip performs whole-program dead code analysis by starting from configured entry points and doing a mark-and-sweep walk through the TypeScript/JavaScript module graph. Any export, import, file, or dependency that is not reachable from an entry point is flagged as unused.

This approach is fundamentally superior to per-file tools (like ts-prune) because it understands the full module graph: a symbol exported from `utils.ts` and imported in `api.ts` is live even if `api.ts` itself only re-exports it to `index.ts`.

**Categories of findings:**

| Category | knip term | What it catches |
|---|---|---|
| Unused files | `unlisted-files` | TypeScript files with no inbound imports |
| Unused exports | `unused-exports` | Exported symbols that are never imported elsewhere |
| Unused dependencies | `unlisted-dependencies` | `package.json` deps that are never imported |
| Unused dev dependencies | `unlisted-dev-dependencies` | devDeps never used in config, test, or build files |
| Duplicate exports | `duplicate-exports` | Same symbol exported more than once |
| Unused enum members | `unused-enum-members` | TypeScript enum values never referenced |
| Unused class members | `unused-class-members` | Private/public class fields never accessed |

**Running knip:**

```bash
# JSON output (used by the skill's dead_code.js)
npx --yes knip --reporter json 2>/dev/null

# Human-readable
npx --yes knip

# With explicit config file
npx --yes knip --config knip.json
```

**JSON output shape:**

```json
{
  "files": ["src/utils/legacyHelpers.ts"],
  "exports": [
    {
      "name": "formatLegacyDate",
      "pos": 67,
      "line": 23,
      "col": 0,
      "isType": false,
      "filePath": "src/utils/legacyHelpers.ts"
    }
  ],
  "dependencies": {
    "unused": ["lodash-es", "moment"],
    "unlisted": ["undeclared-package"],
    "unresolved": []
  }
}
```

**Config file (`knip.json` or `package.json` `"knip"` key):**

See `assets/knip.template.json` for a production-ready template.

Key fields:
- `entry` — glob patterns for entry points (e.g., `src/index.ts`, `vite.config.ts`)
- `project` — glob patterns for all project files to consider
- `ignore` — patterns to skip entirely (generated files, test fixtures)
- `ignoreDependencies` — specific package names to never flag as unused
- `ignoreExportsUsedInFile` — prevents flagging exports only used within the same file (reduces false positives for module-internal helpers)
- `extends` — framework preset (e.g., `"next"`, `"vite"`, `"remix"`, `"astro"`)

**Framework presets:**

knip has built-in presets for the most common frameworks that automatically configure correct entry points. Relevant for this project:

```json
{
  "extends": ["vite"],
  "entry": ["src/main.tsx"]
}
```

Without the correct preset, knip may flag framework-defined entry points (e.g., Next.js `pages/`, Vite `index.html`) as unused.

**Known caveats:**

- **Dynamic imports** — `import(computedPath)` is not followed; any module only reachable via dynamic import will be flagged as unused.
- **`require()` with computed paths** — same limitation.
- **Barrel file re-exports** — `export * from './module'` is generally handled, but deep barrel chains can cause missed references. Use `ignoreExportsUsedInFile: true`.
- **Monorepos** — each workspace needs its own knip run with the correct `entry` and `project` for that workspace. The orchestrator runs knip per-workspace and merges results.
- **Generated files** — proto stubs, GraphQL codegen, Prisma clients — add to `ignore`.
- **`eval` and reflection** — knip cannot see symbols accessed via `eval`, `window[dynamicKey]`, or similar patterns.

**Why not ts-prune:**

ts-prune was the original go-to for TypeScript dead code analysis but has been in maintenance mode since 2022. Its own README now recommends knip. ts-prune works by scanning for exported symbols that are never imported anywhere — it has no concept of the module graph or entry points, so it produces many false positives for symbols that are imported transitively through barrel files.

---

## jscpd (duplication)

**Version:** v4+ (npm package: `jscpd`)

**What it does:**

jscpd (JavaScript Copy-Paste Detector) detects duplicated code blocks across files. It tokenizes source files and finds repeated token sequences above a configurable minimum length. It is language-agnostic and works across 150+ languages, making it the same tool for both TypeScript and Python duplication detection.

**Running jscpd:**

```bash
# JSON output with clone detail
npx --yes jscpd src/ \
  --reporters json \
  --output /tmp/jscpd-out \
  --min-lines 6 \
  --min-tokens 50 \
  --ignore "**/*.test.ts,**/*.spec.ts,**/*.d.ts"

# The JSON report is written to /tmp/jscpd-out/jscpd-report.json
```

**JSON output shape:**

```json
{
  "statistics": {
    "total": {
      "lines": 15234,
      "tokens": 89201,
      "sources": 87,
      "clones": 14,
      "duplicatedLines": 423,
      "duplicatedTokens": 2841,
      "percentage": 2.77,
      "percentageTokens": 3.18
    }
  },
  "duplicates": [
    {
      "format": "typescript",
      "lines": 24,
      "tokens": 198,
      "fragment": "...",
      "firstFile": {
        "name": "src/api/users.ts",
        "start": 88,
        "end": 112
      },
      "secondFile": {
        "name": "src/api/teams.ts",
        "start": 14,
        "end": 38
      }
    }
  ]
}
```

**Key flags:**

| Flag | Default | Purpose |
|---|---|---|
| `--min-lines` | 5 | Minimum clone size in lines |
| `--min-tokens` | 50 | Minimum clone size in tokens |
| `--reporters` | `console` | Use `json` for machine output |
| `--output` | cwd | Directory to write JSON report |
| `--ignore` | none | Glob patterns to skip |
| `--languages` | all | Restrict to specific languages |
| `--threshold` | 0 | Exit non-zero if duplication % exceeds this |

**Thresholds:**

The skill defaults to `--min-lines 6 --min-tokens 50`. This avoids flagging trivial patterns (import lines, short type aliases) while catching meaningful copy-paste blocks.

For the duplication verdict:
- `warn` if `statistics.total.percentage > 5`
- `fail` if `statistics.total.percentage > 15` (or configurable)

**Known caveats:**

- Will flag **generated files** (proto stubs, GraphQL codegen, migration files) as heavily duplicated. Always add generated directories to `--ignore`.
- Will flag **test fixtures** and **mock data** that happen to be similar. These are rarely worth DRY-ing up. Add test files to `--ignore` or accept the noise.
- Does not understand **semantic equivalence** — two functions doing the same thing with different variable names are not detected.
- Very **large files** (> 5000 lines) are processed but may be slow.

---

## ESLint complexity rule

**What it does:**

The ESLint `complexity` rule counts the cyclomatic complexity (CC) of each function. CC counts the number of independent execution paths: +1 for the function entry, +1 for each `if`, `else if`, `for`, `while`, `do-while`, `case`, `catch`, `&&`, `||`, `??`, `?.`, ternary `? :`.

The `@typescript-eslint` parser and plugin extend this to TypeScript-specific constructs and also add a `cognitive-complexity` rule that scores functions by how hard they are for a human to understand (more sensitive to nesting depth).

**Running in isolation (no project ESLint config):**

```bash
# Create a minimal config on the fly and run only the complexity rule
npx --yes eslint \
  --no-eslintrc \
  --parser @typescript-eslint/parser \
  --rule '{"complexity": ["warn", 10]}' \
  --format json \
  src/**/*.{ts,tsx}
```

For the skill's purposes, the `no-eslintrc` approach (ESLint 8 syntax) or `--no-eslint-ignore` + `-c /tmp/eslint-complexity.json` (ESLint 9 flat config) ensures the complexity check runs the same way regardless of the target project's existing ESLint configuration.

**JSON output shape:**

```json
[
  {
    "filePath": "/abs/path/src/billing/engine.ts",
    "messages": [
      {
        "ruleId": "complexity",
        "severity": 1,
        "message": "Function 'computeInvoice' has a complexity of 18. Maximum allowed is 10.",
        "line": 23,
        "column": 1,
        "endLine": 89,
        "endColumn": 1,
        "nodeType": "FunctionDeclaration"
      }
    ],
    "errorCount": 0,
    "warningCount": 1
  }
]
```

**Extracting CC value:**

The CC value is embedded in the `message` string. The skill's `complexity.js` parses it with:

```javascript
const match = msg.message.match(/has a complexity of (\d+)/);
const cc = match ? parseInt(match[1], 10) : null;
```

**Thresholds:**

The skill uses the same thresholds as the Python layer:
- `CC_WARN = 10` (ESLint rule set to `["warn", 10]`)
- `CC_FAIL = 25` (separate pass with `["error", 25]` or post-filter)

**Integrating with existing project ESLint config:**

If the target project already has ESLint configured with `@typescript-eslint`, the complexity rule can be added to the existing config instead of running in isolation. However, running in isolation is safer for the skill because it ensures consistent results regardless of what the project has configured.

For projects that want to enforce complexity in their own CI, add to `.eslintrc.json`:

```json
{
  "rules": {
    "complexity": ["warn", 10],
    "@typescript-eslint/no-misleading-character-class": "off"
  }
}
```

**Known caveats:**

- **Framework callbacks** — React event handlers, Promise chains, and array method callbacks (`map`, `filter`, `reduce`) all add to CC. A `handleSubmit` with 3 conditions and 2 async paths can easily reach CC=8 without being truly complex.
- **Ternary chains** — every ternary adds +1. JSX with many inline ternaries for conditional rendering inflates CC.
- **Logical operators** — `&&` and `||` add +1 each. Guard clauses (`if (!x) return`) also add +1 even though they reduce cognitive complexity.
- **`// eslint-disable-next-line complexity`** — use sparingly for well-understood high-complexity functions (e.g., a large `switch` dispatcher). Document why.

---

## dependency-cruiser

**Version:** v16+ (npm package: `dependency-cruiser`)

**What it does:**

dependency-cruiser builds the full module dependency graph of a TypeScript/JavaScript project and enforces rules against it. Rules can detect circular imports, forbidden import edges, orphaned files, and architecture layer violations.

Without a config file, it detects circular imports automatically. With a config, it enforces any rule expressible as a directed edge predicate (from-path matches X, to-path matches Y, severity is error/warn/info).

**Running:**

```bash
# Detect circular imports only (no config needed)
npx --yes depcruise \
  --output-type json \
  --no-config \
  src/

# Full rule enforcement with config
npx --yes depcruise \
  --output-type json \
  --config .dependency-cruiser.cjs \
  src/

# Generate a visual graph (optional, for documentation)
npx --yes depcruise \
  --output-type dot \
  --config .dependency-cruiser.cjs \
  src/ | dot -T svg > dependency-graph.svg
```

**JSON output shape:**

```json
{
  "modules": [
    {
      "source": "src/domain/OrderModel.ts",
      "dependencies": [
        {
          "resolved": "src/components/OrderTable.tsx",
          "dependencyTypes": ["local"],
          "valid": false,
          "rules": [
            {
              "severity": "error",
              "name": "no-ui-in-domain"
            }
          ]
        }
      ],
      "valid": false,
      "rules": []
    }
  ],
  "summary": {
    "violations": [
      {
        "type": "dependency",
        "from": "src/domain/OrderModel.ts",
        "to": "src/components/OrderTable.tsx",
        "rule": {
          "severity": "error",
          "name": "no-ui-in-domain"
        }
      }
    ],
    "error": 1,
    "warn": 0,
    "info": 0,
    "totalCruised": 87,
    "optionsUsed": {}
  }
}
```

**Initializing a config:**

```bash
# Interactive setup (generates .dependency-cruiser.cjs)
npx depcruise --init

# Use the skill's template instead:
cp .agents/skills/codebase-intelligence/assets/dependency-cruiser.template.cjs .dependency-cruiser.cjs
```

**Rule examples for layered architecture:**

```javascript
// No UI imports in domain layer
{
  name: 'no-ui-in-domain',
  severity: 'error',
  from: { path: '^src/domain' },
  to: { path: '^src/(components|pages|ui)' }
}

// No circular imports (always-on by default)
{
  name: 'no-circular',
  severity: 'warn',
  from: {},
  to: { circular: true }
}

// Orphaned files (nothing imports them)
{
  name: 'no-orphans',
  severity: 'info',
  from: { orphan: true, pathNot: ['\\.d\\.ts$', 'index\\.(ts|tsx)$'] },
  to: {}
}
```

See `assets/dependency-cruiser.template.cjs` for a complete production-ready config for a layered React/TypeScript frontend.

**TypeScript path aliases:**

If the project uses `tsconfig.json` `paths` or `baseUrl`, configure dependency-cruiser to resolve them:

```javascript
options: {
  tsConfig: { fileName: 'tsconfig.json' },
  tsPreCompilationDeps: true
}
```

**Known caveats:**

- **Without config**, only circular imports are detected. Layer-boundary enforcement requires a `.dependency-cruiser.cjs` config.
- **TypeScript path aliases** must be reflected in the config's `tsConfig` option or aliases will not resolve.
- **Very large codebases** (> 1000 files) can be slow; use `--include-only '^src/'` to limit scope.
- **`node_modules`** should always be in `doNotFollow.path` to avoid analyzing third-party code.

---

## Fallow (optional / future fast-path)

**Repository:** https://github.com/fallow-rs/fallow

**What it does:**

Fallow is a Rust-based static analysis tool for TypeScript/JavaScript that runs six analyses in a single pass: dead code, duplication, complexity, circular dependencies, architecture boundaries, and PR risk scoring. It was the primary research subject for the TypeScript tool selection.

**Output formats:** JSON (`CheckOutput`), SARIF, CodeClimate, Markdown, LSP diagnostics, MCP server.

**Installing:**

```bash
# From cargo (requires Rust toolchain)
cargo install fallow-cli

# Binary releases (no Rust required)
# Check https://github.com/fallow-rs/fallow/releases for platform binaries

# GitHub Action
- uses: fallow-rs/fallow-action@v1
  with:
    format: json
```

**Running:**

```bash
# JSON output
fallow check --output json .

# Markdown report
fallow check --output markdown .

# Only specific checks
fallow check --checks dead-code,complexity .
```

**When to prefer Fallow over the 4-tool combo:**

- The team has a Rust toolchain available (via `rustup`)
- The codebase is TypeScript-only (no Python to audit)
- Performance matters: fallow runs in a single pass vs. four sequential tool invocations
- You want SARIF output for GitHub Advanced Security integration
- You want the LSP/VS Code extension for inline diagnostics during development

**Planned integration:**

The skill is designed to accept `--engine fallow` as an optional flag:

```bash
bash scripts/audit.sh /path/to/repo --lang typescript --engine fallow
```

When this flag is used:
1. The script checks if `fallow` is on PATH
2. Runs `fallow check --output json .` and writes the output to `raw/fallow_raw.json`
3. `scripts/typescript/fallow_adapter.js` maps fallow's `CheckOutput` JSON to the v2.0 schema
4. The 4-tool pipeline is skipped entirely

This is deferred to a future iteration. For now, the 4-tool combo (knip + jscpd + ESLint + dependency-cruiser) is the default TypeScript engine.

---

## Tool version compatibility

| Tool | Minimum version | Notes |
|---|---|---|
| `knip` | 5.0 | v5 changed the JSON output schema significantly |
| `jscpd` | 4.0 | v4 reorganized CLI flags |
| `eslint` | 8.0 | ESLint 9 uses flat config — the skill's isolation mode adapts |
| `@typescript-eslint/parser` | 7.0 | Matches ESLint 8+ |
| `dependency-cruiser` | 16.0 | v16 improved TypeScript path resolution |
| `fallow` | 0.3 (planned) | Not yet integrated |

Always pin tool versions in CI for reproducible results. The skill's `audit.sh` logs the version of each tool it invokes to `raw/tool_versions.json`.
