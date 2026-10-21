"""Personal watchlist with signals at a glance."""

import streamlit as st

from core import api
from core.ui import (
    ANALYZE, SIGNAL_COLORS, SIGNAL_EMOJI, arrow, card, cards_grid, cls, color_for, esc, fmt_money, goto,
    html_block, section, signal_badge, sparkline_svg, toggle_watch,
)


def _add():
    q = st.session_state.get("wl_add", "").strip().upper()
    if q and q not in st.session_state.watchlist:
        st.session_state.watchlist.append(q)
    st.session_state.wl_add = ""


def render(period: str):
    section("Your watchlist", "Track the stocks you care about. Saved for this browser session.", "Watchlist")

    c1, c2 = st.columns([4, 1])
    c1.text_input("Add ticker", key="wl_add", placeholder="Add a ticker — e.g. AMZN, HDFCBANK.NS, ETH-USD",
                  label_visibility="collapsed", on_change=_add)
    c2.button("＋ Add", type="primary", use_container_width=True, on_click=_add)

    wl = st.session_state.watchlist
    if not wl:
        st.info("Your watchlist is empty. Add a ticker above or use ☆ on the Analyze page.")
        return

    with st.spinner("Updating signals…"):
        preds = api.predict_many(tuple(wl), period)

    counts = {"BUY": 0, "HOLD": 0, "SELL": 0}
    for p in preds.values():
        if p:
            counts[p["signal"]] = counts.get(p["signal"], 0) + 1
    avg = [p["change_pct_1d"] for p in preds.values() if p]
    avg_chg = sum(avg) / len(avg) if avg else 0
    cards_grid([
        card("Tracked", str(len(wl)), "tickers"),
        card("Avg. move today", f'<span class="{cls(avg_chg)}">{arrow(avg_chg)} {avg_chg:+.2f}%</span>', "equal-weighted"),
        *[card(f"{SIGNAL_EMOJI[s]} {s}", f'<span style="color:{SIGNAL_COLORS[s]}">{n}</span>', "signals") for s, n in counts.items()],
    ], 160)

    for i in range(0, len(wl), 3):
        cols = st.columns(3)
        for col, tk in zip(cols, wl[i:i + 3]):
            p = preds.get(tk)
            with col:
                if not p:
                    html_block(card(esc(tk), "—", "No data — check the symbol"))
                else:
                    chg = p["change_pct_1d"]
                    html_block(card(
                        f'{esc(p["ticker"])}',
                        f'{fmt_money(p["last_price"], p.get("currency"))}',
                        f'<span class="{cls(chg)}">{arrow(chg)} {chg:+.2f}%</span> · RSI {p["rsi"]:.0f} · '
                        f'{signal_badge(p["signal"], p["confidence"])}',
                        extra=sparkline_svg(p["history_close"][-40:], color_for(p["forecast_trend_pct"])),
                    ))
                b1, b2 = st.columns([3, 1])
                b1.button("Analyze →", key=f"wl_go_{tk}", use_container_width=True, on_click=goto,
                          args=(ANALYZE, p["ticker"] if p else tk))
                b2.button("✕", key=f"wl_rm_{tk}", use_container_width=True, on_click=toggle_watch, args=(tk,),
                          help="Remove from watchlist")
