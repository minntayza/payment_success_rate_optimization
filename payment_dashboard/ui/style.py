"""Page-level CSS and theming."""

from __future__ import annotations

import streamlit as st

PAGE_CSS = """
<style>
html, body, [class*="css"] {
    font-family: Inter, "Noto Sans Myanmar", "Myanmar Text", sans-serif;
}
.stApp {
    background:
        radial-gradient(circle at 90% 0%, rgba(37, 99, 235, 0.10), transparent 30rem),
        #f7f9fc;
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
[data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]
) {
    --language-accent: #2563EB;
    border-color: color-mix(in srgb, var(--language-accent) 45%, transparent);
    border-left: 4px solid var(--language-accent);
    border-radius: 14px;
    background: color-mix(in srgb, var(--language-accent) 7%, transparent);
    box-shadow: 0 5px 18px rgba(15, 23, 42, 0.06);
    padding: 0.2rem;
    transition: border-color 160ms ease, background-color 160ms ease;
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
    input[aria-label="Language / ဘာသာစကား"]:focus-visible
) label[data-baseweb="checkbox"] > div:first-child {
    outline: 3px solid color-mix(in srgb, var(--language-accent) 45%, transparent);
    outline-offset: 3px;
}
@media (prefers-color-scheme: dark) {
    [data-testid="stVerticalBlockBorderWrapper"]:has(
        input[aria-label="Language / ဘာသာစကား"]
    ) {
        background: color-mix(in srgb, var(--language-accent) 13%, transparent);
    }
}
</style>
"""


def apply_page_style() -> None:
    """Inject custom CSS into the Streamlit page."""
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
