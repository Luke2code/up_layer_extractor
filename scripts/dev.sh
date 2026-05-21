#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PY="${ROOT}/.venv/bin/python"

if [[ ! -x "${BACKEND_PY}" ]]; then
  echo "Backend venv python not found: ${BACKEND_PY}" >&2
  exit 1
fi

cleanup() {
  jobs -pr | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "${ROOT}"
  PYTHONPATH="${ROOT}" "${BACKEND_PY}" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 4101
) &
backend_pid=$!

(
  cd "${ROOT}/frontend"
  npm run dev
) &
frontend_pid=$!

echo "Backend:  http://127.0.0.1:4101"
echo "Frontend: http://127.0.0.1:4100"

wait -n "${backend_pid}" "${frontend_pid}"
