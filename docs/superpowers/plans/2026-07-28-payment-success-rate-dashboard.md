# Payment Success Rate Optimization Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local academic Streamlit dashboard that enriches 1,000 Kaggle transactions with reproducibly random gateway labels, analyzes payment success, replays transactions chronologically, and detects 10-percentage-point drops over per-gateway 50-transaction windows.

**Architecture:** A small `payment_dashboard` package separates schema validation, data preparation, analytics, and alert detection from the Streamlit UI. The original CSV remains immutable; a command generates a prepared CSV, while Streamlit replays chronological prefixes and applies UI filters only after alert calculations.

**Tech Stack:** Python 3.11+, Pandas 2.2.3, NumPy 2.1.3, Streamlit 1.40.1, Plotly 5.24.1, Pytest 8.3.3

## Global Constraints

- Run entirely on the local machine; do not add cloud deployment.
- Treat `/Users/mintayza/Downloads/transaction_data.csv` as immutable source data.
- Add exactly one source column named `Bank Gateway`.
- Use only `Gateway A`, `Gateway B`, `Gateway C`, and `Gateway D`.
- Assign gateways uniformly at random with a fixed seed; never modify transaction outcomes.
- Compute each gateway baseline from the full prepared dataset.
- Compute rolling rates from the latest 50 replayed transactions for each gateway.
- Trigger at a drop of at least 0.10, meaning 10 percentage points.
- Do not trigger when a gateway has fewer than 50 replayed transactions.
- Keep dashboard presentation filters separate from alert input.
- Preserve the simulated nature of gateway data in all documentation and UI copy.

## Planned File Structure

```text
payment_success_rate_optimization/
├── .gitignore
├── README.md
├── requirements.txt
├── data/
│   ├── raw/
│   │   └── transaction_data.csv
│   └── processed/
│       └── .gitkeep
├── docs/
│   ├── customer-support-guide.md
│   └── superpowers/
│       ├── plans/
│       └── specs/
├── payment_dashboard/
│   ├── __init__.py
│   ├── alerting.py
│   ├── analytics.py
│   ├── app.py
│   ├── data_loader.py
│   └── prepare_data.py
└── tests/
    ├── conftest.py
    ├── test_alerting.py
    ├── test_analytics.py
    ├── test_app.py
    ├── test_data_loader.py
    └── test_prepare_data.py
```

---

### Task 1: Establish the Python Project and Test Fixture

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `payment_dashboard/__init__.py`
- Create: `tests/conftest.py`
- Create: `data/processed/.gitkeep`

**Interfaces:**
- Consumes: The existing Git repository and source CSV outside the repository.
- Produces: An importable `payment_dashboard` package and `sample_transactions: pd.DataFrame` Pytest fixture.

- [ ] **Step 1: Create the dependency and ignore configuration**

Create `requirements.txt`:

```text
numpy==2.1.3
pandas==2.2.3
plotly==5.24.1
pytest==8.3.3
streamlit==1.40.1
```

Create `.gitignore`:

```text
.DS_Store
.venv/
__pycache__/
.pytest_cache/
*.py[cod]
data/raw/*.csv
data/processed/*.csv
```

Create `payment_dashboard/__init__.py`:

```python
"""Local payment success-rate optimization dashboard."""
```

- [ ] **Step 2: Create and activate the virtual environment**

Run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Expected: all five dependencies install and `python --version` reports 3.11 or newer.

- [ ] **Step 3: Add a reusable transaction fixture**

Create `tests/conftest.py`:

```python
from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def sample_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Transaction ID": ["TX1", "TX2", "TX3", "TX4"],
            "Sender Account ID": ["S1", "S2", "S3", "S4"],
            "Receiver Account ID": ["R1", "R2", "R3", "R4"],
            "Transaction Amount": [100.0, 200.0, 300.0, 400.0],
            "Transaction Type": ["Transfer", "Deposit", "Withdrawal", "Transfer"],
            "Timestamp": [
                "2025-01-17 10:03:00",
                "2025-01-17 10:01:00",
                "2025-01-17 10:04:00",
                "2025-01-17 10:02:00",
            ],
            "Transaction Status": ["Success", "Failed", "Success", "Failed"],
            "Fraud Flag": [False, False, True, True],
            "Geolocation (Latitude/Longitude)": ["A", "B", "C", "D"],
            "Device Used": ["Mobile", "Desktop", "Mobile", "Desktop"],
            "Network Slice ID": ["Slice1", "Slice2", "Slice1", "Slice2"],
            "Latency (ms)": [4, 12, 8, 20],
            "Slice Bandwidth (Mbps)": [100, 110, 120, 130],
            "PIN Code": ["1111", "2222", "3333", "4444"],
        }
    )
```

- [ ] **Step 4: Verify the package and fixture load**

Run:

```bash
pytest --collect-only -q
python -c "import payment_dashboard"
```

Expected: Pytest completes collection without import errors, and the package import exits with status 0.

- [ ] **Step 5: Commit**

```bash
git add .gitignore requirements.txt payment_dashboard/__init__.py tests/conftest.py data/processed/.gitkeep
git commit -m "chore: initialize payment dashboard project"
```

---

### Task 2: Implement Strict Data Loading and Validation

**Files:**
- Create: `payment_dashboard/data_loader.py`
- Create: `tests/test_data_loader.py`

**Interfaces:**
- Consumes: A `str | pathlib.Path` pointing to a raw or prepared CSV.
- Produces: `load_transactions(path: str | Path, require_gateway: bool = True) -> pd.DataFrame` and `validate_transactions(frame: pd.DataFrame, require_gateway: bool = True) -> None`.

- [ ] **Step 1: Write validation tests**

Create `tests/test_data_loader.py`:

```python
from __future__ import annotations

import pandas as pd
import pytest

from payment_dashboard.data_loader import DataValidationError, validate_transactions


def test_valid_raw_data_passes_without_gateway(sample_transactions):
    validate_transactions(sample_transactions, require_gateway=False)


def test_duplicate_transaction_id_is_rejected(sample_transactions):
    duplicated = sample_transactions.copy()
    duplicated.loc[1, "Transaction ID"] = "TX1"

    with pytest.raises(DataValidationError, match="unique"):
        validate_transactions(duplicated, require_gateway=False)


def test_invalid_status_is_rejected(sample_transactions):
    invalid = sample_transactions.copy()
    invalid.loc[0, "Transaction Status"] = "Pending"

    with pytest.raises(DataValidationError, match="Transaction Status"):
        validate_transactions(invalid, require_gateway=False)


def test_missing_gateway_is_rejected_for_prepared_data(sample_transactions):
    with pytest.raises(DataValidationError, match="Bank Gateway"):
        validate_transactions(sample_transactions, require_gateway=True)


def test_negative_latency_is_rejected(sample_transactions):
    invalid = sample_transactions.copy()
    invalid.loc[0, "Latency (ms)"] = -1

    with pytest.raises(DataValidationError, match="Latency"):
        validate_transactions(invalid, require_gateway=False)
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```bash
pytest tests/test_data_loader.py -v
```

Expected: collection fails because `payment_dashboard.data_loader` does not exist.

- [ ] **Step 3: Implement schema validation and loading**

Create `payment_dashboard/data_loader.py`:

```python
from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "Transaction ID",
    "Sender Account ID",
    "Receiver Account ID",
    "Transaction Amount",
    "Transaction Type",
    "Timestamp",
    "Transaction Status",
    "Fraud Flag",
    "Geolocation (Latitude/Longitude)",
    "Device Used",
    "Network Slice ID",
    "Latency (ms)",
    "Slice Bandwidth (Mbps)",
    "PIN Code",
}
GATEWAYS = ("Gateway A", "Gateway B", "Gateway C", "Gateway D")
STATUSES = {"Success", "Failed"}


class DataValidationError(ValueError):
    """Raised when transaction data violates the project schema."""


def validate_transactions(
    frame: pd.DataFrame,
    require_gateway: bool = True,
) -> None:
    required = REQUIRED_COLUMNS | ({"Bank Gateway"} if require_gateway else set())
    missing = sorted(required - set(frame.columns))
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")
    if frame.empty:
        raise DataValidationError("Transaction data is empty")
    if frame["Transaction ID"].isna().any() or frame["Transaction ID"].eq("").any():
        raise DataValidationError("Transaction ID must be non-empty")
    if not frame["Transaction ID"].is_unique:
        raise DataValidationError("Transaction ID must be unique")
    if not set(frame["Transaction Status"].dropna()).issubset(STATUSES):
        raise DataValidationError("Transaction Status must be Success or Failed")

    for column in ("Transaction Amount", "Latency (ms)"):
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or values.lt(0).any():
            raise DataValidationError(f"{column} must be numeric and non-negative")

    timestamps = pd.to_datetime(frame["Timestamp"], errors="coerce")
    if timestamps.isna().any():
        raise DataValidationError("Timestamp contains invalid values")

    if require_gateway:
        gateways = set(frame["Bank Gateway"].dropna())
        if frame["Bank Gateway"].isna().any() or not gateways.issubset(GATEWAYS):
            raise DataValidationError(
                "Bank Gateway must contain exactly one value from Gateway A-D per row"
            )


def load_transactions(
    path: str | Path,
    require_gateway: bool = True,
) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.is_file():
        raise DataValidationError(f"CSV file does not exist: {csv_path}")
    try:
        frame = pd.read_csv(csv_path, dtype={"PIN Code": "string"})
    except (OSError, pd.errors.ParserError) as exc:
        raise DataValidationError(f"Unable to read CSV: {csv_path}") from exc

    validate_transactions(frame, require_gateway=require_gateway)
    result = frame.copy()
    result["Timestamp"] = pd.to_datetime(result["Timestamp"])
    result["Transaction Amount"] = pd.to_numeric(result["Transaction Amount"])
    result["Latency (ms)"] = pd.to_numeric(result["Latency (ms)"])
    result["Fraud Flag"] = result["Fraud Flag"].astype("boolean")
    return result.sort_values("Timestamp", kind="stable").reset_index(drop=True)
```

- [ ] **Step 4: Run validation tests**

Run:

```bash
pytest tests/test_data_loader.py -v
```

Expected: all five tests pass.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/data_loader.py tests/test_data_loader.py
git commit -m "feat: validate and load transaction data"
```

---

### Task 3: Build Reproducible Gateway-Enrichment Command

**Files:**
- Create: `payment_dashboard/prepare_data.py`
- Create: `tests/test_prepare_data.py`
- Create locally, do not commit: `data/raw/transaction_data.csv`
- Generate locally, do not commit: `data/processed/transactions_with_gateways.csv`

**Interfaces:**
- Consumes: `load_transactions(path, require_gateway=False)`.
- Produces: `assign_gateways(frame: pd.DataFrame, seed: int = 20260728) -> pd.DataFrame` and CLI arguments `--input`, `--output`, and `--seed`.

- [ ] **Step 1: Write gateway-assignment tests**

Create `tests/test_prepare_data.py`:

```python
from __future__ import annotations

import pandas as pd

from payment_dashboard.prepare_data import assign_gateways


def test_assignment_is_reproducible(sample_transactions):
    first = assign_gateways(sample_transactions, seed=42)
    second = assign_gateways(sample_transactions, seed=42)

    assert first["Bank Gateway"].tolist() == second["Bank Gateway"].tolist()


def test_assignment_preserves_source_data(sample_transactions):
    prepared = assign_gateways(sample_transactions, seed=42)

    pd.testing.assert_frame_equal(
        prepared.drop(columns=["Bank Gateway"]),
        sample_transactions.sort_values("Timestamp", kind="stable").reset_index(drop=True),
        check_dtype=False,
    )


def test_all_gateway_labels_are_valid(sample_transactions):
    prepared = assign_gateways(sample_transactions, seed=42)

    assert set(prepared["Bank Gateway"]).issubset(
        {"Gateway A", "Gateway B", "Gateway C", "Gateway D"}
    )


def test_distribution_is_reasonably_uniform():
    frame = pd.DataFrame(
        {
            "Transaction ID": [f"TX{i}" for i in range(1000)],
            "Timestamp": pd.date_range("2025-01-01", periods=1000, freq="min"),
        }
    )

    prepared = assign_gateways(frame, seed=20260728)
    counts = prepared["Bank Gateway"].value_counts()

    assert counts.between(200, 300).all()
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```bash
pytest tests/test_prepare_data.py -v
```

Expected: collection fails because `payment_dashboard.prepare_data` does not exist.

- [ ] **Step 3: Implement deterministic assignment and CLI**

Create `payment_dashboard/prepare_data.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from payment_dashboard.data_loader import GATEWAYS, load_transactions, validate_transactions

DEFAULT_SEED = 20260728


def assign_gateways(
    frame: pd.DataFrame,
    seed: int = DEFAULT_SEED,
) -> pd.DataFrame:
    result = frame.sort_values("Timestamp", kind="stable").reset_index(drop=True).copy()
    generator = np.random.default_rng(seed)
    result["Bank Gateway"] = generator.choice(GATEWAYS, size=len(result), replace=True)
    return result


def prepare_file(input_path: Path, output_path: Path, seed: int) -> None:
    source = load_transactions(input_path, require_gateway=False)
    prepared = assign_gateways(source, seed=seed)
    validate_transactions(prepared, require_gateway=True)
    if len(prepared) != len(source):
        raise RuntimeError("Prepared row count differs from source")
    if prepared["Transaction Status"].tolist() != source["Transaction Status"].tolist():
        raise RuntimeError("Transaction outcomes changed during preparation")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Add simulated gateways to transactions")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    prepare_file(args.input, args.output, args.seed)
    print(f"Prepared transactions written to {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests and prepare the real dataset**

Run:

```bash
pytest tests/test_prepare_data.py -v
mkdir -p data/raw data/processed
cp /Users/mintayza/Downloads/transaction_data.csv data/raw/transaction_data.csv
python -m payment_dashboard.prepare_data \
  --input data/raw/transaction_data.csv \
  --output data/processed/transactions_with_gateways.csv \
  --seed 20260728
```

Expected: four tests pass and the CLI reports the prepared output path.

- [ ] **Step 5: Verify the real prepared file**

Run:

```bash
python -c "import pandas as pd; p=pd.read_csv('data/processed/transactions_with_gateways.csv'); print(len(p)); print(p['Bank Gateway'].value_counts().sort_index()); print(p['Transaction Status'].value_counts())"
```

Expected: 1,000 rows; each gateway count is between 200 and 300; status counts remain 487 `Success` and 513 `Failed`.

- [ ] **Step 6: Commit**

```bash
git add payment_dashboard/prepare_data.py tests/test_prepare_data.py
git commit -m "feat: add reproducible gateway enrichment"
```

---

### Task 4: Implement Analytical Metrics

**Files:**
- Create: `payment_dashboard/analytics.py`
- Create: `tests/test_analytics.py`

**Interfaces:**
- Consumes: A validated prepared `pd.DataFrame`.
- Produces: `add_latency_band`, `apply_filters`, `summary_metrics`, `gateway_summary`, `failure_breakdown`, and `success_rate_series`.

- [ ] **Step 1: Write analytical tests**

Create `tests/test_analytics.py`:

```python
from __future__ import annotations

import pandas as pd

from payment_dashboard.analytics import (
    add_latency_band,
    apply_filters,
    failure_breakdown,
    gateway_summary,
    summary_metrics,
)


def prepared_fixture(sample_transactions):
    frame = sample_transactions.copy()
    frame["Timestamp"] = pd.to_datetime(frame["Timestamp"])
    frame["Bank Gateway"] = ["Gateway A", "Gateway A", "Gateway B", "Gateway B"]
    return frame


def test_summary_metrics(sample_transactions):
    metrics = summary_metrics(prepared_fixture(sample_transactions))

    assert metrics == {
        "transaction_count": 4,
        "success_rate": 0.5,
        "failed_count": 2,
        "average_latency_ms": 11.0,
        "p95_latency_ms": 18.8,
    }


def test_gateway_summary(sample_transactions):
    result = gateway_summary(prepared_fixture(sample_transactions)).set_index(
        "Bank Gateway"
    )

    assert result.loc["Gateway A", "transaction_count"] == 2
    assert result.loc["Gateway A", "success_rate"] == 0.5


def test_filters_can_return_empty_frame(sample_transactions):
    result = apply_filters(
        prepared_fixture(sample_transactions),
        gateways=["Gateway D"],
        transaction_types=[],
        devices=[],
        statuses=[],
        start=None,
        end=None,
    )

    assert result.empty


def test_failure_breakdown_counts_only_failures(sample_transactions):
    frame = add_latency_band(prepared_fixture(sample_transactions))
    result = failure_breakdown(frame, dimension="Latency Band")

    assert result["failed_count"].sum() == 2
    assert set(result["Latency Band"]) <= {"0-5 ms", "6-10 ms", "11-15 ms", "16+ ms"}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_analytics.py -v
```

Expected: collection fails because `payment_dashboard.analytics` does not exist.

- [ ] **Step 3: Implement pure analytical functions**

Create `payment_dashboard/analytics.py`:

```python
from __future__ import annotations

from datetime import date

import pandas as pd


def add_latency_band(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["Latency Band"] = pd.cut(
        result["Latency (ms)"],
        bins=[-float("inf"), 5, 10, 15, float("inf")],
        labels=["0-5 ms", "6-10 ms", "11-15 ms", "16+ ms"],
    )
    return result


def summary_metrics(frame: pd.DataFrame) -> dict[str, int | float]:
    count = len(frame)
    success_rate = frame["Transaction Status"].eq("Success").mean() if count else 0.0
    return {
        "transaction_count": count,
        "success_rate": float(success_rate),
        "failed_count": int(frame["Transaction Status"].eq("Failed").sum()),
        "average_latency_ms": float(frame["Latency (ms)"].mean()) if count else 0.0,
        "p95_latency_ms": float(frame["Latency (ms)"].quantile(0.95)) if count else 0.0,
    }


def gateway_summary(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.assign(
        is_success=frame["Transaction Status"].eq("Success").astype(int)
    )
    return (
        working.groupby("Bank Gateway", observed=True)
        .agg(
            transaction_count=("Transaction ID", "count"),
            success_rate=("is_success", "mean"),
            average_latency_ms=("Latency (ms)", "mean"),
        )
        .reset_index()
        .sort_values("Bank Gateway")
    )


def failure_breakdown(frame: pd.DataFrame, dimension: str) -> pd.DataFrame:
    failures = frame.loc[frame["Transaction Status"].eq("Failed")]
    return (
        failures.groupby(dimension, observed=True)
        .size()
        .rename("failed_count")
        .reset_index()
        .sort_values("failed_count", ascending=False)
    )


def success_rate_series(frame: pd.DataFrame, frequency: str = "15min") -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["Timestamp", "success_rate", "transaction_count"])
    working = frame.assign(
        is_success=frame["Transaction Status"].eq("Success").astype(int)
    ).set_index("Timestamp")
    return (
        working.resample(frequency)
        .agg(success_rate=("is_success", "mean"), transaction_count=("is_success", "size"))
        .dropna(subset=["success_rate"])
        .reset_index()
    )


def apply_filters(
    frame: pd.DataFrame,
    gateways: list[str],
    transaction_types: list[str],
    devices: list[str],
    statuses: list[str],
    start: date | None,
    end: date | None,
) -> pd.DataFrame:
    mask = pd.Series(True, index=frame.index)
    for column, selected in (
        ("Bank Gateway", gateways),
        ("Transaction Type", transaction_types),
        ("Device Used", devices),
        ("Transaction Status", statuses),
    ):
        if selected:
            mask &= frame[column].isin(selected)
    if start is not None:
        mask &= frame["Timestamp"].dt.date >= start
    if end is not None:
        mask &= frame["Timestamp"].dt.date <= end
    return frame.loc[mask].copy()
```

- [ ] **Step 4: Run analytical tests**

Run:

```bash
pytest tests/test_analytics.py -v
```

Expected: all four tests pass.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/analytics.py tests/test_analytics.py
git commit -m "feat: calculate payment success analytics"
```

---

### Task 5: Implement Baseline and Rolling Alert Detection

**Files:**
- Create: `payment_dashboard/alerting.py`
- Create: `tests/test_alerting.py`

**Interfaces:**
- Consumes: The full prepared frame and the current unfiltered chronological replay frame.
- Produces: `calculate_baselines(full_frame: pd.DataFrame) -> pd.Series` and `evaluate_alerts(full_frame: pd.DataFrame, replay_frame: pd.DataFrame, window_size: int = 50, threshold: float = 0.10) -> pd.DataFrame`.

- [ ] **Step 1: Write alert tests**

Create `tests/test_alerting.py`:

```python
from __future__ import annotations

import pandas as pd

from payment_dashboard.alerting import evaluate_alerts


def transactions(gateway: str, successes: int, failures: int, prefix: str):
    statuses = ["Success"] * successes + ["Failed"] * failures
    return pd.DataFrame(
        {
            "Transaction ID": [f"{prefix}{index}" for index in range(len(statuses))],
            "Bank Gateway": gateway,
            "Transaction Status": statuses,
        }
    )


def test_exact_ten_point_drop_triggers():
    full = transactions("Gateway A", 70, 30, "F")
    replay = transactions("Gateway A", 30, 20, "R")

    result = evaluate_alerts(full, replay).iloc[0]

    assert result["baseline_rate"] == 0.7
    assert result["rolling_rate"] == 0.6
    assert result["drop"] == 0.1
    assert bool(result["is_alert"]) is True


def test_less_than_ten_point_drop_does_not_trigger():
    full = transactions("Gateway A", 70, 30, "F")
    replay = transactions("Gateway A", 31, 19, "R")

    assert bool(evaluate_alerts(full, replay).iloc[0]["is_alert"]) is False


def test_fewer_than_fifty_gateway_transactions_is_insufficient():
    full = transactions("Gateway A", 70, 30, "F")
    replay = transactions("Gateway A", 29, 20, "R")

    result = evaluate_alerts(full, replay).iloc[0]

    assert bool(result["has_sufficient_history"]) is False
    assert bool(result["is_alert"]) is False
    assert pd.isna(result["rolling_rate"])


def test_latest_fifty_transactions_are_used():
    full = transactions("Gateway A", 70, 30, "F")
    older = transactions("Gateway A", 50, 0, "O")
    latest = transactions("Gateway A", 25, 25, "L")

    result = evaluate_alerts(full, pd.concat([older, latest])).iloc[0]

    assert result["rolling_rate"] == 0.5
    assert bool(result["is_alert"]) is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_alerting.py -v
```

Expected: collection fails because `payment_dashboard.alerting` does not exist.

- [ ] **Step 3: Implement alert evaluation**

Create `payment_dashboard/alerting.py`:

```python
from __future__ import annotations

import pandas as pd

from payment_dashboard.data_loader import GATEWAYS


def calculate_baselines(full_frame: pd.DataFrame) -> pd.Series:
    return (
        full_frame.assign(
            is_success=full_frame["Transaction Status"].eq("Success").astype(int)
        )
        .groupby("Bank Gateway", observed=True)["is_success"]
        .mean()
        .reindex(GATEWAYS)
    )


def evaluate_alerts(
    full_frame: pd.DataFrame,
    replay_frame: pd.DataFrame,
    window_size: int = 50,
    threshold: float = 0.10,
) -> pd.DataFrame:
    baselines = calculate_baselines(full_frame)
    records: list[dict[str, object]] = []
    for gateway in GATEWAYS:
        gateway_rows = replay_frame.loc[
            replay_frame["Bank Gateway"].eq(gateway)
        ]
        sufficient = len(gateway_rows) >= window_size
        rolling_rate = (
            gateway_rows.tail(window_size)["Transaction Status"].eq("Success").mean()
            if sufficient
            else float("nan")
        )
        baseline = float(baselines[gateway])
        drop = round(baseline - float(rolling_rate), 12) if sufficient else float("nan")
        records.append(
            {
                "Bank Gateway": gateway,
                "baseline_rate": baseline,
                "rolling_rate": rolling_rate,
                "drop": drop,
                "has_sufficient_history": sufficient,
                "is_alert": sufficient and drop >= threshold,
            }
        )
    return pd.DataFrame.from_records(records)
```

- [ ] **Step 4: Run alert tests**

Run:

```bash
pytest tests/test_alerting.py -v
```

Expected: all four tests pass.

- [ ] **Step 5: Commit**

```bash
git add payment_dashboard/alerting.py tests/test_alerting.py
git commit -m "feat: detect rolling gateway success drops"
```

---

### Task 6: Assemble the Streamlit Dashboard

**Files:**
- Create: `payment_dashboard/app.py`
- Create: `tests/test_app.py`

**Interfaces:**
- Consumes: `load_transactions`, analytics functions, and `evaluate_alerts`.
- Produces: A local Streamlit page launched with `streamlit run payment_dashboard/app.py`.

- [ ] **Step 1: Write UI helper tests**

Create `tests/test_app.py`:

```python
from __future__ import annotations

import pandas as pd

from payment_dashboard.app import build_dashboard_state


def test_alerts_ignore_display_filters(sample_transactions):
    full = pd.concat([sample_transactions] * 60, ignore_index=True)
    full["Transaction ID"] = [f"TX{i}" for i in range(len(full))]
    full["Timestamp"] = pd.date_range("2025-01-01", periods=len(full), freq="min")
    full["Bank Gateway"] = [
        f"Gateway {chr(65 + (i % 4))}" for i in range(len(full))
    ]
    replay = full.iloc[:220]

    state = build_dashboard_state(
        full_frame=full,
        replay_count=220,
        gateways=["Gateway D"],
        transaction_types=[],
        devices=[],
        statuses=["Failed"],
        start=None,
        end=None,
    )

    assert len(state["alert_input"]) == 220
    assert set(state["display_frame"]["Bank Gateway"]) <= {"Gateway D"}
    assert set(state["display_frame"]["Transaction Status"]) <= {"Failed"}
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```bash
pytest tests/test_app.py -v
```

Expected: collection fails because `payment_dashboard.app` does not exist.

- [ ] **Step 3: Implement testable dashboard state**

Create the imports and state builder at the top of `payment_dashboard/app.py`:

```python
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from payment_dashboard.alerting import evaluate_alerts
from payment_dashboard.analytics import (
    add_latency_band,
    apply_filters,
    failure_breakdown,
    gateway_summary,
    success_rate_series,
    summary_metrics,
)
from payment_dashboard.data_loader import DataValidationError, load_transactions

DEFAULT_DATA_PATH = Path("data/processed/transactions_with_gateways.csv")


def build_dashboard_state(
    full_frame: pd.DataFrame,
    replay_count: int,
    gateways: list[str],
    transaction_types: list[str],
    devices: list[str],
    statuses: list[str],
    start: date | None,
    end: date | None,
) -> dict[str, object]:
    replay_frame = full_frame.iloc[:replay_count].copy()
    display_frame = apply_filters(
        replay_frame,
        gateways,
        transaction_types,
        devices,
        statuses,
        start,
        end,
    )
    display_frame = add_latency_band(display_frame)
    return {
        "alert_input": replay_frame,
        "display_frame": display_frame,
        "alerts": evaluate_alerts(full_frame, replay_frame),
    }
```

- [ ] **Step 4: Run the helper test**

Run:

```bash
pytest tests/test_app.py -v
```

Expected: the filter-separation test passes.

- [ ] **Step 5: Add the Streamlit page**

Append to `payment_dashboard/app.py`:

```python
def render_app() -> None:
    st.set_page_config(page_title="Payment Success Monitor", layout="wide")
    st.title("Payment Success Rate Optimization Dashboard")
    st.caption(
        "Academic demo: gateway labels are simulated and do not represent "
        "real gateway performance."
    )

    data_path = Path(os.getenv("PAYMENT_DATA_PATH", str(DEFAULT_DATA_PATH)))
    try:
        full_frame = load_transactions(data_path, require_gateway=True)
    except DataValidationError as exc:
        st.error(str(exc))
        st.stop()

    replay_count = st.sidebar.slider(
        "Replayed transactions",
        min_value=1,
        max_value=len(full_frame),
        value=len(full_frame),
    )
    gateways = st.sidebar.multiselect(
        "Gateway",
        sorted(full_frame["Bank Gateway"].unique()),
    )
    transaction_types = st.sidebar.multiselect(
        "Transaction type",
        sorted(full_frame["Transaction Type"].unique()),
    )
    devices = st.sidebar.multiselect(
        "Device",
        sorted(full_frame["Device Used"].unique()),
    )
    statuses = st.sidebar.multiselect(
        "Status",
        sorted(full_frame["Transaction Status"].unique()),
    )
    minimum_date = full_frame["Timestamp"].min().date()
    maximum_date = full_frame["Timestamp"].max().date()
    selected_dates = st.sidebar.date_input(
        "Date range",
        value=(minimum_date, maximum_date),
        min_value=minimum_date,
        max_value=maximum_date,
    )
    start, end = (
        selected_dates
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2
        else (minimum_date, maximum_date)
    )

    state = build_dashboard_state(
        full_frame,
        replay_count,
        gateways,
        transaction_types,
        devices,
        statuses,
        start,
        end,
    )
    display_frame = state["display_frame"]
    alerts = state["alerts"]

    active_alerts = int(alerts["is_alert"].sum())
    metrics = summary_metrics(display_frame)
    columns = st.columns(5)
    columns[0].metric("Transactions", f"{metrics['transaction_count']:,}")
    columns[1].metric("Success rate", f"{metrics['success_rate']:.1%}")
    columns[2].metric("Failed", f"{metrics['failed_count']:,}")
    columns[3].metric("Average latency", f"{metrics['average_latency_ms']:.1f} ms")
    columns[4].metric("Active alerts", active_alerts)

    st.subheader("Gateway alerts")
    alert_display = alerts.copy()
    for column in ("baseline_rate", "rolling_rate", "drop"):
        alert_display[column] = alert_display[column].map(
            lambda value: "Insufficient history" if pd.isna(value) else f"{value:.1%}"
        )
    st.dataframe(alert_display, use_container_width=True, hide_index=True)

    if display_frame.empty:
        st.info("No transactions match the selected filters.")
        return

    gateways_chart = gateway_summary(display_frame)
    left, right = st.columns(2)
    left.plotly_chart(
        px.bar(
            gateways_chart,
            x="Bank Gateway",
            y="success_rate",
            title="Success rate by gateway",
            range_y=[0, 1],
        ),
        use_container_width=True,
    )
    right.plotly_chart(
        px.bar(
            gateways_chart,
            x="Bank Gateway",
            y="transaction_count",
            title="Transaction volume by gateway",
        ),
        use_container_width=True,
    )

    series = success_rate_series(display_frame)
    st.plotly_chart(
        px.line(
            series,
            x="Timestamp",
            y="success_rate",
            markers=True,
            title="Success rate over time",
        ),
        use_container_width=True,
    )

    for dimension in (
        "Fraud Flag",
        "Latency Band",
        "Device Used",
        "Transaction Type",
    ):
        breakdown = failure_breakdown(display_frame, dimension)
        st.plotly_chart(
            px.bar(
                breakdown,
                x=dimension,
                y="failed_count",
                title=f"Failures by {dimension}",
            ),
            use_container_width=True,
        )

    st.subheader("Recent transactions")
    st.dataframe(
        display_frame.sort_values("Timestamp", ascending=False).head(25),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    render_app()
```

- [ ] **Step 6: Run all tests and launch the dashboard**

Run:

```bash
pytest -q
streamlit run payment_dashboard/app.py
```

Expected: all tests pass; Streamlit prints a local URL; the browser page shows five KPIs, filters, alert states, charts, and recent transactions.

- [ ] **Step 7: Manually verify dashboard behavior**

Check these exact behaviors:

1. Set replay count below 50: every gateway shows insufficient history.
2. Move replay count to 1,000: KPI transaction count shows 1,000 when filters are empty.
3. Select `Gateway A`: charts and recent transactions contain only Gateway A.
4. Select `Failed`: displayed success rate becomes 0%, but gateway alerts remain unchanged.
5. Choose a filter combination with no rows: the dashboard shows the empty-result message and no broken chart.
6. Confirm the page caption says gateway labels are simulated.

- [ ] **Step 8: Commit**

```bash
git add payment_dashboard/app.py tests/test_app.py
git commit -m "feat: add local Streamlit monitoring dashboard"
```

---

### Task 7: Add User and Customer-Support Documentation

**Files:**
- Create: `README.md`
- Create: `docs/customer-support-guide.md`

**Interfaces:**
- Consumes: The completed CLI and dashboard behavior.
- Produces: Reproducible setup, demo, metric, limitation, and support instructions.

- [ ] **Step 1: Write the README**

Create `README.md` with these commands and definitions:

```markdown
# Payment Success Rate Optimization Dashboard

This academic MVP adds reproducibly random Gateway A-D labels to a Kaggle
transaction dataset and demonstrates local payment monitoring. The gateway
labels are simulated and must not be interpreted as real gateway performance.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p data/raw data/processed
cp /Users/mintayza/Downloads/transaction_data.csv data/raw/transaction_data.csv
```

## Prepare data

```bash
python -m payment_dashboard.prepare_data \
  --input data/raw/transaction_data.csv \
  --output data/processed/transactions_with_gateways.csv \
  --seed 20260728
```

## Test

```bash
pytest -q
```

## Run

```bash
streamlit run payment_dashboard/app.py
```

## Metric definitions

- Success rate: successful transactions divided by all transactions in scope.
- Gateway baseline: gateway success rate across the full prepared dataset.
- Rolling rate: success rate across the latest 50 replayed transactions for one gateway.
- Alert: baseline minus rolling rate is at least 10 percentage points.
- Insufficient history: fewer than 50 replayed transactions for a gateway.

Dashboard filters change displayed analytics but do not change gateway alert
calculations. The replay slider simulates chronological arrival; it does not
provide a production streaming pipeline.
```

- [ ] **Step 2: Write the support guide**

Create `docs/customer-support-guide.md`:

```markdown
# Customer Support Guide

## Reading the dashboard

Use the recent-transactions table to locate a transaction by transaction ID.
Confirm its status, gateway, timestamp, device, latency, and fraud flag before
responding to a customer.

## Failure interpretation

- High latency can indicate simulated network or gateway delay.
- `Fraud Flag = True` indicates the record was flagged, but does not prove fraud.
- Failed deposits, withdrawals, and transfers should be grouped by transaction
  type to identify broad patterns.
- The source dataset does not contain explicit insufficient-balance or incorrect
  PIN/OTP failure-reason fields, so support staff must not claim either cause.

## Alert interpretation

An alert means a gateway's latest 50 replayed transactions are at least 10
percentage points below its full-dataset baseline. It is a demonstration signal,
not evidence of a real bank outage. If history is insufficient, wait until 50
transactions have been replayed for that gateway.

## Suggested response workflow

1. Search for the transaction ID in the recent-transactions table.
2. Record the status, timestamp, gateway, latency, device, and fraud flag.
3. Check whether the gateway alert panel shows an active alert.
4. Explain that the dashboard is a simulated academic environment.
5. Escalate only as part of the classroom demonstration procedure.
```

- [ ] **Step 3: Verify documentation commands**

Run:

```bash
python -m payment_dashboard.prepare_data \
  --input data/raw/transaction_data.csv \
  --output data/processed/transactions_with_gateways.csv \
  --seed 20260728
pytest -q
```

Expected: data preparation succeeds and the complete test suite passes.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/customer-support-guide.md
git commit -m "docs: add setup and support guidance"
```

---

### Task 8: Complete End-to-End Acceptance Verification

**Files:**
- Modify only if verification discovers a defect: the smallest responsible source or test file.

**Interfaces:**
- Consumes: The complete project.
- Produces: Evidence that the local MVP satisfies the approved design.

- [ ] **Step 1: Run the complete automated suite**

Run:

```bash
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Verify source preservation and prepared schema**

Run:

```bash
python -c "import pandas as pd; raw=pd.read_csv('data/raw/transaction_data.csv').set_index('Transaction ID'); prepared=pd.read_csv('data/processed/transactions_with_gateways.csv').set_index('Transaction ID'); assert len(raw)==len(prepared)==1000; assert set(raw.index)==set(prepared.index); assert raw['Transaction Status'].sort_index().equals(prepared['Transaction Status'].sort_index()); assert set(prepared['Bank Gateway'])=={'Gateway A','Gateway B','Gateway C','Gateway D'}; print('data acceptance passed')"
```

Expected: `data acceptance passed`.

- [ ] **Step 3: Run the local app**

Run:

```bash
streamlit run payment_dashboard/app.py
```

Expected: the application starts without a traceback and all Task 6 manual checks pass.

- [ ] **Step 4: Review repository scope**

Run:

```bash
git status --short
git log --oneline --decorate -10
```

Expected: source and documentation changes are committed; ignored raw and processed CSV files do not appear; no unrelated files are staged.

- [ ] **Step 5: Commit verification fixes if any were required**

If verification required a focused correction, run:

```bash
git add payment_dashboard tests README.md docs/customer-support-guide.md
git commit -m "fix: satisfy dashboard acceptance checks"
```

If no correction was required, do not create an empty commit.

## Final Demonstration Sequence

1. Start Streamlit locally.
2. Explain that the original Kaggle outcomes remain unchanged and gateways are randomly simulated.
3. Show the full-dataset KPI values, including 1,000 transactions and the observed success rate.
4. Compare success rate, volume, and latency across Gateway A-D.
5. Move the replay slider backward to show insufficient-history states.
6. Move it forward to show rolling calculations and any naturally occurring alert.
7. Apply gateway and status filters and show that charts change while alerts remain stable.
8. Show failure breakdowns and the recent-transactions table.
9. Close by explaining the MVP limitation: it monitors historical simulated data and makes no claim about real banks.
