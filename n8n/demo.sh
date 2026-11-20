#!/usr/bin/env bash
# macOS/Linux equivalent of n8n/demo.ps1. Run from the repository root with Node 24 and npm on PATH.
#
#   n8n/demo.sh                 fresh n8n + register, Finn's synthetic walkthrough, then stop
#   n8n/demo.sh --hold          same, but keep both listeners running for a rehearsal
#   n8n/demo.sh --voice         --python, then the closed voice harness (voice/harness.py)
#   n8n/demo.sh --trace         --python, then the live evidence trace (n8n/live-trace.py --decide)
#   n8n/demo.sh --python        also start the Python backend (backend/.env, live BRANE) on
#                               127.0.0.1:8000 wired to this n8n webhook, and send live cases
#
# Env overrides: N8N_PACKAGE (where n8n 2.48.7 is installed, default $TMPDIR/culo-n8n-2-48-7),
#                PYTHON (interpreter with backend/requirements.txt installed, default python3).
set -euo pipefail
HOLD=0 PY=0 TRACE=0 VOICE=0
for arg in "$@"; do
  case "$arg" in
    --hold) HOLD=1 ;;
    --python) PY=1 ;;
    --trace) PY=1 TRACE=1 ;;
    --voice) PY=1 VOICE=1 ;;
    *) echo "unknown option $arg" >&2; exit 2 ;;
  esac
done
cd "$(dirname "$0")/.."
ROOT=$PWD
[ "$(node -p 'process.versions.node.split(".")[0]')" = 24 ] || { echo "Use Node 24 for this demo." >&2; exit 1; }
for port in 5689 8788; do
  if nc -z 127.0.0.1 "$port" 2>/dev/null; then echo "Demo port $port is in use. Use an empty demo instance." >&2; exit 1; fi
done
if [ "$PY" = 1 ] && nc -z 127.0.0.1 8000 2>/dev/null; then echo "Port 8000 is in use." >&2; exit 1; fi

TMP=${TMPDIR:-/tmp}
PACKAGE=${N8N_PACKAGE:-$TMP/culo-n8n-2-48-7}
CLI=$PACKAGE/node_modules/n8n/bin/n8n
if [ ! -f "$CLI" ]; then
  npm install --prefix "$PACKAGE" n8n@2.48.7 --no-audit --no-fund
fi

export N8N_USER_FOLDER
N8N_USER_FOLDER=$(mktemp -d "$TMP/culo-runtime-XXXXXX")
export N8N_LISTEN_ADDRESS=127.0.0.1 N8N_HOST=127.0.0.1 N8N_PORT=5689 N8N_PROTOCOL=http
export N8N_SECURE_COOKIE=false N8N_DIAGNOSTICS_ENABLED=false N8N_VERSION_NOTIFICATIONS_ENABLED=false
export N8N_TEMPLATES_ENABLED=false N8N_LOG_LEVEL=error
export EXECUTIONS_DATA_SAVE_ON_SUCCESS=none EXECUTIONS_DATA_SAVE_ON_ERROR=none
export EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=false EXECUTIONS_DATA_SAVE_ON_PROGRESS=false

PIDS=()
cleanup() { for pid in "${PIDS[@]:-}"; do [ -n "$pid" ] && kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT

node "$CLI" start >"$N8N_USER_FOLDER/n8n.log" 2>&1 &
PIDS+=($!)
for _ in $(seq 1 120); do
  curl -sf http://127.0.0.1:5689/healthz/readiness >/dev/null 2>&1 && break
  kill -0 "${PIDS[0]}" 2>/dev/null || { echo "n8n exited before readiness, see $N8N_USER_FOLDER/n8n.log" >&2; exit 1; }
  sleep 1
done
curl -sf http://127.0.0.1:5689/healthz/readiness >/dev/null || { echo "n8n did not become ready." >&2; exit 1; }

CONFIG=$(node n8n/setup-demo.mjs | tail -n 1)
[ -f "$CONFIG" ] || { echo "Demo setup failed." >&2; exit 1; }
node --env-file="$CONFIG" n8n/service.mjs >"$N8N_USER_FOLDER/register.log" 2>&1 &
PIDS+=($!)
sleep 1
kill -0 "${PIDS[1]}" 2>/dev/null || { echo "Register failed to start." >&2; exit 1; }

node --env-file="$CONFIG" n8n/walkthrough.mjs

if [ "$PY" = 1 ]; then
  N8N_TOKEN=$(grep '^N8N_TOKEN=' "$CONFIG" | cut -d= -f2-)
  ( cd backend && N8N_WEBHOOK_URL=http://127.0.0.1:5689/webhook/protected-case N8N_WEBHOOK_SECRET=$N8N_TOKEN \
      exec "${PYTHON:-python3}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log \
      >"$N8N_USER_FOLDER/backend.log" 2>&1 ) &
  PIDS+=($!)
  for _ in $(seq 1 30); do curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 1; done
  "${PYTHON:-python3}" n8n/live-python.py "$CONFIG" "$ROOT/backend/.env" "$ROOT/data/synthetic_reports.json"
  if [ "$TRACE" = 1 ]; then
    "${PYTHON:-python3}" n8n/live-trace.py "$CONFIG" "$ROOT/backend/.env" "$ROOT/backend" "$ROOT/evidence" --decide
  fi
  if [ "$VOICE" = 1 ]; then
    "${PYTHON:-python3}" voice/harness.py "$CONFIG" "$ROOT/backend/.env" "$ROOT/evidence"
  fi
fi

if [ "$HOLD" = 1 ]; then
  echo "Review at http://127.0.0.1:8788/review as handler. Private demo credentials are in $CONFIG. Keep them off camera."
  read -r -p "Press Enter after the rehearsal to stop this instance " _
fi
