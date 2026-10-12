#!/usr/bin/env bash
set -euo pipefail

: "${STATE_DIRECTORY:?STATE_DIRECTORY is provided by systemd}"
exec "$HOME/stt_api/venv/bin/python" -B -m scripts.sync_edge_outbox \
  --database "$STATE_DIRECTORY/stt_data.db" \
  --endpoint "${EDGE_SYNC_ENDPOINT:?EDGE_SYNC_ENDPOINT is required}" \
  --token "${EDGE_SYNC_TOKEN:?EDGE_SYNC_TOKEN is required}" \
  --batch-size 100 --timeout 30

