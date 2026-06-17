# konecty-dev — Design

> Content architecture for the advisory skill. Spec: `spec.md`. Decisions: `STATE.md` D1–D13.
> This is a **documentation** skill — "architecture" here means how knowledge is partitioned across
> `SKILL.md` + 8 reference docs, what each contains, and how they cross-link.

## 1. Design principles

1. **Lean router, deep references.** `SKILL.md` carries only: frontmatter, the trigger→reference table, the SDK→REST decision cascade, and the prerequisites. All substance lives in `references/` (NFR1).
2. **One concept, one home.** Each fact lives in exactly one doc; others link to it. The filter language lives only in `filters.md`; auth only in `auth-for-code.md` (D8). No duplication → no drift.
3. **SDK-first, REST-complete.** Every operation is shown SDK-first (Python, TS). REST is a complete parallel track, not an afterthought (D4).
4. **Self-contained & pinned.** No cross-skill file dependencies (D8). Every SDK doc states its tested version and links upstream for the long tail (D7).
5. **Generic examples only.** Modules are always `Contact`, `Opportunity`, `Product`, `Task`; logic is invented; no client-derived content (D10/D13).

## 2. Reference graph

```
SKILL.md ──┬─→ getting-started.md ──→ (picks a track, links onward)
           │        │
           │        ├─→ python-sdk.md ─────┐
           │        ├─→ typescript-sdk.md ─┤→ filters.md   (filter language, shared)
           │        └─→ rest-api.md ───────┘→ auth-for-code.md (token, shared)
           │
           ├─→ recipes.md   (composes the above into end-to-end patterns)
           └─→ hooks.md     (server-side hook logic; links to konecty-meta to apply)
```

Cross-link rules:
- `python-sdk.md` / `typescript-sdk.md` / `rest-api.md` each link to `filters.md` for filter syntax and to `auth-for-code.md` for credentials — they never restate them.
- Each SDK doc's "Gaps → REST" section links to the specific `rest-api.md` anchor for the missing feature (D5).
- `hooks.md` ends linking to `konecty-meta` (apply/version/validate the hook) (D9).

## 3. Surface map — endpoint ↔ Python SDK ↔ TS SDK ↔ doc ↔ status

Tested versions: **Python `konecty_sdk_python` 2.0.3**, **TS `@konecty/sdk` 1.0.0** (D7).

| Operation | REST endpoint | Python SDK | TS SDK | Primary doc | Note |
|-----------|---------------|------------|--------|-------------|------|
| Authenticate | `POST /rest/auth/login` → `authId` | constructor `token` (login not wrapped) | `client.login()` | auth-for-code.md | token = `Authorization` value |
| Find / search | `GET /rest/data/:doc/find` | `find` / `find_sync` / `find_one` | `find` | python/ts/rest | filter via filters.md |
| Find by id | `GET /rest/data/:doc/:id` | `find_by_id` | (via `find`) | python/ts/rest | |
| Create | `POST /rest/data/:doc` | `create` | `create` | python/ts/rest | |
| Update | `PUT /rest/data/:doc` | `update` / `update_one` | `update` | python/ts/rest | needs `_id`+`_updatedAt` |
| Delete | `DELETE /rest/data/:doc` | `delete_one` | `delete` | python/ts/rest | |
| Count | `GET …/find` (count) | `count_documents` / `count_stream` | `streamCount` | python/ts | |
| Stream find | `GET /rest/stream/:doc/findStream` | `find_stream` | `findStream` | recipes.md | volume pagination |
| Cross-module query | `POST /rest/query/json` | `execute_query_json` | `executeQueryJson` | python/ts/rest | needs `relations[≥1]` (see STATE D9) |
| SQL query | `POST /rest/query/sql` | `execute_query_sql` | `executeQuerySql` | python/ts/rest | SELECT-only, length cap |
| File upload | `POST /rest/file/upload/…` | `upload_file` | **`FilesManager`** (not on client) | python/ts/rest | **TS gap on client** → FilesManager or REST |
| File download | `GET /rest/file/:doc/:code/:field/:name` | `download_file` | `downloadFile` | python/ts/rest | |
| Image download | `GET /rest/image/…` | `download_image` | `downloadImage` | python/ts | styles full/thumb/wm |
| KPI / graph / pivot | `GET /rest/data/:doc/{kpi,graph,pivot}` | `get_kpi`/`get_graph`/`get_pivot` | `getKpi`/`getGraph`/`getPivot` | recipes.md | |
| History | `GET /rest/data/:doc/:id/history` | **❌ gap** → REST | `getHistory` | rest-api.md | **Python gap** |
| Lookup field | `GET /rest/data/:doc/lookup/:field` | **❌ gap** → REST | `lookup` | rest-api.md | **Python gap** |
| Menu / form / list-view | `GET /api/{menu,form,list-view}/…` | **❌ gap** → REST | `getMenu`/`getForm`/`getListView` | rest-api.md | **Python gap** |
| Comments | `/rest/comment/:doc/:id…` | full | full | recipes.md | both cover |
| Notifications | `/rest/notifications…` | full | full | recipes.md | both cover |
| Subscriptions | `/rest/subscriptions/:doc/:id` | full | full | recipes.md | both cover |
| changeUser | `POST /rest/changeUser/:doc/:action` | full | full | recipes.md | both cover |
| Admin meta CRUD | `/api/admin/meta/*` | **❌ neither** | **❌ neither** | (out of scope) | → `konecty-meta` |

This table is the single source for each SDK doc's **"Gaps → REST"** section (D5).

## 4. Per-reference outline

### 4.1 `getting-started.md`
- Decision: which track? (flowchart in §5) — Python? TS/Node? neither → REST.
- Install: `pip install konecty_sdk_python==2.0.3` / `npm i @konecty/sdk@1.0.0`.
- First client (both SDKs) + a `curl` smoke call. Points to auth-for-code.md for the token.
- Links onward to the three track docs.

### 4.2 `auth-for-code.md` (D6)
- The model: `authId` (from `POST /rest/auth/login`) **is** the `Authorization` header value.
- Obtain a service-account token (login snippet, Python + TS + curl).
- Store in env (`KONECTY_TOKEN`) / secret manager; rotation; least-privilege account; never hardcode/commit.
- Dev-time shortcut: reuse `~/.konecty/.env` written by `konecty-data` (explicitly *not* the production pattern).
- Strict-CORS note for `/rest/auth/*` (`Sec-Fetch-Site: none`) from STATE spike findings.

### 4.3 `python-sdk.md` (pin 2.0.3)
- Header: "Tested against 2.0.3 — full surface in `konecty-sdk-python/docs/api.md`".
- Client init (sync + async); find/find_one/create/update_one/delete_one; query json/sql; file up/download; streaming.
- "Gaps → REST" → history, lookup, menu/form/list-view (native `httpx`/`requests` reusing `KONECTY_TOKEN`).

### 4.4 `typescript-sdk.md` (pin 1.0.0)
- Header: "Tested against 1.0.0 — full surface in `konecty-sdk/docs/api.md`".
- Client init `{endpoint, accessKey}`; find/create/update/delete; query json/sql; download; `getHistory`/`getMenu`/`lookup` (TS advantages).
- "Gaps → REST" → client-level **file upload** (use `FilesManager` or REST).

### 4.5 `rest-api.md` (agnostic, complete — D4)
- Base URL, `Authorization` header, `success`/error envelope, status codes (200/400/401/403/404/429/500).
- Data endpoints (find GET+POST, by-id, create, update, delete), query (json+sql, NDJSON `_meta` line), file (upload/download/delete), auth (login/OTP/logout/info).
- Pagination (`start`/`limit`/`total`), sorting (`[{property,direction}]`), field selection (`fields`).
- Every endpoint with a `curl` example. Links to filters.md.

### 4.6 `filters.md` (shared — D3/D4)
- `{ match: "and|or", conditions: [{ term, operator, value }], filters: [...], textSearch }`.
- Operators: `equals`, `not_equals`, `in`, `not_in`, `contains`, `starts_with`, `end_with`, `less_than`, `greater_than`, `between`, `exists`, lookup `term: "field._id"`.
- One worked example per operator; nested groups; cross-module `relations` shape (links to query sections).

### 4.7 `recipes.md`
- Incremental sync (`_updatedAt` watermark + pagination).
- Volume export via stream (`findStream`/`find_stream`).
- File attach/replace flow.
- Cross-module query with aggregators (`count`/`push`).
- Robust client: retry/backoff, 429 handling, timeouts, error envelope parsing.
- KPI/graph/pivot quick calls.

### 4.8 `hooks.md` (D9 — server contract from `Konecty/src/imports/data/scripts.js` + docs + Konecty ADR-0005)
- What a hook is; sandbox = `node:vm` (no `require`/`import`/FS).
- Per type — field name, when it fires, purpose, variable table, return contract, transaction boundary:
  - `scriptBeforeValidation` — before validation; mutates (merge returned obj); `data, emails, user, console, extraData{original,request,validated}`; inside tx; can `emails.push()`.
  - `validationScript` (+ `validationData` query-prefetch) — after validation; veto `{success, reason?}`; `data, user, console, extraData`; inside tx.
  - `scriptAfterSave` — after commit; side effects; `data, user, console, Models, extraData, moment, momentzone, request`; async supported; **outside** tx.
- Lifecycle diagram (create/update order); delete runs none; `changeUser*` only if `changeUserRunHooks===true`.
- 2–3 generic examples (computed field; cross-field veto; cross-doc side effect).
- Closes: "to version, validate (`/api/admin/meta/hook/validate`) and apply the hook → use `konecty-meta`."

## 5. Decision cascade (goes in SKILL.md)

```
Need to access Konecty from code?
├─ Language has an official SDK (Python / Node-TS)?
│   ├─ Yes → use the SDK (preferred)
│   │        └─ Feature missing from the SDK? → call REST with the language's native
│   │           HTTP client, reusing the same KONECTY_TOKEN  (see <sdk>.md "Gaps → REST")
│   └─ No  → use the raw REST API (rest-api.md) — fully documented, curl examples
└─ Writing server-side business logic on the document itself? → hooks.md
```

## 6. SKILL.md draft

**Frontmatter `description`** (bilingual, <1024 chars, no angle brackets — D12):

> Guides developers and developer-agents who WRITE CODE to integrate with the Konecty platform — preferring the official SDKs (Python `konecty_sdk_python`, Node/TS `@konecty/sdk`) and documenting the full REST API for any other language. Covers authenticating server-side code (service-account token), find/query, create, update, delete, cross-module and SQL queries, file upload/download, and writing data hooks (scriptBeforeValidation, validationScript, scriptAfterSave). Use when: escrever código, criar integração, integrar meu app/serviço com Konecty, usar o SDK Python/Node, exemplo de código/cliente, gerar um cliente, autenticar código no Konecty, escrever um hook; write code, build an integration, use the Konecty SDK, code example, generate a client, authenticate server-side, write a hook. Do NOT use to run one-off data operations (find/create/update/delete now) — use konecty-data; or to manage schema/metadata — use konecty-meta.

**Trigger table** (body): one row per reference, pt-BR + EN phrases, mirroring the existing skills' format. SDK→REST cascade (§5) printed right below.

## 7. Verification (D11)
- `make validate` on `konecty-dev`.
- Examples verified at authoring time against pinned SDKs + the REST contract mined here.
- Triggering eval (skill-creator): "build an integration" → konecty-dev; "buscar contatos" → konecty-data.
- Sanitization `grep` gate (D13) + `make audit`.

## 8. Out-of-design (deferred to authoring)
- Exact prose, the final recipe count, and which 3 hook examples — authoring details, not architecture.
