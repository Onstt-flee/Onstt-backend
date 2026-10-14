# Feedback verifier holdout v0.2 seal

## 상태

- 레코드: 120
- 데이터 SHA-256: `44a8dec5f4cf49a730c85c9d8be8c04e8be7013d43ba2ecc742c129059282358`
- 검수 상태: `generated_validated`
- 모델 추론 횟수: 120
- 프로토콜 상태: 소비 완료(`consumed=true`), 재실행 금지

데이터와 임계값은 로컬 커밋 `5ff3393`으로 첫 추론 전에 고정했다. 2026-10-15에
LoRA를 정확히 한 번 실행했으며 이후 정답, 후보 판단, 프롬프트, 임계값은 수정하지
않았다. 실행기는 이제 소비된 프로토콜과 SHA-256 불일치를 거부한다.

## 구성과 격리

원문 120건은 `evaluation/judgment/holdout_v0.5.jsonl`에서 가져오고 피드백 검수용
후보 판단과 정답을 새로 결정론적으로 생성했다. `agree`, 과교정, 오류 누락,
잘못된 교정, 비최소 교정, 오류 유형 오류, 불필요한 보류, 근거 불일치,
근거 없는 교정 사례를 포함한다.

- feedback-v0.1 학습 입력 600건과 완전 동일 입력 중복: 0
- 소비된 feedback holdout v0.1과 완전 동일 입력 중복: 0
- `source_stratum`: GPU/Pi 각 60건

`source_stratum`은 실제 GPU/Pi 출력이 아니라 채점 경로의 균형을 확인하기 위한
모의 표식이다. 따라서 strata 간 지표 차이는 실제 양자화 회귀를 증명하지 않는다.
실제 GPU/Pi 비교에는 각 런타임의 원시 판단 출력으로 만든 별도 시험이 필요하다.

## 실행 규약

- 모델: `feedback-qwen3-8b-v01`
- 어댑터 아티팩트 SHA-256:
  `efbbc9d2cf2bed81e6ce24da6070c25d7bc0755c213875224cfa204d58a22630`
- vLLM: 0.28.0
- reasoning parser: `qwen3`
- temperature: 0
- max tokens: 512
- strict JSON-only `feedback-v0.1` 계약

홀드아웃에 없는 학습 입력 1건으로 reasoning parser가 `message.content`에 JSON만
전달하는지 확인한 뒤 실행했다. 공식 결과는
`training/feedback/FEEDBACK_V0.2_RESULT.md`를 따른다.

## 해석 한계

자동 생성·검증 데이터이며 사람 또는 일본어 전문가 검수본이 아니다. 또한 원문은
판단모델 평가에 이미 사용된 내부 코퍼스에서 파생되어 외부 독립 품질 인증으로
사용할 수 없다. 이 시험의 역할은 v0.1 템플릿 암기와 출력 파서 문제를 분리해
피드백모델의 다음 개발 방향을 정하는 것이다.
