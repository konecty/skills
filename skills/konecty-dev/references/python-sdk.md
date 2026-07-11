# Konecty Python SDK — Developer Reference

Tested against **`konecty_sdk_python` 2.0.3**.
Full endpoint mapping and response contracts: see [`api.md`](../../../konecty-sdk-python/docs/api.md) in the upstream repo.

## Installation

```bash
uv pip install konecty-sdk-python
```

---

## Client initialisation

`KonectyClient` is the single entry point. It is **async-first** (`aiohttp` under the hood); a synchronous convenience layer exists for `find`, `find_one`, and settings helpers.

```python
import os
from KonectySdkPython import KonectyClient

# Token is sent as-is in the Authorization header (no "Bearer" prefix).
# See auth-for-code.md for how to obtain and store the token.
client = KonectyClient(
    base_url=os.environ["KONECTY_URL"],   # e.g. "https://app.myorg.konecty.com"
    token=os.environ["KONECTY_TOKEN"],
)
```

For synchronous scripts call `find_sync` / `find_one_sync` directly — no event loop required for those two methods.

---

## Core operations

### find / find_sync

```python
import asyncio
from KonectySdkPython import KonectyClient, KonectyFilter, KonectyFindParams, SortOrder

client = KonectyClient(base_url=..., token=...)

# Build a filter — see filters.md for the full operator list.
f = (
    KonectyFilter.create("and")
    .add_condition("status", "equals", "Active")
    .add_condition("campaign", "exists", True)
)

params = KonectyFindParams(
    filter=f,
    fields=["name", "email", "status"],
    sort=[SortOrder(property="name", direction="ASC")],
    start=0,
    limit=50,
)

# Async
records = await client.find("Contact", params)

# Sync (no event loop needed)
records = client.find_sync("Contact", params)
```

**Returns** `List[KonectyDict]` (`Dict[str, Any]`). Raises `KonectyAPIError` on API-level failures.

---

### find_one / find_one_sync

```python
# Async
contact = await client.find_one(
    "Contact",
    KonectyFilter.create().add_condition("email.address", "equals", "alice@example.com"),
)

# Sync
contact = client.find_one_sync(
    "Contact",
    KonectyFilter.create().add_condition("email.address", "equals", "alice@example.com"),
)
```

**Returns** `Optional[KonectyDict]` (the first match, or `None`).

---

### find_by_id

```python
contact = await client.find_by_id("Contact", "64a1f3c2e8b0a400123abcde")
```

**Signature:** `find_by_id(module: str, id: str) -> Optional[KonectyDict]`

---

### create

```python
new_contact = await client.create("Contact", {
    "name": {"first": "Alice", "last": "Smith", "full": "Alice Smith"},
    "email": [{"address": "alice@example.com"}],
    "status": "Active",
})
# System fields (_updatedAt, _createdAt, _updatedBy, _createdBy) are stripped automatically.
```

**Signature:** `create(module: str, data: KonectyDict) -> Optional[KonectyDict]`
Returns the created record dict, or `None` if the server returns an empty data array.

---

### update_one

Konecty uses optimistic concurrency: every write must supply the `_updatedAt` timestamp from the record you last read.

```python
from datetime import datetime, timezone

# 1. Fetch the record first to get the current _updatedAt.
contact = await client.find_by_id("Contact", "64a1f3c2e8b0a400123abcde")
updated_at = datetime.fromisoformat(
    contact["_updatedAt"]["$date"].replace("Z", "+00:00")
)

# 2. Update, passing the datetime object directly.
result = await client.update_one(
    "Contact",
    id="64a1f3c2e8b0a400123abcde",
    updatedAt=updated_at,         # datetime (naive or aware)
    data={"status": "Inactive"},
)
```

**Signature:** `update_one(module: str, id: str, updatedAt: datetime, data: KonectyDict) -> Optional[KonectyDict]`

---

### update (batch)

```python
from KonectySdkPython import KonectyUpdateId, KonectyDateTime

ids = KonectyUpdateId.from_list([
    {"_id": "64a1f3c2e8b0a400123abcde", "_updatedAt": contact_a["_updatedAt"]},
    {"_id": "64a1f3c2e8b0a400123abcdf", "_updatedAt": contact_b["_updatedAt"]},
])
results = await client.update("Contact", ids, {"status": "Inactive"})
```

**Signature:** `update(module: str, ids: list[KonectyUpdateId], data: KonectyDict) -> list[KonectyDict]`

---

### delete_one

```python
await client.delete_one(
    "Contact",
    id="64a1f3c2e8b0a400123abcde",
    updatedAt=updated_at,    # same optimistic-concurrency datetime as update_one
)
```

**Signature:** `delete_one(module: str, id: str, updatedAt: datetime) -> Optional[KonectyDict]`

---

### count_documents

```python
total = await client.count_documents(
    "Opportunity",
    KonectyFilter.create().add_condition("status", "equals", "Open"),
)
print(total)  # int
```

**Signature:** `count_documents(module: str, filter_params: KonectyFilter) -> int`

---

### execute_query_json / execute_query_sql

Both return a `QueryResult` object with an async generator `.stream`, an optional `.total`, and optional `.meta`.

```python
# --- JSON query (cross-module, full control) ---
from KonectySdkPython.lib.feature_types.query_json import QueryJson

query = QueryJson(document="Contact", limit=100)
result = await client.execute_query_json(query, include_total=True)
async for record in result.stream:
    print(record)
print("Total:", result.total)

# --- SQL query (ad-hoc SELECT, same engine) ---
result = await client.execute_query_sql(
    "SELECT _id, name, status FROM Contact WHERE status = 'Active' LIMIT 50",
    include_total=True,
)
async for record in result.stream:
    print(record)
```

**Signatures:**
```python
execute_query_json(body: Any, *, include_total: bool = True, include_meta: bool = False) -> QueryResult
execute_query_sql(sql: str, *, include_total: bool = True, include_meta: bool = False) -> QueryResult
```

SQL dialect: MySQL-style SELECT only; max 10 000 characters. The stream is single-use — consume it once.

---

### upload_file / download_file / download_image

```python
# Upload — accepts bytes, a local path string, or an async generator of bytes.
file_key = await client.upload_file(
    module="Contact",
    record_code="ABC123",       # record's code field, not _id
    field_name="attachments",
    file=b"<raw bytes>",
    file_name="contract.pdf",
    file_type="application/pdf",  # optional MIME hint
)

# Download a file attachment
data: bytes = await client.download_file(
    module="Contact",
    record_code="ABC123",
    field_name="attachments",
    file_name="contract.pdf",
)

# Download an image (style: "full" | "thumb" | "wm" | None)
thumb: bytes = await client.download_image(
    module="Product",
    record_id="64a1f3c2e8b0a400123abcde",
    field_name="photo",
    file_name="product.jpg",
    style="thumb",
)
```

Max upload size: 20 MB (server-side limit). One file per call.

---

### find_stream (NDJSON streaming)

Use when fetching large datasets to avoid loading everything into memory.

```python
from KonectySdkPython import KonectyFindParams, KonectyFilter

params = KonectyFindParams(
    filter=KonectyFilter.create().add_condition("status", "equals", "Active"),
    limit=10000,
)
result = await client.find_stream("Contact", params, include_total=True)
async for record in result.stream:
    process(record)
print("Total:", result.total)
```

**Signature:** `find_stream(module: str, options: KonectyFindParams, *, include_total: bool = False) -> FindStreamResult`

---

## Gaps — calling REST directly

The SDK does **not** cover:

| Feature | REST endpoint |
|---|---|
| Record history | `GET /rest/data/{module}/{id}/history` |
| Lookup / relation data | `GET /rest/data/{module}/lookup` |
| Menu / form / list-view metadata | `GET /rest/menu/documents/{id}` (partially via `get_document`) |
| Admin meta (MetaObjects) | `GET/POST /api/admin/meta/*` |

For these, reuse the same credentials with a plain HTTP client. The token is sent as a bare `Authorization` header (no `Bearer` prefix), matching exactly what `KonectyClient` does.

**Example — fetch record history via `urllib` (stdlib):**

```python
import json
import os
import urllib.request

base_url = os.environ["KONECTY_URL"]
token    = os.environ["KONECTY_TOKEN"]
module   = "Contact"
record_id = "64a1f3c2e8b0a400123abcde"

req = urllib.request.Request(
    f"{base_url}/rest/data/{module}/{record_id}/history",
    headers={"Authorization": token},
)
with urllib.request.urlopen(req) as resp:
    history = json.loads(resp.read())

for entry in history.get("data", []):
    print(entry["_updatedAt"], entry.get("_updatedBy", {}).get("name"))
```

If `httpx` or `requests` is available in your environment, pass the same `Authorization` header and you can reuse the `client.base_url` and `client.headers` attributes directly.

For admin-meta endpoints (schema CRUD, sync, access profiles) see `rest-api.md` and the `konecty-meta` skill.
