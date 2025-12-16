.PHONY: help format lint test clean install

help:
	@echo "Available commands:"
	@echo "  make format    - Format all Python code with black"
	@echo "  make lint      - Lint all Python code with ruff"
	@echo "  make test      - Run tests"
	@echo "  make install   - Install root-level dev dependencies"
	@echo "  make clean     - Clean build artifacts"

format:
	@echo "Formatting code with black..."
	@if command -v poetry >/dev/null 2>&1 && [ -f pyproject.toml ]; then \
		poetry run black scaper/ --line-length 120 || black scaper/ --line-length 120; \
	else \
		black scaper/ --line-length 120; \
	fi
	@echo "✓ Code formatted"

lint:
	@echo "Linting code with ruff..."
	@if command -v poetry >/dev/null 2>&1 && [ -f pyproject.toml ]; then \
		poetry run ruff check scaper/ || ruff check scaper/; \
	else \
		ruff check scaper/; \
	fi
	@echo "✓ Linting complete"

test:
	@echo "Running tests..."
	@echo "⚠️  Tests not yet implemented"

install:
	@echo "Installing root-level dev dependencies..."
	@poetry install --no-root
	@echo "✓ Dependencies installed"

clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	@echo "✓ Clean complete"

