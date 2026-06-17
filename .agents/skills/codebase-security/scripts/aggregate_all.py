#!/usr/bin/env python3
"""aggregate_all.py — unified aggregator for the codebase-security audit.

Reads:
    <out-dir>/raw/common/secrets.json
    <out-dir>/raw/common/git_history.json
    <out-dir>/raw/common/config_exposure.json
    <out-dir>/raw/python/{sast,vuln_deps,supply_chain}.json      (if --has-python 1)
    <out-dir>/raw/typescript/{sast,vuln_deps,supply_chain}.json  (if --has-typescript 1)

Writes:
    <out-dir>/security.json   — schema_version 1.0, machine contract
    <out-dir>/security.md     — human report
    <out-dir>/security.sarif  — SARIF 2.1.0 for GitHub code scanning / IDEs

Verdict logic:
    FAIL if ANY of:
        - secret with high severity outside test files (current tree)
        - config_exposure finding with high severity
        - SAST high severity with high/medium confidence outside tests
        - dependency vulnerability critical/high, or any malicious package
    WARN if ANY other finding exists, or a layer was skipped/errored
    PASS otherwise
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCHEMA_VERSION = "1.0"
COMMON_LAYERS = ["secrets", "git_history", "config_exposure"]
LANG_LAYERS = ["sast", "vuln_deps", "supply_chain"]
SARIF_LEVEL = {"critical": "error", "high": "error", "medium": "warning",
               "low": "note", "info": "note", "unknown": "warning"}


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"error": True, "reason": "invalid JSON or unreadable file"}


def git_head_sha(repo: Path) -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(repo)
        ).stdout.strip() or "unknown"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def layer_warnings(name: str, layer: dict, group: str) -> list[str]:
    out = []
    if layer.get("error"):
        out.append(f"layer `{group}:{name}` failed — see raw/{group}/{name}.err")
    if layer.get("skipped"):
        out.append(f"layer `{group}:{name}` skipped: {layer.get('reason', 'unknown')}")
    out.extend(f"{group}:{name}: {w}" for w in layer.get("warnings", []))
    return out


def sev_counts(findings: list[dict]) -> dict:
    out = {s: 0 for s in ("critical", "high", "medium", "low", "info", "unknown")}
    for f in findings:
        out[f.get("severity", "unknown") if f.get("severity") in out else "unknown"] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--has-python", default="0")
    ap.add_argument("--has-typescript", default="0")
    ap.add_argument("--scope", default="full")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).resolve()
    repo = Path(args.repo).resolve()

    groups: dict[str, dict[str, dict]] = {"common": {}}
    for layer in COMMON_LAYERS:
        groups["common"][layer] = load(out_dir / "raw" / "common" / f"{layer}.json")
    if args.has_python == "1":
        groups["python"] = {n: load(out_dir / "raw" / "python" / f"{n}.json") for n in LANG_LAYERS}
    if args.has_typescript == "1":
        groups["typescript"] = {n: load(out_dir / "raw" / "typescript" / f"{n}.json") for n in LANG_LAYERS}

    warnings: list[str] = []
    for group, layers in groups.items():
        for name, layer in layers.items():
            warnings.extend(layer_warnings(name, layer, group))

    # ------------------------------------------------------------------
    # Pull the verdict-relevant counters
    # ------------------------------------------------------------------
    secrets = groups["common"]["secrets"]
    history = groups["common"]["git_history"]
    config = groups["common"]["config_exposure"]

    secrets_high = secrets.get("counts", {}).get("high_non_test", 0)
    history_only = history.get("counts", {}).get("history_only", 0)
    config_high = sum(1 for f in config.get("findings", []) if f.get("severity") == "high")

    sast_high = 0
    vuln_critical_high = 0
    malicious = 0
    fail_reasons: list[str] = []
    total_findings = 0

    for group, layers in groups.items():
        for layer in layers.values():
            total_findings += len(layer.get("findings", []))
        if group == "common":
            continue
        sast = layers.get("sast", {})
        sast_high += sast.get("counts", {}).get("high_actionable", 0)
        vd = layers.get("vuln_deps", {})
        bysev = vd.get("counts", {}).get("by_severity", {})
        vuln_critical_high += bysev.get("critical", 0) + bysev.get("high", 0)
        malicious += vd.get("counts", {}).get("malicious", 0)

    if secrets_high:
        fail_reasons.append(f"{secrets_high} high-severity secret(s) in the working tree")
    if config_high:
        fail_reasons.append(f"{config_high} high-severity exposure(s) (tracked sensitive files / TLS off / privileged containers)")
    if sast_high:
        fail_reasons.append(f"{sast_high} high-severity SAST finding(s) outside tests")
    if malicious:
        fail_reasons.append(f"{malicious} MALICIOUS package advisory/advisories")
    if vuln_critical_high:
        fail_reasons.append(f"{vuln_critical_high} critical/high dependency vulnerability(ies)")

    if fail_reasons:
        verdict, verdict_reason = "fail", "; ".join(fail_reasons)
    elif total_findings > 0 or history_only > 0:
        verdict = "warn"
        bits = []
        if history_only:
            bits.append(f"{history_only} secret(s) in git history only")
        if total_findings:
            bits.append(f"{total_findings} non-blocking finding(s)")
        verdict_reason = "; ".join(bits)
    else:
        verdict, verdict_reason = "pass", "no findings"

    # ------------------------------------------------------------------
    # security.json
    # ------------------------------------------------------------------
    def layer_block(layer: dict) -> dict:
        return {
            "tool": layer.get("tool", layer.get("tools", "?")),
            "skipped": bool(layer.get("skipped")),
            "fallback_used": bool(layer.get("fallback_used")),
            "counts": layer.get("counts", {"total": 0}),
            "findings": layer.get("findings", []),
        }

    audit = {
        "schema_version": SCHEMA_VERSION,
        "kind": "security",
        "repo": {
            "path": str(repo),
            "head_sha": git_head_sha(repo),
            "analysis_scope": args.scope,
            "languages": [g for g in ("python", "typescript") if g in groups],
        },
        "layers": {
            group: {name: layer_block(layer) for name, layer in layers.items()}
            for group, layers in groups.items()
        },
        "summary": {
            "total_findings": total_findings,
            "secrets_high_current_tree": secrets_high,
            "secrets_history_only": history_only,
            "config_exposure_high": config_high,
            "sast_high_actionable": sast_high,
            "vuln_deps_critical_high": vuln_critical_high,
            "malicious_packages": malicious,
            "warnings": warnings,
        },
        "strict": bool(args.strict),
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }
    (out_dir / "security.json").write_text(json.dumps(audit, indent=2))

    # ------------------------------------------------------------------
    # security.md
    # ------------------------------------------------------------------
    md = render_markdown(repo, audit, groups)
    (out_dir / "security.md").write_text(md)

    # ------------------------------------------------------------------
    # security.sarif
    # ------------------------------------------------------------------
    (out_dir / "security.sarif").write_text(json.dumps(render_sarif(groups), indent=2))

    print(f"aggregate: verdict={verdict} ({verdict_reason})")
    return 0


def fmt_finding(f: dict) -> str:
    loc = f.get("path", f.get("package", "?"))
    line = f.get("line")
    if line:
        loc = f"{loc}:{line}"
    rule = f.get("rule", f.get("vuln_id", "?"))
    msg = f.get("message") or f.get("summary") or f.get("secret_redacted", "")
    sev = f.get("severity", "?").upper()
    extra = ""
    if f.get("in_test_file"):
        extra = " _(test file)_"
    if f.get("fixed_in"):
        extra += f" — fix: {', '.join(map(str, f['fixed_in'][:2]))}"
    return f"- **[{sev}]** `{loc}` — {rule}: {msg}{extra}"


def render_section(title: str, layer: dict, cap: int = 25) -> list[str]:
    findings = layer.get("findings", [])
    lines = [f"### {title} ({len(findings)} findings)", ""]
    if layer.get("skipped"):
        lines.append(f"_Skipped: {layer.get('reason', 'unknown')}_")
        lines.append("")
        return lines
    if not findings:
        lines.append("None.")
        lines.append("")
        return lines
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 2}
    ranked = sorted(findings, key=lambda f: order.get(f.get("severity", "unknown"), 2))
    lines.extend(fmt_finding(f) for f in ranked[:cap])
    if len(ranked) > cap:
        lines.append(f"- … and {len(ranked) - cap} more (see security.json)")
    lines.append("")
    return lines


def render_markdown(repo: Path, audit: dict, groups: dict) -> str:
    s = audit["summary"]
    lines = [
        f"# Security Audit — {repo.name}",
        "",
        f"**Verdict:** {audit['verdict'].upper()} — {audit['verdict_reason']}",
        "",
        "## At a glance",
        "",
        "| Layer | Tool | Findings | Blocking |",
        "|---|---|---|---|",
    ]
    blocking_map = {
        ("common", "secrets"): s["secrets_high_current_tree"],
        ("common", "git_history"): 0,
        ("common", "config_exposure"): s["config_exposure_high"],
    }
    for group, layers in groups.items():
        for name, layer in layers.items():
            tool = layer.get("tool") or ",".join(layer.get("tools", [])) or "—"
            n = len(layer.get("findings", []))
            if layer.get("skipped"):
                cell = "_skipped_"
            else:
                cell = str(n)
            blocking = blocking_map.get((group, name), "")
            if group != "common" and name == "sast":
                blocking = layer.get("counts", {}).get("high_actionable", 0)
            if group != "common" and name == "vuln_deps":
                bysev = layer.get("counts", {}).get("by_severity", {})
                blocking = bysev.get("critical", 0) + bysev.get("high", 0) + layer.get("counts", {}).get("malicious", 0)
            lines.append(f"| {group}:{name} | {tool} | {cell} | {blocking or ''} |")
    lines.append("")

    lines.extend(render_section("Secrets in working tree", groups["common"]["secrets"]))
    lines.extend(render_section("Secrets in git history", groups["common"]["git_history"]))
    lines.extend(render_section("Config & exposure", groups["common"]["config_exposure"]))
    for lang in ("python", "typescript"):
        if lang not in groups:
            continue
        lines.append(f"## {lang.capitalize()} findings")
        lines.append("")
        lines.extend(render_section("SAST", groups[lang]["sast"]))
        lines.extend(render_section("Vulnerable dependencies", groups[lang]["vuln_deps"]))
        lines.extend(render_section("Supply chain", groups[lang]["supply_chain"]))

    if s["warnings"]:
        lines.append("## Warnings")
        lines.append("")
        lines.extend(f"- {w}" for w in s["warnings"])
        lines.append("")

    lines.append("## Suggested next actions")
    lines.append("")
    n = 1
    if s["secrets_high_current_tree"]:
        lines.append(f"{n}. **Rotate every leaked credential now**, then remove it from code. Removal without rotation fixes nothing.")
        n += 1
    if s["malicious_packages"]:
        lines.append(f"{n}. **Remove the malicious package(s) immediately** and audit what their install scripts touched.")
        n += 1
    if s["vuln_deps_critical_high"]:
        lines.append(f"{n}. Upgrade the critical/high vulnerable dependencies (fix versions listed above).")
        n += 1
    if s["sast_high_actionable"]:
        lines.append(f"{n}. Fix the high-severity SAST findings (injection/TLS class issues first).")
        n += 1
    if s["config_exposure_high"]:
        lines.append(f"{n}. Untrack the sensitive files (`git rm --cached` + .gitignore) and rotate their contents.")
        n += 1
    if s["secrets_history_only"]:
        lines.append(f"{n}. Rotate history-leaked credentials; purge with `git filter-repo` only if the repo is/was shared.")
        n += 1
    if n == 1:
        lines.append("1. Nothing blocking. Re-run with all scanners installed (gitleaks, semgrep, osv-scanner) for maximum coverage.")
    lines.append("")
    return "\n".join(lines)


def render_sarif(groups: dict) -> dict:
    results = []
    rules_seen: dict[str, dict] = {}
    for group, layers in groups.items():
        for name, layer in layers.items():
            for f in layer.get("findings", []):
                rule_id = str(f.get("rule") or f.get("vuln_id") or f"{group}.{name}")
                if rule_id not in rules_seen:
                    rules_seen[rule_id] = {
                        "id": rule_id,
                        "shortDescription": {"text": (f.get("message") or f.get("summary") or rule_id)[:120]},
                    }
                msg = f.get("message") or f.get("summary") or f.get("secret_redacted") or rule_id
                if f.get("package"):
                    msg = f"{f['package']}@{f.get('version', '?')}: {msg}"
                results.append({
                    "ruleId": rule_id,
                    "level": SARIF_LEVEL.get(f.get("severity", "unknown"), "warning"),
                    "message": {"text": msg[:400]},
                    "locations": [{
                        "physicalLocation": {
                            "artifactLocation": {"uri": f.get("path") or f.get("manifest") or "package.json"},
                            "region": {"startLine": max(1, int(f.get("line") or 1))},
                        }
                    }],
                })
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "codebase-security",
                "informationUri": "https://github.com/",
                "rules": list(rules_seen.values()),
            }},
            "results": results,
        }],
    }


if __name__ == "__main__":
    sys.exit(main())
