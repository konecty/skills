# Project State — KonectySkills

> Decision log and the *why* behind them. Source of truth. Update on every session.

## Current focus

- **Feature EXECUTED (PR #2 open):** `konecty-dev` — third skill, advisory. `SKILL.md` (lean router, description 912 chars) + 8 references (~2.5k lines, signatures verified against the real SDKs/server) written by parallel Sonnet subagents. Cross-links 100% resolve; `make check` green; `make validate` passes (the `name does not match directory "."` error is a `gh skill` env quirk affecting konecty-data too); `make audit` warn/warn (no fail). Specs: `.specs/features/konecty-dev/`. PR #2 = feat/konecty-skills-consolidation → main (the consolidation is the project's intended new main).
- **Client-name purge (D13).** A client name was found in 6 pre-existing tracked files (konecty-meta references + 1 changelog) — pre-existing debt, not from konecty-dev (its files were clean). Resolution (user decision 2026-06-17): (1) working tree anonymized to generic placeholders (`acme`, `*.example.com`); (2) git history rewritten via `uvx git-filter-repo --replace-text` to purge the name from all past commits → **0 occurrences in history**. The codename↔real-name map lives only in git-ignored `SOURCES.local.md`; never write the literal name in a tracked file (this STATE entry itself was once a leak — keep it generic). Policy: ADR-0005.
  - **Incident + recovery (logged for honesty):** a first rewrite was run against a stale *local* `main` and force-pushed, which momentarily reverted the collaborator's merged PR #1 from public `main`. Detected and **immediately restored** `origin/main` to its original commit (no data lost). The correct purge was then prepared in an **isolated clone**, rewriting all three branches in one consistent pass — verified 0 name occurrences in history AND the PR #1 merge + the collaborator's skill preserved. Backup bundle: `/tmp/konecty-skills-prefilter-backup.bundle`.
  - **Pending:** force-push of the three corrected branches (main, feat/konecty-skills-consolidation, feat/add-skill-code-review) — the last is a collaborator branch, so coordinate before pushing it.
- **Feature COMPLETE:** `e2e-harness` — dockerized Konecty stack + pseudo-agent driving every skill subcommand. **93% line coverage** of the skill scripts (gate `--fail-under=90`), 472 tests passing + 1 documented xfail. Both completion-gate audits pass (intelligence + security = `warn`, no `fail`). konecty-data tested live on 3.8.10 where the public image agrees; the drifted/meta surface covered by the faithful `MockKonecty`. Live swap for konecty-meta deferred to a PR-299 image (D8). Spec: `.specs/features/e2e-harness/`.

## Decisions

### 2026-06-17 — konecty-dev skill design (feature: konecty-dev)

Third skill. Resolved end-to-end in a `grill-with-docs` session. Full spec: `.specs/features/konecty-dev/spec.md`. Sensitive-source policy: `docs/adr/0005-reference-examples-patterns-not-content.md`.

- **D1. Purely advisory.** Unlike `konecty-data`/`konecty-meta` (operational — scripts that *run* REST calls), `konecty-dev` *teaches*: a lean `SKILL.md` → curated `references/`, generating code the developer embeds. **No `scripts/`, no live calls.** For interactive data inspection during dev, it points to `konecty-data`.
- **D2. Name = `konecty-dev`** (keeps `konecty-<domain>`; "developer-agent writing integration code", not bound to one access medium). `konecty-sdk` rejected (undersells the raw-REST half, collides with upstream SDK repo names).
- **D3. Boundary by intent.** "Operate now" (buscar/criar/listar dados concretos) → `konecty-data`/`konecty-meta`; "build an integration / write code / use the SDK" → `konecty-dev`. Tie-breaker for ambiguous "give me an example": mentions language/SDK/file/project → `konecty-dev`; mentions concrete data → `konecty-data`.
- **D4. REST = first-class agnostic track** (via `curl`, complete), not just a fallback — for languages without an SDK (Java, Go, PHP). Complete references **per scenario** (Python SDK / TS SDK / REST). No per-language samples beyond Python/TS.
- **D5. 3-level fallback cascade:** SDK feature → use SDK; feature absent but language has SDK → native HTTP client reusing the same token (don't switch SDKs); no SDK → raw REST. Each SDK doc has a "Gaps → REST" section. SDK gaps mapped: Python lacks `getHistory`/`getMenu`/`lookup`/metadata; TS lacks client-level file upload (separate `FilesManager`); neither covers `/api/admin/meta/*`.
- **D6. Auth for code = service-account token** (`authId` from `POST /rest/auth/login`, stored in `KONECTY_TOKEN` env, never hardcoded) + security practices. OTP / `~/.konecty/.env` only a dev-time shortcut, not production.
- **D7. Re-document curated** (not vendored, not link-only); pinned to tested SDK versions (Python `2.0.3`, TS `1.0.0`); each doc opens "Tested against vX.Y.Z — full surface in `<repo>/docs/api.md`".
- **D8. Out of the shared-files invariant.** No `auth.py`/`modules.py`; auth doc (`auth-for-code.md`, service token) is distinct from the OTP `auth.md`. Not in `shared-files.txt`.
- **D9. `hooks.md` self-contained, "write-the-logic" cut.** 4 types (purpose, lifecycle, sandbox vars, examples). Controlled conceptual overlap with `konecty-meta/hook.md` (which *manages/persists* hooks) accepted; closes pointing to `konecty-meta` to version/apply. Server contract mined from `Konecty/src/imports/data/scripts.js` + `docs/{en,pt-BR}/hooks.md` + Konecty ADR-0005 (`scriptAfterSave` outside the transaction).
- **D10. Reference-project examples = patterns, not content** (ADR-0005). Mine `reference-metas` (codename) for idiomatic *shape* only; rewrite 100% with generic modules + invented logic; sanitization checklist per example.
- **D11. Verification proportional to advisory nature:** `make validate` (mandatory) + curated example verification at authoring time + triggering eval via `skill-creator` + sanitization `grep` in the gate. **No** dedicated CI compile harness, **no** e2e Docker, **no** shared-files.
- **D12. Language:** `SKILL.md` `description` bilingual (pt-BR + EN triggers, like existing skills); reference bodies in **English**.
- **D13. No client name in tracked files / history** (public repo). Tracked files use codename `reference-metas`; real path only in git-ignored `.specs/features/konecty-dev/SOURCES.local.md` (`*.local.md` + `SOURCES.local.md` added to `.gitignore`). A `grep` gate fails on any known client name — verify it *never entered* rather than clean up later.

### 2026-06-17 — installer CLI design (feature: konecty-skills-installer)

- **D1. One-command installer inspirado no Reversa, em Python.** `uvx --from git+https://github.com/konecty/skills konecty-skills install` (repo real = **`konecty/skills`**, público; o remote é `git@github.com:konecty/skills.git`, NÃO `KonectySkills`). Stack Python stdlib encaixa porque as skills já são stdlib puro; `uvx` roda efêmero sem instalação permanente. Espelha o fluxo do Reversa (detectar engine → selecionar → copiar → entry-file → manifest SHA-256) + acrescenta **parametrização de credenciais** (nosso diferencial).
- **D2. Skills baixadas do git em runtime (não package data).** A CLI puxa o tarball da branch/tag na hora — sempre a última versão, desacoplada da versão da CLI. Resolvido no design: tarball via `https://github.com/konecty/skills/archive/refs/heads/{ref}.tar.gz` + `urllib`/`tarfile` (verificado 200; sem exigir `git` no PATH). Q1–Q3 do spec resolvidas em `design.md`: download=tarball; reuso de `auth.py`=subprocess (não import — funções dão `SystemExit`); paths=modelo universal do Reversa (`.agents/skills/` + mirror `.claude/skills/`, `~/.claude/skills/` global).
- **D3. OTP no install.** O passo de credenciais pergunta `KONECTY_URL` e oferece rodar o fluxo OTP ali mesmo (request-otp → verify-otp), gravando `~/.konecty/.env`, reusando `scripts/auth.py` (sem duplicar a lógica). Pular o OTP grava só a URL.
- **D4. Pacote mora em `installer/` neste repo.** Um PR, ciclo único; `uvx --from git+…` aponta para cá. Repo separado/PyPI ficam para depois.
- **D5. Banner = ANSI Shadow blocado, 7 letras → 7 cores do globo** (vermelho/laranja/amarelo/verde/teal/azul/roxo), truecolor. Protótipo validado renderizando em terminal. Subtítulo "BUSINESS PLATFORM".
- **D6. Comandos:** `install` / `configure` / `status` / `update` (proteção SHA-256 contra sobrescrever edições locais) / `doctor` (testa conexão) / `uninstall`. Princípio sagrado herdado do Reversa: **nunca apaga/modifica arquivos preexistentes do usuário.**

### 2026-06-17 — e2e harness design (feature: e2e-harness)

- **D1. Skill invocation = in-process `main(argv)` + a few subprocess smoke calls.** Calling each script's `main(argv)` in-process lets `coverage.py` track argparse + dispatch + `cmd_*` branches in one process (current tests call `cmd_*` directly and never cover `main()`/argparse, capping coverage at ~39%). A handful of real `subprocess` invocations prove the CLI actually runs.
- **D2. Metadata bootstrap = rely on Konecty's built-in base metas + create an isolated E2E document via `konecty-meta`.** The `konecty/konecty` image already ships a base set of metas (Contact, Activity, …) on boot, so data ops have a target without seeding mongo. Write-heavy/destructive tests operate on a freshly-created `E2E*` document and tear it down via `meta_remove` — never corrupting base data.
- **D3. "Inference mocks" = a deterministic intent→command router (no LLM).** A PT/EN phrase router maps user intent to the skill command sequence, mirroring company-brain's offline mock. Covers the skill-selection path with zero API cost or flakiness.
- **D4. Coverage gate = `--fail-under=90`, aim 100%.** Auth/OTP network branches that need a live mail server are mocked; local validation branches run for real.
- **D5. Reference implementation = `/Users/silveira/dev/side-projects/company-brain/`.** Mirror its `docker-compose.yml` (mongo replica set + `mongodb-init` + rabbitmq + `konecty/konecty`), `scripts/konecty_admin_token.py` (admin password from `docker logs` → `/rest/auth/login` → `authId`), and the `record()` PASS/FAIL/SKIP reporting pattern.

## Spike findings — 2026-06-17 (T1, resolves R1–R3 + new blocker)

Probed live against a fresh `konecty/konecty` stack on alt ports (:3200).

- **Image:** company-brain pins `3.2.3` (internal version 1.1.0) — a slim data-runtime that lacks `/rest/query/*` and the whole meta API (hence brain seeds metas straight into mongo). The newest tag is **`3.8.10`**, which exposes the full surface. **E2E pins `3.8.10`.**
- **Boot contract (3.8.10):** requires `COOKIES_SECRET`; needs `NODE_ENV=production` so metas resolve at `/app/private/metadata` (dev mode looks for a nonexistent `src/` path). Both set in `e2e/docker-compose.yml`.
- **R1 — CONFIRMED.** 3.8.10 ships **21 seed metas** on first boot (Contact, Activity, Opportunity, User, Namespace, …). `modules list` against the fresh instance returns all of them. No mongo seeding needed.
- **Auth scheme CHANGED.** 3.8.10 login wants the **raw password** (server hashes); the old `password_SHA256` scheme is rejected. `/rest/auth/*` is a strict-CORS zone → send `Sec-Fetch-Site: none` (or an allow-listed `Origin`). Token script updated to try raw→sha256 and send `Sec-Fetch-Site: none`.
- **konecty-data — FULLY live-testable on 3.8.10.** Verified live: `/rest/query/explorer/modules`, `/rest/query/json`, `/rest/query/sql`, `/rest/data/:doc` find+create, `/rest/file/upload/...` routes present (R2 mitigated — routes exist). Drove the real `modules.py` end-to-end successfully.
- **🚩 BLOCKER — konecty-meta endpoints are STALE.** The skill targets `/api/admin/meta/*`, which **does not exist** on 3.2.3 *or* 3.8.10. The real meta-admin API in 3.8.10 is: `GET/POST/DELETE /api/document[/:name|/:id]`, `GET /api/metas/:document`, `GET /api/form/:document/:id`, `GET /api/list-view/:document/:id`, and `GET/POST/PUT/DELETE /rest/access/:document[/:name]`. So konecty-meta cannot be live-tested as written — pending user decision. R3 depends on the resolution.

### 2026-06-17 — konecty-meta handling for the e2e (resolves the spike blocker)

- **D6. konecty-meta is live-correct but unreleased.** Konecty PR [#299](https://github.com/konecty/Konecty/pull/299) ("feat: admin meta CRUD API", branch `feature/meta-crud-api`) implements exactly the `/api/admin/meta/*` surface the skill uses (admin-only, all meta types, hook sub-routes, reload). The skill's endpoints are **correct** — just not in any published image yet.
- **D7. This round: konecty-data 100% live on 3.8.10; konecty-meta covered by faithful HTTP mocks.** Mocks target the `/api/admin/meta/*` contract from PR #299 (request/response shapes mined from the skill scripts + the existing `tests/integration/test_konecty_meta_ops.py`, which passed against a real backend). Mocks exercise the client code to reach the ≥90% coverage gate.
- **D8. Live konecty-meta deferred to the next round** — when a dev image built from PR #299 (or its merge) is published, swap the mock layer for live calls against it. Harness is structured so only the transport (live vs mocked) changes, not the test bodies.

### 2026-06-17 — konecty-data also drifted from public images → hybrid architecture

- **Finding.** Even on 3.8.10, parts of konecty-data don't match the public image: `/rest/query/json` and `/rest/query/sql` **require a `relations` array with ≥1 element**, but the skill's internal record-fetch (and `find query`/`sql`, `create lookup`, `update fetch`/`patch`, `delete preview`/`delete`) omit it → HTTP 400. Login also changed (raw password + `Sec-Fetch-Site`). The skills are written for the team's target Konecty, not public images.
- **D9. Hybrid test architecture.**
  - **Live suite** (`tests/e2e/test_live_data.py`, marked `live`): drives the konecty-data subset the public 3.8.10 image *does* support against the real stack — `auth login-options`, `modules list/fields/search`, `find find` (+filter/fields/ndjson), `create create`, `update update` (explicit `--ids`). Real integration proof. Skipped if the stack is down. Test records cleaned up via direct API in a finalizer (skill `delete` uses the drifted query path).
  - **Mock coverage suite** (`tests/e2e/test_data_mock.py` + `test_meta_mock.py`, marked `mock`): drives **every** subcommand of both skills against an extended `MockKonecty` (data + query + file + auth + meta) so all code paths execute → the ≥90% coverage gate. No stack needed.
  - Net: real e2e where the image agrees, full coverage everywhere, honest separation, clean path to fully-live next round.
- **D10. `uv` runs the suite** (`uv run --with pytest --with coverage pytest ...`) — system pip is PEP-668 externally-managed; `uv` matches the company-brain reference and needs no global installs.

## Deferred ideas

- **Fully-live e2e for the drifted paths** (query/json+relations, meta API) against a Konecty image built from PR #299 / the team's target version — swap mock transport for live (D8, D9).
- Publishing the harness as CI (GitHub Action) once green locally.
