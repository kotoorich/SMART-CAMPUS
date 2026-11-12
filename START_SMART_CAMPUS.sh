#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Python 3.11/3.12 is required."; exit 1; }
command -v npm >/dev/null || { echo "Node.js 20+ and npm are required."; exit 1; }
[ -f backend/.env ] || cp backend/.env.example backend/.env
[ -f frontend/.env ] || cp frontend/.env.example frontend/.env
[ -x backend/.venv/bin/python ] || python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -r backend/requirements.txt
backend/.venv/bin/python -c "from zoneinfo import ZoneInfo; ZoneInfo('Africa/Accra'); print('Timezone database OK: Africa/Accra')"
if [ ! -d frontend/node_modules ]; then (cd frontend && npm install); fi
( cd backend && ../backend/.venv/bin/python -m uvicorn main:app --reload ) &
BACKEND_PID=$!
( cd frontend && npm run dev -- --host 127.0.0.1 ) &
FRONTEND_PID=$!
trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true' EXIT INT TERM
sleep 8
if command -v xdg-open >/dev/null; then xdg-open http://localhost:5173
elif command -v open >/dev/null; then open http://localhost:5173
fi
wait
