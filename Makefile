.PHONY: help setup test coverage lint typecheck check build clean

UV ?= uv

help:
	@printf '%s\n' 'Targets: setup test coverage lint typecheck check build clean'

setup:
	$(UV) sync --extra dev

test:
	$(UV) run --extra dev pytest

coverage:
	$(UV) run --extra dev pytest --cov=portolan --cov-report=term-missing

lint:
	$(UV) run --extra dev ruff check .

typecheck:
	$(UV) run --extra dev mypy

check: lint typecheck test

build:
	$(UV) build

clean:
	rm -rf dist build *.egg-info .pytest_cache .ruff_cache .mypy_cache htmlcov
