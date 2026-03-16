# konecty-session: OTP-only login and two-phase flow

## Summary
konecty-session was updated so that login is **OTP-only** when the namespace has OTP configured: the agent first requests an OTP, the user receives the code, then the agent receives the OTP from the user and verifies it to obtain and persist the token. If the namespace does not have OTP enabled, the skill cannot be used.

## Motivation
Login in Konecty is only allowed via OTP when the namespace has OTP configured (email/WhatsApp). Without OTP enabled, this session flow must not be used. The flow has two clear moments: request OTP → user provides OTP → verify and persist token, with care for token validity.

## What changed
- **SKILL.md:** Rewritten for OTP-only flow: (1) Check GET /api/auth/login-options; if no OTP enabled, inform user and stop. (2) Request OTP (POST /api/auth/request-otp with email or phone). (3) User provides 6-digit code. (4) Verify OTP (POST /api/auth/verify-otp) and persist token; document token validity/expiration.
- **reference.md:** Documents login-options, request-otp, verify-otp APIs; states that OTP must be enabled in the namespace; notes token validity and session expiration.
- **scripts/login.py:** Replaced password login with subcommands: `login-options` (GET login-options, exit 1 if OTP not enabled), `request-otp` (POST request-otp with --email or --phone), `verify-otp` (POST verify-otp with --email/--phone and --otp, then write .env and ~/.konecty/credentials). Stdlib-only, no password or /rest/auth/login.

## Technical impact
- Other skills continue to use KONECTY_URL and KONECTY_TOKEN; they should handle expired tokens by asking the user to run the OTP flow again.
- Script usage: `python3 scripts/login.py login-options --host <url>`, `python3 scripts/login.py request-otp --host <url> --email <email>`, `python3 scripts/login.py verify-otp --host <url> --email <email> --otp <code>` (or --phone with E.164).

## How to validate
- Run `python3 scripts/login.py login-options --host <konecty_url>` and confirm output includes emailOtpEnabled/whatsAppOtpEnabled.
- Run request-otp then verify-otp with a valid email/phone and OTP; confirm .env and credentials are written with authId.

## Files affected
- `skills/konecty-session/SKILL.md`
- `skills/konecty-session/reference.md`
- `skills/konecty-session/scripts/login.py`
- `docs/changelog/README.md`
- `docs/changelog/2026-03-16_konecty-session-otp-only.md` (new)

## Migration
Users who relied on password-based login via this skill must switch to the OTP flow. Namespaces without OTP cannot use this skill to obtain a session.
