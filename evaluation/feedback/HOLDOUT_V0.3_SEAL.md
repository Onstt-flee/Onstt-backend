# Feedback verifier holdout v0.3 pre-training seal

## 고정 상태

- 레코드: 120
- 데이터 SHA-256: `fbb6d1f53f31467f3fb2fb295cb1b9ebcbabd2ed6e64859e425222bbe70d8313`
- 정답 분포: agree 32, disagree 80, unreviewable 8
- 검수 상태: `generated_validated`
- 모델 추론 횟수: 0
- 프로토콜: `ready_for_inference=true`, `consumed=false`

새 feedback-v0.2 학습보다 먼저 데이터와 기준을 고정했다. 학습 완료 후 어댑터,
학습 데이터, 학습 설정의 SHA-256을 프로토콜에 기록했다. 이 변경을 별도 추론 전
커밋으로 고정한 뒤에만 한 번 실행한다.

## 격리와 범위

- feedback-v0.1 학습 입력과 완전 동일 입력: 0
- feedback holdout v0.1과 완전 동일 입력: 0
- feedback holdout v0.2와 완전 동일 입력: 0
- STT 표기 경계 8건은 원음 부재 때문에 `unreviewable`로 평가

원문은 이미 소비된 내부 judgment holdout v0.4에서 파생했으므로 외부 독립
코퍼스가 아니다. 실제 Pi GGUF 판단 출력도 현재 저장소에 없어 GPU/Pi 차이는
측정하지 않는다. 따라서 이 시험지는 내부 후보 선택에만 사용하고, 통과하더라도
운영 자격이나 전문가 검수를 주장하지 않는다.

## 다음 단계

1. Qwen3-8B + feedback-v0.2 LoRA를 이 시험지에서 정확히 한 번 실행한다.
2. 필수 품질 기준을 통과해도 실제 Pi 출력과 독립 라벨이 확보되기 전에는
   운영 worker, 관리자 경고, 200건 shadow를 활성화하지 않는다.
