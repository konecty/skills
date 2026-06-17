# Hook Scripts

Hooks are scripts attached to a Document metadata object that run automatically during
create and update operations. They let you compute derived fields, enforce business rules,
and trigger side effects — all without touching the Konecty core.

## Sandbox

Every hook runs inside a `node:vm` context (`createContext` / `runInContext`). The sandbox
is completely isolated: there is no `require`, no `import`, no filesystem access, and no
network except the `request` helper that Konecty injects explicitly in `scriptAfterSave`.
All standard JavaScript globals are available. Use `console.log` freely — output appears
in Konecty server logs.

---

## The Three Hook Types

| # | Metadata field | Fires | Transaction | Can mutate record |
|---|---------------|-------|-------------|-------------------|
| 1 | `scriptBeforeValidation` | Before field validation | Inside | Yes — return value merged |
| 2 | `validationScript` | After validation, before commit | Inside | No — veto only |
| 3 | `scriptAfterSave` | After successful commit | Outside | No — side effects only |

`validationData` is a companion metadata field for hook 2 (see below).

All three fields are optional strings on the Document schema
(`src/imports/model/Document/index.ts`). None is required; they are independent of each
other.

---

## 1. `scriptBeforeValidation`

### When it fires
First in the pipeline, on every create and update.

### Purpose
Mutate the incoming record before Konecty validates field types, required checks, and
lookup resolution. Use it to compute derived fields, normalise values, or stamp timestamps
based on state changes.

### Injected variables

| Variable | Type | Description |
|----------|------|-------------|
| `data` | object | The full record as it will be validated (includes incoming changes merged on top of the current DB state) |
| `emails` | array | Push email descriptors here to trigger outbound mail after save |
| `user` | object | The authenticated user performing the operation |
| `console` | object | Standard JS console (logs go to Konecty server logs) |
| `extraData` | object | `extraData.original` — the record as stored before this operation (empty object on create); `extraData.request` — the raw payload sent by the caller |

> Note: `extraData` is in scope as a sandbox variable even though the wrapper function
> signature is `(data, emails, user, console)`. Access it directly by name inside the
> script body.

### Return contract
Return a plain object. Konecty merges it into `data` before proceeding to validation.
Return `{}` (or nothing) to leave `data` unchanged.

```js
// scriptBeforeValidation — example body
var ret = {};

if (data.closeDate == null && data.stage === 'Closed Won') {
    ret.closeDate = new Date();
}

return ret;
```

### Email descriptor shape (optional)
```js
emails.push({
    from: 'noreply@example.com',
    to: 'owner@example.com',
    server: 'default',
    subject: 'Record updated',
    html: '<p>Your record was updated.</p>',
});
```

### Transaction boundary
Runs **inside** the MongoDB transaction. A thrown exception aborts the transaction and
returns an error to the caller.

---

## 2. `validationScript` (+ `validationData`)

### When it fires
Second in the pipeline, after field validation has completed and all lookups have been
resolved. Runs on every create and update.

### Purpose
Veto the operation when a cross-field or cross-document business rule is violated. This
is the right place for rules that cannot be expressed as field-level constraints.

### `validationData` — query prefetch
Before the script runs, Konecty reads the `validationData` metadata key. Each top-level
key in that object names a dataset, and the value is a Konecty query filter (with
`$this.<field>` dynamic references resolved against the current record). The query result
array is placed under `extraData.<key>`. Example metadata:

```json
"validationData": {
    "relatedTasks": {
        "document": "Task",
        "field": "_id, status",
        "filter": {
            "match": "and",
            "conditions": [
                { "term": "opportunityId._id", "operator": "equals", "value": "$this._id" }
            ]
        }
    }
}
```

Inside the script, `extraData.relatedTasks` is an array of Task records. If a key's query
fails, that key is silently omitted from `extraData`.

### Injected variables

| Variable | Type | Description |
|----------|------|-------------|
| `data` | object | The full, validated record (read-only — mutations here are discarded) |
| `user` | object | The authenticated user |
| `console` | object | Standard JS console |
| `extraData` | object | Datasets resolved from `validationData`; empty object when `validationData` is absent |

### Return contract
Return an object with a `success` boolean. Any other shape is treated as success.

```js
// success
return { success: true };

// veto — caller receives an error with this reason
return { success: false, reason: 'Rule violated: ...' };
```

If the script throws, Konecty treats it as a failed validation and returns an error.

```js
// validationScript — example body
var openTasks = ((extraData || {}).relatedTasks || [])
    .filter(function(t) { return t.status === 'Open'; });

if (data.stage === 'Closed Lost' && openTasks.length > 0) {
    return {
        success: false,
        reason: 'Cannot close opportunity with ' + openTasks.length + ' open task(s).',
    };
}

return { success: true };
```

### Transaction boundary
Runs **inside** the MongoDB transaction. A veto or thrown exception rolls back the
transaction.

---

## 3. `scriptAfterSave`

### When it fires
Last in the pipeline, after the transaction commits successfully. Runs on create and update.

### Purpose
Trigger side effects that must happen only after the record is durably committed: cascade
updates to related documents, outbound HTTP calls, notifications, synchronisation tasks.

### Why outside the transaction (ADR-0005)
Running `scriptAfterSave` inside the transaction extends its lifetime and raises the
probability of `NoSuchTransaction` aborts under contention. Because post-save customisation
is not part of the atomic consistency boundary, Konecty executes it after a confirmed
commit and before event dispatch. Consequence: if the hook fails, the record is already
saved — log the error explicitly, do not rely on automatic rollback.

### Injected variables

| Variable | Type | Description |
|----------|------|-------------|
| `data` | array | The saved records (one element per record processed; always an array) |
| `user` | object | The authenticated user |
| `console` | object | Standard JS console |
| `Models` | object | All Konecty MongoDB collections keyed by metadata name, e.g. `Models['Task']` |
| `extraData` | object | Currently an empty object in standard flows; reserved for future use |
| `moment` | function | `moment` library (date helpers) |
| `momentzone` | function | `moment-timezone` library |
| `request` | object | HTTP client — see below |

> `moment` and `momentzone` are injected into the sandbox context but are not named
> parameters of the wrapper function `(data, user, console, Models, extraData)`. Reference
> them directly by name inside the script body.

### `request` methods
```js
request.post({ url, body, json, headers });
```
Additional methods may be available via the underlying HTTP client; `post` is documented
and tested.

### Return contract
No meaningful return. The result value is ignored by the caller. Errors are logged;
they do not affect the HTTP response sent to the original caller.

### `async` / `await`
The wrapper is an `async` function. `await` is fully supported:

```js
// scriptAfterSave — example body
for (var i = 0; i < data.length; i++) {
    var record = data[i];

    await Models['Task'].updateMany(
        { 'opportunityId._id': record._id },
        { $set: { ownerName: record.ownerName } },
    );
}
```

### Transaction boundary
Runs **outside** the MongoDB transaction (ADR-0005).

---

## Lifecycle Diagram

```
CREATE / UPDATE request
        │
        ▼
┌────────────────────────┐
│  scriptBeforeValidation│  (inside transaction)
│  mutates data          │
└────────────┬───────────┘
             │
             ▼
┌────────────────────────┐
│  Field validation      │  (inside transaction)
│  type / required /     │
│  lookup resolution     │
└────────────┬───────────┘
             │
             ▼
┌────────────────────────┐
│  validationScript      │  (inside transaction)
│  veto or approve       │
│  (validationData       │
│   prefetched first)    │
└────────────┬───────────┘
             │
             ▼
┌────────────────────────┐
│  DB commit             │  ← transaction ends here
└────────────┬───────────┘
             │
             ▼
┌────────────────────────┐
│  scriptAfterSave       │  (outside transaction)
│  side effects          │
└────────────┬───────────┘
             │
             ▼
        Response to caller
```

---

## Edge Cases

### Delete operations
The delete flow runs **no hooks**. `scriptBeforeValidation`, `validationScript`, and
`scriptAfterSave` are never called on record deletion.

### `changeUser*` operations
`changeUser` bulk-reassigns the `_user` field on a set of records. By default, hooks are
skipped for these operations. Set `changeUserRunHooks: true` on the Document metadata to
enable `scriptBeforeValidation` and `scriptAfterSave` for `changeUser` flows. The
`validationScript` is not triggered by `changeUser` even when `changeUserRunHooks` is
`true`.

---

## Generic Examples

### (a) `scriptBeforeValidation` — compute a derived field on Opportunity

```js
// Computes a numeric priority score from urgency and value fields.
// Returns an object to be merged into the record before validation.
var ret = {};

var urgency  = data.urgencyLevel  || 0;   // integer 1-5
var dealSize = data.estimatedValue || 0;  // number

ret.priorityScore = urgency * dealSize;

if (ret.priorityScore > 50000) {
    ret.tier = 'Strategic';
} else if (ret.priorityScore > 10000) {
    ret.tier = 'Standard';
} else {
    ret.tier = 'Low';
}

return ret;
```

### (b) `validationScript` — veto a cross-field rule on Product

```js
// Blocks publishing a Product that has no associated price list entry.
// extraData.prices is populated via validationData querying PriceList.
var prices = ((extraData || {}).prices || []);

if (data.status === 'Published' && prices.length === 0) {
    return {
        success: false,
        reason: 'A product must have at least one price list entry before it can be published.',
    };
}

return { success: true };
```

Companion `validationData` metadata:

```json
"validationData": {
    "prices": {
        "document": "PriceList",
        "field": "_id, amount",
        "filter": {
            "match": "and",
            "conditions": [
                { "term": "productId._id", "operator": "equals", "value": "$this._id" }
            ]
        }
    }
}
```

### (c) `scriptAfterSave` — cross-document update and outbound HTTP on Contact

```js
// When a Contact is marked inactive, close all their open Tasks
// and notify an external service.
for (var i = 0; i < data.length; i++) {
    var contact = data[i];

    if (contact.active === false) {
        await Models['Task'].updateMany(
            { 'contactId._id': contact._id, status: 'Open' },
            { $set: { status: 'Cancelled', cancelReason: 'Contact deactivated' } },
        );

        await request.post({
            url: 'https://api.example.com/webhooks/contact-deactivated',
            json: true,
            headers: { 'Content-Type': 'application/json' },
            body: { contactId: contact._id, timestamp: new Date().toISOString() },
        });
    }
}
```

---

## Managing and Versioning Hooks

Writing logic here is only part of the job. To validate the script syntax against the
server contract, version it in your metadata repository, and apply it to a running
instance, use the **`konecty-meta`** skill — specifically the `hook` subcommand.
