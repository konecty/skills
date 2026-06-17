.DEFAULT_GOAL := help
.PHONY: help setup lint validate shared-check installer-test test test-cov audit check clean

DATA  := skills/konecty-data
META  := skills/konecty-meta
SKILLS := $(DATA) $(META)

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "} {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Point git at .githooks (idempotent — run after cloning)
	git config core.hooksPath .githooks
	@echo "Git hooks path set to .githooks"

lint: ## Byte-compile every skill script (stdlib syntax check)
	@find skills -name '*.py' -not -path '*/__pycache__/*' -print0 | \
		xargs -0 python3 -m py_compile && echo "py_compile OK"

shared-check: ## Run the gated shared-files divergence guard
	@.githooks/pre-commit

validate: ## Validate both SKILL.md against the agentskills.io spec (needs gh skill)
	@command -v gh >/dev/null 2>&1 || { echo "gh not installed — skipping"; exit 0; }
	@for s in $(SKILLS); do echo "== $$s =="; (cd $$s && gh skill publish --dry-run) || exit 1; done

installer-test: ## Run the konecty-skills installer unit tests (stdlib only, offline)
	@(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)

test: ## Run the integration suite (needs Konecty at :3000 + ~/.konecty/.env)
	@python3 -m pytest tests/integration -q

test-cov: ## Run integration suite with coverage report (same prereqs as test)
	@bash tests/run_coverage.sh

audit: ## Code-health + security audit (the completion gate before a PR)
	@bash .agents/skills/codebase-intelligence/scripts/audit.sh . --changed-since main
	@bash .agents/skills/codebase-security/scripts/audit.sh . --changed-since main

check: lint shared-check installer-test ## Offline gate: syntax + shared-files divergence + installer tests (no live server)

clean: ## Remove Python and coverage artifacts
	@find . -path ./.agents -prune -o -name '__pycache__' -type d -print0 2>/dev/null | xargs -0 rm -rf
	@rm -rf .coverage .coverage.* htmlcov tests/coverage_html tests/coverage.xml
	@echo "cleaned"
