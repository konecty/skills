#!/usr/bin/env python3
"""Layer 1 — Dead code detection.

Combines:
- vulture (functions, classes, methods, unreachable code)
- ruff F401 / F811 / F841 (unused imports, redefinitions, unused locals)

Vulture cannot see dynamic dispatch (Flask routes, Django signals, Celery tasks).
We auto-detect common frameworks and inject a whitelist of decorator patterns
that mark functions as "live" even if no static caller exists.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Decorator patterns that indicate a function is dynamically called.
# If any of these appears immediately above a definition, we treat it as live.
DYNAMIC_DECORATORS = [
    r"@app\.route",          # Flask
    r"@blueprint\.route",    # Flask blueprints
    r"@router\.(get|post|put|delete|patch)",  # FastAPI
    r"@receiver",            # Django signals
    r"@shared_task",         # Celery
    r"@task",                # Celery / Invoke
    r"@app\.task",           # Celery
    r"@pytest\.fixture",     # pytest
    r"@hookimpl",            # pluggy
    r"@register",            # django admin / generic
    r"@click\.command",      # click
    r"@click\.group",
    r"@cli\.command",
]


def detect_framework_hints(repo: Path) -> list[str]:
    """Look at pyproject.toml + requirements files to guess frameworks."""
    hints = []
    for fname in ("pyproject.toml", "requirements.txt", "Pipfile", "setup.cfg"):
        p = repo / fname
        if not p.exists():
            continue
        try:
            content = p.read_text(errors="ignore").lower()
        except OSError:
            continue
        for kw in ("flask", "django", "fastapi", "celery", "pytest", "click", "typer"):
            if kw in content and kw not in hints:
                hints.append(kw)
    return hints


def build_whitelist(targets: list[Path]) -> list[str]:
    """Scan source files for names following dynamic-dispatch decorators.

    Vulture's whitelist format is a list of `_.name` attribute accesses;
    we synthesize those so vulture stops reporting them.
    """
    pattern = re.compile(
        r"^\s*(?:" + "|".join(DYNAMIC_DECORATORS) + r")\b[^\n]*\n"
        r"\s*(?:async\s+)?def\s+([A-Za-z_]\w*)",
        re.MULTILINE,
    )
    names: set[str] = set()
    for f in targets:
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for m in pattern.finditer(text):
            names.add(m.group(1))
    return [f"_.{n}" for n in sorted(n for n in names if n is not None)]


def run_vulture(repo: Path, targets_file: Path, whitelist_path: Path, min_confidence: int = 60) -> list[dict]:
    """Run vulture and parse text output.

    min_confidence=60 is the right default for an *audit* — we want broad
    coverage and let the human triage. Vulture assigns 60% confidence to
    functions/classes/methods (because they could be imported externally),
    90% to imports, and 100% to truly unreachable code. Use 80+ when you
    want to be conservative (e.g. auto-delete pass).
    """
    args = [
        "vulture",
        str(repo),
        str(whitelist_path),
        "--min-confidence",
        str(min_confidence),
        "--exclude",
        "tests,test_*,*_test.py,migrations,*/migrations/*,build,dist,.venv,venv,.agents",
    ]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return []

    findings = []
    # vulture line format: "path:line: unused <kind> '<name>' (NN% confidence)"
    line_re = re.compile(
        r"^(?P<path>[^:]+):(?P<line>\d+): unused (?P<kind>\w+) '(?P<name>[^']+)' \((?P<conf>\d+)% confidence\)"
    )
    for line in result.stdout.splitlines():
        m = line_re.match(line)
        if not m:
            continue
        try:
            rel = str(Path(m["path"]).resolve().relative_to(repo))
        except ValueError:
            rel = m["path"]
        findings.append({
            "path": rel,
            "line": int(m["line"]),
            "kind": f"unused_{m['kind']}",
            "name": m["name"],
            "confidence": int(m["conf"]),
            "tool": "vulture",
            "action": {"type": "delete", "auto_fixable": False},
        })
    return findings


def run_ruff(repo: Path) -> list[dict]:
    """Run ruff to catch F401 (unused imports), F811 (redefs), F841 (unused vars)."""
    args = [
        "ruff", "check", str(repo),
        "--select", "F401,F811,F841",
        "--output-format", "json",
        "--no-fix",
        "--force-exclude",
    ]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return []
    if not result.stdout.strip():
        return []
    try:
        items = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    kind_map = {
        "F401": "unused_import",
        "F811": "redefined_unused",
        "F841": "unused_variable",
    }
    findings = []
    for it in items:
        code = it.get("code", "")
        try:
            rel = str(Path(it["filename"]).resolve().relative_to(repo))
        except (ValueError, KeyError):
            rel = it.get("filename", "?")
        findings.append({
            "path": rel,
            "line": it.get("location", {}).get("row", 0),
            "kind": kind_map.get(code, code),
            "name": it.get("message", ""),
            "confidence": 100,  # ruff is deterministic
            "tool": "ruff",
            "action": {
                "type": "delete",
                "auto_fixable": code in ("F401", "F841"),
            },
        })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=True, help="file with newline-separated relative paths")
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-confidence", type=int, default=60,
                    help="vulture confidence floor (60=broad audit, 80=conservative)")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    targets_file = Path(args.targets)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Load targets to use for the dynamic-decorator scan.
    targets: list[Path] = []
    if targets_file.exists():
        for line in targets_file.read_text().splitlines():
            line = line.strip().lstrip("./")
            if line:
                p = (repo / line).resolve()
                if p.exists():
                    targets.append(p)
    if not targets:
        targets = list(repo.rglob("*.py"))

    # Build dynamic-callable whitelist for vulture.
    whitelist_names = build_whitelist(targets)
    whitelist_path = out.parent / "vulture_whitelist.py"
    whitelist_path.write_text("\n".join(whitelist_names) + "\n" if whitelist_names else "")

    vulture_findings = run_vulture(repo, targets_file, whitelist_path, args.min_confidence)
    ruff_findings = run_ruff(repo)

    payload = {
        "layer": "dead_code",
        "framework_hints": detect_framework_hints(repo),
        "whitelist_size": len(whitelist_names),
        "findings": vulture_findings + ruff_findings,
        "counts": {
            "vulture": len(vulture_findings),
            "ruff": len(ruff_findings),
            "total": len(vulture_findings) + len(ruff_findings),
        },
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"dead_code: {payload['counts']['total']} findings "
          f"(vulture={payload['counts']['vulture']}, ruff={payload['counts']['ruff']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
