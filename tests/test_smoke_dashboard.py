"""Contract tests for the optional browser dashboard smoke check."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "smoke_dashboard.py"
METRIC_SELECTOR = "[data-testid='stMetricLabel']"
NAVIGATION_SELECTOR = "[data-testid='stRadioGroup']"
NAVIGATION_LABELS = ("Overview", "Gateways", "Routing Lab", "Transactions", "Admin")
VIEW_DESCRIPTIONS = {
    "Overview": "Live payment health at a glance.",
    "Gateways": "Compare gateway performance and alerts.",
    "Routing Lab": "Optimize payment routing decisions.",
    "Transactions": "Inspect filtered payment activity.",
    "Admin": "Manage dashboard access and payments.",
}
VIEW_CONTENT_TEXT = {
    "Overview": "AI operations brief",
    "Gateways": "Gateway performance",
    "Routing Lab": "Payment routing optimization",
    "Transactions": "How to interpret this dashboard",
}
DESKTOP_WIDTH = 1440
NARROW_WIDTH = 390
ADMIN_EXPANDER_LABEL = "Administrator transaction manager"


@dataclass
class _Element:
    text: str = ""
    visible: bool = True
    visible_after_wait: bool = False
    on_click: Callable[[], None] | None = None
    on_wait: Callable[[], None] | None = None


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

    def click(self) -> None:
        if not self.elements:
            raise TimeoutError("locator did not become clickable")
        if self.elements[0].on_click is not None:
            self.elements[0].on_click()

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
            if item.on_wait is not None:
                item.on_wait()
            if item.visible_after_wait:
                item.visible = True
        if not any(item.visible for item in self.elements):
            raise TimeoutError("locator did not become visible")


class _NavigationLocator:
    def __init__(self, page: _Page) -> None:
        self.page = page

    def get_by_text(self, text: str, *, exact: bool) -> _Locator:
        return self.page.navigation_item(text, exact=exact)


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
        navigation_labels: tuple[str, ...] = NAVIGATION_LABELS,
        admin_login_visible: bool = True,
        admin_disabled_visible: bool = False,
        admin_metrics: list[_Element] | None = None,
        overflowing_widths: set[int] | None = None,
        overflowing_layouts: set[tuple[str, int]] | None = None,
        duplicate_text_labels: set[str] | None = None,
        delayed_navigation: bool = False,
        delayed_admin_content: bool = False,
        admin_expanded: bool = False,
        missing_view_content: set[str] | None = None,
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
        self.navigation_labels = navigation_labels
        self.admin_login_visible = admin_login_visible
        self.admin_disabled_visible = admin_disabled_visible
        self.admin_metrics = [] if admin_metrics is None else admin_metrics
        self.overflowing_widths = (
            set() if overflowing_widths is None else overflowing_widths
        )
        self.overflowing_layouts = (
            set() if overflowing_layouts is None else overflowing_layouts
        )
        self.duplicate_text_labels = (
            set() if duplicate_text_labels is None else duplicate_text_labels
        )
        self.delayed_navigation = delayed_navigation
        self.delayed_admin_content = delayed_admin_content
        self.admin_expanded = admin_expanded
        self.missing_view_content = (
            set() if missing_view_content is None else missing_view_content
        )
        self.admin_transition_pending = False
        self.active_view = "Overview"
        self.pending_view: str | None = None
        self.clicked_views: list[str] = []
        self.viewport_widths: list[int] = []
        self.screenshots: list[tuple[str, int]] = []
        self.waits: list[int] = []
        self.viewport_width = 0

    def goto(self, *_args: object, **_kwargs: object) -> _Response | None:
        return self.response

    def locator(self, selector: str) -> _Locator | _NavigationLocator:
        if selector == NAVIGATION_SELECTOR:
            return _NavigationLocator(self)
        if selector == ".source-status":
            return _Locator(self.source_badge)
        if selector == METRIC_SELECTOR:
            if self.admin_transition_pending:
                return _Locator(self.metrics)
            if self.active_view == "Overview":
                return _Locator(self.metrics)
            if self.active_view == "Admin":
                return _Locator(self.admin_metrics)
            return _Locator([])
        return _Locator(self.errors)

    def get_by_text(self, text: str, *, exact: bool) -> _Locator:
        assert exact
        if text in self.navigation_labels:
            elements = [
                _Element(text, on_click=lambda: self._select_view(text)),
            ]
            if text in self.duplicate_text_labels:
                elements.append(_Element(text))
            return _Locator(elements)
        if text in VIEW_DESCRIPTIONS.values():
            label = next(
                name
                for name, description in VIEW_DESCRIPTIONS.items()
                if text == description
            )
            if label == self.active_view:
                return _Locator([_Element(text)])
            if label == self.pending_view:
                return _Locator(
                    [
                        _Element(
                            text,
                            visible=False,
                            visible_after_wait=True,
                            on_wait=self._apply_pending_view,
                        )
                    ]
                )
            return _Locator([])
        if text in VIEW_CONTENT_TEXT.values():
            label = next(
                name
                for name, content_text in VIEW_CONTENT_TEXT.items()
                if text == content_text
            )
            if label in self.missing_view_content:
                return _Locator([])
            if label == self.active_view:
                return _Locator([_Element(text)])
            if label == self.pending_view:
                return _Locator(
                    [
                        _Element(
                            text,
                            visible=False,
                            visible_after_wait=True,
                            on_wait=self._apply_pending_view,
                        )
                    ]
                )
            return _Locator([])
        if text == ADMIN_EXPANDER_LABEL and self.pending_view == "Admin":
            return _Locator(
                [
                    _Element(
                        text,
                        visible=False,
                        visible_after_wait=True,
                        on_click=self._open_admin_expander,
                        on_wait=self._apply_pending_view,
                    )
                ]
            )
        if text == ADMIN_EXPANDER_LABEL and self.active_view == "Admin":
            return self._admin_expander_locator(text)
        if text == "Sign in" and self.active_view == "Admin":
            return self._admin_state_locator(
                text,
                visible=self.admin_login_visible and self.admin_expanded,
            )
        if (
            text
            == ("Database editing is unavailable while demo fallback data is active.")
            and self.pending_view == "Admin"
        ):
            return _Locator(
                [
                    _Element(
                        text,
                        visible=False,
                        visible_after_wait=self.admin_disabled_visible,
                        on_wait=self._apply_pending_view,
                    )
                ]
            )
        if text == (
            "Database editing is unavailable while demo fallback data is active."
        ) and (self.active_view == "Admin"):
            return self._admin_state_locator(text, visible=self.admin_disabled_visible)
        return _Locator([])

    def navigation_item(self, text: str, *, exact: bool) -> _Locator:
        assert exact
        if text not in self.navigation_labels:
            return _Locator([])
        return _Locator([_Element(text, on_click=lambda: self._select_view(text))])

    def set_viewport_size(self, viewport: dict[str, int]) -> None:
        self.viewport_width = viewport["width"]
        self.viewport_widths.append(self.viewport_width)

    def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(timeout)

    def evaluate(self, expression: str) -> bool:
        assert expression == (
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        return (
            self.viewport_width not in self.overflowing_widths
            and (self.active_view, self.viewport_width) not in self.overflowing_layouts
        )

    def screenshot(self, *, full_page: bool) -> bytes:
        assert full_page
        self.screenshots.append((self.active_view, self.viewport_width))
        return b"screenshot"

    def _select_view(self, label: str) -> None:
        if label == "Admin" and self.delayed_admin_content:
            self.admin_transition_pending = True
        if self.delayed_navigation:
            self.pending_view = label
        else:
            self.active_view = label
        self.clicked_views.append(label)

    def _apply_pending_view(self) -> None:
        assert self.pending_view is not None
        self.active_view = self.pending_view
        self.pending_view = None

    def _admin_state_locator(self, text: str, *, visible: bool) -> _Locator:
        if not self.admin_transition_pending:
            return _Locator([_Element(text, visible=visible)])
        return _Locator(
            [
                _Element(
                    text,
                    visible=False,
                    visible_after_wait=visible,
                    on_wait=self._finish_admin_transition,
                )
            ]
        )

    def _admin_expander_locator(self, text: str) -> _Locator:
        if not self.admin_transition_pending:
            return _Locator([_Element(text, on_click=self._open_admin_expander)])
        return _Locator(
            [
                _Element(
                    text,
                    visible=False,
                    visible_after_wait=True,
                    on_click=self._open_admin_expander,
                    on_wait=self._finish_admin_transition,
                )
            ]
        )

    def _open_admin_expander(self) -> None:
        self.admin_expanded = True

    def _finish_admin_transition(self) -> None:
        self.admin_transition_pending = False


class _Browser:
    def __init__(self, page: _Page) -> None:
        self.page = page

    def new_page(self, **kwargs: object) -> _Page:
        viewport = kwargs.get("viewport")
        if isinstance(viewport, dict):
            self.page.set_viewport_size(viewport)
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


@pytest.mark.integration
def test_browser_smoke_visits_and_captures_every_view_at_both_widths() -> None:
    """Every destination needs desktop and narrow visual evidence."""
    module = _load_smoke_module()
    page = _Page(
        source_badge=[_Element("DEMO Simulated demo data")],
        admin_disabled_visible=True,
    )

    _run(module, page)

    assert page.clicked_views == list(NAVIGATION_LABELS)
    assert page.viewport_widths == [DESKTOP_WIDTH] + [
        width for _label in NAVIGATION_LABELS for width in (NARROW_WIDTH, DESKTOP_WIDTH)
    ]
    assert page.screenshots == [
        (label, width)
        for label in NAVIGATION_LABELS
        for width in (DESKTOP_WIDTH, NARROW_WIDTH)
    ]


@pytest.mark.integration
@pytest.mark.parametrize("label", NAVIGATION_LABELS)
@pytest.mark.parametrize("width", [DESKTOP_WIDTH, NARROW_WIDTH])
def test_browser_smoke_rejects_horizontal_overflow_in_every_view(
    label: str,
    width: int,
) -> None:
    """Layout-heavy destinations cannot escape the page at either viewport."""
    module = _load_smoke_module()
    page = _Page(
        source_badge=[_Element("DEMO Simulated demo data")],
        admin_disabled_visible=True,
        overflowing_layouts={(label, width)},
    )

    with pytest.raises(module.SmokeCheckError, match=f"{label}.*horizontal overflow"):
        _run(module, page)


@pytest.mark.integration
@pytest.mark.parametrize("width", [DESKTOP_WIDTH, NARROW_WIDTH])
def test_browser_smoke_rejects_overview_horizontal_overflow(width: int) -> None:
    """Overview cannot extend the page beyond either supported viewport."""
    module = _load_smoke_module()

    with pytest.raises(module.SmokeCheckError, match="horizontal overflow"):
        _run(module, _Page(overflowing_widths={width}))


@pytest.mark.integration
def test_browser_smoke_rejects_overview_kpis_in_admin() -> None:
    """Admin must not inherit metric cards from the Overview workflow."""
    module = _load_smoke_module()
    page = _Page(admin_metrics=[_Element("Transactions")])

    with pytest.raises(module.SmokeCheckError, match="Overview KPI"):
        _run(module, page)


@pytest.mark.integration
def test_browser_smoke_requires_sign_in_for_live_admin() -> None:
    """A live-data Admin destination must expose its authentication entry point."""
    module = _load_smoke_module()
    page = _Page(admin_login_visible=False)

    with pytest.raises(module.SmokeCheckError, match="sign-in"):
        _run(module, page)


@pytest.mark.integration
def test_browser_smoke_expands_live_admin_before_waiting_for_sign_in() -> None:
    """Live authentication is visible only after opening the Admin expander."""
    module = _load_smoke_module()
    page = _Page()

    _run(module, page)

    assert page.admin_expanded is True


@pytest.mark.integration
def test_browser_smoke_accepts_disabled_admin_in_demo_mode() -> None:
    """Safe demo QA accepts the documented non-mutating Admin state."""
    module = _load_smoke_module()
    page = _Page(
        source_badge=[_Element("DEMO Simulated demo data")],
        admin_login_visible=False,
        admin_disabled_visible=True,
    )

    _run(module, page)

    assert "Admin" in page.clicked_views


def test_browser_smoke_defaults_to_the_local_dashboard() -> None:
    """The documented no-argument command targets the approved local server."""
    module = _load_smoke_module()
    try:
        arguments = module._arguments([])
    except SystemExit:
        pytest.fail("the smoke command still requires an explicit URL")

    assert arguments.url == "http://localhost:8501"


@pytest.mark.integration
def test_browser_smoke_scopes_navigation_away_from_view_content() -> None:
    """A chart label matching a destination cannot make navigation ambiguous."""
    module = _load_smoke_module()
    page = _Page(duplicate_text_labels={"Transactions"})

    _run(module, page)

    assert "Transactions" in page.clicked_views


@pytest.mark.integration
def test_browser_smoke_waits_for_each_selected_view_to_render() -> None:
    """View assertions cannot run against stale content from the previous rerun."""
    module = _load_smoke_module()
    page = _Page(delayed_navigation=True)

    _run(module, page)

    assert page.active_view == "Admin"
    assert page.pending_view is None


@pytest.mark.integration
@pytest.mark.parametrize("label", tuple(VIEW_CONTENT_TEXT))
def test_browser_smoke_rejects_shell_ready_without_view_content(label: str) -> None:
    """A destination caption cannot substitute for rendered workflow content."""
    module = _load_smoke_module()
    page = _Page(missing_view_content={label})

    with pytest.raises(module.SmokeCheckError, match=label):
        _run(module, page)


@pytest.mark.integration
def test_browser_smoke_waits_for_admin_content_before_isolation_check() -> None:
    """Admin isolation is measured only after its rerun replaces Overview cards."""
    module = _load_smoke_module()
    page = _Page(delayed_admin_content=True)

    _run(module, page)

    assert page.admin_transition_pending is False
