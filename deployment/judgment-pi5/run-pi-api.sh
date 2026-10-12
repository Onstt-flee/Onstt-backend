#!/usr/bin/env bash
set -euo pipefail

: "${STATE_DIRECTORY:?STATE_DIRECTORY is provided by systemd}"
export STT_DATABASE_URL="sqlite:///$STATE_DIRECTORY/stt_data.db"
export PYTHONPATH="$HOME/stt_api"
exec "$HOME/stt_api/venv/bin/uvicorn" main:app \
  --host 127.0.0.1 --port 8001 --workers 1

