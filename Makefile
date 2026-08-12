PYTHON = .venv/bin/python
PYTEST = $(PYTHON) -m pytest
RUFF = .venv/bin/ruff

.PHONY: help setup test test-unit test-integration test-live smoke lint format typecheck check run prepare load-mongodb verify-clean clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup:  ## Create venv and install dependencies
	uv sync --extra dev --frozen

test:  ## Run all tests
	$(PYTEST) -q

test-unit:  ## Run unit tests only
	$(PYTEST) -q -m "not integration"

test-integration:  ## Run integration tests only
	$(PYTEST) -q -m integration

test-live:  ## Run opt-in Atlas and AI provider contract checks
	RUN_ATLAS_TESTS=1 RUN_AI_TESTS=1 $(PYTEST) -q tests/test_live_atlas.py tests/test_live_ai.py

smoke:  ## Browser-smoke a running dashboard (set DASHBOARD_URL)
	@test -n "$(DASHBOARD_URL)" || (echo "Set DASHBOARD_URL, e.g. http://localhost:8501" >&2; exit 2)
	$(PYTHON) scripts/smoke_dashboard.py "$(DASHBOARD_URL)"

lint:  ## Run ruff linter
	$(RUFF) check payment_dashboard/ tests/ scripts/

format:  ## Auto-format code with ruff
	$(RUFF) format payment_dashboard/ tests/ scripts/

typecheck:  ## Run strict static type checking
	$(PYTHON) -m mypy payment_dashboard

check: lint typecheck test  ## Run all offline quality gates

run:  ## Start the Streamlit dashboard
	$(PYTHON) -m streamlit run payment_dashboard/app.py

prepare:  ## Prepare data (requires raw CSV in data/raw/)
	$(PYTHON) -m payment_dashboard.prepare_data \
		--input data/raw/transaction_data.csv \
		--output data/processed/transactions_with_gateways.csv

load-mongodb:  ## Import prepared simulated data into MongoDB Atlas
	$(PYTHON) -m payment_dashboard.load_mongodb \
		--input data/processed/transactions_with_gateways.csv

verify-clean:  ## Verify install and launch from a clean Git export
	./scripts/verify_clean_checkout.sh

clean:  ## Remove build artifacts
	rm -rf .venv build dist *.egg-info .ruff_cache .mypy_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
