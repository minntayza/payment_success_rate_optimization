import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[1]
GUIDE = ROOT / "docs" / "project-function-and-data-guide.md"
REQUIRED_HEADINGS = {
    "# Payment Success Rate Optimization: Project Function and Dataset Guide",
    "## 1. Project overview",
    "## 2. Dashboard tour",
    "## 3. Dataset lifecycle",
    "## 4. Dataset fields and management controls",
    "## 5. Functional architecture",
    "## 6. Analytical definitions",
    "## 7. How to run and verify the project",
    "## 8. Interpretation and troubleshooting",
}


def _invalid_local_targets(text: str) -> list[str]:
    targets = re.findall(r"\[[^]]+\]\((?!https?://|#)([^)]+)\)", text)
    invalid = []
    for target in targets:
        path = Path(target)
        resolved = (GUIDE.parent / path).resolve()
        if (
            path.is_absolute()
            or not resolved.is_relative_to(ROOT.resolve())
            or not resolved.exists()
        ):
            invalid.append(target)
    return invalid


def test_project_guide_has_required_structure() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    assert set(text.splitlines()) >= REQUIRED_HEADINGS
    assert "```mermaid" in text
    assert "data analysis and management" in text.lower()
    assert "synthetic" in text.lower()
    assert "non-causal" in text.lower()


def test_project_guide_local_links_resolve() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    targets = re.findall(r"\[[^]]+\]\((?!https?://|#)([^)]+)\)", text)
    assert targets
    assert _invalid_local_targets(text) == []


def test_project_guide_link_contract_rejects_absolute_and_escaping_targets() -> None:
    absolute = str(ROOT / "README.md")
    unsafe_text = f"[absolute]({absolute}) and [escape](../..)"
    assert _invalid_local_targets(unsafe_text) == [absolute, "../.."]


def test_project_guide_keeps_routing_inputs_outside_dashboard_snapshot() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    assert 'VALID --> LOCALCTX["Validated prepared local routing contexts"]' in text
    assert 'MONGO --> LIVECTX["Full active MongoDB routing contexts"]' in text
    assert "LOCALCTX --> ROUTING" in text
    assert "LIVECTX --> ROUTING" in text
    assert "SNAP --> ROUTING" not in text
    assert "SNAP --> ANALYTICS" not in text
    assert "PANDAS --> PRESULT" in text
    assert "MONGO --> MRESULT" in text
    assert "PRESULT --> SNAP" in text
    assert "MRESULT --> SNAP" in text
    assert (
        "Each repository computes metrics, trends, failure summary, alerts, and "
        "transaction page data before assembling `DashboardSnapshot` as the "
        "presentation contract."
    ) in " ".join(text.split())


def test_project_guide_describes_checksum_consistency_without_security_claims() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "checksum consistency verification" in normalized
    assert (
        "Changing both an artifact and its unsigned mutable manifest can pass "
        "this check."
    ) in normalized
    assert "authenticated integrity or nonrepudiation" in normalized
    assert "rejects tampering" not in text


def test_project_guide_distinguishes_repository_pagination() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "server-paginated" not in text
    assert "pandas slices a sorted in-memory frame" in normalized
    assert "MongoDB performs server-side pagination" in normalized


def test_project_guide_documents_destructive_clean_target() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "`make clean`" in text
    assert (
        "Destructive local cleanup that removes `.venv` and development caches."
        in normalized
    )


def test_project_guide_documents_a_runnable_fresh_clone_demo() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "`PAYMENT_DEMO_MODE=1 make run`" in text
    assert "`make prepare` before normal `make run`" in text
    assert (
        "`PAYMENT_DEMO_MODE` controls generation of fallback data, not backend "
        "selection."
    ) in normalized
    assert "A successful configured MongoDB connection takes precedence." in normalized
    assert (
        "Generated fallback may be used when MongoDB is absent or after a "
        "categorized MongoDB connection failure, when no prepared CSV is available."
    ) in normalized
    assert "process environment, `.streamlit/secrets.toml`, and `.env`" in normalized
    assert "only when MongoDB is not configured" not in text
    assert "does not attempt live MongoDB" not in text


def test_project_guide_contract_is_marked_integration(
    request: pytest.FixtureRequest,
) -> None:
    assert request.node.get_closest_marker("integration") is not None
