# `/analyze` 제한 용량 shadow 큐 실기동 결과

> 후속 상태: admission 전 rate probe에서는 10 req/s에서 queue full·TTL 만료가 발생했다. 이후 1 req/s token bucket 적용 결과 failure/drop 0을 확인했다. 최신 결과는 [shadow admission 결과](STAGING_ANALYZE_SHADOW_ADMISSION_RESULT.md)를 따른다.

- 상태: **응답 격리 26/26·shadow 처리 26/26·drop 0건 통과, 기본 비활성 유지**
- 일시: 2026-10-08 KST
- 모델: Qwen3-4B + `judgment-qwen3-4b-failure-focus-v0.2-d`
- 환경: sudo 없는 사용자 systemd, FastAPI 1 worker, 판단 동시 실행 상한 2
- 큐: 프로세스 로컬 단일 consumer, 최대 64건, 항목 TTL 30초

## 변경 내용

기존 FastAPI background task가 각 요청마다 즉시 모델 용량을 경쟁하던 구조를, 응답 이후 enqueue만 수행하는 제한 큐로 교체했다.

- `JUDGMENT_SHADOW_QUEUE_MAX_SIZE=64`
- `JUDGMENT_SHADOW_ITEM_TTL_SECONDS=30`
- 실제 모델 호출 consumer는 프로세스당 1개다.
- 큐 포화, TTL 만료, worker 미가동, 종료 유예 초과는 원문 없이 범주와 건수만 집계한다.
- worker는 직접 판단 API와 기존 프로세스 로컬 모델 용량 제한을 공유한다. 용량이 찼으면 TTL 안에서 짧게 대기하며 직접 판단 요청과 경쟁해 무한 적재하지 않는다.
- API 종료 시 신규 enqueue를 막고 설정된 shutdown grace 안에서 큐를 drain한 뒤 잔여 항목을 `shutdown_drop`으로 폐기한다.
- `judgment_results`에는 shadow 결과를 저장하지 않는다.

`GET /health/judgment`의 shadow 계약은 `judgment-shadow-monitor-v0.2`로 올렸다. 큐 설정 유효성, worker 상태, 현재 깊이, enqueue·drop·만료·종료 폐기, 모델·큐 대기 지연시간을 내용 없이 제공한다.

## 동일 입력 OFF/ON 결과

규칙 기반 합성 일본어 인사 3건을 동일 격리 DB snapshot에 넣었다. shadow OFF와 ON을 각각 동시성 1·6건, 2·8건, 4·12건으로 실행했다. 양쪽 입력 계획 SHA-256은 `f13cd2bf467aea092597d8684240f7073c5897d07abb7a7e47b6db5887da5f85`로 같다.

| 동시성 | 요청 | OFF p95 | ON p95 | p95 변화 | OFF 처리량 | ON 처리량 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 6 | 31.832ms | 37.323ms | +17.25% | 107.639 req/s | 97.220 req/s |
| 2 | 8 | 18.433ms | 11.857ms | -35.68% | 166.412 req/s | 220.210 req/s |
| 4 | 12 | 74.969ms | 58.331ms | -22.19% | 155.769 req/s | 185.705 req/s |

두 모드 모두 `/analyze` HTTP 200·기존 응답 계약 26/26, `analyses` 26행 증가, `judgment_results` 증가 0행을 기록했다. 표본이 작고 각 모드가 별도 프로세스에서 실행됐으므로 p95 변화율은 절대 성능 승인 기준으로 사용하지 않는다.

shadow ON의 처리 결과:

- 예약·enqueue·모델 호출·성공: 각각 26건
- 실패·drop·TTL 만료·종료 폐기·재시도: 모두 0건
- 판단 분포: `acceptable` 26건
- 모델 지연시간: p50 604.218ms, p95 653.229ms, 최대 770.798ms
- 큐 대기시간: p50 7509.501ms, p95 14877.508ms, 최대 15526.212ms
- 종료 시 queue depth: 0
- 응답·집계에 요청 본문, 발화 ID, 교정문과 원시 오류: 없음

큐 적용 전 같은 26건에서는 실제 모델 호출 2건, `overloaded` 폐기 24건이었다. 제한 큐 적용 후 폐기 0건과 전 건 처리를 확인했다.

## 판정과 한계

이번 단계의 목적이던 **기존 응답 비간섭과 대표성 있는 소규모 burst 수집**은 통과했다. 하지만 26건 burst의 shadow 결과는 p95 기준 약 14.88초 늦게 생성됐다. 이는 `/analyze` 응답 지연이 아니라 비동기 결과의 신선도 지연이다.

따라서 기능 플래그 기본값과 학습자 노출 상태는 변경하지 않는다. 다음 단계는 새 모델 학습이나 holdout 실행이 아니라, 합성 입력의 도착률을 제어한 rate probe로 다음을 확인하는 것이다.

1. 입력률이 단일 worker 처리율보다 낮을 때 queue depth가 안정적으로 0으로 복귀하는지
2. 처리율을 넘을 때 TTL과 최대 길이가 예상대로 drop을 제한하는지
3. `/analyze` 응답 계약과 `judgment_results=0`이 계속 유지되는지

실제 사용자 트래픽 분포가 없으므로 이번 26건 결과만으로 큐 크기 64와 TTL 30초를 운영 최적값이라고 주장하지 않는다.

## 검증과 복원

- 전체 회귀 테스트: 248/248 통과
- 서비스: 모델/API 모두 inactive
- 기능 플래그: `JUDGMENT_ENABLED=false`, `JUDGMENT_SHADOW_ENABLED=false`
- 원본·격리 DB SHA-256: `ef3b42b92516c5332f2ed1dcd63ffe1a9c2ff8a53650c24a32205a0161ff09c9`
- 격리 DB `judgment_results`: 0
- `holdout_v0.4`: 모델 추론 0회 유지
- 커밋·푸시: 수행하지 않음
