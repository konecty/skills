<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo-horizontal-white.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/logo-horizontal-color.png">
  <img alt="Konecty" src="docs/logo-horizontal-color.png" width="300">
</picture>

# KonectySkills

> **Install, inform your company URL, log in via browser — and talk to your CRM.**

MCP-first skills for AI agents like Claude Code. Execution happens on **Konecty's own
MCP servers** (`/mcp` and `/admin-mcp`); the skills teach the agent how to use them
correctly — which tool to call, in which order, with which guardrails. No local HTTP
scripts, no `.env` editing.

[![Known Vulnerabilities](https://snyk.io/test/github/konecty/skills/badge.svg)](https://snyk.io/test/github/konecty/skills)
[![agentskills.io](https://img.shields.io/badge/agentskills.io-compatible-6366f1?style=flat-square)](https://agentskills.io)
[![skills.sh](https://img.shields.io/badge/skills.sh-compatible-6366f1?style=flat-square)](https://skills.sh)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue?style=flat-square)](./LICENSE)

**[🇧🇷 Versão em Português →](./README.md)**

---

## Quick install

```bash
uvx --from git+https://github.com/konecty/skills konecty-skills install
```

The installer asks for your company's Konecty URL, validates it (`https` + the
`/.well-known/oauth-protected-resource` probe), registers the `konecty` MCP server
(`<url>/mcp`, user scope in Claude Code), offers the admin path, and copies the 4
skills. On first use, Claude Code opens the browser for the OAuth login — done:

> "what open opportunities does client X have?"

**Prerequisites:**

- Python 3.9+ and `uv` (`pip install uv` or `brew install uv`)
- A Konecty deployment with MCP enabled (see [Server requirements](#konecty-server-requirements))
- Claude Code (without the `claude` CLI, the installer prints the exact `claude mcp add` commands for manual execution)

### Installer commands

| Command | What it does |
|---------|--------------|
| `install` | URL → validate → register the `konecty` MCP server → optional admin path (OTP → `konecty-admin` entry with Bearer header) → copy the 4 skills |
| `configure` | Interim admin token only: OTP login → `~/.konecty/.env` + `konecty-admin` MCP entry |
| `status` | Installed skills, engines, MCP registration, admin-token presence |
| `update` | Re-fetch skills with SHA-256 protection (never overwrites local edits) |
| `doctor` | URL reachable, well-known + audience match (`PLATFORM_MCP_RESOURCE_URL`), MCP servers registered, admin token validity |
| `uninstall` | Remove the skills (`--purge` also removes credentials and MCP entries) |

Re-running `install` is idempotent: existing `konecty*` entries are replaced
(remove + add), never duplicated; pre-existing user files are never touched.

### Conversational setup

Prefer doing everything inside Claude Code? The **konecty-setup** skill covers the
same flow conversationally: first setup, switching company/URL, re-authentication,
and enablement troubleshooting ("set up konecty", "connect my CRM").

---

## The four skills

| Skill | MCP server | What it teaches |
|-------|------------|-----------------|
| **konecty-data** | `konecty` (`/mcp`) | CRM data conversations: module/field discovery, search with validated filters (`filter_build`), cross-module queries (`query_json`), create, fetch-first update (`_updatedAt`), delete with preview + confirmation, files |
| **konecty-meta** | `konecty-admin` (`/admin-mcp`) | Metadata administration: document schemas, lists, views, access profiles, pivots, hooks (validate → upsert), Namespace (incl. MCP flags), doctor, and repo↔database sync |
| **konecty-setup** | — | Conversational setup/reconfiguration of the MCP servers; troubleshooting matrix |
| **konecty-dev** | — *(advisory)* | Konecty integration code: official SDKs (Python/TS), REST API, hooks, recipes |

The skills **execute no HTTP** — they name the MCP tools (`records_find`,
`query_json`, `meta_document_upsert`, …) and Konecty executes.

---

## Authentication

- **User (`konecty`)**: Claude Code's native OAuth — DCR → authorize + PKCE → token,
  all in the browser. Scopes `read` (+ `write` when the namespace enables
  `mcpUserWriteEnabled`).
- **Admin (`konecty-admin`), interim path**: OTP login → `authTokenId` registered as
  an `Authorization: Bearer` header on the MCP entry. When it expires, `konecty-setup`
  guides the re-login.
- **Admin, target path (OAuth)**: Konecty grants the `admin` scope at consent for
  **trusted clients** (provisioned via `OAUTH_CLIENTS_JSON`;
  [konecty/Konecty#453](https://github.com/konecty/Konecty/pull/453)) when the user has
  `admin: true`. Switching is a re-registration only — nothing in the skills changes.

---

## Konecty server requirements

Your company's Konecty must expose the MCP servers (a release shipping
`/mcp` + `/admin-mcp`) and enable, on the **Namespace**:

| Flag | Effect |
|------|--------|
| `mcpUserEnabled` | Enables `/mcp` (503 when off) |
| `mcpAdminEnabled` | Enables `/admin-mcp` |
| `mcpRoleIds` | Role allowlist for MCP access — **deny-by-default** (403 `mcp_access_denied` when empty) |
| `mcpUserWriteEnabled` | Writes over MCP (default: read-only — writes return `insufficient_scope`) |

Deployment: `PLATFORM_MCP_RESOURCE_URL` must be exactly the public `/mcp` URL (OAuth
token audience validation). Konecty instances **without MCP** are not supported by
this version — pin the last script-based tag of this repository.

---

## E2E testing

The e2e suite boots a disposable Konecty stack **built from local source** (a
`../Konecty` worktree) and drives the documented MCP tools with a stdlib JSON-RPC
client — every flow the skills describe has ≥1 case (find, query, create, update,
delete preview+confirm, upload, OTP, meta read/upserts/hook/doctor/sync, guard errors,
and the OAuth scenarios including the trusted-client admin scope).

```bash
make e2e   # purge → build+up → wait → bootstrap MCP flags → suites → purge
```

**Prerequisites:** Docker, `uv`, Node 24 + Yarn (dist build), and the Konecty repo
cloned at `../Konecty`.

| Target | What it does |
|--------|--------------|
| `make e2e` | Full self-contained cycle (always tears the stack down) |
| `make e2e-src` | Creates the `e2e/.konecty-src` worktree and builds `dist/` |
| `make e2e-up` | Image build + stack up + wait + MCP flags bootstrap |
| `make e2e-down` / `e2e-reset` | Stop the stack (reset drops volumes — fresh admin next boot) |
| `make e2e-token` | Extract the admin token from container logs |
| `make e2e-run` | Run the suites against an already-running stack |

---

## Repository layout

```
skills/              # The 4 skills (one folder per skill: SKILL.md + references/)
├── konecty-data/    # User-MCP guide (data)
├── konecty-meta/    # Admin-MCP guide (metadata)
├── konecty-setup/   # Conversational setup + troubleshooting
└── konecty-dev/     # Advisory: SDKs, REST API, hooks, recipes
installer/           # konecty-skills CLI (Python stdlib, uvx entry point)
e2e/                 # Docker stack (compose + bootstrap) for the e2e tests
tests/e2e/           # E2E suites (stdlib MCP client + pytest)
.specs/              # SDD specs: project, codebase analysis, features
template/            # Template for new skills
spec/                # Agent Skills standard reference
docs/                # Documentation, ADRs, and changelog
```

---

## Development

```bash
make help            # list all targets
make setup           # point git at .githooks (once after cloning)
make check           # offline gate: py_compile + installer tests
make validate        # gh skill publish --dry-run (validates SKILL.md)
make audit           # codebase-intelligence + codebase-security (PR gate)
make e2e             # full e2e cycle
```

### Creating a new skill

1. Create a folder under `skills/` with a short lowercase name.
2. Add `SKILL.md` with YAML frontmatter (`name` + `description`) and Markdown instructions.
3. Skills are **procedural guides** — execution stays on Konecty's MCP servers. If a
   capability is missing from the MCP, the gap becomes an upstream Konecty feature,
   never a local script (ADR).
4. Document the change in `docs/changelog/YYYY-MM-DD_slug.md`.

See [template/SKILL.md](./template/SKILL.md) and follow the **skill-creator** workflow.

### Completion gate (before any PR)

```bash
make check   # offline verification
make audit   # intelligence + security (a fail verdict blocks the PR)
```

---

## Publishing to marketplaces

```bash
make publish VERSION=1.2.0 CHANGELOG="What changed"   # all marketplaces
make publish-gh       VERSION=1.2.0                    # GitHub via gh skill
make publish-clawhub  VERSION=1.2.0 CHANGELOG="..."    # OpenClaw
make publish-hermes                                    # Hermes (NousResearch)
```

Skills appear organically on [skills.sh](https://skills.sh) once the repository is
public with a valid `SKILL.md` (`npx skills add konecty/skills`). Anthropic/skills and
tech-leads-club are curated via Pull Request.

---

## Security

- Installer and e2e suite use **Python stdlib only** — no third-party dependencies.
- The skills contain no executable code: `grep -rE "urllib|http.client" skills/konecty-data skills/konecty-meta` → empty.
- Audits: Snyk (badge above), Socket (supply chain), and Gen Agent Trust Hub
  ([ai.gendigital.com/agent-trust-hub](https://ai.gendigital.com/agent-trust-hub)).

---

## Documentation

- [Architecture Decision Records (ADR)](./docs/adr/README.md)
- [Changelog](./docs/changelog/README.md)
- [🇧🇷 Versão em Português](./README.md)

---

## License

This project is licensed under the **GNU Affero General Public License v3.0
(AGPL-3.0)**. See [`LICENSE`](./LICENSE) for the full text.

Built with ❤️ by the [Konecty](https://konecty.com) team.
