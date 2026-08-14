"""Content-addressed persistence for synthetic routing benchmark evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True, slots=True)
class BenchmarkRunManifest:
    run_id: str
    configuration: dict[str, object]
    artifact_digests: dict[str, str]


@dataclass(frozen=True, slots=True)
class PersistedBenchmarkRun:
    manifest: BenchmarkRunManifest
    contexts: pd.DataFrame
    candidates: pd.DataFrame
    outcomes: pd.DataFrame
    report: pd.DataFrame


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class RoutingRunStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(
        self,
        *,
        contexts: pd.DataFrame,
        candidates: pd.DataFrame,
        outcomes: pd.DataFrame,
        report: pd.DataFrame,
        configuration: dict[str, object],
    ) -> BenchmarkRunManifest:
        config_bytes = json.dumps(
            configuration, sort_keys=True, separators=(",", ":")
        ).encode()
        frames = {
            "contexts": contexts,
            "candidates": candidates,
            "outcomes": outcomes,
            "report": report,
        }
        encoded = {
            name: frame.to_csv(index=False, lineterminator="\n").encode()
            for name, frame in frames.items()
        }
        digests = {name: _digest(content) for name, content in encoded.items()}
        run_id = _digest(
            config_bytes
            + "".join(f"{name}:{digests[name]}" for name in sorted(digests)).encode()
        )[:16]
        manifest = BenchmarkRunManifest(run_id, dict(configuration), digests)
        run_path = self.root / run_id
        run_path.mkdir(parents=True, exist_ok=True)
        for name, content in encoded.items():
            (run_path / f"{name}.csv").write_bytes(content)
        (run_path / "manifest.json").write_text(
            json.dumps(asdict(manifest), sort_keys=True, indent=2), encoding="utf-8"
        )
        return manifest

    def load(self, run_id: str) -> PersistedBenchmarkRun:
        run_path = self.root / run_id
        raw_manifest = json.loads(
            (run_path / "manifest.json").read_text(encoding="utf-8")
        )
        manifest = BenchmarkRunManifest(**raw_manifest)
        frames: dict[str, pd.DataFrame] = {}
        for name, expected in manifest.artifact_digests.items():
            path = run_path / f"{name}.csv"
            content = path.read_bytes()
            if _digest(content) != expected:
                raise ValueError(f"Artifact digest mismatch: {name}")
            frames[name] = pd.read_csv(path)
        contexts = frames["contexts"]
        for column in ("Timestamp", "Benchmark Timestamp"):
            if column in contexts:
                contexts[column] = pd.to_datetime(contexts[column], utc=True)
        candidates = frames["candidates"]
        for column in ("timestamp", "source_timestamp"):
            if column in candidates:
                candidates[column] = pd.to_datetime(candidates[column], utc=True)
        return PersistedBenchmarkRun(
            manifest,
            contexts,
            candidates,
            frames["outcomes"],
            frames["report"],
        )
