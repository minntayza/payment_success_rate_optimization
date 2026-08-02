"""Run a focused browser smoke check against a running Streamlit dashboard."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import Any

SOURCE_BADGE_SELECTOR = ".source-status"
METRIC_LABEL_SELECTOR = "[data-testid='stMetricLabel']"
ERROR_DETAIL_SELECTOR = (
    "[data-testid='stException'], "
    "[data-testid='stExceptionDetails'], "
    "[data-testid='stNotificationContentError']"
)
REQUIRED_KPI_LABELS = ("Transactions", "Success rate")
TIMEOUT_MS = 30_000


class SmokeCheckError(RuntimeError):
    """Raised when the rendered dashboard misses an essential health signal."""


def run_dashboard_smoke(
    url: str,
    sync_playwright_factory: Callable[[], Any],
) -> None:
    """Assert that a running dashboard renders its core operational signals."""
    with sync_playwright_factory() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            if response is None:
                raise SmokeCheckError("Dashboard load failed without an HTTP response")
            if not response.ok:
                raise SmokeCheckError(
                    f"Dashboard load failed with HTTP status {response.status}"
                )

            source_badge = page.locator(SOURCE_BADGE_SELECTOR)
            if source_badge.count() != 1:
                raise SmokeCheckError("Dashboard must render exactly one source badge")
            visible_source_badge = source_badge.first
            try:
                visible_source_badge.wait_for(state="visible", timeout=TIMEOUT_MS)
            except Exception as exc:
                raise SmokeCheckError("Dashboard source badge is not visible") from exc
            if not visible_source_badge.is_visible():
                raise SmokeCheckError("Dashboard source badge is not visible")

            metric_labels = page.locator(METRIC_LABEL_SELECTOR)
            for label in REQUIRED_KPI_LABELS:
                matching = metric_labels.filter(has_text=label)
                try:
                    matching.wait_for(state="visible", timeout=TIMEOUT_MS)
                except Exception as exc:
                    raise SmokeCheckError(
                        f"Dashboard is missing visible KPI label: {label}"
                    ) from exc
                exact_visible_match = any(
                    matching.nth(index).is_visible()
                    and matching.nth(index).inner_text().strip() == label
                    for index in range(matching.count())
                )
                if not exact_visible_match:
                    raise SmokeCheckError(
                        f"Dashboard is missing visible KPI label: {label}"
                    )

            error_details = page.locator(ERROR_DETAIL_SELECTOR)
            if any(
                error_details.nth(index).is_visible()
                for index in range(error_details.count())
            ):
                raise SmokeCheckError("Dashboard rendered a visible exception or error")
        finally:
            browser.close()


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a running dashboard in headless Chromium."
    )
    parser.add_argument("url", help="Dashboard URL, for example http://localhost:8501")
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
