.DEFAULT_GOAL := help
.PHONY: help setup lint validate installer-test test test-cov audit check clean \
        publish-gh publish-clawhub publish-hermes publish

DATA       := skills/konecty-data
META       := skills/konecty-meta
DEV        := skills/konecty-dev
SETUP      := skills/konecty-setup
SKILLS     := $(DATA) $(META)
ALL_SKILLS := $(DATA) $(META) $(DEV) $(SETUP)

VERSION   ?= $(shell git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//' || echo "1.0.0")
CHANGELOG ?= Release $(VERSION)

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "} {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Point git at .githooks (idempotent — run after cloning)
	git config core.hooksPath .githooks
	@echo "Git hooks path set to .githooks"

lint: ## Byte-compile all Python — installer + any remaining scripts (stdlib syntax check)
	@find installer skills e2e tests -name '*.py' -not -path '*/__pycache__/*' -print0 | \
		xargs -0 python3 -m py_compile && echo "py_compile OK"

validate: ## Validate all SKILL.md against the agentskills.io spec (needs gh skill)
	@command -v gh >/dev/null 2>&1 || { echo "gh not installed — skipping"; exit 0; }
	@for s in $(ALL_SKILLS); do echo "== $$s =="; (cd $$s && gh skill publish --dry-run) || exit 1; done

installer-test: ## Run the konecty-skills installer unit tests (stdlib only, offline)
	@(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)

test: ## Run the integration suite (needs Konecty at :3000 + ~/.konecty/.env)
	@python3 -m pytest tests/integration -q

test-cov: ## Run integration suite with coverage report (same prereqs as test)
	@bash tests/run_coverage.sh

audit: ## Code-health + security audit (the completion gate before a PR)
	@bash .agents/skills/codebase-intelligence/scripts/audit.sh . --changed-since main
	@bash .agents/skills/codebase-security/scripts/audit.sh . --changed-since main

check: lint installer-test ## Offline gate: Python syntax + installer tests (no live server)

clean: ## Remove Python and coverage artifacts
	@find . -path ./.agents -prune -o -name '__pycache__' -type d -print0 2>/dev/null | xargs -0 rm -rf
	@rm -rf .coverage .coverage.* htmlcov tests/coverage_html tests/coverage.xml
	@echo "cleaned"

## ─── E2E harness (dockerized Konecty + pseudo-agent) ──────────────────────
.PHONY: e2e-up e2e-down e2e-reset e2e-wait e2e-token e2e-run e2e-cov e2e-sec e2e-infer e2e

E2E_COMPOSE := docker compose -f e2e/docker-compose.yml
E2E_URL     ?= http://localhost:3200
E2E_PYTEST  := uv run --with pytest --with coverage python -m
E2E_COV     := uv run --with coverage python -m coverage

e2e-up: ## Boot the disposable Konecty stack and wait until healthy
	$(E2E_COMPOSE) up -d
	@python3 e2e/scripts/wait_for_konecty.py --url $(E2E_URL) --timeout 180

e2e-down: ## Stop the e2e stack (keeps volumes)
	$(E2E_COMPOSE) down

e2e-reset: ## Stop the e2e stack and DROP volumes (clean DB + fresh admin next boot)
	$(E2E_COMPOSE) down -v

e2e-wait: ## Poll the e2e Konecty /liveness until healthy
	@python3 e2e/scripts/wait_for_konecty.py --url $(E2E_URL) --timeout 180

e2e-token: ## Print an admin token from the e2e container logs (does not write ~/.konecty/.env)
	@python3 e2e/scripts/konecty_admin_token.py --url $(E2E_URL) --print-only

e2e-run: ## Run the full e2e suite (live + mock + security + inference)
	@$(E2E_PYTEST) pytest tests/e2e/ -v

e2e-cov: ## Run the e2e suite with coverage and the >=90% gate
	@$(E2E_PYTEST) coverage run -m pytest tests/e2e/ -q
	@$(E2E_COV) report --show-missing --fail-under=90
	@$(E2E_COV) html >/dev/null && $(E2E_COV) xml >/dev/null && echo "coverage html: tests/coverage_html/index.html"

e2e-sec: ## Run only the security suite
	@$(E2E_PYTEST) pytest tests/e2e/test_security.py -v

e2e-infer: ## Run only the inference/intent-router suite
	@$(E2E_PYTEST) pytest tests/e2e/test_inference.py -v

## ─── Publishing ─────────────────────────────────────────────────────────────
## Usage: make publish-clawhub VERSION=1.2.0 CHANGELOG="Fix auth edge case"
##        make publish          VERSION=1.2.0 CHANGELOG="Fix auth edge case"

publish-gh: validate ## Publish all skills to GitHub via gh skill (needs: gh auth login)
	@command -v gh >/dev/null 2>&1 || { echo "ERROR: gh not installed. Run: gh auth login"; exit 1; }
	@for s in $(ALL_SKILLS); do echo "== $$s =="; (cd $$s && gh skill publish --fix) || exit 1; done

publish-clawhub: validate ## Publish all skills to OpenClaw/clawhub (needs: npm i -g clawhub && clawhub login)
	@command -v clawhub >/dev/null 2>&1 || { echo "ERROR: run 'npm i -g clawhub' then 'clawhub login'"; exit 1; }
	@for s in $(ALL_SKILLS); do \
		slug=$$(basename $$s); \
		echo "== $$slug v$(VERSION) =="; \
		clawhub skill publish ./$$s --slug $$slug --version $(VERSION) --changelog "$(CHANGELOG)" || exit 1; \
	done

publish-hermes: ## Publish all skills to Hermes/NousResearch (GitHub-backed, no separate auth)
	@command -v hermes >/dev/null 2>&1 || { echo "ERROR: hermes not installed"; exit 1; }
	@for s in $(ALL_SKILLS); do \
		echo "== $$s =="; \
		hermes skills publish $$s --to github --repo konecty/skills || exit 1; \
	done

publish: validate publish-gh publish-clawhub publish-hermes ## Publish to all marketplaces (gh + clawhub + hermes)

## ─── E2E harness (dockerized Konecty + pseudo-agent) ──────────────────────

e2e: ## Self-contained run: purge -> up -> wait -> coverage gate -> purge (always tears down, even on failure/interrupt)
	@set -e; \
	trap '$(E2E_COMPOSE) down -v >/dev/null 2>&1 || true' EXIT INT TERM; \
	$(E2E_COMPOSE) down -v; \
	$(E2E_COMPOSE) up -d; \
	python3 e2e/scripts/wait_for_konecty.py --url $(E2E_URL) --timeout 180; \
	$(E2E_PYTEST) coverage run -m pytest tests/e2e/ -q; \
	$(E2E_COV) report --show-missing --fail-under=90; \
	$(E2E_COV) html >/dev/null && $(E2E_COV) xml >/dev/null; \
	echo "coverage html: tests/coverage_html/index.html"
