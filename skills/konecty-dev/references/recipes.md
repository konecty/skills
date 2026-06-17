# Konecty Developer Recipes

End-to-end patterns that compose the SDK primitives. Each recipe is a runnable
snippet verified against the real method signatures in the Python SDK
(`KonectyClient`) and TypeScript SDK (`KonectyClient`). For filter construction
see [`filters.md`](filters.md). For per-method signatures and auth setup see
[`python-sdk.md`](python-sdk.md) and [`typescript-sdk.md`](typescript-sdk.md).

---

## 1. Incremental sync — poll by `_updatedAt` watermark

Stream only records changed since the last run. Persist the cursor so the next
call starts exactly where you left off.

See [`filters.md`](filters.md) for the `greater_than` operator and
`KonectyFindParams`.

### Python

```python
import asyncio, json, os
from datetime import datetime, timezone
from pathlib import Path
from KonectySdkPython import KonectyClient
from KonectySdkPython.lib.filters import KonectyFilter, KonectyFindParams, SortOrder

CURSOR_FILE = Path(".sync_cursor_contact.json")
PAGE_SIZE   = 200

def load_cursor() -> datetime:
    if CURSOR_FILE.exists():
        ts = json.loads(CURSOR_FILE.read_text())["cursor"]
        return datetime.fromisoformat(ts)
    return datetime(2000, 1, 1, tzinfo=timezone.utc)

def save_cursor(dt: datetime) -> None:
    CURSOR_FILE.write_text(json.dumps({"cursor": dt.isoformat()}))

async def sync_contacts() -> None:
    client = KonectyClient(os.environ["KONECTY_URL"], os.environ["KONECTY_TOKEN"])
    watermark = load_cursor()
    start     = 0
    new_high  = watermark

    while True:
        f = (
            KonectyFilter.create()
            .add_condition("_updatedAt", "greater_than", watermark)
        )
        params = KonectyFindParams(
            filter=f,
            start=start,
            limit=PAGE_SIZE,
            sort=[SortOrder(property="_updatedAt", direction="ASC")],
        )
        batch = await client.find("Contact", params)
        if not batch:
            break
        for record in batch:
            process(record)                         # your logic here
            ts = record.get("_updatedAt")
            if ts and ts > new_high:
                new_high = ts
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    save_cursor(new_high)

def process(record): ...

asyncio.run(sync_contacts())
```

### TypeScript

```typescript
import { KonectyClient } from '@konecty/sdk/sdk/Client';
import fs from 'fs';

const CURSOR_FILE = '.sync_cursor_contact.json';
const PAGE_SIZE   = 200;

function loadCursor(): string {
  if (fs.existsSync(CURSOR_FILE)) return JSON.parse(fs.readFileSync(CURSOR_FILE, 'utf8')).cursor;
  return '2000-01-01T00:00:00.000Z';
}
function saveCursor(ts: string) { fs.writeFileSync(CURSOR_FILE, JSON.stringify({ cursor: ts })); }

const client = new KonectyClient({ endpoint: process.env.KONECTY_URL, accessKey: process.env.KONECTY_TOKEN });

async function syncContacts() {
  const watermark = loadCursor();
  let start = 0, newHigh = watermark;

  while (true) {
    const result = await client.find('Contact', {
      filter: { match: 'and', conditions: [{ term: '_updatedAt', operator: 'greater_than', value: watermark }] },
      start,
      limit: PAGE_SIZE,
      sort: [{ property: '_updatedAt', direction: 'ASC' }],
    });
    if (!result.success || !result.data?.length) break;
    for (const record of result.data) {
      process(record);
      if (record._updatedAt && record._updatedAt > newHigh) newHigh = record._updatedAt as string;
    }
    if (result.data.length < PAGE_SIZE) break;
    start += PAGE_SIZE;
  }
  saveCursor(newHigh);
}
```

---

## 2. Volume export via stream

Use `find_stream` / `findStream` to iterate millions of records without loading
them all into memory. The server sends NDJSON; the SDK exposes an async
generator. The generator must not be reused after exhaustion — call
`find_stream` again for a new pass.

### Python

```python
import asyncio, os
from KonectySdkPython import KonectyClient
from KonectySdkPython.lib.filters import KonectyFilter, KonectyFindParams

async def export_opportunities() -> None:
    client = KonectyClient(os.environ["KONECTY_URL"], os.environ["KONECTY_TOKEN"])
    f      = KonectyFilter.create().add_condition("status", "in", ["Open", "Negotiation"])
    params = KonectyFindParams(filter=f, fields=["_id", "name", "value", "status"])

    result = await client.find_stream("Opportunity", params, include_total=True)
    print(f"Streaming ~{result.total} records")

    async for record in result.stream:
        emit(record)          # write to file, DB, queue, etc.

def emit(record): ...
asyncio.run(export_opportunities())
```

### TypeScript

```typescript
import { KonectyClient } from '@konecty/sdk/sdk/Client';

const client = new KonectyClient({ endpoint: process.env.KONECTY_URL, accessKey: process.env.KONECTY_TOKEN });

async function exportOpportunities() {
  const { stream, total } = await client.findStream(
    'Opportunity',
    {
      filter: { match: 'and', conditions: [{ term: 'status', operator: 'in', value: ['Open', 'Negotiation'] }] },
      fields: ['_id', 'name', 'value', 'status'],
    },
    true, // includeTotal
  );
  console.log(`Streaming ~${total} records`);
  for await (const record of stream) {
    emit(record);
  }
}
```

---

## 3. File attach / replace flow

Upload a file to a record field, then read it back.

REST endpoint used internally:
`POST /rest/file/upload/ns/access/{module}/{recordCode}/{fieldName}`
(multipart/form-data, field key `file`).

### Python — `upload_file`

`upload_file` accepts raw `bytes` (requires `file_name`), a local path `str`,
or an `AsyncGenerator[bytes, None]`. It returns the `key` (file ID) assigned by
the server.

```python
import asyncio, os
from KonectySdkPython import KonectyClient

async def attach_pdf(record_code: str, pdf_path: str) -> None:
    client = KonectyClient(os.environ["KONECTY_URL"], os.environ["KONECTY_TOKEN"])

    # Upload from a local path (file_name inferred from path).
    file_key = await client.upload_file(
        module="Contact",
        record_code=record_code,
        field_name="attachments",
        file=pdf_path,          # str → treated as local path
    )
    print(f"Uploaded key: {file_key}")

    # Read it back as bytes (needs the file name, not the key).
    import os.path
    file_bytes = await client.download_file(
        module="Contact",
        record_code=record_code,
        field_name="attachments",
        file_name=os.path.basename(pdf_path),
    )
    print(f"Downloaded {len(file_bytes)} bytes")

asyncio.run(attach_pdf("C-001", "/tmp/contract.pdf"))
```

### TypeScript — `FilesManager`

`FilesManager` is instantiated from a typed Module class; it manages all files
on one field of one record. Use `upload(formData)` to attach and `deleteFile`
to replace.

```typescript
import { KonectyClient } from '@konecty/sdk/sdk/Client';
import { FilesManager } from '@konecty/sdk';   // re-exported from main package
import FormData from 'form-data';
import fs from 'fs';

const client = new KonectyClient({ endpoint: process.env.KONECTY_URL, accessKey: process.env.KONECTY_TOKEN });

async function attachPdf(recordId: string, recordCode: string, pdfPath: string) {
  const filesManager = new FilesManager(
    { endpoint: process.env.KONECTY_URL, accessKey: process.env.KONECTY_TOKEN },
    { metaObject: 'Contact', recordId, recordCode, fieldName: 'attachments', files: [] },
  );

  const fd = new FormData();
  fd.append('file', fs.createReadStream(pdfPath));

  const result = await filesManager.upload(fd);
  if (!result.success) throw new Error(JSON.stringify(result.errors));
  console.log('Uploaded:', result.data);
}
```

> **REST note:** when calling without a SDK wrapper, send
> `POST /rest/file/upload/ns/access/{Module}/{recordCode}/{fieldName}` with
> `Content-Type: multipart/form-data` and the file under the key `file`.
> Maximum size is 20 MB (nginx hard limit).

---

## 4. Cross-module query with aggregators

`execute_query_json` / `executeQueryJson` joins a primary document with related
ones in a single server round-trip. Each relation must declare at least one
aggregator. `push` collects matching child records into an array;
`count` counts them.

See [`filters.md`](filters.md) for the full filter syntax used in
`CrossModuleRelation.filter`.

### Python

```python
import asyncio, os
from KonectySdkPython import KonectyClient
from KonectySdkPython.lib.feature_types.cross_module_query import (
    CrossModuleQuery, CrossModuleRelation, Aggregator,
)

async def contacts_with_open_opps() -> None:
    client = KonectyClient(os.environ["KONECTY_URL"], os.environ["KONECTY_TOKEN"])

    query = CrossModuleQuery(
        document="Contact",
        filter={"match": "and", "conditions": [{"term": "active", "operator": "equals", "value": True}]},
        fields="_id,name,email",
        limit=500,
        relations=[
            CrossModuleRelation(
                document="Opportunity",
                lookup="contact",           # lookup field on Opportunity pointing to Contact
                filter={"status": {"$in": ["Open", "Negotiation"]}},
                fields="_id,name,value",
                aggregators={
                    "opportunities": Aggregator(aggregator="push"),  # embed matching records
                    "oppCount":      Aggregator(aggregator="count"),  # also count them
                },
            )
        ],
    )

    result = await client.execute_query_json(query, include_total=True)
    print(f"Total contacts: {result.total}")
    async for contact in result.stream:
        print(contact["name"], "→", contact.get("oppCount"), "open opps")

asyncio.run(contacts_with_open_opps())
```

### TypeScript

```typescript
import { KonectyClient } from '@konecty/sdk/sdk/Client';
import type { CrossModuleQuery } from '@konecty/sdk/sdk/types/crossModuleQuery';

const client = new KonectyClient({ endpoint: process.env.KONECTY_URL, accessKey: process.env.KONECTY_TOKEN });

async function contactsWithOpenOpps() {
  const query: CrossModuleQuery = {
    document: 'Contact',
    filter: { match: 'and', conditions: [{ term: 'active', operator: 'equals', value: true }] },
    fields: '_id,name,email',
    limit: 500,
    relations: [
      {
        document: 'Opportunity',
        lookup: 'contact',
        filter: { status: { $in: ['Open', 'Negotiation'] } },
        fields: '_id,name,value',
        aggregators: {
          opportunities: { aggregator: 'push' },
          oppCount:      { aggregator: 'count' },
        },
      },
    ],
  };

  const { stream, total } = await client.executeQueryJson(query);
  console.log('Total contacts:', total);
  for await (const contact of stream) {
    console.log(contact.name, '→', (contact as any).oppCount, 'open opps');
  }
}
```

---

## 5. Robust client — retry with exponential backoff

Konecty returns HTTP 429 when the OTP endpoint exceeds 5 requests/minute per
phone or email. Data endpoints may also throttle under high load. The SDK does
not retry automatically; implement a wrapper that handles 429, transient 5xx,
and the `{success: false, errors}` envelope.

### Python

```python
import asyncio, os
from KonectySdkPython import KonectyClient
from KonectySdkPython.lib.exceptions import KonectyAPIError
import aiohttp

MAX_ATTEMPTS = 4
BASE_DELAY   = 1.0   # seconds

async def with_retry(coro_fn, *args, **kwargs):
    """Call `coro_fn(*args, **kwargs)` with exponential backoff on 429 / 5xx."""
    delay = BASE_DELAY
    for attempt in range(MAX_ATTEMPTS):
        try:
            return await coro_fn(*args, **kwargs)
        except aiohttp.ClientResponseError as exc:
            if exc.status == 429 or exc.status >= 500:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(delay * (2 ** attempt))
            else:
                raise
        except KonectyAPIError as exc:
            # {success: false, errors: [...]} — do not retry; fix the payload
            raise

async def main():
    client = KonectyClient(os.environ["KONECTY_URL"], os.environ["KONECTY_TOKEN"])
    from KonectySdkPython.lib.filters import KonectyFilter, KonectyFindParams

    f      = KonectyFilter.create().add_condition("status", "equals", "New")
    params = KonectyFindParams(filter=f, limit=50)

    records = await with_retry(client.find, "Task", params)
    print(records)

asyncio.run(main())
```

### TypeScript

```typescript
import { KonectyClient, KonectyFindResult } from '@konecty/sdk/sdk/Client';

const MAX_ATTEMPTS = 4;
const BASE_DELAY_MS = 1000;

async function withRetry<T>(fn: () => Promise<KonectyFindResult<T>>): Promise<KonectyFindResult<T>> {
  let delay = BASE_DELAY_MS;
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    let result: KonectyFindResult<T>;
    try {
      result = await fn();
    } catch (err: any) {
      // Network / HTTP-level errors (fetch throws on 4xx/5xx in some environments)
      const status = err?.status ?? 0;
      if ((status === 429 || status >= 500) && attempt < MAX_ATTEMPTS - 1) {
        await new Promise(res => setTimeout(res, delay * 2 ** attempt));
        continue;
      }
      throw err;
    }
    if (!result.success) {
      // {success: false, errors} — do not retry; surface immediately
      throw new Error(JSON.stringify(result.errors));
    }
    return result;
  }
  throw new Error('Max retry attempts exceeded');
}

const client = new KonectyClient({ endpoint: process.env.KONECTY_URL, accessKey: process.env.KONECTY_TOKEN });

async function main() {
  const result = await withRetry(() =>
    client.find('Task', {
      filter: { match: 'and', conditions: [{ term: 'status', operator: 'equals', value: 'New' }] },
      limit: 50,
    }),
  );
  console.log(result.data);
}
```

---

## 6. KPI / graph / pivot quick calls

These aggregation helpers return a single computed value or visualisation from
the server. They all accept an optional `filter` / `params` to scope the data.

### Python

```python
import asyncio, os
from KonectySdkPython import KonectyClient
from KonectySdkPython.lib.feature_types.kpi import KpiConfig
from KonectySdkPython.lib.filters import KonectyFilter

async def aggregation_examples():
    client = KonectyClient(os.environ["KONECTY_URL"], os.environ["KONECTY_TOKEN"])

    # KPI: total value of open Opportunities
    f      = KonectyFilter.create().add_condition("status", "equals", "Open")
    kpi    = await client.get_kpi(
        "Opportunity",
        KpiConfig(operation="sum", field="value"),
        filter_params=f,
    )
    print("Total open value:", kpi)

    # Graph: monthly count (returns SVG string)
    svg = await client.get_graph(
        "Opportunity",
        {"type": "bar", "xAxis": {"field": "_createdAt", "aggregator": "M"}, "yAxis": {"field": "_id", "aggregation": "count"}},
        filter_params=f,
    )

    # Pivot: opportunity value by status × type
    pivot = await client.get_pivot(
        "Opportunity",
        {"rows": [{"field": "status"}], "columns": [{"field": "type"}], "values": [{"field": "value", "aggregator": "sum"}]},
    )
    print(pivot)

asyncio.run(aggregation_examples())
```

### TypeScript

```typescript
import { KonectyClient } from '@konecty/sdk/sdk/Client';

const client = new KonectyClient({ endpoint: process.env.KONECTY_URL, accessKey: process.env.KONECTY_TOKEN });

async function aggregationExamples() {
  const filter = { match: 'and', conditions: [{ term: 'status', operator: 'equals', value: 'Open' }] };

  // KPI
  const kpi = await client.getKpi('Opportunity', { operation: 'sum', field: 'value' }, { filter });
  console.log('KPI:', kpi);

  // Graph → SVG string
  const svg = await client.getGraph(
    'Opportunity',
    { type: 'bar', xAxis: { field: '_createdAt', aggregator: 'M' }, yAxis: { field: '_id', aggregation: 'count' } },
    { filter },
  );

  // Pivot
  const pivot = await client.getPivot(
    'Opportunity',
    { rows: [{ field: 'status' }], columns: [{ field: 'type' }], values: [{ field: 'value', aggregator: 'sum' }] },
    { filter },
  );
  console.log(pivot);
}
```
