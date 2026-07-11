---
name: konecty-dev
description: "Helps developer-agents WRITE CODE to integrate with the Konecty platform — preferring the official SDKs (Python konecty_sdk_python, Node/TS @konecty/sdk), with the full REST API documented for other languages. Covers authenticating server-side code (service-account token), find/query, create, update, delete, cross-module and SQL queries, file upload/download, and writing data hooks (scriptBeforeValidation, validationScript, scriptAfterSave). Use when: escrever código, criar integração, integrar meu app/serviço com Konecty, usar o SDK Python/Node, exemplo de código, gerar um cliente, autenticar código, escrever um hook; write code, build an integration, use the Konecty SDK, code example, generate a client, authenticate server-side, call the Konecty API, write a hook. Do NOT use to run one-off data ops now (find/create/update/delete) — use konecty-data; or to manage schema/metadata — use konecty-meta."
---

# Konecty Dev

Advisory skill for **writing code** that integrates with Konecty. It does not run anything — it teaches
how to build the integration and generates code the developer embeds in their own app. For running a
one-off data operation now, use `konecty-data`; for schema/metadata changes, use `konecty-meta`.

## Prerequisites

The code you write authenticates with a **service-account token** (the `authId` returned by
`POST /rest/auth/login`), supplied via environment, never hardcoded:

```
KONECTY_URL=https://<host>
KONECTY_TOKEN=<authId>
```

See [references/auth-for-code.md](references/auth-for-code.md) for obtaining and securing the token.

## Access path — choose your track

```
Accessing Konecty from code?
├─ Language has an official SDK (Python / Node-TS)?
│   ├─ Yes → use the SDK (always preferred)
│   │        └─ Feature missing from the SDK? → call REST with the language's native HTTP
│   │           client, reusing the same KONECTY_TOKEN (see each SDK doc's "Gaps → REST")
│   └─ No  → use the raw REST API — fully documented with curl (rest-api.md)
└─ Writing server-side business logic on the document itself? → hooks.md
```

SDKs are always preferred. REST is a first-class, language-agnostic track for languages without an
SDK (Java, Go, PHP, …) and the documented fallback when an SDK lacks a feature.

## Commands

| Trigger Pattern | Reference |
|----------------|-----------|
| Get started, choose SDK vs REST, install, first client, começar, qual SDK usar, instalar, primeiro cliente | [references/getting-started.md](references/getting-started.md) |
| Authenticate code, service-account token, env var, security, autenticar código, token de serviço, segurança do token | [references/auth-for-code.md](references/auth-for-code.md) |
| Python SDK, konecty_sdk_python, write Python, exemplo Python, cliente Python | [references/python-sdk.md](references/python-sdk.md) |
| TypeScript/Node SDK, @konecty/sdk, write Node/TS, exemplo Node, cliente TypeScript | [references/typescript-sdk.md](references/typescript-sdk.md) |
| REST API, curl, no SDK / other language (Go, Java, PHP), HTTP endpoints, chamar API REST, sem SDK, outra linguagem | [references/rest-api.md](references/rest-api.md) |
| Filters, conditions, operators, query syntax, filtros, condições, operadores, sintaxe de busca | [references/filters.md](references/filters.md) |
| Recipes, patterns, sync, pagination, retry, file upload flow, receitas, padrões, sincronizar, paginação, repetição | [references/recipes.md](references/recipes.md) |
| Write a hook, scriptBeforeValidation, validationScript, scriptAfterSave, hook variables, escrever hook, lógica de servidor | [references/hooks.md](references/hooks.md) |

## Notes

- Advisory only — no `scripts/`, no live calls. Not part of the `shared-files.txt` invariant.
- Examples are pinned to tested SDK versions (Python `2.0.3`, Node/TS `1.0.0`); each SDK doc links
  upstream for the full surface.
- To version, validate, and apply a hook (not just write it), use `konecty-meta`.
