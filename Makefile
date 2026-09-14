.PHONY: install run test lint
install:
	python -m pip install -r requirements.lock
	python -m pip install -e ".[dev]"
run:
	python -m expense_ai_copilot
test:
	python -m pytest
lint:
	python -m ruff check .
