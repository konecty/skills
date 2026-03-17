# Namespace Schema Reference

## Overview

Namespace is a singleton document in `MetaObjects` with `_id: "Namespace"` and `type: "namespace"`. It holds the global configuration for the tenant.

In the filesystem repo: `MetaObjects/Namespace/document.json`

## Schema

| Field                         | Type                                  | Description                                                |
| ----------------------------- | ------------------------------------- | ---------------------------------------------------------- |
| `_id`                         | string                                | Always `"Namespace"`                                       |
| `type`                        | `"namespace"`                         | Discriminator                                              |
| `ns`                          | string                                | Namespace identifier (e.g. `"foxter"`)                     |
| `name`                        | string                                | Display name                                               |
| `shortName`                   | string                                | Short display name                                         |
| `logoURL`                     | string                                | Logo URL                                                   |
| `logoBig`                     | string                                | Large logo URL                                             |
| `logoSmall`                   | string                                | Small logo URL                                             |
| `siteURL`                     | string                                | Site URL                                                   |
| `active`                      | boolean                               | Whether the namespace is active                            |
| `emailServers`                | `Record<key, SmtpConfig>`             | SMTP server configurations                                 |
| `QueueConfig`                 | QueueConfig                           | RabbitMQ resources and queue definitions                   |
| `storage`                     | StorageConfig                         | File storage configuration                                 |
| `plan`                        | PlanConfig                            | Feature flags and plan settings                            |
| `onCreate`                    | string or string[]                    | HTTP URL(s) called on any record create                    |
| `onUpdate`                    | string or string[]                    | HTTP URL(s) called on any record update                    |
| `onDelete`                    | string or string[]                    | HTTP URL(s) called on any record delete                    |
| `public`                      | string[]                              | Namespace fields exposed without authentication            |
| `trackUserGeolocation`        | boolean                               | Track user GPS location                                    |
| `trackUserFingerprint`        | boolean                               | Track user browser fingerprint                             |
| `loginExpiration`             | number                                | Login token expiration (deprecated, use sessionExpiration)  |
| `sessionExpirationInSeconds`  | number                                | Session timeout in seconds                                 |
| `dateFormat`                  | string                                | Date format string (Luxon format)                          |
| `exportXlsLimit`              | number                                | Max rows for XLS export                                    |
| `sendAlertEmail`              | boolean                               | Send alert emails on certain actions                       |
| `addressComplementValidation` | string                                | Regex for address complement validation                    |
| `addressSource`               | `"DNE"` or `"Google"`                 | Address lookup provider                                    |
| `loginPageVariant`            | string                                | Login page variant                                         |
| `ddd`                         | number                                | Default area code for phone numbers                        |
| `watermark`                   | string                                | Image watermark identifier                                 |
| `konfront`                    | object                                | Portal/storefront configuration                            |
| `coldcall`                    | object                                | Cold call campaign configuration                           |
| `RocketChat`                  | RocketChatConfig                      | Rocket.Chat integration                                    |
| `facebookApp`                 | object                                | Facebook integration                                       |
| `googleApp`                   | object                                | Google OAuth configuration                                 |
| `otpConfig`                   | OtpConfig                             | OTP delivery settings                                      |
| `export`                      | `{ largeThreshold }`                  | Export configuration                                       |
| `flows`                       | object                                | Workflow/flow configuration                                |

## emailServers

Map of SMTP server configurations. Keys are referenced by hooks via `emails.push({ server: "key" })`.

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

| Field       | Type    | Required | Description                           |
| ----------- | ------- | -------- | ------------------------------------- |
| `host`      | string  | yes*     | SMTP host                             |
| `port`      | number  | yes*     | SMTP port                             |
| `auth`      | object  | yes*     | `{ user, pass }`                      |
| `secure`    | boolean | no       | Use TLS                               |
| `ignoreTLS` | boolean | no       | Skip TLS entirely                     |
| `service`   | string  | no       | Named service (e.g. `"SES"`) — replaces host/port |
| `tls`       | object  | no       | `{ rejectUnauthorized: boolean }`     |
| `authMethod`| string  | no       | SMTP auth method (e.g. `"LOGIN"`)     |
| `debug`     | boolean | no       | Enable debug logging                  |
| `useUserCredentials` | boolean | no | Use per-user credentials instead      |

*`host`/`port`/`auth` are required unless `service` is specified.

## QueueConfig

Defines RabbitMQ connections and the queues they manage.

```json
{
  "resources": {
    "rabbitmq_default": {
      "type": "rabbitmq",
      "url": "amqp://user:pass@host:5672",
      "queues": [
        { "name": "foxter-sync-postgres" },
        { "name": "trigger-lead-flow" },
        { "name": "marketplace-notification-queue" },
        { "name": "opportunities_filter_changes" },
        { "name": "ppo_discarded" },
        { "name": "piperz-create-session-queue" }
      ]
    }
  },
  "konsistent": ["rabbitmq_default", "konsistent"]
}
```

### resources

Map of resource names to connection configurations:

| Field           | Type     | Required | Description                        |
| --------------- | -------- | -------- | ---------------------------------- |
| `type`          | `"rabbitmq"` | yes  | Resource type (only rabbitmq supported) |
| `url`           | string   | yes      | AMQP connection URL                |
| `queues`        | array    | yes      | List of `{ name, driverParams? }` — queues to create on this connection |

### konsistent

Tuple `[resourceName, queueName]` — which queue receives Konsistent change-propagation events.

The Konsistent system propagates changes (inherited fields, reverse lookups, relations) when records are updated. If `plan.useExternalKonsistent` is `true`, these events are published to this queue instead of being processed inline.

## storage

File storage configuration. Three types supported:

**Server storage (proxy to external server):**
```json
{
  "type": "server",
  "config": {
    "upload": "https://blob.foxter.com.br",
    "preview": "https://blob.foxter.com.br",
    "headers": { "origin": "https://crm.foxter.com.br" }
  }
}
```

**S3 storage:**
```json
{
  "type": "s3",
  "config": {
    "bucket": "my-bucket",
    "region": "us-east-1",
    "accessKeyId": "...",
    "secretAccessKey": "..."
  }
}
```

**Filesystem storage:**
```json
{
  "type": "fs",
  "config": { "directory": "/data/uploads" }
}
```

## plan

Feature flags for the namespace:

```json
{
  "useExternalKonsistent": true,
  "features": {
    "createHistory": true,
    "updateInheritedFields": true,
    "updateReverseLookups": true,
    "updateRelations": true
  }
}
```

- `useExternalKonsistent`: When `true`, Konsistent change events are published to `QueueConfig.konsistent` queue instead of processed inline. Requires `QueueConfig.konsistent` to be configured.
- `features`: Controls which Konsistent operations are active. All default to `true` when not specified.

## onCreate / onUpdate / onDelete

Global HTTP webhook URLs. Called for every record save across all documents. URL template supports `${documentId}` and `${dataId}`.

```json
{
  "onCreate": "http://webservices.example.com/sync/${documentId}/${dataId}",
  "onUpdate": "http://webservices.example.com/sync/${documentId}/${dataId}",
  "onDelete": "http://webservices.example.com/sync/${documentId}/${dataId}"
}
```

Can be a string (single URL) or an array of strings (multiple URLs).

These are different from `document.events` which are per-document and conditional. The namespace webhooks fire for ALL documents unconditionally.

## RocketChat

Integration with Rocket.Chat:

```json
{
  "accessToken": "encrypted-token",
  "livechat": {
    "token": "livechat-widget-token",
    "queue": { "_id": "queue-id" },
    "campaign": { "_id": "campaign-id" },
    "saveCampaignTarget": true
  },
  "alertWebhook": "https://rocketchat.example.com/hooks/..."
}
```

## konfront

Portal/storefront configuration for public-facing sites:

```json
{
  "siteUser": { "_id": "...", "group": { "_id": "...", "name": "..." }, "name": "..." },
  "saveOpportunity": true,
  "opportunityStatus": "Nova",
  "productSearch": true,
  "setCampaign": true,
  "useQueue": true,
  "searchAnyProduct": true,
  "userLabel": "Corretor",
  "chooseAnotherLabel": "Escolher outro corretor"
}
```

## otpConfig

OTP (One-Time Password) delivery configuration:

```json
{
  "expirationMinutes": 5,
  "whatsapp": {
    "accessToken": "...",
    "phoneNumberId": "...",
    "templateId": "...",
    "languageCode": "pt_BR"
  },
  "emailTemplateId": "template-id",
  "emailFrom": "noreply@example.com"
}
```

## Real-world example (foxter)

```json
{
  "_id": "Namespace",
  "type": "namespace",
  "ns": "foxter",
  "active": true,
  "name": "Foxter Cia. Imobiliaria",
  "shortName": "Foxter",
  "siteURL": "https://www.foxterciaimobiliaria.com.br/",
  "dateFormat": "ccc LLL dd yyyy TTT",
  "exportXlsLimit": 2500,
  "sendAlertEmail": true,
  "trackUserGeolocation": false,
  "trackUserFingerprint": true,
  "emailServers": {
    "smtp_foxter": {
      "host": "email-smtp.us-east-1.amazonaws.com",
      "port": 2587,
      "auth": { "user": "...", "pass": "..." },
      "secure": false
    },
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
        "queues": [
          { "name": "foxter-sync-postgres" },
          { "name": "trigger-lead-flow" },
          { "name": "marketplace-notification-queue" }
        ]
      }
    },
    "konsistent": ["rabbitmq_default", "konsistent"]
  },
  "plan": { "useExternalKonsistent": true },
  "public": ["ns", "name", "shortName", "logoBig", "logoSmall", "konfront", "coldcall"]
}
```
