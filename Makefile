.PHONY: fmt lint typecheck test check

fmt:
	ruff format .
	ruff check --fix .

lint:
	ruff check .
	ruff format --check .

typecheck:
	mypy outreach_lint

test:
	pytest

check: lint typecheck test
