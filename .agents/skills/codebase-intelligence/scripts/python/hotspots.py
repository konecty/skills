#!/usr/bin/env python3
"""Layer 6 — Hotspots (churn × complexity).

A "hotspot" is a file that is BOTH changing often AND complex. These are
the highest-leverage refactor targets: investing here pays compound interest
because the team keeps editing them.

Formula:
    score = log(1 + commits_last_90d) * max_cyclomatic_in_file

Files with score above the 90th percentile are flagged as `refactor_target`.

If the repo is a shallow clone (fewer than 30 commits), this layer warns
and emits an empty findings list — the user should run `git fetch --unshallow`.
"""
from __future__ import annotations
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from collections import Counter

SHALLOW_THRESHOLD = 30
WINDOW_DAYS = 90


def git_total_commits(repo: Path) -> int:
    try:
        out = subprocess.check_output(
            ["git", "rev-list", "--count", "HEAD"], cwd=str(repo), text=True
        )
        return int(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return 0


def git_churn(repo: Path) -> Counter:
    """Count commits per .py file in the last WINDOW_DAYS."""
    try:
        out = subprocess.check_output(
            ["git", "log", f"--since={WINDOW_DAYS}.days.ago",
             "--name-only", "--pretty=format:", "--", "*.py"],
            cwd=str(repo), text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Counter()

    counter: Counter = Counter()
    for line in out.splitlines():
        line = line.strip()
        if line and line.endswith(".py"):
            counter[line] += 1
    return counter


def max_cc_per_file(repo: Path) -> dict[str, int]:
    """Run `radon cc -j` and return max complexity per file."""
    args = ["radon", "cc", str(repo), "-j",
            "-e", "*/migrations/*,*/.venv/*,*/venv/*,*/build/*,*/dist/*"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {}
    if not result.stdout.strip():
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    out: dict[str, int] = {}
    for file_path, items in data.items():
        if not isinstance(items, list):
            continue
        try:
            rel = str(Path(file_path).resolve().relative_to(repo))
        except ValueError:
            rel = file_path
        complexities = [it.get("complexity", 0) for it in items]
        if complexities:
            out[rel] = max(complexities)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    total_commits = git_total_commits(repo)
    if total_commits == 0:
        payload = {
            "layer": "hotspots",
            "skipped": True,
            "reason": "not a git repository or git not available",
            "findings": [],
            "counts": {"total": 0},
        }
        out.write_text(json.dumps(payload, indent=2))
        print("hotspots: skipped (no git history)")
        return 0
    if total_commits < SHALLOW_THRESHOLD:
        payload = {
            "layer": "hotspots",
            "skipped": True,
            "reason": f"shallow clone ({total_commits} commits) — run `git fetch --unshallow`",
            "findings": [],
            "counts": {"total": 0},
        }
        out.write_text(json.dumps(payload, indent=2))
        print(f"hotspots: skipped (shallow clone, {total_commits} commits)")
        return 0

    churn = git_churn(repo)
    cc = max_cc_per_file(repo)

    scored: list[dict] = []
    for path, commits in churn.items():
        max_cc = cc.get(path, 1)
        score = round(math.log1p(commits) * max_cc, 2)
        scored.append({
            "path": path,
            "commits_last_90d": commits,
            "max_cyclomatic": max_cc,
            "score": score,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Mark the top 10% (or top 5, whichever is smaller) as refactor targets
    cutoff = max(5, int(len(scored) * 0.1)) if scored else 0
    for i, item in enumerate(scored):
        item["verdict"] = "refactor_target" if i < cutoff else "informational"

    payload = {
        "layer": "hotspots",
        "window_days": WINDOW_DAYS,
        "total_commits_in_repo": total_commits,
        "findings": scored[:50],  # cap at top 50 to keep JSON small
        "counts": {
            "total": len(scored),
            "refactor_targets": min(cutoff, len(scored)),
        },
    }
    out.write_text(json.dumps(payload, indent=2))
    top = scored[0]["path"] if scored else "—"
    print(f"hotspots: {len(scored)} files scored, top risk = {top}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
