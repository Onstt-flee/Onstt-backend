# 실제 GPU/Pi 판단쌍 수집 절차

기준일: 2026-10-15

## 목적과 현재 상태

feedback-v0.2는 내부 시험지에서 허위 불일치 안전 기준을 실패했다. 다음 모델을 바로
재학습하지 않고 실제 GPU BF16과 Pi GGUF가 같은 입력에 만든 판단쌍을 먼저 확보한다.
현재 실제 Pi 산출물이 없으므로 수집 건수는 0이며 새 feedback holdout과 학습은
차단된 상태다.

`scripts/prepare_feedback_runtime_pairs.py`는 다음만 수행한다.

- GPU/Pi JSONL의 입력 집합이 완전히 같은지 확인
- 원시 응답을 다시 파싱해 저장된 판단과 일치하는지 확인
- GPU runner manifest와 GPU JSONL SHA-256 대조
- Pi 50건 벤치마크 summary가 Pi JSONL·Q4/Q5·모델·어댑터 해시를 증명하는지 확인
- 문장과 ID가 없는 집계 JSON만 생성

런타임 일치도는 문법 정확도가 아니다. 실제 판단쌍 50개가 통과해도 독립 라벨 없이는
`feedback_holdout_ready=false`가 유지된다.

## 1. 같은 50개 입력 실행

GPU 서버에서 v0.2-D를 현재 고정 조건으로 실행한다. 아래 출력 디렉터리는 Git에서
제외된다.

```bash
cd /home/cap-minsung/stt_api
mkdir -p evaluation/feedback/intake

venv/bin/python -m evaluation.judgment.runner \
  --dataset evaluation/judgment/seed_v0.1.jsonl \
  --endpoint http://127.0.0.1:1234/v1/chat/completions \
  --model judgment-v02d \
  --output evaluation/feedback/intake/gpu-v02d-pi50.jsonl \
  --limit 50 --prompt-version judgment-v0.2 \
  --temperature 0 --top-p 1 --max-tokens 512 --timeout 120
```

Pi에서는 Q5 후보 환경을 명시적으로 선택하고 기존 벤치마크 스크립트를 실행한다.

```bash
cd /home/cap-minsung/stt_api
set -a
source deployment/judgment-pi5/pi5-q5-candidate.env
set +a
deployment/judgment-pi5/run-benchmark-50.sh "$HOME/pi5-evaluation/feedback-pairs-v01"
```

Pi에서 생성된 다음 두 파일만 private network의 GPU 서버
`evaluation/feedback/intake/`로 복사한다.

- `pi5-q5-v02d-benchmark50.jsonl`
- `pi5-q5-v02d-benchmark50.summary.json`

문장 내용이 든 JSONL을 Git, 공개 링크, 채팅 또는 보고서에 첨부하지 않는다.

## 2. 해시 준비

- GPU adapter SHA-256:
  `2e758256afe68c3005b595f9f664b5f76734606b923dbb2c7bc858e81e9e55c6`
- GPU HF 모델 manifest SHA-256:
  `86cf6cbe487216982ba0cc0adafa649925d1f2e61d86b2fc63cfe34f99f91013`
- Pi Q5 model SHA-256:
  `c393c664d0749b8b0e797895a284d7260bb1e813b7aeb318e04b08ae0c3f5f2f`
- Pi GGUF LoRA SHA-256:
  `e513c35c51b02f19ece2890337dde242e019fed1b8ccff8a9b5d1a027b4749d2`

GPU HF 모델은 여러 파일이므로 `MODEL_MANIFEST.json`의 SHA-256을 사용한다. 이
manifest는 모델 revision과 세 weight shard·index·tokenizer 해시를 고정한다. 임의
shard 하나나 디렉터리 경로 문자열의 해시는 사용하지 않는다.

## 3. 판단쌍 검증

```bash
venv/bin/python -m scripts.prepare_feedback_runtime_pairs \
  --gpu-run evaluation/feedback/intake/gpu-v02d-pi50.jsonl \
  --gpu-run-manifest evaluation/feedback/intake/gpu-v02d-pi50.jsonl.manifest.json \
  --pi-run evaluation/feedback/intake/pi5-q5-v02d-benchmark50.jsonl \
  --pi-benchmark-summary evaluation/feedback/intake/pi5-q5-v02d-benchmark50.summary.json \
  --gpu-model-sha256 86cf6cbe487216982ba0cc0adafa649925d1f2e61d86b2fc63cfe34f99f91013 \
  --gpu-adapter-sha256 2e758256afe68c3005b595f9f664b5f76734606b923dbb2c7bc858e81e9e55c6 \
  --pi-model-sha256 c393c664d0749b8b0e797895a284d7260bb1e813b7aeb318e04b08ae0c3f5f2f \
  --pi-adapter-sha256 e513c35c51b02f19ece2890337dde242e019fed1b8ccff8a9b5d1a027b4749d2 \
  --pi-quantization Q5_K_M \
  --output evaluation/feedback/runtime-pairs-v0.1.summary.json
```

성공 조건은 양쪽 50건의 입력 SHA 집합 일치, 전송·계약 100%, 원시 응답 재파싱
일치, GPU manifest 일치, Pi 벤치마크 증빙 일치다. 결과 summary에는 개수·일치율과
해시만 들어가며 문장·문맥·ID는 포함되지 않는다.

## 4. 이후 게이트

1. 실제 판단쌍 50건을 확보하면 GPU/Pi별 feedback 품질 격차를 평가할 입력 기반만
   준비된 것으로 본다.
2. 별도의 독립 라벨이 없으면 새 holdout을 만들거나 feedback-v0.3을 선택하지 않는다.
3. 독립 라벨이 확보되면 먼저 새 시험지를 봉인하고 해시를 커밋한다.
4. 그 뒤에만 v0.2 실패 6건과 보류 경계를 학습 데이터에 보강한다.
5. 새 후보가 모든 안전 기준을 통과하기 전에는 worker와 200건 shadow를 켜지 않는다.
