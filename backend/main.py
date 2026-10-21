"""
main.py — FastAPI backend for the Stock Prediction Chatbot.

Endpoints:
  GET  /health                      -> liveness check
  GET  /stock/{ticker}/predict      -> full technical analysis + BUY/SELL/HOLD signal
  GET  /stock/{ticker}/history      -> raw OHLC history (for charting)
  POST /chat                        -> natural-language chat endpoint

Run with:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from predictor import analyze_stock, fetch_history, TickerNotFoundError
from ticker_resolver import resolve_ticker

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "Stock Prediction Chatbot API")
DEFAULT_PERIOD = os.getenv("DEFAULT_HISTORY_PERIOD", "6mo")
FORECAST_DAYS = int(os.getenv("FORECAST_DAYS", "5"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app = FastAPI(title=APP_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thread pool so blocking yfinance calls don't stall the event loop.
_executor = ThreadPoolExecutor(max_workers=8)


class ChatRequest(BaseModel):
    message: str
    period: Optional[str] = None
    forecast_days: Optional[int] = None


class ChatResponse(BaseModel):
    reply: str
    ticker: Optional[str] = None
    data: Optional[dict] = None


@app.get("/health")
def health():
    return {"status": "ok", "app": APP_NAME, "time": time.time()}


@app.get("/stock/{ticker}/predict")
def predict(ticker: str, period: str = DEFAULT_PERIOD, forecast_days: int = FORECAST_DAYS):
    resolved = resolve_ticker(ticker) or ticker.upper()
    try:
        result = analyze_stock(resolved, period=period, forecast_days=forecast_days)
    except TickerNotFoundError:
        raise HTTPException(status_code=404, detail=f"Could not find data for '{ticker}'.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return result.__dict__


@app.get("/stock/{ticker}/history")
def history(ticker: str, period: str = "1y", interval: str = "1d"):
    resolved = resolve_ticker(ticker) or ticker.upper()
    try:
        df = fetch_history(resolved, period=period, interval=interval)
    except TickerNotFoundError:
        raise HTTPException(status_code=404, detail=f"Could not find data for '{ticker}'.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "ticker": resolved,
        "dates": [d.strftime("%Y-%m-%d %H:%M:%S") for d in df.index],
        "open": df["Open"].round(2).tolist(),
        "high": df["High"].round(2).tolist(),
        "low": df["Low"].round(2).tolist(),
        "close": df["Close"].round(2).tolist(),
        "volume": df["Volume"].tolist(),
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return ChatResponse(reply=_format_reply(result), ticker=ticker, data=result.__dict__)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
