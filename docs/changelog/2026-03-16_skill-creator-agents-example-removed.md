# skill-creator moved to agents/skills, example-skill removed

## Summary
skill-creator was moved from `skills/skill-creator` to `agents/skills/skill-creator` so it lives with external/reference skills rather than Konecty project skills. example-skill was removed from the repository.

## Motivation
skill-creator is from anthropics/skills and is not a Konecty product skill; it belongs in a separate area (agents/skills). example-skill was only a placeholder and is no longer needed.

## What changed
- **agents/skills/** created; **skill-creator** moved from `skills/skill-creator` to `agents/skills/skill-creator` (git mv to preserve history).
- **skills/example-skill** removed from the repo.
- **README.md:** structure table updated: `skills/` for Konecty project skills (e.g. konecty-session); `agents/skills/` for external/reference skills (e.g. skill-creator).
- **docs/adr/0002-estrutura-repositorio.md:** structure diagram and bullets updated to include `agents/skills/` and to describe skills/ vs agents/skills.

## How to validate
- `agents/skills/skill-creator/` exists with SKILL.md, agents/, scripts/, etc.
- `skills/` contains only konecty-session (and future Konecty skills).
- `skills/example-skill` no longer exists.

## Files affected
- README.md
- docs/adr/0002-estrutura-repositorio.md
- docs/changelog/README.md
- docs/changelog/2026-03-16_skill-creator-agents-example-removed.md (new)
- skills/skill-creator/ → agents/skills/skill-creator/ (moved)
- skills/example-skill/ (removed)
