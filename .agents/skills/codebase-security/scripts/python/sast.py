#!/usr/bin/env python3
"""Layer 4 (Python) — SAST: insecure code patterns.

Primary tool: bandit (PATH, or `uvx bandit` when uv is installed — no global
install required). Optional second pass: semgrep with the registry security
ruleset when semgrep is on PATH (needs network on first run to fetch rules).

Findings carry bandit's severity AND confidence — the aggregator only fails
the build on HIGH severity with HIGH/MEDIUM confidence outside tests.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|fixtures)(/|$)|_test\.py$|^test_")
# Glob-anchored: a bare "test" would also exclude any repo whose *path*
# contains the substring (e.g. /tmp/sec-test) — bandit matches substrings.
EXCLUDES = ("*/tests/*,*/test/*,*/.venv/*,*/venv/*,*/node_modules/*,"
            "*/build/*,*/dist/*,*/migrations/*,*/.security-audit/*")


def bandit_cmd() -> list[str] | None:
    if shutil.which("bandit"):
        return ["bandit"]
    if shutil.which("uvx"):
        return ["uvx", "bandit"]
    return None


def run_bandit(repo: Path, targets: list[str]) -> tuple[list[dict], str | None]:
    cmd = bandit_cmd()
    if cmd is None:
        return [], "bandit not available (install bandit, or install uv for uvx fallback)"
    scan_paths = targets if targets else ["-r", str(repo)]
    if targets:
        scan_paths = targets  # bandit accepts explicit file lists without -r
    args = cmd + scan_paths + ["-f", "json", "-q", "-x", EXCLUDES]
    if not targets:
        args = cmd + ["-r", str(repo), "-f", "json", "-q", "-x", EXCLUDES]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=600)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return [], f"bandit failed: {e}"
    if not result.stdout.strip():
        return [], f"bandit produced no output (stderr: {result.stderr[:200]})"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [], "bandit emitted invalid JSON"

    findings = []
    for it in data.get("results", []):
        path = it.get("filename", "?")
        try:
            path = str(Path(path).resolve().relative_to(repo))
        except ValueError:
            pass
        cwe = it.get("issue_cwe") or {}
        message = it.get("issue_text", "")
        # B105/B106/B107 quote the hardcoded password verbatim — redact it
        # so the secret never lands in the report.
        if it.get("test_id") in ("B105", "B106", "B107"):
            message = re.sub(r"'[^']{4,}'", lambda m: f"'{m.group(0)[1:5]}…(redacted)'", message)
        findings.append({
            "path": path,
            "line": it.get("line_number", 0),
            "rule": it.get("test_id", "?"),
            "rule_name": it.get("test_name", ""),
            "severity": it.get("issue_severity", "LOW").lower(),
            "confidence": it.get("issue_confidence", "LOW").lower(),
            "message": message,
            "cwe": f"CWE-{cwe.get('id')}" if cwe.get("id") else "",
            "in_test_file": bool(TEST_PATH.search(path)),
            "tool": "bandit",
            "url": it.get("more_info", ""),
        })
    return findings, None


def run_semgrep(repo: Path) -> tuple[list[dict], str | None]:
    """Optional second engine — only when semgrep is already on PATH."""
    if not shutil.which("semgrep"):
        return [], None  # not a warning; semgrep is opt-in extra coverage
    args = ["semgrep", "scan", "--config", "p/security-audit", "--json", "--quiet",
            "--metrics", "off", "--timeout", "120", str(repo)]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=900)
        data = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return [], "semgrep present but failed (offline? rules fetch needs network) — bandit results stand alone"

    sev_map = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}
    findings = []
    for it in data.get("results", []):
        path = it.get("path", "?")
        try:
            path = str(Path(path).resolve().relative_to(repo))
        except ValueError:
            pass
        if not path.endswith(".py"):
            continue
        extra = it.get("extra", {})
        findings.append({
            "path": path,
            "line": it.get("start", {}).get("line", 0),
            "rule": it.get("check_id", "?"),
            "rule_name": it.get("check_id", "?").split(".")[-1],
            "severity": sev_map.get(extra.get("severity", "INFO"), "low"),
            "confidence": "medium",
            "message": extra.get("message", "")[:300],
            "cwe": (extra.get("metadata", {}).get("cwe") or [""])[0][:8] if isinstance(extra.get("metadata", {}).get("cwe"), list) else "",
            "in_test_file": bool(TEST_PATH.search(path)),
            "tool": "semgrep",
            "url": "",
        })
    return findings, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Targets file absent = full scan; present = diff scope (no .py → skip).
    diff_scope = bool(args.targets) and Path(args.targets).exists()
    targets: list[str] = []
    if diff_scope:
        targets = [
            str((repo / line.strip()).resolve())
            for line in Path(args.targets).read_text().splitlines()
            if line.strip().endswith(".py") and (repo / line.strip()).exists()
        ]
        if not targets:
            out.write_text(json.dumps({
                "layer": "sast", "skipped": True,
                "reason": "no changed Python files in scope",
                "findings": [], "counts": {"total": 0},
            }, indent=2))
            print("sast(py): skipped (no changed .py files)")
            return 0

    warnings: list[str] = []
    bandit_findings, w = run_bandit(repo, targets)
    if w:
        warnings.append(w)
    semgrep_findings, w = run_semgrep(repo) if not targets else ([], None)
    if w:
        warnings.append(w)

    # Dedupe: same path+line reported by both engines → keep bandit's.
    seen = {(f["path"], f["line"]) for f in bandit_findings}
    findings = bandit_findings + [
        f for f in semgrep_findings if (f["path"], f["line"]) not in seen
    ]

    if not findings and warnings and "bandit" in warnings[0]:
        payload = {
            "layer": "sast", "skipped": True, "reason": warnings[0],
            "findings": [], "counts": {"total": 0}, "warnings": warnings,
        }
    else:
        high = sum(1 for f in findings
                   if f["severity"] == "high" and f["confidence"] in ("high", "medium")
                   and not f["in_test_file"])
        payload = {
            "layer": "sast",
            "tools": sorted({f["tool"] for f in findings}) or ["bandit"],
            "findings": findings,
            "counts": {
                "total": len(findings),
                "high_actionable": high,
                "by_severity": {s: sum(1 for f in findings if f["severity"] == s)
                                for s in ("high", "medium", "low")},
            },
            "warnings": warnings,
        }
    out.write_text(json.dumps(payload, indent=2))
    print(f"sast(py): {payload['counts']['total']} findings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
