# Meta Hook — generate, validate, persist

Hook code management on the `konecty-admin` MCP server. **Mandatory order:
`meta_hook_validate` first, `meta_hook_upsert` only after validation passes.**

## Tools

- `meta_hook_validate` — input: `script`. Output: `validation`.
  Validates hook source before save; rejects scripts that import external modules
  (`require`/`import`) or contain comments (`//`, `/* */`).
- `meta_hook_upsert` — input: `id`, `hook` (payload carrying the hook `script`).
  Output: `result`. Persists the hook metadata. It re-checks the same rules — but
  never skip the explicit validate step: catching problems before a write is the
  guardrail.

Reading existing hook code: `meta_read` on the document (hooks are fields of the
document meta — `scriptBeforeValidation`, `validationScript`, `scriptAfterSave`,
`validationData`).

## Flow for any hook change

1. `meta_read` (document name) → current hook code and context.
2. Write/modify the hook following the contracts and rules below.
3. `meta_hook_validate` with the script. Fix and repeat until it passes.
4. Show the user the final code and what it changes.
5. `meta_hook_upsert`.
6. `meta_read` to confirm the persisted state.

## Hook types

| Hook | Kind | When it runs | Sandbox variables | Returns |
|------|------|-------------|--------------------|---------|
| `scriptBeforeValidation` | JS | Before validation | `data, emails, user, console, extraData` | Object merged into `data` |
| `validationData` | JSON | Before validationScript | N/A (config) | Feeds `extraData` |
| `validationScript` | JS | After validationData | `data, user, console, extraData` | `{ success, reason? }` |
| `scriptAfterSave` | JS | After record saved | `data, user, console, Models, extraData, moment, momentzone, request` | None |

Execution order: `scriptBeforeValidation` → `validationData` → `validationScript` →
save → `scriptAfterSave`.

## Code generation rules

1. **scriptBeforeValidation**: always `var ret = {};` at top, `return ret;` at bottom.
2. **validationScript**: always return `{ success: true }` on the happy path;
   reject with `{ success: false, reason: '...' }`.
3. **scriptAfterSave**: `data` may be an **array** for batch operations.
4. **validationData**: pure JSON; `$this.<field>` placeholders resolve from the
   record being saved.
5. `emails.push()` works **only** in `scriptBeforeValidation`.
6. No `require()` / `import` — hooks run in a `node:vm` sandbox.
7. No inline comments in JS hook source (`//` or `/* */`) — validation rejects them.
8. Only `scriptAfterSave` supports `await`; the others are synchronous.
9. Use try/catch around complex logic so hook failures don't block saves.
10. Never post to RabbitMQ from hooks — use `document.events`
    ([document.md](document.md)).

---

# Hook Contracts

## scriptBeforeValidation

`extraData` = `{ request: changedFields, original: preUpdateRecord }` on update;
`{ request: allFields }` on create (`original` undefined). Return an object whose
keys are merged into `data` — this is how computed fields work.

```javascript
var ret = {};
if (data.plan && (!extraData.original || data.plan._id !== extraData.original.plan._id)) {
  ret.planBaseDate = new Date();
}
return ret;
```

### emails.push mechanism

Emails are queued, not sent directly: each pushed object becomes a `Message`
document (`type: 'Email'`, `status: 'Send'`) processed by a worker.

```javascript
emails.push({
  toPath: 'contact.email.0.address',
  from: 'Acme <atendimento@acme.com>',
  server: 'smtp_acme',
  template: 'forwardCandidate',
  relations: { candidate: 1, job: 1, contact: 1 }
});
```

- `relations` populate lookup fields first; then `toPath` (dot-notation) resolves
  the recipient against the populated data.
- `server` references a key in `Namespace.emailServers`
  ([namespace.md](namespace.md)).
- Raw variant: `{ to, from, server, subject, html }`.

## validationData

JSON config that pre-fetches related data for `validationScript`; each alias becomes
a key in `extraData` (array of matching records).

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

## validationScript

```javascript
if (data.plan != null && data.mainContact != null) {
  return {
    success: false,
    reason: 'Um contato não pode ter um Plano e um Contato Principal ao mesmo tempo.'
  };
}
return { success: true };
```

## scriptAfterSave

`data` can be an array; `extraData.original` holds pre-update record(s). Has
`Models` (direct MongoDB collection handles), `moment`, `momentzone`, `request`
(HTTP). No `emails[]` here — use `document.events` for integrations.

```javascript
if (data && data.length > 0) {
  for (var index in data) {
    var original = extraData && extraData.original ? extraData.original[index] : null;
    var record = data[index];
    if (record.status === 'Em Prospecção' && (!original || original.status !== 'Em Prospecção')) {
      konectyCall('data:create', {
        document: 'Opportunity',
        data: { status: 'Nova', contact: { _id: record._id } }
      });
    }
  }
}
```

---

# Common Patterns

**Guard create vs update** — `extraData.original` is undefined on create:

```javascript
var ret = {};
if (extraData.original == null) {
  ret.initialStatus = 'Nova';
} else if (data.status !== extraData.original.status) {
  ret.statusChangedAt = new Date();
}
return ret;
```

**Detect a specific field change** — `extraData.request` has only changed fields:

```javascript
var ret = {};
if (extraData.request && extraData.request.plan) {
  if (!extraData.original.plan || data.plan._id !== extraData.original.plan._id) {
    ret.planBaseDate = new Date();
  }
}
return ret;
```

**Role-based field protection** (revert unauthorized changes):

```javascript
var ret = {};
if (['Corretor', 'Gerente'].indexOf(user.role.name) > -1) {
  if (['Cancelar agendamento'].indexOf(data.photographyStatus) === -1) {
    ret.photographyStatus = extraData.original.photographyStatus;
  }
}
return ret;
```

**Error-safe computation**:

```javascript
var ret = {};
try {
  if (data.sale && data.sale.value && data.areaPrivate > 0) {
    ret.areaPrice = { currency: 'BRL', value: data.sale.value / data.areaPrivate };
  }
} catch (e) {
  console.error(e);
}
return ret;
```

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| Validation rejects imports | `require`/`import` in script | Use only sandbox variables |
| Validation rejects comments | `//` or `/* */` present | Remove all comments |
| `undefined` returned from validationScript | Missing `return { success: true }` | Always return the success object |
| `emails.push` fails in scriptAfterSave | `emails` only exists in scriptBeforeValidation | Move email logic there |
| `$this.field` not resolved | Field doesn't exist on the record | Match the document schema |
| Async in scriptBeforeValidation | Only scriptAfterSave supports `await` | Use sync patterns |
