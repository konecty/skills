---
name: code-review
description: Full multi-agent code review of a finished PR against its spec (.specs/ from tlc-spec-driven) and Konecty-hub task. Orchestrates 6 specialized reviewers (security, requirements, tests, architecture, regression/hallucination, performance), consolidates findings into a single report with stable IDs, lets the user select which findings to fix, dispatches correction subagents, and re-reviews only what was fixed. Use when the user types "/code-review", asks to "review this PR", "review PR #N", "code review", "revisar o PR", or wants a quality gate before merge. Do NOT trigger during normal coding or feature implementation.
license: CC-BY-4.0
metadata:
  author: Tiago / Konecty
  version: 0.1.0
---

# Code Review — Orchestration Protocol

Complete review of a finished PR. The complexity of the PR does not change the flow: **all 6 reviewers always run**, from small to large changes.

**Design principles:**
- **Script where determinism is possible, LLM where interpretation is required.** Scripts produce findings with confidence 1.0; LLM reviewers apply a ≥80% confidence filter.
- **Reviewers report findings only.** They never write to files, never post comments, never fix anything. Output is structured JSON (see `references/finding-schema.md`).
- **Stack-agnostic.** Scripts discover or ask — never assume npm/pip/bundler. Commands come from `.specs/codebase/` docs, detection, or the user.
- **State lives in a file, not in the model.** `review-state.json` is the single source of truth for finding status and re-review counters. Scripts mutate it; the orchestrator only reads it.

```
/code-review
  → [SH]  collect-context.sh          context.json + missing[]
  → [LLM] Context Readiness Gate      fallback: ask user only for what's missing
  → [LLM ×4 + HYBRID ×2] reviewers    parallel, findings JSON only
  → [SH]  consolidate.sh              dedup, stable IDs, severity, gaps, render
  → [LLM] orchestrator                semantic polish + present report
  → user selects findings to fix
  → [SH]  review-state.sh accept      mark accepted findings
  → [LLM ×N] correctors               one per origin reviewer with accepted findings
  → [SH]  review-state.sh scope       compute scoped re-review, enforce limits
  → [LLM] scoped re-review            only affected reviewers, only touched files
  → loop (per-finding counter, max 2)
```

---

## Phase 1 — Context Collection

Run `scripts/collect-context.sh`. It gathers and emits `context.json`:

1. **PR data + diff** — `git diff` against the base branch (or `gh pr diff` when available), PR title/body/branch.
2. **Spec** — locate `.specs/features/[feature]/` (spec.md, design.md, tasks.md, context.md) or `.specs/quick/NNN-slug/` matching the branch/feature name.
3. **Codebase docs** — list available files in `.specs/codebase/` (STACK.md, ARCHITECTURE.md, CONVENTIONS.md, TESTING.md, etc.).
4. **Konecty-hub task** — fetch the general task description (integration hook; see `scripts/SCRIPTS.md`).
5. **Stack detection** — language, package manager, test command, coverage command. Prefer `.specs/codebase/STACK.md` and `TESTING.md`; fall back to lockfile/manifest detection.

The user may pre-supply any of this in the invocation (e.g. `/code-review PR 42, task: <description>`). Pre-supplied data wins; the script fills the rest.

### Context Readiness Gate

Inspect `context.json.missing[]` and classify each gap:

| Class | Sources | If missing |
|---|---|---|
| **Blocking** | diff / PR | STOP. Ask the user to point to the branch/PR or paste the diff. No review without a diff. |
| **Critical (manual fallback)** | spec (`.specs/features` or `.specs/quick`) AND Konecty task | Ask the user to provide the task **in structured form**: short description + acceptance criteria (bullet list). Free text is acceptable but restate it as criteria and confirm. |
| **Degradable (warn)** | `.specs/codebase/` docs, test/coverage commands | Inform which reviewers lose precision (Architecture and Performance run with generic criteria; Tests script may be skipped). Offer manual input or proceed with the warning recorded in the report. |

Present a compact context map before proceeding: ✅ found / ⚠️ missing → action taken. Only ask about what is missing — never re-ask what was found or pre-supplied.

When the gate passes, initialize state: `scripts/review-state.sh init`.

---

## Phase 2 — Parallel Review

Send **one message** with all reviewer Task calls launched simultaneously.

| # | Reviewer | Mode | Reference |
|---|---|---|---|
| 1 | Security | Hybrid: `scripts/security-scan.sh` + LLM | `references/reviewer-security.md` |
| 2 | Requirements & DoD | LLM | `references/reviewer-requirements.md` |
| 3 | Tests & Coverage | Hybrid: `scripts/run-tests.sh` + LLM | `references/reviewer-tests.md` |
| 4 | Architecture & Patterns | LLM | `references/reviewer-architecture.md` |
| 5 | Regression & Hallucination | LLM | `references/reviewer-regression.md` |
| 6 | Performance | LLM | `references/reviewer-performance.md` |

For the hybrid reviewers, run the script **first** and pass its JSON output into the subagent prompt — the LLM must not re-verify what the script already settled.

**Each reviewer subagent receives (and nothing more):**
- Its own reference file content
- The diff
- The slice of context its reference file declares (spec for #2, codebase docs for #4 and #6, script output for #1 and #3)
- The finding JSON contract from `references/finding-schema.md`

**Each reviewer subagent does NOT receive:** other reviewers' instructions or output, chat history, the full `.specs/` tree, or `review-state.json`.

**Each reviewer returns:** a JSON array of findings — errors only, no positive commentary, no prose outside the JSON. An empty array is a valid and expected result.

### Universal reviewer rules

1. Findings may only point at lines **added in the diff** (`+` lines, excluding `+++`).
2. LLM findings require **≥80% confidence**; when uncertain, omit. Script findings carry confidence 1.0.
3. Never approve, request changes, modify files, or post anything. Report findings; nothing else.
4. Every finding states **why** it is a problem and a specific, actionable recommendation.
5. Stay inside your declared scope. Adjacent problems belong to another reviewer — do not duplicate their work.

---

## Phase 3 — Consolidation

Run `scripts/consolidate.sh` over the 6 finding arrays. It performs the deterministic work:

- Deduplicate findings at the same `{file, line ±3}` (keep both origins on the surviving entry)
- Assign **stable IDs**: `{ORIGIN}-{NNN}` (e.g. `SEC-001`, `ARQ-003`) — these IDs persist for the whole session and drive selection, correction, and re-review counters
- Group by severity: 🔒 Security → 🚨 Critical → ⚡ Performance → ⚠️ Warning → 💡 Suggestion
- **Gap detection**: changed files with zero findings from any reviewer → listed for manual attention (config/lock/pure-type files exempt)
- Render the report skeleton (markdown)

Then apply the **orchestrator polish pass** — see `references/consolidation.md`: semantic dedup the script can't do, executive summary, and the code markers. Each finding is rendered with the snippet of the offending code plus an inline-comment-ready marker (`<!-- code-review:{origin}:{id} -->`), so the same structure maps 1:1 to GitHub inline comments in the future GitHub-Action mode.

Present the report. Then offer the fix step: fix **all**, fix a **selection** (by ID or by severity — e.g. "fix all critical, ignore suggestions"), or stop here.

---

## Phase 4 — User Selection

Record the decision: `scripts/review-state.sh accept <IDs|--severity critical,security|--all>`. Findings not accepted are marked `dismissed` and never re-surface unless the user asks.

---

## Phase 5 — Correction

Dispatch **one correction subagent per origin reviewer that has accepted findings** (e.g. 3 accepted findings from Requirements → 1 corrector fixes all 3; accepted findings from 4 reviewers → 4 correctors). Correctors for independent origins run in parallel; if two correctors would touch the same file, run them sequentially.

Each corrector receives: its findings (full JSON), the diff hunks involved, the relevant `.specs/` slices its findings reference, and the rules in `references/correction.md`.

**Authority boundary (non-negotiable):** correctors fix only mechanical issues with a single correct answer. Anything involving a design choice, public contract change, business behavior, or a suspected false positive is **escalated to the user**, never forced. See `references/correction.md`.

Each corrector returns per finding: `fixed` (with files touched) | `escalated` (with reason). Record results: `scripts/review-state.sh record-fix ...`.

---

## Phase 6 — Scoped Re-review

Run `scripts/review-state.sh scope`. It computes, from state alone:

- **Which reviewers re-run**: only those whose findings were fixed
- **Which files/lines they inspect**: only what the correctors touched
- **Counters**: increments `fix_attempts` per finding; any finding that already failed verification twice is **frozen and escalated** — no third attempt, ever

Re-run the scoped reviewers (same references, same rules, scoped input). Outcomes per finding:

- **Fixed confirmed** → mark `verified`
- **Still present** → `reopened`; eligible for one more correction round only if `fix_attempts < 2`
- **NEW finding introduced by a fix** → report it to the user immediately and explicitly, labeled as fix-induced; it enters the report as a new finding with its own fresh ID and counter

The first re-review covers the whole corrected batch; from the second cycle on, tracking is **per finding** — different findings may be in different cycles simultaneously. When every accepted finding is `verified`, `escalated`, or `dismissed`, the session is complete: present the final state summary.

---

## Local vs GitHub execution

This skill currently targets **local execution** (developer invokes `/code-review`, report is shown in the conversation). The finding structure, stable IDs, and inline markers are deliberately designed so a future GitHub-Action mode can post the same findings as PR inline comments without changing the reviewers. Do not build GitHub posting yet.

## File map

- `references/finding-schema.md` — finding JSON contract + `review-state.json` shape. **Read before Phase 2.**
- `references/reviewer-*.md` — one per reviewer; passed verbatim to the subagent.
- `references/consolidation.md` — orchestrator polish pass + report template.
- `references/correction.md` — corrector behavior + escalation rules.
- `scripts/SCRIPTS.md` — contract (inputs/outputs/exit codes) of every script. Implementation pending.
