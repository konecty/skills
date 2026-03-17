# Hook Contracts Reference

## Overview

Konecty supports 4 hook types. All are fields on the document meta (`type: "document"`) in `MetaObjects`. In the filesystem repo, they live under `{Document}/hook/`.

| Hook                      | File type | Moment                         | Sandbox variables                             | Expected return                      |
| ------------------------- | --------- | ------------------------------ | --------------------------------------------- | ------------------------------------ |
| `scriptBeforeValidation`  | `.js`     | Before validation, before save | `data, emails, user, console, extraData`      | Object merged into `data`            |
| `validationData`          | `.json`   | Before validationScript runs   | N/A (JSON config, not executed as code)        | N/A (feeds extraData)               |
| `validationScript`        | `.js`     | After validationData resolves  | `data, user, console, extraData`              | `{ success: boolean, reason?: string }` |
| `scriptAfterSave`         | `.js`     | After record is saved          | `data, user, console, Models, extraData`      | No expected return (fire and forget) |

## Execution order

```
1. scriptBeforeValidation  →  returns computed fields merged into data
2. validationData          →  pre-fetches related data into extraData
3. validationScript        →  validates data, can reject with reason
4. [record is saved to MongoDB]
5. scriptAfterSave         →  post-save side effects
```

---

## scriptBeforeValidation

**File:** `{Document}/hook/scriptBeforeValidation.js`

**Sandbox:**

| Variable    | Type     | Description                                                              |
| ----------- | -------- | ------------------------------------------------------------------------ |
| `data`      | object   | The full record being created/updated (merged with existing on update)    |
| `emails`    | array    | Push email objects here to queue emails (see emails.push below)           |
| `user`      | object   | Current user: `{ _id, name, group, role, director, active, ... }`        |
| `console`   | object   | Standard console for logging                                              |
| `extraData` | object   | `{ request: changedFields, original: preUpdateRecord }` on update; `{ request: allFields }` on create |

**Return:** An object whose keys will be merged into `data`. This is how computed fields work.

```javascript
var ret = {};
if (data.plan && (!extraData.original || data.plan._id !== extraData.original.plan._id)) {
  ret.planBaseDate = new Date();
}
return ret;
```

**extraData differences:**
- **Create:** `extraData.original` is `undefined`; `extraData.request` contains all submitted fields
- **Update:** `extraData.original` is the full record before update; `extraData.request` contains only the changed fields

### emails.push mechanism

Emails are NOT sent directly. Objects pushed to `emails[]` are processed after the script runs:

1. If `email.relations` is defined, `populateLookupsData(meta._id, data, email.relations)` fetches related records
2. If `email.toPath` is defined, `get(populatedData, email.toPath)` resolves the recipient address
3. Each email becomes a `Message` document with `{ type: 'Email', status: 'Send' }` — a worker processes the queue

**Template variant (most common):**

```javascript
emails.push({
  toPath: 'contact.email.0.address',     // dot-notation resolved against populated data
  from: 'Egalitê <egalite@egalite.com.br>',
  server: 'smtp_egalite',                // key in Namespace.emailServers
  template: 'forwardCandidate',          // email template name
  relations: { candidate: 1, job: 1, contact: 1 }  // lookups to populate before resolving toPath
});
```

**Raw HTML variant (less common):**

```javascript
emails.push({
  to: 'dest@example.com',
  from: 'sender@example.com',
  server: 'smtp_x',
  subject: 'Subject line',
  html: '<p>Email body</p>'
});
```

---

## validationData

**File:** `{Document}/hook/validationData.json`

**Purpose:** Pre-fetches related data that `validationScript` needs for validation. Results are passed as `extraData` to `validationScript`.

**Structure:**

```json
{
  "aliasName": {
    "document": "DocumentName",
    "fields": "field1, field2, field3",
    "filter": {
      "match": "and",
      "conditions": [
        { "term": "_id", "operator": "equals", "value": "$this._id" }
      ]
    },
    "limit": 10000
  }
}
```

| Property   | Type   | Description                                                        |
| ---------- | ------ | ------------------------------------------------------------------ |
| `document` | string | Document to query                                                  |
| `fields`   | string | Comma-separated field names to return                              |
| `filter`   | KonFilter | Filter with `$this.<field>` placeholders resolved from current record |
| `limit`    | number | Max records to fetch (optional)                                    |

**`$this.<field>` resolution:** The backend calls `parseDynamicData(filter, '$this', fullData)` which replaces `$this._id`, `$this.address.city`, etc. with actual values from the record being saved.

**Result:** Each alias becomes a key in `extraData` passed to `validationScript`. The value is an array of matching records.

**Real example (Product):**

```json
{
  "original": {
    "fields": "_id, address, status, sale, tower",
    "document": "Product",
    "filter": {
      "match": "and",
      "conditions": [{ "term": "_id", "operator": "equals", "value": "$this._id" }]
    }
  },
  "existingActiveProducts": {
    "fields": "code, status, address, tower",
    "document": "Product",
    "filter": {
      "match": "and",
      "conditions": [
        { "term": "address.place", "operator": "equals", "value": "$this.address.place" },
        { "term": "address.number", "operator": "equals", "value": "$this.address.number" },
        { "term": "address.city", "operator": "equals", "value": "$this.address.city" },
        { "term": "address.state", "operator": "equals", "value": "$this.address.state" }
      ]
    },
    "limit": 10000
  }
}
```

In this example, `validationScript` receives `extraData.original` (array with the current record's pre-update state) and `extraData.existingActiveProducts` (array of products at the same address).

---

## validationScript

**File:** `{Document}/hook/validationScript.js`

**Sandbox:**

| Variable    | Type   | Description                                                    |
| ----------- | ------ | -------------------------------------------------------------- |
| `data`      | object | Full record (with computed fields from scriptBeforeValidation) |
| `user`      | object | Current user                                                   |
| `console`   | object | Standard console                                               |
| `extraData` | object | Results from validationData queries (empty `{}` if no validationData) |

**Return:** Must return `{ success: boolean, reason?: string }`. If `success` is `false`, the save is rejected and `reason` is shown to the user.

```javascript
if (data.plan != null && data.mainContact != null) {
  return {
    success: false,
    reason: 'Um contato não pode ter um Plano e um Contato Principal ao mesmo tempo.'
  };
}
return { success: true };
```

---

## scriptAfterSave

**File:** `{Document}/hook/scriptAfterSave.js`

**Sandbox:**

| Variable    | Type   | Description                                                    |
| ----------- | ------ | -------------------------------------------------------------- |
| `data`      | object | The saved record(s) — can be array for batch operations        |
| `user`      | object | Current user                                                   |
| `console`   | object | Standard console                                               |
| `Models`    | object | `MetaObject.Collections` — direct MongoDB collection handles   |
| `extraData` | object | `{ original: preUpdateRecord(s) }`                             |
| `moment`    | object | moment.js library                                              |
| `momentzone`| object | moment-timezone library                                        |
| `request`   | object | HTTP request library                                           |

**Return:** No expected return. The function is async-capable (`await` is supported).

**IMPORTANT:** `scriptAfterSave` does NOT have access to `emails[]`. Use `document.events` for queue/webhook integrations, not this hook.

```javascript
var original = null;
if (data && data.length > 0) {
  for (var index in data) {
    if (extraData && extraData['original'] && extraData['original'][index]) {
      original = extraData['original'][index];
    }
    var record = data[index];
    if (record.status === 'Em Prospecção' && (!original || original.status !== 'Em Prospecção')) {
      konectyCall('data:create', {
        document: 'Opportunity',
        data: { status: 'Nova', contact: { _id: data[0]._id } }
      });
    }
    if (record.status === 'Ativo' && record.createPassword === true) {
      request.post('https://api.example.com/activate-user?c=' + record.code);
    }
  }
}
```

---

## Common errors

| Error                                         | Cause                                            | Fix                                              |
| --------------------------------------------- | ------------------------------------------------ | ------------------------------------------------ |
| `ReferenceError: require is not defined`       | Hooks run in a VM sandbox — no `require`         | Use only sandbox variables                       |
| Return `undefined` from validationScript       | Missing `return { success: true }`               | Always return the success object                 |
| `emails.push` in scriptAfterSave              | `emails` is not available in afterSave sandbox   | Move email logic to scriptBeforeValidation        |
| `$this.field` not resolved in validationData  | Field does not exist on the record               | Verify field name matches document schema         |
| Async code in scriptBeforeValidation          | Only scriptAfterSave supports `await`            | Use sync patterns in beforeValidation             |
