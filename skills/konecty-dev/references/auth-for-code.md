# Konecty Authentication for Code — Reference

> This doc covers the **service-account / server-side token** model used in application code and
> CI pipelines. For the interactive OTP flow used by the `konecty-data` skill, see
> `skills/konecty-data/references/auth.md`.

---

## The model

`POST /rest/auth/login` returns `{ authId: "<token>", ... }`.
That `authId` string is the **entire value** of the `Authorization` header for every subsequent
request. There is no "Bearer" prefix, no wrapping — just the raw token.

```
Authorization: <authId value>
```

Alternatively, requests carrying a cookie `_authTokenId=<token>` are also accepted (browser SSO
use case; not recommended for server code).

---

## Obtain a service-account token

Create a dedicated Konecty user for the integration (least-privilege, no admin flag unless
required), then log in once to capture its `authId`.

### CORS note

`/rest/auth/*` is in the strict-CORS zone. Server-to-server calls without an `Origin` header are
accepted **only when an `Authorization` header is present** or when `Sec-Fetch-Site: none` is set.
For a plain `curl` or script that does not send `Origin`, this is fine as long as you are not
also relying on cookies. Never send a cross-origin browser request to this endpoint without an
allow-listed `Origin`.

### Password field

Pass the **raw plaintext password** in the `password` field. The server bcrypt-verifies it
directly. The TypeScript SDK additionally sends a `password_SHA256` field (SHA-256 hex of the
plaintext) so that legacy accounts hashed against a pre-hash are also accepted — you can include
it for compatibility, but `password` alone is sufficient for all accounts created after
Konecty 3.8.10.

### curl

```bash
KONECTY_URL="https://app.example.com"

response=$(curl -s -X POST "${KONECTY_URL}/rest/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"user":"svc-account@example.com","password":"<password>"}')

export KONECTY_TOKEN=$(echo "$response" | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['authId'])")

echo "Token: $KONECTY_TOKEN"
```

### Python (no SDK)

```python
import os, requests

resp = requests.post(
    f"{os.environ['KONECTY_URL']}/rest/auth/login",
    json={"user": "svc-account@example.com", "password": "<password>"},
)
resp.raise_for_status()
body = resp.json()
assert body["success"], body.get("errors")
token = body["authId"]   # store this in your secret manager
```

### TypeScript SDK

```typescript
import { KonectyClient } from '@konecty/sdk';

const client = new KonectyClient({ endpoint: process.env.KONECTY_URL });
const result = await client.login('svc-account@example.com', '<password>');
// result.authId — store this; client.options.accessKey is now set internally
```

The SDK's `login()` sends `password` (MD5) and `password_SHA256` (SHA-256) together for
backward compatibility. `result.authId` is the token.

---

## Use the token in code

**Always inject the token from the environment, never hardcode it.**

### Python SDK

```python
import os, asyncio
from KonectySdkPython import KonectyClient

client = KonectyClient(
    base_url=os.environ["KONECTY_URL"],
    token=os.environ["KONECTY_TOKEN"],
)
# client.headers == {"Authorization": "<token>"}
```

### TypeScript SDK

```typescript
import { KonectyClient } from '@konecty/sdk';

const client = new KonectyClient({
    endpoint: process.env.KONECTY_URL,
    accessKey: process.env.KONECTY_TOKEN,
});
```

### Raw HTTP (curl / any language)

```bash
curl -s "${KONECTY_URL}/rest/data/Contact/find?fields=name,email" \
  -H "Authorization: ${KONECTY_TOKEN}"
```

---

## Security practices

- **Store in environment variables or a secret manager** (Vault, AWS Secrets Manager, GitHub
  Actions secrets, etc.). Never hardcode the token in source files.
- **Gitignore `.env` files** — add `.env` and `*.env` to `.gitignore`. Set file permissions
  to `600` for local credential files (`chmod 600 .env`).
- **Use a least-privilege service account** — grant only the modules and operations the
  integration actually needs. Avoid using an admin user token in application code.
- **Rotate tokens** — re-authenticate the service account periodically or on suspected
  compromise. The server retains up to `sessionExpirationInSeconds` (namespace config,
  default 30 days) before expiring a token. Treat it as a long-lived credential and rotate
  it like a password.
- **Never log the token** — ensure your HTTP client or logging middleware does not capture
  the `Authorization` header in log output.

---

## Dev-time shortcut (NOT for production)

During local development you can reuse the token written by the `konecty-data` skill:

```bash
source ~/.konecty/.env   # exports KONECTY_URL and KONECTY_TOKEN
python my_script.py      # or: node my_script.js
```

This token belongs to your interactive user account. It is convenient for development but
must not be used in production deployments — use an injected service-account token there.
