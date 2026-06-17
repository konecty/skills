# Config examples

Copy these into the target repo to enable the relevant layers and tune thresholds.

## pyproject.toml — full setup

```toml
[tool.ruff]
line-length = 100
target-version = "py310"
extend-exclude = ["migrations", "build", "dist"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
fixable = ["ALL"]
ignore = ["E501"]  # line length handled by formatter

[tool.deptry]
exclude = ["tests", "build", "dist", "venv", ".venv"]
ignore_missing = []          # add packages here if deptry can't resolve them
ignore_unused = []           # add packages declared but used dynamically (e.g. plugins)
known_first_party = ["myapp"]

[tool.deptry.per_rule_ignores]
DEP002 = ["uvicorn", "gunicorn"]  # runtime servers loaded by name, not imported

[tool.vulture]
min_confidence = 80
paths = ["src", "myapp"]
exclude = ["tests/", "migrations/"]
ignore_decorators = [
    "@app.route",
    "@router.*",
    "@receiver",
    "@shared_task",
    "@pytest.fixture",
]
```

## .importlinter — architecture boundaries

Place this file at the repo root. The skill auto-detects it and runs `lint-imports`.

### Layered architecture (most common)

```ini
[importlinter]
root_package = myapp
include_external_packages = True

[importlinter:contract:layers]
name = Application layered architecture
type = layers
layers =
    myapp.interface
    myapp.application
    myapp.domain
    myapp.infrastructure
```

This says: code in `myapp.interface` may import from `myapp.application`, `myapp.domain`, and `myapp.infrastructure`. Code in `myapp.domain` may import only from `myapp.infrastructure`. Reversed imports are violations.

### Hexagonal / ports-and-adapters

```ini
[importlinter]
root_package = myapp

[importlinter:contract:independence]
name = Adapters are independent of each other
type = independence
modules =
    myapp.adapters.http
    myapp.adapters.cli
    myapp.adapters.celery

[importlinter:contract:forbidden]
name = Domain must not depend on adapters
type = forbidden
source_modules =
    myapp.domain
forbidden_modules =
    myapp.adapters
```

### Forbidden test → production imports

```ini
[importlinter:contract:forbidden]
name = Production code must not import from tests
type = forbidden
source_modules = myapp
forbidden_modules = tests
```

## .vulture-whitelist.py — manual overrides

When auto-detection misses a dynamic-dispatch pattern, add the names here:

```python
# Custom Konecty decorator that registers handlers by name
_.handle_signup_complete
_.handle_payment_received

# Django admin actions registered via the admin.register pattern
_.export_as_csv
_.mark_as_processed

# Pydantic validators called by name
_.validate_email_domain
```

Pass it explicitly to vulture: `vulture src/ .vulture-whitelist.py --min-confidence 80`. The skill does this automatically — it writes a generated whitelist to `<out-dir>/raw/python/vulture_whitelist.py` and you can copy the relevant entries into a permanent `.vulture-whitelist.py` if you want them to survive across audits.

## .github/workflows/audit.yml — CI gate

```yaml
name: codebase-audit

on:
  pull_request:
    branches: [main]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # required for hotspots layer

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install audit tooling
        run: |
          pip install vulture ruff radon pylint deptry import-linter

      - name: Clone skill
        run: git clone https://github.com/<you>/codebase-intelligence /tmp/ci

      - name: Run audit on changed files only
        run: bash /tmp/ci/scripts/audit.sh . --output ./audit-out --changed-since origin/main

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: audit-report
          path: audit-out/

      - name: Post summary
        if: always()
        run: cat audit-out/audit.md >> $GITHUB_STEP_SUMMARY
```

This fails the PR if `audit.sh` exits non-zero (i.e., verdict is `fail`).

## .pre-commit-hooks.yaml — pre-commit integration

```yaml
- repo: local
  hooks:
    - id: codebase-audit
      name: codebase audit (changed files)
      entry: bash scripts/audit.sh . --output .audit-precommit --changed-since HEAD~1
      language: system
      pass_filenames: false
      stages: [pre-push]
```

Use `pre-push` rather than `pre-commit` — the full audit is too slow for every commit. Pre-push gives the developer the report before the PR goes up.
