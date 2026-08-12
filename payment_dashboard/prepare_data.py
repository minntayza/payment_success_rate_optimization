from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from payment_dashboard.config import DEFAULT_SEED, GATEWAYS
from payment_dashboard.data_loader import (
    DataValidationError,
    load_transactions,
    validate_transactions,
)
from payment_dashboard.simulation import simulate_transactions

log = logging.getLogger(__name__)


def verify_source_manifest(source_path: Path, manifest_path: Path) -> None:
    """Verify the source filename, row count, and SHA-256 provenance contract."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataValidationError("Unable to read source manifest") from exc
    if source_path.name != manifest.get("filename"):
        raise DataValidationError("Source filename does not match manifest")
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if digest != manifest.get("sha256"):
        raise DataValidationError("Source checksum does not match manifest")
    row_count = len(pd.read_csv(source_path))
    if row_count != int(manifest.get("rows", -1)):
        raise DataValidationError("Source row count does not match manifest")


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
    prepared = simulate_transactions(source, seed=seed)
    validate_transactions(prepared, require_gateway=True)
    if len(prepared) != len(source):
        raise RuntimeError("Prepared row count differs from source")
    if (
        prepared["Source Transaction Status"].tolist()
        != source["Transaction Status"].tolist()
    ):
        raise RuntimeError("Source transaction statuses changed during preparation")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add simulated gateways to transactions"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/source-manifest.json")
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    verify_source_manifest(args.input, args.manifest)
    prepare_file(args.input, args.output, args.seed)
    log.info("Prepared transactions written to %s", args.output)


if __name__ == "__main__":
    main()
