import streamlit as st


APP_STYLE = """
<style>
/* Material 3 Expressive-inspired palette */
:root {
    --m3-primary: #3b82f6;
    --m3-on-primary: #ffffff;
    --m3-primary-container: #eaf2ff;
    --m3-on-primary-container: #0f2a52;
    --m3-secondary-container: #eef2f7;
    --m3-surface: #fcfcfd;
    --m3-surface-container: #f5f7fa;
    --m3-surface-container-high: #edf1f5;
    --m3-outline: #cfd8e3;
    --m3-outline-variant: #e4e9f0;
    --m3-on-surface: #111827;
    --m3-on-surface-variant: #4b5563;
    --m3-shadow: 0 1px 4px rgba(17, 24, 39, 0.06);
}

/* Section cards */
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    background: var(--m3-surface-container) !important;
    border: 1px solid var(--m3-outline-variant) !important;
    border-left: 2px solid #bfdbfe !important;
    border-radius: 14px !important;
    box-shadow: var(--m3-shadow) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] > div {
    padding: 0.85rem 0.95rem !important;
}

/* KPI metric cards: subtle, no nested hard borders */
div[data-testid="stMetric"] {
    background: var(--m3-surface) !important;
    border: 1px solid var(--m3-outline-variant) !important;
    border-radius: 16px !important;
    padding: 0.5rem 0.65rem !important;
}
div[data-testid="stMetricLabel"] p {
    color: var(--m3-on-surface-variant) !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em !important;
}
div[data-testid="stMetricValue"] {
    color: var(--m3-on-surface) !important;
}

/* Headings and section emphasis */
h3, h4, h5 {
    color: var(--m3-on-primary-container) !important;
    font-weight: 700 !important;
}

/* Better spacing between column blocks */
div[data-testid="stHorizontalBlock"] { gap: 0.7rem !important; }

/* Selectbox/input accents */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    border-radius: 14px !important;
    border: 1px solid #bfdbfe !important;
    background: var(--m3-surface) !important;
}
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="input"] > div:focus-within {
    border-color: var(--m3-primary) !important;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.20) !important;
}

/* Expander styling */
details {
    background: #f9fbff !important;
    border: 1px solid #e5edfb !important;
    border-radius: 12px !important;
    padding: 0.2rem 0.4rem !important;
}

/* Table header tint */
div[data-testid="stDataFrame"] thead tr th {
    background: #bfdbfe !important;
    color: #1e3a8a !important;
    font-weight: 700 !important;
}

/* Hide Streamlit heading anchor link shown on hover */
a[href^="#"] {
    display: none !important;
}

/* Keep sibling cards visually aligned in desktop layouts */
@media (min-width: 1201px) {
    div[data-testid="column"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        height: 100% !important;
    }
    div[data-testid="column"] > div[data-testid="stVerticalBlockBorderWrapper"] > div {
        height: 100% !important;
    }
}

/* Responsive layout: allow columns to wrap */
@media (max-width: 1200px) {
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    div[data-testid="column"] {
        flex: 1 1 280px !important;
        min-width: 280px !important;
    }
}

@media (max-width: 760px) {
    div[data-testid="column"] {
        min-width: 100% !important;
        flex-basis: 100% !important;
    }
    div[data-testid="stMetric"] label p {
        font-size: 0.82rem !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
}
</style>
"""


def apply_app_styles() -> None:
    st.markdown(APP_STYLE, unsafe_allow_html=True)
