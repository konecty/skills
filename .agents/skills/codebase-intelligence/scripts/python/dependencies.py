#!/usr/bin/env python3
"""Layer 4 — Dependency hygiene.

Uses deptry to detect:
- DEP001 missing dependencies (imported but not declared)
- DEP002 unused dependencies (declared but not imported)
- DEP003 transitive dependencies (imported but only available transitively)
- DEP004 dev-only dependencies used in production code

Skipped gracefully when no pyproject.toml/requirements.txt is present.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

KIND_MAP = {
    "DEP001": "missing_from_pyproject",
    "DEP002": "unused",
    "DEP003": "transitive",
    "DEP004": "dev_in_prod",
    "DEP005": "stdlib_misclassified",
}


def has_dep_manifest(repo: Path) -> bool:
    for fname in ("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile"):
        if (repo / fname).exists():
            return True
    return False


def run_deptry(repo: Path) -> list[dict]:
    # Use "." (relative) so pyproject.toml exclude patterns match relative paths.
    # Passing an absolute path causes deptry to compare absolute paths against
    # relative exclude regexes, silently skipping all exclusions.
    args = ["deptry", ".", "--json-output", "/dev/stdout", "--no-ansi"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False, cwd=str(repo))
    except FileNotFoundError:
        return []
    # deptry prints the JSON among its other output; find the JSON array
    output = result.stdout.strip()
    if not output:
        return []
    # deptry's --json-output writes pure JSON; if it merged with stderr we still get JSON
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        # try to find the JSON substring
        start = output.find("[")
        end = output.rfind("]")
        if start == -1 or end == -1:
            return []
        try:
            data = json.loads(output[start:end + 1])
        except json.JSONDecodeError:
            return []

    if not isinstance(data, list):
        return []
    return data


def normalize(item: dict) -> dict:
    code = item.get("error", {}).get("code") or item.get("code", "")
    module = item.get("module") or item.get("error", {}).get("module", "")
    location = item.get("location") or {}
    return {
        "name": module,
        "kind": KIND_MAP.get(code, code or "unknown"),
        "path": location.get("file"),
        "line": location.get("line"),
        "tool": "deptry",
        "raw_code": code,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not has_dep_manifest(repo):
        payload = {
            "layer": "dependencies",
            "skipped": True,
            "reason": "no dependency manifest found (pyproject.toml / requirements.txt / etc.)",
            "findings": [],
            "counts": {"total": 0},
        }
        out.write_text(json.dumps(payload, indent=2))
        print("dependencies: skipped (no manifest)")
        return 0

    raw = run_deptry(repo)
    findings = [normalize(it) for it in raw]

    by_kind: dict[str, int] = {}
    for f in findings:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1

    payload = {
        "layer": "dependencies",
        "findings": findings,
        "counts": {
            "total": len(findings),
            "by_kind": by_kind,
            "missing": by_kind.get("missing_from_pyproject", 0),
            "unused": by_kind.get("unused", 0),
        },
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"dependencies: {len(findings)} issues "
          f"(missing={by_kind.get('missing_from_pyproject', 0)}, "
          f"unused={by_kind.get('unused', 0)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
