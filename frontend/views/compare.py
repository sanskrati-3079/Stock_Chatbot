"""Compare several tickers side by side."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import api
from core.indicators import stats, to_frame
from core.ui import POPULAR, SIGNAL_EMOJI, section, show_fig, style_fig

PALETTE = ["#6d4aff", "#0891b2", "#d97706", "#16a34a", "#dc2626", "#db2777"]


def _add_custom():
    q = st.session_state.get("cmp_add", "").strip().upper()
    if q:
        opts = st.session_state.setdefault("cmp_options", list(POPULAR))
        if q not in opts:
            opts.append(q)
        sel = st.session_state.get("cmp_sel", [])
        if q not in sel and len(sel) < 6:
            st.session_state.cmp_sel = sel + [q]
    st.session_state.cmp_add = ""


def render(period: str):
    section("Compare stocks", "Rebase up to six tickers to 100 and compare performance, risk and signals.", "Compare")
    st.session_state.setdefault("cmp_options", list(POPULAR))
    st.session_state.setdefault("cmp_sel", ["AAPL", "MSFT", "NVDA"])

    c1, c2 = st.columns([3, 1.4])
    sel = c1.multiselect("Tickers", st.session_state.cmp_options, key="cmp_sel", max_selections=6)
    c2.text_input("Add another ticker", key="cmp_add", placeholder="e.g. AMZN, HDFCBANK.NS", on_change=_add_custom)

    if len(sel) < 2:
        st.info("Pick at least two tickers to compare.")
        return

    with st.spinner("Fetching data…"):
        hists = api.history_many(tuple(sel), period)
        preds = api.predict_many(tuple(sel), period)

    frames = {tk: to_frame(h) for tk, h in hists.items() if h and h.get("close")}
    missing = [tk for tk in sel if tk not in frames]
    if missing:
        st.warning(f"No data for: {', '.join(missing)}")
    if len(frames) < 2:
        return

    # Normalised performance (dates aligned on the date part only)
    closes = pd.DataFrame({tk: df["close"].set_axis(df.index.normalize()) for tk, df in frames.items()}).sort_index()
    closes = closes.ffill().dropna()
    rebased = closes / closes.iloc[0] * 100

    fig = go.Figure()
    for i, tk in enumerate(rebased.columns):
        fig.add_trace(go.Scatter(x=rebased.index, y=rebased[tk], name=tk, line=dict(color=PALETTE[i % len(PALETTE)], width=2.2),
                                 hovertemplate="%{y:.1f}<extra>" + tk + "</extra>"))
    fig.add_hline(y=100, line=dict(color="#94a3b8", dash="dot", width=1))
    style_fig(fig, 440)
    show_fig(fig, "cmp_perf")

    rows = []
    for tk, df in frames.items():
        s = stats(df)
        p = preds.get(tk) or {}
        rows.append({
            "Ticker": tk,
            "Price": float(df["close"].iloc[-1]),
            "Return %": s["period_return"],
            "Volatility %": s["volatility"],
            "Max DD %": s["max_drawdown"],
            "Sharpe": s["sharpe"],
            "RSI": p.get("rsi"),
            "Signal": f'{SIGNAL_EMOJI.get(p.get("signal"), "")} {p.get("signal", "—")}',
            "Confidence": p.get("confidence"),
        })
    rows.sort(key=lambda r: r["Return %"], reverse=True)
    st.dataframe(
        rows, hide_index=True, use_container_width=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="%.2f"),
            "Return %": st.column_config.NumberColumn(format="%+.2f%%"),
            "Volatility %": st.column_config.NumberColumn(format="%.1f%%"),
            "Max DD %": st.column_config.NumberColumn(format="%.2f%%"),
            "Sharpe": st.column_config.NumberColumn(format="%.2f"),
            "RSI": st.column_config.NumberColumn(format="%.1f"),
            "Confidence": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
        },
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Correlation of daily returns**")
        corr = closes.pct_change().dropna().corr().round(2)
        fig = go.Figure(go.Heatmap(z=corr.values, x=corr.columns, y=corr.index, zmin=-1, zmax=1,
                                   colorscale=[[0, "#dc2626"], [0.5, "#f8fafc"], [1, "#6d4aff"]],
                                   text=corr.values, texttemplate="%{text}", showscale=False))
        style_fig(fig, 340, legend=False)
        fig.update_layout(hovermode="closest")
        fig.update_yaxes(side="left", autorange="reversed")
        show_fig(fig, "cmp_corr")
    with c2:
        st.markdown("**Risk vs. return**")
        fig = go.Figure()
        for i, r in enumerate(rows):
            fig.add_trace(go.Scatter(x=[r["Volatility %"]], y=[r["Return %"]], mode="markers+text", text=[r["Ticker"]],
                                     textposition="top center", name=r["Ticker"],
                                     marker=dict(size=16, color=PALETTE[i % len(PALETTE)], line=dict(width=0))))
        style_fig(fig, 340, legend=False)
        fig.update_layout(hovermode="closest")
        fig.update_xaxes(title="Annualized volatility %", showgrid=True, gridcolor="rgba(15,23,42,0.07)")
        fig.update_yaxes(title="Period return %", side="left")
        show_fig(fig, "cmp_risk")
