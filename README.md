# 📈 Stock Prediction Chatbot

A chatbot where you can ask about (almost) any listed stock — worldwide — and get:

- A technical analysis (RSI, MACD, SMA20/50, Bollinger-style trend)
- A **BUY / SELL / HOLD** signal with a confidence score
- A short-term price forecast
- An interactive chart

**Stack:** FastAPI (REST backend) + Streamlit (chat frontend) + `yfinance` (free market data — no paid API key needed).

> ⚠️ This is an educational technical-analysis tool, **not financial advice**. Markets are unpredictable; always do your own research.

---

## 1. Project structure

```
stock_chatbot/
├── backend/
│   ├── main.py              # FastAPI app (REST endpoints + chat logic)
│   ├── predictor.py          # indicators, signal scoring, forecasting
│   ├── ticker_resolver.py    # maps chat text / company names -> tickers
│   └── requirements.txt
├── frontend/
│   ├── app.py                # Streamlit chat UI
│   └── requirements.txt
├── .env                       # working default config (no keys required)
├── .env.example
├── run_frontend.sh
└── README.md
```

## 2. Setup

Requires Python 3.12+.

```bash
cd Stock_Chatbot/backend
./start.sh
# -> first run creates .venv and installs everything (about 15 s)
# -> runs FastAPI on http://localhost:8000
# -> interactive API docs at http://localhost:8000/docs
```

No need to create or activate a virtual environment yourself; `start.sh` does it.

## 3. Using the chatbot

Type things like:

- "should I buy Reliance?"
- "predict TCS"
- "AAPL forecast"
- "is Tesla a good buy today?"
- Or just paste a raw ticker: `RELIANCE.NS`, `AAPL`, `BTC-USD`, `^NSEI`

**Ticker coverage:** because the backend uses Yahoo Finance (`yfinance`), it works for essentially any listed instrument — US stocks, Indian stocks (use `.NS` for NSE / `.BO` for BSE), UK/European/Asian exchanges, major indices, and crypto — as long as you give a valid symbol or a name in the built-in name map (`backend/ticker_resolver.py`, easily extendable).

## 4. REST API reference

| Method | Endpoint                          | Description                                  |
|--------|------------------------------------|-----------------------------------------------|
| GET    | `/health`                          | Liveness check                                |
| GET    | `/stock/{ticker}/predict`          | Full analysis + BUY/SELL/HOLD signal          |
| GET    | `/stock/{ticker}/history`          | Raw OHLCV history for custom charting         |
| POST   | `/chat`                            | Body: `{"message": "should I buy TCS"}`       |

Interactive Swagger docs: `http://localhost:8000/docs`

## 5. How the signal is generated

`backend/predictor.py` computes a simple weighted score from:

1. **RSI(14)** — oversold (<30) is bullish, overbought (>70) is bearish
2. **SMA20 vs SMA50** — trend direction
3. **MACD histogram** — momentum
4. **Linear-regression forecast** on the last 30 sessions — short-term trend

The combined score maps to `BUY` / `HOLD` / `SELL` with a confidence percentage. All logic lives in one function (`analyze_stock`) so you can easily swap in a more advanced model (LSTM, Prophet, XGBoost, or a call out to an LLM) later.

## 6. Extending it

- Add more companies to `COMMON_NAME_MAP` in `ticker_resolver.py`.
- Add a paid data provider as fallback (Alpha Vantage / Finnhub) — the `.env` already has placeholders.
- Swap the forecasting model in `predictor.py::_forecast_next_days` for something fancier.
- Deploy the backend on Vercel or Render; see [DEPLOYMENT.md](DEPLOYMENT.md). Deploy the frontend on Streamlit Community Cloud and set `BACKEND_URL` to the backend URL.

## 7. Performance notes

- Yahoo Finance responses are cached in-memory for 5 minutes (`TTLCache`) so repeated chat queries about the same stock are instant.
- yfinance calls are isolated behind a thread pool in the API layer so the event loop doesn't block.
- All indicator math is vectorized with pandas/numpy — no per-row Python loops.
