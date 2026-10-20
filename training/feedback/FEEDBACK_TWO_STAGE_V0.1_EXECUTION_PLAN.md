# feedback two-stage v0.1 단일 실행계획

기준일: 2026-10-18

## 후보와 가설

후보는 Qwen3-8B BF16과 `feedback-verifier-v0.5` LoRA다. 같은 alias를 stage 1과
stage 2에 사용하되 서로 다른 엄격 프롬프트와 토큰 한도를 적용한다. v0.5는 기존 단일 호출
평가에서 미채택됐으며 이 상태는 바뀌지 않는다. 이번 실험은 재학습 없이 역할을 분리했을 때
결합 출력 계약 실패와 권장 교정 실패가 줄어드는지만 검증하는 구조적 실험이다.

## 고정값

- 데이터: holdout v0.7 120건, SHA-256
  `e928c104a39623891dc41d9fcc8ed285517594d9eea417662cdc91235f84e6ab`
- 베이스 manifest SHA-256:
  `915e444325028baa6485288a8147ee067385eb34bab425006605f21cba1647f5`
- 어댑터 SHA-256:
  `f6896ab2f0fdd408fb42a4a1fa6fa28f5039f557fab25a0aa7b7a1e76af52d95`
- alias: `feedback-qwen3-8b-v05-two-stage`
- endpoint: `127.0.0.1:1235`
- temperature 0, top-p 1, stage 1 192토큰, stage 2 384토큰
- vLLM 0.28.0, reasoning parser `qwen3`, `VLLM_USE_FLASHINFER_SAMPLER=0`
- 계약·실행기·채점기 해시는 execution plan JSON에 고정

## 단일 실행 경계

선봉인 protocol은 수정하지 않는다. 별도 execution plan만 `ready_for_inference=true`이며
실행 횟수는 0이다. 실행기는 endpoint와 결과 경로를 대조하고 시작 즉시 원자적 claim을
생성한다. 프로세스가 중단되어도 claim을 삭제해 재실행하지 않는다. 완료 시 결과 해시가 든
receipt를 남긴다. 원시 결과·claim·receipt·가중치는 Git 밖에 보관한다.

## 판정 경계

v0.7의 사전 임계값을 하나라도 실패하면 후보를 미채택한다. 통과하더라도 자동으로 운영,
관리자 경고, 학습자 노출 또는 자동 재학습에 연결하지 않는다. 자동 생성·검증 시험 결과이며
일본어 전문가 인증으로 표현하지 않는다.
