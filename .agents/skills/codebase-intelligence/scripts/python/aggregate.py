#!/usr/bin/env python3
"""Python aggregator — merges the six layer JSONs into raw/python/aggregate.json.

Reads:
    <out-dir>/raw/python/dead_code.json
    <out-dir>/raw/python/duplication.json
    <out-dir>/raw/python/complexity.json
    <out-dir>/raw/python/dependencies.json
    <out-dir>/raw/python/boundaries.json
    <out-dir>/raw/python/hotspots.json

Writes:
    <out-dir>/raw/python/aggregate.json   — Python section for the top-level aggregator

Output shape:
    {
      "lang": "python",
      "python_files": N,
      "python_loc": N,
      "summary": { ...all summary fields... },
      "findings": { ...all findings fields... },
      "warnings": [...]
    }

Note: verdict, schema_version, and repo are NOT included here — those belong
to the top-level aggregate_all.py aggregator.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"error": True, "reason": "invalid JSON"}


def safe_get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def count_python_loc(repo: Path) -> tuple[int, int]:
    """Count .py files and total LOC (excluding common vendored dirs)."""
    skip = {".venv", "venv", "build", "dist", "node_modules", "__pycache__", ".git"}
    files = 0
    loc = 0
    for p in repo.rglob("*.py"):
        if any(part in skip for part in p.parts):
            continue
        files += 1
        try:
            loc += sum(1 for _ in p.open(encoding="utf-8", errors="ignore"))
        except OSError:
            pass
    return files, loc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--scope", default="full")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    repo = Path(args.repo).resolve()
    raw_python = out_dir / "raw" / "python"
    raw_python.mkdir(parents=True, exist_ok=True)

    dead_code = load(raw_python / "dead_code.json")
    duplication = load(raw_python / "duplication.json")
    complexity = load(raw_python / "complexity.json")
    dependencies = load(raw_python / "dependencies.json")
    boundaries = load(raw_python / "boundaries.json")
    hotspots = load(raw_python / "hotspots.json")

    # Collect warnings from skipped/errored layers
    warnings: list[str] = []
    for name, layer in [
        ("dead_code", dead_code), ("duplication", duplication),
        ("complexity", complexity), ("dependencies", dependencies),
        ("boundaries", boundaries), ("hotspots", hotspots),
    ]:
        if layer.get("error"):
            warnings.append(f"layer `{name}` failed — see raw/python/{name}.err")
        if layer.get("skipped"):
            warnings.append(f"layer `{name}` skipped: {layer.get('reason', 'unknown')}")

    py_files, py_loc = count_python_loc(repo)
    duplicated_lines = safe_get(duplication, "counts", "duplicated_lines", default=0)
    dup_rate = round(100.0 * duplicated_lines / py_loc, 2) if py_loc else 0.0

    # Count critical complexity (CC >= 25)
    critical = sum(
        1 for item in complexity.get("findings", [])
        if item.get("verdict") == "above_threshold"
    )

    dep_findings = dependencies.get("findings", [])
    unused_deps = sum(1 for d in dep_findings if d.get("kind") == "unused")
    missing_deps = sum(1 for d in dep_findings if d.get("kind") == "missing_from_pyproject")

    boundary_findings = boundaries.get("findings", [])
    boundary_violations = sum(1 for b in boundary_findings if b.get("kind") == "boundary_violation")
    circular_cycles = sum(1 for b in boundary_findings if b.get("kind") == "circular_import")

    hotspot_top = [
        {"path": h["path"], "score": h["score"]}
        for h in hotspots.get("findings", [])[:5]
    ]

    summary = {
        "dead_code_count": dead_code.get("counts", {}).get("total", 0),
        "duplication_clone_groups": duplication.get("counts", {}).get("clone_groups", 0),
        "duplicated_lines": duplicated_lines,
        "duplication_rate_pct": dup_rate,
        "functions_above_cc_threshold": complexity.get("counts", {}).get("total", 0),
        "functions_at_critical_complexity": critical,
        "avg_maintainability_index": safe_get(complexity, "summary", "avg_maintainability_index"),
        "maintainability_grade": safe_get(complexity, "summary", "maintainability_grade", default="N/A"),
        "unused_dependencies": unused_deps,
        "missing_dependencies": missing_deps,
        "boundary_violations": boundary_violations,
        "circular_import_cycles": circular_cycles,
        "hotspots_top_risk": hotspot_top,
    }

    result = {
        "lang": "python",
        "python_files": py_files,
        "python_loc": py_loc,
        "summary": summary,
        "findings": {
            "dead_code": dead_code.get("findings", []),
            "duplication": duplication.get("findings", []),
            "complexity": complexity.get("findings", []),
            "dependencies": dependencies.get("findings", []),
            "boundaries": boundaries.get("findings", []),
            "hotspots": hotspots.get("findings", []),
        },
        "warnings": warnings,
    }

    (raw_python / "aggregate.json").write_text(json.dumps(result, indent=2))

    print(f"python aggregate: {py_files} files, {py_loc} LOC, "
          f"dead_code={summary['dead_code_count']}, "
          f"critical_cc={critical}, "
          f"missing_deps={missing_deps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
