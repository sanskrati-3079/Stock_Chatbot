"""
main.py — FastAPI backend for the Stock Prediction Chatbot.

Endpoints:
  GET  /                            -> service info
  GET  /health                      -> liveness check
  GET  /stock/{ticker}/predict      -> full technical analysis + BUY/SELL/HOLD signal
  GET  /stock/{ticker}/history      -> raw OHLC history (for charting)
  POST /chat                        -> natural-language chat endpoint

Run locally with:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Endpoints are plain `def` functions, so FastAPI runs them in its thread
pool and the blocking yfinance calls never stall the event loop.
"""

import logging
import math
import os
import time
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from predictor import analyze_stock, fetch_history, DataSourceError, TickerNotFoundError
from ticker_resolver import resolve_ticker

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("stock_chatbot")

# Values Yahoo Finance actually accepts; anything else is rejected with 422
# instead of silently returning odd data or a 500.
Period = Literal["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
Interval = Literal["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]
VALID_PERIODS = Period.__args__

APP_NAME = os.getenv("APP_NAME", "Stock Prediction Chatbot API")
DEFAULT_PERIOD = os.getenv("DEFAULT_HISTORY_PERIOD", "6mo")
if DEFAULT_PERIOD not in VALID_PERIODS:
    logger.warning("Invalid DEFAULT_HISTORY_PERIOD=%r, falling back to 6mo", DEFAULT_PERIOD)
    DEFAULT_PERIOD = "6mo"
FORECAST_DAYS = min(max(int(os.getenv("FORECAST_DAYS", "5")), 1), 30)
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

app = FastAPI(title=APP_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    # Browsers reject credentialed requests to a wildcard origin, so only
    # enable credentials when explicit origins are configured.
    allow_credentials="*" not in CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=500)
    period: Optional[Period] = None
    forecast_days: Optional[int] = Field(None, ge=1, le=30)


class ChatResponse(BaseModel):
    reply: str
    ticker: Optional[str] = None
    data: Optional[dict] = None


@app.get("/")
def root():
    return {"app": APP_NAME, "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME, "time": time.time()}


@app.get("/stock/{ticker}/predict")
def predict(
    ticker: str,
    period: Period = DEFAULT_PERIOD,
    forecast_days: int = Query(FORECAST_DAYS, ge=1, le=30),
):
    resolved = resolve_ticker(ticker) or ticker.upper()
    try:
        result = analyze_stock(resolved, period=period, forecast_days=forecast_days)
    except TickerNotFoundError:
        raise HTTPException(status_code=404, detail=f"Could not find data for '{ticker}'.")
    except DataSourceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("predict failed for %s", resolved)
        raise HTTPException(status_code=500, detail="Internal error while analysing the stock.")
    return result.__dict__


def _clean(values) -> list:
    """Round floats and turn NaN/inf into None so the response is valid JSON."""
    out = []
    for v in values:
        v = float(v)
        out.append(round(v, 2) if math.isfinite(v) else None)
    return out


@app.get("/stock/{ticker}/history")
def history(ticker: str, period: Period = "1y", interval: Interval = "1d"):
    resolved = resolve_ticker(ticker) or ticker.upper()
    try:
        df = fetch_history(resolved, period=period, interval=interval)
    except TickerNotFoundError:
        raise HTTPException(status_code=404, detail=f"Could not find data for '{ticker}'.")
    except DataSourceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("history failed for %s", resolved)
        raise HTTPException(status_code=500, detail="Internal error while fetching history.")

    return {
        "ticker": resolved,
        "dates": [d.strftime("%Y-%m-%d %H:%M:%S") for d in df.index],
        "open": _clean(df["Open"]),
        "high": _clean(df["High"]),
        "low": _clean(df["Low"]),
        "close": _clean(df["Close"]),
        "volume": [int(v) if math.isfinite(v) else None for v in df["Volume"].astype(float)],
    }


def _format_reply(result) -> str:
    emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(result.signal, "⚪")
    lines = [
        f"{emoji} **{result.ticker}** — Signal: **{result.signal}** (confidence: {result.confidence}%)",
        f"Last price: {result.last_price} ({result.change_pct_1d:+.2f}% today)",
        f"RSI(14): {result.rsi} | SMA20: {result.sma20} | SMA50: {result.sma50}",
        f"{len(result.forecast_prices)}-session forecast trend: {result.forecast_trend_pct:+.2f}%",
        "",
        "Why:",
    ]
    lines += [f"• {r}" for r in result.reasons]
    lines.append("")
    lines.append("_This is an automated technical-analysis signal, not financial advice._")
    return "\n".join(lines)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Empty message.")

    ticker = resolve_ticker(message)
    if not ticker:
        return ChatResponse(
            reply=(
                "I couldn't identify a stock in your message. "
                "Try naming a company or ticker directly, e.g. "
                "\"should I buy TCS\", \"predict AAPL\", or \"RELIANCE.NS\"."
            ),
            ticker=None,
            data=None,
        )

    try:
        result = analyze_stock(
            ticker,
            period=req.period or DEFAULT_PERIOD,
            forecast_days=req.forecast_days or FORECAST_DAYS,
        )
    except TickerNotFoundError:
        return ChatResponse(
            reply=f"I resolved your query to ticker `{ticker}` but couldn't fetch data for it. "
                  f"Please check the symbol (Indian stocks need a .NS or .BO suffix, e.g. TCS.NS).",
            ticker=ticker,
            data=None,
        )
    except DataSourceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        logger.exception("chat failed for %s", ticker)
        raise HTTPException(status_code=500, detail="Internal error while analysing the stock.")

    return ChatResponse(reply=_format_reply(result), ticker=ticker, data=result.__dict__)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
