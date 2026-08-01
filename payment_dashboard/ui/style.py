"""Page-level CSS and theming."""

from __future__ import annotations

import streamlit as st

PAGE_CSS = """
<style>
:root {
    --plum: #6c5ce7;
    --plum-dark: #4e3db8;
    --apricot: #ffb86c;
    --mint: #dff7eb;
    --rose: #ffe1e8;
    --ink: #2b2141;
    --muted: #6f667d;
    --canvas: #fffaf4;
    --surface: #ffffff;
    --sidebar: #2b2141;
    --radius-lg: 22px;
    --shadow-soft: 0 12px 35px rgba(43, 33, 65, 0.10);
}

html, body, [class*="css"] {
    font-family: Inter, "Noto Sans Myanmar", "Myanmar Text", sans-serif;
    background: var(--canvas);
    overflow-x: hidden;
}

.stApp {
    background: var(--canvas);
    color: var(--ink);
}

[data-testid="stMain"] {
    color: var(--ink);
    background: var(--canvas);
    color-scheme: light;
    overflow-x: hidden;
}

[data-testid="stMain"] p,
[data-testid="stMain"] li,
[data-testid="stMain"] label,
[data-testid="stMain"] [data-testid="stMarkdownContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stWidgetLabel"] {
    color: #334155 !important;
}

[data-testid="stMain"] h1,
[data-testid="stMain"] h2,
[data-testid="stMain"] h3,
[data-testid="stMain"] h4,
[data-testid="stMain"] h5,
[data-testid="stMain"] h6 {
    color: #0f172a !important;
}

[data-testid="stSidebar"] {
    background: var(--sidebar);
}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #ffffff !important;
}

.block-container {
    max-width: 1440px;
    padding-top: 2rem;
    padding-bottom: 4rem;
}

.playful-hero {
    position: relative;
    isolation: isolate;
    overflow: hidden;
    margin-bottom: 1.5rem;
    padding: 2.25rem 2.5rem;
    border-radius: var(--radius-lg);
    background: linear-gradient(120deg, #4c1d95, #5b21b6 58%, #7c2d12);
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
    background: rgba(15, 23, 42, 0.18);
    content: "";
}

.playful-hero::before {
    top: -7rem;
    right: 8%;
}

.playful-hero::after {
    right: -5rem;
    bottom: -8rem;
    background: rgba(15, 23, 42, 0.12);
}

.playful-hero h1,
.playful-hero p {
    color: #ffffff !important;
}

.playful-hero h1 {
    max-width: 50rem;
    margin: 0.2rem 0 0.7rem;
    font-size: clamp(1.9rem, 4vw, 3.25rem);
    line-height: 1.15;
}

.hero-eyebrow {
    margin: 0;
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.hero-subtitle {
    max-width: 48rem;
    margin-bottom: 1rem;
    line-height: 1.6;
}

.status-pill {
    display: inline-block;
    max-width: 100%;
    padding: 0.45rem 0.8rem;
    border: 1px solid rgba(255, 255, 255, 0.6);
    border-radius: 999px;
    background: rgba(43, 33, 65, 0.28);
    color: #ffffff;
    font-size: 0.85rem;
    font-weight: 750;
    overflow-wrap: anywhere;
}

.empty-state {
    max-width: 44rem;
    margin: 1.5rem auto 2rem;
    padding: 2rem;
    border: 1px solid #e7defa;
    border-radius: var(--radius-lg);
    background: linear-gradient(135deg, #ffffff, #f9f6ff);
    box-shadow: var(--shadow-soft);
    text-align: center;
}

.empty-state h2 { margin: 0.5rem 0; }
.empty-state p { margin: 0.35rem auto 1rem; }

.empty-mascot {
    display: block;
    width: 6rem;
    height: 6rem;
    max-width: 100%;
    margin: 0 auto 0.75rem;
}

.empty-action {
    display: inline-block;
    padding: 0.45rem 0.8rem;
    border-radius: 999px;
    background: var(--mint);
    color: var(--ink);
    font-weight: 750;
}

[data-testid="stMetric"] {
    height: 100%;
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid #eee9f8;
    border-top: 5px solid var(--plum);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    box-shadow: 0 6px 20px rgba(15, 23, 42, 0.05);
}

.st-key-kpi_transactions [data-testid="stMetric"] { border-top-color: var(--plum); }
.st-key-kpi_success [data-testid="stMetric"] { border-top-color: #37a977; }
.st-key-kpi_failed [data-testid="stMetric"] { border-top-color: #e56b88; }
.st-key-kpi_latency [data-testid="stMetric"] { border-top-color: var(--apricot); }
.st-key-kpi_alerts [data-testid="stMetric"] { border-top-color: #5b9bd5; }

.kpi-icon {
    display: inline-grid;
    width: 2rem;
    height: 2rem;
    margin-bottom: 0.35rem;
    place-items: center;
    border-radius: 10px;
    background: #ede9fe;
    color: #4c1d95;
    font-size: 1.1rem;
    font-weight: 800;
}

.st-key-kpi_success .kpi-icon { background: #dff7eb; color: #166534; }
.st-key-kpi_failed .kpi-icon { background: #ffe1e8; color: #9f1239; }
.st-key-kpi_latency .kpi-icon { background: #ffedd5; color: #9a3412; }
.st-key-kpi_alerts .kpi-icon { background: #e0f2fe; color: #075985; }

[data-testid="stMetricLabel"] { color: #475569; }
[data-testid="stMetricValue"] { color: #0f172a; }

.stButton > button {
    min-height: 2.6rem;
    border: 2px solid var(--plum);
    border-radius: 12px;
    background: var(--surface);
    color: var(--plum-dark);
    font-weight: 750;
}

.stButton > button[kind="primary"] {
    background: var(--plum);
    color: #ffffff;
}

.stButton > button:hover { border-color: var(--plum-dark); background: #f2efff; }
.stButton > button[kind="primary"]:hover { background: var(--plum-dark); }

button:focus-visible,
input:focus-visible,
textarea:focus-visible,
select:focus-visible,
[role="button"]:focus-visible {
    outline: 3px solid var(--apricot) !important;
    outline-offset: 3px;
}

[data-testid="stAlert"] {
    border-radius: 14px;
}

[data-testid="stNotificationContentSuccess"] {
    border-left: 5px solid #15803d;
    background: #dcfce7;
}

[data-testid="stNotificationContentInfo"] {
    border-left: 5px solid #0369a1;
    background: #e0f2fe;
}

[data-testid="stNotificationContentError"] {
    border-left: 5px solid #be123c;
    background: #ffe4e6;
}

[data-testid="stNotificationContentWarning"] {
    border-left: 5px solid #b45309;
    background: #fef3c7;
}

[data-testid="stAlert"],
[data-testid="stAlert"] p,
[data-testid="stAlert"] li {
    color: #0f172a !important;
}

.st-key-ai_brief_card {
    margin: 1.25rem 0;
    padding: 1.5rem;
    border: 1px solid #7c3aed;
    border-radius: var(--radius-lg);
    background: linear-gradient(135deg, #4c1d95, #6d28d9);
    box-shadow: var(--shadow-soft);
}

.st-key-ai_brief_card,
.st-key-ai_brief_card p,
.st-key-ai_brief_card li,
.st-key-ai_brief_card [data-testid="stCaptionContainer"],
.st-key-ai_brief_card [data-testid="stWidgetLabel"],
.st-key-ai_brief_card h1,
.st-key-ai_brief_card h2,
.st-key-ai_brief_card h3,
.st-key-ai_brief_card h4,
.st-key-ai_brief_card h5,
.st-key-ai_brief_card h6 {
    color: #ffffff !important;
}

.st-key-ai_brief_card [data-testid="stAlert"] p,
.st-key-ai_brief_card [data-testid="stAlert"] li {
    color: #0f172a !important;
}

.st-key-ai_brief_result {
    padding: 1.25rem 1.4rem;
    border: 1px solid #e7defa;
    border-radius: var(--radius-lg);
    background: linear-gradient(135deg, #ffffff, #f9f6ff);
    box-shadow: var(--shadow-soft);
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
.st-key-ai_brief_result h6 { color: #0f172a !important; }
.st-key-ai_brief_result a { color: #1d4ed8 !important; }
.st-key-ai_brief_result code { color: #7c2d12 !important; background: #fff7ed; }

div[data-testid="stDataFrame"] {
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 4px 16px rgba(43, 33, 65, 0.06);
}

[data-testid="stExpander"] {
    border: 1px solid #e7defa;
    border-radius: 14px;
    background: var(--surface);
}

[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stDateInput"] input {
    border-radius: 10px;
    border-color: #cfc6e8;
    background: #ffffff;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: rgba(255, 255, 255, 0.22);
    border-radius: 14px;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]
) {
    --language-accent: #2563eb;
    border: 0;
    background: transparent;
    box-shadow: none;
    padding: 0;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]:checked
) { --language-accent: #d4a017; }

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
) [data-testid="stCaptionContainer"] { color: #0f172a !important; }

[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]
) [data-testid="stWidgetLabel"] { color: #ffffff !important; }

[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]
) [data-testid="stCaptionContainer"] { color: #ffffff !important; }

[data-testid="stVerticalBlockBorderWrapper"]:has(
    input[aria-label="Language / ဘာသာစကား"]:focus-visible
) label[data-baseweb="checkbox"] > div:first-child {
    outline: 3px solid color-mix(in srgb, var(--language-accent) 45%, transparent);
    outline-offset: 3px;
}

@media (max-width: 768px) {
    html, body, .stApp, [data-testid="stMain"] { overflow-x: hidden; }
    .block-container { padding: 1rem 0.9rem 2.5rem; }
    .playful-hero { margin-bottom: 1rem; padding: 1.45rem 1.25rem; }
    .playful-hero::before, .playful-hero::after { display: none; }
    .playful-hero h1, .hero-subtitle, .status-pill,
    [data-testid="stMetric"], [data-testid="stAlert"] { overflow-wrap: anywhere; }
    [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
    [data-testid="stHorizontalBlock"]:has(.st-key-kpi_transactions)
    > [data-testid="stColumn"] {
        flex: 1 1 100%;
        min-width: 100%;
    }
    [data-testid="stMetric"] { padding: 0.85rem 0.9rem; }
    .st-key-ai_brief_result { padding: 1rem; }
}
</style>
"""


def apply_page_style() -> None:
    """Inject custom CSS into the Streamlit page."""
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
