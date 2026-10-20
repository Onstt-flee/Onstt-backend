# feedback holdout v0.8 학습 전 봉인

기준일: 2026-10-19

feedback-v0.6 단계별 학습 전에 신규 120문항을 봉인했다. 분포는 `agree 50`,
`disagree 60`, `unreviewable 10`이며 stage 2 정답은 disagree 60건에만 존재한다.

기존 feedback 학습 v0.1~v0.5, holdout v0.1~v0.7, 조사 진단 v0.1/v0.2와
particle adversarial v0.1을 대조했다. 정확 입력과 원문 중복은 모두 0건이다.

| 파일 | SHA-256 |
| --- | --- |
| 데이터 | `541b8cd0cccfbb5fd9c8e7a63fcbe2174871472fb6e635c841387198ced7a16d` |
| manifest | `da19d1a44618e4814021053428ba23356d0a67a22e2f8a89045bf1c9042d972e` |
| protocol | `3d876bffc4369e6fa5872ee5996ad35d0609e17f61a2d4ed6b7f73e41ad9c122` |

현재 `ready_for_inference=false`, `consumed=false`, `model_inference_count=0`이다.
자동 생성·검증 데이터이며 사람 또는 일본어 전문가 검수 자료가 아니다. v0.6 학습 완료 후
후보·어댑터·코드 해시를 별도 실행계획에 고정하기 전에는 이 시험지를 열지 않는다.
