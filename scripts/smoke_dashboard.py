"""Run a focused browser smoke check against a running Streamlit dashboard."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import Any

SOURCE_BADGE_SELECTOR = ".source-status"
METRIC_LABEL_SELECTOR = "[data-testid='stMetricLabel']"
NAVIGATION_SELECTOR = "[data-testid='stRadioGroup']"
ERROR_DETAIL_SELECTOR = (
    "[data-testid='stException'], "
    "[data-testid='stExceptionDetails'], "
    "[data-testid='stNotificationContentError']"
)
REQUIRED_KPI_LABELS = ("Transactions", "Success rate")
NAVIGATION_LABELS = ("Overview", "Gateways", "Routing Lab", "Transactions", "Admin")
VIEW_READY_TEXT = {
    "Overview": "Live payment health at a glance.",
    "Gateways": "Compare gateway performance and alerts.",
    "Routing Lab": "Optimize payment routing decisions.",
    "Transactions": "Inspect filtered payment activity.",
    "Admin": "Manage dashboard access and payments.",
}
DESKTOP_VIEWPORT = {"width": 1440, "height": 1000}
NARROW_VIEWPORT = {"width": 390, "height": 844}
OVERFLOW_EVALUATION = "document.documentElement.scrollWidth <= window.innerWidth"
ADMIN_LOGIN_LABEL = "Sign in"
ADMIN_DEMO_DISABLED_LABEL = (
    "Database editing is unavailable while demo fallback data is active."
)
LOCAL_DASHBOARD_URL = "http://localhost:8501"
VIEW_SETTLE_MS = 100
TIMEOUT_MS = 30_000


class SmokeCheckError(RuntimeError):
    """Raised when the rendered dashboard misses an essential health signal."""


def _wait_for_visible(locator: Any, message: str) -> None:
    try:
        locator.wait_for(state="visible", timeout=TIMEOUT_MS)
    except Exception as exc:
        raise SmokeCheckError(message) from exc
    if not locator.is_visible():
        raise SmokeCheckError(message)


def _assert_no_visible_errors(page: Any) -> None:
    error_details = page.locator(ERROR_DETAIL_SELECTOR)
    if any(
        error_details.nth(index).is_visible() for index in range(error_details.count())
    ):
        raise SmokeCheckError("Dashboard rendered a visible exception or error")


def _assert_required_kpis(page: Any) -> None:
    metric_labels = page.locator(METRIC_LABEL_SELECTOR)
    for label in REQUIRED_KPI_LABELS:
        matching = metric_labels.filter(has_text=label)
        _wait_for_visible(
            matching,
            f"Dashboard is missing visible KPI label: {label}",
        )
        exact_visible_match = any(
            matching.nth(index).is_visible()
            and matching.nth(index).inner_text().strip() == label
            for index in range(matching.count())
        )
        if not exact_visible_match:
            raise SmokeCheckError(f"Dashboard is missing visible KPI label: {label}")


def _select_view(page: Any, label: str) -> None:
    navigation_item = page.locator(NAVIGATION_SELECTOR).get_by_text(label, exact=True)
    _wait_for_visible(
        navigation_item,
        f"Dashboard is missing top-level navigation label: {label}",
    )
    try:
        navigation_item.click()
    except Exception as exc:
        raise SmokeCheckError(f"Dashboard could not select view: {label}") from exc
    page.wait_for_timeout(VIEW_SETTLE_MS)
    _wait_for_visible(
        page.get_by_text(VIEW_READY_TEXT[label], exact=True),
        f"Dashboard view did not finish rendering: {label}",
    )
    _assert_no_visible_errors(page)


def _capture_overview(page: Any, viewport_name: str) -> None:
    _assert_required_kpis(page)
    if not page.evaluate(OVERFLOW_EVALUATION):
        raise SmokeCheckError(
            f"Overview has horizontal overflow at the {viewport_name} viewport"
        )
    page.screenshot(full_page=True)


def _assert_admin_isolated(page: Any, *, demo_mode: bool) -> None:
    label = ADMIN_DEMO_DISABLED_LABEL if demo_mode else ADMIN_LOGIN_LABEL
    message = (
        "Demo Admin did not expose its disabled editing state"
        if demo_mode
        else "Live Admin did not expose its sign-in control"
    )
    _wait_for_visible(page.get_by_text(label, exact=True), message)

    metric_labels = page.locator(METRIC_LABEL_SELECTOR)
    if any(
        metric_labels.nth(index).is_visible() for index in range(metric_labels.count())
    ):
        raise SmokeCheckError("Admin rendered an Overview KPI card")


def run_dashboard_smoke(
    url: str,
    sync_playwright_factory: Callable[[], Any],
) -> None:
    """Assert that a running dashboard renders its core operational signals."""
    with sync_playwright_factory() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport=DESKTOP_VIEWPORT)
            response = page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            if response is None:
                raise SmokeCheckError("Dashboard load failed without an HTTP response")
            if not response.ok:
                raise SmokeCheckError(
                    f"Dashboard load failed with HTTP status {response.status}"
                )

            source_badge = page.locator(SOURCE_BADGE_SELECTOR)
            visible_source_badge = source_badge.first
            _wait_for_visible(
                visible_source_badge,
                "Dashboard source badge is not visible",
            )
            if source_badge.count() != 1:
                raise SmokeCheckError("Dashboard must render exactly one source badge")
            demo_mode = "DEMO" in visible_source_badge.inner_text().upper()

            for label in NAVIGATION_LABELS:
                _select_view(page, label)
                if label == "Overview":
                    _capture_overview(page, "desktop")
                elif label == "Admin":
                    _assert_admin_isolated(page, demo_mode=demo_mode)

            page.set_viewport_size(NARROW_VIEWPORT)
            _select_view(page, "Overview")
            _capture_overview(page, "narrow")
        finally:
            browser.close()


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a running dashboard in headless Chromium."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=LOCAL_DASHBOARD_URL,
        help=f"Dashboard URL (default: {LOCAL_DASHBOARD_URL})",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Return zero only when the dashboard meets the browser smoke contract."""
    args = _arguments(argv)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright is unavailable. Install development dependencies and run "
            "'.venv/bin/python -m playwright install chromium'.",
            file=sys.stderr,
        )
        return 2

    try:
        run_dashboard_smoke(args.url, sync_playwright)
    except Exception as exc:
        print(f"Dashboard smoke check failed: {exc}", file=sys.stderr)
        return 1
    print("Dashboard smoke check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
