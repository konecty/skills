# Claude Code plugin + marketplace

**Date:** 2026-07-14
**Type:** feat (packaging, additive)

## Problem

The only install paths were the `uvx` installer (needs a terminal + `uv`) and manually
copying skill folders. Non-technical customers had no UI-only path into Claude Code.

## Change

- `.claude-plugin/marketplace.json` — marketplace catalog (name `konecty`) listing one
  plugin whose `source` is the repo root (`"./"`) with `skills: ["./skills/"]`, so all 4
  skills load via the default `skills/` scan.
- `.claude-plugin/plugin.json` — plugin `konecty-crm` v0.1.1 (aligned with the package),
  metadata only. **No `mcpServers` entry**: MCP registration is per-company (different
  Konecty URL per customer) and stays conversational via `konecty-setup` after install.
- README.md / README.en.md — new "Instalação via plugin (sem terminal)" /
  "Install via plugin (no terminal)" section: `/plugin marketplace add konecty/skills` →
  `/plugin` → install, then tell Claude your Konecty URL.
- `.specs/features/plugin-marketplace/spec.md` — feature spec.

Additive only: no change to the `uvx` installer or any skill content. Only documented
plugin-schema fields used; validated with `claude plugin validate`.

## Verification

- `python3 -m json.tool` parses both manifests; required fields present.
- `claude plugin validate` → "Validation passed".
- `source "./"` + `skills ["./skills/"]` resolve to the 4 existing skill dirs, each with a
  valid `SKILL.md`; `grep` confirms no `mcpServers` in `plugin.json`.
