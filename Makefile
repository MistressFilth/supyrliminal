.PHONY: help init sync unit-test test clean lint typecheck format check release

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

init: ## Set up the environment from scratch (install deps, create venv)
	uv sync

sync: ## Update an existing environment to match current config
	uv sync

unit-test: sync ## Run unit tests
	.venv/bin/python -m pytest tests/unit/ -v

test: unit-test ## Run all tests

clean: ## Remove build and cache artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true

lint: sync ## Run linters
	uvx ruff check .

typecheck: sync ## Type-check the package source
	.venv/bin/python -m mypy supyrliminal

format: sync ## Auto-format source files
	uvx ruff format .

check: lint typecheck format ## Run lint, typecheck, and format

release: ## Build, tag, and release a new version
	@echo "Release workflow lives outside this Makefile; see CHANGELOG.md and pyproject.toml."
