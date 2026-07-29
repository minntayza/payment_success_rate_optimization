from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from payment_dashboard.data_loader import (
    GATEWAYS,
    load_transactions,
    validate_transactions,
)

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
    if prepared["Transaction Status"].tolist() != source[
        "Transaction Status"
    ].tolist():
        raise RuntimeError("Transaction outcomes changed during preparation")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add simulated gateways to transactions"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    prepare_file(args.input, args.output, args.seed)
    print(f"Prepared transactions written to {args.output}")


if __name__ == "__main__":
    main()
