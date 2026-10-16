# 일본어 판단·피드백 듀얼모델 통합 현황

기준일: 2026-10-16
대상 브랜치: `api`
기준 체크포인트: 실제 shadow `758f345` 이후 관리자 집계 후속 체크포인트

이 문서는 현재 사용할 모델, 완료된 검증, 아직 증명되지 않은 범위와 다음 작업을 한곳에서
확인하기 위한 상위 요약이다. 세부 수치와 재현 근거는 마지막의 원본 문서를 따른다.

## 1. 한 줄 결론

GPU 서버에서 `Qwen3-4B + judgment-v0.2-D`가 먼저 판단하고,
`Qwen3-8B + feedback-verifier-v0.3`이 비동기로 그 결과를 검수하는 구조까지 구현·시험했다.
현재는 **GPU 전용 비노출 shadow 후보**이며 운영 기본 활성, 학습자 노출, 자동 교체·자동 배포는
승인하지 않았다. Raspberry Pi 경로는 현재 범위에서 제외하고 후속 작업으로 보존한다.

## 2. 현재 모델 선택

| 역할 | 현재 모델 | 상태 | 사용 범위 |
| --- | --- | --- | --- |
| 1차 문법 판단 | Qwen3-4B-Instruct-2507 + `judgment-v0.2-D` LoRA | 제한적 staging/shadow 기준선 | GPU, 기능 플래그 기본 OFF |
| 2차 결과 검수 | Qwen3-8B + `feedback-verifier-v0.3` LoRA | 내부 평가 통과, 합성 shadow 통과 | GPU 비동기 worker, 기능 플래그 기본 OFF |
| 판단 후속 LoRA | v0.2-F/I/J 등 | 미채택 | 비교 기록만 유지 |
| Pi 판단 | Q4_K_M/Q5_K_M GGUF + v0.2-D LoRA | 보류 | 이번 피드백모델 단계에서 제외 |
| 고용량 상한 비교 | Qwen3-14B | 오프라인 기준선 | 온라인 서비스 미사용 |

`v0.2-D`는 현재 가장 안정적인 판단 기준선이지만 최종 운영 승인 모델은 아니다.
피드백 v0.3도 판단 결과를 덮어쓰지 않으며 별도 audit으로만 저장한다.

## 3. 실행 구조

```text
STT 텍스트
  -> judgment-v0.2-D
  -> judgment_results 저장
  -> feedback_audit_jobs 생성
  -> feedback-verifier-v0.3 비동기 검수
  -> agree / disagree / unreviewable
  -> feedback_audits 별도 저장
  -> 보호된 관리자 API에서만 조회
```

안전 경계는 다음과 같다.

- 피드백 지연이나 장애가 기존 판단 API를 실패시키지 않는다.
- 피드백 결과는 기존 `judgment_results`를 수정하지 않는다.
- 판단·피드백 계약 위반은 임의 보정하지 않고 실패로 남긴다.
- 숫자 confidence를 생성하거나 저장하지 않는다.
- 모델이 수정 위치를 만들지 않고 백엔드가 원문과 교정문의 Unicode diff를 계산한다.
- 관리자 API는 Bearer 인증을 요구하며 목록 응답에 원문을 기본 노출하지 않는다.

## 4. 판단모델 검증 현황

### v0.2-D

- 봉인된 `holdout_v0.3`에서 사전 안전 기준을 통과했다.
- 기존 표본과 겹치지 않는 저장 STT 100건 shadow에서 최종 계약 성공 `99/100`,
  재시도율 `1%`, 성공 요청 p95 `1108.711ms`였다.
- 원문 보존 위반 1건은 재시도 후에도 실패해 503 차단 대상으로 유지했다.
- 기능 플래그와 학습자 노출은 계속 비활성이다.

### 후속 후보

- v0.2-I는 안전성 회귀로 미채택했다.
- v0.2-J는 구조 `120/120`, 재현율 `92%`였지만 과교정 `3/50`, 정밀도 `92%`,
  허용 교정문 `36/50`으로 사전 기준을 실패했다.
- 따라서 후속 버전이 아니라 v0.2-D를 연구·staging 기준선으로 유지한다.

## 5. 피드백모델 학습과 내부 평가

### 학습

| 항목 | 값 |
| --- | ---: |
| 전체 데이터 | 1,782건 |
| train / eval | 1,604 / 178 |
| epoch / step | 1 / 201 |
| LoRA rank / alpha / dropout | 16 / 32 / 0.05 |
| seed | 42 |
| train loss | 0.2034627781 |
| eval loss | 0.0109435385 |
| 학습 시간 | 1110.592초 |

자동 생성·검증 데이터는 `generated_validated`이며 사람 또는 일본어 전문가 검수 데이터로
표현하지 않는다.

### 봉인 holdout v0.4 단일 실행

| 지표 | 결과 | 내부 기준 |
| --- | ---: | ---: |
| JSON/계약 성공률 | 119/120, 99.17% | 99% 이상 |
| 올바른 판단 허위 불일치율 | 0% | 2% 이하 |
| 불일치 탐지 정밀도 | 100% | 95% 이상 |
| 불일치 탐지 재현율 | 98.57% | 80% 이상 |
| 권장 decision 정확도 | 94.29% | 90% 이상 |
| 허용 권장 교정문 일치율 | 85.71% | 80% 이상 |
| p95 | 2.617초 | 5초 이하 |

모든 내부 기준은 통과했다. 다만 이 시험지는 자동 생성·검증된 내부 자료이고 Pi 출처 비교와
외부 독립 라벨을 포함하지 않으므로 상태는 `passed_internal_gpu_evaluation`이다.

남은 실패는 계약 1건, 권장 decision 3건, 허용 교정문 5건이다. 소비된 holdout은 재튜닝이나
모델 재선택에 다시 사용하지 않는다.

## 6. 듀얼모델 배선·운영 안전 검증

### 합성 비노출 shadow 200건

실제 신규 판단 데이터가 충분하지 않아 결정론적 합성 일본어 200건으로 두 실모델의 연결만
검증했다.

| 구간 | 결과 |
| --- | ---: |
| 판단 전송·계약 | 200/200 |
| 피드백 작업·계약·audit 저장 | 200/200 |
| 피드백 verdict | agree 199, disagree 1 |
| 중복 job / audit | 0 / 0 |
| 판단 snapshot 변경 | 0건 |
| 판단 p95 | 961.580ms |
| 피드백 p95 | 1195.256ms |

이 결과는 queue, 계약, 저장, 모델 연결의 안정성 근거다. 정답 라벨이 없으므로 정확도,
과교정률 또는 일본어 품질 근거로 해석하지 않는다. 유일한 불일치 후보의 방향은 합리적이었지만
설명과 오류 유형에는 재검토 여지가 있어 학습 데이터로 사용하지 않는다.

### 관리자 API와 장애 복구

- 인증 없는 관리자 목록은 401, 보호된 health/list/issues/detail은 200을 확인했다.
- 피드백 모델 중단 시 readiness는 503 `model_unavailable`로 닫혔다.
- 완료된 audit 재시도는 409로 차단했다.
- worker를 실제 `SIGKILL -9`로 종료한 뒤 만료 lease를 회수해 두 번째 시도에서 성공했다.
- 복구 후 audit은 정확히 1개였고 중복과 판단 원본 변경은 0건이었다.
- 실제 격리 DB 관리자 투영은 이슈 그룹 8개(`emerging` 6, `recurrent` 2)를
  반환했고, 모델 불일치 멤버십 14건과 `contract` 실패 경고 1건을 내용 없이 집계했다.
- 반복 상태는 audit 행이 아니라 고유 `judgment_id` 수로 계산해 모델 버전별 재검수가
  반복 횟수를 부풀리지 않는다. 검사 전후 격리 DB SHA-256은 동일했다.
- 정답 라벨이 없으므로 반복 그룹은 오류 확정이나 품질 지표가 아니다.
- 이 프로세스 장애 시험은 로컬 stub 피드백 서버를 사용했으므로 모델 품질 근거가 아니다.

## 7. 현재 승인 범위

| 항목 | 상태 |
| --- | --- |
| 판단·피드백 코드 및 DB 구조 | 구현 완료 |
| feedback-v0.3 내부 GPU 평가 | 통과 |
| 실모델 합성 200건 배선 검증 | 통과 |
| 관리자 API 인증·장애 검증 | 통과 |
| worker lease·재시도·강제 종료 복구 | 통과 |
| 실제 STT 관리자 반복 이슈 집계 | 읽기 전용·비노출 검증 통과, 품질 판정은 미실행 |
| 실제 저장 STT 200건 feedback shadow | 운영 계약 통과, 품질 검수는 미실행 |
| 최소 독립 품질 검수 | 사람 검수 보류에 따라 미실행 |
| 학습자 경고 노출 | 금지 |
| 운영 기본 활성 | 금지 |
| 피드백 기반 자동 재학습·자동 배포 | 금지 |
| Pi 판단과 피드백 연동 | 보류 |

따라서 지금 가능한 작업은 기능 플래그를 기본 OFF로 유지한 **GPU 관리자용 비노출 shadow**다.

실제 저장 일본어 STT 200건을 비공개 snapshot으로 고정해 두 실모델을 실행했다.
판단모델은 운영과 동일한 1회 원문보존 재시도 적용 후 198/200(99.0%) 계약 성공,
재시도 5건 중 3건 복구, 2건 최종 차단을 기록했다. 피드백모델은 유효 판단 198건 중
197건 audit을 저장했고 1건은 3회 계약 실패 후 안전하게 격리했다. 판단 변경과 중복은
0건이었다. 정답 라벨과 음성 근거가 없으므로 품질 성능으로 해석하지 않는다.

## 8. 체크포인트와 파일 보존

- 로컬 기준점: 실제 shadow `758f345`와 후속 관리자 집계 체크포인트
- 브랜치 상태: 로컬 `api` 변경은 원격에 아직 푸시하지 않음
- 전체 회귀 테스트: `359/359` 통과
- 프로젝트·Qwen3 PEFT 두 환경 `pip check`: 통과
- 가중치, 원시 모델 출력, 임시 SQLite, 음성은 Git에 넣지 않는다.
- 추적 문서에는 집계와 SHA-256만 남긴다.

핵심 해시:

| 산출물 | SHA-256 |
| --- | --- |
| feedback-v0.3 학습 데이터 | `fca3ba047ffc5c19b2af5a3c515538bfda22ae92e50b0d5c3d611ee643a8d196` |
| feedback-v0.3 설정 | `998a7a8d89dee594780a5a2aa2a03ee3059e34836609c943b2c626aca0457bef` |
| feedback-v0.3 어댑터 | `3bcbc80d1559dacf60a84c708a8ab4c51ee4bd33532acf2ab134394aa2dcd1ad` |
| holdout v0.4 데이터 | `c22c5ddb0153c60d7087ef1e26580e669ea974e2bdafb0e65142f9eaeed60802` |
| holdout v0.4 원시 실행 | `6d3fe9032251403e05d2c8ab970ee7bd7f1ddb11c6f9c5d2afa9e1aeab4abf32` |

체크포인트에 포함하지 않은 Pi 후속 변경 4개는 작업 트리에 따로 남아 있다. 통합 문서 변경도
이번 정리 작업이므로 아직 커밋하지 않는다.

## 9. 다음 작업 순서

1. 기능 플래그 OFF와 학습자 비노출 상태를 유지한다.
2. 관리자 반복 이슈 집계는 검증 완료 상태로 유지하고 새 staging 데이터만 누적 관찰한다.
3. 사람 상세 검수는 보류하되 학습자 경고나 자동 재학습 전에 최소 독립 품질 검수를 요구한다.
4. 정답 라벨 없는 실제 shadow 결과를 학습 데이터나 정확도 주장에 사용하지 않는다.
5. 반복 실패가 충분히 누적된 뒤에만 새 판단모델 후보와 미사용 holdout을 설계한다.
6. Raspberry Pi 연동은 GPU 경로와 분리된 체크포인트에서 재개한다.

## 10. 기준 문서 지도

| 확인 목적 | 기준 문서 |
| --- | --- |
| 전체 시간순 진행 | [`../PROGRESS.md`](../PROGRESS.md) |
| 듀얼모델 설계와 안전 경계 | [`FEEDBACK_DUAL_MODEL_DESIGN.md`](FEEDBACK_DUAL_MODEL_DESIGN.md) |
| feedback-v0.3 학습 | [`../training/feedback/FEEDBACK_V0.3_TRAIN_RESULT.md`](../training/feedback/FEEDBACK_V0.3_TRAIN_RESULT.md) |
| 봉인 holdout 평가 | [`../training/feedback/FEEDBACK_V0.3_HOLDOUT_V0.4_RESULT.md`](../training/feedback/FEEDBACK_V0.3_HOLDOUT_V0.4_RESULT.md) |
| 합성 200건 shadow | [`../training/feedback/FEEDBACK_V0.3_SYNTHETIC_SHADOW_RESULT.md`](../training/feedback/FEEDBACK_V0.3_SYNTHETIC_SHADOW_RESULT.md) |
| 실제 저장 STT 200건 shadow | [`../training/feedback/FEEDBACK_V0.3_ACTUAL_STT_SHADOW_RESULT.md`](../training/feedback/FEEDBACK_V0.3_ACTUAL_STT_SHADOW_RESULT.md) |
| 관리자 API 시험 | [`../training/feedback/FEEDBACK_V0.3_ADMIN_SHADOW_RESULT.md`](../training/feedback/FEEDBACK_V0.3_ADMIN_SHADOW_RESULT.md) |
| worker 논리 복구 시험 | [`../training/feedback/FEEDBACK_V0.3_WORKER_RECOVERY_RESULT.md`](../training/feedback/FEEDBACK_V0.3_WORKER_RECOVERY_RESULT.md) |
| worker 실제 프로세스 종료 시험 | [`../training/feedback/FEEDBACK_V0.3_WORKER_PROCESS_CRASH_RESULT.md`](../training/feedback/FEEDBACK_V0.3_WORKER_PROCESS_CRASH_RESULT.md) |
| 체크포인트 안전 감사 | [`../training/feedback/FEEDBACK_V0.3_CHECKPOINT_AUDIT.md`](../training/feedback/FEEDBACK_V0.3_CHECKPOINT_AUDIT.md) |
| 판단모델 정책 | [`../deployment/judgment-staging/MODEL_POLICY.md`](../deployment/judgment-staging/MODEL_POLICY.md) |
| 판단 v0.2-D 최종 선택 근거 | [`../training/judgment/V0.2_DF_HOLDOUT_V0.3_RESULT.md`](../training/judgment/V0.2_DF_HOLDOUT_V0.3_RESULT.md) |
| Pi 보류 경로 | [`../deployment/judgment-pi5/README.md`](../deployment/judgment-pi5/README.md) |

## 11. 용어 해석 주의

- **내부 평가 통과**는 자동 생성·검증 시험 기준 통과이며 일본어 전문가 인증이 아니다.
- **shadow 통과**는 사용자 응답에 노출하지 않은 상태의 실행 검증이다.
- **합성 shadow**는 운영 배선 근거이며 실제 사용자 분포나 언어 정확도 근거가 아니다.
- **staging 후보**는 운영 기본값 승인과 다르다.
- **agree 199/200**은 정답률 99.5%가 아니다. 정답 라벨이 없는 모델 간 일치 집계다.
