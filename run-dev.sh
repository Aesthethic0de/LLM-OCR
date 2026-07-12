#!/usr/bin/env bash
# Runs the FastAPI backend and the Vite frontend together for local testing.
# Assumes a vLLM server is already running separately (see Backend/README.md).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/Backend"
FRONTEND_DIR="$ROOT_DIR/Frontend"

if [ ! -d "$BACKEND_DIR/.venv" ]; then
  echo "Backend virtualenv not found. Run this first:"
  echo "  cd Backend && python -m venv .venv && ./.venv/Scripts/pip install -r requirements.txt"
  exit 1
fi

if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "Backend/.env not found, copying from .env.example"
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Frontend dependencies not installed. Run this first:"
  echo "  cd Frontend && npm install"
  exit 1
fi

PIDS=()
cleanup() {
  echo
  echo "Stopping backend and frontend..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting backend on http://localhost:8080 ..."
(cd "$BACKEND_DIR" && ./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8080) &
PIDS+=($!)

echo "Starting frontend on http://localhost:5173 ..."
(cd "$FRONTEND_DIR" && npm run dev) &
PIDS+=($!)

wait
