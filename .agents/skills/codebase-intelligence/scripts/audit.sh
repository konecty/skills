#!/usr/bin/env bash
# audit.sh — language-aware codebase intelligence orchestrator.
#
# Usage:
#   bash audit.sh <repo-path> [--output <dir>] [--changed-since <ref>]
#                             [--lang python|typescript|auto] [--skip <layer>]
#                             [--with-docs] [--with-tests]
#
# Layers: dead_code, duplication, complexity, dependencies, boundaries, hotspots
#
# Exit codes: 0 pass, 1 fail (verdict=fail), 2 setup error.

set -euo pipefail

REPO=""
OUT_DIR=""
CHANGED_SINCE=""
SKIP=()
LANG="auto"
WITH_DOCS=0
WITH_TESTS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)       OUT_DIR="$2";       shift 2 ;;
    --changed-since) CHANGED_SINCE="$2"; shift 2 ;;
    --skip)         SKIP+=("$2");       shift 2 ;;
    --lang)         LANG="$2";          shift 2 ;;
    --with-docs)    WITH_DOCS=1;        shift ;;
    --with-tests)   WITH_TESTS=1;       shift ;;
    -h|--help)
      head -n 12 "$0" | tail -n 11
      exit 0
      ;;
    *)
      if [[ -z "$REPO" ]]; then REPO="$1"; else
        echo "Unexpected argument: $1" >&2; exit 2
      fi
      shift
      ;;
  esac
done

if [[ -z "$REPO" ]]; then
  echo "ERROR: repo path required. Usage: bash audit.sh <repo-path> [options]" >&2
  exit 2
fi
if [[ ! -d "$REPO" ]]; then
  echo "ERROR: $REPO is not a directory" >&2; exit 2
fi
REPO="$(cd "$REPO" && pwd)"

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------
HAS_PYTHON=0
HAS_TS=0

case "$LANG" in
  python)
    HAS_PYTHON=1
    HAS_TS=0
    ;;
  typescript)
    HAS_PYTHON=0
    HAS_TS=1
    ;;
  auto)
    # Python: pyproject.toml / setup.py / requirements.txt or any .py file
    if [[ -f "$REPO/pyproject.toml" || -f "$REPO/setup.py" || -f "$REPO/requirements.txt" ]]; then
      HAS_PYTHON=1
    fi
    if [[ $(find "$REPO" -maxdepth 4 -name "*.py" -not -path "*/.*" | head -1) ]]; then
      HAS_PYTHON=1
    fi
    # TypeScript/JavaScript: package.json
    if [[ -f "$REPO/package.json" ]]; then
      HAS_TS=1
    fi
    ;;
  *)
    echo "ERROR: --lang must be python, typescript, or auto (got: $LANG)" >&2; exit 2
    ;;
esac

if [[ "$HAS_PYTHON" -eq 0 && "$HAS_TS" -eq 0 ]]; then
  echo "ERROR: no recognised language detected in $REPO" >&2
  echo "       Use --lang python or --lang typescript to force." >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
if [[ -z "$OUT_DIR" ]]; then
  OUT_DIR="$REPO/.codebase-audit"
fi

[[ "$HAS_PYTHON" -eq 1 ]] && mkdir -p "$OUT_DIR/raw/python"
[[ "$HAS_TS"     -eq 1 ]] && mkdir -p "$OUT_DIR/raw/typescript"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

LANGS=""
[[ "$HAS_PYTHON" -eq 1 ]] && LANGS="${LANGS:+$LANGS, }Python"
[[ "$HAS_TS"     -eq 1 ]] && LANGS="${LANGS:+$LANGS, }TypeScript"

echo ">>> Codebase Intelligence"
echo "    repo:      $REPO"
echo "    languages: $LANGS"
echo "    output:    $OUT_DIR"
[[ -n "$CHANGED_SINCE" ]] && echo "    scope:     changed since $CHANGED_SINCE"
echo

# ---------------------------------------------------------------------------
# Tool availability checks
# ---------------------------------------------------------------------------
check_tool() {
  local tool="$1"; local hint="$2"
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "MISSING: $tool — install with: $hint" >&2
    return 1
  fi
  return 0
}

MISSING=0

if [[ "$HAS_PYTHON" -eq 1 ]]; then
  check_tool vulture   "pip install vulture"           || MISSING=1
  check_tool ruff      "pip install ruff"              || MISSING=1
  check_tool radon     "pip install radon"             || MISSING=1
  check_tool pylint    "pip install pylint"            || MISSING=1
  check_tool deptry    "pip install deptry"            || true  # optional
  check_tool lint-imports "pip install import-linter"  || true  # optional

  if [[ "$MISSING" -ne 0 ]]; then
    echo "Install missing Python tools and re-run. Recommended: pipx or uv tool install." >&2
    exit 2
  fi
fi

if [[ "$HAS_TS" -eq 1 ]]; then
  TS_MISSING=0
  check_tool node  "Install Node.js from https://nodejs.org" || TS_MISSING=1
  check_tool npx   "Install Node.js from https://nodejs.org" || TS_MISSING=1

  if [[ "$TS_MISSING" -ne 0 ]]; then
    echo "Install Node.js and re-run." >&2
    exit 2
  fi
fi

# ---------------------------------------------------------------------------
# Skip helper
# ---------------------------------------------------------------------------
should_skip() {
  local name="$1"
  for s in "${SKIP[@]:-}"; do [[ "$s" == "$name" ]] && return 0; done
  return 1
}

# ---------------------------------------------------------------------------
# Python layers
# ---------------------------------------------------------------------------
if [[ "$HAS_PYTHON" -eq 1 ]]; then
  PYTHON_SCRIPT_DIR="$SCRIPT_DIR/python"

  # Build target file list
  TARGETS_FILE="$OUT_DIR/raw/python/targets.txt"
  if [[ -n "$CHANGED_SINCE" ]]; then
    (cd "$REPO" && git diff --name-only "$CHANGED_SINCE"...HEAD -- '*.py' || true) \
      | { grep -vE '(^|/)\.' || true; } > "$TARGETS_FILE"  # drop dot-dirs (e.g. .agents/) — consistent with full-scan branch
    if [[ ! -s "$TARGETS_FILE" ]]; then
      echo "No Python files changed since $CHANGED_SINCE — skipping Python layers."
      echo '{"schema_version":"1.0","verdict":"pass","summary":{"warnings":["no changed python files"]}}' \
        > "$OUT_DIR/raw/python/aggregate.json"
      HAS_PYTHON=0
    fi
  else
    (cd "$REPO" && find . -name '*.py' \
      -not -path '*/\.*' \
      -not -path '*/node_modules/*' \
      -not -path '*/venv/*' \
      -not -path '*/.venv/*') > "$TARGETS_FILE"
  fi
fi

if [[ "$HAS_PYTHON" -eq 1 ]]; then
  run_python_layer() {
    local name="$1"; local script="$2"
    should_skip "$name" && { echo "[skip] python:$name"; return; }
    echo "[run]  python:$name"
    if ! python3 "$PYTHON_SCRIPT_DIR/$script" "$REPO" \
          --targets "$OUT_DIR/raw/python/targets.txt" \
          --out "$OUT_DIR/raw/python/${name}.json" 2>"$OUT_DIR/raw/python/${name}.err"; then
      echo "  ! python:$name failed; see $OUT_DIR/raw/python/${name}.err"
      echo '{"error":true,"layer":"'"$name"'","lang":"python"}' > "$OUT_DIR/raw/python/${name}.json"
    fi
  }

  run_python_layer dead_code    dead_code.py
  run_python_layer duplication  duplication.py
  run_python_layer complexity   complexity.py
  run_python_layer dependencies dependencies.py
  run_python_layer boundaries   boundaries.py
  run_python_layer hotspots     hotspots.py

  echo "[run]  python:aggregate"
  # aggregate.py takes the TOP-LEVEL out dir and resolves raw/python itself;
  # passing raw/python here double-appends it (writes to raw/python/raw/python).
  python3 "$PYTHON_SCRIPT_DIR/aggregate.py" "$OUT_DIR" \
    --repo "$REPO" \
    ${CHANGED_SINCE:+--scope "changed-since:$CHANGED_SINCE"}
fi

# ---------------------------------------------------------------------------
# TypeScript layers
# ---------------------------------------------------------------------------
if [[ "$HAS_TS" -eq 1 ]]; then
  TS_SCRIPT_DIR="$SCRIPT_DIR/typescript"

  run_ts_layer() {
    local name="$1"; local script="$2"
    should_skip "$name" && { echo "[skip] typescript:$name"; return; }
    echo "[run]  typescript:$name"
    if ! node "$TS_SCRIPT_DIR/$script" --repo "$REPO" \
          --out "$OUT_DIR/raw/typescript/${name}.json" 2>"$OUT_DIR/raw/typescript/${name}.err"; then
      echo "  ! typescript:$name failed; see $OUT_DIR/raw/typescript/${name}.err"
      echo '{"error":true,"layer":"'"$name"'","lang":"typescript"}' > "$OUT_DIR/raw/typescript/${name}.json"
    fi
  }

  run_ts_layer dead_code    dead_code.js
  run_ts_layer duplication  duplication.js
  run_ts_layer complexity   complexity.js
  run_ts_layer dependencies dependencies.js
  run_ts_layer boundaries   boundaries.js
  run_ts_layer hotspots     hotspots.js

  echo "[run]  typescript:aggregate"
  node "$TS_SCRIPT_DIR/aggregate.js" "$OUT_DIR" --repo "$REPO"
fi

# ---------------------------------------------------------------------------
# Unified aggregation
# ---------------------------------------------------------------------------
echo "[run]  aggregate:unified"
python3 "$SCRIPT_DIR/aggregate_all.py" "$OUT_DIR" \
  --repo "$REPO" \
  --has-python "$HAS_PYTHON" \
  --has-typescript "$HAS_TS" \
  ${CHANGED_SINCE:+--scope "changed-since:$CHANGED_SINCE"}

# ---------------------------------------------------------------------------
# Surface verdict
# ---------------------------------------------------------------------------
VERDICT="$(python3 -c "import json; print(json.load(open('$OUT_DIR/audit.json'))['verdict'])")"
echo
echo ">>> Verdict: $VERDICT"
echo ">>> Report:  $OUT_DIR/audit.md"
echo ">>> JSON:    $OUT_DIR/audit.json"

# ---------------------------------------------------------------------------
# Ensure .codebase-audit is in .gitignore
# ---------------------------------------------------------------------------
GITIGNORE="$REPO/.gitignore"
if [[ -f "$GITIGNORE" ]]; then
  if ! grep -qxF ".codebase-audit/" "$GITIGNORE" && ! grep -qxF ".codebase-audit" "$GITIGNORE"; then
    echo "" >> "$GITIGNORE"
    echo "# codebase-intelligence audit output" >> "$GITIGNORE"
    echo ".codebase-audit/" >> "$GITIGNORE"
    echo "    (added .codebase-audit/ to .gitignore)"
  fi
elif [[ -d "$REPO/.git" ]]; then
  echo "# codebase-intelligence audit output" > "$GITIGNORE"
  echo ".codebase-audit/" >> "$GITIGNORE"
  echo "    (created .gitignore with .codebase-audit/)"
fi

case "$VERDICT" in
  fail) exit 1 ;;
  *)    exit 0 ;;
esac
