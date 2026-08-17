import re
from pathlib import Path

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
