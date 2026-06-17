#!/usr/bin/env python3
"""Layer 2 — Code duplication detection.

Uses pylint's `duplicate-code` checker. Pylint is slow on big repos but
produces high-quality cross-file matches without needing a separate tool.

We disable all other checks for speed and parse the JSON output into our
unified findings shape.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from collections import defaultdict


def run_pylint(repo: Path) -> str:
    """Run pylint only with duplicate-code enabled. Returns text output."""
    args = [
        "pylint",
        str(repo),
        "--disable=all",
        "--enable=duplicate-code",
        "--min-similarity-lines=6",
        "--ignore-comments=yes",
        "--ignore-docstrings=yes",
        "--ignore-imports=yes",
        "--reports=no",
        "--score=no",
        # pylint doesn't emit JSON for duplicate-code groups, so we parse text
        "--output-format=text",
        "--persistent=no",
        # Exclude venvs and generated/tool directories so pylint doesn't scan
        # tens of thousands of third-party files.
        "--ignore=.venv,venv,.agents,node_modules,dist,build,__pycache__",
    ]
    try:
        result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=600)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return result.stdout


def parse_duplicate_blocks(text: str, repo: Path) -> list[dict]:
    """Parse pylint's `R0801: Similar lines in N files` blocks.

    The format is roughly:
        path/file.py:1:0: R0801: Similar lines in 2 files
        ==pkg.module_a:[12:34]
        ==pkg.module_b:[88:110]
        <actual lines of code>
    """
    findings: list[dict] = []
    if not text:
        return findings

    # Split into "blocks" by the R0801 marker
    blocks = re.split(r"^.+?: R0801: Similar lines in \d+ files\s*$", text, flags=re.MULTILINE)
    headers = re.findall(r"R0801: Similar lines in (\d+) files", text)

    for idx, (header_count, block) in enumerate(zip(headers, blocks[1:])):
        # Lines like "==pkg.path:[12:34]" describe instances
        instance_re = re.compile(r"^==([^:]+):\[(\d+):(\d+)\]\s*$", re.MULTILINE)
        instances = []
        for m in instance_re.finditer(block):
            module = m.group(1)
            # Convert dotted module to relative path heuristically
            cand = repo / (module.replace(".", "/") + ".py")
            rel = str(cand.relative_to(repo)) if cand.exists() else module
            start = int(m.group(2))
            end = int(m.group(3))
            instances.append({"path": rel, "start": start, "end": end})
        if not instances:
            continue
        line_count = instances[0]["end"] - instances[0]["start"]
        findings.append({
            "clone_id": f"g{idx + 1}",
            "lines": line_count,
            "instances": instances,
            "action": {"type": "extract_shared_helper", "auto_fixable": False},
        })
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    text = run_pylint(repo)
    findings = parse_duplicate_blocks(text, repo)

    duplicated_lines = sum(f["lines"] * len(f["instances"]) for f in findings)
    payload = {
        "layer": "duplication",
        "findings": findings,
        "counts": {
            "clone_groups": len(findings),
            "duplicated_lines": duplicated_lines,
        },
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"duplication: {len(findings)} clone groups, {duplicated_lines} duplicated lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
