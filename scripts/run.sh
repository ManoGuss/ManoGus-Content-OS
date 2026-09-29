#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT
cd frontend
npm run dev
