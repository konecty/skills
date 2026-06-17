# TypeScript SDK Reference

Tested against `@konecty/sdk` 1.0.0.

Full API surface (all method → REST endpoint mappings, every type exported):
`/Users/silveira/dev/Konecty/konecty-sdk/docs/api.md`

---

## Client initialisation

```ts
import { KonectyClient } from '@konecty/sdk/Client';

const client = new KonectyClient({
  endpoint:  process.env.KONECTY_URL,   // required — no default
  accessKey: process.env.KONECTY_TOKEN, // pre-obtained token
});
```

`KonectyClientOptions` also accepts `credentialsFile` (Node path to a credentials
file) and `fileManager.providerUrl` / `fileManager.origin` (override the base URL
used by `FilesManager` for uploads).

The client is synchronous to construct. All operations are `async`. For how to
obtain a token via the OTP flow see `auth-for-code.md`.

---

## Core CRUD operations

### find

```ts
import type { KonectyFindParams, KonectyFindResult } from '@konecty/sdk/Client';

const result: KonectyFindResult<Contact> = await client.find<Contact>(
  'Contact',
  {
    filter: { match: 'and', conditions: [{ term: 'status', operator: 'equals', value: 'active' }] },
    sort:   [{ name: 'asc' }],
    limit:  50,
    start:  0,
    fields: ['_id', 'name', 'email', 'status'],
  } satisfies KonectyFindParams,
);

if (result.success) {
  console.log(result.total, result.data);
}
```

`KonectyFindResult<T>` shape: `{ success, total?, data?: T[], errors? }`.

Filter syntax is not restated here — see `filters.md`.

### create

```ts
const result = await client.create('Opportunity', {
  name:   'New deal',
  status: 'open',
  value:  1000,
});
// result: KonectyFindResult<Opportunity & KonectyDocument>
```

### update

The `ids` array must include both `_id` and `_updatedAt` for each record — the
server uses `_updatedAt` for optimistic-concurrency checking.

```ts
const result = await client.update(
  'Opportunity',
  { status: 'won' },                                // fields to change
  [{ _id: 'abc123', _updatedAt: existingUpdatedAt }],
);
```

### delete

```ts
const result = await client.delete(
  'Task',
  [{ _id: 'task-id-1', _updatedAt: existingUpdatedAt }],
);
```

---

## Cross-module queries

### executeQueryJson

Runs a structured cross-module query. Returns an async generator — iterate with
`for await`.

```ts
import { createCrossModuleQuery } from '@konecty/sdk/CrossModuleQueryBuilder';

const query = createCrossModuleQuery('Contact')
  .filter({ match: 'and', conditions: [{ term: 'status', operator: 'equals', value: 'active' }] })
  .fields('name.full,code')
  .relation('Opportunity', 'contact', b => b.aggregator('count', { aggregator: 'count' }))
  .includeTotal(true)
  .build();

const { stream, total } = await client.executeQueryJson(query);
for await (const record of stream) {
  console.log(record);
}
```

`total` is only populated when `includeTotal(true)` is set.

### executeQuerySql

```ts
const { stream, total } = await client.executeQuerySql(
  'SELECT _id, name FROM Contact WHERE status = "active" LIMIT 100',
  { includeTotal: true, includeMeta: false },
);
for await (const row of stream) {
  console.log(row);
}
```

Both methods return `Promise<{ stream: AsyncGenerator<T>; total?: number }>`.
Do not reuse the generator after consumption; call the method again for a second pass.

---

## File downloads

```ts
// Generic file attachment (returns ArrayBuffer)
const buf: ArrayBuffer = await client.downloadFile(
  'Product',   // document name
  'PROD-001',  // record code
  'documents', // field name
  'spec.pdf',  // file name as stored in Konecty
);

// Image field — optional style: 'full' | 'thumb' | 'wm'
const img: ArrayBuffer = await client.downloadImage(
  'Product',
  'record-id-xyz',
  'pictures',
  'hero.jpg',
  'thumb',
);
```

Both reject the Promise on HTTP 4xx/5xx. Wrap in `try/catch`.

---

## TS-only helpers

```ts
// Audit trail for a record
const history = await client.getHistory('Contact', recordId);
// → KonectyFindResult<History>

// Navigation menu (default: 'main'; also 'user' | 'admin')
const menu = await client.getMenu('main');
// → KonectyFindResult<Menu>

// Column/filter definitions for a named list view
const listView = await client.getListView('Opportunity', 'Default');
// → KonectyGetMetaResult<List>

// Typeahead / relation field suggestions
const suggestions = await client.lookup('Contact', 'account', 'Acme', {
  filter: {},
});
// → KonectyFindResult<T>
```

---

## Analytics — KPI, Graph, Pivot

```ts
// Single aggregation over a filtered set
const kpi = await client.getKpi(
  'Opportunity',
  { operation: 'sum', field: 'value' },
  { filter: { match: 'and', conditions: [{ term: 'status', operator: 'equals', value: 'won' }] } },
);
// → { success: true, value: number, count: number }

// Chart data — returns a string (rendered chart or data URL)
const chart: string = await client.getGraph('Product', graphConfig);

// Pivot table
const pivot = await client.getPivot('Opportunity', pivotConfig);
```

`graphConfig` and `pivotConfig` types are exported from
`@konecty/sdk/types/graph` and `@konecty/sdk/types/pivot` respectively.

---

## File uploads — gap: use FilesManager

`KonectyClient` has **no** upload method. Uploads go through the separate
`FilesManager` class, obtained via a module instance:

```ts
import { KonectyModule, ModuleConfig } from '@konecty/sdk/Module';

// Define a module that mirrors a Konecty document
class ProductModule extends KonectyModule {
  static config: ModuleConfig = { name: 'Product' };
}

const ProductMod = new ProductModule({ endpoint, accessKey });
const product = await ProductMod.findOne({ filter: { ... } });

// One FilesManager per field per record
const fm = ProductMod.filesManager({
  recordId:  product._id,
  fieldName: 'pictures',
  files:     product.pictures,  // current file array stored in Konecty
});

// Upload (browser FormData or Node form-data)
const fd = new FormData();
fd.append('file', fileBlob);
const uploadResult = await fm.upload(fd);

// Delete by stored file name
await fm.deleteFile('hero.jpg');

// Reorder — in-memory only; persist with a client.update() afterwards
await fm.reorder(['new-first.jpg', 'second.jpg', 'hero.jpg']);
const updatedFiles = fm.toJson();
await client.update('Product', { pictures: updatedFiles }, [{ _id: product._id, _updatedAt: product._updatedAt }]);
```

`FilesManager` POSTs to `POST /rest/file/upload/ns/access/:document/:recordId/:fieldName`.
For raw REST upload details see `rest-api.md`.

Admin metadata endpoints (`/api/admin/meta/*`) are not covered by the TS SDK —
use the `konecty-meta` skill for those operations.
