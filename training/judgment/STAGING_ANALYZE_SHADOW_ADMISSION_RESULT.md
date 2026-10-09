# `/analyze` shadow admission/token-bucket 결과

- 상태: **1 req/s 이하 전량 처리, 고율 입력 익명 sampling, queue drop 0**
- 일시: 2026-10-08 KST
- 설정: token bucket 1 req/s, burst 1, 경계 지터 허용 50ms, 큐 최대 64건, TTL 30초, 단일 consumer
- 모델: Qwen3-4B + `judgment-qwen3-4b-failure-focus-v0.2-d`
- 입력 계획 SHA-256: `f35627f143bec3eda418f8887197e372ed1849dc0fb23be24d9727b3322d37be`

## 구현 원칙

큐 앞에서 요청 내용·사용자 ID와 무관하게 프로세스 로컬 token bucket으로 admission을 결정한다. 초과 입력은 모델 실패나 drop으로 기록하지 않고 `sampled_out_total`에만 익명 집계한다. `/analyze` 응답과 `analyses` 저장은 admission 결과에 영향을 받지 않으며 shadow 판단은 `judgment_results`에 저장하지 않는다.

기본값은 `JUDGMENT_SHADOW_ADMISSION_RPS=1`, `JUDGMENT_SHADOW_ADMISSION_BURST=1`이다. 정확히 1초 간격인 요청이 background task 스케줄링의 수 ms 오차로 제외되지 않도록 최대 50ms의 경계 지터만 허용한다. 이 허용치는 burst 용량을 늘리지 않으며 모니터에 공개된다.

## 실측 결과

규칙 기반 합성 일본어 3건을 격리 staging DB에 넣고 0.5, 1, 2, 10 req/s 순서로 총 100건을 전송했다. 구간 사이에는 bucket 재충전을 위해 1.1초를 두었다. 결과에는 요청·응답 본문, 발화 ID, 교정문과 원시 오류를 기록하지 않았다.

| 목표·실제 입력률 | 요청 | `/analyze` 성공 | shadow 성공 | sampled out | failure/drop | 전송 종료 큐 | 응답 p95 | 판정 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0.5 req/s | 4 | 4/4 | 4 | 0 | 0/0 | 0 | 524.716ms | 통과 |
| 1.0 req/s | 6 | 6/6 | 6 | 0 | 0/0 | 0 | 81.173ms | 통과 |
| 2.0 req/s | 10 | 10/10 | 5 | 5 | 0/0 | 0 | 79.963ms | 통과 |
| 10.0 req/s | 80 | 80/80 | 8 | 72 | 0/0 | 0 | 55.472ms | 통과 |

- 기존 `AnalysisResponse`: 100/100 성공
- 기존 `analyses`: 요청 수만큼 증가
- `judgment_results`: 모든 구간 0행 증가
- shadow model success: 23건
- sampled out: 77건
- `queue_full`, `expired`, 기타 failure/drop: 모두 0건
- 최종 queue depth: 모든 구간 0
- 누적 queue wait p95: 0.609ms, 최대 0.727ms
- 누적 모델 지연 p95: 782.169ms, 최대 782.228ms

0.5와 1 req/s는 전량 처리됐고 2와 10 req/s는 예상대로 약 1 req/s만 모델에 전달됐다. 직전 큐-only 실험의 10 req/s 구간에서는 queue full 3건·TTL 만료 16건·큐 대기 p95 29.1초가 발생했지만, admission 적용 후 세 값은 각각 0건·0건·0.609ms로 줄었다.

## calibration 기록

첫 구현 실측은 0.5·2·10 req/s 구간을 통과했지만 정확히 1 req/s에서 background enqueue 시각이 경계보다 수 ms 빨라 2/6건이 `sampled_out` 처리됐다. 모델이나 큐 실패는 없었다. 이 결과를 승인 결과로 사용하지 않고 50ms 경계 지터 허용을 코드·모니터 계약에 명시한 뒤 프로세스와 DB를 초기화해 동일 입력 계획으로 재실행했다. 최종 표는 재실행 결과다.

## 판정과 한계

admission은 기존 `/analyze` 응답을 보호하면서 shadow 유입률을 모델의 단기 처리율 근처로 제한했다. 정상 운용에서 queue full·TTL 만료가 사라졌으므로 **제한적 staging/shadow 수집의 실행 안전성 경계는 충족**한다.

다만 이는 합성 입력의 짧은 시스템 안정성 실험이다. 문법 정확도, 과교정률, 실제 사용자 분포의 대표성, 장시간 soak, 다중 API worker·replica의 전역 rate limit을 증명하지 않는다. token bucket과 집계는 프로세스 로컬이므로 다중 worker 전환 전에는 외부 전역 admission이 필요하다. 기능 플래그 기본 비활성과 학습자 노출 미승인을 유지한다.

## 검증과 복원

- admission 집중 테스트: 26/26 통과
- 실측 전 전체 회귀 테스트: 253/253 통과
- 최종 전체 회귀 테스트: 254/254 통과
- 프로젝트·Qwen3 PEFT 두 환경 `pip check`: 통과
- 체크포인트 감사: 변경 109경로, 금지 경로·대용량 파일 0, 보호 해시 일치
- `git diff --check`: 통과
- 서비스: 모델/API 모두 inactive
- 기능 플래그: 둘 다 false
- 격리 DB 복원 SHA-256: `ef3b42b92516c5332f2ed1dcd63ffe1a9c2ff8a53650c24a32205a0161ff09c9`
- 격리 DB `judgment_results`: 0
- `holdout_v0.4`: 모델 추론 0회 유지
- 커밋·푸시: 수행하지 않음

최종 전체 회귀·두 환경 `pip check`·체크포인트 감사·문서 일관성 검사는 문서 반영 후 모두 통과했다.
