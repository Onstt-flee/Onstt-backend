# feedback holdout v0.11 선봉인

기준일: 2026-10-20

## 목적

feedback-v0.8은 내부 holdout을 통과했지만 실제 저장 STT shadow에서 최종 3건이 모두 Stage 2 계약을 위반했다. v0.9의 Stage 2 계약 안정성 보강 전에 권장 판단 세 종류와 경계 오류를 독립 어휘로 검사할 미사용 시험지 v0.11을 먼저 봉인한다.

## 구성

| 구분 | 건수 |
| --- | ---: |
| 전체 | 120 |
| agree | 30 |
| disagree | 80 |
| unreviewable | 10 |
| Stage 2 정답 보유 | 80 |
| wrong correction·error type 집중 | 25 |
| 의미 변경·과도 교정 집중 | 30 |

기존 학습 v0.1~v0.8, holdout v0.1~v0.10, 조사 진단 및 adversarial 자료와 정확 입력·원문 중복은 모두 0건이다. 소비된 v0.10 문장을 복사하지 않았다.

## 봉인 상태와 해시

- 데이터: `a020895a9b289fd5e4a1b68660486898d4813b5b72d542da89855df8e745b984`
- manifest: `0f28a1a698e00f1faf0187c582fbaec35ff345b2cfd56755a6350bf1895d4df0`
- protocol: `f439f8d7c7bf839fa807c48642916c14c4bd2fcc21b1389b47c3f3bf5ab60b06`
- 생성기: `7e1370dfed820999a207efeeeb5f1ea1c3938911c3e55addc758418a5d21bab9`
- `ready_for_inference=false`, `consumed=false`, 추론 0회
- `sealed_before_v0.9_training=true`

## 경계

이 데이터는 `generated_validated`이며 사람 또는 일본어 전문가 검수 자료가 아니다. v0.9 학습 및 실행계획 해시를 고정하기 전에는 추론하지 않는다. 단 한 번 평가한 뒤 결과와 무관하게 재사용하지 않는다.
