"""Client-side indicator and statistics calculations on OHLCV history."""

import numpy as np
import pandas as pd


def to_frame(hist: dict) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "open": hist["open"],
            "high": hist["high"],
            "low": hist["low"],
            "close": hist["close"],
            "volume": hist["volume"],
        },
        index=pd.to_datetime(hist["dates"]),
    )
    return df.dropna(subset=["close"])


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["close"]
    df["sma20"] = close.rolling(20, min_periods=1).mean()
    df["sma50"] = close.rolling(50, min_periods=1).mean()
    std = close.rolling(20, min_periods=1).std().fillna(0)
    df["bb_upper"] = df["sma20"] + 2 * std
    df["bb_lower"] = df["sma20"] - 2 * std

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = (100 - 100 / (1 + rs)).fillna(50)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df


def daily_returns(df: pd.DataFrame) -> pd.Series:
    return df["close"].pct_change().dropna()


def stats(df: pd.DataFrame) -> dict:
    close = df["close"]
    rets = daily_returns(df)
    vol_d = float(rets.std()) if len(rets) > 1 else 0.0
    running_max = close.cummax()
    drawdown = (close / running_max - 1).min()
    mean_d = float(rets.mean()) if len(rets) else 0.0
    return {
        "period_return": float(close.iloc[-1] / close.iloc[0] - 1) * 100 if len(close) > 1 else 0.0,
        "high": float(df["high"].max()),
        "low": float(df["low"].min()),
        "volatility": vol_d * np.sqrt(252) * 100,
        "daily_vol": vol_d,
        "max_drawdown": float(drawdown) * 100,
        "sharpe": (mean_d / vol_d * np.sqrt(252)) if vol_d else 0.0,
        "avg_volume": float(df["volume"].mean()),
        "up_days": float((rets > 0).mean() * 100) if len(rets) else 0.0,
        "best_day": float(rets.max() * 100) if len(rets) else 0.0,
        "worst_day": float(rets.min() * 100) if len(rets) else 0.0,
        "sessions": int(len(df)),
    }


def trades_weekends(index: pd.DatetimeIndex) -> bool:
    return bool((index.dayofweek >= 5).any())
