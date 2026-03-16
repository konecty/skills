# Repository initialization

## Summary
Initialized KonectySkills repository with structure inspired by [anthropics/skills](https://github.com/anthropics/skills).

## Motivation
Enable creation and maintenance of multiple Agent Skills for the Konecty ecosystem in a single, versioned repo.

## What changed
- **Root:** `README.md`, `.gitignore`.
- **template/** — `SKILL.md` template for new skills (YAML frontmatter + sections).
- **spec/** — `README.md` pointing to Agent Skills spec (agentskills.io).
- **skills/** — Empty directory (`.gitkeep`) ready for skill folders.
- **docs/** — `README.md`, `development.md`, changelog with this entry.

## Technical impact
- No runtime dependencies; skills are Markdown + optional assets.
- Compatible with Cursor and other agents that support the Agent Skills format.

## How to validate
- Clone repo and confirm `README.md`, `template/SKILL.md`, `spec/README.md`, `skills/.gitkeep`, and `docs/` files exist.
- Use `template/SKILL.md` as base to add a new skill under `skills/`.

## Files affected
- `README.md` (new)
- `.gitignore` (new)
- `template/SKILL.md` (new)
- `spec/README.md` (new)
- `skills/.gitkeep` (new)
- `docs/README.md` (new)
- `docs/development.md` (new)
- `docs/changelog/README.md` (new)
- `docs/changelog/2026-03-16_repo-initialization.md` (new)

## Migration
None.
