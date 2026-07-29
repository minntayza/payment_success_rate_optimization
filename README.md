# Payment Success Rate Optimization Dashboard

A local Streamlit web application for exploring payment success, comparing
simulated gateways, analyzing failure patterns, and detecting recent
success-rate degradation.

This is an academic MVP built from a Kaggle transaction dataset. Gateway A-D
labels are assigned randomly with a fixed seed. They are simulated and must not
be interpreted as measurements of real banks or payment gateways.

## Features

- Reproducible Gateway A-D assignment
- Strict CSV schema and value validation
- Overall and gateway-level payment success metrics
- Interactive filters for gateway, transaction type, device, status, and date
- Chronological transaction replay
- Latest-50 rolling gateway monitoring
- Alerts for drops of at least 10 percentage points below baseline
- Top-of-page English/မြန်မာ language switch
- Button-triggered English AI Operations Brief generated with MiMo 2.5 Pro
- Interactive Plotly charts and recent-transaction investigation

## Requirements

- Python 3.11 or newer
- Access to an Anthropic-compatible MiMo 2.5 Pro endpoint
- The source file `transaction_data.csv`

## Setup

From the project directory:

```bash
make setup
mkdir -p data/raw data/processed
cp /path/to/transaction_data.csv data/raw/transaction_data.csv
```

`make setup` creates `.venv` and installs the project and development tools as
an editable package. The equivalent manual install is:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

The CSV files under `data/raw/` and `data/processed/` are intentionally ignored
by Git.

### Configure the optional AI brief

Set the Anthropic-compatible endpoint and API key in the shell that starts
Streamlit. The model defaults to `mimo-2.5-pro`:

```bash
export ANTHROPIC_BASE_URL=https://your-provider.example
export ANTHROPIC_API_KEY=replace-with-your-api-key
export ANTHROPIC_MODEL=mimo-2.5-pro
```

Do not commit your real API key. Only aggregate metrics are sent to the model.
Raw transaction rows,
transaction IDs, timestamps, and individual amounts are excluded.

## Prepare the dataset

Generate the gateway-enriched dataset:

```bash
make prepare
```

The command:

1. Validates the source schema and values.
2. Sorts transactions chronologically.
3. Assigns Gateway A-D using a reproducible random seed.
4. Preserves all original transaction outcomes.
5. Writes a separate processed CSV.

## Run the tests

```bash
make test
```

## Start the web app

```bash
ARROW_DEFAULT_MEMORY_POOL=system make run
```

Open [http://localhost:8501](http://localhost:8501) if the browser does not open
automatically. Stop the server with `Ctrl+C`.

## Use the dashboard

1. Use the English/မြန်မာ switch above the title to choose the dashboard
   language. Gateway names and transaction category values remain unchanged.
2. Move the replay slider to control how many chronological transactions have
   arrived.
3. Use sidebar filters to narrow the displayed KPIs, charts, and transaction
   table.
4. Click **Generate AI Brief** for an English summary of the current filtered
   view. The output is retained until the underlying metrics change.
5. Expand **Evidence sent to the AI model** to compare the generated text
   with the exact aggregate facts supplied to MiMo.
6. Review Gateway Health to compare each baseline with its latest 50 replayed
   transactions.
7. Use Failure Analysis to investigate patterns by fraud flag, latency band,
   device, and transaction type.
8. Use Recent Transactions to inspect individual records.

The AI brief is English-only, uses simulated gateway data, and is not real
financial or routing advice. If configuration is missing or the provider is
unavailable, the dashboard shows an actionable error without exposing the key.

Display filters do not change alert calculations. Alerts always use the
unfiltered chronological replay stream.

## Metric definitions

- **Success rate:** Successful transactions divided by all transactions in the
  current display scope.
- **Gateway baseline:** A gateway's success rate across the full prepared
  dataset.
- **Rolling rate:** Success rate across the latest 50 replayed transactions for
  one gateway.
- **Drop:** Gateway baseline minus its rolling rate.
- **Alert:** A drop of at least 10 percentage points.
- **Insufficient history:** Fewer than 50 replayed transactions for a gateway.
- **Average latency:** Mean transaction latency in milliseconds.
- **P95 latency:** The latency value at or below which 95% of transactions fall.

## Project structure

```text
payment_dashboard/
├── alerting.py       # Baselines and rolling alert evaluation
├── analytics.py      # Metrics, filtering, breakdowns, and time series
├── app.py            # Streamlit web interface
├── data_loader.py    # Schema validation and typed loading
└── prepare_data.py   # Reproducible gateway enrichment command

tests/
├── conftest.py
├── test_alerting.py
├── test_analytics.py
├── test_app.py
├── test_data_loader.py
└── test_prepare_data.py
```

## Troubleshooting

### Prepared data is missing

Run the preparation command again and confirm this file exists:

```text
data/processed/transactions_with_gateways.csv
```

### A gateway shows insufficient history

Move the replay slider forward until that gateway has at least 50 replayed
transactions.

### The local port is already in use

Choose another port:

```bash
.venv/bin/python -m streamlit run payment_dashboard/app.py --server.port 8502
```

## Limitations

- Gateway labels are random and do not describe real gateway performance.
- The replay slider simulates arrival from a historical CSV; it is not a
  production streaming pipeline.
- The application does not connect to banks, payment APIs, databases, or
  external alert-delivery services.
- The dataset has no explicit insufficient-balance, incorrect PIN, or incorrect
  OTP failure-reason fields.
- The application is designed for local academic demonstration, not production
  operations.

For support interpretation, see
[docs/customer-support-guide.md](docs/customer-support-guide.md).
