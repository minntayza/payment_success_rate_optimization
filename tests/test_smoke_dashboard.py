"""Contract tests for the optional browser dashboard smoke check."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "smoke_dashboard.py"


class _Locator:
    def __init__(self, *, count: int = 1, text: str = "") -> None:
        self._count = count
        self._text = text

    @property
    def first(self) -> _Locator:
        return self

    def count(self) -> int:
        return self._count

    def inner_text(self) -> str:
        return self._text

    def is_visible(self) -> bool:
        return self._count > 0


class _Page:
    def __init__(
        self,
        *,
        source_badge_count: int,
        body_text: str,
        exceptions: int,
    ) -> None:
        self.source_badge_count = source_badge_count
        self.body_text = body_text
        self.exceptions = exceptions

    def goto(self, *_args: object, **_kwargs: object) -> None:
        return None

    def wait_for_selector(self, *_args: object, **_kwargs: object) -> None:
        return None

    def locator(self, selector: str) -> _Locator:
        if selector == ".source-status":
            return _Locator(count=self.source_badge_count)
        if selector == "body":
            return _Locator(text=self.body_text)
        return _Locator(count=self.exceptions)


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


@pytest.mark.integration
@pytest.mark.parametrize(
    ("source_badge_count", "body_text", "exceptions", "expected_message"),
    [
        (0, "Transactions\nSuccess rate", 0, "source badge"),
        (1, "Transactions", 0, "Success rate"),
        (1, "Transactions\nSuccess rate", 1, "exception"),
    ],
)
def test_browser_smoke_rejects_missing_dashboard_signals(
    source_badge_count: int,
    body_text: str,
    exceptions: int,
    expected_message: str,
) -> None:
    """A missing badge/KPI or rendered exception must fail the smoke command."""
    module = _load_smoke_module()
    page = _Page(
        source_badge_count=source_badge_count,
        body_text=body_text,
        exceptions=exceptions,
    )

    with pytest.raises(module.SmokeCheckError, match=expected_message):
        module.run_dashboard_smoke(
            "http://dashboard.test", lambda: _PlaywrightContext(page)
        )


@pytest.mark.integration
def test_browser_smoke_accepts_the_english_dashboard_kpi_labels() -> None:
    """The smoke contract accepts the labels rendered by the English dashboard."""
    module = _load_smoke_module()
    page = _Page(
        source_badge_count=1,
        body_text="Transactions\nSuccess rate",
        exceptions=0,
    )

    module.run_dashboard_smoke(
        "http://dashboard.test", lambda: _PlaywrightContext(page)
    )
