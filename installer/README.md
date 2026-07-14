# konecty-skills

One-command installer for the [Konecty](https://github.com/konecty/skills) Agent Skills
(`konecty-data`, `konecty-meta`, `konecty-setup`, `konecty-dev`). Informs your company's
Konecty URL, registers Konecty's own MCP servers in Claude Code (`konecty` at `/mcp`,
`konecty-admin` at `/admin-mcp`), and copies the skills — without ever deleting or
modifying your existing files. Log in via the browser (OAuth) and talk to your CRM.

```bash
uvx --from git+https://github.com/konecty/skills konecty-skills install
```

## Commands

| Command | What it does |
|---------|--------------|
| `install` | Prompt the company URL → validate (https + MCP well-known probe) → register the `konecty` MCP server (user scope) → optional admin path (OTP → `konecty-admin` entry with Bearer header) → copy the 4 skills → write manifest |
| `configure` | Interim admin token only: OTP login → `~/.konecty/.env` + `konecty-admin` MCP entry |
| `status` | Installed skills, engines, MCP registration, and admin-token presence |
| `update` | Re-fetch skills with SHA-256 protection (never overwrites local edits) |
| `doctor` | URL reachable, MCP well-known + audience match (`PLATFORM_MCP_RESOURCE_URL`), MCP servers registered, admin token validity |
| `uninstall` | Remove the installed skills (`--purge` also removes credentials and the MCP entries) |

Notes:

- Re-running `install` is idempotent: existing `konecty`/`konecty-admin` entries are
  **replaced** (remove + add), never duplicated; pre-existing user files are never touched.
- If the `claude` CLI is not installed, the exact `claude mcp add` commands are printed
  for manual execution instead of failing.
- User authentication is OAuth handled natively by Claude Code (browser login on first
  use). `~/.konecty/.env` only stores the **interim admin token** for the `konecty-admin`
  server; once your Konecty supports admin OAuth (trusted clients), switching is a
  re-registration only — see the `konecty-setup` skill.
- Konecty instances without MCP support (well-known 404) are not supported by this
  version — pin the last script-based release tag instead.

Stdlib only — no third-party runtime dependencies.
