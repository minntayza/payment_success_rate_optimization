# Payment Success Rate Optimization Dashboard Design

## 1. Purpose

Build an academic/demo MVP that analyzes a Kaggle payment transaction dataset and demonstrates how gateway-level payment success can be monitored locally. The application uses simulated gateway assignments, chronological transaction replay, analytical charts, and rolling success-rate alerts.

The MVP runs locally in Streamlit. It does not connect to real banks, payment gateways, messaging services, databases, or cloud deployment platforms.

## 2. Source Data

The source is `transaction_data.csv`, containing 1,000 transactions and these fields:

- Transaction ID
- Sender Account ID
- Receiver Account ID
- Transaction Amount
- Transaction Type
- Timestamp
- Transaction Status
- Fraud Flag
- Geolocation (Latitude/Longitude)
- Device Used
- Network Slice ID
- Latency (ms)
- Slice Bandwidth (Mbps)
- PIN Code

The source has no missing values and uses `Success` and `Failed` transaction statuses. Its observed overall success rate is 48.7%.

The original source file remains unchanged. A preparation command creates a derived dataset with one additional column named `Bank Gateway`.

## 3. Gateway Simulation

Each transaction receives exactly one of these neutral labels:

- Gateway A
- Gateway B
- Gateway C
- Gateway D

Assignment is uniformly random and uses a fixed seed so repeated preparation runs produce the same output. Gateway assignment must not alter transaction status or any other original value. The design deliberately creates no relationship between gateway and outcome.

The prepared data is sorted chronologically by parsed timestamp before being written to a separate CSV.

## 4. Architecture

The MVP uses Python 3, Pandas, NumPy, Streamlit, Plotly, and Pytest. It is divided into five focused components:

### `prepare_data.py`

Reads the source CSV, validates required columns, assigns gateways reproducibly, sorts transactions by timestamp, and writes the prepared CSV. It verifies that the row count and original transaction outcomes are unchanged.

### `data_loader.py`

Loads prepared data, normalizes internal column names and data types, and enforces the input schema. It returns a clean DataFrame to analytical consumers.

### `analytics.py`

Provides pure calculation functions for:

- Overall and gateway-level success rates
- Transaction and failure counts
- Average and percentile latency
- Transaction volume by gateway
- Breakdowns by device, transaction type, fraud flag, and latency band
- Chronological success-rate series

### `alerting.py`

Computes a full-dataset baseline success rate for each gateway. During chronological replay, it compares the baseline with that gateway's most recent 50 transactions.

An alert triggers when:

```text
baseline success rate - rolling success rate >= 0.10
```

This is a drop of at least 10 percentage points, not a relative 10% decrease. A gateway with fewer than 50 replayed transactions has insufficient history and cannot trigger an alert.

### `app.py`

Assembles the local Streamlit user interface, calls analytical modules, controls chronological replay, applies presentation filters, and displays alert results.

## 5. Data Flow

```text
Original Kaggle CSV
        |
        v
Data preparation and validation
        |
        v
Prepared CSV with Bank Gateway
        |
        v
Chronological replay subset
        |
        +--> Baseline and rolling alert calculation
        |
        +--> User-selected presentation filters
                  |
                  v
          KPIs, charts, and transaction table
```

The replay control chooses the number of chronologically ordered transactions considered available. This simulates transactions arriving over time without requiring a streaming service.

Alerts use the unfiltered replay subset. Dashboard filters affect only the displayed analysis. Consequently, selecting only failed transactions or one device type cannot create a false gateway alert.

## 6. Dashboard

The Streamlit dashboard contains:

- KPI cards for transaction count, overall success rate, failed transactions, average latency, and active alerts
- Filters for gateway, transaction type, device, status, and time range
- Gateway success-rate and transaction-volume comparisons
- Failure breakdowns by fraud flag, latency band, device, and transaction type
- A chronological success-rate chart
- An alert panel showing gateway baseline, rolling rate, percentage-point drop, history sufficiency, and trigger state
- A recent-transactions table
- A replay slider controlling how many chronological transactions are available

Empty filter results show an explanatory message rather than empty or broken charts.

## 7. Validation and Error Handling

Data preparation stops with a clear error when:

- The source file is missing, empty, or unreadable
- A required column is absent
- Transaction IDs are empty or duplicated
- Timestamps cannot be parsed
- Amount or latency is non-numeric or negative
- Status is not `Success` or `Failed`
- Prepared gateway values are outside Gateway A-D
- Any row lacks a gateway
- The prepared row count differs from the source
- Original transaction outcomes change

If prepared data fails validation at application startup, Streamlit displays a user-friendly error and stops safely.

## 8. Testing

Automated tests cover:

- Deterministic gateway assignment for a fixed seed
- Approximately uniform allocation across four gateways, using a tolerance appropriate for 1,000 random assignments
- Schema and value validation
- Preservation of source row count and transaction outcomes
- Overall and grouped success-rate calculations
- Rolling-window boundaries
- The exact 10-percentage-point alert threshold
- Insufficient gateway history
- Separation between display filters and alert input
- A Streamlit startup smoke test

Manual acceptance checks cover:

- Local application startup
- Replay slider behavior
- Dashboard filters and empty-filter handling
- Chart and KPI consistency
- Recent-transaction ordering
- Alert-panel states

Because gateway assignment is random, the dataset is not guaranteed to contain an alerting window. The application reports the observed calculations honestly and does not modify outcomes to force an alert.

## 9. Local Operation

The intended workflow is:

1. Create and activate a Python virtual environment.
2. Install pinned project dependencies.
3. Copy the Kaggle CSV into the documented local data location.
4. Run the preparation command to generate the gateway-enriched CSV.
5. Run automated tests.
6. Start the application with Streamlit.
7. Use the replay slider and filters to demonstrate monitoring behavior.

No cloud deployment is in scope.

## 10. Deliverables

- Reproducible data-preparation command
- Prepared transaction CSV generated locally
- Modular analytical and alerting code
- Local Streamlit dashboard
- Automated test suite
- README with setup, execution, metric definitions, and demo instructions
- Short customer-support guide explaining how to interpret failures and alerts

## 11. Out of Scope

- Real gateway or banking integrations
- Real-time message queues
- External Slack, Telegram, or email delivery
- Authentication and authorization
- Persistent database storage
- Predictive machine-learning models
- Production infrastructure, security hardening, and cloud deployment
- Claims that gateway assignment reveals real gateway performance

## 12. Acceptance Criteria

The design is complete when:

- The source CSV is preserved unchanged.
- The prepared dataset contains all 1,000 source transactions and one valid gateway per row.
- Preparation is reproducible with the documented seed.
- The dashboard runs locally and exposes all specified KPIs, filters, charts, replay controls, and alert states.
- Gateway baselines use the full prepared dataset.
- Rolling rates use the latest 50 replayed transactions for each gateway.
- Alerts trigger only at a drop of at least 10 percentage points.
- Presentation filters do not change alert calculations.
- Automated tests pass.
- Documentation explains setup, limitations, and the simulated nature of gateway data.
