# ADR initialization

## Summary
Initialized Architecture Decision Records (ADR) in KonectySkills, aligned with the format used in ui and Konecty repos, with renumbered ADRs specific to this repository.

## Motivation
Provide a single place to record decisions about skill format, repository structure, and documentation standards, and keep consistency with the rest of the Konecty ecosystem.

## What changed
- **docs/adr/:** Added `README.md` (purpose, when to create, how to create, naming, index) and `template.md` (Context, Decision, Alternatives, Consequences, References).
- **ADR-0001:** Formato Agent Skills — adoption of SKILL.md + YAML frontmatter (name, description) and Markdown body per [agentskills.io](https://agentskills.io).
- **ADR-0002:** Estrutura do repositório — layout with `template/`, `spec/`, `skills/`, `docs/` (inspired by anthropics/skills).
- **ADR-0003:** Documentação e changelog obrigatórios — mandatory docs and changelog for repo-level changes; ADRs for architectural/standards decisions.

## Technical impact
- New or updated decisions affecting format, structure, or conventions should be documented with an ADR and/or changelog entry as per ADR-0003.

## How to validate
- Confirm `docs/adr/README.md`, `docs/adr/template.md`, and `docs/adr/0001-formato-agent-skills.md` through `0003-documentacao-changelog-obrigatorios.md` exist and are linked from docs and root README.

## Files affected
- `docs/adr/README.md` (new)
- `docs/adr/template.md` (new)
- `docs/adr/0001-formato-agent-skills.md` (new)
- `docs/adr/0002-estrutura-repositorio.md` (new)
- `docs/adr/0003-documentacao-changelog-obrigatorios.md` (new)
- `docs/README.md` (updated — ADR link)
- `README.md` (updated — ADR link)
- `docs/changelog/README.md` (updated — new entry)
- `docs/changelog/2026-03-16_adr-initialization.md` (new)

## Migration
None.
