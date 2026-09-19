#!/usr/bin/env bash
# Convenience script: sets up and runs the full stack locally without Docker.
# Usage: bash scripts/dev_setup.sh
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Backend setup =="
cd "$ROOT_DIR/backend"
if [ ! -d venv ]; then
  python -m venv venv
fi
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate
pip install -r requirements.txt
python -m app.ml.train_sla
python -m app.seed

echo "== Starting backend (background) =="
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "Backend running (PID $BACKEND_PID) on http://localhost:8000"

echo "== Frontend setup =="
cd "$ROOT_DIR/frontend"
npm install

echo "== Starting frontend =="
npm run dev
