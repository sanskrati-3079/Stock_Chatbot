#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/frontend"
pip install -r requirements.txt
cp -n ../.env . 2>/dev/null || true
streamlit run app.py
