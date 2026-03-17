# Document Events Reference

## Overview

Documents can declare an `events` array in their meta definition. These events are evaluated by the `EventManager` after every record save. If the conditions match, the system publishes a message to a RabbitMQ queue or calls a webhook URL.

**Important:** RabbitMQ queues are NOT accessed inside hooks (`scriptAfterSave`). All queue/webhook integrations are declarative via `document.events`.

## Schema

Each event in the `events` array follows the `DocumentEventSchema`:

```json
{
  "name": "optional-human-readable-name",
  "conditions": {
    "all": [
      { "fact": "operation", "operator": "equal", "value": "update" },
      { "fact": "metaName", "operator": "equal", "value": "Product" }
    ]
  },
  "event": {
    "type": "queue",
    "resource": "rabbitmq_default",
    "queue": "foxter-sync-postgres",
    "sendOriginal": true,
    "sendFull": false
  }
}
```

### Event types

**Queue event:**

| Field          | Type                 | Required | Description                                       |
| -------------- | -------------------- | -------- | ------------------------------------------------- |
| `type`         | `"queue"`            | yes      | Event type discriminator                          |
| `queue`        | string or string[]   | yes      | Queue name(s) to publish to                       |
| `resource`     | string               | yes      | Resource name from `Namespace.QueueConfig.resources` |
| `headers`      | Record<string, any>  | no       | Custom headers passed to the queue message        |
| `sendOriginal` | boolean              | no       | Include pre-save record in the payload            |
| `sendFull`     | boolean              | no       | Include full record in the payload                |

**Webhook event:**

| Field          | Type                 | Required | Description                                       |
| -------------- | -------------------- | -------- | ------------------------------------------------- |
| `type`         | `"webhook"`          | yes      | Event type discriminator                          |
| `url`          | string               | yes      | URL to call                                       |
| `method`       | string               | no       | HTTP method (default: `"GET"`)                    |
| `headers`      | Record<string, string> | no     | HTTP headers                                      |
| `sendOriginal` | boolean              | no       | Include pre-save record in the payload            |
| `sendFull`     | boolean              | no       | Include full record in the payload                |

### Conditions

Conditions use [json-rules-engine](https://github.com/CacheControl/json-rules-engine/blob/master/docs/rules.md) syntax.

Available facts:

| Fact        | Type   | Description                                      |
| ----------- | ------ | ------------------------------------------------ |
| `metaName`  | string | Document name (e.g. `"Product"`)                 |
| `operation` | string | `"create"`, `"update"`, or `"delete"`            |
| `data`      | object | The saved record data                            |
| `original`  | object | Pre-save record (available if `sendOriginal`)    |
| `full`      | object | Full record (available if `sendFull`)            |

Condition operators follow json-rules-engine: `equal`, `notEqual`, `in`, `notIn`, `contains`, `doesNotContain`, `lessThan`, `greaterThan`, etc.

**Examples:**

Trigger only on update:
```json
{ "all": [{ "fact": "operation", "operator": "equal", "value": "update" }] }
```

Trigger when status changes to "Ativo":
```json
{
  "all": [
    { "fact": "operation", "operator": "equal", "value": "update" },
    { "fact": "data", "path": "$.status", "operator": "equal", "value": "Ativo" }
  ]
}
```

## How EventManager processes events

1. After a record save, `EventManager.sendEvent(metaName, operation, { data, original, full })` is called
2. All document events are pre-loaded into a `json-rules-engine` instance at startup (and on metadata reload)
3. The engine evaluates all conditions against the facts
4. For each matching event:
   - **Queue:** `queueManager.sendMessage(resource, queueName, eventData, params)` — publishes to the RabbitMQ queue defined in `Namespace.QueueConfig.resources`
   - **Webhook:** `fetch(url, { method, headers, body: JSON.stringify(eventData) })`

## Relationship with Namespace.QueueConfig

The `resource` field in a queue event references a key in `Namespace.QueueConfig.resources`:

```
event.params.resource = "rabbitmq_default"
                          ↓
Namespace.QueueConfig.resources["rabbitmq_default"] = {
  type: "rabbitmq",
  url: "amqp://...",
  queues: [{ name: "foxter-sync-postgres" }, ...]
}
```

The queue name in the event must exist in the resource's `queues` array. The `QueueManager` creates the queues on startup based on this configuration.

## Payload sent to queue/webhook

```json
{
  "metaName": "Product",
  "operation": "update",
  "data": { ... saved record ... },
  "original": { ... pre-save record (if sendOriginal) ... },
  "full": { ... full record (if sendFull) ... }
}
```

## In the filesystem repo

Events are part of the `document.json` file:

```json
{
  "_id": "Product",
  "type": "document",
  "fields": { ... },
  "events": [
    {
      "name": "sync-postgres",
      "conditions": { "all": [{ "fact": "operation", "operator": "in", "value": ["create", "update"] }] },
      "event": { "type": "queue", "resource": "rabbitmq_default", "queue": "foxter-sync-postgres", "sendOriginal": true }
    }
  ]
}
```
