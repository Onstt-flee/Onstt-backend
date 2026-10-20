# feedback-v0.7 Stage 1 comparison 단일 실행계획

기준일: 2026-10-19

## 후보와 가설

후보는 Qwen3-8B BF16과 stage별 계약으로 새로 학습한 `feedback-verifier-v0.7-stage1-comparison` LoRA다. 같은 alias를 stage 1과 stage 2에 사용하되 서로 다른 엄격 프롬프트와 토큰 한도를 적용한다. 학습 완료는 채택을 의미하지 않으며, 봉인된 v0.9에서 교정문 비교 실패 회복과 안전 클래스 보존을 단 한 번 검증한다.

## 고정값

- 데이터: holdout v0.9 120건, SHA-256
  `8582052baeece84b67e6afd44f167deff71ae275eac68fe61c5f77fe7ea1df48`
- 베이스 manifest SHA-256:
  `915e444325028baa6485288a8147ee067385eb34bab425006605f21cba1647f5`
- 어댑터 SHA-256:
  `d336e68a82643a9e161f6430ffb7f7fc164c6dd3ac9e863891b82564e9444382`
- alias: `feedback-qwen3-8b-v07-stage1-comparison`
- endpoint: `127.0.0.1:1235`
- temperature 0, top-p 1, stage 1 192토큰, stage 2 384토큰
- vLLM 0.28.0, reasoning parser `qwen3`, `VLLM_USE_FLASHINFER_SAMPLER=0`
- 계약·실행기·채점기 해시는 execution plan JSON에 고정
- execution plan SHA-256: `1defe7d51776354a452eeab2d79e8adbed6dfedd4f23f4736d0e2384115e1862`

## 단일 실행 경계

선봉인 protocol은 수정하지 않는다. 별도 execution plan만 `ready_for_inference=true`이며
실행 횟수는 0이다. 실행기는 endpoint와 결과 경로를 대조하고 시작 즉시 원자적 claim을
생성한다. 프로세스가 중단되어도 claim을 삭제해 재실행하지 않는다. 완료 시 결과 해시가 든
receipt를 남긴다. 원시 결과·claim·receipt·가중치는 Git 밖에 보관한다.

## 판정 경계

v0.9의 사전 임계값을 하나라도 실패하면 후보를 미채택한다. 통과하더라도 자동으로 운영,
관리자 경고, 학습자 노출 또는 자동 재학습에 연결하지 않는다. 자동 생성·검증 시험 결과이며
일본어 전문가 인증으로 표현하지 않는다.
