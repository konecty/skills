# Konecty Skills Installer — Validation Summary (T15)

**Date:** 2026-06-17
**Build:** `installer/` @ branch `feat/konecty-skills-consolidation`
**Unit tests:** 128 passing (`make installer-test`).

---

## Acceptance-test results

| Spec Independent Test | Result | Evidence |
|-----------------------|--------|----------|
| **INSTALL** — fresh dir with `.claude/` → both skills copied + manifest written | ✅ PASS | Integration run installed `konecty-data` + `konecty-meta` (44 files SHA-256-hashed in manifest), wrote `.env`, merged `CLAUDE.md` entry block. |
| **CRED** — write valid `~/.konecty/.env` | ✅ PASS (URL) / ⏭️ SKIP (live OTP) | `--yes --url` writes `KONECTY_URL` at `0o600`. Live OTP (`request-otp`/`verify-otp`) needs an interactive 6-digit code + a running Konecty mail flow — skipped per STATE D4 (OTP network branch validated manually, mocked in units). |
| **UPD** — edit installed `SKILL.md`, update preserves + reports conflict | ✅ PASS | After a local edit, `update --yes` kept the edited file byte-for-byte and reported `Preserved (locally modified): claude:konecty-data/SKILL.md`; a new upstream file was added. |
| **DOC** — uninstall removes skills, leaves `.env`; doctor runs | ✅ PASS | `uninstall --yes` removed tracked files + popped the manifest entry; an untracked sibling survived; `.env` left intact. `status`/`doctor` exit 0. |
| **Cursor engine path** | ⏭️ DEFERRED | `.cursor/skills/` not independently verified against Cursor docs (design open item). `claude` + `agents` paths validated. Keep `cursor` behind verification before advertising it. |

**Real network path:** the GitHub archive download (`_download` → `https://github.com/konecty/skills/archive/refs/heads/{ref}.tar.gz`) was exercised live and parsed correctly. The install/update/uninstall pipeline above was validated against **real skill content** by substituting only the network byte-source with a tarball built from the local working tree (byte-identical to what GitHub serves once merged).

---

## Findings / action items

### 🚩 BLOCKER — consolidated skills are not on `main` yet
`main` still ships the **old 18 skills** (`konecty-create`, `konecty-find`, `konecty-session`, `konecty-meta-*`, …). The consolidated `konecty-data` / `konecty-meta` exist only on this feature branch (not pushed). Therefore `uvx --from git+…/skills konecty-skills install` with the **default `ref=main` extracts 0 skills today**.
**Action:** merge `feat/konecty-skills-consolidation` → `main` (or push the branch and install with `--ref feat/konecty-skills-consolidation`) before the installer is usable in production. The installer is correct; this is a data/branch dependency.

### ⚠️ uvx local-path build caching (dev only)
`uvx --from ./installer` caches the built wheel by version (`0.1.0`); editing the source without bumping the version makes uvx re-run a stale build (`--refresh` did not force a rebuild for the local-path source). Workarounds during development: `uv cache clean konecty-skills`, bump the version, or use a venv (`pip install ./installer`). **Not an issue for production** `git+https://…` installs — uv keys those by commit SHA. Consider bumping `version` on each release.

---

## What was NOT run live
- **OTP end-to-end** against a real Konecty (interactive code). Covered by mocked unit tests + the `auth.py` subprocess contract; run manually once a dev Konecty session is available.
- **`doctor` connection probe** against a reachable Konecty with a valid token (probe logic unit-tested with a patched `_probe_konecty`).
