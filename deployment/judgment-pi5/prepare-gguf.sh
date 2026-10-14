#!/usr/bin/env bash
set -euo pipefail

: "${LLAMA_CPP_DIR:?LLAMA_CPP_DIR is required}"
: "${BASE_MODEL_DIR:?BASE_MODEL_DIR is required}"
: "${LORA_DIR:?LORA_DIR is required}"
: "${OUTPUT_DIR:?OUTPUT_DIR is required}"

test -d "$LLAMA_CPP_DIR/.git"
test -f "$BASE_MODEL_DIR/config.json"
test -f "$LORA_DIR/adapter_config.json"
mkdir -p "$OUTPUT_DIR"

llama_commit="$(git -C "$LLAMA_CPP_DIR" rev-parse HEAD)"
python_bin="${CONVERSION_PYTHON:-python3}"
f16="$OUTPUT_DIR/Qwen3-4B-Instruct-2507-F16.gguf"
q4="$OUTPUT_DIR/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
adapter="$OUTPUT_DIR/judgment-v0.2-d-f16.gguf"
quantize_bin="${LLAMA_QUANTIZE_BIN:-$LLAMA_CPP_DIR/build/bin/llama-quantize}"

"$python_bin" "$LLAMA_CPP_DIR/convert_hf_to_gguf.py" \
  "$BASE_MODEL_DIR" --outfile "$f16" --outtype f16
"$quantize_bin" "$f16" "$q4" Q4_K_M
"$python_bin" "$LLAMA_CPP_DIR/convert_lora_to_gguf.py" \
  "$LORA_DIR" --base "$BASE_MODEL_DIR" --outfile "$adapter" --outtype f16
"$python_bin" -B -m scripts.write_pi_model_manifest \
  --output "$OUTPUT_DIR/pi5-model-manifest.json" \
  --llama-commit "$llama_commit" --model "$q4" --adapter "$adapter" \
  --quantization Q4_K_M

echo "GGUF conversion completed; original HF and PEFT directories were not modified."
