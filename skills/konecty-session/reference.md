# Konecty Session — Reference (OTP flow)

## Prerequisite: OTP enabled in namespace

Login via this skill is only possible when the Konecty namespace has OTP configured (email and/or WhatsApp). If the namespace does not have OTP enabled, the session flow cannot be used. Check **login-options** first.

## APIs (OTP flow)

Base URL: `{KONECTY_URL}` (no trailing slash). All request/verify bodies are JSON, `Content-Type: application/json`.

### GET /api/auth/login-options

Returns which login methods are enabled for the current namespace.

**Response:** `{ passwordEnabled: boolean, emailOtpEnabled: boolean, whatsAppOtpEnabled: boolean }`

- If neither `emailOtpEnabled` nor `whatsAppOtpEnabled` is true, the konecty-session skill cannot obtain a token (OTP login not available).

### POST /api/auth/request-otp

Sends a one-time code to the user's email or phone. Exactly one of `email` or `phoneNumber` must be provided.

**Body:**
- `{ "email": "user@example.com" }` or
- `{ "phoneNumber": "+5511999999999" }` (E.164 format)

**Response:** `{ success: true, message: "OTP sent via ..." }` or `{ success: false, errors: [...] }`

After success, the user receives the 6-digit code by email or WhatsApp. The agent should then ask the user to provide the code.

### POST /api/auth/verify-otp

Verifies the OTP code and returns the session token. Same identifier (email or phone) as in request-otp, plus the 6-digit code.

**Body:**
- `{ "email": "user@example.com", "otpCode": "123456" }` or
- `{ "phoneNumber": "+5511999999999", "otpCode": "123456" }`

**Response (success):** `{ success: true, logged: true, authId: "<token>", user: { _id, ... } }`

- `authId` is the session token to store as `KONECTY_TOKEN`.
- Use `user._id` optionally as `KONECTY_USER_ID`.

After a successful verify-otp, persist `authId` (and optionally `user._id`) to **~/.konecty/.env** and **~/.konecty/credentials** (shared location so all skills can use the same token). Do not store the OTP code.

## Token validity

The session token (`authId`) is valid for a period defined by the namespace (e.g. `sessionExpirationInSeconds`). After expiration, API calls using that token will fail (e.g. 401). Other skills should treat invalid/expired token by asking the user to run the konecty-session flow again (request OTP → receive code → verify OTP → persist new token).

## Environment variables (for other skills)

| Variable | Required | Description |
|----------|----------|-------------|
| `KONECTY_URL` | Yes | Konecty base URL, no trailing slash |
| `KONECTY_TOKEN` | Yes | Session token (`authId`) from verify-otp |
| `KONECTY_USER_ID` | No | Logged-in user `_id` |

## Shared credential location (all skills)

Token and URL are written to **~/.konecty/** so any skill can use them:

- **~/.konecty/.env** — `KONECTY_URL=...`, `KONECTY_TOKEN=...`, `KONECTY_USER_ID=...` (load with `source ~/.konecty/.env` or your language’s env loader).
- **~/.konecty/credentials** — ini format for Node `@konecty/sdk` and CLI:

```ini
[default]
host = https://app.konecty.com
userId = <user _id>
authId = <session token>
```

`authId` is the value of `KONECTY_TOKEN`.
