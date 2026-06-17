# Tool selection rationale & sharp edges

Why each engine was chosen, what its fallback costs, and the flags that matter.

---

## Secrets: gitleaks (primary) / builtin regex (fallback)

**Why gitleaks over trufflehog:** single static Go binary, ~190 curated rules with per-rule entropy tuning, two CLI modes that map exactly to our two layers (`dir` = working tree, `git` = history), and JSON report output. Trufflehog's killer feature is credential *verification* (it calls the provider to test the key) — powerful, but it phones home with the secret, which is the wrong default for an agent-driven audit.

Sharp edges:
- CLI dialect changed in v8.19 (`detect --no-git` → `dir`). The scripts try both.
- `--exit-code 0` is required — by default gitleaks exits 1 on findings, which our orchestrator would misread as tool failure.
- Allowlisting: drop `assets/gitleaks.template.toml` into the repo as `.gitleaks.toml`; gitleaks picks it up automatically. Prefer per-finding fingerprint allowlists over path allowlists.

**Builtin fallback:** ~16 token-format rules + an entropy-gated generic-assignment rule. Filters: placeholder words in the line, dummy values (`pass`, `changeme`…), pure identifiers (`args.password`), values containing code punctuation, Shannon entropy < 3.0 for loose rules. It will miss rotated formats and exotic providers — always report `fallback_used: true` to the user as reduced coverage.

## SAST Python: bandit (primary) + semgrep (bonus)

**Why bandit:** the standard, AST-based, zero config, granular severity×confidence, CWE tags, runs fine via `uvx bandit` with no install. **Why not semgrep as primary:** registry rules need network + the binary is heavy; as an optional second engine it adds cross-function patterns bandit misses. Dedupe is by `path:line`, bandit wins.

Sharp edges:
- `-x` excludes match **substrings of absolute paths**. Always anchor with globs (`*/tests/*`), never bare words — a bare `test` exclude silently empties the scan for any repo whose path contains "test".
- B105/B106/B107 messages quote the hardcoded password verbatim — the script redacts them before they reach the report.
- bandit `low`×`low` is noise by design; surface counts, not items.

## SAST TypeScript: semgrep (primary) / builtin regex (fallback)

**Why semgrep over eslint-plugin-security:** eslint-plugin-security needs an eslint config harmonised with the project's own (flat vs legacy config conflicts break runs); semgrep is standalone and its `p/security-audit` pack covers JS/TS injection, XSS sinks, crypto misuse. The builtin fallback is 12 regex rules for the classic sinks (eval, exec-with-concat, innerHTML, createCipher, rejectUnauthorized…) — honest but shallow; line-based regex cannot see dataflow.

## SCA Python: osv-scanner (preferred) / pip-audit (fallback)

**Why osv-scanner first:** one binary covers PyPI *and* npm, reads lockfiles directly (uv.lock, poetry.lock, requirements.txt), recurses into monorepos, and — uniquely — reports OSV `MAL-*` **malicious package advisories**, which is the "compromised packages" requirement. CLI dialect differs between v1 and v2; the scripts try both.

**pip-audit path:** for uv projects there is no requirements.txt, so the script runs `uv export --format requirements-txt --no-emit-project --no-hashes` to a temp file, then `pip-audit -r tmp --no-deps --disable-pip` (fast path, no venv — valid because the export is fully pinned). Hand-written unpinned requirements trigger a retry with venv-based resolution, which is slow and can fail in sandboxes. pip-audit JSON carries **no severity field** — those findings surface as `unknown` severity; check the CVE manually before dismissing.

## SCA TypeScript: npm/pnpm/yarn audit + osv-scanner merge

Lockfile determines the command (`package-lock.json` → npm, etc.). npm audit v2 JSON nests advisories under `via`; transitive entries may have no advisory object — those keep `vuln_id: "transitive"`. yarn classic emits ndjson (`auditAdvisory` rows). All need network and a registry that serves the audit endpoint (private registries often don't — expect `skipped`).

## Supply chain: builtin, offline by design

The complement to SCA: structure instead of advisories. Typosquat check is edit-distance-1 against embedded top-package lists (~60 per ecosystem) — a heuristic that asks a question, not a verdict. Install-script enumeration needs `node_modules` present (reads each direct dep's `package.json` scripts); without it the layer says so instead of pretending it checked.

## Config/exposure: builtin

`git ls-files` is the source of truth — only **tracked** files count as exposures. Content confirmation avoids cheap FPs: a `.pem` without `PRIVATE KEY` inside is public material (info), a service-account `.json` without `"private_key"` is config (low).

## SARIF output

Minimal but valid 2.1.0: one run, one driver (`codebase-security`), rules deduped by id, severity mapped critical/high→error, medium→warning, low/info→note. Good enough for GitHub code scanning upload and IDE SARIF viewers. Package-level findings (no file/line) anchor at the manifest file, line 1.
