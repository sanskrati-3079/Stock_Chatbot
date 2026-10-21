#!/usr/bin/env bash
# Start the backend locally:  ./start.sh
#
# No need to activate anything first. On the first run (and whenever
# requirements.txt changes) it creates .venv and installs the packages.
# It always runs the project's own Python, never a global uvicorn.
set -e
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
    echo "Python 3.12 or newer is required (found: $(python3 --version 2>&1))." >&2
    exit 1
  fi
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
  echo "Installing requirements..."
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt
  touch .venv/.installed
fi

echo "Starting server at http://localhost:${PORT:-8000}  (docs: /docs, stop: Ctrl+C)"
exec .venv/bin/python -m uvicorn main:app --reload --reload-dir . --port "${PORT:-8000}"
