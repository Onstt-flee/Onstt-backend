# 피드백모델 연구 동결 체크포인트

기준일: 2026-10-18

> 이 문서는 2026-10-18 당시 체크포인트다. 최신 상태는 `FEEDBACK_V0.9_HOLDOUT_V0.11_RESULT.md`와 `deployment/feedback-staging/model-policy.json`을 따른다.

## 확정 상태

- 운영 승인 피드백모델: 없음
- 학습자 노출: 금지
- 자동 재학습: 금지
- 기본 기능 플래그: 비활성
- 관리자용 GPU 비노출 shadow: `feedback-verifier-v0.3`만 허용
- `feedback-verifier-v0.4`, `feedback-verifier-v0.5`: 미채택 연구 기록
- `feedback-particle-risk-v0.1`: adversarial 기준 실패, 오프라인 연구 전용

`feedback-v0.3`의 shadow 허용은 문법 정확도나 운영 기본값 승인을 뜻하지 않는다. 기존
실제 저장 STT shadow는 정답 라벨 없는 배선·계약·격리 검증이다.

## 기계 판독 정책

정책은 `deployment/feedback-staging/model-policy.json`에 고정했다. 검증기는 다음을
fail-closed로 검사한다.

1. 운영 승인 모델이 `null`인지
2. `FEEDBACK_AUDIT_ENABLED=false`인지
3. 학습자 노출과 자동 재학습이 금지됐는지
4. v0.3 shadow alias·어댑터·SHA-256이 환경 예제와 systemd 서비스에 일치하는지
5. v0.4/v0.5가 미채택 상태인지
6. 조사 게이트가 adversarial 실패 결과와 함께 오프라인 상태인지
7. 소비한 holdout 재사용과 진단셋 맞춤 예외 추가가 금지됐는지

검증 결과 14/14 항목이 통과했다.

## 다음 실험 재개 조건

다음 학습이나 관문 후보는 현재 승인되지 않았다. 재개하려면 다음 순서를 지킨다.

1. 이전 후보와 구조적으로 다른 변경 가설을 작성한다.
2. 신규 미사용 평가셋과 합격 기준을 학습 전에 봉인한다.
3. 소비된 holdout v0.4/v0.5/v0.6과 particle adversarial v0.1을 모델 선택에 재사용하지 않는다.
4. 새 후보를 정확히 한 번 실행해 사전 기준으로 판정한다.
5. 통과하더라도 학습자 노출 전 별도의 독립 품질 검수를 요구한다.

같은 자동 템플릿 계열 LoRA 반복이나 사건 명사 예외 목록 확대는 다음 후보 가설로 인정하지
않는다.

## 파일과 해시

- 정책: `deployment/feedback-staging/model-policy.json`
  - SHA-256: `f94aff6d91f050b437abdc9d4bd22856f681e6d712ea170f83a0fb369972822e`
- 검증기: `scripts/validate_feedback_model_policy.py`
  - SHA-256: `07f698d3e98fa96bc7927931010538bc7c8b0425a21b8274e7c4cc48ca195e3b`
- 내용 없는 검증 결과: `evaluation/feedback/model_policy_v0.1.result.json`
  - SHA-256: `907b884225f3081a83016e4d4cf4a1868795dfa33d6080a55864769a1b73b25d`

## 검증

- 정책 일관성 검사: 14/14 통과
- 전체 회귀 테스트: 393/393 통과
- 프로젝트 및 Qwen3 PEFT 환경 `pip check`: 통과
- 변경 경로·내외부 해시·금지 파일·비밀 패턴 감사: 통과
- `git diff --check`: 통과

커밋과 푸시는 수행하지 않았다.
