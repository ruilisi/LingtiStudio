#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/app"
API_PORT="${PORT_API:-8000}"
WEB_PORT="${PORT_FRONTEND:-3000}"

mkdir -p \
  "${APP_DIR}/configs" \
  "${APP_DIR}/data/outputs" \
  "${APP_DIR}/data/assets" \
  "${APP_DIR}/data/temp" \
  "${APP_DIR}/data/memory" \
  "${APP_DIR}/data/uploads"

cd "${APP_DIR}"

python3 -m uvicorn api.server:app --host 0.0.0.0 --port "${API_PORT}" &
BACKEND_PID=$!

cd "${APP_DIR}/frontend"
./node_modules/.bin/next start -H 0.0.0.0 -p "${WEB_PORT}" &
FRONTEND_PID=$!

cleanup() {
  kill "${BACKEND_PID}" "${FRONTEND_PID}" 2>/dev/null || true
  wait "${BACKEND_PID}" 2>/dev/null || true
  wait "${FRONTEND_PID}" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

wait -n "${BACKEND_PID}" "${FRONTEND_PID}"
STATUS=$?
cleanup
exit "${STATUS}"

