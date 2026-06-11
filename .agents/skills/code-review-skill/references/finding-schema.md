# Finding Schema & Review State

This is the data contract of the entire skill. Reviewers emit findings in this exact shape; scripts consolidate and mutate state; the orchestrator only reads.

## Finding object

Every reviewer (LLM or script) returns a JSON array of these objects. No prose outside the JSON.

```json
{
  "origin": "security | requirements | tests | architecture | regression | performance",
  "source": "llm | script",
  "severity": "critical | security | performance | warning | suggestion",
  "title": "Short imperative title (max ~10 words)",
  "file": "src/path/to/file.ts",
  "line_start": 42,
  "line_end": 45,
  "evidence": "the exact offending line(s) quoted from the diff",
  "description": "What is wrong and WHY it matters. 1-3 sentences.",
  "recommendation": "Specific, actionable fix. Code sketch allowed if < 6 lines.",
  "confidence": 0.9,
  "rule_ref": "optional — doc + rule that backs the finding, e.g. 'CONVENTIONS.md — Repository Pattern'",
  "requirement_ref": "optional — requirement/task ID from spec.md or Konecty task, used by the requirements reviewer"
}
```

Field rules:

- `file`/`line_*` must point at `+` lines of the diff. PR-level findings (e.g. "requirement R3 not implemented anywhere") use `"file": null` and `"line_start": null`.
- `severity` mapping: 🚨 `critical` (bugs/logic errors that will cause failures) · 🔒 `security` · ⚡ `performance` · ⚠️ `warning` (maintainability/code smell) · 💡 `suggestion` (optional improvement).
- `confidence` < 0.8 → do not emit the finding at all (LLM reviewers). Script findings always use 1.0.
- `evidence` is mandatory for line-anchored findings — a finding without quoted evidence is not actionable.

## Fields added by consolidation (never by reviewers)

```json
{
  "id": "SEC-001",
  "status": "open",
  "fix_attempts": 0,
  "requires_human": false,
  "duplicate_of": null,
  "merged_origins": ["security", "performance"],
  "fix_induced": false,
  "notes": []
}
```

- `id` — `{PREFIX}-{NNN}` per origin: `SEC` security · `REQ` requirements · `TST` tests · `ARQ` architecture · `REG` regression · `PRF` performance. Sequential per origin, assigned once, **never reassigned or reused** within a session.
- `fix_induced: true` — finding discovered during a re-review that was introduced by a correction. Gets a fresh ID and a fresh counter, and is flagged loudly in the report.

## Status machine (per finding)

```
open ──(user accepts)──→ accepted ──(corrector)──→ fixed ──(re-review ok)──→ verified
  │                          │                        │
  │                          │                        └─(re-review fails)→ reopened
  │                          └─(corrector can't decide)→ escalated            │
  └─(user skips)→ dismissed                                                   │
                                          reopened ──(fix_attempts < 2)──→ accepted (next round)
                                          reopened ──(fix_attempts ≥ 2)──→ escalated (frozen)
```

- `fix_attempts` increments each time a finding goes through a fix + re-review cycle.
- A finding at `fix_attempts = 2` that is still `reopened` is **frozen**: status → `escalated`, never auto-corrected again. The report tells the user exactly which findings hit the wall and why.
- The **first** re-review of a session runs as a batch over everything fixed; from then on, cycle tracking is strictly per finding — finding A may be `verified` while finding B is on its last attempt.

Terminal states: `verified`, `escalated`, `dismissed`. Session ends when every finding is terminal.

## review-state.json

Single source of truth, mutated only by `scripts/review-state.sh`. The orchestrator reads it; LLM subagents never see it.

```json
{
  "session_id": "cr-2026-06-11-a1b2",
  "created_at": "ISO-8601",
  "cycle": 0,
  "pr": { "branch": "...", "base": "...", "title": "...", "number": null },
  "context": {
    "spec_path": ".specs/features/recommendations-v2/",
    "spec_kind": "feature | quick | manual",
    "codebase_docs": ["STACK.md", "TESTING.md"],
    "konecty_task": { "found": true, "summary": "..." },
    "stack": { "language": "typescript", "package_manager": "pnpm",
               "test_cmd": "pnpm test", "coverage_cmd": "pnpm test -- --coverage",
               "coverage_threshold": 80 },
    "degraded": ["architecture: no CONVENTIONS.md — generic criteria"]
  },
  "findings": [ /* consolidated finding objects */ ],
  "history": [ { "ts": "...", "event": "accept | record-fix | scope | escalate", "detail": "..." } ]
}
```

## Inline marker (GitHub-ready)

Every rendered finding carries `<!-- code-review:{origin}:{id} -->` as its first line. Invisible in rendered markdown; in the future GitHub mode it becomes the dedup/threading key for PR inline comments — same data, different transport.
