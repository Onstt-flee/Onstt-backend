# feedback-v0.9 Stage 2 contract-stability holdout v0.11 결과

기준일: 2026-10-20

## 결론

Qwen3-8B `feedback-verifier-v0.9-stage2-contract-stability`을 봉인된 holdout v0.11 120건에서 정확히 한 번 실행했다. Stage 1 안전성과 탐지·권장 판단·교정문·지연시간은 통과했지만 Stage 2 계약 성공률이 76/80(95%)로 사전 기준 99%에 미달했다. 따라서 v0.9는 미채택이며 운영·관리자 경고·학습자 노출에 연결하지 않는다. holdout v0.11은 소비 완료이며 재실행하지 않는다.

## 학습

- 베이스: Qwen3-8B, LoRA rank 16, alpha 32, dropout 0.05, seed 42, epoch 1
- 데이터: v0.8 전체 3,871건 + Stage 2 계약 안정성 120건 = 3,991건
- 분할: train 3,585건, eval 406건
- 학습 손실: 0.134448, 검증 손실: 0.004822, 총 449 steps, 1,525초
- 어댑터: `feedback-verifier-v0.9-stage2-contract-stability`
- 어댑터 SHA-256: `ce68df0d09446bea943e5b800995cd489703bce7a2f57544f974cc3b069f4cdc`

## 결과

| 지표 | 결과 | 기준 | 판정 |
| --- | ---: | ---: | --- |
| Stage 1 계약 | 120/120 (100%) | ≥99% | 통과 |
| 허위 불일치 | 0/40 (0%) | ≤2% | 통과 |
| 불일치 정밀도 | 80/80 (100%) | ≥95% | 통과 |
| 불일치 재현율 | 80/80 (100%) | ≥80% | 통과 |
| 보류 정확도 | 10/10 (100%) | ≥90% | 통과 |
| Stage 2 호출 규율 | 120/120 (100%) | 100% | 통과 |
| Stage 2 계약 | 76/80 (95%) | ≥99% | **실패** |
| 권장 decision | 75/80 (93.75%) | ≥90% | 통과 |
| 허용 교정문 | 45/45 (100%) | ≥80% | 통과 |
| 조건부 총 p95 | 2.888초 | ≤10초 | 통과 |

실패 4건은 모두 미완성 발화를 `acceptable`로 본 후보를 검수하는 `disagree_should_abstain` 가족에 집중됐다. Stage 1이 이를 `false_negative`로 잘못 분류하면서, Stage 2가 실제로 `insufficient_evidence`를 생성한 3건도 issue code와 권장 decision의 계약 불일치로 차단됐다. 나머지 1건은 `needs_correction`을 생성했다. 별도로 같은 가족 1건은 계약은 통과했지만 권장 decision이 틀려 총 권장 판단 정확도는 75/80이다.

## 남은 한계

- Stage 1 issue code와 Stage 2 권장 decision 사이의 의미 계약을 안정적으로 지키지 못해 자동 검수기로 사용할 수 없다.
- 이 평가는 자동 생성·검증 데이터의 사전 기준 판정이며 사람 또는 일본어 전문가 인증이 아니다.
- v0.9는 미채택이다. 추가 버전 학습을 자동으로 이어가지 않고, 현재 최선인 v0.8도 제한적 내부 shadow 상태로 유지한다.

## 고정 해시

- 데이터: `a020895a9b289fd5e4a1b68660486898d4813b5b72d542da89855df8e745b984`
- execution plan: `6d2d776cedbeffb27b2039a78a2905423a9d4449eb6c93842b89e79eded3c83d`
- 어댑터: `ce68df0d09446bea943e5b800995cd489703bce7a2f57544f974cc3b069f4cdc`
- 원시 결과(Git 제외): `5681e535aaea04ef672ad1d48c7fffef4048ffdd5aeff0ae74168cc8035e35b8`
- 원시 manifest(Git 제외): `d8f017e5cf969a2786b4e41b63bc4a901c65f0f64e33b8107d3acea8210421a1`
- claim(Git 제외): `73bbd72ee0e728a6552c408307817235a718c02351ad3dfdaffa8a9764b0dad7`
- receipt(Git 제외): `8087b8d95d1cb344ff8050517b5cb15458bfa9e454b8ff75f034b5a34e6c055e`
- 결과 요약: `25ee4ca9e3652fba0681ee51c21864b9fc9a4a3c9b34f88d5edfbfec2f39aa5d`
- 실행 기록: `86f2754dc49134d484dfd1b7a44ec6749c11a08adf5d9a81c8a895cb60a27a4f`

이 평가셋은 자동 생성·계약 검증 자료이며 사람 또는 일본어 전문가 인증 자료가 아니다.
