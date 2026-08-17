# Project Function and Dataset Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one accurate, layered Markdown guide that explains the repository's data analysis, data management, dashboard, and synthetic routing functions to non-technical readers, new developers, and project judges.

**Architecture:** The guide follows the transaction dataset from provenance through validation, preparation, storage, repositories, analytics, routing evidence, dashboard views, and audited administration. A focused documentation test protects its required structure and verifies every repository-relative Markdown link resolves.

**Tech Stack:** Markdown, Mermaid, Python 3.11+, pytest, pathlib, Ruff, strict mypy.

## Global Constraints

- Create `docs/project-function-and-data-guide.md` as the single layered guide.
- Frame the repository explicitly as a data analysis and management project.
- Serve non-technical users first and new developers/project judges second.
- Describe current code behavior rather than historical design promises.
- Distinguish descriptive analytics from synthetic, non-causal routing evidence.
- Explain both demo/pandas and live/MongoDB data paths where behavior differs.
- Include no credentials, PINs, account values, generated datasets, or personal payment data.
- Use repository-relative Markdown links without unstable source line numbers.
- Preserve all application, dataset, security, and calculation behavior; this task changes documentation and its contract test only.

---

### Task 1: End-to-End Project Function and Dataset Guide

**Files:**
- Create: `docs/project-function-and-data-guide.md`
- Create: `tests/test_project_guide.py`

**Interfaces:**
- Consumes: current modules, `Makefile`, `README.md`, `docs/data-card.md`, `docs/mongodb-atlas-setup.md`, `docs/customer-support-guide.md`, `data/source-manifest.json`, and the approved design specification.
- Produces: a stable documentation contract containing the required sections and valid repository-relative links.

- [ ] **Step 1: Add a failing documentation contract test**

Create `tests/test_project_guide.py` with:

```python
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
    assert REQUIRED_HEADINGS <= set(text.splitlines())
    assert "```mermaid" in text
    assert "data analysis and management" in text.lower()
    assert "synthetic" in text.lower()
    assert "non-causal" in text.lower()


def test_project_guide_local_links_resolve() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    targets = re.findall(r"\[[^]]+\]\((?!https?://|#)([^)]+)\)", text)
    assert targets
    missing = [target for target in targets if not (GUIDE.parent / target).resolve().exists()]
    assert missing == []
```

- [ ] **Step 2: Run the test and verify the missing-guide failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_project_guide.py -q
```

Expected: FAIL with `FileNotFoundError` for
`docs/project-function-and-data-guide.md`.

- [ ] **Step 3: Write the layered guide from verified sources**

Create `docs/project-function-and-data-guide.md` with this exact top-level
structure:

```markdown
# Payment Success Rate Optimization: Project Function and Dataset Guide

## 1. Project overview
## 2. Dashboard tour
## 3. Dataset lifecycle
## 4. Dataset fields and management controls
## 5. Functional architecture
## 6. Analytical definitions
## 7. How to run and verify the project
## 8. Interpretation and troubleshooting
```

Populate the sections using this verified source map:

- provenance and integrity: `data/source-manifest.json`,
  `payment_dashboard/prepare_data.py`, `payment_dashboard/data_loader.py`;
- deterministic gateway enrichment: `payment_dashboard/simulation.py`;
- repository contracts and snapshots: `payment_dashboard/dashboard_repository.py`,
  `payment_dashboard/mongodb.py`;
- metrics and alerts: `payment_dashboard/analytics.py`,
  `payment_dashboard/alerting.py`, `payment_dashboard/config.py`;
- routing benchmark and artifacts: `payment_dashboard/routing_config.py`,
  `payment_dashboard/routing_simulation.py`,
  `payment_dashboard/routing_evaluation.py`,
  `payment_dashboard/routing_optimizer.py`,
  `payment_dashboard/routing_repository.py`,
  `payment_dashboard/routing_run_store.py`;
- AI brief: `payment_dashboard/ai_brief.py`;
- authentication, mutation, and audit: `payment_dashboard/admin_auth.py`,
  `payment_dashboard/transaction_service.py`,
  `payment_dashboard/load_mongodb.py`;
- application/views: `payment_dashboard/app.py`, `payment_dashboard/ui/shell.py`,
  `payment_dashboard/ui/views.py`, `payment_dashboard/ui/sections.py`,
  `payment_dashboard/ui/optimization.py`;
- commands: `Makefile`; and
- limitations/setup: `README.md`, `docs/data-card.md`,
  `docs/mongodb-atlas-setup.md`, `docs/customer-support-guide.md`.

The Mermaid diagram must show the raw-manifest branch through preparation into
both demo/pandas and live/MongoDB repositories, followed by snapshots, analytics,
routing evidence, five UI views, and audited Admin mutations.

State exact current alert constants: latest window 50, minimum earlier baseline
200, and alert threshold 10 percentage points with a confidence interval whose
lower bound is greater than zero. Explain the `173/50` insufficient-history
example and the current MongoDB blank-rate presentation.

State the current simulation versions `controlled-v1`, `routing-benchmark-v4`,
and manual mutation version `manual-v1`. Explain that mixed versions are rejected
rather than silently pooled.

Document the supported commands from `make help`: `setup`, `prepare`, `run`,
`load-mongodb`, `test`, `test-unit`, `test-integration`, `test-live`, `smoke`,
`lint`, `format`, `typecheck`, `check`, and `verify-clean`.

- [ ] **Step 4: Run focused documentation tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_project_guide.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Verify guide content against current contracts**

Run:

```bash
rg -n 'T[B]D|T[O]DO|F[I]XME|pin_code|mongodb\+srv://|ADMIN_PASSWORD=' docs/project-function-and-data-guide.md
```

Expected: no output.

Run:

```bash
rg -n 'latest 50|200|10 percentage points|controlled-v1|routing-benchmark-v4|manual-v1' docs/project-function-and-data-guide.md
```

Expected: every verified threshold/version appears in explanatory text.

- [ ] **Step 6: Run repository quality gates**

Run:

```bash
make check
.venv/bin/ruff format --check payment_dashboard tests scripts
git diff --check
```

Expected: lint, strict mypy, complete pytest, formatting, and whitespace checks
all pass; only the two documented opt-in live tests may be skipped.

- [ ] **Step 7: Commit the guide and contract test**

```bash
git add docs/project-function-and-data-guide.md tests/test_project_guide.py
git commit -m "docs: explain project functions and dataset lifecycle"
```
