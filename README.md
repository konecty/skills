# KonectySkills

Repository of **Agent Skills** for Konecty ecosystem. Skills are folders of instructions and resources that AI agents (e.g. Cursor, Claude Code) load dynamically to perform specialized tasks in a repeatable way.

For the Agent Skills standard, see [agentskills.io](https://agentskills.io). This repo is inspired by [anthropics/skills](https://github.com/anthropics/skills).

## Structure

| Path | Purpose |
|------|---------|
| [./skills](./skills) | Konecty skills (each skill in its own folder with `SKILL.md`). Includes [skill-creator](./skills/skill-creator) (from [anthropics/skills](https://github.com/anthropics/skills)) and [konecty-session](./skills/konecty-session) (login and persist token for other skills). |
| [./template](./template) | Template for creating new skills |
| [./spec](./spec) | Reference to the Agent Skills specification |
| [./docs](./docs) | Project documentation and changelog |

## Creating a skill

1. Copy the [template](./template) folder or create a new folder under `skills/`.
2. Add a `SKILL.md` with YAML frontmatter and instructions:

```markdown
---
name: my-skill-name
description: A clear description of what this skill does and when to use it.
---

# My Skill Name

Instructions the agent will follow when this skill is active.

## Examples
- Example usage 1
- Example usage 2

## Guidelines
- Guideline 1
- Guideline 2
```

**Frontmatter (required):**
- `name` — Unique identifier (lowercase, hyphens for spaces).
- `description` — What the skill does and when the agent should use it.

The rest of the file is Markdown: instructions, examples, and guidelines.

## Using skills in Cursor

Skills in this repo can be installed under `.cursor/skills/` (or your Cursor skills path). Each skill is a folder containing `SKILL.md`; the agent uses the `description` to decide when to load the skill.

## Documentation

- [Contributing & development](./docs/development.md)
- [Architecture Decision Records (ADR)](./docs/adr/README.md)
- [Changelog](./docs/changelog/README.md)
