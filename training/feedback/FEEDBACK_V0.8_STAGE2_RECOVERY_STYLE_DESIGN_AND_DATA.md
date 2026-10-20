# feedback-v0.8 Stage 2 복구·문체 보존 설계와 데이터

기준일: 2026-10-19

## 목적

v0.7은 Stage 1 불일치 재현율을 66.67%에서 91.67%로 개선했지만, 불필요한 보류 5건을 놓쳤고 Stage 2에서 정상 원문 복구 계약 3건과 정중체 교정 10건을 실패했다. v0.7 전체를 유지하고 이 세 실패 구조만 단계별로 보강한다.

## 보강 구성

기존 v0.7 단계별 3,731건을 유지하고 140건을 추가했다.

| 추가 유형 | Stage 1 | Stage 2 | 합계 |
| --- | ---: | ---: | ---: |
| 불필요한 보류 / 정당한 보류 경계 | 40 | 0 | 40 |
| 정상 원문 복구 | 0 | 40 | 40 |
| 정중 과거형 보존 | 0 | 40 | 40 |
| 장소 의미 보존 최소 교정 | 0 | 20 | 20 |
| 합계 | 40 | 100 | 140 |

| 전체 데이터 | Stage 1 | Stage 2 | 합계 |
| --- | ---: | ---: | ---: |
| train | 2,264 | 1,213 | 3,477 |
| eval | 258 | 136 | 394 |
| 전체 | 2,522 | 1,349 | 3,871 |

봉인된 v0.7·v0.8·v0.9·v0.10과 정확 입력 및 원문 중복은 0건이다. 추가 자료는 `generated_validated`이며 사람 또는 일본어 전문가 검수로 표시하지 않는다.

## 학습 설정

- 베이스: Qwen3-8B BF16
- LoRA: rank 16, alpha 32, dropout 0.05
- seed 42, epoch 1, learning rate 2e-4
- 출력: `feedback-verifier-v0.8-stage2-recovery-style`
- v0.7과 동일 하이퍼파라미터로 데이터 보강 효과만 비교

## 고정 해시

- 생성기: `00c9f365458bacef8df198e83ebe6a4014a4f1228a0552334a027f9e9ca1e8cd`
- 설정: `b8fd543fbffe80dfa8a3fb2bbfbea417822ada14db7ec3f1ad64c9e9d9959e6a`
- 원천: `07ae62567c5448066b107bd07b96372c65548146a7c3c542cc6cec542090ab6d`
- train ChatML: `71cabbdc57fd791a946797553339bdbe4dcf758a06d506deeddfbb18ba5cbc49`
- eval ChatML: `0efe383190ad578c4b5b7eb301dad41eeec1201899730667341bb5f197a63a52`
- manifest: `a8a95034da970e9aa37450f9f4756627a51423568952a12a97544ca40bbc634b`

## 학습 결과

- 상태: `generated_validated` (운영 승인 또는 전문가 검수 의미 아님)
- 실행 시각: 2026-10-19T12:16:20Z
- 학습/검증: 3,477 / 394건, 435 step, epoch 1
- train loss: `0.13570145415150542`
- eval loss: `0.005595449358224869`
- 학습 시간: `1481.472초`, 전체 실행: `1522.511초`
- 어댑터 크기: `174,655,536바이트`

외부 보관 산출물 SHA-256:

- `adapter_model.safetensors`: `c2f5901f97474337617f8e81fa61257f5e5d556f8b61a19ab57cb3e5e91e6180`
- `adapter_config.json`: `33cdee4522aff5293c2263d55a903597fb6b32e0401d43918742d4d5f32abb87`
- `run_manifest.json`: `99445e0f031ebd960f9463113bcb66ccfbbfea2c05a969a41f95d79900da96e9`

학습은 완료됐지만 후보 채택 여부는 아직 결정하지 않는다. 봉인된 holdout v0.10은 여전히 추론 0회이며, 실행계획과 단일 실행 claim을 고정한 뒤 정확히 한 번만 평가한다.
