"""
Offline tests: Yahoo Finance is replaced with synthetic data, so these run
deterministically without network access.

Run from backend/:  pytest -q
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402
import predictor  # noqa: E402
import ticker_resolver  # noqa: E402
from yfinance.exceptions import YFRateLimitError  # noqa: E402

_REAL_YF_SEARCH = ticker_resolver._yf_search


def _make_df(n=130, trend=0.5, start=100.0, nan_rows=()):
    idx = pd.date_range("2026-01-01", periods=n, freq="B", tz="America/New_York")
    close = start + trend * np.arange(n) + np.sin(np.arange(n)) * 2
    df = pd.DataFrame(
        {
            "Open": close - 1,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )
    for i in nan_rows:
        df.iloc[i, df.columns.get_loc("Close")] = np.nan
    if n > 5:
        df.iloc[5, df.columns.get_loc("Volume")] = np.nan  # partial NaN must not break JSON
    return df


class FakeTicker:
    data: dict = {}
    calls = 0
    rate_limited = False

    def __init__(self, symbol):
        self.symbol = symbol

    def history(self, period="1y", interval="1d", auto_adjust=True):
        FakeTicker.calls += 1
        if FakeTicker.rate_limited:
            raise YFRateLimitError()
        return FakeTicker.data.get(self.symbol, pd.DataFrame()).copy()

    @property
    def fast_info(self):
        class Info:
            currency = "USD"
        return Info()


@pytest.fixture(autouse=True)
def fake_yahoo(monkeypatch):
    FakeTicker.data = {
        "AAPL": _make_df(trend=1.0),
        "TCS.NS": _make_df(trend=-1.0, start=4000),
        "RELIANCE.NS": _make_df(trend=0.0, nan_rows=(10, 20)),
        "TINY": _make_df(n=1),
    }
    FakeTicker.calls = 0
    FakeTicker.rate_limited = False
    monkeypatch.setattr(predictor.yf, "Ticker", FakeTicker)
    monkeypatch.setattr(ticker_resolver, "_yf_search", lambda q: None)
    predictor._DATA_CACHE.clear()
    predictor._CURRENCY_CACHE.clear()
    yield


@pytest.fixture
def client():
    return TestClient(main.app)


# ---------------------------------------------------------------- basics

def test_root_and_health(client):
    assert client.get("/").status_code == 200
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_openapi_docs(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


# ---------------------------------------------------------------- /predict

def test_predict_ok(client):
    r = client.get("/stock/AAPL/predict")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["signal"] in {"BUY", "SELL", "HOLD"}
    assert 0 <= body["confidence"] <= 100
    assert len(body["forecast_prices"]) == main.FORECAST_DAYS
    assert body["currency"] == "USD"
    assert len(body["history_close"]) == len(body["history_dates"]) <= 120


def test_predict_uptrend_is_buy_downtrend_is_sell(client):
    assert client.get("/stock/AAPL/predict").json()["forecast_trend_pct"] > 0
    assert client.get("/stock/TCS/predict").json()["forecast_trend_pct"] < 0


def test_predict_resolves_company_name(client):
    r = client.get("/stock/tcs/predict")
    assert r.status_code == 200 and r.json()["ticker"] == "TCS.NS"


def test_predict_with_nan_rows(client):
    r = client.get("/stock/RELIANCE.NS/predict")
    assert r.status_code == 200
    assert None not in r.json()["history_close"]


def test_predict_single_row(client):
    r = client.get("/stock/TINY/predict?forecast_days=3")
    assert r.status_code == 200
    assert len(r.json()["forecast_prices"]) == 3


def test_predict_unknown_ticker_404(client):
    assert client.get("/stock/ZZZZZZ/predict").status_code == 404


@pytest.mark.parametrize("qs", ["forecast_days=0", "forecast_days=-1", "forecast_days=31",
                                "forecast_days=abc", "period=7mo", "period=bogus"])
def test_predict_rejects_bad_params(client, qs):
    assert client.get(f"/stock/AAPL/predict?{qs}").status_code == 422


def test_predict_rate_limit_503(client):
    FakeTicker.rate_limited = True
    r = client.get("/stock/AAPL/predict")
    assert r.status_code == 503


def test_predict_unexpected_error_hides_details(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(main, "analyze_stock", boom)
    r = client.get("/stock/AAPL/predict")
    assert r.status_code == 500
    assert "secret" not in r.text


def test_cache_avoids_refetch(client):
    client.get("/stock/AAPL/predict")
    client.get("/stock/AAPL/predict")
    assert FakeTicker.calls == 1


# ---------------------------------------------------------------- /history

def test_history_ok_and_json_safe(client):
    r = client.get("/stock/AAPL/history?period=6mo&interval=1d")
    assert r.status_code == 200
    body = r.json()
    n = len(body["dates"])
    assert n > 0 and all(len(body[k]) == n for k in ("open", "high", "low", "close", "volume"))
    assert body["volume"][5] is None  # NaN became null, not a crash


def test_history_bad_interval_422(client):
    assert client.get("/stock/AAPL/history?interval=7d").status_code == 422


def test_history_404(client):
    assert client.get("/stock/ZZZZZZ/history").status_code == 404


# ---------------------------------------------------------------- /chat

@pytest.mark.parametrize("message,ticker", [
    ("should I buy TCS?", "TCS.NS"),
    ("predict apple", "AAPL"),
    ("AAPL forecast", "AAPL"),
    ("reliance kharidna chahiye?", "RELIANCE.NS"),
])
def test_chat_resolves_and_replies(client, message, ticker):
    r = client.post("/chat", json={"message": message})
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == ticker
    assert "Signal" in body["reply"]
    assert body["data"]["signal"] in {"BUY", "SELL", "HOLD"}


def test_chat_custom_params(client):
    r = client.post("/chat", json={"message": "AAPL", "period": "1y", "forecast_days": 10})
    assert r.status_code == 200 and len(r.json()["data"]["forecast_prices"]) == 10


def test_chat_no_ticker_found(client):
    r = client.post("/chat", json={"message": "hello there how are you doing"})
    assert r.status_code == 200
    assert r.json()["ticker"] is None


def test_chat_unknown_ticker_friendly_reply(client):
    r = client.post("/chat", json={"message": "ZZZZZZ"})
    assert r.status_code == 200
    assert r.json()["data"] is None


@pytest.mark.parametrize("payload,status", [
    ({"message": "   "}, 400),
    ({}, 422),
    ({"message": "x" * 501}, 422),
    ({"message": "AAPL", "forecast_days": 0}, 422),
    ({"message": "AAPL", "period": "7mo"}, 422),
])
def test_chat_validation(client, payload, status):
    assert client.post("/chat", json=payload).status_code == status


def test_chat_rate_limit_503(client):
    FakeTicker.rate_limited = True
    assert client.post("/chat", json={"message": "AAPL"}).status_code == 503


# ---------------------------------------------------------------- CORS

def test_cors_preflight(client):
    r = client.options("/chat", headers={
        "Origin": "https://example.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] in ("*", "https://example.com")


# ---------------------------------------------------------------- units

def test_forecast_matches_least_squares():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    preds, slope = predictor._forecast_next_days(s, 2)
    assert slope == pytest.approx(1.0)
    assert preds == pytest.approx([5.0, 6.0])


def test_search_failures_not_cached(monkeypatch):
    ticker_resolver._SEARCH_CACHE.clear()
    attempts = {"n": 0}

    class FlakySearch:
        def __init__(self, q, max_results=1):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise ConnectionError("blip")
            self.quotes = [{"symbol": "MSFT"}]

    monkeypatch.setattr(ticker_resolver.yf, "Search", FlakySearch)
    assert _REAL_YF_SEARCH("microsoftish") is None
    assert _REAL_YF_SEARCH("microsoftish") == "MSFT"


@pytest.mark.parametrize("text,expected", [
    ("should I buy ON", "ON"),
    ("hdfc bank", "HDFCBANK.NS"),
    ("bitcoin price", "BTC-USD"),  # must not match "itc"
    ("RELIANCE.NS", "RELIANCE.NS"),
    ("should i invest in nvidia now", "NVDA"),
    ("", None),
])
def test_resolver(text, expected):
    assert ticker_resolver.resolve_ticker(text) == expected
