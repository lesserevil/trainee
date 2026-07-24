# BEGIN OOMPAH PROJECT BOOTSTRAP v:1
# Project Makefile.
#
# Targets are documented inline with `## ` comments so `make help` stays
# current as this file is customized.
# END OOMPAH PROJECT BOOTSTRAP

.DEFAULT_GOAL := help

.PHONY: help init setup fmt fmt-check build test lint clean

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

help: ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "; printf "Usage: make <target>\n\nTargets:\n"} \
		/^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' \
		$(MAKEFILE_LIST)

init: ## Initialize local repo prerequisites.
	@set -e; \
	if [ ! -d .git ]; then \
		echo "[init] git init"; \
		git init; \
	else \
		echo "[init] git: already initialized"; \
	fi; \
	if command -v oompah >/dev/null 2>&1; then \
		echo "[init] oompah: $$(oompah --help >/dev/null 2>&1 && echo installed)"; \
	else \
		echo "[init] oompah CLI not found. Install with:"; \
		echo "       uv tool install git+https://github.com/lesserevil/oompah"; \
	fi

setup: init ## Install trainee and its browser/audio prerequisites.
	@sh scripts/setup.sh

fmt: ## Format all source files in place.
	@echo "fmt: not yet configured - edit Makefile" && exit 1

fmt-check: ## Check formatting without modifying files.
	@echo "fmt-check: not yet configured - edit Makefile" && exit 1

build: ## Build the native audio helper and check Python bytecode compilation.
	@sh scripts/build_audio_helper.sh
	@$(PYTHON) -m compileall -q \
		browser content context model quiz config.py trainee.py

test: ## Run the test suite.
	@$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

lint: ## Run static analysis / linters.
	@echo "lint: not yet configured - edit Makefile" && exit 1

clean: ## Remove build artifacts.
	@rm -rf .build
