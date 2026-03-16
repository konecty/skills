# Agent Skills specification

The Agent Skills format used in this repository follows the standard described at:

- **Specification:** [agentskills.io](https://agentskills.io)
- **Reference implementation:** [anthropics/skills](https://github.com/anthropics/skills)

Each skill is a folder containing at least a `SKILL.md` file with:

1. **YAML frontmatter** with `name` and `description`.
2. **Markdown body** with instructions, examples, and guidelines for the agent.

Optional assets (scripts, configs, other files) may live in the same folder and be referenced from `SKILL.md`.
