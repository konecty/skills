# skill-creator copied from anthropics/skills

## Summary
Copied the full **skill-creator** skill from [anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/skill-creator) into KonectySkills for use when creating and improving skills in the Konecty ecosystem.

## Motivation
Use the same workflow (draft → test → review → improve → description optimization) and tooling (eval viewer, scripts, agents) that Anthropic uses for skill creation, so future Konecty skills can be created and iterated with evals and benchmarks.

## What changed
- **skills/skill-creator/** added with:
  - `SKILL.md` — main skill instructions (create, run evals, improve, description optimization)
  - `agents/` — grader.md, comparator.md, analyzer.md (subagent instructions)
  - `assets/` — eval_review.html (trigger eval review UI)
  - `eval-viewer/` — generate_review.py, viewer.html (review UI and benchmark)
  - `references/` — schemas.md (JSON schemas for evals, grading, benchmark)
  - `scripts/` — aggregate_benchmark.py, generate_report.py, improve_description.py, package_skill.py, quick_validate.py, run_eval.py, run_loop.py, utils.py
  - `LICENSE.txt` — Apache License 2.0 (from upstream)
  - `NOTICE` — attribution to anthropics/skills and Apache 2.0

## Technical impact
- Python 3 and optional `claude` CLI are required for scripts (run_loop, run_eval, generate_review, etc.). Cursor/Claude Code users can use the skill for drafting and improving skills; full eval/benchmark flow may require subagents and environment as described in the skill.
- No changes to existing skills or template.

## How to validate
- Confirm `skills/skill-creator/` exists with SKILL.md, agents/, assets/, eval-viewer/, references/, scripts/, LICENSE.txt, NOTICE.
- Use the skill when asked to create or improve a skill (e.g. “use the skill-creator skill to create a new skill for X”).

## Files affected
- `skills/skill-creator/` (new — copied from upstream)
- `skills/skill-creator/NOTICE` (new — attribution)
- `README.md` (updated — mention skill-creator in structure table)
- `docs/changelog/README.md` (updated — new entry)
- `docs/changelog/2026-03-16_skill-creator-copy.md` (new)

## Migration
None.
