# Meta Namespace — global tenant configuration

Manage the Namespace singleton with `meta_namespace_update` on the `konecty-admin`
MCP server.

## Tool

`meta_namespace_update` — input: `patch`. Output: `result`.

Unlike the `meta_*_upsert` tools, this is a **real patch**: only the keys present in
`patch` are set; everything else is preserved. Still, nested objects are replaced
wholesale per key — to change one email server inside `emailServers`, send the
complete `emailServers` map with your change applied.

Namespace changes affect the whole tenant (email, queues, storage, sessions, MCP
availability). Restate what will change and get user confirmation before patching.

## MCP enablement flags (this skill's own gates)

These namespace keys control MCP availability — the errors they cause are mapped in
[errors → konecty-data](../../konecty-data/references/errors.md) and in
konecty-setup's troubleshooting:

| Key | Type | Effect |
|-----|------|--------|
| `mcpUserEnabled` | boolean | Off ⇒ `/mcp` returns service unavailable (503) |
| `mcpAdminEnabled` | boolean | Off ⇒ `/admin-mcp` returns service unavailable (503) |
| `mcpRoleIds` | string[] | Role `_id`s allowed on the user MCP. **Deny-by-default**: empty/absent ⇒ nobody has access (403 `mcp_access_denied`). Applies to every user-MCP caller — cannot be bypassed per session |
| `mcpUserWriteEnabled` | boolean | Absent/`false` ⇒ **read-only**: `write` scope stripped from every user-MCP caller; write/destructive tools rejected with `insufficient_scope`. `true` ⇒ editing enabled |

Example — enable writes over the user MCP:

```json
{ "patch": { "mcpUserWriteEnabled": true } }
```

Example — allowlist roles:

```json
{ "patch": { "mcpRoleIds": ["<role-_id-1>", "<role-_id-2>"] } }
```

The Admin MCP (`meta_*`) is not affected by `mcpUserWriteEnabled`; it has its own
gate (`admin` flag + `admin` scope).

---

# Namespace Schema Reference

Singleton in `MetaObjects`: `_id: "Namespace"`, `type: "namespace"`.

| Field                         | Type                                  | Description                                                |
| ----------------------------- | ------------------------------------- | ---------------------------------------------------------- |
| `ns`                          | string                                | Namespace identifier (e.g. `"acme"`)                       |
| `name` / `shortName`          | string                                | Display names                                              |
| `logoURL` / `logoBig` / `logoSmall` | string                          | Logos                                                      |
| `active`                      | boolean                               | Namespace active                                           |
| `emailServers`                | `Record<key, SmtpConfig>`             | SMTP servers (referenced by hooks' `emails.push({ server })`) |
| `QueueConfig`                 | QueueConfig                           | RabbitMQ resources and queues (referenced by `document.events`) |
| `storage`                     | StorageConfig                         | File storage (`server` / `s3` / `fs`)                      |
| `plan`                        | PlanConfig                            | Feature flags (`useExternalKonsistent`, `features`)        |
| `onCreate` / `onUpdate` / `onDelete` | string or string[]             | Global webhooks for ALL documents (`${documentId}`/`${dataId}` templates) |
| `public`                      | string[]                              | Namespace fields exposed without authentication            |
| `sessionExpirationInSeconds`  | number                                | Session timeout                                            |
| `dateFormat`                  | string                                | Date format (Luxon)                                        |
| `otpConfig`                   | OtpConfig                             | OTP delivery for the Konecty **UI login** (expiration, WhatsApp, email template) — unrelated to MCP auth, which is OAuth-only |
| `addressSource`               | `"DNE"` or `"Google"`                 | Address lookup provider                                    |
| `mcpUserEnabled` / `mcpAdminEnabled` / `mcpRoleIds` / `mcpUserWriteEnabled` | see above | MCP gates |
| `RocketChat` / `konfront` / `coldcall` / `facebookApp` / `googleApp` / `flows` | object | Integrations |

## emailServers

```json
{
  "smtp_acme": {
    "host": "email-smtp.us-east-1.amazonaws.com",
    "port": 2587,
    "auth": { "user": "AKIA...", "pass": "..." },
    "secure": false
  },
  "default": { "host": "...", "port": 2587, "auth": { "user": "...", "pass": "..." } }
}
```

`host`/`port`/`auth` required unless `service` (e.g. `"SES"`) is set. Optional:
`secure`, `ignoreTLS`, `tls.rejectUnauthorized`, `authMethod`, `useUserCredentials`.

## QueueConfig

```json
{
  "resources": {
    "rabbitmq_default": {
      "type": "rabbitmq",
      "url": "amqp://user:pass@host:5672",
      "queues": [{ "name": "acme-sync-postgres" }, { "name": "trigger-lead-flow" }]
    }
  },
  "konsistent": ["rabbitmq_default", "konsistent"]
}
```

- `resources`: map of connection configs; queue names used by `document.events`
  must exist in the resource's `queues`.
- `konsistent`: `[resourceName, queueName]` receiving Konsistent change-propagation
  events when `plan.useExternalKonsistent` is `true`.

## storage

```json
{ "type": "server", "config": { "upload": "https://blob.example.com", "preview": "https://blob.example.com", "headers": { "origin": "https://crm.example.com" } } }
{ "type": "s3", "config": { "bucket": "my-bucket", "region": "us-east-1", "accessKeyId": "...", "secretAccessKey": "..." } }
{ "type": "fs", "config": { "directory": "/data/uploads" } }
```

## plan

```json
{
  "useExternalKonsistent": true,
  "features": { "createHistory": true, "updateInheritedFields": true, "updateReverseLookups": true, "updateRelations": true }
}
```

## Global webhooks

`onCreate`/`onUpdate`/`onDelete` fire for **every** document unconditionally (string
or array of URL templates). For per-document conditional integrations use
`document.events` instead ([document.md](document.md)).

## otpConfig

Configures OTP delivery for the Konecty **UI login** (not MCP auth — MCP access
is OAuth-only, see [auth.md](auth.md)).

```json
{
  "expirationMinutes": 5,
  "whatsapp": { "accessToken": "...", "phoneNumberId": "...", "templateId": "...", "languageCode": "pt_BR" },
  "emailTemplateId": "template-id",
  "emailFrom": "noreply@example.com"
}
```
