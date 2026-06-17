#!/usr/bin/env python3
"""Layer 6 (Python) — supply-chain hygiene (offline, no network needed).

Checks the dependency *declarations* rather than known CVEs:
- direct git/URL dependencies (no registry review, mutable targets)
- unpinned or open-ended version specs in requirements.txt
- missing lockfile (pyproject without uv.lock/poetry.lock)
- typosquat heuristic: edit-distance 1 from a popular PyPI package name

Malicious-package advisories (OSV `MAL-`) are layer 5's job via osv-scanner;
this layer is the structural complement that works offline.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - py<3.11
    tomllib = None

POPULAR_PYPI = [
    "requests", "urllib3", "numpy", "pandas", "django", "flask", "fastapi",
    "sqlalchemy", "pydantic", "boto3", "botocore", "setuptools", "pip", "wheel",
    "cryptography", "certifi", "charset-normalizer", "idna", "click", "typer",
    "pytest", "httpx", "aiohttp", "celery", "redis", "pillow", "scipy",
    "matplotlib", "scikit-learn", "tensorflow", "torch", "transformers",
    "openai", "anthropic", "langchain", "jinja2", "pyyaml", "python-dotenv",
    "attrs", "rich", "uvicorn", "gunicorn", "starlette", "alembic", "psycopg2",
    "pymongo", "kafka-python", "grpcio", "protobuf", "google-api-python-client",
    "colorama", "tqdm", "packaging", "six", "python-dateutil", "pytz",
]
POPULAR_SET = set(POPULAR_PYPI)

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def edit_distance_1(a: str, b: str) -> bool:
    """True if a and b differ by exactly one edit (insert/delete/substitute)."""
    if a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        return sum(1 for x, y in zip(a, b, strict=True) if x != y) == 1
    if la > lb:
        a, b, la, lb = b, a, lb, la
    # a is shorter by 1: check single insertion
    i = j = diff = 0
    while i < la and j < lb:
        if a[i] != b[j]:
            diff += 1
            if diff > 1:
                return False
            j += 1
        else:
            i += 1
            j += 1
    return True


def normalize(name: str) -> str:
    return re.sub(r"[._-]+", "-", name.lower())


def parse_requirement(line: str) -> tuple[str, str] | None:
    """Return (name, spec) for a requirements.txt-style line, or None."""
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith(("-", "--")):
        return None
    if line.startswith(("git+", "hg+", "svn+", "http://", "https://", "file:")):
        return ("", line)  # URL dependency, no name parsed
    m = NAME_RE.match(line)
    if not m:
        return None
    name = m.group(0)
    spec = line[len(name):].split(";")[0].strip()
    return (name, spec)


def collect_declared(repo: Path) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Return ([(name, spec, source_file)], warnings)."""
    declared: list[tuple[str, str, str]] = []
    warnings: list[str] = []

    pyproject = repo / "pyproject.toml"
    if pyproject.exists() and tomllib:
        try:
            data = tomllib.loads(pyproject.read_text(errors="ignore"))
        except (tomllib.TOMLDecodeError, OSError) as e:
            data = {}
            warnings.append(f"pyproject.toml unparseable: {e}")
        deps = (data.get("project") or {}).get("dependencies") or []
        for group in ((data.get("project") or {}).get("optional-dependencies") or {}).values():
            deps.extend(group)
        for group in (data.get("dependency-groups") or {}).values():
            deps.extend(d for d in group if isinstance(d, str))
        for d in deps:
            parsed = parse_requirement(d)
            if parsed:
                declared.append((*parsed, "pyproject.toml"))

    for req_name in ("requirements.txt", "requirements-dev.txt", "requirements/base.txt"):
        req = repo / req_name
        if not req.exists():
            continue
        for line in req.read_text(errors="ignore").splitlines():
            parsed = parse_requirement(line)
            if parsed:
                declared.append((*parsed, req_name))

    return declared, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False)  # unused; manifest-level layer
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    declared, warnings = collect_declared(repo)
    findings: list[dict] = []

    if not declared:
        payload = {
            "layer": "supply_chain", "skipped": True,
            "reason": "no pyproject.toml/requirements.txt dependencies found",
            "findings": [], "counts": {"total": 0}, "warnings": warnings,
        }
        out.write_text(json.dumps(payload, indent=2))
        print("supply_chain(py): skipped (no declared dependencies)")
        return 0

    has_lockfile = any((repo / f).exists() for f in ("uv.lock", "poetry.lock", "Pipfile.lock", "pdm.lock"))
    uses_requirements_only = not (repo / "pyproject.toml").exists()

    for name, spec, source in declared:
        # URL / VCS dependency
        if not name and spec:
            findings.append({
                "package": spec[:80], "rule": "url-dependency", "severity": "medium",
                "message": "Direct URL/VCS dependency bypasses the registry and is mutable unless commit-pinned",
                "manifest": source, "tool": "supply-chain",
                "remediation": "Pin to a full commit SHA, or publish to a registry.",
            })
            continue
        if "@" in spec and ("git+" in spec or "://" in spec):
            findings.append({
                "package": name, "rule": "url-dependency", "severity": "medium",
                "message": "Dependency resolved from URL/VCS instead of the registry",
                "manifest": source, "tool": "supply-chain",
                "remediation": "Pin to a full commit SHA, or publish to a registry.",
            })

        # Typosquat heuristic — only for names NOT in the popular list themselves.
        norm = normalize(name)
        if norm and norm not in POPULAR_SET:
            hits = [p for p in POPULAR_PYPI if edit_distance_1(norm, p)]
            if hits:
                findings.append({
                    "package": name, "rule": "possible-typosquat", "severity": "medium",
                    "message": f"Name is one edit away from popular package(s): {', '.join(hits)} — verify it is intentional",
                    "manifest": source, "tool": "supply-chain",
                    "remediation": "Confirm on pypi.org this is the package you meant.",
                })

        # Pinning — only meaningful for requirements.txt-style installs without a lockfile.
        if source.startswith("requirements") and not has_lockfile:
            if not spec:
                findings.append({
                    "package": name, "rule": "unpinned-dependency", "severity": "low",
                    "message": "No version constraint and no lockfile — installs whatever is newest",
                    "manifest": source, "tool": "supply-chain",
                    "remediation": "Pin with == or adopt a lockfile (uv/poetry/pip-tools).",
                })
            elif spec.startswith(">=") and "<" not in spec and "==" not in spec:
                findings.append({
                    "package": name, "rule": "open-ended-constraint", "severity": "low",
                    "message": f"Open-ended constraint `{spec}` with no lockfile",
                    "manifest": source, "tool": "supply-chain",
                    "remediation": "Add an upper bound or adopt a lockfile.",
                })

    if (repo / "pyproject.toml").exists() and not has_lockfile and not uses_requirements_only:
        findings.append({
            "package": "(project)", "rule": "missing-lockfile", "severity": "medium",
            "message": "pyproject.toml without a lockfile — builds are not reproducible and silently pick up new releases",
            "manifest": "pyproject.toml", "tool": "supply-chain",
            "remediation": "Commit uv.lock (uv sync) or poetry.lock.",
        })

    by_sev = {s: sum(1 for f in findings if f["severity"] == s)
              for s in ("high", "medium", "low")}
    payload = {
        "layer": "supply_chain",
        "tool": "supply-chain",
        "declared_dependencies": len(declared),
        "has_lockfile": has_lockfile,
        "findings": findings,
        "counts": {"total": len(findings), **by_sev},
        "warnings": warnings,
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"supply_chain(py): {len(findings)} findings over {len(declared)} declared deps "
          f"(lockfile={'yes' if has_lockfile else 'no'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
