"""Conversational assistant backed by the /chat endpoint."""

import streamlit as st

from core import api
from core.ui import ANALYZE, cards_grid, goto, html_block, rsi_card, section, signal_badge, signal_card, card, cls, arrow, esc, fmt_money, sparkline_svg, color_for

SUGGESTIONS = ["Should I buy Reliance?", "Predict TCS", "Is Tesla a good buy today?", "NVIDIA forecast"]
GREETING = (
    "Hi! I'm **StockSense**, your stock analysis assistant. Ask me about almost any listed stock worldwide — "
    "US, NSE, BSE, crypto or indices — and I'll give you a technical signal with the reasoning behind it."
)


def _reset():
    st.session_state.messages = [{"role": "assistant", "content": GREETING}]


def _ask(text: str):
    st.session_state.pending_prompt = text


def _render_data(data: dict, idx: int):
    chg, ft = data["change_pct_1d"], data.get("forecast_trend_pct", 0.0)
    html_block(
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
        f'<span style="font-size:1.3rem;font-weight:800;color:#0f172a">{esc(data["ticker"])}</span>'
        f'{signal_badge(data["signal"], data["confidence"])}</div>'
    )
    cards_grid([
        card("Price", fmt_money(data["last_price"], data.get("currency")),
             f'<span class="{cls(chg)}">{arrow(chg)} {chg:+.2f}% today</span>',
             extra=sparkline_svg(data["history_close"][-40:], color_for(ft))),
        signal_card(data),
        rsi_card(float(data["rsi"])),
        card("5-day forecast", f'<span class="{cls(ft)}">{arrow(ft)} {ft:+.2f}%</span>', "Linear trend projection"),
    ], 170)
    with st.expander("Why this signal?"):
        for r in data.get("reasons", []):
            st.markdown(f"- {r}")
    st.button(f"Open full analysis for {data['ticker']} →", key=f"chat_open_{idx}", on_click=goto,
              args=(ANALYZE, data["ticker"]))


def render(period: str):
    if "messages" not in st.session_state:
        _reset()

    c1, c2 = st.columns([5, 1])
    with c1:
        section("AI stock assistant", "Ask in plain English — I'll find the ticker and explain the signal.", "Chat")
    with c2:
        st.write("")
        st.write("")
        st.button("🗑️ Clear chat", use_container_width=True, on_click=_reset)

    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"], avatar="🧑" if msg["role"] == "user" else "🤖"):
            if msg.get("data"):
                _render_data(msg["data"], idx)
            else:
                st.markdown(msg["content"])

    if len(st.session_state.messages) == 1:
        cols = st.columns(len(SUGGESTIONS))
        for col, s in zip(cols, SUGGESTIONS):
            col.button(s, key=f"sug_{s}", use_container_width=True, on_click=_ask, args=(s,))

    prompt = st.chat_input("Ask about a stock, e.g. 'should I buy TCS today?'") or st.session_state.pop("pending_prompt", None)
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analyzing…"):
                result = api.chat(prompt, period)
        st.session_state.messages.append({"role": "assistant", "content": result["reply"], "data": result.get("data")})
        st.rerun()
