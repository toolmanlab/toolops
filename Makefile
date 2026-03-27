.PHONY: install dev lint fmt typecheck test test-cov clean

PYTHON := python3
PKG    := toolops

install:
	pip install -e .

dev:
	pip install -e ".[dev,all]"

lint:
	ruff check $(PKG) tests

fmt:
	ruff format $(PKG) tests

typecheck:
	mypy $(PKG)

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=$(PKG) --cov-report=html --cov-report=term-missing

clean:
	rm -rf dist build .eggs *.egg-info .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage

# ── Docker helpers ────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

status:
	toolops status
