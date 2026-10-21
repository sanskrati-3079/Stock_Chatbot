"""Landing page: hero, live market pulse, trending signals, features, FAQ."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import streamlit as st

from core import api
from core.ui import (
    ANALYZE, CHAT, COMPARE, LEARN, POPULAR, SIGNAL_EMOJI,
    arrow, card, cards_grid, cls, color_for, esc, fmt_money, goto, html_block, section, sparkline_svg,
)

INDICES = [
    ("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ"), ("^DJI", "Dow Jones"),
    ("^NSEI", "NIFTY 50"), ("^BSESN", "SENSEX"), ("BTC-USD", "Bitcoin"),
]

FEATURES = [
    ("🎯", "BUY / HOLD / SELL signals", "A transparent scoring model combining RSI, moving-average crossovers, MACD momentum and trend."),
    ("🔮", "Short-term forecasts", "A regression model projects the next five sessions, with an uncertainty band based on recent volatility."),
    ("🕯️", "Pro-grade charts", "Candlesticks, volume, Bollinger Bands, RSI and MACD panels — interactive and zoomable."),
    ("⚖️", "Side-by-side compare", "Rebase several stocks to 100 and compare returns, volatility, drawdowns and correlation."),
    ("⭐", "Personal watchlist", "Track your favourite tickers and see every signal at a glance in one table."),
    ("💬", "Plain-English chat", "Ask “should I buy Reliance?” — the assistant finds the ticker and explains its reasoning."),
]

STEPS = [
    ("Pick a stock", "Search by ticker or company name — US, NSE, BSE, crypto and indices are all supported."),
    ("We crunch the data", "Live prices from Yahoo Finance feed five technical indicators and a trend model."),
    ("Get a clear answer", "See the signal, its confidence and the exact reasons — then dig into charts and stats."),
]

FAQ = [
    ("Where does the data come from?", "Prices come from Yahoo Finance and are refreshed every few minutes. "
     "Indian stocks use the .NS (NSE) or .BO (BSE) suffix, e.g. TCS.NS."),
    ("How is the signal calculated?", "Each indicator adds or subtracts points: RSI extremes (±2), SMA20 vs SMA50 (±1), "
     "MACD histogram (±1) and the 5-day trend projection (±1). A total of +2 or more is BUY, −2 or less is SELL, "
     "otherwise HOLD. Confidence is 50% + 12.5% per point of score. See the Learn tab for details."),
    ("Is this financial advice?", "No. StockSense is an educational tool based purely on technical indicators. "
     "It ignores fundamentals, news and your personal situation. Always do your own research."),
    ("Which markets are covered?", "Almost any symbol on Yahoo Finance: NYSE, NASDAQ, NSE, BSE, LSE, major indices and crypto."),
]


def _market_status() -> list[tuple[str, bool]]:
    ny = datetime.now(ZoneInfo("America/New_York"))
    ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    us_open = ny.weekday() < 5 and time(9, 30) <= ny.time() < time(16, 0)
    in_open = ist.weekday() < 5 and time(9, 15) <= ist.time() < time(15, 30)
    return [("NYSE", us_open), ("NSE", in_open), ("Crypto", True)]


def _hero():
    pills = "".join(
        f'<span class="pill"><span class="dot" style="background:{"#16a34a" if o else "#94a3b8"};'
        f'box-shadow:0 0 6px {"#16a34a" if o else "transparent"}"></span>{name} · {"Open" if o else "Closed"}</span>'
        for name, o in _market_status()
    )
    html_block(
        '<div class="hero">'
        f'<div class="pills">{pills}</div>'
        "<h1>Smarter stock insights, explained in plain English.</h1>"
        "<p>Technical signals, short-term forecasts and pro-grade charts for thousands of stocks, indices and "
        "crypto — or just ask the AI assistant.</p>"
        '<div class="stats-strip">'
        '<div class="stat"><div class="n">50,000+</div><div class="l">Tickers worldwide</div></div>'
        '<div class="stat"><div class="n">5</div><div class="l">Technical indicators</div></div>'
        '<div class="stat"><div class="n">5-day</div><div class="l">Price forecast</div></div>'
        '<div class="stat"><div class="n">~5 min</div><div class="l">Data freshness</div></div>'
        "</div></div>"
    )
    c1, c2, c3, _ = st.columns([1.2, 1.2, 1.2, 3])
    c1.button("📈 Analyze a stock", type="primary", use_container_width=True, on_click=goto, args=(ANALYZE,))
    c2.button("💬 Ask the AI", use_container_width=True, on_click=goto, args=(CHAT,))
    c3.button("⚖️ Compare stocks", use_container_width=True, on_click=goto, args=(COMPARE,))


def _market_pulse():
    section("Market pulse", "Major indices and crypto over the last month.", "Live overview")
    with st.spinner("Loading markets…"):
        hist = api.history_many(tuple(t for t, _ in INDICES), "1mo")
    items = []
    for tk, name in INDICES:
        h = hist.get(tk)
        if not h or len(h.get("close", [])) < 2:
            items.append(card(name, "—", "Data unavailable"))
            continue
        close = [c for c in h["close"] if c is not None]
        last, prev = close[-1], close[-2]
        d1 = (last / prev - 1) * 100 if prev else 0
        m1 = (last / close[0] - 1) * 100 if close[0] else 0
        items.append(card(
            name, f"{last:,.2f}",
            f'<span class="{cls(d1)}">{arrow(d1)} {d1:+.2f}%</span> today · {m1:+.1f}% 1M',
            extra=sparkline_svg(close, color_for(m1)),
        ))
    cards_grid(items, 140)


def _trending(period: str):
    section("Trending signals", "Today's model output for popular stocks, refreshed every few minutes.", "Signals")
    with st.spinner("Scanning popular stocks…"):
        preds = api.predict_many(tuple(POPULAR), period)
    rows = [p for p in preds.values() if p]
    if not rows:
        st.info(api.SERVICE_DOWN)
        return

    best_buy = max(rows, key=lambda p: (p["signal"] == "BUY", p["confidence"], p["forecast_trend_pct"]))
    oversold = min(rows, key=lambda p: p["rsi"])
    mover = max(rows, key=lambda p: abs(p["change_pct_1d"]))
    highlights = [
        ("🏆 Strongest signal", best_buy, f'{SIGNAL_EMOJI.get(best_buy["signal"], "")} {best_buy["signal"]} · {best_buy["confidence"]:.0f}%'),
        ("🧊 Lowest RSI", oversold, f'RSI {oversold["rsi"]:.1f}'),
        ("⚡ Biggest mover", mover, f'{arrow(mover["change_pct_1d"])} {mover["change_pct_1d"]:+.2f}% today'),
    ]
    cols = st.columns(3)
    for col, (label, p, sub) in zip(cols, highlights):
        with col:
            html_block(card(label, esc(p["ticker"]), f'{fmt_money(p["last_price"], p.get("currency"))} · {sub}',
                            extra=sparkline_svg(p["history_close"][-30:], color_for(p["forecast_trend_pct"]))))
            st.button(f"Analyze {p['ticker']} →", key=f"hl_{label}", use_container_width=True,
                      on_click=goto, args=(ANALYZE, p["ticker"]))

    table = [
        {
            "Ticker": p["ticker"],
            "Price": p["last_price"],
            "1D %": p["change_pct_1d"],
            "Signal": f'{SIGNAL_EMOJI.get(p["signal"], "")} {p["signal"]}',
            "Confidence": p["confidence"],
            "RSI": p["rsi"],
            "5D forecast %": p["forecast_trend_pct"],
            "30D trend": p["history_close"][-30:],
        }
        for p in rows
    ]
    st.dataframe(
        table, hide_index=True, use_container_width=True,
        column_config={
            "Price": st.column_config.NumberColumn(format="%.2f"),
            "1D %": st.column_config.NumberColumn(format="%+.2f%%"),
            "Confidence": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
            "RSI": st.column_config.NumberColumn(format="%.1f"),
            "5D forecast %": st.column_config.NumberColumn(format="%+.2f%%"),
            "30D trend": st.column_config.LineChartColumn(width="medium"),
        },
    )


def _features():
    section("Everything you need to read the market", "Built for curious investors — no jargon required.", "Features")
    cards_grid(
        [f'<div class="card feature"><div class="ic">{i}</div><div class="t">{t}</div><div class="d">{d}</div></div>'
         for i, t, d in FEATURES],
        280,
    )


def _how_it_works():
    section("How it works", eyebrow="3 simple steps")
    cards_grid(
        [f'<div class="card feature step"><div class="num">{n}</div><div class="t">{t}</div><div class="d">{d}</div></div>'
         for n, (t, d) in enumerate(STEPS, 1)],
        260,
    )


def _faq():
    section("Frequently asked questions", eyebrow="FAQ")
    for q, a in FAQ:
        with st.expander(q):
            st.write(a)
    st.button("📚 Learn how the indicators work →", on_click=goto, args=(LEARN,))


def render(period: str):
    _hero()
    _market_pulse()
    _trending(period)
    _features()
    _how_it_works()
    _faq()
    html_block(
        '<div class="footer"><b>StockSense AI</b> · Market data via Yahoo Finance, delayed and refreshed every ~5 minutes.<br>'
        "⚠️ For educational purposes only. Signals are generated from technical indicators and are not financial advice.</div>"
    )
