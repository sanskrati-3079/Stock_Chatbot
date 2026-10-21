"""
Smoke-test a running/deployed backend against live Yahoo Finance data.
Uses only the standard library, so it runs anywhere.

  python smoke_test.py https://your-app.vercel.app
  python smoke_test.py                # defaults to http://localhost:8000
"""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read()), time.time() - start
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), time.time() - start


CHECKS = [
    ("GET", "/health", None, 200),
    ("GET", "/stock/AAPL/predict", None, 200),
    ("GET", "/stock/RELIANCE.NS/predict", None, 200),
    ("GET", "/stock/BTC-USD/history?period=1mo", None, 200),
    ("GET", "/stock/NOPE_XYZ123/predict", None, 404),
    ("GET", "/stock/AAPL/predict?forecast_days=0", None, 422),
    ("POST", "/chat", {"message": "should I buy TCS?"}, 200),
    ("POST", "/chat", {"message": "is Tesla a good buy today?"}, 200),
]

failed = 0
for method, path, body, expected in CHECKS:
    status, payload, secs = call(method, path, body)
    ok = status == expected
    failed += not ok
    hint = payload.get("detail") or payload.get("signal") or (payload.get("data") or {}).get("signal") or ""
    print(f"{'PASS' if ok else 'FAIL'}  {status}  {secs:5.2f}s  {method} {path}  {str(hint)[:60]}")

print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} checks passed against {BASE}")
sys.exit(1 if failed else 0)
