# ruff: noqa: E501
"""Page-level CSS and theming."""

from __future__ import annotations

import streamlit as st

PAGE_CSS = """
<style>
:root {
    --canvas: #07111F;
    --surface: #0D1B2A;
    --surface-raised: #122235;
    --border: #24364B;
    --text: #F8FAFC;
    --muted: #94A3B8;
    --accent: #38BDF8;
    --accent-strong: #0EA5E9;
    --success: #22C55E;
    --warning: #FBBF24;
    --error: #F87171;
    --radius-lg: 16px;
    --shadow-soft: 0 14px 34px rgba(0, 0, 0, 0.24);
}

html, body, [class*="css"] {
    font-family: Inter, "Noto Sans Myanmar", "Myanmar Text", sans-serif;
    background: var(--canvas);
    color: var(--text);
    overflow-x: hidden;
}

.stApp, [data-testid="stMain"] {
    background: var(--canvas);
    color: var(--text);
    color-scheme: dark;
    overflow-x: hidden;
}

[data-testid="stMain"] p,
[data-testid="stMain"] li,
[data-testid="stMain"] label,
[data-testid="stMain"] [data-testid="stMarkdownContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stWidgetLabel"] {
    color: var(--text) !important;
}

[data-testid="stMain"] h1,
[data-testid="stMain"] h2,
[data-testid="stMain"] h3,
[data-testid="stMain"] h4,
[data-testid="stMain"] h5,
[data-testid="stMain"] h6 {
    color: var(--text) !important;
    letter-spacing: -0.02em;
}

[data-testid="stSidebar"] {
    background: #081524;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 { color: #ffffff !important; }

.block-container {
    max-width: 1440px;
    padding-top: 1.25rem;
    padding-bottom: 3rem;
}

.playful-hero {
    position: relative;
    isolation: isolate;
    overflow: hidden;
    margin-bottom: 1rem;
    padding: 1.75rem 2rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: linear-gradient(120deg, var(--surface), #122235 58%, #0F2740);
    box-shadow: var(--shadow-soft);
    color: #ffffff;
}

.playful-hero::before,
.playful-hero::after {
    position: absolute;
    z-index: -1;
    width: 13rem;
    height: 13rem;
    border-radius: 50%;
    background: rgba(56, 189, 248, 0.12);
    content: "";
}

.playful-hero::before { top: -7rem; right: 8%; }
.playful-hero::after { right: -5rem; bottom: -8rem; background: rgba(34, 197, 94, 0.08); }
.playful-hero h1, .playful-hero p { color: #ffffff !important; }
.playful-hero h1 { max-width: 50rem; margin: 0.2rem 0 0.7rem; font-size: clamp(1.9rem, 4vw, 3.25rem); line-height: 1.15; }
.hero-eyebrow { margin: 0; color: var(--accent) !important; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; }
.hero-subtitle { max-width: 48rem; margin-bottom: 1rem; color: var(--muted) !important; line-height: 1.6; }

.status-pill, .status-success, .status-warning, .status-error {
    display: inline-block;
    max-width: 100%;
    padding: 0.38rem 0.72rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--surface-raised);
    color: var(--text);
    font-size: 0.82rem;
    font-weight: 750;
    overflow-wrap: anywhere;
}
.status-success { border-color: var(--success); color: var(--success); }
.status-warning { border-color: var(--warning); color: var(--warning); }
.status-error { border-color: var(--error); color: var(--error); }

.empty-state, .st-key-ai_brief_result {
    max-width: 44rem;
    margin: 1.25rem auto 2rem;
    padding: 1.4rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--surface);
    box-shadow: var(--shadow-soft);
    color: var(--text);
    text-align: center;
}
.empty-state h2, .empty-state p { color: var(--text) !important; }
.empty-state h2 { margin: 0.5rem 0; }
.empty-state p { margin: 0.35rem auto 1rem; }
.empty-mascot { display: block; width: 6rem; height: 6rem; max-width: 100%; margin: 0 auto 0.75rem; }
.empty-action { display: inline-block; padding: 0.45rem 0.8rem; border-radius: 999px; background: var(--accent); color: #06101D; font-weight: 750; }

[data-testid="stMetric"] {
    height: 100%;
    padding: 0.9rem 1rem;
    border: 1px solid var(--border);
    border-top: 3px solid var(--accent);
    border-radius: 12px;
    background: var(--surface);
    box-shadow: var(--shadow-soft);
}
.st-key-kpi_success [data-testid="stMetric"] { border-top-color: var(--success); }
.st-key-kpi_failed [data-testid="stMetric"] { border-top-color: var(--error); }
.st-key-kpi_latency [data-testid="stMetric"] { border-top-color: var(--warning); }
.kpi-icon { display: inline-grid; width: 2rem; height: 2rem; margin-bottom: 0.35rem; place-items: center; border-radius: 8px; background: #123047; color: var(--accent); font-size: 1.1rem; font-weight: 800; }
[data-testid="stMetricLabel"], [data-testid="stMetricValue"] { color: var(--text) !important; }

.stButton > button {
    min-height: 2.45rem;
    border: 1px solid var(--border);
    border-radius: 9px;
    background: var(--surface-raised);
    color: var(--text);
    font-weight: 750;
}
.stButton > button[kind="primary"] { border-color: var(--accent); background: var(--accent); color: #06101D; }
.stButton > button:hover { border-color: var(--accent); background: #123047; }
.stButton > button[kind="primary"]:hover { background: var(--accent-strong); }

[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stDateInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stForm"] {
    border-color: var(--border) !important;
    border-radius: 9px;
    background: var(--surface-raised) !important;
    color: var(--text) !important;
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible,
select:focus-visible,
[role="button"]:focus-visible,
[role="radio"]:focus-visible {
    outline: 3px solid var(--accent) !important;
    outline-offset: 3px;
}

[data-testid="stAlert"] { border: 1px solid var(--border); border-radius: 10px; background: var(--surface-raised); }
[data-testid="stAlert"], [data-testid="stAlert"] p, [data-testid="stAlert"] li { color: var(--text) !important; }
[data-testid="stNotificationContentSuccess"] { border-left: 5px solid #22C55E; background: #103B2A; }
[data-testid="stNotificationContentInfo"] { border-left: 5px solid #38BDF8; background: #123047; }
[data-testid="stNotificationContentError"] { border-left: 5px solid #F87171; background: #3B1D28; }
[data-testid="stNotificationContentWarning"] { border-left: 5px solid #FBBF24; background: #3D3215; }

.st-key-ai_brief_card {
    margin: 1.25rem 0;
    padding: 1.25rem;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: linear-gradient(135deg, #102D47, #0D1B2A);
    box-shadow: var(--shadow-soft);
}
.st-key-ai_brief_card, .st-key-ai_brief_card p, .st-key-ai_brief_card li, .st-key-ai_brief_card [data-testid="stCaptionContainer"], .st-key-ai_brief_card [data-testid="stWidgetLabel"], .st-key-ai_brief_card h1, .st-key-ai_brief_card h2, .st-key-ai_brief_card h3, .st-key-ai_brief_card h4, .st-key-ai_brief_card h5, .st-key-ai_brief_card h6 { color: #ffffff !important; }
.st-key-ai_brief_result, .st-key-ai_brief_result p, .st-key-ai_brief_result li, .st-key-ai_brief_result strong, .st-key-ai_brief_result em, .st-key-ai_brief_result h1, .st-key-ai_brief_result h2, .st-key-ai_brief_result h3, .st-key-ai_brief_result h4, .st-key-ai_brief_result h5, .st-key-ai_brief_result h6 { color: var(--text) !important; }
.st-key-ai_brief_result a { color: var(--accent) !important; }
.st-key-ai_brief_result code { color: var(--warning) !important; background: #122235; }

div[data-testid="stDataFrame"] { max-width: 100%; border: 1px solid var(--border); border-radius: 10px; overflow-x: auto; overflow-y: hidden; background: var(--surface); }
[data-testid="stExpander"] { border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }

[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--border); border-radius: 10px; background: var(--surface); }
[data-testid="stVerticalBlockBorderWrapper"]:has(input[aria-label="Language / ဘာသာစကား"]) { --language-accent: #38BDF8; border: 0; background: transparent; box-shadow: none; padding: 0; }
[data-testid="stVerticalBlockBorderWrapper"]:has(input[aria-label="Language / ဘာသာစကား"]:checked) { --language-accent: #FBBF24; }
[data-testid="stVerticalBlockBorderWrapper"]:has(input[aria-label="Language / ဘာသာစကား"]) label[data-baseweb="checkbox"] > div:first-child { background-color: var(--language-accent) !important; }
[data-testid="stVerticalBlockBorderWrapper"]:has(input[aria-label="Language / ဘာသာစကား"]) [data-testid="stWidgetLabel"], [data-testid="stVerticalBlockBorderWrapper"]:has(input[aria-label="Language / ဘာသာစကား"]) [data-testid="stCaptionContainer"] { color: var(--text) !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]
) [data-testid="stWidgetLabel"] { color: #ffffff !important; }
[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]
) [data-testid="stCaptionContainer"] { color: #ffffff !important; }

div[role="radiogroup"] { display: flex; gap: 0.35rem; overflow-x: auto; padding-bottom: 0.25rem; }
div[role="radiogroup"] label { border: 1px solid var(--border); border-radius: 999px; background: var(--surface); color: var(--text) !important; white-space: nowrap; }

@media (max-width: 1024px) {
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { flex: 1 1 50%; min-width: 50%; }
}
@media (max-width: 768px) {
    html, body, .stApp, [data-testid="stMain"] { overflow-x: hidden; }
    .block-container { padding: 1rem 0.9rem 2.5rem; }
    .playful-hero { margin-bottom: 1rem; padding: 1.4rem 1.2rem; }
    .playful-hero::before, .playful-hero::after { display: none; }
    .playful-hero h1, .hero-subtitle, .status-pill, [data-testid="stMetric"], [data-testid="stAlert"] { overflow-wrap: anywhere; }
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
    [data-testid="stHorizontalBlock"]:has(.st-key-kpi_transactions) > [data-testid="stColumn"] { flex: 1 1 100%; min-width: 100%; }
    [data-testid="stMetric"] { padding: 0.85rem 0.9rem; }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { scroll-behavior: auto !important; transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }
}
</style>
"""


def apply_page_style() -> None:
    """Inject custom CSS into the Streamlit page."""
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
