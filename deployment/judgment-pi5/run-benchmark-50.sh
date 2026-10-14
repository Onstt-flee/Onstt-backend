#!/usr/bin/env bash
set -euo pipefail

output_dir="${1:?usage: run-benchmark-50.sh OUTPUT_DIR}"
mkdir -p "$output_dir"
python_bin="$HOME/stt_api/venv/bin/python"
quantization="${EDGE_QUANTIZATION:-Q4_K_M}"
case "$quantization" in
  Q4_K_M) quantization_slug="q4" ;;
  Q5_K_M) quantization_slug="q5" ;;
  *) echo "Unsupported EDGE_QUANTIZATION: $quantization" >&2; exit 2 ;;
esac
: "${EDGE_MODEL_SHA256:?EDGE_MODEL_SHA256 must be set from the active Pi manifest}"
: "${EDGE_ADAPTER_SHA256:?EDGE_ADAPTER_SHA256 must be set from the active Pi manifest}"
raw="$output_dir/pi5-${quantization_slug}-v02d-benchmark50.jsonl"
summary="$output_dir/pi5-${quantization_slug}-v02d-benchmark50.summary.json"

before="$(vcgencmd get_throttled)"
"$python_bin" -B -m evaluation.judgment.runner \
  --dataset "$HOME/stt_api/evaluation/judgment/seed_v0.1.jsonl" \
  --endpoint http://127.0.0.1:1234/v1/chat/completions \
  --model judgment-v02d --output "$raw" --limit 50 \
  --prompt-version judgment-v0.2 --temperature 0 --top-p 1 \
  --max-tokens 512 --timeout 120
after="$(vcgencmd get_throttled)"
memory_peak="$(systemctl --user show judgment-pi5-llama.service -p MemoryPeak --value)"

"$python_bin" -B -m scripts.summarize_pi5_benchmark \
  --run "$raw" --output "$summary" --memory-peak-bytes "$memory_peak" \
  --throttled-before "$before" --throttled-after "$after" \
  --quantization "$quantization" \
  --model-sha256 "$EDGE_MODEL_SHA256" \
  --adapter-sha256 "$EDGE_ADAPTER_SHA256"

echo "Raw JSONL can contain sentence content and must remain outside Git: $raw"
