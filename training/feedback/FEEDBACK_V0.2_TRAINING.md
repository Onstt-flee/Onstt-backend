# feedback-v0.2 Qwen3-8B LoRA 학습 기록

기준일: 2026-10-15

- 베이스: Qwen3-8B BF16
- 데이터: 자동 생성·검증 1,582건(train 1,424/eval 158)
- v0.3 원문 및 완전 입력 중복: 0
- LoRA: rank 16, alpha 32, dropout 0.05, seed 42
- 1 epoch, 178 optimizer step
- 총 시간: 984.752초
- train loss: 0.2145529916
- internal eval loss: 0.0097800447
- adapter model: 174,655,536바이트
- adapter model SHA-256: `9b4fc64f1ce8ea5ac0f4a41be61ca407df6be866b67623727d2f003807c2f427`
- adapter config SHA-256: `ee488c11bb745d50de77695fc521ca74a8abe186f2c4591d3e4d989f75c944cb`
- run manifest SHA-256: `125827959070847841c6384cbbea7f34eea490b27f417ae70fbe551e12edf038`
- 학습 데이터 SHA-256: `e16ba93aa9ba2b4abc098d478a9a66ea9cf94fc7f3e0b6b5815a5afc83da9ff8`
- 설정 SHA-256: `e1aae512ed5f0e3e2b5ecc88494bd8f311f27640fd6fc2c522083cc39fc4350b`

가중치는 Git에 넣지 않고 `/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.2`
에 보존한다. 낮은 내부 eval loss는 같은 결정론적 생성 규칙의 split 결과이므로 일반화
근거가 아니다. 후보 판단은 추론 0회로 봉인된 feedback holdout v0.3의 단일 실행으로
결정한다.
