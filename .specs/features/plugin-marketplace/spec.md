# Feature: Distribute skills as a Claude Code plugin + marketplace

Status: in progress
Scope: Medium (additive packaging only, no code/skill-content changes)
Owner: Leonardo Viva

## Problem

Today the only ways to get the Konecty skills into Claude Code are (1) the `uvx`
installer (`konecty-skills install`), which requires a terminal and `uv`, and (2)
manually copying skill folders. Non-technical customers have no UI-only path.

Claude Code's native plugin system lets users add a marketplace and install a plugin
entirely from the `/plugin` UI — no shell. Packaging the 4 skills as a plugin hosted in
THIS repo gives customers that path.

## Goal

A plugin + marketplace hosted in this repo, installable via
`/plugin marketplace add konecty/skills` → `/plugin` → install, bundling the 4 skills
(`konecty-data`, `konecty-meta`, `konecty-setup`, `konecty-dev`).

## Design constraints (MUST honor)

1. **No hardcoded MCP server.** The plugin bundles the 4 SKILLS ONLY. It MUST NOT ship an
   `mcpServers` entry. MCP registration is per-company (each customer has a different
   Konecty URL) and is handled conversationally by the `konecty-setup` skill after
   install. The plugin manifest schema makes `mcpServers` optional — a plugin can ship
   skills alone — so omitting it is valid and intentional. Baking a URL in would be wrong
   for every customer but the one it was built for.
2. **Repo root doubles as the plugin root.** The skills already live in `skills/`, which
   is the plugin system's default skills location. `marketplace.json` lists ONE plugin
   whose `source` is the marketplace root (`"./"`). Skills are discovered from `skills/`.
3. **Additive only.** Nothing about the existing `uvx` installer or the skills' content
   changes. This adds two manifest files, README docs, and a changelog entry.

## Design (verified against docs)

Schema confirmed against the official Claude Code docs (2026-07):
- https://code.claude.com/docs/en/plugins-reference.md (plugin.json + marketplace entry schema)
- https://code.claude.com/docs/en/plugin-marketplaces.md (marketplace.json schema, relative-path sources)
- https://code.claude.com/docs/en/discover-plugins.md (add-marketplace + install flow)

Files (both at repo root, inside `.claude-plugin/`):

- `.claude-plugin/marketplace.json` — marketplace catalog. Fields: `name`, `owner`,
  `plugins[]`. The single plugin entry uses `source: "./"` (relative path resolving to the
  marketplace/repo root) and `skills: ["./skills/"]` — per docs, listing `./skills/`
  under a marketplace-root source keeps the full scan of all 4 skill subdirectories.
- `.claude-plugin/plugin.json` — plugin manifest. `name: konecty-crm`, `version: 0.1.1`
  (aligned with the repo package version), `description`, `displayName`, `author`,
  `homepage`, `repository`, `license`, `keywords`. No `mcpServers` field (constraint #1).

Only documented fields are used; no invented fields.

## Acceptance Criteria

- **AC1** — WHEN a user runs `/plugin marketplace add konecty/skills` THEN Claude Code
  SHALL discover a valid marketplace manifest at `.claude-plugin/marketplace.json`.
- **AC2** — WHEN the user installs the plugin from `/plugin` THEN the 4 skills SHALL become
  available (namespaced `konecty-crm:<skill>`) with no shell commands.
- **AC3** — WHEN installed THEN invoking `konecty-setup` SHALL guide MCP registration for
  the user's company URL (unchanged behavior) — the plugin does not and need not carry a
  server URL.
- **AC4** — The manifest(s) SHALL validate against the documented schema (valid JSON,
  required fields present, skill paths resolve, no invented fields).

## Verification

Cannot run the interactive `/plugin` UI in this environment. Verification is:
- `python3 -m json.tool` parses both manifests (valid JSON). [AC4]
- Required fields present: marketplace `name`/`owner`/`plugins[]`; plugin `name`. [AC4]
- `source: "./"` + `skills: ["./skills/"]` resolve to the 4 existing skill dirs, each with
  a valid `SKILL.md`. [AC1, AC2]
- `mcpServers` absent from `plugin.json` — grep confirms. [AC3, constraint #1]
- `konecty-setup/SKILL.md` unchanged (git shows no diff under `skills/`). [AC3]
- `make validate` still passes for the two published skills (known `gh skill` env quirk
  "name does not match directory '.'" ignored). [additive-only]

## Out of scope

- Publishing to the Anthropic official/community marketplace (curated, separate PR).
- Any change to the `uvx` installer, skill scripts, or skill content.
- Automating MCP registration inside the plugin (deliberately left to `konecty-setup`).
