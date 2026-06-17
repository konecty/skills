#!/usr/bin/env bash
# audit.sh — language-aware codebase security orchestrator.
#
# Usage:
#   bash audit.sh <repo-path> [--output <dir>] [--changed-since <ref>]
#                             [--lang python|typescript|auto] [--skip <layer>]
#                             [--strict] [--no-history]
#
# Layers: secrets, git_history, config_exposure (language-agnostic)
#         sast, vuln_deps, supply_chain       (per language)
#
# Exit codes: 0 pass/warn, 1 fail (or warn with --strict), 2 setup error.

set -euo pipefail

REPO=""
OUT_DIR=""
CHANGED_SINCE=""
SKIP=()
SCAN_LANG="auto"   # never name this LANG — it would clobber the locale env var
STRICT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)        OUT_DIR="$2";        shift 2 ;;
    --changed-since) CHANGED_SINCE="$2";  shift 2 ;;
    --skip)          SKIP+=("$2");        shift 2 ;;
    --lang)          SCAN_LANG="$2";      shift 2 ;;
    --strict)        STRICT=1;            shift ;;
    --no-history)    SKIP+=("git_history"); shift ;;
    -h|--help)
      head -n 13 "$0" | tail -n 12
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

case "$SCAN_LANG" in
  python)     HAS_PYTHON=1 ;;
  typescript) HAS_TS=1 ;;
  auto)
    if [[ -f "$REPO/pyproject.toml" || -f "$REPO/setup.py" || -f "$REPO/requirements.txt" ]]; then
      HAS_PYTHON=1
    elif [[ $(find "$REPO" -maxdepth 4 -name "*.py" -not -path "*/.*" -not -path "*/node_modules/*" 2>/dev/null | head -1) ]]; then
      HAS_PYTHON=1
    fi
    if [[ -f "$REPO/package.json" ]]; then
      HAS_TS=1
    fi
    ;;
  *)
    echo "ERROR: --lang must be python, typescript, or auto (got: $SCAN_LANG)" >&2; exit 2
    ;;
esac

# The language-agnostic layers (secrets/history/config) run even when no
# language is detected — secrets do not care what language they leak from.

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
if [[ -z "$OUT_DIR" ]]; then
  OUT_DIR="$REPO/.security-audit"
fi
mkdir -p "$OUT_DIR/raw/common"
[[ "$HAS_PYTHON" -eq 1 ]] && mkdir -p "$OUT_DIR/raw/python"
[[ "$HAS_TS"     -eq 1 ]] && mkdir -p "$OUT_DIR/raw/typescript"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

LANGS="common"
[[ "$HAS_PYTHON" -eq 1 ]] && LANGS="$LANGS, Python"
[[ "$HAS_TS"     -eq 1 ]] && LANGS="$LANGS, TypeScript"

echo ">>> Codebase Security"
echo "    repo:      $REPO"
echo "    layers:    $LANGS"
echo "    output:    $OUT_DIR"
[[ -n "$CHANGED_SINCE" ]] && echo "    scope:     changed since $CHANGED_SINCE"
echo

# ---------------------------------------------------------------------------
# Only hard requirement is python3; every scanner degrades gracefully.
# ---------------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required to run the audit scripts" >&2
  exit 2
fi

should_skip() {
  local name="$1"
  for s in "${SKIP[@]:-}"; do [[ "$s" == "$name" ]] && return 0; done
  return 1
}

# ---------------------------------------------------------------------------
# Changed-files target list (applies to file-level layers: secrets, sast).
# Manifest-level layers (vuln_deps, supply_chain) always run on the full repo
# because the lockfile is the unit of analysis, not the diff.
# ---------------------------------------------------------------------------
# Contract with the layer scripts: targets file ABSENT = full scan;
# PRESENT (even empty) = diff scope — empty means "nothing changed, skip".
TARGETS_FILE="$OUT_DIR/raw/common/targets.txt"
rm -f "$TARGETS_FILE"
if [[ -n "$CHANGED_SINCE" ]]; then
  (cd "$REPO" && git diff --name-only "$CHANGED_SINCE"...HEAD 2>/dev/null || true) > "$TARGETS_FILE"
  if [[ ! -s "$TARGETS_FILE" ]]; then
    echo "    note: no committed changes since $CHANGED_SINCE — file-level layers will be skipped"
  fi
fi

run_layer() {
  # run_layer <group> <name> <interpreter> <script> [extra args...]
  local group="$1" name="$2" interp="$3" script="$4"
  shift 4
  should_skip "$name" && { echo "[skip] $group:$name"; return 0; }
  echo "[run]  $group:$name"
  if ! "$interp" "$script" "$REPO" \
        --targets "$TARGETS_FILE" \
        --out "$OUT_DIR/raw/$group/${name}.json" "$@" \
        2>"$OUT_DIR/raw/$group/${name}.err"; then
    echo "  ! $group:$name failed; see $OUT_DIR/raw/$group/${name}.err"
    echo "{\"error\":true,\"layer\":\"$name\",\"group\":\"$group\"}" > "$OUT_DIR/raw/$group/${name}.json"
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Language-agnostic layers
# ---------------------------------------------------------------------------
run_layer common secrets         python3 "$SCRIPT_DIR/common/secrets.py"
run_layer common git_history     python3 "$SCRIPT_DIR/common/git_history.py"
run_layer common config_exposure python3 "$SCRIPT_DIR/common/config_exposure.py"

# ---------------------------------------------------------------------------
# Python layers
# ---------------------------------------------------------------------------
if [[ "$HAS_PYTHON" -eq 1 ]]; then
  run_layer python sast         python3 "$SCRIPT_DIR/python/sast.py"
  run_layer python vuln_deps    python3 "$SCRIPT_DIR/python/vuln_deps.py"
  run_layer python supply_chain python3 "$SCRIPT_DIR/python/supply_chain.py"
fi

# ---------------------------------------------------------------------------
# TypeScript layers
# ---------------------------------------------------------------------------
if [[ "$HAS_TS" -eq 1 ]]; then
  if command -v node >/dev/null 2>&1; then
    run_layer typescript sast         node "$SCRIPT_DIR/typescript/sast.js"
    run_layer typescript vuln_deps    node "$SCRIPT_DIR/typescript/vuln_deps.js"
    run_layer typescript supply_chain node "$SCRIPT_DIR/typescript/supply_chain.js"
  else
    echo "  ! Node.js not found — skipping TypeScript layers" >&2
    echo '{"error":true,"layer":"all","group":"typescript","reason":"node not installed"}' \
      > "$OUT_DIR/raw/typescript/sast.json"
  fi
fi

# ---------------------------------------------------------------------------
# Unified aggregation
# ---------------------------------------------------------------------------
echo "[run]  aggregate"
python3 "$SCRIPT_DIR/aggregate_all.py" "$OUT_DIR" \
  --repo "$REPO" \
  --has-python "$HAS_PYTHON" \
  --has-typescript "$HAS_TS" \
  ${STRICT:+$( [[ "$STRICT" -eq 1 ]] && echo --strict )} \
  ${CHANGED_SINCE:+--scope "changed-since:$CHANGED_SINCE"}

VERDICT="$(python3 -c "import json; print(json.load(open('$OUT_DIR/security.json'))['verdict'])")"
echo
echo ">>> Verdict: $VERDICT"
echo ">>> Report:  $OUT_DIR/security.md"
echo ">>> JSON:    $OUT_DIR/security.json"
echo ">>> SARIF:   $OUT_DIR/security.sarif"

# ---------------------------------------------------------------------------
# Ensure .security-audit is in .gitignore (the report may quote secret context)
# ---------------------------------------------------------------------------
GITIGNORE="$REPO/.gitignore"
if [[ -f "$GITIGNORE" ]]; then
  if ! grep -qxF ".security-audit/" "$GITIGNORE" && ! grep -qxF ".security-audit" "$GITIGNORE"; then
    { echo ""; echo "# codebase-security audit output"; echo ".security-audit/"; } >> "$GITIGNORE"
    echo "    (added .security-audit/ to .gitignore)"
  fi
elif [[ -d "$REPO/.git" ]]; then
  { echo "# codebase-security audit output"; echo ".security-audit/"; } > "$GITIGNORE"
  echo "    (created .gitignore with .security-audit/)"
fi

case "$VERDICT" in
  fail) exit 1 ;;
  warn) [[ "$STRICT" -eq 1 ]] && exit 1 || exit 0 ;;
  *)    exit 0 ;;
esac
