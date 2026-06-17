#!/usr/bin/env python3
"""Layer 5 (Python) — known-vulnerable dependencies (SCA).

Strategy, in order of preference:
1. osv-scanner on the repo (covers uv.lock, poetry.lock, requirements.txt,
   Pipfile.lock — and flags OSV `MAL-` malicious-package advisories).
2. pip-audit (PATH or `uvx pip-audit`) against requirements.txt, or against
   a temporary export of uv.lock (`uv export --format requirements-txt`).

Both need network access (OSV / PyPI advisory APIs). Offline → layer is
skipped with an explicit warning, never silently green.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def severity_from_osv(vuln: dict) -> str:
    """Normalise the GHSA-style severity OSV carries in database_specific."""
    ds = (vuln.get("database_specific") or {}).get("severity", "")
    return {"CRITICAL": "critical", "HIGH": "high", "MODERATE": "medium",
            "MEDIUM": "medium", "LOW": "low"}.get(ds.upper(), "unknown")


def run_osv_scanner(repo: Path) -> tuple[list[dict] | None, str | None]:
    if not shutil.which("osv-scanner"):
        return None, None
    # v2 dialect first, then v1.
    for args in (
        ["osv-scanner", "scan", "source", "-r", "--format", "json", str(repo)],
        ["osv-scanner", "--recursive", "--format", "json", str(repo)],
    ):
        try:
            result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=600)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None, "osv-scanner timed out or vanished"
        # exit 1 = vulns found (still valid JSON); 127/128 = bad CLI dialect
        if result.stdout.strip().startswith("{"):
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                continue
            findings = []
            for res in data.get("results", []):
                source = res.get("source", {}).get("path", "")
                for pkg in res.get("packages", []):
                    info = pkg.get("package", {})
                    if info.get("ecosystem") not in ("PyPI", ""):
                        continue
                    for vuln in pkg.get("vulnerabilities", []):
                        vid = vuln.get("id", "?")
                        aliases = vuln.get("aliases", []) or []
                        is_malicious = vid.startswith("MAL-") or any(a.startswith("MAL-") for a in aliases)
                        findings.append({
                            "package": info.get("name", "?"),
                            "version": info.get("version", "?"),
                            "vuln_id": vid,
                            "aliases": aliases,
                            "severity": "critical" if is_malicious else severity_from_osv(vuln),
                            "malicious": is_malicious,
                            "summary": (vuln.get("summary") or "")[:200],
                            "fixed_in": _osv_fixed_versions(vuln, info.get("name", "")),
                            "manifest": source,
                            "tool": "osv-scanner",
                        })
            return findings, None
    return None, "osv-scanner present but both CLI dialects failed"


def _osv_fixed_versions(vuln: dict, pkg: str) -> list[str]:
    fixed = []
    for aff in vuln.get("affected", []) or []:
        if aff.get("package", {}).get("name", "").lower() != pkg.lower():
            continue
        for r in aff.get("ranges", []) or []:
            for ev in r.get("events", []) or []:
                if "fixed" in ev:
                    fixed.append(ev["fixed"])
    return sorted(set(fixed))[:3]


def pip_audit_cmd() -> list[str] | None:
    if shutil.which("pip-audit"):
        return ["pip-audit"]
    if shutil.which("uvx"):
        return ["uvx", "pip-audit"]
    return None


def requirements_source(repo: Path) -> tuple[Path | None, bool, str | None]:
    """Return (requirements file, is_temporary, warning)."""
    req = repo / "requirements.txt"
    if req.exists():
        return req, False, None
    if (repo / "uv.lock").exists() and shutil.which("uv"):
        tmp = Path(tempfile.mkstemp(suffix="-requirements.txt")[1])
        result = subprocess.run(
            ["uv", "export", "--format", "requirements-txt", "--no-emit-project",
             "--no-hashes", "-o", str(tmp)],
            cwd=str(repo), capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            return tmp, True, None
        tmp.unlink(missing_ok=True)
        return None, False, f"uv export failed: {result.stderr[:200]}"
    return None, False, "no requirements.txt and no uv.lock+uv to export from"


def run_pip_audit(repo: Path) -> tuple[list[dict] | None, str | None]:
    cmd = pip_audit_cmd()
    if cmd is None:
        return None, "pip-audit not available (install pip-audit, or uv for uvx fallback)"
    req, temporary, warn = requirements_source(repo)
    if req is None:
        return None, warn
    try:
        # --no-deps --disable-pip works on fully pinned files (uv/poetry
        # exports always are) without building a venv. Unpinned hand-written
        # requirements need the slower venv-based resolution — retry without
        # the fast-path flags if pinning is the complaint.
        base = cmd + ["-r", str(req), "--format", "json", "--progress-spinner", "off"]
        result = subprocess.run(
            base + ["--no-deps", "--disable-pip"],
            capture_output=True, text=True, check=False, timeout=600,
        )
        if result.returncode and "pinned" in (result.stderr or "").lower():
            result = subprocess.run(base, capture_output=True, text=True,
                                    check=False, timeout=600)
    except subprocess.TimeoutExpired:
        return None, "pip-audit timed out (network?)"
    finally:
        if temporary:
            req.unlink(missing_ok=True)
    if not result.stdout.strip().startswith("{") and not result.stdout.strip().startswith("["):
        return None, f"pip-audit failed: {(result.stderr or result.stdout)[:300]}"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, "pip-audit emitted invalid JSON"

    deps = data.get("dependencies", data if isinstance(data, list) else [])
    findings = []
    for dep in deps:
        for v in dep.get("vulns", []):
            findings.append({
                "package": dep.get("name", "?"),
                "version": dep.get("version", "?"),
                "vuln_id": v.get("id", "?"),
                "aliases": v.get("aliases", []),
                "severity": "unknown",  # pip-audit JSON has no severity field
                "malicious": False,
                "summary": (v.get("description") or "")[:200],
                "fixed_in": v.get("fix_versions", []),
                "manifest": "requirements.txt|uv.lock",
                "tool": "pip-audit",
            })
    return findings, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False)  # unused; manifest-level layer
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    findings, warn = run_osv_scanner(repo)
    tool = "osv-scanner"
    if warn:
        warnings.append(warn)
    if findings is None:
        findings, warn = run_pip_audit(repo)
        tool = "pip-audit"
        if warn:
            warnings.append(warn)

    if findings is None:
        payload = {
            "layer": "vuln_deps", "skipped": True,
            "reason": "; ".join(warnings) or "no SCA tool available",
            "findings": [], "counts": {"total": 0}, "warnings": warnings,
        }
        out.write_text(json.dumps(payload, indent=2))
        print(f"vuln_deps(py): SKIPPED — {payload['reason']}")
        return 0

    by_sev = {s: sum(1 for f in findings if f["severity"] == s)
              for s in ("critical", "high", "medium", "low", "unknown")}
    payload = {
        "layer": "vuln_deps",
        "tool": tool,
        "findings": findings,
        "counts": {
            "total": len(findings),
            "malicious": sum(1 for f in findings if f["malicious"]),
            "fixable": sum(1 for f in findings if f["fixed_in"]),
            "by_severity": by_sev,
        },
        "warnings": warnings,
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"vuln_deps(py): {len(findings)} vulns via {tool} "
          f"(critical={by_sev['critical']}, high={by_sev['high']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
