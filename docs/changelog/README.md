# Changelog

All notable changes to KonectySkills are documented here.

| Date | Summary |
|------|---------|
| [2026-07-14](./2026-07-14_admin-oauth-default.md) | **Admin OAuth por padrão**: instalador e skill `konecty-setup` passam a liderar com o caminho OAuth de cliente confiável para o admin MCP (`konecty-admin`); OTP → Bearer vira fallback explícito (`--admin-auth otp` / Konecty antigo). Novo flag `--admin-auth {oauth,otp}` (default oauth); prompt de `client_id` (`claude-code-admin`) e `callback_port` (`19819`); +4 testes unitários |
| [2026-07-14](./2026-07-14_uvx-root-packaging.md) | **Fix do uvx**: `pyproject.toml` movido de `installer/` para a raiz do repo (fonte única; wheel aponta para `installer/src`) — o one-liner `uvx --from git+…` falhava por não achar packaging na raiz; v0.1.1 |
| [2026-07-13](./2026-07-13_mcp-first.md) | **MCP-first** (ADR-0006): skills viram guias sobre os servidores MCP do Konecty (`/mcp`, `/admin-mcp`) — zero scripts HTTP; nova skill `konecty-setup`; instalador registra MCP + OAuth no navegador; escopo `admin` OAuth para clientes confiáveis (konecty/Konecty#453); harness e2e reconstruído (cliente JSON-RPC stdlib, 39 casos, build do Konecty local); shared-files invariant dissolvido |
| [2026-06-17](./2026-06-17_konecty-dev-skill.md) | `konecty-dev` skill (3rd skill, first advisory): teaches developer-agents to write integration code — SDK-first (Python 2.0.3, Node/TS 1.0.0) + full REST track for other languages; lean SKILL.md + 8 references incl. hooks runtime contract; out of the shared-files invariant |
| [2026-06-17](./2026-06-17_e2e-harness.md) | E2E harness: `e2e/` dockerized stack (3.8.10, alt ports) + bootstrap scripts, `tests/e2e/` pseudo-agent + mock + 4 test suites (~473 tests), pytest.ini + .coveragerc, 10 `make e2e-*` targets — 93% coverage; konecty-meta mocked pending Konecty PR #299; konecty-data live/mock split |
| [2026-06-17](./2026-06-17_installer-cli.md) | `konecty-skills` CLI installer (`uvx`, stdlib only): engine detection, runtime skill download, OTP credential setup, SHA-256 manifest, colored banner — 128 unit tests |
| [2026-06-17](./2026-06-17_audit-exclude-agents-complexity-refactor.md) | Exclude `.agents/` from audits (ruff.toml + changed-since dot-dir filter); refactor `cmd_upload`/`cmd_apply` below CC 25 — intelligence gate FAIL→WARN |
| [2026-06-17](./2026-06-17_agents-md-bestpractices-make-skills.md) | AGENTS.md gains Read first / Commands / completion-gate sections; Makefile expanded; marketing/copywriting skills vendored |
| [2026-04-23](./2026-04-23_konecty-meta-remove-skill.md) | konecty-meta-remove skill: interactive full-module metadata deletion via `/api/admin/meta` |
| [2026-03-16](./2026-03-16_repo-initialization.md) | Repository initialization and base structure |
| [2026-03-16](./2026-03-16_adr-initialization.md) | ADR directory, template, and initial ADRs (0001–0003) |
| [2026-03-16](./2026-03-16_skill-creator-copy.md) | Copy of skill-creator from anthropics/skills for future skill creation |
| [2026-03-16](./2026-03-16_konecty-session-skill.md) | konecty-session skill: login and persist token in .env / ~/.konecty/credentials |
| [2026-03-16](./2026-03-16_konecty-session-otp-only.md) | konecty-session: OTP-only login, two-phase flow (request OTP → verify OTP), token validity |
| [2026-03-16](./2026-03-16_skill-creator-agents-example-removed.md) | skill-creator moved to agents/skills; example-skill removed |
| [2026-03-16](./2026-03-16_konecty-modules-skill.md) | konecty-modules skill: list accessible modules, fields, types via /rest/query/explorer/modules |
| [2026-03-16](./2026-03-16_konecty-find-skill.md) | konecty-find skill: search and query records with full filter/operator documentation and cross-module query support |
| [2026-03-16](./2026-03-16_konecty-create-skill.md) | konecty-create skill: create records with workflow for field discovery, lookup resolution, and picklist validation |
| [2026-03-16](./2026-03-16_konecty-update-skill.md) | konecty-update skill: update records enforcing fetch-first workflow to obtain _updatedAt before every PUT |
| [2026-03-16](./2026-03-16_konecty-delete-skill.md) | konecty-delete skill: delete one record at a time with preview + --confirm guardrails |
| [2026-03-16](./2026-03-16_konecty-meta-skills.md) | 10 konecty-meta skills: read, document, list, view, access, pivot, hook, namespace, doctor, sync |
