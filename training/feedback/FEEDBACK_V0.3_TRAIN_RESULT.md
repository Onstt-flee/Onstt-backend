# feedback-verifier v0.3 학습 결과

기준일: 2026-10-15

## 결론

Qwen3-8B 기반 `feedback-verifier-v0.3` LoRA 학습을 완료했다. 이 단계는 학습
완료일 뿐 채택 결과가 아니다. 봉인된 holdout v0.4 단일 실행과 안전 기준 판정 전까지
피드백 worker, 관리자 경고, shadow는 계속 비활성이다.

## 입력과 학습 조건

- 학습 데이터: 1,782건(train 1,604 / eval 178)
- 데이터 SHA-256: `fca3ba047ffc5c19b2af5a3c515538bfda22ae92e50b0d5c3d611ee643a8d196`
- train SHA-256: `e4e243d51cbe7913f85bd6d2aa8076527881d30199eec807f5c6d95003dd97f5`
- eval SHA-256: `48aab6ba8ba7ab361a4fd66ff70b431ce054580ef6935d32ad2616b0a6842954`
- 베이스 모델 manifest SHA-256: `915e444325028baa6485288a8147ee067385eb34bab425006605f21cba1647f5`
- seed 42, 1 epoch, 201 step
- LoRA rank 16, alpha 32, dropout 0.05
- 학습률 0.0002, gradient accumulation 8

## 결과

- 총 소요 시간: 1,110.592초
- 실제 학습 시간: 1,075.412초
- train loss: `0.2034627781`
- eval loss: `0.0109435385`
- 어댑터 크기: 174,655,536 bytes
- 어댑터 SHA-256: `3bcbc80d1559dacf60a84c708a8ab4c51ee4bd33532acf2ab134394aa2dcd1ad`
- adapter config SHA-256: `f89df57617783dbe624d3213a02d44a3ddc87f53cc033bb5d1ce1a9fdb83b27b`
- run manifest SHA-256: `64781b806577c974940257f2d823017098551b24a7a72cd201a32e87841000b2`

어댑터와 원시 학습 산출물은 Git에 넣지 않고
`/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.3`에 보관한다.

## 실행 환경

- GPU: NVIDIA RTX A6000
- Python 3.12.14
- PyTorch 2.13.0+cu130 / CUDA 13.0
- Transformers 5.16.1
- TRL 0.28.0 / PEFT 0.20.0 / Datasets 4.8.5

처음 사용한 `qwen3-peft` 환경에는 `datasets`가 없어 모델 적재 전에 중단됐으며
출력 파일은 생성되지 않았다. 기존의 완전한 `qwen3-lora-train` 환경에서 입력 해시를
재검증한 뒤 본 학습을 완료했다.

## 다음 단계

holdout v0.4 프로토콜에 어댑터·데이터·설정·run manifest 해시를 결합했다. 다음은
Qwen3-8B와 v0.3 LoRA를 vLLM으로 한 번 제공하고 120건을 temperature 0으로 정확히
한 번 실행하는 것이다. 결과 확인 후 같은 시험지 재실행이나 재튜닝은 금지한다.
