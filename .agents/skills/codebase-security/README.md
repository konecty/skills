# codebase-security

Security audit skill for Python + TypeScript/JavaScript repositories: secrets
(working tree and git history), SAST, vulnerable dependencies (CVEs), malicious
packages, supply-chain hygiene, and config/exposure checks. Companion to
`codebase-intelligence` (code health) — zero overlap by design.

```bash
bash scripts/audit.sh <repo-path>                      # full audit
bash scripts/audit.sh <repo-path> --changed-since main # PR scope
bash scripts/audit.sh <repo-path> --strict --no-history # CI gate
```

Outputs in `<repo>/.security-audit/`: `security.json` (agent contract),
`security.md` (human report), `security.sarif` (GitHub code scanning).
Exit codes: 0 pass/warn · 1 fail · 2 setup error.

Only `python3` is required; every scanner degrades gracefully (PATH binary →
`uvx`/`npx` → builtin fallback → explicit `skipped` with install hint).
Recommended for full coverage: `gitleaks`, `osv-scanner`, `semgrep`.

See `SKILL.md` for the full contract, `references/interpretation.md` for
triage guidance, `references/tools.md` for tool rationale.
