# Meta Schemas Reference

All metadata types live in the `MetaObjects` MongoDB collection, discriminated by the `type` field.

## document

`_id` pattern: `{DocumentName}` (e.g. `Contact`, `User`)

| Field                      | Type                    | Required | Description                                         |
| -------------------------- | ----------------------- | -------- | --------------------------------------------------- |
| `_id`                      | string                  | yes      | Document name                                       |
| `type`                     | `"document"`            | yes      | Discriminator                                       |
| `name`                     | string                  | yes      | Same as `_id`                                       |
| `label`                    | `{ en, pt_BR }`         | yes      | Bilingual label                                     |
| `plurals`                  | `{ en, pt_BR }`         | yes      | Bilingual plural label                              |
| `icon`                     | string                  | yes      | Icon name                                           |
| `fields`                   | `Record<name, Field>`   | yes      | Object-map of field definitions (NOT an array)       |
| `collection`               | string                  | no       | MongoDB collection name (defaults to `data.{name}`) |
| `group`                    | string                  | no       | Menu group                                          |
| `menuSorter`               | number                  | no       | Menu sort order                                     |
| `description`              | `{ en, pt_BR }`         | no       | Description text                                    |
| `help`                     | `{ en, pt_BR }`         | no       | Help text                                           |
| `access`                   | string                  | no       | Default access profile name                         |
| `relations`                | Relation[]              | no       | Related document definitions                        |
| `indexes`                  | Record<name, Index>     | no       | MongoDB indexes                                     |
| `indexText`                | Record<field, weight>   | no       | Text search index fields                            |
| `events`                   | DocumentEvent[]         | no       | Queue/webhook event declarations                    |
| `scriptBeforeValidation`   | string                  | no       | Hook JS code (injected from .js file in repo)       |
| `validationScript`         | string                  | no       | Hook JS code                                        |
| `scriptAfterSave`          | string                  | no       | Hook JS code                                        |
| `validationData`           | object                  | no       | Hook JSON (injected from .json file in repo)        |

### Minimal example (from User.json)

```json
{
  "_id": "User",
  "type": "document",
  "name": "User",
  "collection": "users",
  "label": { "en": "User", "pt_BR": "Usuário" },
  "plurals": { "en": "Users", "pt_BR": "Usuários" },
  "icon": "user",
  "description": { "en": "System users", "pt_BR": "Usuários do sistema" },
  "fields": {
    "active": {
      "type": "boolean", "name": "active",
      "label": { "en": "Active", "pt_BR": "Ativo" },
      "isRequired": true, "isSortable": true, "defaultValue": true
    },
    "code": {
      "type": "autoNumber", "name": "code",
      "label": { "en": "Code", "pt_BR": "Código" },
      "isUnique": true, "isSortable": true
    },
    "emails": {
      "type": "email", "name": "emails",
      "label": { "en": "Email", "pt_BR": "Email" },
      "isList": true, "isSortable": true
    }
  }
}
```

---

## list

`_id` pattern: `{Document}:list:{Name}` (e.g. `Activity:list:Default`)

| Field            | Type                        | Required | Description                                        |
| ---------------- | --------------------------- | -------- | -------------------------------------------------- |
| `_id`            | string                      | yes      | `{Document}:list:{Name}`                           |
| `type`           | `"list"`                    | yes      | Discriminator                                      |
| `document`       | string                      | yes      | Parent document name                               |
| `name`           | string                      | yes      | List name                                          |
| `label`          | `{ en, pt_BR }`             | yes      | Bilingual label                                    |
| `plurals`        | `{ en, pt_BR }`             | yes      | Bilingual plural                                   |
| `columns`        | `Record<name, Column>`      | yes      | Object-map of columns (NOT an array)               |
| `sorters`        | `[{ term, direction }]`     | yes      | Default sort order                                 |
| `view`           | string                      | no       | Form view to open on click (default: `"Default"`)  |
| `filter`         | KonFilter                   | no       | Default filter                                     |
| `refreshRate`    | `{ options, default }`      | yes      | Auto-refresh options (seconds, 0=off)              |
| `rowsPerPage`    | `{ options, default }`      | yes      | Pagination options                                 |
| `loadDataAtOpen` | boolean                     | no       | Load data immediately                              |
| `calendars`      | Calendar[]                  | no       | Calendar view definitions                          |
| `boards`         | Board[]                     | no       | Board/kanban definitions                           |
| `namespace`      | string[]                    | no       | Namespace(s)                                       |
| `icon`           | string                      | no       | Icon name                                          |
| `menuSorter`     | number                      | no       | Menu sort                                          |
| `group`          | string                      | no       | Menu group                                         |

### Column structure

```json
{
  "code": {
    "name": "code",
    "linkField": "code",
    "visible": true,
    "minWidth": 60,
    "sort": 0
  }
}
```

- `linkField`: maps to a field name in the parent document's `fields`
- `visible`: shown by default
- `sort`: column display order
- `style`: optional styling (e.g. `colorBasedOnTime`)

### Real example (Activity:list:Default)

```json
{
  "_id": "Activity:list:Default",
  "type": "list",
  "document": "Activity",
  "name": "Default",
  "label": { "pt_BR": "Atividade", "en": "Activity" },
  "plurals": { "en": "Activities", "pt_BR": "Atividades" },
  "columns": {
    "code": { "name": "code", "linkField": "code", "visible": true, "minWidth": 60, "sort": 0 },
    "status": { "name": "status", "linkField": "status", "visible": true, "minWidth": 100, "sort": 1 },
    "subject": { "name": "subject", "linkField": "subject", "visible": true, "minWidth": 250, "sort": 6 }
  },
  "filter": {
    "match": "and",
    "conditions": {
      "status:in": {
        "term": "status", "value": ["Nova", "Em Andamento"],
        "operator": "in", "editable": true,
        "style": { "columns": 1, "renderAs": "checkbox" },
        "sort": 5
      }
    }
  },
  "sorters": [{ "term": "code", "direction": "desc" }],
  "refreshRate": { "options": [0, 5, 10, 15, 30, 60], "default": 0 },
  "rowsPerPage": { "options": [5, 10, 25, 50, 100], "default": 25 },
  "view": "Default",
  "loadDataAtOpen": true
}
```

---

## view (FormSchema)

`_id` pattern: `{Document}:view:{Name}` (e.g. `Activity:view:Default`)

| Field       | Type              | Required | Description                              |
| ----------- | ----------------- | -------- | ---------------------------------------- |
| `_id`       | string            | yes      | `{Document}:view:{Name}`                 |
| `type`      | `"view"`          | yes      | Discriminator                            |
| `document`  | string            | yes      | Parent document name                     |
| `name`      | string            | yes      | View name                                |
| `label`     | `{ en, pt_BR }`   | yes      | Label (can use `{field}` interpolation)  |
| `plurals`   | `{ en, pt_BR }`   | yes      | Bilingual plural                         |
| `visuals`   | Visual[]          | no       | Recursive visual tree                    |
| `parent`    | string            | no       | Parent view for inheritance              |
| `namespace` | string[]          | no       | Namespace(s)                             |
| `icon`      | string            | no       | Icon name                                |

### Visual tree types

- `visualGroup`: container with nested `visuals[]`, has `style.title` and `style.icon`
- `visualSymlink`: references a field from the document; has `fieldName` and optional `style`
- `reverseLookup`: shows related records from another document; has `field`, `document`, `list`

### Real example (Activity:view:Default)

```json
{
  "_id": "Activity:view:Default",
  "type": "view",
  "document": "Activity",
  "name": "Default",
  "label": { "en": "{code}: {type} - {subject}", "pt_BR": "{code}: {type} - {subject}" },
  "plurals": { "en": "New Activity", "pt_BR": "Nova Atividade" },
  "visuals": [
    {
      "type": "visualGroup",
      "label": { "en": "Formulário", "pt_BR": "Formulário" },
      "visuals": [
        {
          "type": "visualGroup",
          "style": { "icon": "info-sign", "title": { "pt_BR": "Informações", "en": "Information" } },
          "label": { "en": "Information", "pt_BR": "Informações" },
          "visuals": [
            { "type": "visualSymlink", "style": { "readOnlyVersion": true }, "fieldName": "code" },
            { "type": "visualSymlink", "style": { "renderAs": "with_scroll" }, "fieldName": "type" },
            { "type": "visualSymlink", "fieldName": "subject" }
          ]
        }
      ]
    },
    {
      "type": "reverseLookup",
      "style": { "title": { "en": "Sub-activities", "pt_BR": "Subatividades" } },
      "field": "relatedTo",
      "document": "Activity",
      "list": "ForLookup"
    }
  ]
}
```

---

## pivot

`_id` pattern: `{Document}:pivot:{Name}` (e.g. `Activity:pivot:Default`)

| Field         | Type                        | Required | Description                               |
| ------------- | --------------------------- | -------- | ----------------------------------------- |
| `_id`         | string                      | yes      | `{Document}:pivot:{Name}`                 |
| `type`        | `"pivot"`                   | yes      | Discriminator                             |
| `document`    | string                      | yes      | Parent document name                      |
| `name`        | string                      | yes      | Pivot name                                |
| `label`       | `{ en, pt_BR }`             | yes      | Bilingual label                           |
| `plurals`     | `{ en, pt_BR }`             | yes      | Bilingual plural                          |
| `rows`        | PivotField[]                | no       | Row grouping fields                       |
| `columns`     | `Record<name, Column>`      | no       | Column fields                             |
| `values`      | PivotValue[]                | no       | Aggregated value fields                   |
| `filter`      | KonFilter                   | no       | Default filter                            |
| `sorters`     | `[{ term, direction }]`     | no       | Default sort                              |
| `refreshRate` | `{ options, default }`      | no       | Auto-refresh                              |
| `rowsPerPage` | `{ options, default }`      | no       | Pagination                                |
| `namespace`   | string[]                    | no       | Namespace(s)                              |
| `icon`        | string                      | no       | Icon name                                 |
| `menuSorter`  | number                      | no       | Menu sort                                 |
| `group`       | string                      | no       | Menu group                                |

### PivotValue

```json
{ "name": "code", "linkField": "code", "visible": true, "minWidth": 50,
  "label": { "en": "Code", "pt_BR": "Código" }, "aggregator": "count" }
```

Supported aggregators: `count`, `sum`, `avg`, `min`, `max`.

### Real example (Activity:pivot:Default)

```json
{
  "_id": "Activity:pivot:Default",
  "type": "pivot",
  "document": "Activity",
  "name": "Default",
  "label": { "en": "Report", "pt_BR": "Relatório" },
  "plurals": { "en": "Report", "pt_BR": "Relatório" },
  "rows": [
    { "name": "_user.group", "linkField": "_user.group", "visible": true,
      "label": { "en": "User", "pt_BR": "Usuário" } },
    { "name": "_user", "linkField": "_user", "visible": true,
      "label": { "en": "User", "pt_BR": "Usuário" } }
  ],
  "columns": {
    "status": { "name": "status", "linkField": "status", "visible": true, "minWidth": 150,
      "label": { "en": "Status", "pt_BR": "Situação" } }
  },
  "values": [
    { "name": "code", "linkField": "code", "visible": true, "minWidth": 50,
      "label": { "en": "Code", "pt_BR": "Código" }, "aggregator": "count" }
  ],
  "filter": {
    "match": "and",
    "conditions": {
      "status:in": { "term": "status", "value": ["Nova", "Em Andamento"],
        "operator": "in", "editable": true }
    }
  },
  "sorters": [{ "term": "status", "direction": "asc" }],
  "rowsPerPage": { "options": [100, 1000, 10000], "default": 1000 }
}
```

---

## access

`_id` pattern: `{Document}:access:{Name}` (e.g. `Contact:access:Corretor`)

See [access-architecture.md](../../konecty-meta-access/references/access-architecture.md) for the complete schema and resolution logic.

### Minimal functional example

```json
{
  "_id": "Contact:access:Default",
  "type": "access",
  "document": "Contact",
  "name": "Default",
  "isReadable": true,
  "isCreatable": true,
  "isUpdatable": true,
  "isDeletable": false,
  "fieldDefaults": {
    "isReadable": true,
    "isCreatable": true,
    "isUpdatable": true,
    "isDeletable": false
  },
  "fields": {}
}
```

---

## namespace

`_id`: always `"Namespace"` (singleton)

| Field                    | Type                          | Required | Description                                  |
| ------------------------ | ----------------------------- | -------- | -------------------------------------------- |
| `_id`                    | string                        | yes      | `"Namespace"`                                |
| `type`                   | `"namespace"`                 | yes      | Discriminator                                |
| `ns`                     | string                        | yes      | Namespace identifier                         |
| `name`                   | string                        | no       | Display name                                 |
| `emailServers`           | `Record<key, SmtpConfig>`     | no       | SMTP servers for email hooks                 |
| `QueueConfig`            | QueueConfig                   | no       | RabbitMQ resources and queue definitions      |
| `storage`                | S3 or FS or Server config     | no       | File storage configuration                   |
| `plan`                   | `{ useExternalKonsistent }`   | no       | Feature flags                                |
| `onCreate`               | string or string[]            | no       | HTTP webhook URL(s) on record create         |
| `onUpdate`               | string or string[]            | no       | HTTP webhook URL(s) on record update         |
| `onDelete`               | string or string[]            | no       | HTTP webhook URL(s) on record delete         |
| `trackUserGeolocation`   | boolean                       | no       | Track user location                          |
| `trackUserFingerprint`   | boolean                       | no       | Track user fingerprint                       |
| `loginExpiration`        | number                        | no       | Login expiration time                        |
| `sessionExpirationInSeconds` | number                    | no       | Session timeout                              |
| `dateFormat`             | string                        | no       | Date format string                           |
| `logoURL`                | string                        | no       | Logo URL                                     |
| `RocketChat`             | object                        | no       | Rocket.Chat integration config               |
| `otpConfig`              | object                        | no       | OTP delivery configuration                   |
| `export`                 | `{ largeThreshold }`          | no       | Export settings                              |
| `public`                 | string[]                      | no       | Fields exposed without authentication        |
| `konfront`               | object                        | no       | Portal/storefront configuration              |
| `coldcall`               | object                        | no       | Cold call campaign configuration             |
| `addressSource`          | `"DNE"` or `"Google"`         | no       | Address lookup provider                      |

### QueueConfig structure

```json
{
  "resources": {
    "rabbitmq_default": {
      "type": "rabbitmq",
      "url": "amqp://user:pass@host:5672",
      "queues": [
        { "name": "foxter-sync-postgres" },
        { "name": "trigger-lead-flow" }
      ]
    }
  },
  "konsistent": ["rabbitmq_default", "konsistent"]
}
```

### emailServers structure

```json
{
  "smtp_foxter": {
    "host": "email-smtp.us-east-1.amazonaws.com",
    "port": 2587,
    "auth": { "user": "AKIA...", "pass": "..." },
    "secure": false
  },
  "default": {
    "host": "email-smtp.us-east-1.amazonaws.com",
    "port": 2587,
    "auth": { "user": "AKIA...", "pass": "..." }
  }
}
```

Referenced by hooks: `emails.push({ server: "smtp_foxter", ... })`

### Minimal Namespace example

```json
{
  "_id": "Namespace",
  "type": "namespace",
  "ns": "foxter",
  "name": "Foxter Cia. Imobiliaria",
  "emailServers": {
    "default": {
      "host": "email-smtp.us-east-1.amazonaws.com",
      "port": 2587,
      "auth": { "user": "...", "pass": "..." }
    }
  },
  "storage": {
    "type": "server",
    "config": {
      "upload": "https://blob.foxter.com.br",
      "preview": "https://blob.foxter.com.br",
      "headers": { "origin": "https://crm.foxter.com.br" }
    }
  },
  "QueueConfig": {
    "resources": {
      "rabbitmq_default": {
        "type": "rabbitmq",
        "url": "amqp://crm:pass@rabbit-cluster:5672",
        "queues": [{ "name": "foxter-sync-postgres" }]
      }
    },
    "konsistent": ["rabbitmq_default", "konsistent"]
  },
  "plan": { "useExternalKonsistent": true }
}
```

---

## composite

`_id` pattern: same as `document` (e.g. `Education`)

Composites have the same schema as `document` but represent embedded sub-documents that do not have their own MongoDB collection. They are referenced via `field.type: "composite"` with `field.document: "Education"`.

---

## card

`_id` pattern: `{Document}:card:{Name}` (e.g. `Opportunity:card:Default`)

Cards are compact view definitions used in board/kanban modes. They follow a similar structure to views but with a simplified layout optimized for card display.
