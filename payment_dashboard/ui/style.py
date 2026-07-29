"""Page-level CSS and theming."""

from __future__ import annotations

import streamlit as st

PAGE_CSS = """
<style>
html, body, [class*="css"] {
    font-family: Inter, "Noto Sans Myanmar", "Myanmar Text", sans-serif;
}
.stApp {
    background: #ffffff;
}
.block-container {
    max-width: 1440px;
    padding-top: 2rem;
    padding-bottom: 4rem;
}
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 1rem 1.1rem;
    box-shadow: 0 6px 20px rgba(15, 23, 42, 0.05);
}
[data-testid="stMetricLabel"] {
    color: #475569;
}
[data-testid="stMetricValue"] {
    color: #0f172a;
}
div[data-testid="stDataFrame"] {
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    overflow: hidden;
}
h1, h2, h3 {
    color: #0f172a;
    letter-spacing: -0.02em;
}
.st-key-ai_brief_result,
.st-key-ai_brief_result p,
.st-key-ai_brief_result li,
.st-key-ai_brief_result strong,
.st-key-ai_brief_result em {
    color: #1e293b !important;
}
.st-key-ai_brief_result h1,
.st-key-ai_brief_result h2,
.st-key-ai_brief_result h3,
.st-key-ai_brief_result h4,
.st-key-ai_brief_result h5,
.st-key-ai_brief_result h6 {
    color: #0f172a !important;
}
.st-key-ai_brief_result a {
    color: #1d4ed8 !important;
}
.st-key-ai_brief_result code {
    color: #7c2d12 !important;
    background: #fff7ed;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]
) {
    --language-accent: #2563EB;
    border: 0;
    background: transparent;
    box-shadow: none;
    padding: 0;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]:checked
) {
    --language-accent: #D4A017;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]
) label[data-baseweb="checkbox"] > div:first-child {
    background-color: var(--language-accent) !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]
) [data-testid="stWidgetLabel"],
[data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]
) [data-testid="stCaptionContainer"] {
    color: #0f172a !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]:focus-visible
) label[data-baseweb="checkbox"] > div:first-child {
    outline: 3px solid color-mix(in srgb, var(--language-accent) 45%, transparent);
    outline-offset: 3px;
}
</style>
"""


def apply_page_style() -> None:
    """Inject custom CSS into the Streamlit page."""
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
