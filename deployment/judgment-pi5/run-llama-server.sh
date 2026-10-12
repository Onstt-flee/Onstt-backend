#!/usr/bin/env bash
set -euo pipefail

: "${PI_MODEL_DIR:?PI_MODEL_DIR is required}"
: "${PI_MODEL_FILE:?PI_MODEL_FILE is required}"
: "${PI_ADAPTER_FILE:?PI_ADAPTER_FILE is required}"

llama_bin="${LLAMA_SERVER_BIN/#%h/$HOME}"
test -x "$llama_bin"
test -r "$PI_MODEL_DIR/$PI_MODEL_FILE"
test -r "$PI_MODEL_DIR/$PI_ADAPTER_FILE"

exec "$llama_bin" \
  --model "$PI_MODEL_DIR/$PI_MODEL_FILE" \
  --lora "$PI_MODEL_DIR/$PI_ADAPTER_FILE" \
  --alias judgment-v02d \
  --host 127.0.0.1 \
  --port 1234 \
  --ctx-size 2048 \
  --parallel 1 \
  --threads 4 \
  --threads-batch 4

