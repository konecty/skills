---
name: codebase-security
description: Run a full security audit of a repository — hardcoded secrets (working tree AND git history), SAST insecure-code patterns, known-vulnerable dependencies (CVEs), malicious/compromised packages, supply-chain hygiene, and config/exposure risks (committed .env, Dockerfile, CI workflows) — for Python and TypeScript/JavaScript codebases. Emits unified structured JSON (for agents), a human-readable Markdown report, and SARIF for CI code-scanning. Use this skill whenever the user asks to audit security, scan for secrets or leaked keys, check dependencies for CVEs or compromised packages, review code for vulnerabilities, or before a release/deploy. Works on monorepos with both languages simultaneously.
---

# Codebase Security

Audit a Python and/or TypeScript/JavaScript repository for the things that get companies breached: leaked credentials, injectable code, vulnerable or malicious dependencies, and exposed configuration. This skill orchestrates nine independent analyses (three language-agnostic + three per language), normalizes their output into a single JSON contract, and renders a Markdown report plus SARIF for CI integration.

The audience for the JSON is **another agent** deciding what to fix or block. The Markdown is for a **human** deciding what to rotate and patch first. The SARIF is for **GitHub code scanning / IDEs**.

**Redaction policy (non-negotiable):** secret values never appear in any output — not in `security.json`, not in the report, not on stdout. Findings carry only the first 4 characters plus the length. When relaying findings to the user, never read the flagged line back verbatim.

## Why this skill exists

The companion skill `codebase-intelligence` answers "is this codebase healthy?". This one answers "is this codebase safe to ship?" — a different toolchain and a different verdict policy (security findings block on severity, not on volume).

| Question | Linter / `npm audit` alone | This skill |
|---|---|---|
| AWS key hardcoded in a source file | ✗ | ✓ |
| Secret committed last year, deleted since | ✗ | ✓ (git history) |
| `subprocess(..., shell=True)` with user input | ✗ | ✓ |
| Dependency with a known CVE | partial (one ecosystem) | ✓ (both, one pass) |
| Malicious package (OSV `MAL-` advisory) | ✗ | ✓ |
| Typosquatted dependency name | ✗ | ✓ |
| `.env` / private key tracked by git | ✗ | ✓ |
| `pull_request_target` exfiltration vector in CI | ✗ | ✓ |
| All of the above for Python AND TypeScript | ✗ | ✓ |

## When to use

- The user asks for a security audit, security review, vulnerability scan, or "is this safe to deploy/release"
- The user mentions a symptom: leaked key, hardcoded secret, CVE, vulnerable dependency, compromised/malicious package, supply-chain risk
- Before a first public release or open-sourcing a repo (run with git history layer ON)
- After adding dependencies (vuln + supply-chain layers)
- On a schedule in CI (use `--strict` and the SARIF output)

Do **not** use for:

- Code health / refactoring (use `codebase-intelligence`)
- Penetration testing or runtime analysis (this is static)
- Authn/authz design review (needs a human who knows the domain)
- License compliance (different problem)

## The nine analyses

| Layer | Scope | Primary tool | Fallback | Catches |
|---|---|---|---|---|
| 1. secrets | all files | `gitleaks dir` | builtin regex + entropy | Hardcoded API keys, tokens, private keys, passwords in URLs |
| 2. git_history | git log | `gitleaks git` | — (skipped, with hint) | Secrets committed and later "deleted" |
| 3. config_exposure | tracked files | builtin | — | Committed .env/keys, Dockerfile as root, curl\|sh, privileged compose, `pull_request_target` checkout, CORS `*`, debug flags, TLS off |
| 4. sast | Python | `bandit` (PATH or `uvx`) | — | Injection, `shell=True`, weak crypto, `verify=False`, pickle/yaml.load … |
| 4. sast | TS/JS | `semgrep p/security-audit` | builtin regex | eval, command/SQL injection, XSS sinks, `createCipher`, `rejectUnauthorized:false` … |
| 5. vuln_deps | Python | `osv-scanner`, else `pip-audit` (uvx; handles `uv.lock` via `uv export`) | — | Known CVEs + OSV `MAL-` malicious advisories |
| 5. vuln_deps | TS/JS | `npm`/`pnpm`/`yarn audit` + `osv-scanner` merge | — | Known CVEs + malicious advisories |
| 6. supply_chain | Python | builtin (offline) | — | git/URL deps, unpinned reqs, missing lockfile, typosquat heuristic |
| 6. supply_chain | TS/JS | builtin (offline) | — | Same + install scripts (pre/postinstall) in direct deps, URL overrides |

Design choices worth knowing:

- **No tool is a hard requirement except `python3`.** Each layer degrades: PATH binary → `uvx`/`npx` fallback where possible → builtin implementation → explicit `skipped` entry with an install hint. A skipped layer is **never silently green** — it lands in `summary.warnings` and the report.
- **vuln_deps needs network** (OSV/PyPI/npm advisory APIs). Offline runs mark the layer skipped.
- **Malicious packages** surface in two complementary ways: OSV `MAL-` advisories via layer 5 (authoritative, needs network) and structural red flags via layer 6 (offline heuristics: typosquats, URL deps, install scripts).

## How to run the audit

### Flow A — full audit, auto-detect languages (default)

```bash
bash scripts/audit.sh <repo-path>
```

Writes to `<repo-path>/.security-audit/` (gitignored automatically — the report references secret locations):
- `security.json` — unified machine contract
- `security.md` — human report
- `security.sarif` — SARIF 2.1.0 for code scanning
- `raw/*/*.json` — per-layer intermediates

### Flow B — PR / changed-files only

```bash
bash scripts/audit.sh <repo-path> --changed-since main
```

File-level layers (secrets, sast) restrict to committed changes since the ref; manifest-level layers (vuln_deps, supply_chain, config_exposure) always run in full because the lockfile is the unit of analysis. No changed files → those layers report `skipped`, they do not silently fall back to a full scan.

### Flow C — single language / skipping layers

```bash
bash scripts/audit.sh <repo-path> --lang python
bash scripts/audit.sh <repo-path> --no-history          # skip the (slow) git history layer
bash scripts/audit.sh <repo-path> --skip supply_chain
```

### Flow D — CI gate

```bash
bash scripts/audit.sh <repo-path> --strict   # exit 1 on warn as well as fail
```

Upload `security.sarif` to GitHub code scanning for inline PR annotations.

### Flow E — single layer

```bash
python3 scripts/common/secrets.py <repo> --out out/raw/common/secrets.json
python3 scripts/python/sast.py <repo> --out out/raw/python/sast.json
node scripts/typescript/supply_chain.js <repo> --out out/raw/typescript/supply_chain.json
```

Then `python3 scripts/aggregate_all.py <out-dir> --repo <repo> --has-python 1 --has-typescript 1`.

## Setup (all optional, in coverage order)

```bash
brew install gitleaks        # secrets + history (biggest coverage win)
brew install osv-scanner     # CVEs + malicious advisories, both ecosystems
uv tool install bandit       # or rely on the automatic `uvx bandit` fallback
uv tool install pip-audit    # or rely on `uvx pip-audit`
brew install semgrep         # upgrades TS SAST from builtin regex to real rules
```

With nothing installed, the audit still runs: builtin secrets regex, builtin TS SAST rules, bandit/pip-audit via `uvx`, offline supply-chain checks. The report's "At a glance" table shows which engine actually ran per layer (`fallback_used: true` in the JSON).

## Output contract (security.json, schema v1.0)

```json
{
  "schema_version": "1.0",
  "kind": "security",
  "repo": {"path": "...", "head_sha": "...", "languages": ["python"], "analysis_scope": "full"},
  "layers": {
    "common":     {"secrets": {}, "git_history": {}, "config_exposure": {}},
    "python":     {"sast": {}, "vuln_deps": {}, "supply_chain": {}},
    "typescript": {"sast": {}, "vuln_deps": {}, "supply_chain": {}}
  },
  "summary": {
    "total_findings": 12,
    "secrets_high_current_tree": 0,
    "secrets_history_only": 1,
    "config_exposure_high": 0,
    "sast_high_actionable": 0,
    "vuln_deps_critical_high": 2,
    "malicious_packages": 0,
    "warnings": ["layer `common:git_history` skipped: gitleaks not installed — ..."]
  },
  "verdict": "fail",
  "verdict_reason": "2 critical/high dependency vulnerability(ies)"
}
```

Each layer block: `{tool, skipped, fallback_used, counts, findings[]}`. Key finding shapes:

**Secret** (value always redacted):
```json
{"path": "src/config.py", "line": 12, "rule": "github-token", "severity": "high",
 "secret_redacted": "ghp_…(40 chars)", "entropy": 4.8, "in_test_file": false,
 "tool": "gitleaks", "remediation": "Rotate the credential, then remove it from the code. Removal alone is not enough."}
```

**SAST:**
```json
{"path": "src/runner.py", "line": 5, "rule": "B602", "severity": "high", "confidence": "high",
 "message": "subprocess call with shell=True identified", "cwe": "CWE-78", "in_test_file": false, "tool": "bandit"}
```

**Dependency vulnerability:**
```json
{"package": "requests", "version": "2.19.0", "vuln_id": "GHSA-x84v-xcm2-53pg",
 "aliases": ["CVE-2018-18074"], "severity": "high", "malicious": false,
 "fixed_in": ["2.20.0"], "manifest": "uv.lock", "tool": "pip-audit"}
```

**Supply chain:**
```json
{"package": "lodahs", "rule": "possible-typosquat", "severity": "medium",
 "message": "Name is one edit away from popular package(s): lodash — verify it is intentional",
 "manifest": "package.json", "tool": "supply-chain"}
```

### Verdict logic

| Verdict | Trigger |
|---|---|
| `fail` | High-severity secret in working tree (outside tests) · high-severity exposure (tracked sensitive file, TLS off, privileged container, CI exfil vector) · high SAST with high/medium confidence outside tests · any malicious package · critical/high dependency CVE |
| `warn` | Anything else found: history-only secrets, medium/low findings, unknown-severity CVEs, unpinned deps, install scripts, skipped layers |
| `pass` | Zero findings, no skipped layers worth flagging |

Exit codes: `0` pass/warn, `1` fail (or warn with `--strict`), `2` setup error.

## Markdown report structure

`security.md` follows a fixed template — keep it grep-stable:

```markdown
# Security Audit — <repo-name>
**Verdict:** PASS | WARN | FAIL — <reason>
## At a glance            <table: layer | tool | findings | blocking>
### Secrets in working tree (N findings)
### Secrets in git history (N findings)
### Config & exposure (N findings)
## Python findings        ### SAST / ### Vulnerable dependencies / ### Supply chain
## TypeScript findings    ### SAST / ### Vulnerable dependencies / ### Supply chain
## Warnings
## Suggested next actions <rotation first, malicious removal second, upgrades third>
```

## Failure modes to handle gracefully

1. **gitleaks missing** — secrets falls back to builtin regex (flagged `fallback_used`); git_history is skipped with an install hint. Tell the user coverage is reduced.
2. **Offline / no network** — vuln_deps skips (pip-audit/osv-scanner/npm audit all need advisory APIs). The verdict can still `fail` on secrets/SAST; it can never claim dependency safety it didn't check — skipped layers are listed in warnings.
3. **uv-managed project without requirements.txt** — handled: `uv export` produces a pinned temp file for pip-audit. Needs `uv` on PATH.
4. **Unpinned hand-written requirements.txt** — pip-audit's fast path needs pins; the script retries with venv-based resolution, which can fail in sandboxes. If skipped, suggest a lockfile (the supply_chain layer will already be flagging it).
5. **semgrep installed but offline** — registry rules can't download; Python keeps bandit, TS falls back to builtin rules.
6. **False-positive secrets in docs/fixtures** — builtin scanner filters placeholder words, dummy values, pure identifiers, and low-entropy captures; findings in test paths are marked `in_test_file` and never block. Remaining FPs: prefer fixing the doc to use an obvious placeholder over allowlisting.
7. **Monorepo with multiple package.json** — vuln_deps runs at repo root only; osv-scanner (if installed) covers nested lockfiles recursively. Recommend installing it for monorepos.
8. **Shallow clone** — git_history sees only the truncated log; note it if `git rev-list --count HEAD` is suspiciously small.

## Reading the output

- Triage order and what to say to the user: `references/interpretation.md`
- Tool selection rationale, per-tool sharp edges, and CI recipes: `references/tools.md`
- Custom gitleaks allowlist template: `assets/gitleaks.template.toml`

The single most important rule when relaying results: **a leaked secret is an incident, not a lint finding.** The first action is always rotation — deleting the line (or even rewriting history) does not un-leak a credential that was ever pushed.

## What this skill is not

- Not a replacement for `codebase-intelligence` — zero overlap by design (it explicitly excludes security; this excludes code health).
- Not a pentest, not a DAST, not a fuzzer — static only.
- Not an authz reviewer — it cannot know which endpoints *should* be public.
- Not a guarantee — `pass` means "the scanners found nothing", not "secure".

## Quick sanity check

1. `security.json` valid (`python3 -m json.tool < security.json > /dev/null`) and `schema_version == "1.0"`
2. `verdict` ∈ {pass, warn, fail}; exit code matches (`--strict` promotes warn)
3. Every detected language has all three layer files under `raw/<lang>/`
4. No secret value appears anywhere in the three output files (spot-check `security.md`)
5. Skipped layers appear in both `summary.warnings` and the report's Warnings section
