# Development & contributing

## Adding a new skill

1. Create a new folder under `skills/` with a short, lowercase name (e.g. `skills/my-new-skill/`).
2. Add `SKILL.md` inside that folder. Use [template/SKILL.md](../template/SKILL.md) as reference:
   - YAML frontmatter with `name` and `description`.
   - Markdown body with instructions, examples, and guidelines.
3. Optionally add other files (scripts, configs) in the same folder and reference them from `SKILL.md`.
4. Document the change in [changelog](./changelog/README.md).

## Skill format

- **name:** Unique identifier, lowercase, hyphens for spaces. Used by the agent to identify the skill.
- **description:** Plain-language description of what the skill does and **when** the agent should use it. This is used for skill selection; be specific.

## Using skills in Cursor

To use KonectySkills from this repo in Cursor:

- Copy or symlink the desired skill folders (e.g. `skills/codigo-limpo`) into your project’s `.cursor/skills/` (or your configured skills path).
- Or reference this repo as a plugin source if your environment supports it.

## Changelog

Every change that affects users or other repos should have an entry in `docs/changelog/YYYY-MM-DD_slug.md` and be listed in `docs/changelog/README.md`.
