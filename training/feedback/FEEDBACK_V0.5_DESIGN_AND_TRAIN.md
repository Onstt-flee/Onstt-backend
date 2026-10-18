# feedback-v0.5 설계 및 학습 결과

기준일: 2026-10-17

## 결론

`feedback-v0.4`의 독립 평가에서 남은 정상 목적지 문장 과민 반응과 존재 장소
`で → に` 교정 누락을 보강한 `feedback-v0.5` LoRA 학습을 완료했다. 학습 전에 별도
`holdout_v0.6` 120건을 먼저 봉인했으며, 학습·기존 평가·진단과 원문 및 완전 입력 중복은
모두 0건이다.

학습 자체는 정상 종료했지만 모델 채택을 뜻하지 않는다. 채택 여부는 봉인된 v0.6에서
Qwen3-8B 베이스라인과 v0.5 LoRA를 각각 정확히 한 번 실행한 결과로만 판단한다.

## 봉인 holdout v0.6

| 구분 | 건수 |
| --- | ---: |
| 전체 | 120 |
| agree | 50 |
| disagree | 60 |
| unreviewable | 10 |
| 정상 교정 동의 | 20 |
| 정상 근거 표현 다양화 | 30 |
| false negative 의미 고정 | 30 |
| false positive 의미 고정 | 20 |
| reason mismatch | 5 |
| 불필요한 보류 | 5 |
| STT·음성 근거 경계 | 10 |

v0.6은 `generated_validated`이며 사람 또는 일본어 전문가 검수 자료가 아니다. 계획된
베이스라인 1회와 LoRA 1회를 완료한 뒤 `consumed=true`로 잠갔다.

## 학습 데이터 v0.5

v0.4 2,082건을 그대로 기반으로 사용하고 실패 구조를 일반화한 새 문항 240건을 추가했다.

| 구분 | 건수 |
| --- | ---: |
| 전체 | 2,322 |
| train | 2,084 |
| eval | 238 |
| 목적지 정상 안정성 | 60 |
| false negative 계약 앵커 | 80 |
| false positive 계약 앵커 | 40 |
| 올바른 존재 장소 교정 동의 | 20 |
| 불필요한 보류 앵커 | 20 |
| 음성 근거 경계 앵커 | 20 |

소비된 v0.5 실패 문장을 그대로 학습하지 않고 다른 명사·장소·동작 템플릿으로 일반화했다.
holdout v0.5·v0.6과 조사 진단 v0.1·v0.2에 대한 원문·완전 입력 중복은 모두 0건이다.

## 학습 조건과 결과

- 베이스: `Qwen/Qwen3-8B`
- LoRA: rank 16, alpha 32, dropout 0.05
- seed: 42
- epoch / step: 1 / 261
- learning rate: 0.0002
- train loss: `0.1581996007428493`
- eval loss: `0.005888455081731081`
- 총 실행 시간: `1521.65`초
- 출력 위치: `/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.5`

## 해시

- holdout v0.6 데이터: `104e0811b89843debb8d9e2e9b3be337cbf528918f85606a88b17b622bef1581`
- holdout manifest: `9333797dfdcce9bdb75f1fc4f12e4955f3722db719dee07e2b526dca577e2499`
- 학습 원본: `991bb71e8a9115cb1b18f786f18636cd0c6e693790d16a7c22b37fb9b7b6220a`
- train ChatML: `7684f1e6707da0def1e7ef603d3dbca84d79cd38e7c938a5f5ce37db1c1c2211`
- eval ChatML: `e1fbc503a2016df6994e03bf816769b5fe77ba3de30bd8e3526874e7b9fb9fe9`
- 학습 manifest: `f8cc618e823e9fca85032116f5016ca9ef832a3c03955a7984d6b452a8a23edc`
- 학습 설정: `cac379894927b87c9151b621a184a1ddab75532c13ff98cf62d920ceb773ec2d`
- LoRA 어댑터: `f6896ab2f0fdd408fb42a4a1fa6fa28f5039f557fab25a0aa7b7a1e76af52d95`
- 어댑터 설정: `2124306d7a848b078aff0ac5e4355e64588a904b271e4c4d95c65c0540aff1c7`
- 학습 실행 manifest: `be5a802a6127d9804f3162327410aaf6cef8fbd43ef3455ba8dded9e29f80e2f`

가중치와 원시 모델 출력은 Git에 넣지 않는다. v0.6 protocol 해시는 두 실행과 최종 판정이
기록된 뒤 소비 완료 상태에서 다시 고정한다.

## 최종 상태

평가 결과는 `FEEDBACK_V0.5_RESULT.md`를 따른다. 필수 기준 세 항목을 실패했으므로 v0.5를
worker·관리자 경고·자동 학습에 연결하지 않는다.
