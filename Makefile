.PHONY: dev test up down status lint typecheck

dev:
	uv run uvicorn toolops.api.app:create_app --factory --reload --port 9000

test:
	uv run pytest tests/unit/ -v

test-all:
	uv run pytest tests/ -v

up:
	docker compose up -d

down:
	docker compose down

status:
	docker compose ps

lint:
	uv run ruff check toolops/ tests/
	uv run ruff format --check toolops/ tests/

format:
	uv run ruff check --fix toolops/ tests/
	uv run ruff format toolops/ tests/

typecheck:
	uv run mypy toolops/

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .coverage .mypy_cache .pytest_cache .ruff_cache
