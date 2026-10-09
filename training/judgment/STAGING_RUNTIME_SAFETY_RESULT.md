# 판단모델 staging backpressure·readiness·종료 안전성 결과

- 실행일: 2026-10-06
- 대상: Qwen3-4B BF16 + v0.2-D LoRA, FastAPI 판단 전용 경로
- 상태: **제한적 staging 운영 안전 경계 통과, 운영 기본 활성화는 미승인**

## 구현 경계

- `JUDGMENT_MAX_CONCURRENCY`: 동시 판단 실행 상한, 기본 4
- `JUDGMENT_QUEUE_TIMEOUT_SECONDS`: 실행 슬롯 대기 시간, 기본 0초
- 포화 시 모델을 호출하거나 DB에 저장하지 않고 HTTP 429와 `Retry-After: 1` 반환
- 종료 시작 후 신규 판단 요청은 HTTP 503으로 차단
- 종료 grace 동안 진행 중 모델 호출과 DB 저장이 끝날 때까지 drain
- `GET /ready/judgment`는 기능 플래그, 런타임 설정, 수락 상태, 모델 health와 `judgment-v02d` alias를 모두 확인
- readiness 실패는 HTTP 503이며 원문·발화 ID·endpoint·원시 오류를 반환하지 않음
- overload, shutdown, runtime configuration 거부는 모델 실패와 분리된 익명 범주로 집계

## 실제 backpressure 검증

격리 SQLite에 합성 발화 4건을 넣고 `JUDGMENT_MAX_CONCURRENCY=2`, 대기 0초, FastAPI 1 worker로 실행했다. readiness는 HTTP 200, `ready=true`, 모델 health와 alias 모두 true를 반환했다. live 사전점검도 통과했다.

1건 워밍업 후 동시성 8로 16건을 동시에 요청한 결과:

- HTTP 200·계약 성공: 2건
- HTTP 429 즉시 거부: 14건
- timeout·HTTP 5xx·계약 실패: 0건
- 실행 경과: 1.155초
- 전체 응답 p50: 20.832ms
- 전체 응답 p95: 1,146.232ms
- 계획 SHA-256: `af0fc6b3dc4a393e6ce8abc11c97c65a4f8e4b4c8ec6cffb9fc3cf8b36018953`

상한을 넘은 14건은 모델 invocation과 DB 저장 전에 차단됐다. 이후 동시성 2 요청 2건은 모두 HTTP 200·계약 성공했고 p95 799.758ms였다. 워밍업과 두 검증을 합쳐 임시 DB에 성공 5건만 저장됐다.

## 종료·격리 검증

- 활성 슬롯을 테스트 thread로 고정하고 종료 상태로 전환했을 때 신규 예약이 거부되는 것을 확인했다.
- 활성 요청이 남아 있으면 `wait_for_idle(0)`이 false이고, 요청 해제 후 true가 되는 것을 확인했다.
- 실제 API와 vLLM은 검증 후 정상 종료했다.
- 원본 DB SHA-256 `ef3b42b92516c5332f2ed1dcd63ffe1a9c2ff8a53650c24a32205a0161ff09c9`와 `judgment_results=0`을 유지했다.
- `holdout_v0.4` SHA-256 `904ca090ccd0e209f95fa68a6a3e9fd762a0009c802f7eae7670838f9558221e`, 모델 추론 0회를 유지했다.
- 임시 DB와 합성 입력은 검증 후 삭제한다.

## 한계와 판정

이 결과는 단일 FastAPI worker 안에서 동시 모델 호출을 제한하고 과부하를 fail-fast로 차단하는 근거다. 다중 worker·다중 replica에서는 제한이 프로세스별로 적용되므로 전체 GPU 상한을 보장하려면 외부 큐 또는 분산 세마포어가 필요하다. 또한 reverse proxy, 인증, 장시간 soak와 강제 종료 시 복구는 아직 검증하지 않았다.

기능 플래그 기본값 `JUDGMENT_ENABLED=false`, 학습자 노출 미승인, 사람·음성 검수 보류를 유지한다. 다음 운영 단계는 환경 설정 문서화 후 짧은 soak와 장애 시 readiness 전환을 검증하는 것이다.
