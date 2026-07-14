# Authentication — user MCP

Both MCP endpoints are **stateless**: the server keeps no MCP conversation auth
session. The token travels with every protected call.

## Default path — OAuth (Claude Code)

When the `konecty` MCP server was registered normally (see **konecty-setup**),
Claude Code handles the OAuth flow natively: browser login + consent on first use,
token refresh afterwards. The access token is sent as an `Authorization: Bearer`
header on every call and resolved server-side.

**Consequence:** call every authenticated tool **without** an `authTokenId`
argument. There is nothing to store or manage. Granted scopes are `read` (and
`write` when the namespace enables `mcpUserWriteEnabled`).

If calls start failing with `401` / `UNAUTHORIZED`, Claude Code's re-authentication
(new browser login) is the fix — guide the user via **konecty-setup** ("fix auth").

## Fallback path — OTP via `session_*` tools

Use only when OAuth is not available for this deployment. The flow (all on the
`konecty` server):

1. `session_login_options` — inspect which OTP methods are enabled
   (output: `options`, `nextSteps`, request/verify examples).
2. Request the code on the chosen channel:
   - `session_request_otp_email` — input `email`.
   - `session_request_otp_phone` — input `phoneNumber` in **E.164**
     (e.g. `+5511999999999`). If the user gives only Brazilian DDD + local number,
     prepend `+55`. Use the same normalized number to request and verify.
3. Ask the user for the received code, then verify with the matching tool:
   - `session_verify_otp_email` / `session_verify_otp_phone` — input the channel
     identifier plus `otpCode`. Output: `authId`, `user`, `logged`, `instructions`.
4. Keep `authId` in the conversation and send it as the `authTokenId` argument on
   **every** authenticated tool call from then on. Never store or echo the OTP code.

`session_logout` (input `authTokenId`) ends the session.

### Error recovery (OTP path)

When an authenticated tool returns `UNAUTHORIZED`:

1. Re-run the OTP flow until a verify tool returns a fresh `authId`.
2. Retry the same tool including the new `authTokenId`.
3. If it still fails, request a new OTP and replace the stored token.

## Admin note

Metadata operations authenticate differently (admin MCP, `konecty-admin` server) —
that is **konecty-meta** territory, not this skill.
