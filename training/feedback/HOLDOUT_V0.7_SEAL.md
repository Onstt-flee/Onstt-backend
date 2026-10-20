# feedback two-stage holdout v0.7 봉인

기준일: 2026-10-18

## 목적과 순서

단일 호출 피드백모델이 verdict 탐지와 권장 교정 생성을 한 번에 수행하면서 발생한 실패를
분리 평가하기 위한 신규 시험지다. `feedback-two-stage-v0.1` 계약 구현 전에 생성·중복
검사·임계값 고정을 완료했다. 봉인 시점의 모델 추론은 0회다.

이 자료는 자동 생성·계약 검증 데이터이며 사람 또는 일본어 전문가 검수 자료가 아니다.
운영 승인이나 실제 사용자 분포를 증명하지 않는다.

## 구성

- 총 120문항
- stage 1: agree 50 / disagree 60 / unreviewable 10
- stage 2 정답이 존재하는 문항: disagree 60건만
- 10개 새로운 도메인 어휘군
- 정상 판단, 정상 교정, 오류 누락, 과교정, 잘못된 교정, 비최소·의미 변경,
  근거 불일치, 불필요한 보류, 음성 없는 표기 경계 포함
- 기존 training v0.1~v0.5, holdout v0.1~v0.6, 조사 진단·adversarial과
  정확 입력 및 원문 중복 0건

## 사전 임계값

| 단계 | 지표 | 기준 |
| --- | --- | ---: |
| stage 1 | 계약 성공률 | 99% 이상 |
| stage 1 | 허위 불일치율 | 2% 이하 |
| stage 1 | 불일치 정밀도 | 95% 이상 |
| stage 1 | 불일치 재현율 | 80% 이상 |
| stage 1 | unreviewable 정확도 | 90% 이상 |
| stage 2 | 호출 규율 | 100% |
| stage 2 | 계약 성공률 | 99% 이상 |
| stage 2 | 권장 decision 정확도 | 90% 이상 |
| stage 2 | 허용 교정문 일치율 | 80% 이상 |
| 조건부 전체 | p95 | 10초 이하 |

stage 2 호출 규율은 유효한 stage 1 `disagree`에만 정확히 한 번 호출하고, agree와
unreviewable에는 호출하지 않는 것을 뜻한다.

## 해시와 상태

- 데이터: `evaluation/feedback/holdout_v0.7.jsonl`
  - SHA-256: `e928c104a39623891dc41d9fcc8ed285517594d9eea417662cdc91235f84e6ab`
- manifest: `evaluation/feedback/holdout_v0.7.manifest.json`
  - SHA-256: `91dbc335db08d65ef7a7f7bf77665853d568c7df32f701b6cb6536ea68100c66`
- protocol: `evaluation/feedback/holdout_v0.7.protocol.json`
  - SHA-256: `f07ca0feb36deca11521a70d5e22f39deab2e1f56a4f9f528fd4e0e3936309d7`
- 상태: `ready_for_inference=false`, `consumed=false`, 모델 추론 0회

후보·어댑터·실행기가 고정되기 전에는 `ready_for_inference`를 바꾸거나 시험지를 실행하지
않는다. 결과 확인 뒤 같은 시험지에 맞춰 프롬프트·데이터·규칙을 수정하지 않는다.

## 검증

- 봉인·계약 신규 단위 테스트: 8/8 통과
- 전체 회귀 테스트: 401/401 통과
- 두 Python 환경 `pip check`: 통과
- 체크포인트 해시 감사와 `git diff --check`: 통과
