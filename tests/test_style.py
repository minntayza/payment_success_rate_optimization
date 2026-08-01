"""Tests for page-level dashboard styling."""

from payment_dashboard.ui.style import PAGE_CSS


def test_playful_theme_exposes_design_tokens_and_component_hooks() -> None:
    for token in (
        "--plum: #6c5ce7",
        "--apricot: #ffb86c",
        "--mint: #dff7eb",
        "--rose: #ffe1e8",
        "--ink: #2b2141",
        "--canvas: #fffaf4",
    ):
        assert token in PAGE_CSS
    for hook in (".playful-hero", ".status-pill", "kpi_success", "ai_brief_result"):
        assert hook in PAGE_CSS


def test_playful_theme_has_narrow_layout_rules() -> None:
    assert "@media (max-width: 768px)" in PAGE_CSS
    assert "overflow-x: hidden" in PAGE_CSS
    assert '[data-testid="stHorizontalBlock"]:has(.st-key-kpi_transactions)' in PAGE_CSS
    assert '[data-testid="stColumn"]' in PAGE_CSS
    assert 'flex: 1 1 100%;' in PAGE_CSS
    assert 'min-width: 100%;' in PAGE_CSS


def test_sidebar_language_control_keeps_its_text_high_contrast() -> None:
    sidebar_widget_label_rule = (
        '[data-testid="stSidebar"] '
        '[data-testid="stVerticalBlockBorderWrapper"]:has(\n'
        '    input[aria-label="Language / ဘာသာစကား"]\n'
        ') [data-testid="stWidgetLabel"] { color: #ffffff !important; }'
    )
    sidebar_caption_rule = (
        '[data-testid="stSidebar"] '
        '[data-testid="stVerticalBlockBorderWrapper"]:has(\n'
        '    input[aria-label="Language / ဘာသာစကား"]\n'
        ') [data-testid="stCaptionContainer"] { color: #ffffff !important; }'
    )
    assert sidebar_widget_label_rule in PAGE_CSS
    assert sidebar_caption_rule in PAGE_CSS


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


def test_main_and_sidebar_text_use_explicit_high_contrast_colors() -> None:
    assert '[data-testid="stMain"]' in PAGE_CSS
    assert '[data-testid="stMain"] p' in PAGE_CSS
    assert '[data-testid="stMain"] [data-testid="stCaptionContainer"]' in PAGE_CSS
    assert '[data-testid="stMain"] h1' in PAGE_CSS
    assert "color: #334155 !important;" in PAGE_CSS
    assert "color: #0f172a !important;" in PAGE_CSS
    assert '[data-testid="stSidebar"] p' in PAGE_CSS
    assert "color: #ffffff !important;" in PAGE_CSS
