"""Tests for page-level dashboard styling."""

import re

from payment_dashboard.ui.style import PAGE_CSS


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    light, dark = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (light + 0.05) / (dark + 0.05)


def _composite(base: str, overlay: tuple[int, int, int, float]) -> str:
    base_channels = [int(base[index : index + 2], 16) for index in (1, 3, 5)]
    red, green, blue, alpha = overlay
    channels = [
        round(alpha * foreground + (1 - alpha) * background)
        for foreground, background in zip(
            (red, green, blue), base_channels, strict=True
        )
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def test_page_css_uses_approved_dark_tokens() -> None:
    assert "--canvas: #07111F" in PAGE_CSS
    assert "--surface: #0D1B2A" in PAGE_CSS
    assert "--accent: #22D3EE" in PAGE_CSS
    assert "--success: #34D399" in PAGE_CSS
    assert "--critical: #FB7185" in PAGE_CSS
    assert "prefers-reduced-motion: reduce" in PAGE_CSS
    assert "#fffaf4" not in PAGE_CSS.lower()


def test_dark_palette_is_used_by_decorative_and_status_styles() -> None:
    assert "background: rgba(34, 211, 238, 0.12);" in PAGE_CSS
    assert "outline: 3px solid var(--accent) !important;" in PAGE_CSS
    assert "border-left: 5px solid #34D399;" in PAGE_CSS
    assert "border-left: 5px solid #FB7185;" in PAGE_CSS
    assert "--language-accent: #22D3EE;" in PAGE_CSS


def test_dark_theme_exposes_design_tokens_and_component_hooks() -> None:
    for token in (
        "--canvas: #07111F",
        "--surface: #0D1B2A",
        "--text: #F8FAFC",
        "--muted: #94A3B8",
        "--accent: #22D3EE",
    ):
        assert token in PAGE_CSS
    for hook in (
        ".playful-hero",
        ".status-pill",
        "kpi_success",
        "ai_brief_card",
        "ai_brief_result",
        "status-success",
        "status-warning",
        "status-error",
    ):
        assert hook in PAGE_CSS


def test_hero_normal_text_has_wcag_aa_contrast_across_background() -> None:
    root_colors = dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", PAGE_CSS))
    hero_rule = re.search(r"\.playful-hero \{(.*?)\n\}", PAGE_CSS, re.DOTALL)
    assert hero_rule is not None
    gradient = re.search(r"background:\s*linear-gradient\((.*)\);", hero_rule.group(1))
    assert gradient is not None
    tokens = re.findall(r"var\((--[\w-]+)\)|(#[0-9a-fA-F]{6})", gradient.group(1))
    backgrounds = [root_colors[name] if name else literal for name, literal in tokens]
    decorative_overlays = ((34, 211, 238, 0.12), (52, 211, 153, 0.08))

    tested_backgrounds = backgrounds + [
        _composite(background, overlay)
        for background in backgrounds
        for overlay in decorative_overlays
    ]

    assert tested_backgrounds
    assert min(_contrast_ratio("#ffffff", color) for color in tested_backgrounds) >= 4.5
    assert "background: rgba(34, 211, 238, 0.12);" in PAGE_CSS
    assert "background: rgba(52, 211, 153, 0.08);" in PAGE_CSS


def test_dark_theme_has_two_and_one_column_layout_rules() -> None:
    assert "@media (max-width: 768px)" in PAGE_CSS
    assert "overflow-x: hidden" in PAGE_CSS
    assert '[data-testid="stHorizontalBlock"]:has(.st-key-kpi_transactions)' in PAGE_CSS
    assert '[data-testid="stColumn"]' in PAGE_CSS
    assert "flex: 1 1 50%;" in PAGE_CSS
    assert "flex: 1 1 100%;" in PAGE_CSS


def test_empty_state_bounds_and_integrates_mascot() -> None:
    assert ".empty-state, .st-key-ai_brief_result {" in PAGE_CSS
    assert "text-align: center;" in PAGE_CSS
    assert ".empty-mascot {" in PAGE_CSS
    assert "width: 6rem;" in PAGE_CSS
    assert "height: 6rem;" in PAGE_CSS
    assert "max-width: 100%;" in PAGE_CSS


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
    assert "color: var(--text) !important;" in PAGE_CSS
    assert ".st-key-ai_brief_result h2" in PAGE_CSS
    assert "color: var(--text) !important;" in PAGE_CSS


def test_entire_ai_feature_has_purple_card_and_readable_text() -> None:
    card_rule = re.search(r"\.st-key-ai_brief_card \{(.*?)\n\}", PAGE_CSS, re.DOTALL)
    assert card_rule is not None
    assert "background: linear-gradient" in card_rule.group(1)
    assert "border-radius: var(--radius-lg);" in card_rule.group(1)
    assert ".st-key-ai_brief_card p" in PAGE_CSS
    assert ".st-key-ai_brief_card h2" in PAGE_CSS
    assert "color: #ffffff !important;" in PAGE_CSS


def test_alert_message_text_uses_high_contrast_color() -> None:
    assert '[data-testid="stAlert"]' in PAGE_CSS
    assert '[data-testid="stAlert"] p' in PAGE_CSS
    assert "color: var(--text) !important;" in PAGE_CSS


def test_alert_kinds_use_distinct_semantic_treatments() -> None:
    backgrounds: set[str] = set()
    borders: set[str] = set()
    for kind in ("Success", "Info", "Error", "Warning"):
        rule = re.search(
            rf'\[data-testid="stNotificationContent{kind}"\] \{{(.*?)\n\}}',
            PAGE_CSS,
            re.DOTALL,
        )
        assert rule is not None
        background = re.search(r"background:\s*(#[0-9a-fA-F]{6})", rule.group(1))
        border = re.search(r"border-left:\s*5px solid (#[0-9a-fA-F]{6})", rule.group(1))
        assert background is not None
        assert border is not None
        backgrounds.add(background.group(1).lower())
        borders.add(border.group(1).lower())

    assert len(backgrounds) == 4
    assert len(borders) == 4


def test_main_and_sidebar_text_use_explicit_high_contrast_colors() -> None:
    assert '[data-testid="stMain"]' in PAGE_CSS
    assert '[data-testid="stMain"] p' in PAGE_CSS
    assert '[data-testid="stMain"] [data-testid="stCaptionContainer"]' in PAGE_CSS
    assert '[data-testid="stMain"] h1' in PAGE_CSS
    assert "color: var(--text) !important;" in PAGE_CSS
    assert '[data-testid="stSidebar"] p' in PAGE_CSS
    assert "color: #ffffff !important;" in PAGE_CSS
