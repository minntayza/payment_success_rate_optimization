"""Run a focused browser smoke check against a running Streamlit dashboard."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import Any

READY_SELECTOR = "[data-testid='stAppViewContainer']"
SOURCE_BADGE_SELECTOR = ".source-status"
EXCEPTION_SELECTOR = "[data-testid='stException'], .stException"
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
            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            page.wait_for_selector(READY_SELECTOR, state="visible", timeout=TIMEOUT_MS)

            source_badge = page.locator(SOURCE_BADGE_SELECTOR)
            if source_badge.count() == 0 or not source_badge.first.is_visible():
                raise SmokeCheckError("Dashboard source badge is not visible")

            visible_text = page.locator("body").inner_text()
            missing_labels = [
                label for label in REQUIRED_KPI_LABELS if label not in visible_text
            ]
            if missing_labels:
                raise SmokeCheckError(
                    "Dashboard is missing KPI labels: " + ", ".join(missing_labels)
                )

            exceptions = page.locator(EXCEPTION_SELECTOR)
            if exceptions.count() and exceptions.first.is_visible():
                raise SmokeCheckError("Dashboard rendered a visible exception")
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
