#!/usr/bin/env bash
set -euo pipefail

output_dir="${1:?usage: run-benchmark-50.sh OUTPUT_DIR}"
mkdir -p "$output_dir"
python_bin="$HOME/stt_api/venv/bin/python"
raw="$output_dir/pi5-q4-v02d-benchmark50.jsonl"
summary="$output_dir/pi5-q4-v02d-benchmark50.summary.json"

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
  --throttled-before "$before" --throttled-after "$after"

echo "Raw JSONL can contain sentence content and must remain outside Git: $raw"
