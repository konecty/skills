# Consolidation — Orchestrator Polish Pass & Report Template

`consolidate.sh` already did the deterministic work: positional dedup (±3 lines), stable IDs, severity grouping, gap detection, report skeleton. Your pass adds only what requires judgment. Keep it light — do not rewrite findings, do not re-review the code.

## 1. Semantic dedup

Scan findings that survived positional dedup but describe **the same root problem** from different angles (e.g. SEC flags a log line as PII exposure and REG flags the same line as leftover debug print). Merge into the lower-numbered ID, append the other origin to `merged_origins`, keep the richer description. Record the merge via `review-state.sh` — never edit JSON by hand.

When two findings share a line but are genuinely different problems, leave both. When in doubt, leave both.

## 2. Executive summary

Write 2-4 sentences at the top: overall verdict feel (e.g. "solid delivery with two blocking issues"), the count by severity, and the single most important thing to fix first. No fluff.

## 3. Code markers

Every finding renders as a block: marker line, location, snippet, description, recommendation. The marker `<!-- code-review:{origin}:{id} -->` is the future GitHub inline-comment key — keep it exactly as generated.

## Report template

```markdown
# 🤖 Code Review — {branch} → {base}

{executive summary}

| | |
|---|---|
| **Reviewers** | 6 of 6 (Security · Requirements · Tests · Architecture · Regression · Performance) |
| **Sources** | spec: {spec_path or "manual input"} · Konecty: {yes/no} · codebase docs: {list or "none — degraded"} |
| **Findings** | {N} across {M} files ({X} from scripts, {Y} from reviewers) |
| **Cycle** | {cycle number} |

{if context.degraded is non-empty: ⚠️ degraded notes, one line each}

---
## 🔒 Security ({n})

<!-- code-review:security:SEC-001 -->
**[SEC-001]** {title} — `{file}:{line_start}`
```{lang}
{evidence}
```
{description}
**Fix:** {recommendation}

## 🚨 Critical ({n})
## ⚡ Performance ({n})
## ⚠️ Warnings ({n})
## 💡 Suggestions ({n})
{same block format; requirements findings show `requirement_ref`; architecture findings show `rule_ref`}

---
## 🔍 Files with no findings
- `{path}` — verify manually or request a targeted review
{omit section when empty; config/lock/pure-type files are pre-excluded by the script}

---
**Next step:** reply with what to fix — `all`, severities (`critical and security`), or IDs (`SEC-001, ARQ-003`). Anything not selected is dismissed for this session.
```

## Re-review report addendum

On re-review cycles, prepend a status table before the findings:

```markdown
## 🔁 Re-review — cycle {n}
| ID | Status | Attempts |
|---|---|---|
| SEC-001 | ✅ verified | 1 |
| REQ-002 | ❌ reopened — 1 attempt left | 1 |
| ARQ-003 | 🧊 escalated — limit reached, needs human | 2 |

{if any fix_induced findings:}
### ⚠️ New issues introduced by fixes
{render them as normal finding blocks, flagged `fix_induced`, fresh IDs}
```

State every escalated finding plainly: what was tried, why it still fails, what decision the human must make.
