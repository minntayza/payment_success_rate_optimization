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
</style>
"""


def apply_page_style() -> None:
    """Inject custom CSS into the Streamlit page."""
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
