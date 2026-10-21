"""
predictor.py
Fetches historical price data (via yfinance) and produces:
  - Technical indicators (SMA, EMA, RSI, MACD, Bollinger Bands)
  - A BUY / SELL / HOLD signal with a confidence score
  - A short-term (N-day) price forecast using linear regression on
    recent log-returns (fast, dependency-light, good enough for a
    directional signal — this is NOT financial advice).

Performance / optimization notes:
  - TTLCache avoids re-hitting Yahoo Finance for the same ticker within
    a short window (huge speedup for repeated chat queries).
  - All heavy numeric work is vectorized with pandas/numpy.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from cachetools import TTLCache
from sklearn.linear_model import LinearRegression

# ---------------------------------------------------------------------------
# Simple in-memory TTL cache: ticker+period -> dataframe (5 minute freshness)
# ---------------------------------------------------------------------------
_DATA_CACHE: TTLCache = TTLCache(maxsize=256, ttl=300)


class TickerNotFoundError(Exception):
    pass


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    cache_key = f"{ticker}|{period}|{interval}"
    if cache_key in _DATA_CACHE:
        return _DATA_CACHE[cache_key]

    tk = yf.Ticker(ticker)
    df = tk.history(period=period, interval=interval, auto_adjust=True)
    if df is None or df.empty:
        raise TickerNotFoundError(f"No data found for ticker '{ticker}'.")

    df = df.dropna(how="all")
    _DATA_CACHE[cache_key] = df
    return df


def _sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).mean()


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _macd(series: pd.Series):
    ema12 = _ema(series, 12)
    ema26 = _ema(series, 26)
    macd_line = ema12 - ema26
    signal_line = _ema(macd_line, 9)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def _bollinger(series: pd.Series, window: int = 20, num_std: float = 2.0):
    mid = _sma(series, window)
    std = series.rolling(window=window, min_periods=1).std().fillna(0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def _forecast_next_days(series: pd.Series, days_ahead: int = 5):
    """Lightweight linear-regression forecast on the last 30 sessions."""
    recent = series.tail(30).reset_index(drop=True)
    X = np.arange(len(recent)).reshape(-1, 1)
    y = recent.values
    model = LinearRegression()
    model.fit(X, y)
    future_X = np.arange(len(recent), len(recent) + days_ahead).reshape(-1, 1)
    preds = model.predict(future_X)
    slope = model.coef_[0]
    return preds.tolist(), float(slope)


@dataclass
class PredictionResult:
    ticker: str
    currency: Optional[str]
    last_price: float
    change_pct_1d: float
    signal: str                 # BUY / SELL / HOLD
    confidence: float            # 0-100
    reasons: list[str] = field(default_factory=list)
    rsi: float = 0.0
    macd_hist: float = 0.0
    sma20: float = 0.0
    sma50: float = 0.0
    forecast_prices: list[float] = field(default_factory=list)
    forecast_trend_pct: float = 0.0
    history_dates: list[str] = field(default_factory=list)
    history_close: list[float] = field(default_factory=list)
    history_sma20: list[float] = field(default_factory=list)
    history_sma50: list[float] = field(default_factory=list)


def analyze_stock(ticker: str, period: str = "6mo", forecast_days: int = 5) -> PredictionResult:
    df = fetch_history(ticker, period=period)
    close = df["Close"]

    sma20 = _sma(close, 20)
    sma50 = _sma(close, 50)
    rsi = _rsi(close, 14)
    macd_line, signal_line, hist = _macd(close)
    upper_bb, mid_bb, lower_bb = _bollinger(close)

    last_price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2]) if len(close) > 1 else last_price
    change_pct_1d = ((last_price - prev_price) / prev_price * 100) if prev_price else 0.0

    last_rsi = float(rsi.iloc[-1])
    last_hist = float(hist.iloc[-1])
    last_sma20 = float(sma20.iloc[-1])
    last_sma50 = float(sma50.iloc[-1])

    forecast_prices, slope = _forecast_next_days(close, forecast_days)
    forecast_trend_pct = ((forecast_prices[-1] - last_price) / last_price * 100) if last_price else 0.0

    # ---------------- Scoring model for BUY / SELL / HOLD ----------------
    score = 0
    reasons = []

    if last_rsi < 30:
        score += 2
        reasons.append(f"RSI is {last_rsi:.1f} (oversold, bullish signal).")
    elif last_rsi > 70:
        score -= 2
        reasons.append(f"RSI is {last_rsi:.1f} (overbought, bearish signal).")
    else:
        reasons.append(f"RSI is {last_rsi:.1f} (neutral zone).")

    if last_sma20 > last_sma50:
        score += 1
        reasons.append("Short-term average (20d) is above long-term average (50d) — uptrend.")
    else:
        score -= 1
        reasons.append("Short-term average (20d) is below long-term average (50d) — downtrend.")

    if last_hist > 0:
        score += 1
        reasons.append("MACD histogram positive — bullish momentum.")
    else:
        score -= 1
        reasons.append("MACD histogram negative — bearish momentum.")

    if forecast_trend_pct > 1:
        score += 1
        reasons.append(f"Linear trend model projects +{forecast_trend_pct:.2f}% over next {forecast_days} sessions.")
    elif forecast_trend_pct < -1:
        score -= 1
        reasons.append(f"Linear trend model projects {forecast_trend_pct:.2f}% over next {forecast_days} sessions.")
    else:
        reasons.append("Linear trend model projects roughly flat price action.")

    if score >= 2:
        signal = "BUY"
    elif score <= -2:
        signal = "SELL"
    else:
        signal = "HOLD"

    confidence = min(100.0, 50 + abs(score) * 12.5)

    currency = None
    try:
        info = yf.Ticker(ticker).fast_info
        currency = getattr(info, "currency", None)
    except Exception:
        pass

    hist_tail = df.tail(120)
    return PredictionResult(
        ticker=ticker.upper(),
        currency=currency,
        last_price=round(last_price, 2),
        change_pct_1d=round(change_pct_1d, 2),
        signal=signal,
        confidence=round(confidence, 1),
        reasons=reasons,
        rsi=round(last_rsi, 2),
        macd_hist=round(last_hist, 4),
        sma20=round(last_sma20, 2),
        sma50=round(last_sma50, 2),
        forecast_prices=[round(p, 2) for p in forecast_prices],
        forecast_trend_pct=round(forecast_trend_pct, 2),
        history_dates=[d.strftime("%Y-%m-%d") for d in hist_tail.index],
        history_close=[round(v, 2) for v in hist_tail["Close"].tolist()],
        history_sma20=[round(v, 2) for v in sma20.tail(120).tolist()],
        history_sma50=[round(v, 2) for v in sma50.tail(120).tolist()],
    )
