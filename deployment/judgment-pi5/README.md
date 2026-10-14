# Raspberry Pi 5 16GB 판단모델 병행 배포

> 2026-10-13 현재: Q4는 dev72 구조 계약 71/72로 실패했다. 별도 Q5_K_M 후보는 구조·GPU 판단 일치 72/72로 양자화 회귀 게이트를 통과했지만 Pi 실측 전이므로 배포 기본값은 Q4로 유지한다. 실제 해시와 비교는 [Q4/Q5 변환·dev72 결과](GPU_CONVERSION_AND_DEV72_RESULT.md)를 따른다.

## 안전 경계

- GPU의 HF BF16 베이스와 PEFT v0.2-D 어댑터는 수정하거나 덮어쓰지 않는다.
- Pi 기본값은 `Q4_K_M GGUF + F16 GGUF LoRA`이며, Q5는 명시적 후보 환경과 preflight 옵션으로만 시험한다.
- GPU API가 최종 데이터 원본이며, Pi 전환은 자동 failover가 아니라 수동 프로필 선택이다.
- 이 구성은 기존의 “제한적 staging/shadow 후보” 상태를 운영 승인으로 바꾸지 않는다.
- 모델·어댑터·원시 실행 JSONL·Pi SQLite는 Git에 올리지 않는다.

## 1. GPU 서버에서 GGUF 만들기

별도 llama.cpp checkout과 변환용 Python 환경을 준비한다. 변환 시점의 llama.cpp 전체 commit은 manifest에 고정된다.

```bash
git clone https://github.com/ggml-org/llama.cpp.git /home/cap-minsung/lora-adapter-bank/tools/llama.cpp
cd /home/cap-minsung/lora-adapter-bank/tools/llama.cpp
python3 -m pip install -r requirements.txt
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j 8

cd /home/cap-minsung/stt_api
export LLAMA_CPP_DIR=/home/cap-minsung/lora-adapter-bank/tools/llama.cpp
export BASE_MODEL_DIR=/home/cap-minsung/lora-adapter-bank/base-models/qwen3-4b-instruct-2507-hf
export LORA_DIR=/home/cap-minsung/lora-adapter-bank/adapters/judgment-qwen3-4b-failure-focus-v0.2-d
export OUTPUT_DIR=/home/cap-minsung/lora-adapter-bank/pi5/qwen3-4b-v02d
export CONVERSION_PYTHON=/home/cap-minsung/lora-adapter-bank/envs/qwen3-peft/bin/python
deployment/judgment-pi5/prepare-gguf.sh
```

성공 조건은 Q4 모델, F16 LoRA, `pi5-model-manifest.json` 세 파일이 생성되고 manifest 해시가 실제 파일과 일치하는 것이다. 변환 실패 시 다른 모델로 대체하거나 원본에 병합하지 않는다.

## 2. Pi OS Bookworm 준비

Pi 5 16GB, 64비트 Bookworm, NVMe, 공식 전원과 능동 냉각을 전제로 한다.

```bash
sudo apt update
sudo apt install -y git cmake build-essential libcurl4-openssl-dev curl jq rsync
git clone https://github.com/ggml-org/llama.cpp.git "$HOME/llama.cpp"
cd "$HOME/llama.cpp"
git checkout <MANIFEST_LLAMA_CPP_COMMIT>
cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=OFF
cmake --build build --config Release -j 4
install -Dm755 build/bin/llama-server "$HOME/.local/bin/llama-server"

curl -LsSf https://astral.sh/uv/install.sh | sh
cd "$HOME/stt_api"
uv python install 3.12
uv venv --python 3.12 venv
uv pip install --python venv/bin/python -r requirements.txt
```

GPU 산출물을 `/mnt/nvme/judgment-models/qwen3-4b-v02d/`에 복사한다. rsync 또는 scp 전송 후 반드시 manifest로 다시 검증한다.

Q5 후보는 GPU 서버에서 다음 세 파일만 Pi로 전송한다. `<PI_HOST>`는 실제 private/VPN 주소로 바꾼다. 모델과 원시 평가 결과는 Git을 거치지 않는다.

```bash
ssh <PI_HOST> 'mkdir -p /mnt/nvme/judgment-models/qwen3-4b-v02d-q5'
rsync -avP \
  /home/cap-minsung/lora-adapter-bank/pi5/qwen3-4b-v02d-q5/Qwen3-4B-Instruct-2507-Q5_K_M.gguf \
  /home/cap-minsung/lora-adapter-bank/pi5/qwen3-4b-v02d/judgment-v0.2-d-f16.gguf \
  deployment/judgment-pi5/model-manifest.q5-candidate.json \
  <PI_HOST>:/mnt/nvme/judgment-models/qwen3-4b-v02d-q5/
```

Pi에서 manifest 이름을 그대로 사용해 검사하며, 파일을 임의로 재명명하지 않는다.

## 3. 환경과 preflight

```bash
cd "$HOME/stt_api"
deployment/judgment-pi5/install-user-services.sh
editor "$HOME/.config/stt-api/judgment-pi5.env"
```

- `EDGE_NODE_ID`: `python3 -c 'import uuid; print(uuid.uuid4())'`로 한 번 생성하고 유지한다.
- `EDGE_SYNC_TOKEN`: `openssl rand -hex 32`로 만들고 Pi/GPU에 같은 값을 넣는다.
- model/adapter SHA-256은 manifest 값을 그대로 사용한다.
- sync URL은 공용 인터넷이 아닌 private network/VPN 주소만 사용한다.

```bash
source "$HOME/.config/stt-api/judgment-pi5.env"
venv/bin/python -B -m scripts.check_pi5_deployment \
  --manifest "$PI_MODEL_DIR/pi5-model-manifest.json" \
  --model-dir "$PI_MODEL_DIR" \
  --llama-server "$HOME/.local/bin/llama-server"
```

`ready: true` 전에는 서비스를 시작하지 않는다.

## 4. 수동 시작과 readiness

```bash
systemctl --user start judgment-pi5-llama.service
curl -fsS http://127.0.0.1:1234/v1/models | jq .

source "$HOME/.config/stt-api/judgment-pi5.env"
venv/bin/python -B -m scripts.check_pi5_deployment \
  --manifest "$PI_MODEL_DIR/pi5-model-manifest.json" \
  --model-dir "$PI_MODEL_DIR" \
  --llama-server "$HOME/.local/bin/llama-server" \
  --live-endpoint http://127.0.0.1:1234

systemctl --user start stt-api-pi5.service
curl -fsS http://127.0.0.1:8001/health | jq .
```

STT 클라이언트는 평소 `profiles/gpu.env`를 사용한다. GPU 장애를 확인한 운영자가 `profiles/pi-local.env`로 바꾼 뒤 STT 완료 후 판단을 순차 호출한다. 두 프로필을 동시에 실행하지 않는다.

## 5. 양자화 회귀와 50건 성능 게이트

```bash
mkdir -p "$HOME/pi5-evaluation"
deployment/judgment-pi5/run-dev72-regression.sh "$HOME/pi5-evaluation/dev72"
deployment/judgment-pi5/run-benchmark-50.sh "$HOME/pi5-evaluation/benchmark50"
```

dev72 게이트는 구조 99%, GPU 판단 일치 95%, 신규 과교정 최대 1건, 허용 교정 감소 최대 2건, 보류→교정 0건을 검사한다. 50건 게이트는 계약 50/50, p95 45초, peak RSS 10GiB 이하, throttling 0을 요구한다. 원시 JSONL은 문장을 포함하므로 Git에 넣지 않는다.

Q5 후보를 Pi에서 시험할 때는 `model-manifest.q5-candidate.json`과 Q5 모델 파일을 같은 NVMe 디렉터리에 둔다. 기본 preflight는 Q5를 거부하므로 후보 시험임을 다음처럼 명시해야 한다.

Q5 시험 환경은 `pi5-q5-candidate.env.example`을 복사해 사용한다. 이 파일은 실제 Q5/LoRA 해시와 `EDGE_QUANTIZATION=Q5_K_M`을 함께 고정해 outbox 출처가 Q4로 잘못 기록되는 것을 막는다.

```bash
source "$HOME/.config/stt-api/judgment-pi5.env"
venv/bin/python -B -m scripts.check_pi5_deployment \
  --manifest "$PI_MODEL_DIR/model-manifest.q5-candidate.json" \
  --model-dir "$PI_MODEL_DIR" \
  --llama-server "$HOME/.local/bin/llama-server" \
  --allow-candidate-q5
```

Q5가 Pi 50건 게이트를 통과하기 전에는 Q4 기본 환경 예제와 서비스 기본 모델 파일을 Q5로 변경하지 않는다.

50건 시험은 활성 환경을 현재 셸에 불러온 뒤 실행한다. 요약 JSON에는 Q4/Q5 구분, 모델·어댑터·원시 실행 SHA-256, p50/p95, peak RSS와 throttling 전후 값만 남고 문장 내용은 포함되지 않는다.

```bash
set -a
source "$HOME/.config/stt-api/judgment-pi5.env"
set +a
deployment/judgment-pi5/run-benchmark-50.sh "$HOME/pi5-evaluation/benchmark50"
```

## 6. GPU 동기화 활성화

GPU API 환경에 `gpu-sync.env.example`의 값을 반영하고 API를 재시작한다. 새 테이블은 기존 테이블을 변경하지 않고 `create_all`로 추가된다.

```bash
curl -i -X POST https://<PRIVATE_GPU_HOST>/edge/v1/sync
```

토큰 없는 요청이 `401`, 기능이 꺼져 있으면 `503`이어야 한다. private network/VPN과 호스트 방화벽에서 Pi 주소만 허용한다.

Pi에서 수동 1회 동기화:

```bash
systemctl --user start stt-api-pi5-sync.service
journalctl --user -u stt-api-pi5-sync.service -n 100 --no-pager
```

20건 단절·복구 시험에서 성공한 뒤에만 timer를 켠다.

```bash
systemctl --user enable --now stt-api-pi5-sync.timer
```

같은 batch를 세 번 보내도 GPU에는 세션·발화·판단이 각각 한 번만 생성돼야 한다. 같은 event UUID의 payload가 달라지면 `409`가 정상이다. 거부된 이벤트는 Pi outbox에 남는다.

## 7. 종료와 롤백

```bash
systemctl --user stop stt-api-pi5-sync.timer stt-api-pi5.service judgment-pi5-llama.service
```

STT 클라이언트를 `gpu.env`로 되돌린다. Pi DB와 모델은 삭제하지 않는다. GPU의 기존 vLLM unit, HF 모델, PEFT LoRA, `/analyze`와 `/judgment` 계약에는 롤백 변경이 없다.
