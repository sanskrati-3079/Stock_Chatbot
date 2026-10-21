#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"
pip install -r requirements.txt
cp -n ../.env . 2>/dev/null || true
uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
