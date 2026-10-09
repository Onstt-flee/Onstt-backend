# 판단모델 staging 실행 가이드

## 현재 허용 범위

- 대상 모델은 `Qwen3-4B + judgment-qwen3-4b-failure-focus-v0.2-d`다.
- 판단 기능의 기본값은 `JUDGMENT_ENABLED=false`다.
- 이 절차는 로컬 staging·Swagger 확인 전용이다. 학습자 응답 경로와 운영 기본값을 활성화하지 않는다.
- 사람 품질 검수와 음성·발음 평가는 현재 보류한다. 따라서 이 절차로 문법 정확도나 발음 성능을 새로 주장하지 않는다.
- 원본 `stt_data.db`는 읽기와 해시 확인에만 사용한다. 판단 결과는 `/tmp`의 복제 DB에만 저장한다.

## 1. 고정 경로

```bash
export STT_API_DIR=/home/cap-minsung/stt_api
export JUDGMENT_BASE_MODEL=/home/cap-minsung/lora-adapter-bank/base-models/qwen3-4b-instruct-2507-hf
export JUDGMENT_LORA=/home/cap-minsung/lora-adapter-bank/adapters/judgment-qwen3-4b-failure-focus-v0.2-d
export JUDGMENT_VLLM=/home/cap-minsung/lora-adapter-bank/envs/qwen3-peft/bin/vllm
```

세 경로가 실제 파일·디렉터리인지 먼저 확인한다.

```bash
test -d "$JUDGMENT_BASE_MODEL"
test -d "$JUDGMENT_LORA"
test -x "$JUDGMENT_VLLM"
```

## 2. 모델 서버 실행

vLLM 0.28.0 환경의 FlashInfer/CUDA-CUB JIT 충돌을 피하기 위해 sampler를 비활성화한다.

```bash
VLLM_USE_FLASHINFER_SAMPLER=0 "$JUDGMENT_VLLM" serve "$JUDGMENT_BASE_MODEL" \
  --host 127.0.0.1 \
  --port 1234 \
  --dtype bfloat16 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.80 \
  --generation-config vllm \
  --enable-lora \
  --lora-modules "judgment-v02d=$JUDGMENT_LORA"
```

다른 터미널에서 상태와 alias를 확인한다.

```bash
curl --fail http://127.0.0.1:1234/health
curl --fail http://127.0.0.1:1234/v1/models
```

`/v1/models` 응답에 `judgment-v02d`가 없으면 API를 시작하지 않는다.

## 3. 임시 DB와 API 실행

임시 작업 디렉터리를 만들고 원본 DB의 해시를 기록한 다음 복제한다.

```bash
export JUDGMENT_STAGING_DIR="$(mktemp -d /tmp/stt-judgment-staging.XXXXXX)"
sha256sum "$STT_API_DIR/stt_data.db"
cp --preserve=mode,timestamps "$STT_API_DIR/stt_data.db" "$JUDGMENT_STAGING_DIR/stt_data.db"
```

`database.py`가 상대 경로 SQLite를 사용하므로 반드시 임시 디렉터리에서 API를 실행한다.

```bash
cd "$JUDGMENT_STAGING_DIR"
export PYTHONPATH="$STT_API_DIR"
export JUDGMENT_ENABLED=true
export JUDGMENT_ENDPOINT=http://127.0.0.1:1234/v1/chat/completions
export JUDGMENT_MODEL=judgment-v02d
export JUDGMENT_ADAPTER=judgment-qwen3-4b-failure-focus-v0.2-d
export JUDGMENT_TIMEOUT_SECONDS=120
export JUDGMENT_MAX_CONCURRENCY=4
export JUDGMENT_QUEUE_TIMEOUT_SECONDS=0
export JUDGMENT_READINESS_TIMEOUT_SECONDS=2
export JUDGMENT_SHUTDOWN_GRACE_SECONDS=30
"$STT_API_DIR/venv/bin/uvicorn" main:app --host 127.0.0.1 --port 8001
```

## 4. 사전점검과 Swagger 확인

API와 모델 서버가 실행 중인 상태에서 별도 터미널로 점검한다.

```bash
cd "$STT_API_DIR"
export JUDGMENT_ENABLED=true
export JUDGMENT_ENDPOINT=http://127.0.0.1:1234/v1/chat/completions
export JUDGMENT_MODEL=judgment-v02d
export JUDGMENT_ADAPTER=judgment-qwen3-4b-failure-focus-v0.2-d
export JUDGMENT_TIMEOUT_SECONDS=120
venv/bin/python -B -m scripts.check_judgment_staging \
  --database "$JUDGMENT_STAGING_DIR/stt_data.db"
```

`passed: true`, `mutations_performed: false`, 모델 alias와 상태·두 판단 OpenAPI 경로가 모두 확인되어야 한다.

Swagger는 `http://127.0.0.1:8001/docs`에서 연다.

- `POST /utterances/{utterance_id}/judgment`: 임시 DB의 기존 발화 한 건으로 판단한다.
- `GET /utterances/{utterance_id}/judgments`: 방금 저장된 결과를 확인한다.
- `GET /health/judgment`: 원문 없이 요청·성공·실패·재시도·결정 분포와 p50/p95 지연시간을 확인한다.
- `GET /ready/judgment`: 기능 플래그·수락 상태·모델 health·고정 alias를 확인하며 준비되지 않으면 503을 반환한다.
- 동시 판단 상한은 기본 4이고 대기열은 기본 0초다. 포화 요청은 모델 호출 전 429와 `Retry-After: 1`로 차단한다.
- 없는 발화는 404, 빈 발화는 400이어야 한다.
- 모델 연결 실패나 출력 계약 위반은 503이어야 하며 `insufficient_evidence`로 위장하면 안 된다.
- 공개 응답에 `confidence`나 내부 재시도 정보가 노출되면 안 된다.

## 5. 원본 DB 무변경 확인

Swagger 확인 전후 원본 DB 해시가 같아야 한다. 임시 DB에는 테스트한 판단 결과만 증가할 수 있다.

```bash
sha256sum "$STT_API_DIR/stt_data.db"
sqlite3 "$JUDGMENT_STAGING_DIR/stt_data.db" 'SELECT COUNT(*) FROM judgment_results;'
```

해시가 다르면 즉시 기능을 중단하고 원인을 조사한다. 원본 DB의 변경을 되돌리는 명령은 자동 실행하지 않는다.

## 6. 중단과 rollback

1. API 프로세스를 `Ctrl-C`로 종료한다.
2. 모델 서버를 `Ctrl-C`로 종료한다.
3. 셸에서 `export JUDGMENT_ENABLED=false`로 되돌린다.
4. 8001과 1234 포트에 관련 프로세스가 남지 않았는지 확인한다.
5. 임시 디렉터리는 로그·결과 확인이 끝날 때까지 보존한다. 삭제가 필요하면 출력된 정확한 `/tmp/stt-judgment-staging.*` 경로를 다시 확인한 뒤 별도로 처리한다.

기능 플래그를 켜지 않은 일반 API는 계속 판단 요청에 503을 반환한다. staging 통과만으로 운영 활성화나 학습자 노출을 승인하지 않는다.

## 동시성·장애 probe

모델과 DB를 호출하지 않는 상태 집계 동시성·장애 분기 검사는 다음과 같다.

```bash
venv/bin/python -B -m scripts.run_judgment_resilience_probe
```

이 결과는 모니터 thread safety 검증이며 실제 FastAPI HTTP 또는 vLLM 처리량으로 해석하지 않는다. 자세한 결과는 `training/judgment/STAGING_RESILIENCE_RESULT.md`를 따른다.

## 제한적 HTTP 실부하

합성 입력을 넣은 격리 DB와 live API에서만 다음 실행기를 사용한다. 원본 DB나 실제 사용자 발화 ID를 전달하지 않는다.

```bash
venv/bin/python -B -m scripts.run_judgment_staging_load \
  --utterance-id 1 --utterance-id 2 --utterance-id 3 \
  --phase 1:6 --phase 2:8 --phase 4:12 \
  --timeout 120
```

실행기는 요청·응답 본문을 출력하지 않고 HTTP 상태, 계약 유효성, p50/p95와 처리량만 집계한다. `--generation-config vllm` 없이 모델 서버를 실행하면 모델 저장소의 숨은 샘플링 기본값이 적용될 수 있으므로 부하 결과를 채택하지 않는다. 2026-10-06 실측 결과와 한계는 `training/judgment/STAGING_HTTP_LOAD_RESULT.md`를 따른다.



## 커밋 전 감사

학습 결과까지 한 번에 커밋하기 직전에 저장소 루트에서 다음을 실행한다.

```bash
venv/bin/python -B -m scripts.audit_judgment_checkpoint
```

`passed: true`여야 하며 원시 실행, DB, 모델 가중치, 오디오, `.env`, 가상환경과 10MiB 초과 변경 파일이 커밋 후보에 포함되면 실패한다. 이 검사는 파일 내용을 결과로 내보내지 않고 경로·크기·보호 해시와 Git 제외 상태만 확인한다.

## 판정 체크리스트

- [ ] 모델 alias가 정확히 `judgment-v02d`다.
- [ ] API는 `/tmp` 복제 DB에서 실행 중이다.
- [ ] 사전점검 결과가 `passed: true`다.
- [ ] Swagger에 상태 조회와 POST/GET 판단 경로가 보인다.
- [ ] 상태 집계에 원문·발화 ID·문맥·원시 오류가 포함되지 않는다.
- [ ] 성공 응답의 계약과 backend diff가 유효하다.
- [ ] 실패는 503으로 닫히고 임시 DB에도 저장되지 않는다.
- [ ] 원본 DB 전후 SHA-256이 동일하다.
- [ ] 종료 후 8001·1234 프로세스가 남지 않는다.
- [ ] `JUDGMENT_ENABLED=false`가 운영 기본값으로 유지된다.

## 단기 soak와 readiness 복구 확인

격리 DB에서만 동시성 2를 약 1분 유지한다.

```bash
venv/bin/python -B -m scripts.run_judgment_staging_load \
  --utterance-id 1 --utterance-id 2 --utterance-id 3 \
  --phase 2:150 --timeout 120
```

그다음 vLLM만 중단하면 `/ready/judgment`가 `model_unavailable`과 HTTP 503을 반환해야 한다. 같은 alias와 고정 옵션으로 vLLM을 재기동한 뒤 API를 재시작하지 않아도 readiness가 HTTP 200으로 돌아와야 하며, 합성 판단 1건을 추가로 성공시켜 실제 복구를 확인한다. 결과는 `training/judgment/STAGING_SOAK_RECOVERY_RESULT.md`를 따른다.

## systemd 기반 staging 프로세스 관리

저장소의 [`deployment/judgment-staging`](../deployment/judgment-staging) 템플릿은 현재 GPU 서버의 절대 경로에 맞춘 **제한적 staging 전용** 설정이다. 템플릿을 추가한 것만으로 서비스가 설치·시작되거나 기능이 승인되지 않는다. 저장소의 환경 예시는 의도적으로 `JUDGMENT_ENABLED=false`다.

### 설치 전 준비

먼저 템플릿과 현재 서버 경로를 검증한다.

```bash
cd /home/cap-minsung/stt_api
systemd-analyze verify \
  deployment/judgment-staging/judgment-vllm.service \
  deployment/judgment-staging/stt-api-judgment-staging.service

test -x /home/cap-minsung/lora-adapter-bank/envs/qwen3-peft/bin/vllm
test -d /home/cap-minsung/lora-adapter-bank/base-models/qwen3-4b-instruct-2507-hf
test -d /home/cap-minsung/lora-adapter-bank/adapters/judgment-qwen3-4b-failure-focus-v0.2-d
```

설치에는 관리자 권한이 필요하다. 다음 명령은 실제 제한적 staging을 시작하기로 결정했을 때만 실행한다.

```bash
sudo install -d -m 0750 -o root -g cap-minsung /etc/stt-api
sudo install -d -m 0750 -o cap-minsung -g cap-minsung /var/lib/stt-api-judgment-staging
sudo install -m 0640 -o root -g cap-minsung \
  deployment/judgment-staging/judgment-staging.env.example \
  /etc/stt-api/judgment-staging.env
sudo install -m 0644 deployment/judgment-staging/judgment-vllm.service \
  /etc/systemd/system/judgment-vllm.service
sudo install -m 0644 deployment/judgment-staging/stt-api-judgment-staging.service \
  /etc/systemd/system/stt-api-judgment-staging.service
```

원본 DB를 직접 열지 않도록 해시를 기록하고 격리본을 만든다. 복사된 DB는 사용자 데이터이므로 Git에 넣거나 외부에 노출하지 않는다.

```bash
sha256sum /home/cap-minsung/stt_api/stt_data.db
sudo install -m 0640 -o cap-minsung -g cap-minsung \
  /home/cap-minsung/stt_api/stt_data.db \
  /var/lib/stt-api-judgment-staging/stt_data.db
```

마지막으로 `/etc/stt-api/judgment-staging.env`의 `JUDGMENT_ENABLED`만 `true`로 명시 변경한다. 이 파일을 변경하지 않으면 API의 `ExecStartPre`가 의도대로 실패한다. 서비스는 자동 부팅 등록하지 않고 수동 시작한다.

```bash
sudo systemctl daemon-reload
sudo systemctl start judgment-vllm.service
sudo systemctl start stt-api-judgment-staging.service
```

### 실행 확인

```bash
systemctl --no-pager --full status judgment-vllm.service
systemctl --no-pager --full status stt-api-judgment-staging.service
curl --fail http://127.0.0.1:8001/health
curl --fail http://127.0.0.1:8001/ready/judgment
```

API는 `--workers 1`로 고정된다. 현재 세마포어와 집계가 프로세스 로컬이므로 worker 수를 늘리면 GPU 전체 동시 실행 상한을 보장할 수 없다. 더 많은 API 프로세스나 replica가 필요하면 먼저 외부 큐 또는 분산 세마포어를 구현한다.

모델 서비스는 API의 약한 의존성(`Wants`)이다. 모델이 중단돼도 API는 살아서 readiness 503을 반환하고, 동일 alias로 모델이 복구되면 API 재시작 없이 readiness가 회복된다. 두 HTTP 포트는 loopback에만 bind되므로 원격 Swagger 확인은 SSH tunnel 또는 기존 인증 프록시를 사용하며 8001/1234를 직접 외부에 개방하지 않는다.

### 중단과 제거

```bash
sudo systemctl stop stt-api-judgment-staging.service
sudo systemctl stop judgment-vllm.service
```

중단 후 포트와 GPU 프로세스를 확인한다. DB와 환경 파일 삭제는 로그·결과 보존 여부를 확인한 뒤 별도로 결정하며 자동 rollback 명령에 포함하지 않는다. 서비스 파일을 제거할 때도 먼저 두 서비스가 중단됐는지 확인하고 `systemctl disable` 여부를 확인한다. 이 템플릿은 `enable`을 요구하지 않는다.

## sudo 없는 사용자 systemd 경로

현재 서버처럼 sudo 권한이 없으면 사용자 systemd를 사용한다. 먼저 user manager 상태를 확인한다.

```bash
systemctl --user is-system-running
loginctl show-user "$USER" -p Linger -p State
```

`running`이면 현재 로그인 세션의 staging에 사용할 수 있다. `Linger=no`이면 로그아웃 이후 상시 실행을 보장하지 않으므로 운영 서비스로 간주하지 않는다.

설치기는 기존 private 환경과 격리 DB를 덮어쓰지 않고, 서비스도 시작하거나 enable하지 않는다.

```bash
cd /home/cap-minsung/stt_api
./scripts/install_judgment_user_services.sh
```

생성 위치는 다음과 같다.

- unit: `~/.config/systemd/user/`
- private 환경: `~/.config/stt-api/judgment-staging.env`
- 격리 DB: `~/.local/state/stt-api-judgment-staging/stt_data.db`

private 환경의 `JUDGMENT_ENABLED=false`를 검토 후 staging 실행 시에만 `true`로 바꾸고 수동 시작한다. `[Install]` 섹션이 없으므로 `enable`하지 않는다.

```bash
systemctl --user start judgment-vllm.service
curl --fail http://127.0.0.1:1234/health
systemctl --user start stt-api-judgment-staging.service
./scripts/check_judgment_user_staging.sh
```

초기 모델 컴파일은 1분 이상 걸릴 수 있다. 모델 health와 `judgment-v02d` alias가 준비되기 전에 API 판단을 실행하지 않는다. 운영 셸에서 직접 사전점검 명령을 호출하면 private 환경을 읽지 않아 비활성으로 판정될 수 있으므로 사용자 경로에서는 반드시 wrapper를 사용한다.

중단은 API부터 수행한다.

```bash
systemctl --user stop stt-api-judgment-staging.service
systemctl --user stop judgment-vllm.service
```

그다음 private 환경을 다시 `false`로 바꾸고 서비스 상태, 8001/1234 listener와 GPU process를 확인한다. 합성 테스트로 변경된 격리 DB를 초기 snapshot으로 되돌릴 때는 정확한 두 경로와 해시를 먼저 확인하고 API가 완전히 중단된 상태에서만 교체한다. 2026-10-08 실측은 `training/judgment/STAGING_DEPLOYMENT_TEMPLATE_RESULT.md`를 따른다.

### 사용자 서비스 안전 관리 명령

직접 환경 파일을 편집하고 여러 `systemctl` 명령을 순서대로 실행하는 대신 다음 관리기를 우선 사용한다.

```bash
cd /home/cap-minsung/stt_api
venv/bin/python -B -m scripts.manage_judgment_user_staging status
venv/bin/python -B -m scripts.manage_judgment_user_staging start --timeout 180
venv/bin/python -B -m scripts.manage_judgment_user_staging stop
```

`start`는 inactive 상태에서만 허용된다. private 환경 권한·소유권·형식과 격리 DB 존재를 먼저 확인하고, 환경을 원자적으로 활성화한 뒤 모델→API 순서로 기동한다. 모델 alias와 전체 live 사전점검 중 하나라도 실패하면 두 서비스를 중단하고 환경을 false로 복원한다.

`stop`은 API→모델 순서로 중단한 뒤 기능 플래그를 false로 복원한다. DB snapshot은 자동으로 덮어쓰거나 삭제하지 않는다. 서비스 중단 뒤 DB를 초기화해야 한다면 대상 경로와 해시를 별도로 확인한다. 상태 출력에는 원문·발화 ID·교정문·원시 오류가 포함되지 않는다.

## 기존 `/analyze`의 shadow 실행

기본 `start`는 shadow를 켜지 않는다. 응답 비간섭 shadow를 명시적으로 검증할 때만 `--shadow`를 사용한다.

```bash
venv/bin/python -B -m scripts.manage_judgment_user_staging start \
  --shadow --timeout 180
```

이 옵션은 private 환경의 `JUDGMENT_ENABLED`와 `JUDGMENT_SHADOW_ENABLED`를 함께 true로 전환한다. 기본 admission은 `JUDGMENT_SHADOW_ADMISSION_RPS=1`, `JUDGMENT_SHADOW_ADMISSION_BURST=1`이고 큐 설정은 `JUDGMENT_SHADOW_QUEUE_MAX_SIZE=64`, `JUDGMENT_SHADOW_ITEM_TTL_SECONDS=30`을 사용한다. 모델·API·OpenAPI 전체 사전점검이 실패하면 두 서비스를 중단하고 두 플래그를 false로 복구한다. `stop`도 두 플래그를 모두 false로 만든다.

shadow가 활성화된 `/analyze` 호출에서는 다음을 확인한다.

- 기존 `AnalysisResponse`에 `decision`, `strategy`, `edits`, `reason_ko`가 추가되지 않는다.
- 기존 분석 결과는 `analyses`에 정상 저장된다.
- background 판단 결과는 `judgment_results`에 저장되지 않는다.
- `GET /health/judgment`의 `shadow` 하위 집계만 증가한다.
- shadow 실패가 기존 `/analyze` HTTP 상태나 응답을 변경하지 않는다.

`GET /health/judgment`는 shadow 집계 추가로 `judgment-monitor-v0.2` 계약을 사용한다. 합성 입력으로 검증하고 종료 후 격리 DB를 초기 snapshot으로 복원한다. 실측 결과는 `training/judgment/STAGING_ANALYZE_SHADOW_RESULT.md`를 따른다.

### shadow OFF/ON 제한 부하 확인

원본 DB나 실제 사용자 발화 ID를 사용하지 않는다. 동일 snapshot에 합성 룰 기반 발화를 넣고 OFF와 ON을 각각 새 서비스 프로세스에서 실행한다.

```bash
venv/bin/python -B -m scripts.run_analyze_shadow_load \
  --database "$JUDGMENT_STAGING_DB" \
  --utterance-id 1 --utterance-id 2 --utterance-id 3 \
  --phase 1:6 --phase 2:8 --phase 4:12 --timeout 120

venv/bin/python -B -m scripts.run_analyze_shadow_load \
  --database "$JUDGMENT_STAGING_DB" \
  --utterance-id 1 --utterance-id 2 --utterance-id 3 \
  --phase 1:6 --phase 2:8 --phase 4:12 --timeout 120 \
  --expect-shadow
```

두 결과의 `input_plan_sha256`이 같아야 하고 `/analyze` 계약 성공 수와 `analyses` 증가 수는 요청 수와 같아야 한다. `judgment_results` 증가는 0이어야 한다. 결과는 원문·응답 본문을 포함하지 않는다. 2026-10-08 큐 적용 전 실측에서는 기존 응답 26/26을 지켰지만 shadow 모델 호출 24/26이 `overloaded`로 폐기됐다. 이후 최대 64건·TTL 30초·단일 consumer 큐를 적용해 동일 입력 26/26 처리와 drop 0건을 확인했다. 최신 결과는 `training/judgment/STAGING_ANALYZE_SHADOW_QUEUE_RESULT.md`를 따른다. 입력률별 후속 측정과 재현 명령은 `training/judgment/STAGING_ANALYZE_SHADOW_RATE_RESULT.md`를 따른다.

### shadow 입력률별 rate probe

```bash
venv/bin/python -B -m scripts.run_analyze_shadow_rate_probe \
  --database "$JUDGMENT_STAGING_DB" \
  --utterance-id 1 --utterance-id 2 --utterance-id 3 \
  --stable-phase 0.5:4 --stable-phase 1:6 \
  --sample-phase 2:10 --sample-phase 10:80 \
  --phase-cooldown 1.1 --timeout 180
```

`stable-phase`는 전 건 enqueue·모델 성공·sample/drop 0을 요구한다. `sample-phase`는 `/analyze` 응답 전 건 성공과 판단 DB 무저장을 유지하면서 초과 입력이 `sampled_out`으로만 분리되고 failure/drop·`queue_full`·`expired`가 0인지 확인한다. admission 이전의 큐 경계 재현이 필요할 때만 `drop-phase`를 사용한다. 모니터의 지연시간 요약은 구간별이 아니라 API 프로세스 시작 이후 누적값이므로 `latency_scope=process_cumulative_since_api_start`로 해석한다. 실제 사용자 발화 ID와 원본 DB를 사용하지 않는다. 최신 실측은 `training/judgment/STAGING_ANALYZE_SHADOW_ADMISSION_RESULT.md`를 따른다.

