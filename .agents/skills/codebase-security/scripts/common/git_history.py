#!/usr/bin/env python3
"""Layer 2 — Secrets in git history.

A secret deleted from the working tree still lives in every clone's history.
This layer runs `gitleaks git` over the full commit log and reports secrets
that are NOT present in the current tree (those are layer 1's job).

Requires gitleaks — there is no cheap builtin fallback for history scanning
(replaying `git log -p` through regexes is too slow for real repos). When
gitleaks is missing the layer emits `skipped` with an install hint.

Secret values are always redacted (first 4 chars + length).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def redact(value: str) -> str:
    return f"{value[:4]}…({len(value)} chars)"


def skipped(out: Path, reason: str) -> int:
    out.write_text(json.dumps({
        "layer": "git_history",
        "skipped": True,
        "reason": reason,
        "findings": [],
        "counts": {"total": 0},
    }, indent=2))
    print(f"git_history: skipped ({reason})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False)  # unused; uniform layer interface
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-commits", type=int, default=0, help="0 = full history")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not (repo / ".git").exists():
        return skipped(out, "not a git repository")
    if not shutil.which("gitleaks"):
        return skipped(out, "gitleaks not installed — install: brew install gitleaks")

    report = Path(tempfile.mkstemp(suffix=".json")[1])
    log_opts = f"--max-count={args.max_commits}" if args.max_commits else ""
    # gitleaks >= 8.19 uses `git`; older releases use `detect` (git mode is default).
    attempts = [
        ["gitleaks", "git", str(repo), "--report-format", "json",
         "--report-path", str(report), "--exit-code", "0", "--no-banner"],
        ["gitleaks", "detect", "-s", str(repo), "--report-format", "json",
         "--report-path", str(report), "--exit-code", "0", "--no-banner"],
    ]
    if log_opts:
        attempts = [a + ["--log-opts", log_opts] for a in attempts]

    items = None
    for cmd in attempts:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0 and report.exists():
            try:
                items = json.loads(report.read_text() or "[]")
                break
            except json.JSONDecodeError:
                continue
    report.unlink(missing_ok=True)
    if items is None:
        return skipped(out, "gitleaks failed in both CLI dialects — see .err file")

    findings = []
    for it in items:
        path = it.get("File", "?")
        in_current_tree = (repo / path).exists()
        findings.append({
            "path": path,
            "line": it.get("StartLine", 0),
            "rule": it.get("RuleID", "unknown"),
            "severity": "high" if not in_current_tree else "info",
            "commit": (it.get("Commit") or "")[:12],
            "commit_date": it.get("Date", ""),
            "author": it.get("Email", ""),
            "still_in_tree": in_current_tree,
            "secret_redacted": redact(it.get("Secret", "")),
            "tool": "gitleaks",
            "remediation": (
                "Rotate the credential. To purge history use `git filter-repo` "
                "(coordinate with the team — it rewrites every clone)."
            ),
        })

    # Findings still in the current tree are layer 1 duplicates; keep them as
    # info so the aggregator can dedupe, but count only history-only leaks.
    history_only = [f for f in findings if not f["still_in_tree"]]
    payload = {
        "layer": "git_history",
        "tool": "gitleaks",
        "findings": findings,
        "counts": {
            "total": len(findings),
            "history_only": len(history_only),
            "also_in_current_tree": len(findings) - len(history_only),
        },
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"git_history: {len(history_only)} history-only leaks "
          f"({len(findings)} total matches)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
