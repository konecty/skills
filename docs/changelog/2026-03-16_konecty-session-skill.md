# konecty-session skill

## Summary
Added **konecty-session** skill to open a Konecty session (login) and persist the access token in `.env` and optionally `~/.konecty/credentials` for use by other skills and scripts.

## Motivation
Enable a single “login once” flow so the user can open a session in Konecty and reuse the token across other skills (e.g. future Konecty API skills) without re-entering credentials.

## What changed
- **skills/konecty-session/** added with:
  - **SKILL.md** — when to use, workflow (Node SDK vs Python script), where credentials are stored, autonomy (install what is needed).
  - **reference.md** — env vars (`KONECTY_URL`, `KONECTY_TOKEN`), credential file format, login API reference.
  - **scripts/login.py** — stdlib-only Python script: POST to `/rest/auth/login`, write `.env` and `~/.konecty/credentials` (ini). No pip install required.

## Technical impact
- Other skills should read `KONECTY_URL` and `KONECTY_TOKEN` from the environment (e.g. from .env). Node projects can use `~/.konecty/credentials` via `@konecty/sdk` or createClientFromCredentialFile.
- Script is Python 3, stdlib only; safe to run without installing dependencies.

## How to validate
- Run from skill dir: `python scripts/login.py --host <url> --user <user> --password <pass>` (or set KONECTY_USER / KONECTY_PASSWORD). Check `.env` and `~/.konecty/credentials` are created/updated.

## Files affected
- `skills/konecty-session/SKILL.md` (new)
- `skills/konecty-session/reference.md` (new)
- `skills/konecty-session/scripts/login.py` (new)
- `docs/changelog/README.md` (updated)
- `docs/changelog/2026-03-16_konecty-session-skill.md` (new)

## Migration
None.
