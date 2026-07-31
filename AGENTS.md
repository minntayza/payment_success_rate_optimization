# Repository Guidelines

## Project Structure & Module Organization

`payment_dashboard/` contains the application code. `app.py` is the Streamlit
entry point, `prepare_data.py` enriches raw transactions with simulated gateway
data, and `analytics.py` and `alerting.py` implement dashboard logic. Shared
configuration and data models live in `config.py` and `models.py`; Supabase
access is isolated in `database.py`, `auth.py`, and `transaction_service.py`; reusable
presentation components belong in `payment_dashboard/ui/`.

Tests live in `tests/` and mirror the application modules. Documentation is in
`docs/`. Place source CSVs in `data/raw/` and generated datasets in
`data/processed/`; both are intentionally excluded from Git.

## Build, Test, and Development Commands

- `make setup` creates `.venv` and installs the package with development tools.
- `make run` starts the local Streamlit app.
- `make prepare` generates the gateway-enriched dataset from the expected raw CSV.
- `make load-supabase` imports the prepared data using local-only Supabase admin credentials.
- `make test` runs the complete pytest suite.
- `make test-unit` or `make test-integration` runs a focused test category.
- `make lint` checks Ruff rules; `make format` applies Ruff formatting.

Run `make help` to see all supported targets. Commands assume Python 3.11 or
newer.

## Coding Style & Naming Conventions

Use four-space indentation, an 88-character line limit, and type hints for
public functions. Follow `snake_case` for modules, functions, variables, and
test names; use `PascalCase` for classes and `UPPER_CASE` for constants. Keep
data transformations deterministic and separate calculation logic from
Streamlit rendering. Ruff enforces imports, modern Python syntax, common bug
patterns, and formatting. Run `make lint` before submitting changes.

## Testing Guidelines

Use pytest. Name files `test_<module>.py` and tests `test_<behavior>`. Put shared
fixtures in `tests/conftest.py`. Mark filesystem, subprocess, or Streamlit tests
with `@pytest.mark.integration`. Add regression tests for metric definitions,
schema validation, gateway simulation, and alert thresholds. No formal coverage
minimum is configured; new behavior should have focused unit tests and pass
`make test`.

## Commit & Pull Request Guidelines

History primarily uses short Conventional Commit subjects such as
`feat: calculate payment success analytics` and `docs: add setup guidance`.
Use an imperative subject with an appropriate prefix (`feat:`, `fix:`, `test:`,
`docs:`, or `chore:`).

Pull requests should explain the user-visible change, identify dataset or metric
assumptions, and include test and lint results. Add screenshots for dashboard
changes and link related issues when available. Never commit credentials,
virtual environments, generated CSVs, or real payment/customer data; this MVP
uses simulated gateway assignments only.
