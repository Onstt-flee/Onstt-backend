# GPU 피드백 검수모델 듀얼 시스템

기준일: 2026-10-14

## 역할과 경계

`Qwen3-4B + v0.2-D` 판단은 기존 API 결과의 최종 원본이다. GPU의
`Qwen3-8B + feedback-v0.1`은 이를 비동기로 검수할 뿐 기존 판단을
수정하거나 학습자 응답을 지연시키지 않는다. Pi Q4/Q5 판단도 edge sync가
완료된 뒤 GPU에서 같은 방식으로 검수한다. 출처와 양자화 정보는 모델 입력에
넣지 않고 provenance에만 보존한다.

## 구현된 흐름

```text
GPU judgment ─┐
              ├─ judgment_results (immutable)
Pi edge sync ─┘       ├─ judgment_provenance
                      └─ feedback_audit_jobs
                                ↓ separate worker
                       Qwen3-8B feedback-v0.1
                                ↓
                         feedback_audits
                                ↓
                protected audit / issue-group APIs
```

- `feedback-v0.1`은 `agree`, `disagree`, `unreviewable`만 허용한다.
- `disagree`에는 문제 코드와 완전한 권장 판단이 필요하다.
- 숫자 confidence와 모델 생성 edit 위치는 금지한다. Unicode edit은 백엔드가 계산한다.
- 계약 위반은 보정하지 않고 1분, 5분, 30분 간격으로 최대 3회 재시도한다.
- 큐 고유키는 판단 ID, 피드백 아티팩트 해시, 계약 버전이다.
- 기존 provenance가 없는 레코드는 `unknown`이며 추측해 채우지 않는다.
- 관리자 목록에는 원문이 없고, 모든 관리 API는 32자 이상 Bearer token이 필요하다.

## 데이터와 평가 상태

- 미사용 holdout: 120건, GPU/Pi strata 각 60건
- holdout SHA-256: `21f23d97b141652d6f53dff3d02b68ad0b3ffc902660ffe88b1b7212599a1eb1`
- 학습 원천: 자동검증 600건, train 540 / internal eval 60
- 학습 원천 SHA-256: `2f39a7988912733cdff88877c55702fb3eb8c01eadab38907c10428a6629006f`
- 사람·전문가 검수로 표시하지 않으며 모두 `generated_validated`다.
- holdout과 학습 원문의 정확 중복은 0건이다.
- holdout은 아직 추론 0회이며 베이스와 LoRA를 각각 정확히 한 번 평가하기 전까지 소비하지 않는다.

필수 통과 기준은 계약 99%, 허위 불일치 2% 이하, 불일치 정밀도 95%,
재현율 80%, 권장 decision 90%, 허용 교정문 80%, 출처 차이 5%p 이하,
A6000 p95 5초 이하다. LoRA가 8B 베이스를 실질적으로 개선하지 않으면
배포하지 않는다.

## 실행 순서

1. 이 변경을 검증하고 체크포인트 커밋한다.
2. 8B 베이스를 별도 vLLM에서 띄워 봉인 holdout을 한 번 실행한다.
3. `training/feedback/config_v0.1.json`으로 rank 16, alpha 32, dropout
   0.05, seed 42 LoRA를 학습한다.
4. LoRA를 같은 holdout에서 한 번 실행하고 동일 scorer로 비교한다.
5. 기준 통과 시에만 worker와 관리자 경고를 staging에서 활성화한다.
6. GPU 100건, Pi 50건 이상을 포함한 총 200건 shadow에서 판단 변경 0,
   job 유실·중복 0을 확인한다.
7. 반복 문제 자동 학습 후보 생성은 이후 단계이며 운영 alias 변경은 항상
   관리자 승인으로 남긴다. 피드백모델은 자신의 출력으로 재학습하지 않는다.

배포 템플릿과 장애 의미는 `deployment/feedback-staging/README.md`를 참고한다.
원시 모델 응답과 가중치는 Git에 넣지 않는다.
