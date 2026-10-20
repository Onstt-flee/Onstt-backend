# feedback-v0.6 단계별 학습 설계와 데이터

기준일: 2026-10-19

## 가설

v0.7 실패는 두 단계 구조 자체보다 결합 출력용 v0.5 어댑터가 stage 1 audit issue와
stage 2 grammar error type을 혼동한 것이 직접 원인이었다. 따라서 새 언어 정답을 추가하지
않고 기존 v0.5 원천 2,322건을 두 개의 시스템 프롬프트와 출력 계약으로 재표현한다.

- Stage 1: 모든 원천 2,322건에서 verdict, audit issue code, 검수 근거만 학습
- Stage 2: disagree 1,249건에서 권장 decision, 최소 교정, grammar error type, 근거만 학습
- agree·unreviewable에는 Stage 2 예시를 만들지 않음
- 학습 메시지는 실제 실행기 요청과 같은 시스템·사용자 구조 사용

## 데이터

| 구분 | Stage 1 | Stage 2 | 합계 |
| --- | ---: | ---: | ---: |
| train | 2,084 | 1,123 | 3,207 |
| eval | 238 | 126 | 364 |
| 전체 | 2,322 | 1,249 | 3,571 |

v0.7·v0.8과 정확 입력 및 원문 중복은 0건이다. holdout 정답과 모델 결과는 학습에 넣지
않았다. 모든 자료는 `generated_validated`이며 사람·전문가 검수로 표시하지 않는다.

## 학습 설정

- 베이스: Qwen3-8B BF16
- LoRA: rank 16, alpha 32, dropout 0.05
- seed 42, epoch 1, learning rate 2e-4
- 출력: `feedback-verifier-v0.6-two-stage`
- v0.5와 동일한 하이퍼파라미터를 유지해 출력 구조 변경 효과를 분리

## 고정 해시

| 산출물 | SHA-256 |
| --- | --- |
| 단계별 원천 | `39eda98851cb42c5bd608d48f794d020a4d80214cd827c7e5e78ac99fa8e5dfe` |
| train ChatML | `3a2864966bf37ba9e30557711d4caa0438dc90e7ed7f22be895979685eec63b8` |
| eval ChatML | `6bc814bf7ccc5b80ace88a51bb330236aa9d167301840fa499baae06a67cde10` |
| manifest | `80d05ae2f9ba9e7930e3d55c363443cdf576364f97f71cc6614443006563c331` |
| 학습 설정 | `1ba63da7578f3f9a2fb4ab8e28cee863dc627a9e614dfef5a4d43e3d6687734d` |

학습은 401 step으로 정상 완료됐다. train loss는 `0.1397754168`, eval loss는 `0.0051684384`, 총 실행 시간은 `1408.473`초다. 어댑터는 Git 밖의 `/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.6-two-stage`에 저장했다. v0.8 추론은 아직 0회이며, 이 학습 완료만으로 모델을 채택하지 않는다.
