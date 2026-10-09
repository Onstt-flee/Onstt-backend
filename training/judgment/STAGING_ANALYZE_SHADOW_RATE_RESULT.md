# `/analyze` shadow 입력률별 rate probe 결과

> 후속 상태: 1 req/s·burst 1 admission 적용 후 총 100건에서 기존 응답 100/100, shadow 성공 23건, `sampled_out` 77건, failure/drop·queue full·expired 0건을 확인했다. 최신 결과는 [shadow admission 결과](STAGING_ANALYZE_SHADOW_ADMISSION_RESULT.md)를 따른다.

- 상태: **저율 구간 drop 0, 고율 구간 bounded drop, 기존 응답 전 건 보호**
- 일시: 2026-10-08 KST
- 큐 설정: 단일 consumer, 최대 64건, TTL 30초
- 모델: Qwen3-4B + `judgment-qwen3-4b-failure-focus-v0.2-d`
- 입력 계획 SHA-256: `3a9b0e87e3e0e600504b11c17007d372ca0efaeecb7a33e2ac7a9e3b3f041104`

## 측정 방식

규칙 기반 합성 일본어 인사 3건만 사용하고 `/analyze` 요청 도착률을 0.5, 1, 2, 10 req/s로 고정했다. 각 구간이 끝날 때 shadow 큐가 terminal 상태와 depth 0에 도달할 때까지 기다린 뒤 다음 구간을 실행했다. 요청·응답 본문, 발화 ID, 교정문과 원시 오류는 결과에 기록하지 않았다.

초기 실행에서 `actual_delivery_rps` 분모에 마지막 HTTP 응답시간이 포함되는 표시 오류를 발견해 결과를 폐기했다. 도착 시각 간격으로 계산하도록 수정·테스트하고 API 프로세스를 재시작해 모니터 집계를 초기화한 뒤 최종 실행을 한 번 더 수행했다. shadow 지연시간 요약은 각 구간 단독 값이 아니라 `process_cumulative_since_api_start` 범위다.

## 최종 결과

| 목표·실제 입력률 | 요청 | `/analyze` 성공 | 전송 종료 시 큐 | shadow 성공 | drop | 최종 상태 | 응답 p95 |
| ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 0.5 req/s | 4 | 4/4 | 0 | 4 | 0 | 통과 | 29.490ms |
| 1.0 req/s | 6 | 6/6 | 0 | 6 | 0 | 통과 | 10.625ms |
| 2.0 req/s | 10 | 10/10 | 2 | 10 | 0 | drain 후 통과 | 9.665ms |
| 10.0 req/s | 80 | 80/80 | 64 | 61 | 19 | 의도된 bounded drop | 9.445ms |

모든 100개 `/analyze` 요청은 HTTP 200과 기존 `AnalysisResponse` 계약을 통과했다. `analyses`는 요청 수만큼 증가했고 `judgment_results`는 모든 구간에서 0행 증가했다.

### 안정 구간

- 0.5 req/s: queue wait p95 0.601ms, 최종 depth 0
- 1.0 req/s: 누적 queue wait p95 0.617ms, 최종 depth 0
- 2.0 req/s: 전송 종료 시 depth 2, drain 완료 후 drop 0, 누적 queue wait p95 970.370ms

단기 표본에서 2 req/s도 전부 처리했지만 큐가 증가하기 시작했으므로 장기 지속 가능 처리율로 승인하지 않는다. 모델 누적 지연시간은 p50 약 604ms, p95 약 650ms였다.

### 과부하 경계

10 req/s 80건을 7.9초에 전달하자 전송 종료 시 큐가 설정 최대치 64에 도달했다.

- enqueue: 77건
- 모델 처리 성공: 61건
- `queue_full`: 3건
- `expired`: 16건
- 총 drop: 19/80, 23.75%
- 누적 queue wait p95: 29106.234ms
- 최대 queue wait: 29961.326ms
- 종료 후 queue depth: 0

이는 큐가 무한히 늘어나지 않고 최대 길이와 TTL로 요청을 제한한다는 증거다. 반면 FIFO 큐의 drop은 트래픽 표본 편향을 만들 수 있으므로 운영 품질 표본 수집 방식으로 즉시 승인하지 않는다.

## 판정과 다음 단계

현재 설정에서 **1 req/s는 짧은 실측상 안정 구간**, **2 req/s는 backlog가 시작되는 경계**, **10 req/s는 명확한 과부하 구간**이다. 실제 지속 가능 처리율은 장기 soak 없이 확정하지 않는다.

다음 작업은 큐 크기를 더 키우는 것이 아니다. shadow admission을 약 1 req/s 이하로 제한하는 token-bucket 또는 샘플링 계층을 큐 앞에 두고 다음 조건을 검증한다.

- `/analyze` 응답은 계속 비간섭
- 초과 입력은 `sampled_out`으로 별도 익명 집계
- 큐의 TTL 만료와 `queue_full`을 정상 운용에서 최소화
- 샘플링이 특정 문장 내용이나 학습자 ID에 의존하지 않음
- 기능 플래그 기본 비활성 유지

## 검증과 복원

- rate probe 단위 테스트: 3/3 통과
- 전체 회귀 테스트: 251/251 통과
- 서비스: 모델/API 모두 inactive
- 기능 플래그: 둘 다 false
- 원본·격리 DB SHA-256: `ef3b42b92516c5332f2ed1dcd63ffe1a9c2ff8a53650c24a32205a0161ff09c9`
- 격리 DB `judgment_results`: 0
- `holdout_v0.4`: 모델 추론 0회 유지
- 커밋·푸시: 수행하지 않음
