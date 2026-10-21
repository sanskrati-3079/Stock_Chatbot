"""Educational content: indicators, signal methodology and glossary."""

import streamlit as st

from core.ui import cards_grid, html_block, section

INDICATORS = [
    ("📉", "RSI (Relative Strength Index)",
     "Measures the speed of recent price moves on a 0–100 scale over 14 sessions. Above 70 suggests the stock is "
     "overbought (may pull back); below 30 suggests oversold (may bounce)."),
    ("〰️", "SMA 20 / SMA 50",
     "Simple moving averages of the last 20 and 50 closing prices. When the faster SMA 20 is above the slower "
     "SMA 50 the short-term trend is up — a “golden cross” style setup."),
    ("📊", "MACD (12, 26, 9)",
     "The gap between the 12- and 26-day exponential averages, compared with its own 9-day average. A positive "
     "histogram means upward momentum is building."),
    ("🎚️", "Bollinger Bands",
     "A 20-day average with bands two standard deviations above and below. Prices hugging the upper band signal "
     "strength; wide bands mean high volatility."),
    ("🔮", "Linear trend forecast",
     "A straight line fitted to the last 30 closes and extended five sessions ahead. Good for direction, not "
     "precise targets."),
    ("🌪️", "Volatility & drawdown",
     "Volatility is the annualized standard deviation of daily returns. Max drawdown is the largest fall from a "
     "peak during the period — a gauge of downside risk."),
]

SCORING = [
    ("RSI below 30", "+2"), ("RSI above 70", "−2"),
    ("SMA 20 above SMA 50", "+1"), ("SMA 20 below SMA 50", "−1"),
    ("MACD histogram positive", "+1"), ("MACD histogram negative", "−1"),
    ("Forecast trend above +1%", "+1"), ("Forecast trend below −1%", "−1"),
]

GLOSSARY = {
    "Ticker": "The short symbol a security trades under, e.g. AAPL. Indian stocks add .NS (NSE) or .BO (BSE).",
    "Candlestick": "A bar showing a session's open, high, low and close. Green when it closed higher than it opened.",
    "Volume": "The number of shares traded in a session. Big moves on high volume are considered more meaningful.",
    "Sharpe ratio": "Return per unit of risk. Above 1 is generally considered good.",
    "Correlation": "How closely two assets move together, from −1 (opposite) to +1 (in lockstep).",
    "Overbought / oversold": "Conditions where price has risen or fallen quickly and may be due for a reversal.",
}


def render(period: str):
    section("Learn the indicators", "Understand exactly what drives every signal you see.", "Learn")
    cards_grid(
        [f'<div class="card feature"><div class="ic">{i}</div><div class="t">{t}</div><div class="d">{d}</div></div>'
         for i, t, d in INDICATORS],
        300,
    )

    section("How the signal is scored", "Each rule adds or subtracts points; the total decides the signal.", "Methodology")
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.dataframe([{"Condition": c, "Points": p} for c, p in SCORING], hide_index=True, use_container_width=True)
    with c2:
        html_block(
            '<div class="card"><div class="k">Decision</div>'
            '<div class="s" style="font-size:.95rem;line-height:1.9;margin-top:8px">'
            '<span class="badge" style="color:#16a34a;border-color:#16a34a66;background:#16a34a1f">BUY</span> score ≥ +2<br>'
            '<span class="badge" style="color:#d97706;border-color:#d9770666;background:#d977061f">HOLD</span> score between −1 and +1<br>'
            '<span class="badge" style="color:#dc2626;border-color:#dc262666;background:#dc26261f">SELL</span> score ≤ −2</div>'
            '<div class="k" style="margin-top:16px">Confidence</div>'
            '<div class="s" style="font-size:.95rem">50% + 12.5% × |score|, capped at 100%.</div></div>'
        )

    section("Glossary", eyebrow="Jargon buster")
    for term, desc in GLOSSARY.items():
        with st.expander(term):
            st.write(desc)

    html_block(
        '<div class="callout" style="margin-top:1.5rem">⚠️ Technical indicators look only at past price and volume. '
        "They ignore earnings, news and macro events, and they can stay “wrong” for a long time. Use them as one input "
        "among many — never as the sole reason to trade.</div>"
    )
