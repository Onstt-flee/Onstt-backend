# feedback-v0.7 Stage 1 교정문 비교 설계와 데이터

기준일: 2026-10-19

## 목적

v0.6은 Stage 1/2 계약을 100% 충족했지만, 잘못된 교정문 10건과 의미 변경·과도 교정 10건을 `agree`로 놓쳤다. 호출된 Stage 2의 decision과 교정문은 모두 맞았으므로 Stage 2 정답은 변경하지 않고 Stage 1의 원문↔후보 교정문 비교 능력만 보강한다.

## 보강 구성

기존 v0.6 단계별 3,571건을 그대로 유지하고 서로 같은 원문에 후보 교정문만 달리한 최소대립쌍 160건을 추가했다.

| 추가 유형 | agree | disagree | 합계 |
| --- | ---: | ---: | ---: |
| 목적지 조사 올바른/잘못된 교정 | 20 | 20 | 40 |
| 동사 활용 올바른/잘못된 교정 | 20 | 20 | 40 |
| 최소 교정/장소 의미 변경 | 20 | 20 | 40 |
| 정상 원문 유지/불필요한 의미 변경 | 20 | 20 | 40 |
| 합계 | 80 | 80 | 160 |

| 전체 데이터 | Stage 1 | Stage 2 | 합계 |
| --- | ---: | ---: | ---: |
| train | 2,228 | 1,123 | 3,351 |
| eval | 254 | 126 | 380 |
| 전체 | 2,482 | 1,249 | 3,731 |

봉인된 v0.7·v0.8·v0.9와 정확 입력 및 원문 중복은 0건이다. 추가 자료는 `generated_validated`이며 사람 또는 일본어 전문가 검수로 표시하지 않는다.

## 학습 설정

- 베이스: Qwen3-8B BF16
- LoRA: rank 16, alpha 32, dropout 0.05
- seed 42, epoch 1, learning rate 2e-4
- 출력: `feedback-verifier-v0.7-stage1-comparison`
- v0.6과 동일 하이퍼파라미터로 데이터 보강 효과만 비교

## 고정 해시

- 생성기: `6fa8493f26364d7e475f7f898093abbb03c9a0c0e7f35e1429984f4c1c59fa98`
- 설정: `f5a3534e6d996db6a7a34cdbe181f9dc813bcb64f96616812c260989fa9f8d7f`
- 원천: `e3cd954b3b0379f233af3300861a843f98e7f9c5ece67317bd2643fe765b2fda`
- train ChatML: `5d9ddc9b03a3b1c7aec3b85e268ef0aebca0653fcd773779680f85dff66c982b`
- eval ChatML: `8590e228330b14778c5c515b485b7a7d38ec787826c1ec61ef1f71671ff4923b`
- manifest: `6bee8f55136dd15b40faa986ab8e2bbb02eee8d56ee6a4981bd4db7abf594b1c`

## 학습 결과

- 상태: `generated_validated` (운영 승인 또는 전문가 검수 의미 아님)
- 실행 시각: 2026-10-19T11:19:09Z
- 학습/검증: 3,351 / 380건, 419 step, epoch 1
- train loss: `0.13965016640617173`
- eval loss: `0.005171988625079393`
- 학습 시간: `1449.5338초`, 전체 실행: `1489.003초`
- 어댑터 크기: `174,655,536바이트`

외부 보관 산출물 SHA-256:

- `adapter_model.safetensors`: `d336e68a82643a9e161f6430ffb7f7fc164c6dd3ac9e863891b82564e9444382`
- `adapter_config.json`: `4f838052826b24e2cad6181a8a90565198f68ba8722b868ea61b73f4164da974`
- `run_manifest.json`: `5a29a922628252596d862b5a80e07f166df6ae450aaef75a1def7199d7646b82`

학습은 완료됐지만 후보 채택 여부는 아직 결정하지 않는다. 봉인된 holdout v0.9는 여전히 추론 0회이며, 실행계획과 단일 실행 claim을 고정한 뒤 정확히 한 번만 평가한다.
