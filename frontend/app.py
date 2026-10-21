"""
Streamlit frontend for the Stock Prediction Chatbot (StockSense AI).
Talks to the FastAPI backend over REST (see backend/main.py).

The backend URL is read only from the BACKEND_URL environment variable (.env)
and is never displayed in the UI.

Run with:
  streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="StockSense AI", page_icon="📈", layout="wide")

from core import api  # noqa: E402
from core.ui import (  # noqa: E402
    ANALYZE, CHAT, COMPARE, HOME, LEARN, NAV_ITEMS, PERIODS, POPULAR, WATCHLIST,
    goto, html_block, init_state, inject_css,
)
from views import analyze, chat, compare, home, learn, watchlist  # noqa: E402

ROUTES = {
    HOME: home.render,
    ANALYZE: analyze.render,
    COMPARE: compare.render,
    WATCHLIST: watchlist.render,
    CHAT: chat.render,
    LEARN: learn.render,
}

inject_css()
init_state()


def _sidebar_search():
    q = st.session_state.get("sb_search", "").strip()
    if q:
        goto(ANALYZE, q)
    st.session_state.sb_search = ""


# ----------------------------- Navbar -----------------------------
left, right = st.columns([1.3, 4.7], vertical_alignment="center")
with left:
    html_block(
        '<div class="nav-brand"><div class="brand-logo">📈</div>'
        '<div><div class="brand-name">StockSense AI</div><div class="brand-sub">Signals · Forecasts · Chat</div></div></div>'
    )
with right:
    page = st.radio("Navigation", NAV_ITEMS, key="nav", horizontal=True, label_visibility="collapsed")
html_block('<div class="nav-sep"></div>')

# ----------------------------- Sidebar -----------------------------
with st.sidebar:
    online = api.is_online()
    html_block(
        f'<div class="status"><span class="dot" style="background:{"#16a34a" if online else "#dc2626"};'
        f'box-shadow:0 0 8px {"#16a34a" if online else "#dc2626"}"></span>'
        f'{"All systems operational" if online else "Service unavailable"}</div>'
    )

    html_block('<div class="side-label">Quick search</div>')
    st.text_input("Search", key="sb_search", placeholder="🔍  Ticker or company…",
                  label_visibility="collapsed", on_change=_sidebar_search)
    st.button("Analyze", key="sb_go", type="primary", use_container_width=True, on_click=_sidebar_search)

    html_block('<div class="side-label">History period</div>')
    period = st.select_slider("History period", options=PERIODS, key="period", label_visibility="collapsed")

    html_block('<div class="side-label">Popular</div>')
    cols = st.columns(2)
    for i, tk in enumerate(POPULAR):
        active = page == ANALYZE and st.session_state.ticker == tk
        cols[i % 2].button(tk, key=f"pop_{tk}", use_container_width=True,
                           type="primary" if active else "secondary", on_click=goto, args=(ANALYZE, tk))

    if st.session_state.watchlist:
        html_block('<div class="side-label">⭐ Watchlist</div>')
        cols = st.columns(2)
        for i, tk in enumerate(st.session_state.watchlist[:8]):
            cols[i % 2].button(tk, key=f"sbwl_{tk}", use_container_width=True, on_click=goto, args=(ANALYZE, tk))

    html_block(
        '<div class="footer" style="margin-top:1.5rem">⚠️ Educational tool only — signals come from technical '
        "indicators and are <b>not</b> financial advice.</div>"
    )

# ----------------------------- Page -----------------------------
ROUTES[page](period)
