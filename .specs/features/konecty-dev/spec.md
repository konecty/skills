# konecty-dev Skill Specification

> Third Konecty skill. Where `konecty-data` and `konecty-meta` *operate*, `konecty-dev` *advises*:
> it teaches a developer-agent how to **write code** that integrates with Konecty — preferring the
> official SDKs, falling back to a fully-documented REST API for languages without one.

## Problem Statement

The two existing skills are **operational** — they ship Python scripts the agent *runs* to perform
REST calls right now (`find.py`, `create.py`, `meta_document.py`, …). There is no skill for the
other half of the work: a developer (or a developer-agent) who needs to **build and ship code** that
talks to Konecty from their own application — a Node service that syncs contacts, a Python job that
exports records, a hook that enforces a business rule. Today that developer has to reverse-engineer
the SDKs and the REST surface from three separate upstream repos.

`konecty-dev` fills that gap as a **purely advisory** skill: a lean `SKILL.md` routing to curated
`references/` that document, with verified examples, how to access Konecty via the **Python SDK**
(preferred), the **TypeScript/JS SDK** (preferred), or the **raw REST API** (first-class, for any
language without an SDK). It executes nothing; it produces code the developer embeds and runs.

## Goals

- [ ] G1 — A developer-agent can pick the right access path (Python SDK → TS SDK → raw REST) and write working integration code for the common operations (auth, find/query, create, update, delete, file upload, cross-module query).
- [ ] G2 — SDKs are **always preferred**; REST is documented as a **first-class agnostic track** (via `curl`) for languages without an SDK (Java, Go, PHP, …) and as the fallback when an SDK lacks a feature.
- [ ] G3 — Every reference is **self-contained** (the skill installs standalone) and **version-pinned** (Python `2.0.3`, TS `1.0.0`) with a pointer upstream for the advanced surface.
- [ ] G4 — A dedicated `hooks.md` teaches developers to **write hook logic** (the 4 hook types, when each fires, the sandbox variables, the transaction boundary).
- [ ] G5 — The skill's `description` cleanly separates its triggers from `konecty-data`/`konecty-meta` so the auto-selector routes "build an integration" here and "operate now" there.
- [ ] G6 — Nothing derived from real client projects leaks: no client name appears in any tracked file or git history.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Executing any REST call / running scripts | `konecty-dev` is advisory only (D1). One-off live operations → `konecty-data`/`konecty-meta`. |
| Managing/persisting hooks as metadata (CRUD via `/api/admin/meta/hook`) | That is `konecty-meta`'s job. `konecty-dev` only teaches how to *write* hook logic (D9). |
| Per-language code examples beyond Python + TS | REST is documented agnostically via `curl`; agents port from there. Maintaining Go/PHP/Ruby samples is too costly (D4). |
| Mirroring 100% of the SDK API | We curate the stable ~80% with verified examples + an upstream pointer for the rest (D7). |
| Entering the `shared-files.txt` invariant | Advisory skill carries no `scripts/`; its auth doc is conceptually distinct (D8). |
| Extending the Docker e2e harness | No live operations to test; verification is `make validate` + triggering eval + sanitization (D11). |

---

## Locked Decisions (resolved in the grill-with-docs session, 2026-06-17)

| ID | Decision |
|----|----------|
| **D1** | **Purely advisory.** No `scripts/`, no live REST calls. Lean `SKILL.md` → `references/`. For interactive data inspection during dev, it points to `konecty-data`. |
| **D2** | **Name = `konecty-dev`.** Keeps the `konecty-<domain>` pattern; signals "developer-agent writing integration code" without binding to one access medium. |
| **D3** | **Boundary by intent.** "Operate now" (buscar/criar/listar dados concretos) → `konecty-data`/`konecty-meta`. "Build an integration / write code / use the SDK" → `konecty-dev`. Tie-breaker for ambiguous "give me an example": mentions a language/SDK/file/project → `konecty-dev`; mentions concrete data to fetch/change → `konecty-data`. |
| **D4** | **REST = first-class agnostic track**, via `curl`, complete (auth, filters, pagination, errors). Serves both as the no-SDK path and the SDK fallback. No per-language samples beyond Python/TS. Complete references for **each** scenario. |
| **D5** | **3-level fallback cascade:** (1) feature in the language's SDK → use SDK; (2) feature absent but language has an SDK → use the language's native HTTP client reusing the same token/config (don't switch SDKs); (3) no SDK → raw REST. Each SDK doc has an explicit **"Gaps → when to drop to REST"** section. |
| **D6** | **Auth for code = service-account token.** Obtain `authId` once via `POST /rest/auth/login`, store in an env var (`KONECTY_TOKEN`), never hardcode. Security practices (secret manager, rotation, least-privilege). OTP / `~/.konecty/.env` mentioned only as a dev-time shortcut, not the production pattern. |
| **D7** | **Re-document curated**, not vendored, not link-only. Self-contained references pinned to the tested SDK versions, each opening with "Tested against vX.Y.Z — full surface in `<repo>/docs/api.md`". |
| **D8** | **Out of the shared-files invariant.** No `scripts/auth.py`/`modules.py`; its auth doc (`auth-for-code.md`, service token) is distinct from the OTP `auth.md`. Not added to `shared-files.txt`. |
| **D9** | **`hooks.md` self-contained, "write-the-logic" cut.** The 4 types with purpose + when-to-use, variable tables, lifecycle (order + transaction boundary), 2–3 examples. Controlled conceptual overlap with `konecty-meta/hook.md` (which manages/persists hooks) is accepted; closes with "to version & apply the hook, use `konecty-meta`." |
| **D10** | **Reference-project examples = patterns, not content.** Mine `reference-metas` for idiomatic *shape* only; rewrite 100% of examples with generic modules and invented logic; sanitization checklist per example. Recorded in **ADR-0005**. |
| **D11** | **Verification proportional to advisory nature:** `make validate` (mandatory) + curated example verification at authoring time against pinned SDKs/REST contract + triggering eval via `skill-creator` + sanitization `grep` in the completion gate. No dedicated CI compile harness; no e2e Docker; no shared-files. |
| **D12** | **Content language:** `SKILL.md` `description` bilingual (pt-BR + EN triggers, like the existing skills); reference bodies in **English**. |
| **D13** | **No client name in tracked files / history.** Tracked files use the codename `reference-metas`; the real path lives only in git-ignored `SOURCES.local.md`. A `grep` task in the completion gate fails on any known client name (verify it never entered, rather than clean it up later). |

---

## Proposed structure

```
skills/konecty-dev/
├── SKILL.md                      # lean: frontmatter + trigger→reference table + SDK→REST cascade
└── references/
    ├── getting-started.md        # track choice (which SDK? none?→REST), install, first client
    ├── auth-for-code.md          # service-account token, env vars, security (D6)
    ├── python-sdk.md             # @2.0.3: client, CRUD, query, file, streaming + "Gaps → REST"
    ├── typescript-sdk.md         # @1.0.0: client, CRUD, query, FilesManager + "Gaps → REST"
    ├── rest-api.md               # agnostic complete track: endpoints, headers, pagination, errors (curl)
    ├── filters.md                # filter language (match/conditions/operators) — shared by all 3 tracks
    ├── recipes.md                # patterns: incremental sync, volume pagination, upload, cross-module, retry/errors
    └── hooks.md                  # 4 hook types: purpose, lifecycle, sandbox vars, examples (D9)
```

---

## User Stories

### P1: Write integration code via the preferred SDK ⭐ MVP

**User Story**: As a developer-agent, I want to generate working code (Python or TS) that authenticates and performs CRUD/query against Konecty, so the developer can embed it in their app.

**Why P1**: The reason the skill exists.

**Acceptance Criteria**:
1. WHEN the user asks to "write code / build an integration / use the Konecty SDK" THEN the skill SHALL activate (and NOT activate for "buscar/criar/listar" concrete-data requests — those route to `konecty-data`).
2. WHEN a language with an SDK is chosen THEN the skill SHALL produce examples using that SDK (Python `KonectyClient(base_url, token)`; TS `new KonectyClient({endpoint, accessKey})`).
3. WHEN the example needs auth THEN it SHALL use a service-account token from an env var (`KONECTY_TOKEN`), never hardcoded (D6).
4. WHEN CRUD/query is requested THEN examples SHALL cover find, create, update (with `_updatedAt`), delete, and cross-module query, pinned to the tested SDK version.

**Independent Test**: Ask "escreve um serviço Node que cria um Contact" → output uses `@konecty/sdk` v1.0.0, env-injected token, and a correct `create` call; `make validate` passes on the `SKILL.md`.

---

### P1: Raw REST track for languages without an SDK ⭐ MVP

**User Story**: As a developer in Go/Java/PHP, I want a complete REST reference with `curl` examples so I can integrate without an SDK.

**Why P1**: Half the promise ("API lindamente documentada"); not everyone uses Python/Node.

**Acceptance Criteria**:
1. WHEN no SDK exists for the language THEN the skill SHALL route to `rest-api.md` (agnostic, complete).
2. `rest-api.md` SHALL document auth (`Authorization` header / `authId`), the documented data/query/file endpoints, pagination, sorting, field selection, and the error/`success` envelope — with `curl` examples.
3. `filters.md` SHALL document the filter language (`match`/`conditions`/operators `equals|in|contains|between|exists|…`) once, referenced by all three tracks.
4. WHEN an SDK lacks a feature (Python: `getHistory`/`getMenu`/`lookup`/metadata reads; TS: client-level file upload) THEN the SDK doc's "Gaps → REST" section SHALL point to the matching `rest-api.md` section (D5).

**Independent Test**: Ask "como faço para ler o histórico de um registro em Python" → output explains the SDK gap and shows a native-HTTP call to `/rest/data/:document/:dataId/history` reusing `KONECTY_TOKEN`.

---

### P2: Write hook logic

**User Story**: As a developer, I want to understand and write Konecty hook code (the lifecycle scripts on a document) so I can add business logic at the data layer.

**Why P2**: High-value, but depends on the core tracks existing first.

**Acceptance Criteria**:
1. `hooks.md` SHALL document the 4 hook types with, for each: exact metadata field name, when it fires, purpose, sandbox variables, return contract, and transaction boundary —
   - `scriptBeforeValidation` (before validation; mutates `data`; vars `data, emails, user, console, extraData`; merges returned object; inside tx),
   - `validationScript` + `validationData` (after validation; vetoes via `{success, reason}`; inside tx),
   - `scriptAfterSave` (after commit; side effects; vars incl. `Models, moment, momentzone, request`; async supported; **outside** tx per Konecty ADR-0005).
2. It SHALL note delete runs no hooks, and `changeUser*` runs before/after only if `changeUserRunHooks === true`.
3. It SHALL note the sandbox is `node:vm` (no `require`/`import`/FS).
4. It SHALL close by pointing to `konecty-meta` to version/validate/apply the hook (D9).
5. Every hook example SHALL use generic modules and invented logic — zero client-derived content (D10/D13).

**Independent Test**: Ask "exemplo de hook que calcula um campo derivado antes de salvar" → a generic `scriptBeforeValidation` returning a computed field on `Opportunity`, with the variable table and "this runs inside the transaction" note.

---

### P2: Auth-for-code & security guidance

**User Story**: As a developer, I want the right way to authenticate server-side code and handle the token securely.

**Acceptance Criteria**:
1. `auth-for-code.md` SHALL show obtaining the `authId` via `POST /rest/auth/login` and the fact that `authId` is the `Authorization` value.
2. It SHALL prescribe env var / secret manager storage, rotation, least-privilege service account, and never committing the token.
3. It SHALL mention the `~/.konecty/.env` token from `konecty-data` as a dev-time shortcut only.

**Independent Test**: Ask "como autentico um cron job Python no Konecty" → service-account login snippet + env-var injection + security notes; no OTP-as-production.

---

## Non-Functional Requirements

- **NFR1 — Lean SKILL.md**: `SKILL.md` under ~300 lines; depth lives in `references/`. `description` < 1024 chars, no angle brackets (D12).
- **NFR2 — Self-contained & standalone**: references do not depend on files from other skills; the skill installs alone (D8).
- **NFR3 — Version-pinned**: every SDK doc states the tested version and links upstream for the full surface (D7).
- **NFR4 — Verified examples**: code examples are checked against the pinned SDKs and the REST contract mined from the server at authoring time (D11).
- **NFR5 — Zero client leakage**: no client name in any tracked file or history; codename only; `grep` gate (D13).
- **NFR6 — Advisory, not operational**: ships no executable scripts and makes no live calls (D1).

## Completion Gate (additions for this feature)

- `make validate` — `gh skill publish --dry-run` on `konecty-dev` passes.
- `make audit` — `codebase-intelligence` + `codebase-security` (existing gate).
- **Sanitization grep** — `grep -ri` over the tracked tree for the known client-name list returns **zero** matches (D13). To be wired into the gate.
- Triggering eval (via `skill-creator`) confirms the D3 boundary.
- ADR-0005 (patterns-not-content) + a `docs/changelog/` entry (new skill = structural change) created during EXECUTE.

## Open Questions

None — all design gray areas were resolved in the grill-with-docs session (D1–D13). Remaining choices
(exact recipe set, prose wording) are authoring details for EXECUTE.
