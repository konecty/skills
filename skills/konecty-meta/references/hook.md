# Konecty Meta Hook

Generate and manage hook code for Konecty documents.

## Prerequisites

Requires **admin** credentials from **konecty-session**. User must have `admin: true`.

## Hook Types

| Hook | File type | When it runs | Available variables | Returns |
|------|-----------|-------------|--------------------|---------| 
| `scriptBeforeValidation` | JS | Before validation | `data, emails, user, console, extraData` | Object merged into `data` |
| `validationData` | JSON | Before validationScript | N/A (config) | Feeds `extraData` |
| `validationScript` | JS | After validationData | `data, user, console, extraData` | `{ success, reason? }` |
| `scriptAfterSave` | JS | After record saved | `data, user, console, Models, extraData` | None |

## Workflow

### 1. List hooks for a document

```bash
python3 scripts/meta_hook.py list Contact
```

### 2. Show a specific hook

```bash
python3 scripts/meta_hook.py show Contact scriptBeforeValidation
python3 scripts/meta_hook.py show Product validationData
```

### 3. Update a hook (from file)

```bash
python3 scripts/meta_hook.py upsert Contact scriptBeforeValidation --file hook.js
python3 scripts/meta_hook.py upsert Product validationData --file validationData.json
```

### 4. Update a hook (inline code)

```bash
python3 scripts/meta_hook.py upsert Contact validationScript --code 'return { success: true };'
```

### 5. Delete a hook

```bash
python3 scripts/meta_hook.py delete Contact scriptAfterSave
```

### 6. Scaffold a hook template

```bash
python3 scripts/meta_hook.py scaffold scriptBeforeValidation
python3 scripts/meta_hook.py scaffold validationData
python3 scripts/meta_hook.py scaffold validationScript
python3 scripts/meta_hook.py scaffold scriptAfterSave
```

### 7. Validate a hook (backend dry-run)

```bash
python3 scripts/meta_hook.py validate scriptBeforeValidation --file hook.js
python3 scripts/meta_hook.py validate scriptBeforeValidation --file hook.js --document Contact
```

This command calls `POST /api/admin/meta/hook/validate` and uses the same backend validations used by apply/doctor.

## Code generation guidelines

When generating hook code, follow these rules:

1. **scriptBeforeValidation**: Always `var ret = {};` at top, always `return ret;` at bottom
2. **validationScript**: Always return `{ success: true }` on the happy path
3. **scriptAfterSave**: Data may be an array for batch operations
4. **validationData**: Pure JSON, use `$this.<field>` for dynamic filters
5. **emails.push()** only works in `scriptBeforeValidation`
6. No `require()` or `import` — hooks run in a VM sandbox
7. No inline comments in JS hook source (`//` or `/* */`)
8. `scriptBeforeValidation` and `validationScript` must include explicit `return`
9. Only `scriptAfterSave` supports `await`
10. Use try/catch for complex logic to prevent hook failures from blocking saves
11. Do NOT post to RabbitMQ queues from hooks — use `document.events` instead

## References

- Hook Contracts section below — detailed contracts for all 4 hooks
- Hook Patterns section below — common implementation patterns with real examples

## Script reference

See [scripts/meta_hook.py](scripts/meta_hook.py). Stdlib only.

---

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

---

# Hook Patterns Reference

Common patterns found in real Konecty hook implementations.

## 1. Computed fields (scriptBeforeValidation)

The most common pattern: compute derived values and return them to be merged into `data`.

```javascript
var ret = {};
// Calculate area price from sale value and area
if (data.sale && data.sale.value && data.areaPrivate && data.areaPrivate > 0) {
  ret.areaPrice = {
    currency: 'BRL',
    value: data.sale.value / data.areaPrivate
  };
}
return ret;
```

## 2. Guard create vs update

Detect whether this is a create or update by checking `extraData.original`.

```javascript
var ret = {};
var original = extraData.original;  // undefined on create, object on update

if (original == null) {
  // CREATE: set initial values
  ret.createdByUser = { _id: user._id };
  ret.initialStatus = 'Nova';
} else {
  // UPDATE: react to field changes
  if (data.status !== original.status) {
    ret.statusChangedAt = new Date();
  }
}
return ret;
```

## 3. Detect specific field changes

Use `extraData.request` (contains only changed fields) or compare `data` vs `extraData.original`.

```javascript
var ret = {};
var req = extraData.request;

// Check if a specific field was changed in this request
if (req && req.plan) {
  if (!extraData.original.plan || data.plan._id !== extraData.original.plan._id) {
    ret.planBaseDate = new Date();
  }
}
return ret;
```

## 4. Email queuing with template (scriptBeforeValidation)

Queue an email using a template, with lookup population for resolving the recipient.

```javascript
if (data.status === 'Encaminhado' && (!extraData.original || extraData.original.status !== 'Encaminhado')) {
  emails.push({
    toPath: 'contact.email.0.address',
    from: 'Egalitê <egalite@egalite.com.br>',
    server: 'smtp_egalite',
    template: 'forwardCandidate',
    relations: { candidate: 1, job: 1, contact: 1 }
  });
}
```

How it works:
1. `relations: { candidate: 1, job: 1, contact: 1 }` tells the system to populate these lookup fields from the record
2. After population, `toPath: 'contact.email.0.address'` resolves to the actual email address
3. `server: 'smtp_egalite'` references a key in `Namespace.emailServers`
4. `template: 'forwardCandidate'` references an email template by name

## 5. Conditional email with notes change

```javascript
if (data.professionalPicturesNotes && (!original || original.professionalPicturesNotes !== data.professionalPicturesNotes)) {
  emails.push({
    toPath: '_user.0.emails.0.address',
    from: 'Atendimento <atendimento@acme.com.br>',
    server: 'smtp_acme',
    template: 'professional-pictures-notes-changed',
    relations: { _user: 1 }
  });
}
```

## 6. Status-driven deadline calculation (scriptBeforeValidation)

Compute a deadline based on status transitions.

```javascript
var ret = {};
if (extraData.request && extraData.request.status) {
  var addDays = -1;
  var referenceDate = new Date();
  switch (extraData.request.status) {
    case 'Aprovado para a vaga': addDays = 1; break;
    case 'Indicado': addDays = 2; break;
    case 'Aguardando': addDays = 3; break;
    case 'Em contratação': addDays = 5; break;
    case 'Contratado': addDays = 90; break;
  }
  if (addDays >= 0) {
    referenceDate.setDate(referenceDate.getDate() + addDays);
    ret.deadline = referenceDate;
  } else {
    ret.deadline = null;
  }
}
return ret;
```

## 7. Validation with pre-fetched data (validationData + validationScript)

**validationData.json** — fetch the original record and related records:

```json
{
  "original": {
    "document": "Product",
    "fields": "_id, status, address",
    "filter": {
      "match": "and",
      "conditions": [{ "term": "_id", "operator": "equals", "value": "$this._id" }]
    }
  },
  "existingProducts": {
    "document": "Product",
    "fields": "code, status, address",
    "filter": {
      "match": "and",
      "conditions": [
        { "term": "address.place", "operator": "equals", "value": "$this.address.place" },
        { "term": "address.city", "operator": "equals", "value": "$this.address.city" }
      ]
    },
    "limit": 100
  }
}
```

**validationScript.js** — use the pre-fetched data:

```javascript
// extraData.original = array of records matching the filter
// extraData.existingProducts = array of products at the same address
if (extraData.existingProducts && extraData.existingProducts.length > 5) {
  return { success: false, reason: 'Too many products at this address' };
}
return { success: true };
```

## 8. Simple business rule validation (validationScript)

```javascript
if (data.plan != null && data.mainContact != null) {
  return {
    success: false,
    reason: 'Um contato não pode ter um Plano e um Contato Principal ao mesmo tempo.'
  };
}
return { success: true };
```

## 9. Direct MongoDB access (scriptAfterSave)

`Models` provides direct access to all MongoDB collections via `MetaObject.Collections`.

```javascript
// Models['data.Contact'] gives the Contact data collection
// Models['Message'] gives the Message collection
if (data && data.length > 0) {
  var record = data[0];
  if (record.status === 'Em Prospecção') {
    // Create related record directly
    konectyCall('data:create', {
      document: 'Opportunity',
      data: { status: 'Nova', contact: { _id: record._id } }
    });
  }
}
```

## 10. HTTP calls (scriptAfterSave)

`request` is available in scriptAfterSave for calling external APIs.

```javascript
if (data && data.length > 0) {
  var record = data[0];
  if (record.status === 'Ativo' && record.createPassword === true) {
    request.post('https://api.example.com/activate-user?c=' + record.code);
  }
}
```

## 11. Role-based field protection (scriptBeforeValidation)

Prevent certain roles from modifying specific fields by reverting to original value.

```javascript
var ret = {};
var original = extraData.original;
if (['Corretor', 'Gerente'].indexOf(user.role.name) > -1) {
  if (['Cancelar agendamento', 'Solicitar Agendamento'].indexOf(data.photographyStatus) === -1) {
    ret.photographyStatus = original.photographyStatus;
  }
}
return ret;
```

## 12. File existence flags (scriptBeforeValidation)

Track whether file fields have content for easier filtering.

```javascript
var ret = {};
if (data.pictures != null && data.pictures.length > 0) {
  ret.picturesExists = true;
} else {
  ret.picturesExists = false;
}
return ret;
```

## 13. Error handling pattern

Wrap complex logic in try/catch to prevent hook failures from blocking saves.

```javascript
var ret = {};
try {
  // complex computation...
  if (data.sale && data.sale.value) {
    ret.targetPercent = Number((data.saleTarget.value / data.sale.value).toFixed(2));
  }
} catch (e) {
  console.log('SCRIPT BEFORE VALIDATION ERROR');
  console.error(e);
}
return ret;
```

## Key constraints

- Hooks run in `node:vm` sandbox — no `require()`, no `import`, no access to Node.js APIs beyond what is in the sandbox
- `scriptBeforeValidation` and `validationScript` are **synchronous** — no `await`
- `scriptAfterSave` supports `await` and has `moment`, `momentzone`, `request` in the sandbox
- `emails.push()` is only available in `scriptBeforeValidation`
- Always `return ret` from `scriptBeforeValidation` (even if empty `{}`)
- Always `return { success: true }` from `validationScript` on the happy path
