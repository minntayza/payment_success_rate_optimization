# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Streamlit-based dashboard for monitoring payment success rates, comparing simulated gateways (A-D), analyzing failure patterns, and detecting success-rate degradation. Built as an academic MVP using a Kaggle transaction dataset.

## Development Commands

### Environment Setup
```bash
make setup           # Creates venv and installs editable + dev deps
# — or manually —
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### Data Preparation
The dashboard requires a gateway-enriched CSV. Raw CSV files are in `data/raw/`, processed files in `data/processed/` (both gitignored).

```bash
make prepare
# — or manually —
python -m payment_dashboard.prepare_data \
  --input data/raw/transaction_data.csv \
  --output data/processed/transactions_with_gateways.csv \
  --seed 20260728
```

### Running Tests
```bash
make test                # All tests (31)
make test-unit           # Unit tests only (25) — no filesystem/subprocess
make test-integration    # Integration tests only (6)
# — or manually —
python -m pytest -q
python -m pytest -m "not integration" -q
python -m pytest -m integration -q
python -m pytest tests/test_analytics.py -q
python -m pytest -k "test_name" -q
```

### Linting and Formatting
```bash
make lint       # ruff check
make format     # ruff format
```

### Starting the Dashboard
```bash
make run
# — or —
streamlit run payment_dashboard/app.py
# Default: http://localhost:8501
```

## Architecture

### Module Layout
```
payment_dashboard/
  __init__.py
  __main__.py          # python -m payment_dashboard entry point
  config.py            # Central constants (GATEWAYS, ALERT_*, paths, colors)
  models.py            # DashboardState frozen dataclass
  data_loader.py       # CSV validation + typed loading
  analytics.py         # Pure metric functions (no side effects)
  alerting.py          # Baseline and rolling-window alert logic
  prepare_data.py      # CLI script for gateway enrichment
  app.py               # Streamlit entry point, session state, orchestration
  ui/
    __init__.py
    style.py           # CSS constants and apply_page_style()
    charts.py          # Plotly figure builders (return go.Figure)
    sections.py        # Streamlit section renderers (KPIs, tables, charts)
```

### Data Flow
1. **Raw data** (`data/raw/transaction_data.csv`) → Kaggle transaction dataset
2. **Preparation** (`prepare_data.py`) → Validates schema, sorts chronologically, assigns random Gateway A-D labels with fixed seed
3. **Processed data** (`data/processed/transactions_with_gateways.csv`) → Enriched CSV loaded by the app
4. **Dashboard** (`app.py`) → Streamlit UI with replay slider and filters
5. **Analytics/Alerting** → Compute metrics on filtered/replayed subsets

### Key Modules

- **`config.py`** — Central constants: `GATEWAYS`, `DEFAULT_SEED`, `ALERT_WINDOW_SIZE`, `ALERT_THRESHOLD`, `DEFAULT_DATA_PATH`, `CHART_COLORS`, `STATUSES`, `REQUIRED_COLUMNS`.
- **`models.py`** — `DashboardState` frozen dataclass with typed fields: `replay_frame`, `display_frame`, `alerts`.
- **`app.py`** — Streamlit entry point. Manages session state (replay slider, filters), orchestrates data loading via `build_dashboard_state()`. UI rendering delegated to `ui/` modules.
- **`ui/charts.py`** — Plotly Express figure builders: `gateway_success_chart()`, `gateway_volume_chart()`, `success_trend_chart()`, `failure_breakdown_chart()`.
- **`ui/sections.py`** — Streamlit section renderers: `render_kpis()`, `render_gateway_health()`, `render_gateway_performance()`, `render_success_trend()`, `render_failure_analysis()`, `render_recent_transactions()`, `render_interpretation_guide()`.
- **`analytics.py`** — Pure functions: `summary_metrics()`, `gateway_summary()`, `failure_breakdown()`, `success_rate_series()`, `apply_filters()`, `add_latency_band()`.
- **`alerting.py`** — `calculate_baselines()` and `evaluate_alerts()` compare rolling-window rates against full-dataset baselines.
- **`data_loader.py`** — `validate_transactions()` and `load_transactions()` with schema enforcement. Raises `DataValidationError`.

### Alert Logic
- Baseline = gateway's success rate across entire processed dataset
- Rolling rate = success rate of gateway's latest 50 replayed transactions
- Alert triggers when drop (baseline - rolling) ≥ 10 percentage points
- "Insufficient history" when fewer than 50 replayed transactions exist for a gateway
- Alerts use unfiltered replay stream; display filters only affect charts/KPIs

### Data Schema
Required columns in CSV: `Transaction ID`, `Sender Account ID`, `Receiver Account ID`, `Transaction Amount`, `Transaction Type`, `Timestamp`, `Transaction Status` (Success/Failed), `Fraud Flag`, `Geolocation (Latitude/Longitude)`, `Device Used`, `Network Slice ID`, `Latency (ms)`, `Slice Bandwidth (Mbps)`, `PIN Code`. After preparation: adds `Bank Gateway` (Gateway A-D).

### Test Fixtures and Markers
- `tests/conftest.py` provides `sample_transactions` fixture (4-row DataFrame) used across test files.
- Tests are marked `@pytest.mark.integration` when they do I/O (filesystem, subprocess, Streamlit). Unmarked tests are unit tests.

## Environment Variables
- `PAYMENT_DATA_PATH` — Override default data path (`data/processed/transactions_with_gateways.csv`)

## Important Notes
- Gateway labels (A-D) are randomly simulated with a fixed seed — do not interpret as real gateway performance
- The replay slider simulates chronological arrival from CSV, not a streaming pipeline
- `data/raw/` and `data/processed/` are gitignored; source CSV must be provided manually
