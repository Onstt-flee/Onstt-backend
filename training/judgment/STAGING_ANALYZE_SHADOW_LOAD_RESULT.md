# 기존 `/analyze` shadow OFF/ON 제한 부하 비교

> 후속 상태: 이 보고서의 24/26 과부하 폐기는 큐 적용 전 기준선이다. 제한 용량 단일 worker 적용 후 동일 입력 26/26 처리·drop 0건을 확인했다. 최신 결과는 [shadow 큐 실기동 결과](STAGING_ANALYZE_SHADOW_QUEUE_RESULT.md)를 따른다.

- 상태: **기존 응답 격리 통과, 현재 shadow 수집 용량은 동시 부하에 부적합**
- 일시: 2026-10-08 KST
- 모델: Qwen3-4B + `judgment-qwen3-4b-failure-focus-v0.2-d`
- 환경: sudo 없는 사용자 systemd, FastAPI 1 worker, 판단 동시 실행 상한 2

## 목적과 입력

동일한 규칙 기반 합성 일본어 인사 3건을 격리 DB에 넣고 기존 `POST /utterances/{id}/analyze`를 shadow OFF와 ON에서 각각 26회 호출했다. 단계는 동시성 1·6건, 2·8건, 4·12건이다. 두 실행 전마다 추적 원본 DB에서 격리 DB를 새로 복원했으며 입력 계획 SHA-256은 양쪽 모두 `f13cd2bf467aea092597d8684240f7073c5897d07abb7a7e47b6db5887da5f85`다.

실행기는 요청·응답 본문, 발화 ID, 교정문과 원시 오류를 결과에 기록하지 않는다. 기존 분석기의 외부 LLM alias 영향을 피하기 위해 룰 기반 greeting 경로만 사용했다. 따라서 이 실험은 기존 `/analyze` 배선과 부하 격리를 확인하며 일반 문장 분석·문법 품질·실제 사용자 트래픽을 대표하지 않는다.

## 결과

| 동시성 | 요청 | OFF p95 | ON p95 | p95 변화 | OFF 처리량 | ON 처리량 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 6 | 31.274ms | 27.760ms | -11.24% | 110.398 req/s | 99.418 req/s |
| 2 | 8 | 19.079ms | 11.875ms | -37.76% | 174.707 req/s | 228.610 req/s |
| 4 | 12 | 55.594ms | 75.651ms | +36.08% | 147.508 req/s | 151.534 req/s |

두 모드 모두 다음 불변 조건을 통과했다.

- `/analyze`: HTTP 200 및 기존 `AnalysisResponse` 계약 26/26
- `analyses`: 요청과 동일하게 26행 증가
- `judgment_results`: 증가 0행
- 판단 필드의 기존 응답 유출: 0건
- 요청·응답 내용의 집계 결과 포함: 없음

shadow ON의 background 결과는 다음과 같다.

- 예약: 26건
- 실제 모델 호출·성공: 2건
- 실패: 24건, 모두 `overloaded`
- 성공 2건 판단: `acceptable`
- 모델 지연시간: p50 636.953ms, p95 676.750ms
- 재시도: 0건

## 판정

기존 `/analyze` 응답과 저장은 shadow 실패로부터 격리됐다. 반면 현재 프로세스 로컬 상한 2와 대기시간 0초 정책에서는 짧은 burst의 92.31%(24/26)가 모델 호출 전에 차단됐다. 동시성 4의 `/analyze` p95도 작은 표본에서 OFF 대비 36.08% 높았다. 따라서 현재 구현은 fail-open 응답 보호에는 적합하지만, 동시 트래픽의 대표성 있는 shadow 결과 수집 기능으로 활성화할 수 없다.

이번 결과로 기능 플래그 기본값을 바꾸지 않는다. 다음 구현은 모델 재학습이 아니라 **응답 경로와 분리된 제한 용량 shadow 큐/worker**를 사전 설계하는 것이다. 큐는 요청을 무한 적재하지 않고 최대 길이, 만료 시간, 단일 소비 동시성, 종료 drain과 익명 drop 집계를 가져야 한다. 이를 구현하기 전에는 `JUDGMENT_SHADOW_ENABLED=false`를 유지한다.

초기 예비 실행은 공개 `AnalysisResponse`의 `candidate_types`와 `error_types`가 JSON 문자열이라는 계약을 리스트로 잘못 검사해 무효 처리했다. 실행기 fixture와 검증기를 실제 계약에 맞추고 단위 테스트를 통과시킨 뒤 위 결과를 새로 측정했다. 또한 시작 중 `KeyboardInterrupt`에도 서비스와 두 플래그가 남지 않도록 수명주기 관리기의 rollback 범위를 보강했다.

## 종료와 복원

- 사용자 모델/API 서비스: inactive
- `JUDGMENT_ENABLED=false`
- `JUDGMENT_SHADOW_ENABLED=false`
- 원본·격리 DB SHA-256: `ef3b42b92516c5332f2ed1dcd63ffe1a9c2ff8a53650c24a32205a0161ff09c9`
- 격리 DB `judgment_results`: 0
- `holdout_v0.4`: 모델 추론 0회 유지
- 커밋·푸시: 수행하지 않음

## 검증

- 전체 회귀 테스트: 242/242 통과
- 프로젝트 가상환경 `pip check`: 통과
- Qwen3 PEFT 가상환경 `pip check`: 통과
- 체크포인트 감사: 통과, 금지 경로·10MiB 초과 변경 파일 0개
- `git diff --check`: 통과
