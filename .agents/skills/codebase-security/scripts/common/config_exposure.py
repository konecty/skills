#!/usr/bin/env python3
"""Layer 3 — Configuration & exposure hygiene (language-agnostic).

Checks things scanners aimed at code miss:
- sensitive files tracked by git (.env, private keys, keystores, service
  accounts, .npmrc/.pypirc/.netrc with credentials)
- Dockerfile risks (no USER → runs as root, curl|sh, ADD from URL, TLS off)
- docker-compose risks (privileged, host network)
- GitHub Actions: pull_request_target + checkout of the PR head (classic
  secrets-exfiltration vector)
- permissive CORS and debug flags in app config (cross-language regexes)

Only files tracked by git are flagged in the sensitive-files check — an
untracked local .env is correct practice, a committed one is an incident.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SENSITIVE_FILE_RULES: list[tuple[str, str, re.Pattern]] = [
    ("tracked-dotenv", "high", re.compile(r"(^|/)\.env(\.local|\.production|\.prod|\.staging|\.dev(elopment)?|\.test)?$")),
    ("tracked-private-key", "high", re.compile(r"(^|/)(id_rsa|id_ed25519|id_ecdsa)(\.|$)|\.(pem|key|p12|pfx|jks|keystore)$")),
    ("tracked-cloud-credentials", "high", re.compile(r"(?i)(^|/)(service[-_]?account.*\.json|credentials(\.json)?|\.aws/credentials|gcloud.*\.json)$")),
    ("tracked-package-manager-auth", "high", re.compile(r"(^|/)(\.npmrc|\.pypirc|\.netrc)$")),
    ("tracked-db-dump", "medium", re.compile(r"\.(sql\.gz|dump|rdb)$")),
]
DOTENV_TEMPLATE = re.compile(r"\.(example|sample|template|dist|defaults)$|^\.env\.example")

CODE_CONFIG_RULES: list[tuple[str, str, str, re.Pattern]] = [
    # (rule, severity, message, pattern)
    ("cors-wildcard", "medium", "CORS allows any origin",
     re.compile(r"""allow_origins\s*=\s*\[\s*["']\*["']|Access-Control-Allow-Origin["']?\s*[,:]\s*["']\*|origin:\s*["']\*["']|CORS_ALLOW_ALL_ORIGINS\s*=\s*True|CORS_ORIGIN_ALLOW_ALL\s*=\s*True""")),
    ("debug-enabled", "medium", "Debug mode enabled in code (verify it is not the production path)",
     re.compile(r"\bDEBUG\s*=\s*True\b|app\.run\([^)]*debug\s*=\s*True|debug:\s*true\b")),
    ("tls-verification-disabled", "high", "TLS certificate verification disabled",
     re.compile(r"rejectUnauthorized:\s*false|NODE_TLS_REJECT_UNAUTHORIZED.{0,10}0|PYTHONHTTPSVERIFY.{0,10}0")),
    ("bind-all-interfaces", "low", "Service binds 0.0.0.0 (fine in containers, risky on hosts)",
     re.compile(r"""["']0\.0\.0\.0["']""")),
]

CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".json"}
EXCLUDE_PARTS = {".git", "node_modules", ".venv", "venv", "dist", "build", ".security-audit", ".codebase-audit", ".agents"}
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec|fixtures|e2e)(/|$)|_test\.|\.test\.|\.spec\.")


def git_tracked_files(repo: Path) -> list[str]:
    try:
        out = subprocess.check_output(["git", "ls-files"], cwd=str(repo), text=True)
        return [line for line in out.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def check_sensitive_files(repo: Path, tracked: list[str]) -> list[dict]:
    findings = []
    for path in tracked:
        if DOTENV_TEMPLATE.search(path):
            continue
        for rule, severity, pattern in SENSITIVE_FILE_RULES:
            if not pattern.search(path):
                continue
            # Confirm content for ambiguous extensions: a .pem with only a
            # certificate (no private key) is public material.
            sev = severity
            full = repo / path
            if path.endswith((".pem", ".key", ".json")) and full.exists():
                try:
                    head = full.read_text(errors="ignore")[:4096]
                except OSError:
                    head = ""
                if path.endswith((".pem", ".key")) and "PRIVATE KEY" not in head:
                    sev = "info"
                if path.endswith(".json") and "private_key" not in head and rule == "tracked-cloud-credentials":
                    sev = "low"
            findings.append({
                "path": path, "line": 0, "rule": rule, "severity": sev,
                "message": f"Sensitive file tracked by git ({rule})",
                "tool": "config-exposure",
                "remediation": "git rm --cached, add to .gitignore, rotate any contained credentials.",
            })
            break
    return findings


def check_dockerfiles(repo: Path, tracked: list[str]) -> list[dict]:
    findings = []
    for path in tracked:
        name = Path(path).name
        if not (name == "Dockerfile" or name.startswith("Dockerfile.")):
            continue
        full = repo / path
        try:
            text = full.read_text(errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()
        if not re.search(r"(?m)^\s*USER\s+(?!root\b)\S+", text):
            findings.append({
                "path": path, "line": 0, "rule": "docker-runs-as-root", "severity": "medium",
                "message": "No USER instruction — container runs as root",
                "tool": "config-exposure",
                "remediation": "Add a non-root USER after installing dependencies.",
            })
        for i, line in enumerate(lines, 1):
            if re.search(r"(curl|wget)[^|\n]*\|\s*(ba|z|da)?sh\b", line):
                findings.append({
                    "path": path, "line": i, "rule": "docker-curl-pipe-sh", "severity": "medium",
                    "message": "Pipes a downloaded script straight into a shell",
                    "tool": "config-exposure",
                    "remediation": "Download, checksum-verify, then execute.",
                })
            if re.search(r"(?i)^\s*ADD\s+https?://", line):
                findings.append({
                    "path": path, "line": i, "rule": "docker-add-from-url", "severity": "low",
                    "message": "ADD from URL — no integrity check",
                    "tool": "config-exposure",
                    "remediation": "Use curl with checksum verification instead of ADD <url>.",
                })
            if re.search(r"--no-check-certificate|\bcurl\b[^|\n]*\s-k\b", line):
                findings.append({
                    "path": path, "line": i, "rule": "docker-tls-disabled", "severity": "high",
                    "message": "TLS verification disabled in build step",
                    "tool": "config-exposure",
                    "remediation": "Remove the insecure flag; fix the underlying CA issue.",
                })
    return findings


def check_compose(repo: Path, tracked: list[str]) -> list[dict]:
    findings = []
    for path in tracked:
        if not re.search(r"(^|/)(docker-)?compose[^/]*\.ya?ml$", path):
            continue
        try:
            lines = (repo / path).read_text(errors="ignore").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            if re.search(r"^\s*privileged:\s*true", line):
                findings.append({
                    "path": path, "line": i, "rule": "compose-privileged", "severity": "high",
                    "message": "privileged: true grants the container full host access",
                    "tool": "config-exposure",
                    "remediation": "Drop privileged; grant the specific capability needed (cap_add).",
                })
            if re.search(r"^\s*network_mode:\s*[\"']?host", line):
                findings.append({
                    "path": path, "line": i, "rule": "compose-host-network", "severity": "medium",
                    "message": "host network mode bypasses container network isolation",
                    "tool": "config-exposure",
                    "remediation": "Use port mappings instead of host networking.",
                })
    return findings


def check_github_actions(repo: Path, tracked: list[str]) -> list[dict]:
    findings = []
    for path in tracked:
        if not re.search(r"^\.github/workflows/[^/]+\.ya?ml$", path):
            continue
        try:
            text = (repo / path).read_text(errors="ignore")
        except OSError:
            continue
        if "pull_request_target" in text and re.search(
            r"ref:\s*\$\{\{\s*github\.event\.pull_request\.head", text
        ):
            findings.append({
                "path": path, "line": 0, "rule": "actions-prt-checkout", "severity": "high",
                "message": "pull_request_target + checkout of PR head: untrusted code runs with repo secrets",
                "tool": "config-exposure",
                "remediation": "Use pull_request, or split the privileged step into a separate workflow.",
            })
    return findings


def check_code_config(repo: Path, tracked: list[str]) -> list[dict]:
    findings = []
    for path in tracked:
        p = Path(path)
        if p.suffix not in CODE_EXTENSIONS:
            continue
        if any(part in EXCLUDE_PARTS for part in p.parts):
            continue
        full = repo / path
        try:
            if full.stat().st_size > 500_000:
                continue
            lines = full.read_text(errors="ignore").splitlines()
        except OSError:
            continue
        in_test = bool(TEST_PATH.search(path))
        for i, line in enumerate(lines, 1):
            for rule, severity, message, pattern in CODE_CONFIG_RULES:
                if pattern.search(line):
                    findings.append({
                        "path": path, "line": i, "rule": rule,
                        "severity": "info" if in_test else severity,
                        "message": message,
                        "tool": "config-exposure",
                        "remediation": "",
                    })
                    break
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False)  # unused; uniform layer interface
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    tracked = git_tracked_files(repo)
    if not tracked:
        out.write_text(json.dumps({
            "layer": "config_exposure", "skipped": True,
            "reason": "not a git repository (sensitive-file check needs `git ls-files`)",
            "findings": [], "counts": {"total": 0},
        }, indent=2))
        print("config_exposure: skipped (no git)")
        return 0

    findings = (
        check_sensitive_files(repo, tracked)
        + check_dockerfiles(repo, tracked)
        + check_compose(repo, tracked)
        + check_github_actions(repo, tracked)
        + check_code_config(repo, tracked)
    )
    by_sev = {s: sum(1 for f in findings if f["severity"] == s)
              for s in ("high", "medium", "low", "info")}
    payload = {
        "layer": "config_exposure",
        "tool": "config-exposure",
        "findings": findings,
        "counts": {"total": len(findings), **by_sev},
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"config_exposure: {len(findings)} findings "
          f"(high={by_sev['high']}, medium={by_sev['medium']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
