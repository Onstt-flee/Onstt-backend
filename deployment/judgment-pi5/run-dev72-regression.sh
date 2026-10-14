#!/usr/bin/env bash
set -euo pipefail

output_dir="${1:?usage: run-dev72-regression.sh OUTPUT_DIR}"
mkdir -p "$output_dir"
python_bin="$HOME/stt_api/venv/bin/python"
quantization="${EDGE_QUANTIZATION:-Q4_K_M}"
case "$quantization" in
  Q4_K_M) quantization_slug="q4" ;;
  Q5_K_M) quantization_slug="q5" ;;
  *) echo "Unsupported EDGE_QUANTIZATION: $quantization" >&2; exit 2 ;;
esac
run_prefix="$output_dir/pi5-${quantization_slug}-v02d-dev72"

"$python_bin" -B -m evaluation.judgment.runner \
  --dataset "$HOME/stt_api/evaluation/judgment/seed_v0.1.jsonl" \
  --endpoint http://127.0.0.1:1234/v1/chat/completions \
  --model judgment-v02d \
  --output "$run_prefix.jsonl" \
  --prompt-version judgment-v0.2 \
  --temperature 0 --top-p 1 --max-tokens 512 --timeout 120

"$python_bin" -B -m evaluation.judgment.scorer \
  --dataset "$HOME/stt_api/evaluation/judgment/seed_v0.1.jsonl" \
  --run "$run_prefix.jsonl" \
  --output-prefix "$run_prefix"

"$python_bin" -B -m scripts.check_pi_quantization_regression \
  --dataset "$HOME/stt_api/evaluation/judgment/seed_v0.1.jsonl" \
  --reference "$HOME/stt_api/evaluation/judgment/runs/judgment-qwen3-4b-v02d-dev72.jsonl" \
  --candidate "$run_prefix.jsonl" \
  --output "$output_dir/pi5-${quantization_slug}-v02d-quantization-gate.json"

echo "Raw JSONL stays outside Git; retain only aggregate report and SHA-256 references."
