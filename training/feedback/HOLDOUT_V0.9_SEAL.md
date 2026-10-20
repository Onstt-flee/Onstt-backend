# feedback holdout v0.9 선봉인

기준일: 2026-10-19

## 목적

feedback-v0.6은 stage별 JSON 계약은 100% 통과했지만 잘못된 교정문 10건과 의미 변경·과도 교정 10건을 `agree`로 놓쳤다. v0.7의 Stage 1 교정문 비교 보강 전에, 같은 위험을 다른 어휘와 문장 구조로 검사할 미사용 시험지 v0.9를 먼저 봉인한다.

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

기존 학습 v0.1~v0.6, holdout v0.1~v0.8, 조사 진단 및 adversarial 자료와 정확 입력·원문 중복은 모두 0건이다. 소비된 v0.8 실패 문장을 복사하지 않았다.

## 봉인 상태와 해시

- 데이터: `8582052baeece84b67e6afd44f167deff71ae275eac68fe61c5f77fe7ea1df48`
- manifest: `c0d319a44ebb222e51c1c339eb30265e3eebc11e6629d6fe438f3e373dd39475`
- protocol: `8188843331fab81ccfb4b1cd76ad4151f939fcf78ba52e7827d2803c02bad963`
- 생성기: `23940966289b3643f731619924bfd7923a6f54f1a701853489448d15ca922f5f`
- `ready_for_inference=false`, `consumed=false`, 추론 0회
- `sealed_before_v0.7_training=true`

## 경계

이 데이터는 `generated_validated`이며 사람 또는 일본어 전문가 검수 자료가 아니다. v0.7 학습 및 실행계획 해시를 고정하기 전에는 추론하지 않는다. 단 한 번 평가한 뒤 결과와 무관하게 재사용하지 않는다.
