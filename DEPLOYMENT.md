# Deploying the backend

The backend (`backend/`) is a stateless FastAPI app. It needs **no database and no API keys**; market data comes from Yahoo Finance via `yfinance`. It runs on Python 3.12 (pinned in `backend/.python-version`).

## Requirements at a glance

| What | Value |
|---|---|
| Python | 3.12, 3.13 or 3.14 (3.11 and older won't work) |
| Install | `pip install -r requirements.txt` |
| Start | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health check | `GET /health` |
| Root directory | `backend` |
| Secrets | none |
| Outbound network | needs HTTPS access to `*.yahoo.com` |
| Memory | 512 MB is enough |

### Environment variables (all optional)

| Name | Default | Notes |
|---|---|---|
| `CORS_ORIGINS` | `*` | Comma-separated. In production, set it to your frontend URL(s), e.g. `https://my-app.vercel.app` |
| `DEFAULT_HISTORY_PERIOD` | `6mo` | One of `1d 5d 1mo 3mo 6mo 1y 2y 5y 10y ytd max` |
| `FORECAST_DAYS` | `5` | Clamped to 1–30 |
| `APP_NAME` | `Stock Prediction Chatbot API` | |
| `LOG_LEVEL` | `INFO` | |
| `YF_CACHE_DIR` | system temp dir | Where yfinance keeps its small on-disk cache |

`backend/.env` is only for local development and is gitignored. On a host, set variables in its dashboard.

---

## Option A: Vercel (serverless)

1. Push the repo to GitHub.
2. On vercel.com, click **Add New → Project** and import the repo.
3. Set **Root Directory** to `backend`. Vercel detects FastAPI from `main.py` automatically.
4. Optionally add `CORS_ORIGINS` under **Environment Variables**.
5. Click **Deploy**, then run `python backend/smoke_test.py https://<your-project>.vercel.app`.

From the CLI: `npm i -g vercel`, then `cd backend && vercel` (preview) or `vercel --prod`.

`backend/vercel.json` sets a 60 s max duration, and `backend/.vercelignore` keeps `.env`, `.venv` and the tests out of the upload. The bundle is about 130 MB, under Vercel's 500 MB limit.

**Trade-offs:** each instance has its own 5-minute in-memory cache, so a cold start costs 1–3 s and the first request for each stock is slower.

## Option B: Render (always-on server; simplest)

1. Push to GitHub.
2. On render.com, click **New → Blueprint** and pick the repo. It reads `render.yaml`.
   - Manual alternative: **New → Web Service**, Root Directory `backend`, Build `pip install -r requirements.txt`, Start `uvicorn main:app --host 0.0.0.0 --port $PORT`, Health Check Path `/health`.
3. The free plan sleeps after 15 minutes idle, and the first request after that takes about 30–50 s. The paid plan doesn't sleep.

---

## Before you deploy

```bash
cd backend
./start.sh                           # sets up .venv on first run, then starts the server
# in a second terminal:
.venv/bin/python -m pytest -q        # offline tests (Yahoo is mocked)
.venv/bin/python smoke_test.py       # live checks against real Yahoo data
```

## Known risk: Yahoo Finance rate limits on cloud IPs

Yahoo sometimes throttles requests from data-centre IPs (AWS, GCP and others; Vercel runs on AWS). When that happens the API returns **503** with a clear message instead of crashing, and the 5-minute cache cuts repeat calls. If you see frequent 503s in production:

- Prefer an always-on host (such as Render), where the in-memory cache is shared by every request.
- For heavy or commercial use, add a paid data provider (Finnhub, Twelve Data or Alpha Vantage) as a fallback in `predictor.fetch_history`.

## Connecting a frontend

Point the frontend at the deployed URL, e.g. `BACKEND_URL=https://<your-backend>`, and set `CORS_ORIGINS` on the backend to the frontend's URL.
