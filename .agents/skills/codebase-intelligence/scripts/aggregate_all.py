#!/usr/bin/env python3
"""aggregate_all.py — unified v2.0 aggregator for multi-language codebase intelligence.

Reads:
    <out-dir>/raw/python/aggregate.json     (if --has-python 1)
    <out-dir>/raw/typescript/aggregate.json (if --has-typescript 1)

Writes:
    <out-dir>/audit.json   — schema_version 2.0, machine contract
    <out-dir>/audit.md     — unified Markdown report

Verdict logic (cross-language):
    FAIL if ANY of:
        - Python: missing dependencies > 0
        - Python or TypeScript: boundary violations > 0
        - Python or TypeScript: cyclomatic complexity >= 25 in any function
    WARN if ANY of:
        - Dead code > 0 (either language)
        - Duplication rate > 5% (either language)
        - Unused dependencies > 0 (either language)
        - Complexity warns > 0 (either language)
        - Circular imports > 0 (either language)
    PASS otherwise
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

SCHEMA_VERSION = "2.0"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def load(path: Path) -> dict:
    """Safe JSON loader — returns {} on missing file or parse error."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"error": True, "reason": "invalid JSON or unreadable file"}


def safe_get(d: dict, *keys, default=None):
    """Safe nested dict accessor."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def git_head_sha(repo: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(repo)
        ).stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def _lang_tag(lang: str) -> str:
    return f"[{lang.capitalize()}]"


# ---------------------------------------------------------------------------
# Summary extraction helpers (language-agnostic, works on both aggregate JSONs)
# ---------------------------------------------------------------------------

def extract_summary(agg: dict) -> dict:
    """Pull normalised summary fields from a per-language aggregate.json."""
    s = agg.get("summary", {})
    f = agg.get("findings", {})

    # dead code
    dead_code_count = (
        safe_get(s, "dead_code_count", default=0)
        or len(f.get("dead_code", []))
    )

    # duplication
    dup_groups = (
        safe_get(s, "duplication_clone_groups", default=0)
        or safe_get(agg, "counts", "clone_groups", default=0)
    )
    dup_lines = (
        safe_get(s, "duplicated_lines", default=0)
        or safe_get(agg, "counts", "duplicated_lines", default=0)
    )
    dup_rate = safe_get(s, "duplication_rate_pct", default=0.0) or 0.0

    # complexity
    funcs_above_threshold = (
        safe_get(s, "functions_above_cc_threshold", default=0)
        or len([
            x for x in f.get("complexity", [])
            if x.get("verdict") in ("above_threshold", "warn", "critical")
        ])
    )
    funcs_critical = (
        safe_get(s, "functions_at_critical_complexity", default=0)
        or len([
            x for x in f.get("complexity", [])
            if x.get("verdict") in ("critical",)
               or x.get("cyclomatic", 0) >= 25
        ])
    )

    # dependencies
    dep_findings = f.get("dependencies", [])
    unused_deps = (
        safe_get(s, "unused_dependencies", default=0)
        or sum(1 for d in dep_findings if d.get("kind") == "unused")
    )
    missing_deps = (
        safe_get(s, "missing_dependencies", default=0)
        or sum(1 for d in dep_findings if d.get("kind") == "missing_from_pyproject")
    )

    # boundaries
    boundary_findings = f.get("boundaries", [])
    boundary_violations = (
        safe_get(s, "boundary_violations", default=0)
        or sum(1 for b in boundary_findings if b.get("kind") == "boundary_violation")
    )
    circular_imports = (
        safe_get(s, "circular_import_cycles", default=0)
        or sum(1 for b in boundary_findings if b.get("kind") == "circular_import")
    )

    # file / loc counts
    py_files = safe_get(agg, "repo", "python_files", default=None)
    py_loc   = safe_get(agg, "repo", "python_loc",   default=None)
    ts_files = safe_get(agg, "repo", "ts_files",     default=None)
    ts_loc   = safe_get(agg, "repo", "ts_loc",       default=None)
    # generic fallbacks
    files = py_files or ts_files or safe_get(agg, "repo", "files", default=0) or 0
    loc   = py_loc   or ts_loc   or safe_get(agg, "repo", "loc",   default=0) or 0

    return {
        "files": files,
        "loc": loc,
        "dead_code_count": dead_code_count,
        "duplication_clone_groups": dup_groups,
        "duplicated_lines": dup_lines,
        "duplication_rate_pct": dup_rate,
        "functions_above_cc_threshold": funcs_above_threshold,
        "functions_at_critical_complexity": funcs_critical,
        "unused_dependencies": unused_deps,
        "missing_dependencies": missing_deps,
        "boundary_violations": boundary_violations,
        "circular_import_cycles": circular_imports,
    }


def get_hotspots(agg: dict, lang: str, n: int = 10) -> list[dict]:
    """Return top-N hotspots from an aggregate.json, tagged with lang."""
    raw = agg.get("findings", {}).get("hotspots", [])
    out = []
    for h in raw[:n]:
        out.append({
            "path": h.get("path", ""),
            "score": h.get("score", 0),
            "commits_last_90d": h.get("commits_last_90d", 0),
            "max_cyclomatic": h.get("max_cyclomatic", 0),
            "lang": lang,
        })
    return out


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------

def compute_verdict(
    py_s: dict | None,
    ts_s: dict | None,
) -> tuple[str, str]:
    """Cross-language verdict. Returns (verdict, reason)."""
    fail_reasons: list[str] = []
    warn_reasons: list[str] = []

    for lang, s in [("Python", py_s), ("TypeScript", ts_s)]:
        if s is None:
            continue
        if lang == "Python" and s.get("missing_dependencies", 0) > 0:
            fail_reasons.append(f"{lang}: {s['missing_dependencies']} missing dependency/ies")
        if s.get("boundary_violations", 0) > 0:
            fail_reasons.append(f"{lang}: {s['boundary_violations']} boundary violation(s)")
        if s.get("functions_at_critical_complexity", 0) > 0:
            fail_reasons.append(
                f"{lang}: {s['functions_at_critical_complexity']} function(s) with CC >= 25"
            )

    if fail_reasons:
        return "fail", "; ".join(fail_reasons)

    for lang, s in [("Python", py_s), ("TypeScript", ts_s)]:
        if s is None:
            continue
        if s.get("dead_code_count", 0) > 0:
            warn_reasons.append(f"{lang}: dead code")
        if (s.get("duplication_rate_pct") or 0) > 5:
            warn_reasons.append(f"{lang}: duplication >5%")
        if s.get("unused_dependencies", 0) > 0:
            warn_reasons.append(f"{lang}: unused dependencies")
        if s.get("functions_above_cc_threshold", 0) > 0:
            warn_reasons.append(f"{lang}: complexity warnings")
        if s.get("circular_import_cycles", 0) > 0:
            warn_reasons.append(f"{lang}: circular imports")

    if warn_reasons:
        return "warn", ", ".join(warn_reasons)

    return "pass", "no issues above warn threshold"


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _complexity_grade_label(cc: int) -> str:
    if cc <= 10:
        return "low risk"
    if cc <= 20:
        return "moderate — consider splitting"
    if cc <= 25:
        return "high — hard to test safely"
    if cc <= 50:
        return "critical — refactor target"
    return "extreme — rewrite recommended"


def render_markdown(
    audit: dict,
    repo_name: str,
    py: dict | None,
    ts: dict | None,
    py_summary: dict | None,
    ts_summary: dict | None,
    combined_hotspots: list[dict],
) -> str:
    langs_detected = audit["repo"]["languages"]
    multi = len(langs_detected) > 1
    verdict = audit["verdict"]
    verdict_label = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(verdict, verdict.upper())
    s_all = audit["summary"]

    lines: list[str] = []
    lines.append(f"# Codebase Intelligence — {repo_name}")
    lines.append("")
    lines.append(f"**Verdict:** {verdict_label} — {audit['verdict_reason']}")
    lines.append("")
    lang_display = " · ".join(l.capitalize() for l in langs_detected)
    lines.append(f"**Languages:** {lang_display}")
    lines.append("")
    lines.append(
        f"_Generated {audit['generated_at']} | "
        f"HEAD `{audit['repo']['head_sha'][:8]}` | "
        f"scope: {audit['repo']['analysis_scope']}_"
    )
    lines.append("")

    # ------------------------------------------------------------------
    # At a glance
    # ------------------------------------------------------------------
    lines.append("## At a glance")
    lines.append("")

    if multi:
        py_s = py_summary or {}
        ts_s = ts_summary or {}
        total_files = (py_s.get("files") or 0) + (ts_s.get("files") or 0)
        total_loc   = (py_s.get("loc") or 0)   + (ts_s.get("loc") or 0)

        lines.append("| Metric | Python | TypeScript | Total |")
        lines.append("|---|---|---|---|")
        lines.append(f"| Files | {py_s.get('files', '—')} | {ts_s.get('files', '—')} | {total_files or '—'} |")
        lines.append(f"| Lines of code | {py_s.get('loc', '—')} | {ts_s.get('loc', '—')} | {total_loc or '—'} |")
        lines.append(
            f"| Dead code items | {py_s.get('dead_code_count', '—')} | "
            f"{ts_s.get('dead_code_count', '—')} | "
            f"{s_all['total_dead_code']} |"
        )
        lines.append(
            f"| Duplication rate | "
            f"{py_s.get('duplication_rate_pct', '—')}% | "
            f"{ts_s.get('duplication_rate_pct', '—')}% | — |"
        )
        lines.append(
            f"| Functions above CC threshold | "
            f"{py_s.get('functions_above_cc_threshold', '—')} | "
            f"{ts_s.get('functions_above_cc_threshold', '—')} | "
            f"{s_all['total_functions_above_cc_threshold']} |"
        )
        lines.append(
            f"| Unused dependencies | "
            f"{py_s.get('unused_dependencies', '—')} | "
            f"{ts_s.get('unused_dependencies', '—')} | "
            f"{s_all['total_unused_dependencies']} |"
        )
        lines.append(
            f"| Boundary violations | "
            f"{py_s.get('boundary_violations', '—')} | "
            f"{ts_s.get('boundary_violations', '—')} | "
            f"{s_all['total_boundary_violations']} |"
        )
        lines.append(
            f"| Circular imports | "
            f"{py_s.get('circular_import_cycles', '—')} | "
            f"{ts_s.get('circular_import_cycles', '—')} | "
            f"{s_all['total_circular_imports']} |"
        )
    else:
        # Single-language table
        single_lang = langs_detected[0]
        single_s = py_summary if single_lang == "python" else ts_summary
        s = single_s or {}
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        lines.append(f"| Files | {s.get('files', '—')} |")
        lines.append(f"| Lines of code | {s.get('loc', '—')} |")
        lines.append(f"| Dead code items | {s.get('dead_code_count', '—')} |")
        lines.append(f"| Duplication rate | {s.get('duplication_rate_pct', '—')}% |")
        lines.append(f"| Functions above CC threshold | {s.get('functions_above_cc_threshold', '—')} |")
        lines.append(f"| Unused dependencies | {s.get('unused_dependencies', '—')} |")
        lines.append(f"| Boundary violations | {s.get('boundary_violations', '—')} |")
        lines.append(f"| Circular imports | {s.get('circular_import_cycles', '—')} |")

    lines.append("")

    # ------------------------------------------------------------------
    # Top 5 cross-language refactor candidates
    # ------------------------------------------------------------------
    lines.append("## Top 5 cross-language refactor candidates")
    lines.append("")
    lines.append(
        "> **How to read this list:** Score = churn × complexity. Files that change constantly "
        "AND are hard to understand safely concentrate most production-bug risk."
    )
    lines.append("")
    top5 = sorted(combined_hotspots, key=lambda h: h.get("score", 0), reverse=True)[:5]
    if top5:
        for h in top5:
            tag = _lang_tag(h["lang"])
            lines.append(
                f"- {tag} **`{h['path']}`** — score {h['score']} "
                f"(churn: {h.get('commits_last_90d', '?')} commits/90d, "
                f"max CC: {h.get('max_cyclomatic', '?')})"
            )
    else:
        lines.append("_No hotspot data available._")
    lines.append("")

    # ------------------------------------------------------------------
    # Per-language findings sections
    # ------------------------------------------------------------------
    def render_language_section(lang: str, agg: dict, s: dict) -> list[str]:
        sec: list[str] = []
        f = agg.get("findings", {})
        lang_cap = lang.capitalize()
        sec.append(f"## {lang_cap} findings")
        sec.append("")

        # Dead code
        dc = f.get("dead_code", [])
        sec.append(f"### Dead code ({len(dc)} items)")
        sec.append("")
        if dc:
            ruff_items     = [i for i in dc if i.get("tool") == "ruff"]
            vulture_high   = [i for i in dc if i.get("tool") == "vulture" and i.get("confidence", 0) >= 80]
            vulture_low    = [i for i in dc if i.get("tool") == "vulture" and i.get("confidence", 0) < 80]
            ts_items       = [i for i in dc if i.get("tool") not in ("ruff", "vulture", None) or
                               (i.get("tool") is None and lang == "typescript")]
            # TypeScript items (ts-prune / knip / custom)
            if ts_items:
                sec.append(f"**{len(ts_items)} unused export(s)/symbol(s):**")
                sec.append("")
                for item in ts_items[:10]:
                    sec.append(f"- `{item.get('path', '?')}:{item.get('line', '?')}` "
                               f"— {item.get('kind', 'unused')} `{item.get('name', '?')}`")
                if len(ts_items) > 10:
                    sec.append(f"- _… {len(ts_items) - 10} more._")
                sec.append("")
            if ruff_items:
                sec.append(f"**Auto-fixable (ruff) — {len(ruff_items)} item(s):** `ruff check --fix` removes these.")
                sec.append("")
                for item in ruff_items[:5]:
                    sec.append(f"- `{item['path']}:{item['line']}` — {item['kind']} `{item['name']}`")
                if len(ruff_items) > 5:
                    sec.append(f"- _… {len(ruff_items) - 5} more._")
                sec.append("")
            if vulture_high:
                sec.append(f"**High-confidence vulture (≥80%) — {len(vulture_high)} item(s):**")
                sec.append("")
                for item in vulture_high[:10]:
                    sec.append(f"- `{item['path']}:{item['line']}` "
                               f"— {item['kind']} `{item['name']}` ({item['confidence']}%)")
                if len(vulture_high) > 10:
                    sec.append(f"- _… {len(vulture_high) - 10} more._")
                sec.append("")
            if vulture_low:
                sec.append(f"**Low-confidence vulture (60–79%) — {len(vulture_low)} item(s):** Verify before deleting.")
                sec.append("")
                for item in vulture_low[:10]:
                    sec.append(f"- `{item['path']}:{item['line']}` "
                               f"— {item['kind']} `{item['name']}` ({item['confidence']}%)")
                if len(vulture_low) > 10:
                    sec.append(f"- _… {len(vulture_low) - 10} more._")
        else:
            sec.append("_None found._")
        sec.append("")

        # Duplication
        dup = f.get("duplication", [])
        dup_rate = s.get("duplication_rate_pct", 0)
        dup_signal = "above warning threshold (>5%)" if dup_rate > 5 else "within acceptable range (≤5%)"
        sec.append(
            f"### Duplication ({s.get('duplication_clone_groups', len(dup))} clone groups, "
            f"{s.get('duplicated_lines', 0):,} duplicated lines — {dup_rate}%, {dup_signal})"
        )
        sec.append("")
        if dup:
            for g in dup[:10]:
                instances = g.get("instances", [])
                paths = ", ".join(
                    f"`{i.get('path', '?')}:{i.get('start', '?')}`" for i in instances
                )
                sec.append(f"- **{g.get('lines', '?')} lines** shared across: {paths}")
            if len(dup) > 10:
                sec.append(f"- _… {len(dup) - 10} more groups — see `audit.json`._")
        else:
            sec.append("_None found._")
        sec.append("")

        # Complexity
        cx = f.get("complexity", [])
        sec.append(f"### Complexity ({len(cx)} functions above threshold)")
        sec.append("")
        if cx:
            cx_sorted = sorted(cx, key=lambda x: x.get("cyclomatic", 0), reverse=True)
            for item in cx_sorted[:15]:
                cc = item.get("cyclomatic", 0)
                label = _complexity_grade_label(cc)
                fn_name = item.get("function") or item.get("name", "?")
                sec.append(
                    f"- `{item.get('path', '?')}:{item.get('line', '?')}` "
                    f"— `{fn_name}` **CC={cc}** ({label})"
                )
            if len(cx_sorted) > 15:
                sec.append(f"- _… {len(cx_sorted) - 15} more — see `audit.json`._")
        else:
            sec.append("_None above threshold._")
        sec.append("")

        # Dependencies
        deps = f.get("dependencies", [])
        sec.append(f"### Dependencies ({len(deps)} issues)")
        sec.append("")
        if deps:
            missing = [d for d in deps if d.get("kind") == "missing_from_pyproject"]
            unused  = [d for d in deps if d.get("kind") == "unused"]
            other   = [d for d in deps if d.get("kind") not in ("missing_from_pyproject", "unused")]
            if missing:
                sec.append(f"**Missing — {len(missing)} package(s)** (will break fresh installs):")
                sec.append("")
                for d in missing:
                    loc = f" @ `{d['path']}:{d['line']}`" if d.get("path") else ""
                    sec.append(f"- `{d['name']}`{loc}")
                sec.append("")
            if unused:
                sec.append(f"**Unused — {len(unused)} package(s)** (safe to remove):")
                sec.append("")
                for d in unused[:20]:
                    sec.append(f"- `{d['name']}`")
                if len(unused) > 20:
                    sec.append(f"- _… {len(unused) - 20} more._")
                sec.append("")
            if other:
                sec.append(f"**Other issues — {len(other)} item(s):**")
                sec.append("")
                for d in other[:10]:
                    loc = f" @ `{d['path']}:{d['line']}`" if d.get("path") else ""
                    sec.append(f"- **{d.get('kind', 'unknown')}**: `{d.get('name', '?')}`{loc}")
        else:
            sec.append("_None — dependency manifest is clean._")
        sec.append("")

        # Architecture boundaries
        b = f.get("boundaries", [])
        violations = [x for x in b if x.get("kind") == "boundary_violation"]
        cycles     = [x for x in b if x.get("kind") == "circular_import"]
        sec.append(
            f"### Architecture boundaries "
            f"({len(violations)} violations, {len(cycles)} circular import cycles)"
        )
        sec.append("")
        if violations:
            for v in violations[:10]:
                sec.append(f"- **Rule violated:** {v.get('rule', '?')} — {v.get('detail', '')}")
        if cycles:
            for c in cycles[:10]:
                cycle_chain = " → ".join(c.get("cycle", []))
                if c.get("cycle"):
                    cycle_chain += f" → {c['cycle'][0]}"
                sec.append(f"- **Circular import ({c.get('size', '?')} modules):** {cycle_chain}")
        if not violations and not cycles:
            sec.append("_No boundary issues found._")
        sec.append("")

        # Hotspots
        hot = f.get("hotspots", [])[:10]
        sec.append(f"### Hotspots (top 10)")
        sec.append("")
        if hot:
            sec.append("| File | Score | Commits/90d | Max CC | Risk |")
            sec.append("|---|---|---|---|---|")
            for h in hot:
                cc = h.get("max_cyclomatic", 0)
                risk = _complexity_grade_label(cc)
                sec.append(
                    f"| `{h['path']}` | {h['score']} | "
                    f"{h.get('commits_last_90d', '?')} | {cc} | {risk} |"
                )
        else:
            sec.append("_No hotspot data._")
        sec.append("")
        return sec

    if py and not py.get("error"):
        lines.extend(render_language_section("python", py, py_summary or {}))

    if ts and not ts.get("error"):
        lines.extend(render_language_section("typescript", ts, ts_summary or {}))

    # ------------------------------------------------------------------
    # Suggested next actions
    # ------------------------------------------------------------------
    lines.append("## Suggested next actions")
    lines.append("")
    actions: list[str] = []

    # FAIL triggers first
    for lang, s in [("Python", py_summary), ("TypeScript", ts_summary)]:
        if s is None:
            continue
        if lang == "Python" and s.get("missing_dependencies", 0):
            actions.append(
                f"**[Python] Fix {s['missing_dependencies']} missing dependency/ies** in `pyproject.toml` — "
                "these imports will fail on a clean install or in CI. Run `deptry .` for details."
            )
        if s.get("boundary_violations", 0):
            actions.append(
                f"**[{lang}] Resolve {s['boundary_violations']} boundary violation(s)** — "
                "these break the architecture contract. "
                "Configure boundary rules to enforce the contract automatically in CI."
            )
        if s.get("functions_at_critical_complexity", 0):
            actions.append(
                f"**[{lang}] Refactor {s['functions_at_critical_complexity']} critical-complexity function(s)** "
                "(CC ≥ 25) — see hotspots list for highest-priority targets."
            )

    # WARN triggers
    for lang, s in [("Python", py_summary), ("TypeScript", ts_summary)]:
        if s is None:
            continue
        if s.get("circular_import_cycles", 0):
            actions.append(
                f"**[{lang}] Break {s['circular_import_cycles']} import cycle(s)** — "
                "extract shared types into a neutral third module."
            )
        if s.get("dead_code_count", 0):
            dc_note = " Run `ruff check --fix` first (auto-fixes unused imports/variables)." \
                if lang == "Python" else ""
            actions.append(
                f"**[{lang}] Trim {s['dead_code_count']} dead code item(s).**{dc_note}"
            )
        if s.get("unused_dependencies", 0):
            actions.append(
                f"**[{lang}] Remove {s['unused_dependencies']} unused dependency/ies** — "
                "smaller dependency surface means faster installs and fewer CVEs."
            )

    if not actions:
        actions.append(
            "**Nothing urgent.** The codebase is in good shape. "
            "Re-run the audit periodically (or on CI) to catch regressions early."
        )

    for i, act in enumerate(actions, 1):
        lines.append(f"{i}. {act}")
    lines.append("")

    # Audit warnings (tool errors etc.)
    if audit.get("summary", {}).get("warnings"):
        lines.append("---")
        lines.append("")
        lines.append("### Audit warnings")
        for w in audit["summary"]["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Unified multi-language codebase intelligence aggregator (v2.0)"
    )
    ap.add_argument("out_dir", help="Audit output directory (contains raw/ sub-dirs)")
    ap.add_argument("--repo", required=True, help="Absolute path to the repository root")
    ap.add_argument("--has-python",     default="0", help="1 if Python layers were run")
    ap.add_argument("--has-typescript", default="0", help="1 if TypeScript layers were run")
    ap.add_argument("--scope", default="full", help="Analysis scope string")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    repo    = Path(args.repo).resolve()

    has_python = args.has_python.strip() == "1"
    has_ts     = args.has_typescript.strip() == "1"

    # Load per-language aggregates
    py: dict | None = None
    ts: dict | None = None
    py_summary: dict | None = None
    ts_summary: dict | None = None

    if has_python:
        py = load(out_dir / "raw" / "python" / "aggregate.json")
        if py and not py.get("error"):
            py_summary = extract_summary(py)

    if has_ts:
        ts = load(out_dir / "raw" / "typescript" / "aggregate.json")
        if ts and not ts.get("error"):
            ts_summary = extract_summary(ts)

    # Detected languages list (order: python first)
    languages: list[str] = []
    if has_python:
        languages.append("python")
    if has_ts:
        languages.append("typescript")

    # Collect warnings from errored aggregates
    agg_warnings: list[str] = []
    if has_python and (not py or py.get("error")):
        agg_warnings.append("python aggregate.json missing or invalid — Python findings may be incomplete")
    if has_ts and (not ts or ts.get("error")):
        agg_warnings.append("typescript aggregate.json missing or invalid — TypeScript findings may be incomplete")

    # Cross-language totals
    def _sum(*vals: int | None) -> int:
        return sum(v or 0 for v in vals)

    all_hotspots: list[dict] = []
    worst_hotspot: dict | None = None

    if py_summary:
        all_hotspots.extend(get_hotspots(py, "python"))
    if ts_summary:
        all_hotspots.extend(get_hotspots(ts, "typescript"))

    if all_hotspots:
        worst_hotspot = max(all_hotspots, key=lambda h: h.get("score", 0))

    summary = {
        "total_dead_code": _sum(
            safe_get(py_summary, "dead_code_count"),
            safe_get(ts_summary, "dead_code_count"),
        ),
        "total_duplication_clone_groups": _sum(
            safe_get(py_summary, "duplication_clone_groups"),
            safe_get(ts_summary, "duplication_clone_groups"),
        ),
        "total_duplicated_lines": _sum(
            safe_get(py_summary, "duplicated_lines"),
            safe_get(ts_summary, "duplicated_lines"),
        ),
        "total_functions_above_cc_threshold": _sum(
            safe_get(py_summary, "functions_above_cc_threshold"),
            safe_get(ts_summary, "functions_above_cc_threshold"),
        ),
        "total_unused_dependencies": _sum(
            safe_get(py_summary, "unused_dependencies"),
            safe_get(ts_summary, "unused_dependencies"),
        ),
        "total_boundary_violations": _sum(
            safe_get(py_summary, "boundary_violations"),
            safe_get(ts_summary, "boundary_violations"),
        ),
        "total_circular_imports": _sum(
            safe_get(py_summary, "circular_import_cycles"),
            safe_get(ts_summary, "circular_import_cycles"),
        ),
        "languages": languages,
        "worst_hotspot": worst_hotspot,
        "warnings": agg_warnings,
    }

    verdict, verdict_reason = compute_verdict(py_summary, ts_summary)

    audit = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo": {
            "path": str(repo),
            "head_sha": git_head_sha(repo),
            "languages": languages,
            "analysis_scope": args.scope,
        },
        "languages": {
            "python":     py if has_python else None,
            "typescript": ts if has_ts else None,
        },
        "summary": summary,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }

    (out_dir / "audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False))

    md = render_markdown(
        audit=audit,
        repo_name=repo.name,
        py=py,
        ts=ts,
        py_summary=py_summary,
        ts_summary=ts_summary,
        combined_hotspots=all_hotspots,
    )
    (out_dir / "audit.md").write_text(md, encoding="utf-8")

    print(f"aggregate_all: verdict={verdict} ({verdict_reason})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
