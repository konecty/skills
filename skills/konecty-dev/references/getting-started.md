# Getting Started with Konecty Integration Code

This skill teaches you how to write code that integrates with the Konecty platform. The preferred path is an official SDK (Python or TypeScript/Node.js); use native HTTP when you need a capability the SDK does not yet expose; fall back to plain REST for other languages. For server-side document logic (before-save hooks, computed fields), see `hooks.md`.

## Track Choice

```
Your language?
│
├─ Python ──────────────────────────────────────────► use konecty_sdk_python
│
├─ TypeScript / Node.js ────────────────────────────► use @konecty/sdk
│
├─ Other language ──────────────────────────────────► REST API → rest-api.md
│
└─ Writing server-side document logic (hooks) ──────► hooks.md

Within Python or TS:
  SDK covers your use case? ─────────────────────────► use SDK method
  Feature missing from SDK? ─────────────────────────► native HTTP with the
                                                        same token (see rest-api.md)
```

## Install

**Python** (requires Python ≥ 3.11):

```bash
pip install konecty_sdk_python==2.0.3
```

**TypeScript / Node.js** (requires Node ≥ 16):

```bash
npm install @konecty/sdk@1.0.0
```

## First Client

Credentials come from environment variables. See `auth-for-code.md` for how to obtain a token.

```bash
export KONECTY_URL=https://your-instance.konecty.com
export KONECTY_TOKEN=your-auth-token
```

### Python — async

```python
import asyncio
import os
from KonectySdkPython.lib.client import KonectyClient
from KonectySdkPython.lib.filters import KonectyFilter, KonectyFindParams

client = KonectyClient(
    base_url=os.environ["KONECTY_URL"],
    token=os.environ["KONECTY_TOKEN"],
)

async def main() -> None:
    params = KonectyFindParams(
        filter=KonectyFilter.create().add_condition("status", "equals", "active"),
        fields=["code", "name", "status"],
        limit=10,
    )
    records = await client.find("Contact", params)
    for r in records:
        print(r["code"], r.get("name"))

asyncio.run(main())
```

### Python — sync

```python
import os
from KonectySdkPython.lib.client import KonectyClient
from KonectySdkPython.lib.filters import KonectyFilter, KonectyFindParams

client = KonectyClient(
    base_url=os.environ["KONECTY_URL"],
    token=os.environ["KONECTY_TOKEN"],
)

params = KonectyFindParams(
    filter=KonectyFilter.create().add_condition("status", "equals", "active"),
    fields=["code", "name", "status"],
    limit=10,
)
records = client.find_sync("Contact", params)
for r in records:
    print(r["code"], r.get("name"))
```

### TypeScript / Node.js

```typescript
import { KonectyClient } from "@konecty/sdk/Client";

const client = new KonectyClient({
  endpoint: process.env.KONECTY_URL!,
  accessKey: process.env.KONECTY_TOKEN,
});

const result = await client.find("Contact", {
  filter: {
    match: "and",
    conditions: [{ term: "status", operator: "equals", value: "active" }],
  },
  fields: ["code", "name", "status"],
  limit: 10,
});

if (result.success) {
  for (const record of result.data ?? []) {
    console.log(record.code, record.name);
  }
}
```

### curl smoke test

Verify your credentials and URL without any SDK:

```bash
curl -s \
  -H "Authorization: $KONECTY_TOKEN" \
  "$KONECTY_URL/rest/data/Contact/find?limit=1" | jq .
```

A successful response looks like `{ "success": true, "total": N, "data": [...] }`.

## Where to Go Next

- `python-sdk.md` — full Python SDK method reference (find, create, update, delete, upload, stream, …)
- `typescript-sdk.md` — full TypeScript SDK method reference
- `rest-api.md` — raw REST endpoints for languages without an SDK
- `filters.md` — KonFilter structure, all operators, dynamic date variables, nested logic
- `recipes.md` — common patterns: pagination, upsert, bulk export, cross-module query
- `hooks.md` — server-side document hooks (before-save, after-save, computed fields)
