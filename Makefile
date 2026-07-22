.DEFAULT_GOAL := help
.PHONY: help setup lint validate installer-test test audit check clean \
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
	@find installer skills e2e tests -path e2e/.konecty-src -prune -o -name '*.py' -not -path '*/__pycache__/*' -print0 | \
		xargs -0 python3 -m py_compile && echo "py_compile OK"

validate: ## Validate all SKILL.md against the agentskills.io spec (needs gh skill)
	@command -v gh >/dev/null 2>&1 || { echo "gh not installed — skipping"; exit 0; }
	@for s in $(ALL_SKILLS); do echo "== $$s =="; (cd $$s && gh skill publish --dry-run) || exit 1; done

installer-test: ## Run the konecty-skills installer unit tests (stdlib only, offline)
	@(cd installer && PYTHONPATH=src python3 -m unittest discover -s tests -t .)

test: e2e-run ## Alias: run the MCP e2e suites (needs `make e2e-up` first)

audit: ## Code-health + security audit (the completion gate before a PR)
	@bash .agents/skills/codebase-intelligence/scripts/audit.sh . --changed-since main
	@bash .agents/skills/codebase-security/scripts/audit.sh . --changed-since main

check: lint installer-test ## Offline gate: Python syntax + installer tests (no live server)

clean: ## Remove Python caches and test artifacts
	@find . \( -path ./.agents -o -path ./e2e/.konecty-src \) -prune -o -name '__pycache__' -type d -print0 2>/dev/null | xargs -0 rm -rf
	@rm -rf .pytest_cache
	@echo "cleaned"

## ─── E2E harness (dockerized Konecty + pseudo-agent) ──────────────────────
.PHONY: e2e-src e2e-up e2e-down e2e-reset e2e-wait e2e-token e2e-run e2e

E2E_COMPOSE     := docker compose -f e2e/docker-compose.yml
E2E_URL         ?= http://localhost:3200
E2E_PYTEST      := uv run --with pytest python -m
KONECTY_REPO    ?= ../Konecty
KONECTY_E2E_REF ?= feat/admin-mcp-meta-delete
E2E_SRC         := e2e/.konecty-src

e2e-src: ## Create/refresh the Konecty source worktree and build dist/ (docker build context)
	@if [ ! -e $(E2E_SRC)/.git ]; then \
		git -C $(KONECTY_REPO) worktree add --detach $(CURDIR)/$(E2E_SRC) $(KONECTY_E2E_REF); \
	fi
	@cd $(E2E_SRC) && yarn install --frozen-lockfile --non-interactive && yarn build

e2e-up: ## Build the Konecty image from source, boot the stack, wait, bootstrap MCP flags
	@[ -e $(E2E_SRC)/.git ] || $(MAKE) e2e-src
	$(E2E_COMPOSE) up -d --build
	@python3 e2e/scripts/wait_for_konecty.py --url $(E2E_URL) --timeout 300
	@python3 e2e/scripts/bootstrap_mcp.py

e2e-down: ## Stop the e2e stack (keeps volumes)
	$(E2E_COMPOSE) down

e2e-reset: ## Stop the e2e stack and DROP volumes (clean DB + fresh admin next boot)
	$(E2E_COMPOSE) down -v

e2e-wait: ## Poll the e2e Konecty /liveness until healthy
	@python3 e2e/scripts/wait_for_konecty.py --url $(E2E_URL) --timeout 180

e2e-token: ## Print an admin token from the e2e container logs (does not write ~/.konecty/.env)
	@python3 e2e/scripts/konecty_admin_token.py --url $(E2E_URL) --print-only

e2e-run: ## Run the MCP e2e suites (smoke + user + admin + oauth) against a running stack
	@$(E2E_PYTEST) pytest tests/e2e/ -v

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
	@command -v hermes >/dev/null 2>&1 || { echo "WARN: hermes not installed — skipping Hermes publish"; exit 0; }
	@for s in $(ALL_SKILLS); do \
		echo "== $$s =="; \
		hermes skills publish $$s --to github --repo konecty/skills || exit 1; \
	done

publish: validate publish-gh publish-clawhub publish-hermes ## Publish to all marketplaces (gh + clawhub + hermes)

## ─── E2E harness (dockerized Konecty + pseudo-agent) ──────────────────────

e2e: ## Self-contained run: purge -> build+up -> wait -> bootstrap -> suites -> purge (always tears down)
	@[ -e $(E2E_SRC)/.git ] || $(MAKE) e2e-src
	@set -e; \
	trap '$(E2E_COMPOSE) down -v >/dev/null 2>&1 || true' EXIT INT TERM; \
	$(E2E_COMPOSE) down -v; \
	$(E2E_COMPOSE) up -d --build; \
	python3 e2e/scripts/wait_for_konecty.py --url $(E2E_URL) --timeout 300; \
	python3 e2e/scripts/bootstrap_mcp.py; \
	$(E2E_PYTEST) pytest tests/e2e/ -q
