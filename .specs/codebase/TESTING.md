# Testing Infrastructure

## Test Frameworks

**Unit/Integration:** None  
**E2E:** None  
**Coverage:** None  
**Manual validation:** `skill-creator` workflow (Draft → Test → Review → Iterate → Optimize → Package)

## Test Organization

**Status:** No automated tests exist in this repository.

There are no `*_test.py`, `test_*.py`, `conftest.py`, `pytest.ini`, `.github/workflows/`, or `Makefile` test targets.

## Testing Patterns

### Manual Skill Validation (current approach)

**Approach:** Human-driven using the `skill-creator` external skill  
**Location:** Not persisted — done interactively in the agent session  
**Steps:**
1. Draft skill SKILL.md
2. Test with real Konecty instance
3. Review description triggers + instructions
4. Iterate based on behavior
5. Optimize description for selection accuracy
6. Package (finalize frontmatter, changelog entry)

### Security Audits (manual, pre-publish)

**Approach:** External CLI tools run manually before publishing to marketplaces  
**Commands:**
```bash
# Prompt injection + credential issues
export SNYK_TOKEN=<token>
uvx snyk-agent-scan@latest --skills                 # all skills
uvx snyk-agent-scan@latest ./skills/<skill-name>    # one skill

# Supply chain
npm i -g @socketsecurity/cli
socket login
socket scan create ./skills/<skill-name>
socket ci

# Web-only trust audit
# Paste skill URL at https://ai.gendigital.com/agent-trust-hub
```

## Test Execution

**Commands:** None (no automated test runner)  
**Configuration:** None

## Coverage Targets

**Current:** 0% — no automated coverage  
**Goals:** Not documented  
**Enforcement:** None — manual discipline only

## Test Coverage Matrix

| Code Layer | Required Test Type | Location Pattern | Run Command |
|---|---|---|---|
| Python scripts (`scripts/*.py`) | unit | none | none |
| SKILL.md frontmatter | schema validation | none | `gh skill publish --dry-run` (partial) |
| Konecty API integration | integration | none | none |
| Credential loading | unit | none | none |
| CLI argument parsing | unit | none | none |

## Parallelism Assessment

| Test Type | Parallel-Safe? | Isolation Model | Evidence |
|---|---|---|---|
| (none exist) | N/A | N/A | N/A |

## Gate Check Commands

| Gate Level | When to Use | Command |
|---|---|---|
| Syntax check | Before commit | `python3 -m py_compile skills/<name>/scripts/<name>.py` |
| Skill validation | Before publishing | `gh skill publish --dry-run` |
| Security scan | Before marketplace publish | `uvx snyk-agent-scan@latest ./skills/<name>` |

**Note:** No automated test suite exists. Until one is created, gate checks are manual. See CONCERNS.md — missing test automation is flagged as HIGH severity.
