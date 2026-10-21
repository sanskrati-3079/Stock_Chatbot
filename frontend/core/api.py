"""
Thin client for the FastAPI backend.

The backend address comes only from the BACKEND_URL environment variable and is
never shown to users — failures surface as a generic "service unavailable" message.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

_BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
_POOL = ThreadPoolExecutor(max_workers=8)
log = logging.getLogger("stock_frontend.api")

SERVICE_DOWN = "The analysis service is temporarily unavailable. Please try again in a moment."


class ApiError(Exception):
    def __init__(self, message: str, not_found: bool = False):
        super().__init__(message)
        self.not_found = not_found


def _get(path: str, params: dict | None = None, timeout: int = 30) -> dict:
    try:
        resp = requests.get(f"{_BACKEND}{path}", params=params, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        log.warning("GET %s failed: %s", path, exc)
        raise ApiError(SERVICE_DOWN) from None
    if resp.status_code == 404:
        raise ApiError("Ticker not found.", not_found=True)
    if not resp.ok:
        log.warning("GET %s -> %s %s", path, resp.status_code, resp.text[:200])
        raise ApiError(SERVICE_DOWN)
    return resp.json()


def _predict_raw(ticker: str, period: str) -> dict:
    return _get(f"/stock/{quote(ticker, safe='')}/predict", {"period": period})


def _history_raw(ticker: str, period: str) -> dict:
    return _get(f"/stock/{quote(ticker, safe='')}/history", {"period": period, "interval": "1d"})


@st.cache_data(ttl=300, show_spinner=False)
def predict(ticker: str, period: str = "6mo") -> dict:
    return _predict_raw(ticker, period)


@st.cache_data(ttl=300, show_spinner=False)
def history(ticker: str, period: str = "6mo") -> dict:
    return _history_raw(ticker, period)


def _many(fn, tickers: tuple[str, ...], period: str) -> dict[str, dict | None]:
    def safe(tk):
        try:
            return fn(tk, period)
        except ApiError:
            return None

    return dict(zip(tickers, _POOL.map(safe, tickers)))


@st.cache_data(ttl=300, show_spinner=False)
def predict_many(tickers: tuple[str, ...], period: str = "6mo") -> dict[str, dict | None]:
    return _many(_predict_raw, tickers, period)


@st.cache_data(ttl=300, show_spinner=False)
def history_many(tickers: tuple[str, ...], period: str = "1mo") -> dict[str, dict | None]:
    return _many(_history_raw, tickers, period)


@st.cache_data(ttl=30, show_spinner=False)
def is_online() -> bool:
    try:
        return requests.get(f"{_BACKEND}/health", timeout=3).ok
    except requests.exceptions.RequestException:
        return False


def chat(message: str, period: str) -> dict:
    try:
        resp = requests.post(f"{_BACKEND}/chat", json={"message": message, "period": period}, timeout=45)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as exc:
        log.warning("chat failed: %s", exc)
        return {"reply": f"⚠️ {SERVICE_DOWN}", "ticker": None, "data": None}
