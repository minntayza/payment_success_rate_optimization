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
VIEW_CONTENT_TEXT = {
    "Overview": "AI operations brief",
    "Gateways": "Gateway performance",
    "Routing Lab": "Payment routing optimization",
    "Transactions": "How to interpret this dashboard",
}
DESKTOP_VIEWPORT = {"width": 1440, "height": 1000}
NARROW_VIEWPORT = {"width": 390, "height": 844}
OVERFLOW_EVALUATION = "document.documentElement.scrollWidth <= window.innerWidth"
ADMIN_LOGIN_LABEL = "Sign in"
ADMIN_EXPANDER_LABEL = "Administrator transaction manager"
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


def _select_view(page: Any, label: str, *, demo_mode: bool) -> None:
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
    ready_text = (
        ADMIN_DEMO_DISABLED_LABEL
        if label == "Admin" and demo_mode
        else ADMIN_EXPANDER_LABEL
        if label == "Admin"
        else VIEW_CONTENT_TEXT[label]
    )
    _wait_for_visible(
        page.get_by_text(ready_text, exact=True),
        f"Dashboard view did not finish rendering: {label}",
    )
    _assert_no_visible_errors(page)


def _capture_view(page: Any, label: str, viewport_name: str) -> None:
    if label == "Overview":
        _assert_required_kpis(page)
    if not page.evaluate(OVERFLOW_EVALUATION):
        raise SmokeCheckError(
            f"{label} has horizontal overflow at the {viewport_name} viewport"
        )
    page.screenshot(full_page=True)


def _assert_admin_isolated(page: Any, *, demo_mode: bool) -> None:
    if not demo_mode:
        expander = page.get_by_text(ADMIN_EXPANDER_LABEL, exact=True)
        _wait_for_visible(
            expander,
            "Live Admin did not expose its transaction manager",
        )
        try:
            expander.click()
        except Exception as exc:
            raise SmokeCheckError(
                "Live Admin transaction manager could not be opened"
            ) from exc

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
                _select_view(page, label, demo_mode=demo_mode)
                _capture_view(page, label, "desktop")
                page.set_viewport_size(NARROW_VIEWPORT)
                _capture_view(page, label, "narrow")
                page.set_viewport_size(DESKTOP_VIEWPORT)
                if label == "Admin":
                    _assert_admin_isolated(page, demo_mode=demo_mode)
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
