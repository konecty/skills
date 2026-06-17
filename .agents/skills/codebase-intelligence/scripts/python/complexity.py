#!/usr/bin/env python3
"""Layer 3 — Complexity metrics.

Uses radon for:
- Cyclomatic complexity (cc) — branching count per function
- Maintainability index (mi) — composite score per file, 0-100
- Halstead volume — code "size" by unique operators/operands

Thresholds (tunable):
- cyclomatic >= 10 → flagged
- cyclomatic >= 25 → above_threshold (contributes to FAIL verdict)
- maintainability_index < 20 → file flagged as "poor"
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

CC_WARN = 10
CC_FAIL = 25
MI_POOR = 20.0


def run_radon_cc(repo: Path) -> dict:
    """radon cc -j produces JSON keyed by file → list of function/method dicts."""
    args = ["radon", "cc", str(repo), "-j", "-s",
            "-e", "*/migrations/*,*/.venv/*,*/venv/*,*/build/*,*/dist/*"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {}
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def run_radon_mi(repo: Path) -> dict:
    """radon mi -j → JSON keyed by file → {mi: float, rank: 'A'|'B'|'C'}"""
    args = ["radon", "mi", str(repo), "-j", "-s",
            "-e", "*/migrations/*,*/.venv/*,*/venv/*,*/build/*,*/dist/*"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {}
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def run_radon_hal(repo: Path) -> dict:
    """radon hal -j → Halstead metrics per file."""
    args = ["radon", "hal", str(repo), "-j",
            "-e", "*/migrations/*,*/.venv/*,*/venv/*,*/build/*,*/dist/*"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {}
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    cc_data = run_radon_cc(repo)
    mi_data = run_radon_mi(repo)
    hal_data = run_radon_hal(repo)

    findings: list[dict] = []
    above_threshold = 0
    flagged_files = 0
    mi_scores: list[float] = []

    for file_path, items in cc_data.items():
        if isinstance(items, dict) and items.get("error"):
            continue
        try:
            rel = str(Path(file_path).resolve().relative_to(repo))
        except ValueError:
            rel = file_path

        mi_for_file = mi_data.get(file_path, {})
        mi_value = mi_for_file.get("mi") if isinstance(mi_for_file, dict) else None
        if isinstance(mi_value, (int, float)):
            mi_scores.append(float(mi_value))
            if mi_value < MI_POOR:
                flagged_files += 1

        hal_for_file = hal_data.get(file_path, {})
        hal_total = hal_for_file.get("total", {}) if isinstance(hal_for_file, dict) else {}
        hal_volume = hal_total.get("volume") if isinstance(hal_total, dict) else None

        for func in items:
            cc = func.get("complexity", 0)
            if cc < CC_WARN:
                continue
            verdict = "above_threshold" if cc >= CC_FAIL else "warn"
            if verdict == "above_threshold":
                above_threshold += 1
            findings.append({
                "path": rel,
                "function": func.get("name"),
                "line": func.get("lineno", 0),
                "cyclomatic": cc,
                "rank": func.get("rank"),
                "maintainability_index": mi_value,
                "halstead_volume": hal_volume,
                "verdict": verdict,
            })

    avg_mi = round(sum(mi_scores) / len(mi_scores), 1) if mi_scores else None

    def grade(mi: float | None) -> str:
        if mi is None:
            return "N/A"
        if mi >= 85:
            return "A"
        if mi >= 65:
            return "B"
        if mi >= 20:
            return "C"
        return "F"

    payload = {
        "layer": "complexity",
        "findings": findings,
        "counts": {
            "above_threshold": above_threshold,
            "warn": len(findings) - above_threshold,
            "total": len(findings),
            "files_with_poor_mi": flagged_files,
        },
        "summary": {
            "avg_maintainability_index": avg_mi,
            "maintainability_grade": grade(avg_mi),
        },
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"complexity: {len(findings)} functions flagged "
          f"({above_threshold} above_threshold), avg MI={avg_mi}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
