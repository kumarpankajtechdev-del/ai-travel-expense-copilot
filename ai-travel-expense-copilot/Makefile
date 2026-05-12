.PHONY: install test lint run docker

install:
	pip install -e '.[dev]'

test:
	pytest -q

lint:
	ruff check src tests

run:
	uvicorn expense_ai_copilot.main:app --reload

docker:
	docker compose up --build
