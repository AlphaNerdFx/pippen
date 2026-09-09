# nba-impact developer tasks.
# Every target here is also what continuous integration runs, so a green
# `make check` locally means a green pipeline remotely.

.DEFAULT_GOAL := help
.PHONY: help install format lint typecheck test check clean docs serve-docs lock requirements

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Create the environment and install dev dependencies
	uv sync --extra dev
	uv run pre-commit install

format:  ## Auto-fix formatting and import order
	uv run ruff format .
	uv run ruff check --fix .

lint:  ## Check formatting and lint rules without changing files
	uv run ruff check .
	uv run ruff format --check .

typecheck:  ## Run mypy in strict mode
	uv run mypy

test:  ## Run the offline test suite with coverage
	uv run pytest -m 'not network' --cov --cov-report=term-missing

test-all:  ## Run every test, including those needing network access
	uv run pytest --cov --cov-report=term-missing

check: lint typecheck test  ## Run everything CI runs

docs:  ## Build the documentation site
	uv run --extra docs mkdocs build --strict

serve-docs:  ## Serve the documentation locally at :8000
	uv run --extra docs mkdocs serve

lock:  ## Refresh the lockfile
	uv lock

requirements:  ## Regenerate requirements.txt from the lockfile for non-uv users
	uv export --no-hashes --no-dev --format requirements-txt -o requirements.txt

clean:  ## Remove caches and build artifacts
	rm -rf build dist site .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +

