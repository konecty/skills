.PHONY: setup

setup:
	git config core.hooksPath .githooks
	@echo "Git hooks path set to .githooks"
	@echo "Run 'make setup' again at any time — it is idempotent."
