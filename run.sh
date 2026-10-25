#!/usr/bin/env bash
# SpatialTwin launcher: sets the project up once, rebuilds the frontend when its sources changed, then serves the app.
#
#   ./run.sh               this laptop only: http://127.0.0.1:8000
#   ./run.sh --lan         also reachable by judges' phones on the same Wi-Fi (exit signs, hazard proposals)
#   ./run.sh --port 8010   another port
#   ./run.sh --build       force a frontend rebuild        ./run.sh --setup   set up only, do not serve
#
# Environment: GEMINI_API_KEY (or in .env) enables live Gemini 4 Argon and the managed-agent team; without it every
# local path still works. SPATIALTWIN_SIGN_SECRET (32+ characters) keeps phone links valid across restarts.
# SPATIALTWIN_VENV points at an existing virtualenv (default: ./.venv).
set -euo pipefail
cd "$(dirname "$0")"

HOST=127.0.0.1
PORT=8000
BUILD=auto
SERVE=1
VENV=${SPATIALTWIN_VENV:-.venv}

say()  { printf '\033[1;32m▸\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --lan) HOST=0.0.0.0 ;;
    --port) [ $# -ge 2 ] || die "--port needs a number"; PORT=$2; shift ;;
    --build) BUILD=always ;;
    --no-build) BUILD=never ;;
    --setup) SERVE=0 ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
  shift
done
case "$PORT" in ''|*[!0-9]*) die "--port must be a number" ;; esac

command -v node >/dev/null || die "Node.js is required (https://nodejs.org)"
command -v python3 >/dev/null || [ -x "$VENV/bin/python" ] || die "Python 3.13 is required"

# --- Python: a virtualenv with the exact locked dependencies (re-synced only when the lock changes) ---------------
if [ ! -x "$VENV/bin/python" ]; then
  say "Creating the Python virtualenv in $VENV"
  python3 -m venv "$VENV"
fi
STAMP="$VENV/.spatialtwin-lock"
LOCK_SUM=$(shasum -a 256 requirements.lock | cut -d' ' -f1)
if [ "$(cat "$STAMP" 2>/dev/null || true)" != "$LOCK_SUM" ]; then
  say "Installing Python dependencies (requirements.lock)"
  if command -v uv >/dev/null; then
    uv pip sync --python "$VENV/bin/python" requirements.lock
  else
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet -r requirements.lock
  fi
  echo "$LOCK_SUM" > "$STAMP"
fi

# --- Frontend: install once, rebuild dist/ when any source is newer than the last build ------------------------------
if [ ! -d frontend/node_modules ]; then
  say "Installing frontend dependencies (npm ci)"
  (cd frontend && npm ci --silent)
fi
needs_build=0
case "$BUILD" in
  always) needs_build=1 ;;
  never) ;;
  auto)
    if [ ! -f frontend/dist/index.html ] || [ ! -f frontend/dist/sign.html ] \
       || [ -n "$(find frontend/src frontend/index.html frontend/sign.html frontend/vite.config.ts frontend/package.json \
                   -newer frontend/dist/index.html -print -quit 2>/dev/null)" ]; then
      needs_build=1
    fi ;;
esac
if [ "$needs_build" = 1 ]; then
  say "Building the frontend"
  (cd frontend && npm run build --silent >/dev/null)
fi

[ "$SERVE" = 1 ] || { say "Set up. Start with ./run.sh"; exit 0; }

# --- What this run can do ---------------------------------------------------------------------------------------------
if [ -n "${GEMINI_API_KEY:-}" ] || grep -qs '^GEMINI_API_KEY=.\+' .env; then
  say "Gemini 4 Argon: configured (live readings and the live agent team)"
else
  warn "Gemini 4 Argon: no GEMINI_API_KEY (env or .env). Local planner, saved runs and local agent lanes only."
fi
# Recorded readings of a venue's own maps live in the gitignored runtime/saved-runs (a labelled fallback, never live).
if [ -z "${SPATIALTWIN_REAL2SIM_FIXTURES_DIR:-}" ] && [ -d runtime/saved-runs ]; then
  export SPATIALTWIN_REAL2SIM_FIXTURES_DIR=runtime/saved-runs
fi

URL="http://127.0.0.1:$PORT"
if [ "$HOST" = 0.0.0.0 ]; then
  LAN_IP=$( (ipconfig getifaddr en0 || ipconfig getifaddr en1 || hostname -I | awk '{print $1}') 2>/dev/null | head -1 || true)
  [ -n "$LAN_IP" ] || LAN_IP="<laptop-ip>"
  say "Phones (same Wi-Fi): http://$LAN_IP:$PORT  · the guard admits only scoped sign links"
  [ -n "${SPATIALTWIN_SIGN_SECRET:-}" ] || grep -qs '^SPATIALTWIN_SIGN_SECRET=.\{32,\}' .env \
    || warn "SPATIALTWIN_SIGN_SECRET is not set: phone QR links stop working when the server restarts."
  warn "Never point phones at 'vite --host': its proxy makes every phone look like this laptop."
fi
say "SpatialTwin on $URL  (Ctrl+C to stop)"
exec "$VENV/bin/python" -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT"
