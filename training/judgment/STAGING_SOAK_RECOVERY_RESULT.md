# 판단모델 staging 단기 soak·readiness 복구 결과

- 실행일: 2026-10-06
- 대상: Qwen3-4B BF16 + `judgment-qwen3-4b-failure-focus-v0.2-d`
- API: FastAPI 1 worker, `d_only`, `judgment-v0.2`
- 장비: NVIDIA RTX A6000 48GB 단일 GPU
- 상태: **단기 지속 부하와 모델 장애·복구 전환 통과, 운영 기본 활성화는 미승인**

## 실행 조건

- vLLM 0.28.0, BF16, context 4,096
- `--generation-config vllm`, `VLLM_USE_FLASHINFER_SAMPLER=0`
- 격리 SQLite와 합성 일본어 입력 6개
- `JUDGMENT_MAX_CONCURRENCY=2`
- `JUDGMENT_QUEUE_TIMEOUT_SECONDS=0`
- 1건 워밍업 후 동시성 2로 150건 연속 실행
- 요청·응답 본문과 사용자 식별자는 결과에 기록하지 않음

## 단기 soak 결과

| 항목 | 결과 |
| --- | ---: |
| 측정 요청 | 150 |
| HTTP 200·계약 성공 | 150 |
| 실패·timeout·재시도 | 0 |
| 경과 시간 | 57.519초 |
| 처리량 | 2.608 req/s |
| HTTP p50 | 755.203ms |
| HTTP p95 | 850.022ms |
| HTTP 최대 | 895.077ms |
| 계획 SHA-256 | `9afa92c02b504aef87f962b46cb18d21f62ebe8ab33dfd2d73d8ea4b991fea04` |

워밍업을 포함한 API 프로세스 집계는 요청·모델 호출·성공이 각각 151건이고 실패·거부·재시도는 0건이다. 내부 모델 지연시간은 p50 748.007ms, p95 842.920ms, 최대 856.912ms였다. 임시 DB에는 당시 성공 151건만 저장됐다.

## readiness 장애·복구 전환

같은 FastAPI 프로세스를 유지한 채 vLLM만 중단하고 재기동했다.

1. 정상: HTTP 200, `ready=true`, `reason=ready`, model health·alias true
2. vLLM 중단: HTTP 503, `ready=false`, `reason=model_unavailable`
3. 동일 고정 설정 vLLM 재기동: API 재시작 없이 HTTP 200과 `ready=true`로 복구
4. 복구 후 실제 판단 1건: HTTP 200·계약 성공, 790.191ms

장애 응답에는 endpoint, 원시 오류, 원문, 발화 ID나 문맥이 포함되지 않았다. 최종 임시 DB에는 워밍업 1건, soak 150건, 복구 확인 1건을 합쳐 152건만 저장됐다.

## 격리와 종료

- 원본 DB SHA-256: `ef3b42b92516c5332f2ed1dcd63ffe1a9c2ff8a53650c24a32205a0161ff09c9`
- 원본 DB `judgment_results`: 0건 유지
- `holdout_v0.4` SHA-256: `904ca090ccd0e209f95fa68a6a3e9fd762a0009c802f7eae7670838f9558221e`
- `holdout_v0.4` 모델 추론: 0회 유지
- FastAPI·vLLM 종료, GPU memory 1MiB 유휴 확인
- 합성 입력과 임시 판단 결과가 든 `/tmp` 디렉터리 삭제

## 한계와 판정

이번 결과는 약 1분, 동시성 2, 단일 API worker와 로컬 loopback 조건의 지속 부하 안정성만 보여준다. 장시간 memory leak, 다중 worker·replica, reverse proxy, 인증, 네트워크 지연, 운영 DB contention이나 프로세스 강제 종료 복구를 증명하지 않는다. 합성 입력이므로 일본어 문법 정확도나 과교정률 근거도 아니다.

기능 플래그 기본값 `JUDGMENT_ENABLED=false`, 학습자 노출 미승인, 사람·음성 검수 보류를 유지한다. 다음 우선순위는 배포 설정 템플릿과 다중 worker 사용 금지/외부 전역 제한 필요성을 명시한 뒤 staging 프로세스 관리 절차를 고정하는 것이다.
