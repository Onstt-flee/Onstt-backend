# feedback holdout v0.10 선봉인

기준일: 2026-10-19

## 목적

feedback-v0.7은 불일치 재현율을 91.67%로 개선했지만 Stage 2의 정상 원문 복구, 정중체 보존과 계약 기준을 실패했다. v0.8의 Stage 2 복구·문체 보강 전에 같은 위험을 독립 어휘로 검사할 미사용 시험지 v0.10을 먼저 봉인한다.

## 구성

| 구분 | 건수 |
| --- | ---: |
| 전체 | 120 |
| agree | 50 |
| disagree | 60 |
| unreviewable | 10 |
| Stage 2 정답 보유 | 60 |
| 잘못된 교정문 집중 | 20 |
| 의미 변경·과도 교정 집중 | 20 |

기존 학습 v0.1~v0.7, holdout v0.1~v0.9, 조사 진단 및 adversarial 자료와 정확 입력·원문 중복은 모두 0건이다. 소비된 v0.9 실패 문장을 복사하지 않았다.

## 봉인 상태와 해시

- 데이터: `a3457b98022971afbed368b647a1801284069d1857a886a02151e3c382e186c1`
- manifest: `a518dd8428b71b806e3eab1ba3527062936ec1a2a2b316ccff37aee22028b119`
- protocol: `d21c28079ae4c6b85a24d07ca86b146ecfe40e8ac5b1fbfdf45ae24d220b9f95`
- 생성기: `019801ad745fc0d277d0ce205155fd4bdaea02e7b240008dcc5a81cd54ddaf5a`
- `ready_for_inference=false`, `consumed=false`, 추론 0회
- `sealed_before_v0.8_training=true`

## 경계

이 데이터는 `generated_validated`이며 사람 또는 일본어 전문가 검수 자료가 아니다. v0.8 학습 및 실행계획 해시를 고정하기 전에는 추론하지 않는다. 단 한 번 평가한 뒤 결과와 무관하게 재사용하지 않는다.
