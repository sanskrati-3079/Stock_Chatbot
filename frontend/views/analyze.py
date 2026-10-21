"""Deep-dive analysis for a single ticker."""

import math

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import api
from core.indicators import add_indicators, stats, to_frame, trades_weekends
from core.ui import (
    ACCENT, BB_C, DOWN, LEARN, NEUTRAL, POPULAR, SIGNAL_COLORS, SMA20_C, SMA50_C, UP,
    arrow, card, cards_grid, cls, color_for, esc, fmt_big, fmt_money, goto, html_block,
    remember, rsi_card, show_fig, signal_badge, signal_card, style_fig, toggle_watch,
)
from datetime import timedelta


def _on_search():
    q = st.session_state.get("an_search", "").strip()
    if q:
        st.session_state.ticker = q
    st.session_state.an_search = ""


def _search_bar():
    c1, c2 = st.columns([5, 1])
    c1.text_input("Search", key="an_search", placeholder="🔍  Search ticker or company — e.g. NVDA, Infosys, BTC-USD",
                  label_visibility="collapsed", on_change=_on_search)
    c2.button("Analyze", key="an_go", type="primary", use_container_width=True, on_click=_on_search)
    chips = st.session_state.recent[:6] or POPULAR[:6]
    cols = st.columns(len(chips))
    for col, tk in zip(cols, chips):
        col.button(tk, key=f"chip_{tk}", use_container_width=True, on_click=goto, args=(st.session_state.nav, tk))


def _forecast_dates(df, n):
    last = df.index[-1]
    weekends = trades_weekends(df.index)
    out = []
    while len(out) < n:
        last += timedelta(days=1)
        if weekends or last.weekday() < 5:
            out.append(last)
    return out


# ----------------------------- Tabs -----------------------------
def _price_tab(df, data):
    c1, c2, c3 = st.columns([1.2, 3, 1])
    kind = c1.selectbox("Chart type", ["Candlestick", "Line", "Area"], key="an_kind")
    overlays = c2.multiselect("Overlays", ["SMA 20", "SMA 50", "Bollinger Bands", "Forecast"],
                              default=["SMA 20", "SMA 50", "Forecast"], key="an_overlays")
    show_vol = c3.toggle("Volume", value=True, key="an_vol")

    rows = 2 if show_vol else 1
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.78, 0.22] if show_vol else [1])
    if kind == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="Price",
            increasing=dict(line=dict(color=UP), fillcolor=UP), decreasing=dict(line=dict(color=DOWN), fillcolor=DOWN),
        ), 1, 1)
    else:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["close"], name="Close", line=dict(color=ACCENT, width=2.4),
            fill="tozeroy" if kind == "Area" else None, fillcolor="rgba(109,74,255,0.10)",
        ), 1, 1)

    if "Bollinger Bands" in overlays:
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_upper"], name="BB upper", line=dict(color=BB_C, width=1)), 1, 1)
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_lower"], name="BB lower", line=dict(color=BB_C, width=1),
                                 fill="tonexty", fillcolor="rgba(148,163,184,0.15)"), 1, 1)
    if "SMA 20" in overlays:
        fig.add_trace(go.Scatter(x=df.index, y=df["sma20"], name="SMA 20", line=dict(color=SMA20_C, width=1.5)), 1, 1)
    if "SMA 50" in overlays:
        fig.add_trace(go.Scatter(x=df.index, y=df["sma50"], name="SMA 50", line=dict(color=SMA50_C, width=1.5)), 1, 1)
    fc = data.get("forecast_prices") or []
    if "Forecast" in overlays and fc:
        fx = [df.index[-1]] + _forecast_dates(df, len(fc))
        fy = [df["close"].iloc[-1]] + fc
        fig.add_trace(go.Scatter(x=fx, y=fy, name="Forecast", mode="lines+markers",
                                 line=dict(color=color_for(fy[-1] - fy[0]), width=2, dash="dash"), marker=dict(size=5)), 1, 1)

    if show_vol:
        colors = [UP if c >= o else DOWN for o, c in zip(df["open"], df["close"])]
        fig.add_trace(go.Bar(x=df.index, y=df["volume"], name="Volume", marker_color=colors, opacity=0.5,
                             showlegend=False), 2, 1)

    style_fig(fig, 560 if show_vol else 480)
    fig.update_layout(xaxis_rangeslider_visible=False)
    if not trades_weekends(df.index):
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    show_fig(fig, "an_price")


def _indicators_tab(df):
    fig = go.Figure()
    fig.add_hrect(y0=70, y1=100, fillcolor=DOWN, opacity=0.08, line_width=0)
    fig.add_hrect(y0=0, y1=30, fillcolor=UP, opacity=0.08, line_width=0)
    fig.add_hline(y=70, line=dict(color=DOWN, dash="dot", width=1))
    fig.add_hline(y=30, line=dict(color=UP, dash="dot", width=1))
    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI (14)", line=dict(color=ACCENT, width=2)))
    style_fig(fig, 260)
    fig.update_yaxes(range=[0, 100])
    st.markdown("**RSI (14)** — above 70 is overbought, below 30 is oversold.")
    show_fig(fig, "an_rsi")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"], name="Histogram",
                         marker_color=[UP if v >= 0 else DOWN for v in df["macd_hist"]], opacity=0.6))
    fig.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD", line=dict(color=SMA50_C, width=1.8)))
    fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Signal", line=dict(color=SMA20_C, width=1.8)))
    style_fig(fig, 280)
    st.markdown("**MACD (12, 26, 9)** — histogram above zero signals bullish momentum.")
    show_fig(fig, "an_macd")


def _forecast_tab(df, data, st_):
    fc = data.get("forecast_prices") or []
    if not fc:
        st.info("No forecast available for this ticker.")
        return
    last = float(df["close"].iloc[-1])
    dates = _forecast_dates(df, len(fc))
    band = [last * st_["daily_vol"] * math.sqrt(i) for i in range(1, len(fc) + 1)]
    tail = df.tail(60)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tail.index, y=tail["close"], name="History", line=dict(color=ACCENT, width=2.2)))
    fx = [df.index[-1]] + dates
    fig.add_trace(go.Scatter(x=fx, y=[last] + [p + b for p, b in zip(fc, band)], line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fx, y=[last] + [p - b for p, b in zip(fc, band)], line=dict(width=0),
                             fill="tonexty", fillcolor="rgba(109,74,255,0.12)", name="±1σ range", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fx, y=[last] + fc, name="Forecast", mode="lines+markers",
                             line=dict(color=color_for(fc[-1] - last), width=2.4, dash="dash")))
    style_fig(fig, 400)
    if not trades_weekends(df.index):
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])

    c1, c2 = st.columns([2.2, 1])
    with c1:
        show_fig(fig, "an_forecast")
    with c2:
        st.dataframe(
            [{"Date": d.strftime("%a %d %b"), "Price": p, "vs today": (p / last - 1) * 100} for d, p in zip(dates, fc)],
            hide_index=True, use_container_width=True,
            column_config={"Price": st.column_config.NumberColumn(format="%.2f"),
                           "vs today": st.column_config.NumberColumn(format="%+.2f%%")},
        )
        html_block('<div class="callout">The forecast is a linear trend fitted to the last 30 sessions. The shaded '
                   "band shows a ±1 standard-deviation range from recent volatility. Treat it as a direction, "
                   "not a price target.</div>")


def _stats_tab(st_, cur):
    cards_grid([
        card("Period return", f'<span class="{cls(st_["period_return"])}">{st_["period_return"]:+.2f}%</span>', f'{st_["sessions"]} sessions'),
        card("Period high", fmt_money(st_["high"], cur), "Highest intraday price"),
        card("Period low", fmt_money(st_["low"], cur), "Lowest intraday price"),
        card("Volatility", f'{st_["volatility"]:.1f}%', "Annualized std. deviation"),
        card("Max drawdown", f'<span class="down">{st_["max_drawdown"]:.2f}%</span>', "Worst peak-to-trough fall"),
        card("Sharpe ratio", f'{st_["sharpe"]:.2f}', "Annualized, risk-free = 0"),
        card("Best day", f'<span class="up">{st_["best_day"]:+.2f}%</span>', "Largest daily gain"),
        card("Worst day", f'<span class="down">{st_["worst_day"]:+.2f}%</span>', "Largest daily loss"),
        card("Up days", f'{st_["up_days"]:.0f}%', "Share of sessions closing higher"),
        card("Avg volume", fmt_big(st_["avg_volume"]), "Shares traded per session"),
    ], 180)


def _signal_tab(data):
    color = SIGNAL_COLORS.get(data["signal"], NEUTRAL)
    c1, c2 = st.columns([1, 1.6])
    with c1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=data["confidence"], number=dict(suffix="%", font=dict(color="#0f172a")),
            title=dict(text=f"<b>{data['signal']}</b> confidence", font=dict(color=color, size=16)),
            gauge=dict(
                axis=dict(range=[0, 100], tickcolor="#94a3b8"), bar=dict(color=color, thickness=0.3),
                bgcolor="rgba(0,0,0,0)", borderwidth=0,
                steps=[dict(range=[0, 50], color="#f1f5f9"), dict(range=[50, 100], color="#e2e8f0")],
            ),
        ))
        style_fig(fig, 280, legend=False)
        show_fig(fig, "an_gauge")
    with c2:
        st.markdown("**Why this signal?**")
        items = []
        for i, r in enumerate(data.get("reasons", []), 1):
            low = r.lower()
            c = UP if any(w in low for w in ("bullish", "uptrend", "+")) else DOWN if any(w in low for w in ("bearish", "downtrend")) else NEUTRAL
            items.append(f'<div class="reason"><div class="i" style="background:{c}22;color:{c}">{i}</div><div>{esc(r)}</div></div>')
        html_block(f'<div class="reasons" style="grid-template-columns:1fr">{"".join(items)}</div>')
        st.button("📚 How is the signal calculated?", on_click=goto, args=(LEARN,))


# ----------------------------- Page -----------------------------
def render(period: str):
    _search_bar()
    ticker = st.session_state.ticker

    with st.spinner(f"Analyzing {ticker}…"):
        try:
            data = api.predict(ticker, period)
        except api.ApiError as exc:
            if exc.not_found:
                st.error(f"Couldn't find data for **{ticker}**. Check the symbol — Indian stocks need a .NS or .BO suffix (e.g. TCS.NS).")
            else:
                st.error(api.SERVICE_DOWN)
            return
        try:
            df = add_indicators(to_frame(api.history(ticker, period)))
        except api.ApiError:
            df = None

    tk, cur = data["ticker"], data.get("currency")
    remember(tk)
    chg = data["change_pct_1d"]

    html_block(
        '<div class="an-head"><div>'
        f'<div class="an-ticker">{esc(tk)} {signal_badge(data["signal"], data["confidence"])}</div>'
        f'<div class="an-meta">Technical analysis · {esc(cur or "")} · {period} history</div></div>'
        f'<div class="an-price"><div class="v">{fmt_money(data["last_price"], cur)}</div>'
        f'<div class="chg {cls(chg)}">{arrow(chg)} {chg:+.2f}% today</div></div></div>'
    )
    in_wl = tk in st.session_state.watchlist
    b1, _ = st.columns([1.2, 5])
    b1.button("★ In watchlist" if in_wl else "☆ Add to watchlist", use_container_width=True,
              on_click=toggle_watch, args=(tk,), type="secondary" if in_wl else "primary")

    ft = data.get("forecast_trend_pct", 0.0)
    sma20, sma50 = data["sma20"], data["sma50"]
    macd = data.get("macd_hist", 0.0)
    cards_grid([
        signal_card(data),
        rsi_card(float(data["rsi"])),
        card("MACD histogram", f'<span class="{cls(macd)}">{macd:+.3f}</span>', "Bullish momentum" if macd > 0 else "Bearish momentum"),
        card("SMA 20 / 50", fmt_money(sma20, cur),
             f'vs {fmt_money(sma50, cur)} · <span class="{cls(sma20 - sma50)}">{"Uptrend" if sma20 > sma50 else "Downtrend"}</span>'),
        card(f'{len(data.get("forecast_prices") or [])}-day forecast', f'<span class="{cls(ft)}">{arrow(ft)} {ft:+.2f}%</span>',
             "Linear trend projection"),
    ], 160)

    if df is None or df.empty:
        st.warning("Detailed price history is unavailable right now — showing summary only.")
        _signal_tab(data)
        return

    t1, t2, t3, t4, t5 = st.tabs(["📈 Price chart", "📊 Indicators", "🔮 Forecast", "📋 Statistics", "🧠 Signal breakdown"])
    with t1:
        _price_tab(df, data)
    with t2:
        _indicators_tab(df)
    s = stats(df)
    with t3:
        _forecast_tab(df, data, s)
    with t4:
        _stats_tab(s, cur)
    with t5:
        _signal_tab(data)
