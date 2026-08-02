"""Contract tests for the optional browser dashboard smoke check."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "smoke_dashboard.py"
METRIC_SELECTOR = "[data-testid='stMetricLabel']"


@dataclass
class _Element:
    text: str = ""
    visible: bool = True
    visible_after_wait: bool = False


class _Locator:
    def __init__(self, elements: list[_Element]) -> None:
        self.elements = elements

    @property
    def first(self) -> _Locator:
        return self.nth(0)

    def count(self) -> int:
        return len(self.elements)

    def filter(self, *, has_text: str) -> _Locator:
        return _Locator([item for item in self.elements if has_text in item.text])

    def inner_text(self) -> str:
        return self.elements[0].text

    def is_visible(self) -> bool:
        return bool(self.elements and self.elements[0].visible)

    def nth(self, index: int) -> _Locator:
        return _Locator(self.elements[index : index + 1])

    def wait_for(self, *, state: str, timeout: int) -> None:
        assert state == "visible"
        assert timeout > 0
        if len(self.elements) > 1:
            raise RuntimeError("strict mode violation")
        for item in self.elements:
            if item.visible_after_wait:
                item.visible = True
        if not any(item.visible for item in self.elements):
            raise TimeoutError("locator did not become visible")


@dataclass(frozen=True)
class _Response:
    ok: bool
    status: int


class _Page:
    def __init__(
        self,
        *,
        response: _Response | None = None,
        source_badge: list[_Element] | None = None,
        metrics: list[_Element] | None = None,
        errors: list[_Element] | None = None,
    ) -> None:
        self.response = response or _Response(ok=True, status=200)
        self.source_badge = (
            [_Element("LIVE Live MongoDB data")]
            if source_badge is None
            else source_badge
        )
        self.metrics = (
            [_Element("Transactions"), _Element("Success rate")]
            if metrics is None
            else metrics
        )
        self.errors = [] if errors is None else errors

    def goto(self, *_args: object, **_kwargs: object) -> _Response | None:
        return self.response

    def locator(self, selector: str) -> _Locator:
        if selector == ".source-status":
            return _Locator(self.source_badge)
        if selector == METRIC_SELECTOR:
            return _Locator(self.metrics)
        return _Locator(self.errors)


class _Browser:
    def __init__(self, page: _Page) -> None:
        self.page = page

    def new_page(self) -> _Page:
        return self.page

    def close(self) -> None:
        return None


class _Chromium:
    def __init__(self, page: _Page) -> None:
        self.page = page

    def launch(self, **_kwargs: object) -> _Browser:
        return _Browser(self.page)


class _PlaywrightContext:
    def __init__(self, page: _Page) -> None:
        self.playwright = type("Playwright", (), {"chromium": _Chromium(page)})()

    def __enter__(self) -> object:
        return self.playwright

    def __exit__(self, *_args: object) -> None:
        return None


def _load_smoke_module() -> object:
    spec = importlib.util.spec_from_file_location("smoke_dashboard", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(module: object, page: _Page) -> None:
    module.run_dashboard_smoke(
        "http://dashboard.test", lambda: _PlaywrightContext(page)
    )


@pytest.mark.integration
def test_browser_smoke_waits_for_delayed_metric_readiness() -> None:
    """Metric labels that render after navigation are awaited before inspection."""
    module = _load_smoke_module()
    delayed_metrics = [
        _Element("Transactions", visible=False, visible_after_wait=True),
        _Element("Success rate", visible=False, visible_after_wait=True),
    ]

    _run(module, _Page(metrics=delayed_metrics))


@pytest.mark.integration
@pytest.mark.parametrize(
    "response",
    [None, _Response(ok=False, status=404), _Response(ok=False, status=503)],
)
def test_browser_smoke_rejects_failed_navigation(response: _Response | None) -> None:
    """Missing and non-success HTTP responses fail before UI assertions."""
    module = _load_smoke_module()
    page = _Page()
    page.response = response

    with pytest.raises(module.SmokeCheckError, match="load failed"):
        _run(module, page)


@pytest.mark.integration
def test_browser_smoke_rejects_missing_visible_metric_label() -> None:
    """Body text cannot substitute for an actual visible Streamlit metric label."""
    module = _load_smoke_module()
    page = _Page(metrics=[_Element("Transactions")])

    with pytest.raises(module.SmokeCheckError, match="Success rate"):
        _run(module, page)


@pytest.mark.integration
def test_browser_smoke_rejects_missing_source_badge() -> None:
    """The dashboard must identify whether its data source is live or simulated."""
    module = _load_smoke_module()

    with pytest.raises(module.SmokeCheckError, match="source badge"):
        _run(module, _Page(source_badge=[]))


@pytest.mark.integration
def test_browser_smoke_rejects_duplicate_source_badges() -> None:
    """The rendered source indicator must have one unambiguous owner."""
    module = _load_smoke_module()
    page = _Page(
        source_badge=[
            _Element("DEMO Simulated demo data"),
            _Element("DEMO Simulated demo data"),
        ]
    )

    with pytest.raises(module.SmokeCheckError, match="exactly one source badge"):
        _run(module, page)


@pytest.mark.integration
def test_browser_smoke_rejects_a_later_visible_exception() -> None:
    """Every rendered error detail is inspected, not only the first match."""
    module = _load_smoke_module()
    page = _Page(errors=[_Element(visible=False), _Element(visible=True)])

    with pytest.raises(module.SmokeCheckError, match="exception"):
        _run(module, page)
