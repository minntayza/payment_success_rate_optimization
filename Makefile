PYTHON = .venv/bin/python
PYTEST = $(PYTHON) -m pytest
RUFF = .venv/bin/ruff

.PHONY: help setup test test-unit test-integration lint format run prepare load-supabase verify-clean clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup:  ## Create venv and install dependencies
	python3 -m venv .venv
	$(PYTHON) -m pip install -e ".[dev]"

test:  ## Run all tests
	$(PYTEST) -q

test-unit:  ## Run unit tests only
	$(PYTEST) -q -m "not integration"

test-integration:  ## Run integration tests only
	$(PYTEST) -q -m integration

lint:  ## Run ruff linter
	$(RUFF) check payment_dashboard/ tests/

format:  ## Auto-format code with ruff
	$(RUFF) format payment_dashboard/ tests/

run:  ## Start the Streamlit dashboard
	$(PYTHON) -m streamlit run payment_dashboard/app.py

prepare:  ## Prepare data (requires raw CSV in data/raw/)
	$(PYTHON) -m payment_dashboard.prepare_data \
		--input data/raw/transaction_data.csv \
		--output data/processed/transactions_with_gateways.csv

load-supabase:  ## Import prepared simulated data into Supabase
	$(PYTHON) -m payment_dashboard.load_supabase \
		--input data/processed/transactions_with_gateways.csv

verify-clean:  ## Verify install and launch from a clean Git export
	./scripts/verify_clean_checkout.sh

clean:  ## Remove build artifacts
	rm -rf .venv build dist *.egg-info .ruff_cache .mypy_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
