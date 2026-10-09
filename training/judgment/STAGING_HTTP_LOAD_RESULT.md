# 판단모델 staging FastAPI–vLLM 실부하 결과

- 실행일: 2026-10-06
- 대상: Qwen3-4B BF16 + `judgment-qwen3-4b-failure-focus-v0.2-d`
- API 전략: `d_only`, 계약 `judgment-v0.2`
- 장비: NVIDIA RTX A6000 48GB 단일 GPU
- 범위: 격리 SQLite·합성 일본어 입력을 사용한 제한적 HTTP 동시 부하
- 상태: **실행 안전성 기준 통과, 운영 기본 활성화·언어 품질 승격은 미승인**

## 실행 조건

- vLLM 0.28.0, BF16, context 4,096, GPU memory utilization 0.80
- `VLLM_USE_FLASHINFER_SAMPLER=0`
- 숨은 모델 기본 샘플링을 막기 위해 `--generation-config vllm` 적용
- 요청 생성값: temperature 0, top-p 1, max tokens 512
- FastAPI 1 worker, 로컬 loopback HTTP
- 원본 DB가 아닌 `/tmp`의 새 SQLite 사용
- 정상·조사 오류·활용 오류·필러·미완성 경계를 담은 합성 입력 6개 사용
- 워밍업 2건 후 측정 26건
- 측정 계획 SHA-256: `669058265028687fa8fb4dbc1e52321bdcd6c7534ea1910e9446afc80e9b6587`

실행기는 요청·응답 본문을 결과에 기록하지 않는다. 원시 실행 JSON도 Git에 추가하지 않았다.

## 측정 결과

| 동시성 | 요청 | HTTP 200·계약 성공 | 실패 | p50 | p95 | 최대 | 처리량 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 6 | 6 | 0 | 759.517ms | 849.186ms | 849.186ms | 1.303 req/s |
| 2 | 8 | 8 | 0 | 752.227ms | 840.562ms | 840.562ms | 2.582 req/s |
| 4 | 12 | 12 | 0 | 783.961ms | 867.775ms | 867.775ms | 4.786 req/s |

측정 구간 합계는 26/26 성공이다. 워밍업 2건까지 포함한 API 프로세스 집계는 다음과 같다.

- 요청·모델 호출·성공: 각각 28건
- 실패·사전 거부·재시도: 각각 0건
- 내부 모델 지연시간: p50 758.097ms, p95 845.624ms, 최대 859.388ms
- 결정 분포: acceptable 14, needs_correction 10, insufficient_evidence 4
- 임시 DB 판단 저장: 28건
- 상태: `ready`
- 상태 응답의 `contains_request_content`: `false`

HTTP p95는 동시성 4에서도 1초 미만이었고, 요청 수를 늘릴수록 처리량이 거의 선형으로 증가했다. 이 제한된 범위에서 timeout, 계약 실패, 저장 실패나 재시도는 관측되지 않았다.

## 데이터·격리 검증

- 원본 DB SHA-256: `ef3b42b92516c5332f2ed1dcd63ffe1a9c2ff8a53650c24a32205a0161ff09c9`
- 원본 DB `judgment_results`: 0건 유지
- 임시 DB: 합성 발화 6건, 판단 결과 28건
- 원문·응답 본문·사용자 식별자·원시 오류를 추적 결과에 포함하지 않음
- 종료 후 8001·1234 서버를 모두 중단
- `holdout_v0.4`에는 모델 추론을 수행하지 않음

## 판정과 한계

이번 시험은 실제 FastAPI → judgment service → vLLM LoRA → 계약 파서 → SQLite 저장 경로가 동시성 4까지 안정적으로 작동한다는 근거다. 앞선 비중복 100건 shadow의 p95 1,108.711ms보다 이번 합성 입력 측정 p95가 낮았지만 입력 길이와 분포가 다르므로 직접적인 성능 개선으로 해석하지 않는다.

다음 사항은 증명하지 않는다.

- 일본어 문법 판단 정확도·과교정률·발음 또는 STT 품질
- 장시간 soak 안정성, 최대 처리량, GPU 포화점
- 여러 Uvicorn worker 사이의 모니터 집계 일관성
- 원격 네트워크·인증·reverse proxy·운영 DB 조건의 지연시간

따라서 `JUDGMENT_ENABLED=false` 기본값, 학습자 노출 미승인과 사람·음성 검수 보류를 유지한다. 다음 운영 엔지니어링 우선순위는 요청 제한·backpressure·readiness 및 graceful shutdown을 설계하는 것이다.
