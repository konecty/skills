#!/usr/bin/env python3
"""Layer 1 — Hardcoded secrets in the working tree.

Primary tool: gitleaks (`gitleaks dir` / `gitleaks detect --no-git`).
Fallback:     builtin regex scanner with entropy filtering — lower coverage
              than gitleaks but never silently skips the layer.

Secret values are ALWAYS redacted in the output: first 4 chars + length.
The raw value never reaches security.json, the Markdown report, or stdout.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXCLUDE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".security-audit", ".codebase-audit", ".mypy_cache", ".ruff_cache",
    ".pytest_cache", "coverage", ".next", ".turbo",
}
# Lockfiles and minified bundles: high-entropy by nature, near-zero signal.
EXCLUDE_FILES = re.compile(
    r"(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|uv\.lock|poetry\.lock|"
    r"Cargo\.lock|.*\.min\.(js|css)|.*\.map|.*\.svg|.*\.ipynb)$"
)
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec|fixtures|testdata)(/|$)|_test\.|\.test\.|\.spec\.")

PLACEHOLDER = re.compile(
    r"(?i)(example|sample|placeholder|changeme|change-me|your[_-]|dummy|fake|"
    r"xxx+|test[_-]?key|not[_-]?a[_-]?real|<[^>]+>|\$\{|\{\{|process\.env|os\.environ|"
    r"getenv|lorem|redacted|\*{3,})"
)
# Captured values that are obviously documentation stand-ins, not credentials.
DUMMY_VALUES = {
    "pass", "password", "passwd", "pwd", "secret", "senha", "user", "username",
    "test", "example", "changeme", "admin", "root", "foo", "bar", "baz",
    "1234", "12345", "123456", "abc123", "token", "apikey", "key", "value",
    "string", "mypassword", "yourpassword", "hunter2",
}

# (rule_id, severity, regex). Specific token formats are high severity;
# the generic assignment rule is medium and additionally entropy-gated.
PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("aws-access-key-id", "high", re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b")),
    ("github-token", "high", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b")),
    ("github-fine-grained-pat", "high", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b")),
    ("gitlab-pat", "high", re.compile(r"\bglpat-[A-Za-z0-9\-_]{20,}\b")),
    ("slack-token", "high", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b")),
    ("stripe-key", "high", re.compile(r"\b[rs]k_(?:live|test)_[0-9a-zA-Z]{20,}\b")),
    ("anthropic-key", "high", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b")),
    ("openai-key", "high", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9\-_]{20,}T3BlbkFJ[A-Za-z0-9\-_]{20,}\b")),
    ("google-api-key", "high", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("sendgrid-key", "high", re.compile(r"\bSG\.[A-Za-z0-9\-_]{22}\.[A-Za-z0-9\-_]{43}\b")),
    ("npm-token", "high", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("pypi-token", "high", re.compile(r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9\-_]{50,}\b")),
    ("private-key-block", "high", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY( BLOCK)?-----")),
    ("jwt", "medium", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b")),
    ("url-with-password", "high", re.compile(r"\b[a-z][a-z0-9+]*://[^/\s:@'\"]{1,64}:([^@\s'\"]{4,})@[^\s'\"]+")),
    # No leading \b: must also match prefixed names like aws_secret_key.
    # Value may be quoted (code) or bare (.env style).
    ("generic-assignment", "medium", re.compile(
        r"(?i)(?:api[_-]?key|api[_-]?secret|secret[_-]?key|access[_-]?token|auth[_-]?token|"
        r"client[_-]?secret|password|passwd)\b\s*[:=]\s*[\"']?([^\"'\s]{8,})[\"']?"
    )),
]


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    return -sum((n / len(s)) * math.log2(n / len(s)) for n in freq.values())


def redact(value: str) -> str:
    """First 4 chars + ellipsis + total length. Never the full value."""
    return f"{value[:4]}…({len(value)} chars)"


# ---------------------------------------------------------------------------
# gitleaks path
# ---------------------------------------------------------------------------

def run_gitleaks(repo: Path) -> list[dict] | None:
    """Returns findings, or None if gitleaks is unavailable."""
    if not shutil.which("gitleaks"):
        return None
    report = Path(tempfile.mkstemp(suffix=".json")[1])
    # gitleaks >= 8.19 uses `dir`; older releases use `detect --no-git`.
    for args in (
        ["gitleaks", "dir", str(repo), "--report-format", "json",
         "--report-path", str(report), "--exit-code", "0", "--no-banner"],
        ["gitleaks", "detect", "--no-git", "-s", str(repo), "--report-format", "json",
         "--report-path", str(report), "--exit-code", "0", "--no-banner"],
    ):
        try:
            result = subprocess.run(args, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return None
        if result.returncode == 0 and report.exists():
            break
    else:
        return None

    try:
        items = json.loads(report.read_text() or "[]")
    except json.JSONDecodeError:
        return None
    finally:
        report.unlink(missing_ok=True)

    findings = []
    for it in items:
        path = it.get("File", "?")
        try:
            path = str(Path(path).resolve().relative_to(repo))
        except ValueError:
            pass
        if any(part in EXCLUDE_DIRS for part in Path(path).parts):
            continue
        findings.append({
            "path": path,
            "line": it.get("StartLine", 0),
            "rule": it.get("RuleID", "unknown"),
            "severity": "high",
            "secret_redacted": redact(it.get("Secret", "")),
            "entropy": round(it.get("Entropy", 0.0), 2),
            "in_test_file": bool(TEST_PATH.search(path)),
            "tool": "gitleaks",
            "remediation": "Rotate the credential, then remove it from the code. Removal alone is not enough.",
        })
    return findings


# ---------------------------------------------------------------------------
# Builtin fallback
# ---------------------------------------------------------------------------

def iter_files(repo: Path, targets: list[Path]) -> list[Path]:
    if targets:
        return [p for p in targets if p.is_file() and not EXCLUDE_FILES.search(p.name)]
    out = []
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if EXCLUDE_FILES.search(p.name):
            continue
        try:
            if p.stat().st_size > 1_000_000:  # skip >1MB blobs
                continue
        except OSError:
            continue
        out.append(p)
    return out


def run_builtin(repo: Path, targets: list[Path]) -> list[dict]:
    findings = []
    for f in iter_files(repo, targets):
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        if "\x00" in text[:1024]:  # binary
            continue
        rel = str(f.relative_to(repo)) if f.is_relative_to(repo) else str(f)
        for lineno, line in enumerate(text.splitlines(), 1):
            for rule, severity, pattern in PATTERNS:
                m = pattern.search(line)
                if not m:
                    continue
                value = m.group(m.lastindex) if m.lastindex else m.group(0)
                if PLACEHOLDER.search(line):
                    continue
                if value.lower().strip("_-.") in DUMMY_VALUES:
                    continue
                # Bare (unquoted) captures often grab code, not literals:
                # password = get_password(), token = args.password or ...
                # Letters-and-underscore-only (incl. dotted) is an identifier,
                # never a credential — real secrets carry digits/mixed case.
                if rule == "generic-assignment" and re.search(
                    r"[(){}\[\],]|^(self|this|cls)\.|^[a-z_]+(\.[a-z_]+)*$", value
                ):
                    continue
                # Entropy gate only for the loose rules (captured value, not
                # a token with a fixed prefix).
                if rule in ("generic-assignment", "url-with-password") and shannon_entropy(value) < 3.0:
                    continue
                findings.append({
                    "path": rel,
                    "line": lineno,
                    "rule": rule,
                    "severity": severity,
                    "secret_redacted": redact(value),
                    "entropy": round(shannon_entropy(value), 2),
                    "in_test_file": bool(TEST_PATH.search(rel)),
                    "tool": "builtin-regex",
                    "remediation": "Rotate the credential, then remove it from the code. Removal alone is not enough.",
                })
                break  # one finding per line is enough
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False, help="file with newline-separated changed paths (empty = full scan)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Targets file absent = full scan; present = diff scope (empty → skip).
    diff_scope = bool(args.targets) and Path(args.targets).exists()
    targets: list[Path] = []
    if diff_scope:
        for line in Path(args.targets).read_text().splitlines():
            line = line.strip()
            if line and (repo / line).exists():
                targets.append((repo / line).resolve())
        if not targets:
            out.write_text(json.dumps({
                "layer": "secrets", "skipped": True,
                "reason": "no changed files in scope",
                "findings": [], "counts": {"total": 0, "high_non_test": 0},
            }, indent=2))
            print("secrets: skipped (no changed files)")
            return 0

    tool = "gitleaks"
    findings = None
    if not diff_scope:  # gitleaks scans the whole tree; for diffs use builtin on targets
        findings = run_gitleaks(repo)
    if findings is None:
        tool = "builtin-regex"
        findings = run_builtin(repo, targets)

    high = sum(1 for f in findings if f["severity"] == "high" and not f["in_test_file"])
    payload = {
        "layer": "secrets",
        "tool": tool,
        "fallback_used": tool == "builtin-regex",
        "findings": findings,
        "counts": {
            "total": len(findings),
            "high_non_test": high,
            "in_test_files": sum(1 for f in findings if f["in_test_file"]),
        },
    }
    if tool == "builtin-regex" and not shutil.which("gitleaks"):
        payload["warnings"] = [
            "gitleaks not installed — used builtin regex fallback (lower coverage). "
            "Install: brew install gitleaks"
        ]
    out.write_text(json.dumps(payload, indent=2))
    print(f"secrets: {len(findings)} findings ({high} high outside tests) via {tool}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
