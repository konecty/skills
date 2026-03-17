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
    from: 'Atendimento <atendimento@foxter.com.br>',
    server: 'smtp_foxter',
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
