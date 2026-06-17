# Python Analysis Tools

Detailed notes on each tool the skill orchestrates, what it can and cannot detect, and how to extend the skill with additional tools.

## Vulture (dead code — functions, classes, methods)

**What it does:** Static AST walk that flags definitions for which no static reference exists.

**What it cannot see:**
- Dynamic dispatch via decorators (`@app.route`, `@receiver`, `@shared_task`, `@router.get`)
- Reflection / `getattr` lookups
- String-based callable references (Celery task names, Django URL strings, Pydantic plugin hooks)
- ABC subclass requirements (a method may exist only to satisfy an interface)

**How the skill mitigates this:** `scripts/python/dead_code.py` scans target files for the decorators listed in `DYNAMIC_DECORATORS` and synthesizes a whitelist (`_.<func_name>`) on the fly. You can extend the list directly in the script or add a permanent `assets/vulture_whitelist.py` and pass it explicitly.

**Tuning:** `--min-confidence` defaults to 80. Drop to 60 for more aggressive scans (more false positives), bump to 90 for surgical cleanups.

## Ruff (dead code — imports, variables, redefinitions)

Used only with rules `F401`, `F811`, `F841`. These are deterministic (100% confidence) and most are auto-fixable. Run `ruff check --fix --select F401,F811,F841 .` to apply.

For a broader cleanup pass, replace `F401,F811,F841` with `F,UP,B,SIM` in `scripts/python/dead_code.py`.

## Pylint (duplication)

Pylint's `duplicate-code` checker (`R0801`) is slower than `jscpd` but ships with pylint and doesn't require a Node toolchain. It catches structural duplicates after stripping comments, docstrings, and imports.

**Tuning:** `--min-similarity-lines=6` is the default (matches pylint's default). Drop to 4 to find tiny copy-pastes, raise to 10 to focus on bigger blocks.

**Faster alternative:** `jscpd` with the python plugin. Swap `scripts/python/duplication.py` to call `jscpd --reporters json` if Node is available. The output shape would need a thin adapter to match our `findings.duplication` schema.

## Radon (complexity)

Three subcommands:
- `radon cc` — McCabe cyclomatic complexity per function/method
- `radon mi` — maintainability index (0-100 composite of CC, Halstead, LOC, comments) per file
- `radon hal` — Halstead metrics (vocabulary, length, volume, difficulty, effort)

**Why all three:** CC alone misses files that are "wide but flat" (many simple branches). MI catches that. Halstead volume catches files dense in unique operators (cryptography, parsers).

**Thresholds in `scripts/python/complexity.py`:**
- `CC_WARN = 10` — radon's "C" rank, generally accepted as the warning line
- `CC_FAIL = 25` — radon's "F" rank, critical
- `MI_POOR = 20.0` — files below this need attention

Tighten or loosen these for greenfield vs legacy codebases — see `interpretation.md`.

## Deptry (dependency hygiene)

Catches five classes of issues:

| Code | Meaning |
|---|---|
| DEP001 | Imported module not declared in pyproject/requirements |
| DEP002 | Declared dependency never imported anywhere |
| DEP003 | Imported via transitive dependency (works by luck, not contract) |
| DEP004 | Dev-dependency used in production code path |
| DEP005 | Stdlib module declared as third-party (e.g. `typing-extensions` on 3.11+) |

Deptry needs a manifest. If the repo only uses `pip install -e .` with no `pyproject.toml`, this layer is skipped.

## Import-linter (architecture boundaries)

The only layer that requires configuration to be fully useful. Without a config file, the skill falls back to circular-import detection only.

Typical config (`.importlinter` at repo root):

```ini
[importlinter]
root_package = myapp

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers =
    myapp.web
    myapp.application
    myapp.domain
    myapp.infrastructure
```

This says: `web` may import from anything below it, but `infrastructure` must not import from `domain`. Violations show up in the audit.

Other contract types: `forbidden` (blacklist specific edges), `independence` (no cross-imports between siblings).

## Circular-import detector (always-on)

Hand-rolled in `scripts/python/boundaries.py` using `ast` + Tarjan's strongly-connected-components algorithm. Builds the first-party import graph and reports SCCs of size > 1 (cycles) or self-loops.

This runs even when no `.importlinter` config exists, so the boundaries layer always produces some signal.

## Git churn × radon (hotspots)

The score formula:

```
score = log(1 + commits_in_last_90_days) * max_cyclomatic_complexity_in_file
```

The log dampens runaway churn (a file with 200 commits doesn't dominate everything), and multiplying by max-CC focuses on files that are both *active* and *risky*. Files that are heavily edited but simple (e.g., config tables) score low; files that are complex but stable (e.g., a finished parser) score low. Sweet spot: edited often AND complex.

**Why 90 days:** captures current sprint pressure without being dominated by ancient commits. Change `WINDOW_DAYS` in the script for different cadences (30d for fast-moving teams, 180d for slow-moving codebases).

## Extending the skill

To add a 7th layer (e.g., type coverage with `mypy --strict`):

1. Create `scripts/python/type_coverage.py` following the same interface: `argparse(repo, --targets, --out)`, write JSON with `{layer, findings, counts}` shape.
2. Add a line to `audit.sh`: `run_layer type_coverage scripts/python/type_coverage.py`.
3. Update `scripts/python/aggregate.py` to read `raw/python/type_coverage.json` and include its findings in the summary.

Keep each layer self-contained and crash-resistant — `audit.sh` writes `.err` files but does not abort if a layer fails.
