.PHONY: install check guard openapi openapi-check fix test coverage-gate audit run

PYTHON_PATHS = backend/src backend/tests api
OPENAPI_SCHEMA = .claude/backend/openapi.json

install:
	uv sync --locked

check: guard openapi-check
	uv run ruff format --check $(PYTHON_PATHS)
	uv run ruff check $(PYTHON_PATHS)
	uv run mypy
	uv run lint-imports
	uv run vulture

guard:
	@if grep -rniE '#\s*(type:\s*ignore|mypy:\s*ignore-errors|noqa|ruff:\s*noqa|pragma:\s*no cover)' $(PYTHON_PATHS); then \
		echo 'error: suppression comments are not allowed; fix the code instead'; exit 1; fi

openapi:
	uv run python -m neuroctivity.openapi_export $(OPENAPI_SCHEMA)

openapi-check:
	uv run python -m neuroctivity.openapi_export --check $(OPENAPI_SCHEMA)

fix:
	uv run ruff format $(PYTHON_PATHS)
	uv run ruff check --fix $(PYTHON_PATHS)

test:
	uv run coverage erase
	uv run pytest --cov --cov-report=

coverage-gate:
	uv run coverage report --fail-under=95
	uv run coverage report --format=total --include='backend/src/neuroctivity/domain/*,backend/src/neuroctivity/application/*' --fail-under=98
	uv run coverage report --format=total --include='backend/src/neuroctivity/infrastructure/*,backend/src/neuroctivity/transport/*,backend/src/neuroctivity/main.py' --fail-under=90

audit:
	@requirements=$$(mktemp) && \
		uv export --quiet --locked --no-emit-project --no-annotate --format requirements-txt > $$requirements && \
		uvx --from pip-audit==2.10.1 pip-audit --requirement $$requirements --require-hashes --disable-pip --strict; \
		status=$$?; rm -f $$requirements; exit $$status

run:
	API_DOCS_ENABLED=true uv run uvicorn neuroctivity.main:create_app --factory --reload
