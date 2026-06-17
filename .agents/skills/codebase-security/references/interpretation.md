# Interpreting the security audit

How to triage `security.json` / `security.md`, what to tell the user, and the traps.

---

## 1. Triage order (always this sequence)

1. **Secrets in the working tree (high, outside tests).** This is an incident. The credential must be **rotated first** — at the provider, immediately. Only then remove it from code and move it to env/secret manager. Saying "I deleted the line" without rotation is a false fix: the value is in git history, in every clone, possibly in CI logs.
2. **Malicious packages (`malicious: true`).** Remove immediately, then assume compromise: audit what the package's install scripts could have touched (env vars, `~/.ssh`, `.npmrc` tokens), and rotate anything a build machine had access to.
3. **Critical/high dependency CVEs with `fixed_in`.** Upgrade. If the fix is a major version, pin the patched minor instead of deferring.
4. **High SAST findings outside tests.** Injection-class first (command/SQL/XSS), then TLS-verification-off, then weak crypto.
5. **High config exposures.** Tracked `.env`/private keys (`git rm --cached` + gitignore + rotate), `pull_request_target` checkout patterns, privileged containers.
6. **History-only secrets.** Rotate (mandatory); purge history with `git filter-repo` only when the repo is shared/public — it rewrites every clone, coordinate first.
7. Everything else (warn tier) — fold into normal review.

## 2. Severity semantics per layer

- **secrets:** specific token formats (gitleaks rules, builtin `aws-*`/`github-*`/…) are `high`. `generic-assignment` matches are `medium` — real passwords but also the occasional fixture; read the context before escalating. `in_test_file: true` never blocks but still deserves a glance (prod credentials get pasted into tests more often than anyone admits).
- **sast (bandit):** trust `severity` × `confidence` together. `high/high` and `high/medium` block. Bandit `low` is mostly informational (`B404` "subprocess imported") — do not nag users about it; mention only the count.
- **vuln_deps:** `unknown` severity means the advisory has no GHSA severity attached (common with pip-audit output) — treat as medium and check `aliases` for the CVE.
- **supply_chain:** all heuristics. `possible-typosquat` is a *question* ("did you mean lodash?"), not an accusation. Confirm against the registry before recommending removal.

## 3. False-positive patterns to recognise

- **Docs with example URLs** (`amqp://user:pass@host`) — the builtin scanner drops dummy values (`pass`, `secret`, `changeme`…), but novel placeholders slip through. Fix the doc to use an obvious placeholder rather than allowlisting the file.
- **JWTs in test fixtures** — real-format, usually expired/fake. `in_test_file` already downgrades them; verify the payload isn't a live token before dismissing.
- **High-entropy non-secrets** — content hashes, base64 PNGs. Lockfiles and minified bundles are pre-excluded; if one appears, check whether it's actually derivable public data.
- **bandit B608 (SQL) on ORMs** — string-built query text that never reaches a driver. Check the sink.
- **`0.0.0.0` binds** — correct inside containers; the rule is `low` for this reason. Only escalate for processes on developer/host machines.

## 4. CI integration

```yaml
# GitHub Actions sketch
- run: bash .agents/skills/codebase-security/scripts/audit.sh . --strict --no-history
- uses: github/codeql-action/upload-sarif@v3
  if: always()
  with: { sarif_file: .security-audit/security.sarif }
```

- Use `--no-history` in CI (shallow clones make it meaningless; run history scans on a schedule from a full clone instead).
- `--strict` turns warn into exit 1 — adopt only after the baseline is clean, or every PR fails on day one.
- Baseline pattern for legacy repos: run once, file issues for the backlog, then gate PRs with `--changed-since origin/main` so only *new* findings block.

## 5. Agent consumption pattern

```python
audit = json.load(open(".security-audit/security.json"))
if audit["verdict"] == "fail":
    block(audit["verdict_reason"])           # do not open the PR
for w in audit["summary"]["warnings"]:
    note(w)                                   # skipped layers = unverified claims
secrets = audit["layers"]["common"]["secrets"]["findings"]
```

Never echo `secret_redacted` context lines back with the file content around them — quoting the file at that line re-leaks the value. Reference `path:line` only.

## 6. When to re-run

- Before every release; after every dependency bump (vuln/supply layers)
- On PRs via `--changed-since` (cheap)
- Weekly full run including git_history (needs gitleaks + full clone)
- Immediately after any incident — and after rotation, re-run to confirm the old value no longer appears anywhere
