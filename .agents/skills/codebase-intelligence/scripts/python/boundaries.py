#!/usr/bin/env python3
"""Layer 5 — Architecture boundaries and circular imports.

Two modes:
1. If `.importlinter` / `pyproject.toml [tool.importlinter]` config exists,
   delegate to `lint-imports` for full rule enforcement.
2. Always run our own circular-import detector by building an import graph
   with stdlib `ast`. This works even when no architecture rules are defined.

Cycles are reported as ordered lists of module paths.
"""
from __future__ import annotations
import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path
from collections import defaultdict


def has_importlinter_config(repo: Path) -> bool:
    if (repo / ".importlinter").exists():
        return True
    py = repo / "pyproject.toml"
    if py.exists():
        try:
            if "[tool.importlinter]" in py.read_text(errors="ignore"):
                return True
        except OSError:
            pass
    if (repo / "setup.cfg").exists():
        try:
            if "[importlinter]" in (repo / "setup.cfg").read_text(errors="ignore"):
                return True
        except OSError:
            pass
    return False


def run_importlinter(repo: Path) -> list[dict]:
    """Run lint-imports and parse human output (it has no stable JSON mode)."""
    try:
        result = subprocess.run(
            ["lint-imports"], capture_output=True, text=True, check=False, cwd=str(repo)
        )
    except FileNotFoundError:
        return []

    findings: list[dict] = []
    current_rule = None
    for line in result.stdout.splitlines():
        line = line.rstrip()
        if line.startswith("Contract:"):
            current_rule = line.split(":", 1)[1].strip()
        elif "is not allowed to import" in line or "->" in line:
            findings.append({
                "rule": current_rule or "unknown",
                "detail": line.strip(),
                "kind": "boundary_violation",
                "tool": "import-linter",
            })
    return findings


# ---------------------------------------------------------------------------
# Circular-import detection (always runs)
# ---------------------------------------------------------------------------
def module_name(repo: Path, file: Path) -> str:
    rel = file.resolve().relative_to(repo)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def collect_imports(py_file: Path) -> list[str]:
    try:
        tree = ast.parse(py_file.read_text(errors="ignore"), filename=str(py_file))
    except (SyntaxError, OSError):
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def build_graph(repo: Path) -> dict[str, set[str]]:
    """Map module → set of modules it imports (only first-party)."""
    py_files = [
        p for p in repo.rglob("*.py")
        if not any(part in {".venv", "venv", "build", "dist", "node_modules", "migrations"}
                   for part in p.parts)
    ]
    known: set[str] = set()
    for f in py_files:
        try:
            known.add(module_name(repo, f))
        except ValueError:
            continue

    graph: dict[str, set[str]] = defaultdict(set)
    for f in py_files:
        try:
            mod = module_name(repo, f)
        except ValueError:
            continue
        for imp in collect_imports(f):
            # only keep first-party edges (module is known in this repo)
            if imp in known:
                graph[mod].add(imp)
            else:
                # try parent-prefix match (from x.y import z → x.y)
                parts = imp.split(".")
                for i in range(len(parts), 0, -1):
                    prefix = ".".join(parts[:i])
                    if prefix in known:
                        graph[mod].add(prefix)
                        break
    return graph


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Tarjan's SCC algorithm — returns components of size >1 (or self-loops)."""
    index_counter = [0]
    stack: list[str] = []
    lowlink: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    sccs: list[list[str]] = []

    def strongconnect(node: str) -> None:
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        on_stack[node] = True

        for successor in graph.get(node, ()):
            if successor not in index:
                strongconnect(successor)
                lowlink[node] = min(lowlink[node], lowlink[successor])
            elif on_stack.get(successor):
                lowlink[node] = min(lowlink[node], index[successor])

        if lowlink[node] == index[node]:
            scc = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == node:
                    break
            if len(scc) > 1 or (len(scc) == 1 and scc[0] in graph.get(scc[0], ())):
                sccs.append(scc)

    sys.setrecursionlimit(10000)
    for node in list(graph):
        if node not in index:
            try:
                strongconnect(node)
            except RecursionError:
                break
    return sccs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--targets", required=False)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    boundary_findings: list[dict] = []
    importlinter_used = False
    if has_importlinter_config(repo):
        importlinter_used = True
        boundary_findings = run_importlinter(repo)

    graph = build_graph(repo)
    cycles = find_cycles(graph)
    cycle_findings = [
        {"kind": "circular_import", "cycle": scc, "size": len(scc)}
        for scc in cycles
    ]

    payload = {
        "layer": "boundaries",
        "importlinter_config_found": importlinter_used,
        "findings": boundary_findings + cycle_findings,
        "counts": {
            "boundary_violations": len(boundary_findings),
            "circular_import_cycles": len(cycle_findings),
            "total": len(boundary_findings) + len(cycle_findings),
        },
    }
    out.write_text(json.dumps(payload, indent=2))
    print(f"boundaries: {len(boundary_findings)} rule violations, "
          f"{len(cycle_findings)} circular import cycles "
          f"({'import-linter' if importlinter_used else 'cycle-detector only'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
