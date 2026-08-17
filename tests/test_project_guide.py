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
    missing = [
        target for target in targets if not (GUIDE.parent / target).resolve().exists()
    ]
    assert missing == []


def test_project_guide_keeps_routing_inputs_outside_dashboard_snapshot() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    assert 'VALID --> LOCALCTX["Validated prepared local routing contexts"]' in text
    assert 'MONGO --> LIVECTX["Full active MongoDB routing contexts"]' in text
    assert "LOCALCTX --> ROUTING" in text
    assert "LIVECTX --> ROUTING" in text
    assert "SNAP --> ROUTING" not in text
    assert (
        "Snapshot aggregates feed operational analytics, alerts, and the AI brief."
        in text
    )


def test_project_guide_documents_a_runnable_fresh_clone_demo() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    assert "`PAYMENT_DEMO_MODE=1 make run`" in text
    assert "`make prepare` before normal `make run`" in text
    assert (
        "`PAYMENT_DEMO_MODE=1` supplies generated fallback data only when "
        "MongoDB is not configured."
    ) in normalized
    assert (
        "If MongoDB environment or local `.env` settings exist, the app prefers "
        "live MongoDB."
    ) in normalized
    assert (
        "remove or unset MongoDB configuration from both the environment and "
        "local `.env`"
    ) in normalized
    assert "does not attempt live MongoDB" not in text


def test_project_guide_contract_is_marked_integration(
    request: pytest.FixtureRequest,
) -> None:
    assert request.node.get_closest_marker("integration") is not None
