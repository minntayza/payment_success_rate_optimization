"""Tests for page-level dashboard styling."""

from payment_dashboard.ui.style import PAGE_CSS


def test_ai_brief_text_colors_are_scoped_to_result_container() -> None:
    assert ".st-key-ai_brief_result" in PAGE_CSS
    assert ".st-key-ai_brief_result p" in PAGE_CSS
    assert "color: #1e293b !important;" in PAGE_CSS
    assert ".st-key-ai_brief_result h2" in PAGE_CSS
    assert "color: #0f172a !important;" in PAGE_CSS


def test_alert_message_text_uses_high_contrast_color() -> None:
    assert '[data-testid="stAlert"]' in PAGE_CSS
    assert '[data-testid="stAlert"] p' in PAGE_CSS
    assert "color: #0f172a !important;" in PAGE_CSS
