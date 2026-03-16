---
name: konecty-session
description: Opens a Konecty session via OTP login (request OTP, then verify OTP) and persists the access token in .env or ~/.konecty/credentials for use by other skills. Use when the user wants to log in to Konecty with OTP, store credentials, set up KONECTY_TOKEN, or establish a session so other Konecty skills can call the API. Only works when the namespace has OTP enabled (email or WhatsApp).
---

# Konecty Session (OTP login)

Opens an authenticated session with Konecty using **OTP (one-time password)** and persists the token so other skills and scripts can use it. Login is allowed only when the namespace has OTP configured (email and/or WhatsApp); if OTP is not enabled, this skill cannot be used to obtain a session.

## When to use this skill

- User wants to "log in to Konecty", "open a Konecty session", "save Konecty credentials", or "set up Konecty for other skills" and the namespace uses OTP.
- User needs `KONECTY_TOKEN` for automation or other skills and is willing to complete OTP (receive code, then paste it).

## Two-phase flow

1. **Request OTP** — Agent calls the API to send a one-time code to the user's email or phone. User receives the code (email or WhatsApp, according to namespace config).
2. **Receive OTP and obtain token** — User informs the agent of the 6-digit code. Agent calls the verify API, receives the session token (`authId`), and persists it. Consider token validity (session expiration); when the token expires, the user must run this flow again.

## Workflow

### 1. Check if OTP is available

- Call `GET {host}/api/auth/login-options`. Response: `{ passwordEnabled, emailOtpEnabled, whatsAppOtpEnabled }`.
- If neither `emailOtpEnabled` nor `whatsAppOtpEnabled` is true, inform the user: **"This Konecty namespace does not have OTP login enabled. This skill cannot open a session here."** Do not proceed with request-otp.
- If at least one OTP method is true, continue. Gather **host** (e.g. `KONECTY_URL`) and either **email** or **phone number** (E.164, e.g. `+5511999999999`) for the user who will receive the code.

### 2. Request OTP (first moment)

- **API:** `POST {host}/api/auth/request-otp`  
  **Body (JSON):** `{ "email": "user@example.com" }` **or** `{ "phoneNumber": "+5511999999999" }` (exactly one).
- On success, the server sends the code to the user's email or WhatsApp. Tell the user: **"A verification code was sent to your email/phone. When you receive the 6-digit code, paste it here."**
- You can use the bundled script:  
  `python scripts/login.py request-otp --host <url> --email <email>`  
  or `python scripts/login.py request-otp --host <url> --phone <E164>`  
  (see [scripts/login.py](scripts/login.py)).

### 3. Receive OTP and persist token (second moment)

- When the user provides the 6-digit OTP code, call the verify API and then persist the token.
- **API:** `POST {host}/api/auth/verify-otp`  
  **Body (JSON):** `{ "email": "user@example.com", "otpCode": "123456" }` or `{ "phoneNumber": "+5511999999999", "otpCode": "123456" }`.  
  **Response:** `{ success, authId, user }` — same shape as password login; use `authId` as the session token.
- Run the script to verify and write credentials:  
  `python scripts/login.py verify-otp --host <url> --email <email> --otp <code>`  
  or `--phone <E164> --otp <code>`.  
  The script writes **~/.konecty/.env** and **~/.konecty/credentials**; it does **not** store the OTP code, only the resulting token.
- **Token validity:** The session token has a validity period defined by the namespace (e.g. session expiration). Other skills should use `KONECTY_TOKEN` until it expires; when the API returns 401 or session errors, the user must run this OTP flow again to obtain a new token.

### 4. Where credentials are stored (shared for all skills)

- **~/.konecty/.env**: `KONECTY_URL=<host>`, `KONECTY_TOKEN=<authId>`, optionally `KONECTY_USER_ID=<user._id>`. Stored in the same directory as credentials so **all Konecty skills** can load it (e.g. source or load from `~/.konecty/.env`).
- **~/.konecty/credentials**: ini format for Node `@konecty/sdk` and CLI; section `[default]` or `[<host>]` with `host`, `userId`, `authId`.

Other skills should read `KONECTY_URL` and `KONECTY_TOKEN` from the environment (after loading ~/.konecty/.env when needed) and handle expired tokens (e.g. ask the user to run konecty-session again).

## Security and validity

- Do not commit `~/.konecty/.env` or `~/.konecty/credentials`; add `~/.konecty/` to `.gitignore` if storing repo-specific paths.
- Store only the session token (`authId`), never the OTP code or password.
- OTP codes are short-lived and single-use; after verify-otp the code is consumed.
- Session tokens expire; document or remind the user to re-run this flow when the token is no longer valid.

## Reference

- APIs (login-options, request-otp, verify-otp) and token validity: [reference.md](reference.md)
- Script usage: `python scripts/login.py --help`, `python scripts/login.py request-otp --help`, `python scripts/login.py verify-otp --help`.
