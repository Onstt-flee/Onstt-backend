# Japanese STT Conversation API

라즈베리파이에서 생성한 일본어 STT 결과를 GPU 서버에 저장하고, 저장된 발화를 조회하거나 일본어 문장 분석/교정 결과를 관리하는 FastAPI 기반 백엔드입니다.

이 프로젝트는 음성 파일을 직접 STT로 변환하는 서버가 아니라, 외부 STT 클라이언트가 만든 결과를 받아 저장하고 후속 분석을 수행하는 API 서버입니다.

## 현재 개발 상태와 문서 안내

2026-10-16 기준 GPU 전용 듀얼모델의 실제 저장 STT 200건 비노출 shadow까지 완료했습니다. `Qwen3-4B + judgment-v0.2-D`는 운영과 동일한 원문보존 1회 재시도 적용 후 최종 계약 198/200(99.0%), 재시도율 2.5%, p95 1230.975ms였습니다. 계약 유효 198건을 `Qwen3-8B + feedback-verifier-v0.3`이 비동기 검수해 audit 197건을 저장했고, 1건은 3회 계약 실패 후 안전하게 격리했습니다. 중복 job/audit과 기존 판단 변경은 0건입니다. 이 결과는 운영 안정성 근거이며 일본어 정확도나 전문가 인증 근거가 아닙니다. 기능 플래그 기본 비활성, 학습자 비노출, 자동 재학습 보류를 유지합니다. 상세는 [`training/feedback/FEEDBACK_V0.3_ACTUAL_STT_SHADOW_RESULT.md`](training/feedback/FEEDBACK_V0.3_ACTUAL_STT_SHADOW_RESULT.md)를 참고합니다.

기준일은 2026-10-15입니다. v0.2-D는 봉인된 `holdout_v0.3` 안전 기준을 통과했고, 기존 50건과 겹치지 않는 실제 저장 STT 100건 shadow에서도 최종 출력 계약 99/100, 재시도율 1%, 성공 99건 p95 1108.711ms로 제한적 staging/shadow 기준을 통과했습니다. 원문 보존 위반 1건은 1회 재시도 후에도 실패해 503 차단 대상으로 남았습니다. sudo 없는 사용자 systemd, 최대 64건·TTL 30초의 단일 consumer 큐와 1 req/s·burst 1의 비식별 admission을 구현했습니다. 합성 rate probe 100건에서 기존 `/analyze` 응답은 100/100 성공했고, shadow 성공 23건·`sampled_out` 77건·failure/drop 0건을 확인했습니다. 기능 플래그 기본 비활성과 학습자 노출 미승인을 유지합니다. 후속 v0.2-I는 안전성 회귀로 미채택했고, 봉인된 `holdout_v0.4`의 D/F 단독 1회 비교에서는 허용 교정문이 D 32/50·F 36/50으로 사전 40/50 기준을 모두 실패했습니다. v0.4는 소비 완료됐으며 최종 운영 승격 후보는 없습니다. 마지막 v0.2-J는 소비된 v0.4를 학습 전용으로 편입해 45-step 학습했고, v0.5에서 정확히 한 번 평가했습니다. 구조 120/120·재현율 92%·복합 오류 6/10은 개선됐지만 과교정 3/50·정밀도 92%·허용 교정문 36/50으로 사전 기준을 실패해 미채택했습니다. Pi용 Q4_K_M+GGUF LoRA 변환과 로딩은 성공했지만 dev72 구조 계약이 71/72로 필수 72/72 기준에 한 건 미달해 Pi 50건 성능 게이트는 보류했습니다. v0.5는 소비 완료됐고 LoRA 반복은 종료했습니다.

후속 Q5_K_M 후보는 동일 dev72에서 구조 계약과 GPU BF16 판단 일치 72/72로 양자화 회귀 게이트를 통과했습니다. 다만 Pi 5 실장비의 50건 p95·RSS·발열 시험 전이므로 Q4 배포 기본값은 유지하고 Q5는 명시적 벤치마크 후보로만 관리합니다.

현재 선택은 다음과 같습니다.

- 첫 판단 전용 LoRA 학습 베이스: `Qwen/Qwen3-4B-Instruct-2507`
- 보조 스케일 비교 모델: `Qwen/Qwen3-8B`
- 고용량 정확도 상한 기준선: `Qwen/Qwen3-14B`
- 연구·staging 기준선: `Qwen3-4B + judgment-v0.2-D LoRA` 단독
- 최종 운영 승격 후보: 없음
- 운영 기본값 승인 모델: 없음
- 현재 단계: 실제 저장 STT 200건 GPU 듀얼모델 비노출 shadow 완료. 기능 플래그 기본 비활성·학습자 노출 금지를 유지하며 반복 불일치 집계만 관리자용으로 관찰

기존 `POST /utterances/{id}/analyze`의 이진 분석 계약은 그대로 유지합니다. 별도 `POST /utterances/{id}/judgment`는 3단계 판단 계약을 사용하며 `JUDGMENT_ENABLED=false`가 기본값입니다. 모델 서버가 없거나 출력 계약을 위반하면 판단 보류로 위장하지 않고 HTTP 503을 반환합니다.

### 작업 단계별 기준 문서

| 작업 과정 | 우선 참고할 Markdown | 용도 |
| --- | --- | --- |
| 현재 모델·검증·승인 범위 통합 요약 | [`docs/MODEL_SYSTEM_STATUS_2026-10-15.md`](docs/MODEL_SYSTEM_STATUS_2026-10-15.md) | 판단 v0.2-D와 feedback-v0.3의 역할, 핵심 결과, 한계, Git 상태와 다음 작업을 한 번에 확인 |
| 전체 진행 현황·완료/미완료 구분 | [`PROGRESS.md`](PROGRESS.md) | 매 작업 후 계속 갱신하는 단일 진행 현황 문서 |
| GPU 피드백 듀얼모델 설계·구현 | [`docs/FEEDBACK_DUAL_MODEL_DESIGN.md`](docs/FEEDBACK_DUAL_MODEL_DESIGN.md) | 검수 계약, DB·worker·관리 API 경계, 봉인 데이터와 다음 실행 순서 |
| 피드백 staging 배포 | [`deployment/feedback-staging/README.md`](deployment/feedback-staging/README.md) | A6000 듀얼 vLLM 자원 배분, 비활성 기본값, 서비스 시작·장애 처리 |
| feedback-v0.2 최종 내부 평가 | [`training/feedback/FEEDBACK_V0.2_HOLDOUT_V0.3_RESULT.md`](training/feedback/FEEDBACK_V0.2_HOLDOUT_V0.3_RESULT.md) | 단일 실행 지표, 반복 허위 불일치 6건과 미채택 근거 |
| feedback-v0.3 학습 결과 | [`training/feedback/FEEDBACK_V0.3_TRAIN_RESULT.md`](training/feedback/FEEDBACK_V0.3_TRAIN_RESULT.md) | 1,782건 학습 조건, 손실, 어댑터·run manifest 해시 |
| feedback-v0.3 내부 평가 | [`training/feedback/FEEDBACK_V0.3_HOLDOUT_V0.4_RESULT.md`](training/feedback/FEEDBACK_V0.3_HOLDOUT_V0.4_RESULT.md) | 120건 단일 실행 지표, 남은 실패와 GPU-only shadow 범위 |
| feedback-v0.3 합성 비노출 shadow | [`training/feedback/FEEDBACK_V0.3_SYNTHETIC_SHADOW_RESULT.md`](training/feedback/FEEDBACK_V0.3_SYNTHETIC_SHADOW_RESULT.md) | 실제 데이터 부재 시 200건 운영 배선 검증, 판단 불변성·queue 무결성·지연시간과 품질 주장 금지 경계 |
| feedback-v0.3 실제 저장 STT shadow | [`training/feedback/FEEDBACK_V0.3_ACTUAL_STT_SHADOW_RESULT.md`](training/feedback/FEEDBACK_V0.3_ACTUAL_STT_SHADOW_RESULT.md) | 실제 200건 계약·재시도·격리·불변성 결과와 품질 주장 금지 경계 |
| feedback 관리자 API 합성 shadow | [`training/feedback/FEEDBACK_V0.3_ADMIN_SHADOW_RESULT.md`](training/feedback/FEEDBACK_V0.3_ADMIN_SHADOW_RESULT.md) | Bearer 보호, 목록 비노출, 이슈 집계, retry 차단과 모델 장애 readiness 503 검증 |
| feedback worker 장애 복구 훈련 | [`training/feedback/FEEDBACK_V0.3_WORKER_RECOVERY_RESULT.md`](training/feedback/FEEDBACK_V0.3_WORKER_RECOVERY_RESULT.md) | 만료 lease 회수, 재시도 성공, 3회 실패 격리와 판단 불변성 검증 |
| feedback worker 프로세스 강제 종료 | [`training/feedback/FEEDBACK_V0.3_WORKER_PROCESS_CRASH_RESULT.md`](training/feedback/FEEDBACK_V0.3_WORKER_PROCESS_CRASH_RESULT.md) | 실제 worker SIGKILL 후 lease 회수, 정확히 한 번 audit과 진입점 결함 수정 |
| feedback-v0.3 체크포인트 감사 | [`training/feedback/FEEDBACK_V0.3_CHECKPOINT_AUDIT.md`](training/feedback/FEEDBACK_V0.3_CHECKPOINT_AUDIT.md) | 커밋 후보와 Pi 보류 변경 분리, 금지 파일·비밀 패턴·내외부 해시 감사 |
| 실제 GPU/Pi 피드백 입력 수집 | [`evaluation/feedback/RUNTIME_PAIR_INTAKE.md`](evaluation/feedback/RUNTIME_PAIR_INTAKE.md) | 동일 50건 실행, Pi 증빙·해시 검증, 개인정보 없는 집계와 다음 holdout 차단 조건 |
| 평가셋 구성·실행기·채점기 사용법 | [`evaluation/judgment/README.md`](evaluation/judgment/README.md) | 72문항, 출력 계약, 재현 명령과 평가 이력 |
| LoRA 파일럿 데이터·검수·내보내기 | [`training/judgment/README.md`](training/judgment/README.md) | 300문항 구성, 생성 근거, 검증 명령과 검수 승인 게이트 |
| provisional LoRA 실험 결과 | [`training/judgment/PILOT_V0.1_RESULT.md`](training/judgment/PILOT_V0.1_RESULT.md) | Qwen3-4B provisional 학습 조건, 실패 분석과 해시 |
| reviewed LoRA 평가 결과 | [`training/judgment/REVIEWED_V0.1_RESULT.md`](training/judgment/REVIEWED_V0.1_RESULT.md) | 사용자 검수 데이터 학습, 3모델 비교, 과교정 분석 |
| 최소대립쌍 v0.2-B 평가 결과 | [`training/judgment/HARD_NEGATIVES_V0.2_B_RESULT.md`](training/judgment/HARD_NEGATIVES_V0.2_B_RESULT.md) | 540문항 학습, 4모델 비교, 개선·회귀 사례와 채택 판단 |
| 실패 집중 v0.2-C·blind 평가 결과 | [`training/judgment/FAILURE_FOCUS_V0.2_C_RESULT.md`](training/judgment/FAILURE_FOCUS_V0.2_C_RESULT.md) | 출력 계약 v0.2, 628문항 학습, 150문항 holdout과 운영 보류 근거 |
| 동일 계약 v0.2-B 대조군 비교 | [`training/judgment/CONTRACT_CONTROL_V0.2_B_RESULT.md`](training/judgment/CONTRACT_CONTROL_V0.2_B_RESULT.md) | 출력 계약 변경과 추가 데이터 효과 분리, 72문항 대조와 공통 실패 유형 |
| 새 미사용 시험지·v0.2-D 설계 | [`training/judgment/V0.2_D_DESIGN.md`](training/judgment/V0.2_D_DESIGN.md) | 120문항 봉인·중복 감사, 보강 범위와 평가 순서 |
| v0.2-D 학습 데이터 생성 결과 | [`training/judgment/V0.2_D_DATA_RESULT.md`](training/judgment/V0.2_D_DATA_RESULT.md) | 추가 120문항·결합 748문항, 출력 계약과 누수 감사·해시 |
| v0.2-D 45-step LoRA 학습 결과 | [`training/judgment/V0.2_D_TRAIN_RESULT.md`](training/judgment/V0.2_D_TRAIN_RESULT.md) | 동일 하이퍼파라미터, 손실·가중치 해시 |
| v0.2-C↔D 개발셋 비교·회귀 분석 | [`training/judgment/V0.2_D_DEV72_COMPARISON.md`](training/judgment/V0.2_D_DEV72_COMPARISON.md) | 동일 조건 72문항 비교, 교정문 회귀와 holdout 보류 근거 |
| v0.2-E 교정문 회귀 보강 설계·데이터 | [`training/judgment/V0.2_E_DESIGN_AND_DATA.md`](training/judgment/V0.2_E_DESIGN_AND_DATA.md) | 추가 80문항·결합 828문항, 누수 감사·해시와 사전 채택 기준 |
| v0.2-E 학습·C/D/E 개발셋 결과 | [`training/judgment/V0.2_E_TRAIN_AND_DEV72_RESULT.md`](training/judgment/V0.2_E_TRAIN_AND_DEV72_RESULT.md) | 45-step 학습 해시, 교정 회복·안전성 회귀와 채택 보류 근거 |
| D 판단+E 교정 후보 게이트 | [`training/judgment/V0.2_DE_CANDIDATE_GATE_RESULT.md`](training/judgment/V0.2_DE_CANDIDATE_GATE_RESULT.md) | 정답 비사용 선택 규칙, 개발셋 개선·한계와 holdout 전 조건 |
| 최종 holdout 실행 규약 | [`evaluation/judgment/holdout_v0.2.protocol.json`](evaluation/judgment/holdout_v0.2.protocol.json) | D/E 어댑터·프롬프트·선택기 해시와 단일 실행·채택 임계값 |
| 소비된 holdout v0.2 최종 결과 | [`training/judgment/V0.2_DE_HOLDOUT_V0.2_RESULT.md`](training/judgment/V0.2_DE_HOLDOUT_V0.2_RESULT.md) | D 안전 기준 실패, 게이트 개선 0건, API 통합 중단 근거 |
| v0.2-F 보강 설계·새 시험지 | [`training/judgment/V0.2_F_DESIGN.md`](training/judgment/V0.2_F_DESIGN.md) | 실패 유형 보강 범위와 `holdout_v0.3` 봉인·사용 금지 조건 |
| v0.2-F 학습 데이터 결과 | [`training/judgment/V0.2_F_DATA_RESULT.md`](training/judgment/V0.2_F_DATA_RESULT.md) | 추가 120문항·결합 948문항, 누수 감사와 학습 전 검증 |
| v0.2-F 학습·개발셋 비교 | [`training/judgment/V0.2_F_TRAIN_AND_DEV72_RESULT.md`](training/judgment/V0.2_F_TRAIN_AND_DEV72_RESULT.md) | 45-step 학습, D/E/F 안전성·교정문 비교와 F 단독 채택 실패 |
| D 판단+F 교정 후보 게이트 | [`training/judgment/V0.2_DF_CANDIDATE_GATE_RESULT.md`](training/judgment/V0.2_DF_CANDIDATE_GATE_RESULT.md) | D 판단 잠금, 개발셋 교정문 +2와 조건부 지연시간 검증 |
| holdout v0.3 실행 규약 | [`evaluation/judgment/holdout_v0.3.protocol.json`](evaluation/judgment/holdout_v0.3.protocol.json) | D/F 데이터·가중치·프롬프트·선택기·임계값과 단일 실행 정책 봉인 |
| 소비된 holdout v0.3 최종 결과 | [`training/judgment/V0.2_DF_HOLDOUT_V0.3_RESULT.md`](training/judgment/V0.2_DF_HOLDOUT_V0.3_RESULT.md) | D 안전 기준 통과, D+F 게이트 탈락, D 단독 shadow 통합 결정 |
| 실제 STT 50건 shadow 결과 | [`training/judgment/JUDGMENT_D_SHADOW_V0.1_RESULT.md`](training/judgment/JUDGMENT_D_SHADOW_V0.1_RESULT.md) | 49/50 계약 성공·실패 원인·지연시간·운영 승격 보류 근거 |
| 비중복 실제 STT 100건 shadow 파일럿 | [`training/judgment/JUDGMENT_D_SHADOW_V0.2_RESULT.md`](training/judgment/JUDGMENT_D_SHADOW_V0.2_RESULT.md) | 원문 보존 위반 1회 재시도, 99/100 계약 성공·DB 무변경·제한적 staging 판단 |
| 실제 STT 30건 독립 품질 검수 | [`evaluation/judgment/QUALITY_REVIEW_V0.1_GUIDE.md`](evaluation/judgment/QUALITY_REVIEW_V0.1_GUIDE.md) | 기존 150건 제외·예측 비노출 표본, 익명 라벨 작성법·오디오 귀속 금지·완료 검사 |
| 판단모델 staging 실행·중단 절차 | [`docs/JUDGMENT_STAGING_RUNBOOK.md`](docs/JUDGMENT_STAGING_RUNBOOK.md) | 임시 DB, vLLM·API 기동, 읽기 전용 사전점검, Swagger 확인과 rollback |
| 향후 커밋 전 체크포인트 감사 | [`scripts/audit_judgment_checkpoint.py`](scripts/audit_judgment_checkpoint.py) | 원시 실행·DB·가중치·오디오·대용량 파일 차단과 보호 해시·Git 제외 확인 |
| staging 동시성·장애 주입 결과 | [`training/judgment/STAGING_RESILIENCE_RESULT.md`](training/judgment/STAGING_RESILIENCE_RESULT.md) | 합성 1,000이벤트 집계, timeout·재시도 재실패·DB 실패의 차단과 익명 집계 |
| staging FastAPI–vLLM 실부하 결과 | [`training/judgment/STAGING_HTTP_LOAD_RESULT.md`](training/judgment/STAGING_HTTP_LOAD_RESULT.md) | 격리 DB·합성 입력 26건, 동시성 1/2/4의 HTTP 계약·지연시간·처리량 |
| staging backpressure·readiness 결과 | [`training/judgment/STAGING_RUNTIME_SAFETY_RESULT.md`](training/judgment/STAGING_RUNTIME_SAFETY_RESULT.md) | 동시 실행 상한, 429 fail-fast, 모델 alias readiness와 종료 drain 검증 |
| staging 단기 soak·복구 결과 | [`training/judgment/STAGING_SOAK_RECOVERY_RESULT.md`](training/judgment/STAGING_SOAK_RECOVERY_RESULT.md) | 동시성 2·150건 지속 부하와 readiness 200→503→200 자동 복구 |
| staging systemd 배포 템플릿 | [`training/judgment/STAGING_DEPLOYMENT_TEMPLATE_RESULT.md`](training/judgment/STAGING_DEPLOYMENT_TEMPLATE_RESULT.md) | sudo 없는 사용자 서비스의 설치·fail-closed 관리·readiness 복구·합성 판단과 정리 결과 |
| 판단모델 실행·보존 정책 | [`deployment/judgment-staging/MODEL_POLICY.md`](deployment/judgment-staging/MODEL_POLICY.md) | v0.2-D만 staging 실행, 나머지는 기록 전용, 가중치·원시 결과 Git 제외 원칙 |
| 기존 분석 경로 shadow 통합 | [`training/judgment/STAGING_ANALYZE_SHADOW_RESULT.md`](training/judgment/STAGING_ANALYZE_SHADOW_RESULT.md) | `/analyze` 응답 비간섭·판단 무저장 background 실행과 익명 집계 검증 |
| `/analyze` shadow OFF/ON 제한 부하 | [`training/judgment/STAGING_ANALYZE_SHADOW_LOAD_RESULT.md`](training/judgment/STAGING_ANALYZE_SHADOW_LOAD_RESULT.md) | 기존 응답 26/26 격리 통과, shadow 24/26 과부하 차단과 별도 제한 큐 필요성 |
| 제한 용량 shadow 큐 실기동 | [`training/judgment/STAGING_ANALYZE_SHADOW_QUEUE_RESULT.md`](training/judgment/STAGING_ANALYZE_SHADOW_QUEUE_RESULT.md) | 단일 worker·64건·TTL 30초, 동일 burst 처리 26/26·drop 0·큐 대기 p95 14.88초 |
| shadow 입력률별 rate probe | [`training/judgment/STAGING_ANALYZE_SHADOW_RATE_RESULT.md`](training/judgment/STAGING_ANALYZE_SHADOW_RATE_RESULT.md) | admission 전 10 req/s에서 queue full·TTL bounded drop과 응답 100/100 보호 |
| shadow admission 결과 | [`training/judgment/STAGING_ANALYZE_SHADOW_ADMISSION_RESULT.md`](training/judgment/STAGING_ANALYZE_SHADOW_ADMISSION_RESULT.md) | 1 req/s token bucket, 100/100 응답 보호, shadow 23건·sampled out 77건·failure/drop 0 |
| v0.2.1 원문 보존 프롬프트 실험 | [`training/judgment/V0.2_1_PROMPT_HARDENING_RESULT.md`](training/judgment/V0.2_1_PROMPT_HARDENING_RESULT.md) | 동일 서버 v0.2 대조, 구조·판단·재현율 후퇴와 미채택 근거 |
| v0.2-G 합성 계약 보강 실험 | [`training/judgment/V0.2_G_TRAIN_AND_DEV72_RESULT.md`](training/judgment/V0.2_G_TRAIN_AND_DEV72_RESULT.md) | 운영 원문 미사용 108문항, 45-step 학습과 D/G 개발셋 비교·미채택 근거 |
| v0.2-H 고정 노출 샘플링 실험 | [`training/judgment/V0.2_H_TRAIN_AND_DEV72_RESULT.md`](training/judgment/V0.2_H_TRAIN_AND_DEV72_RESULT.md) | 같은 G 의미 소스의 720개 노출 고정, D/G/H 비교와 미채택·v0.4 미사용 근거 |
| v0.2-I D+F 통제 학습 실험 | [`training/judgment/V0.2_I_TRAIN_AND_DEV72_RESULT.md`](training/judgment/V0.2_I_TRAIN_AND_DEV72_RESULT.md) | D에 F 보강분만 결합한 45-step 학습, 교정 소폭 개선과 안전성 회귀·미채택 근거 |
| holdout v0.4 D/F 단독 비교 규약 | [`training/judgment/V0.2_DF_HOLDOUT_V0.4_PROTOCOL.md`](training/judgment/V0.2_DF_HOLDOUT_V0.4_PROTOCOL.md) | D/F를 각 1회 비교하는 절대 안전 기준·F 승격 조건·재실행 금지 정책 |
| 소비된 holdout v0.4 최종 결과 | [`training/judgment/V0.2_DF_HOLDOUT_V0.4_RESULT.md`](training/judgment/V0.2_DF_HOLDOUT_V0.4_RESULT.md) | D/F 모두 허용 교정문 80% 미달, 운영 승격 후보 없음과 다음 학습 분기 |
| 최종 holdout v0.5 봉인 | [`training/judgment/HOLDOUT_V0.5_SEAL.md`](training/judgment/HOLDOUT_V0.5_SEAL.md) | J 학습 전 120문항·중복 감사·추론 0회 봉인과 구조적 독립성 한계 |
| 최종 v0.2-J 학습 설계·데이터 | [`training/judgment/V0.2_J_DESIGN_AND_DATA.md`](training/judgment/V0.2_J_DESIGN_AND_DATA.md) | 소비된 v0.4의 학습 전용 편입, 714회 노출·154 개발셋·해시와 마지막 학습 종료 규칙 |
| v0.2-J 학습 결과·v0.5 규약 | [`training/judgment/V0.2_J_TRAIN_RESULT.md`](training/judgment/V0.2_J_TRAIN_RESULT.md) | 45-step 손실·어댑터 해시, v0.5 단일 실행 절대 기준과 LoRA 종료 조건 |
| v0.2-J·v0.5 최종 결과 | [`training/judgment/V0.2_J_HOLDOUT_V0.5_RESULT.md`](training/judgment/V0.2_J_HOLDOUT_V0.5_RESULT.md) | 단일 실행 수치·실패 유형·미채택 및 LoRA 반복 종료 결정 |
| 결정론적 경계 게이트 v0.1 | [`training/judgment/DETERMINISTIC_BOUNDARY_GATE_V0.1_RESULT.md`](training/judgment/DETERMINISTIC_BOUNDARY_GATE_V0.1_RESULT.md) | 빈 입력·비일본어 사전 라우팅과 STT advisory 분리, D/H replay·운영 미통합 근거 |
| Raspberry Pi 5 병행 배포 | [`deployment/judgment-pi5/README.md`](deployment/judgment-pi5/README.md) | GPU 원본 보존, Q4 기본값·Q5 명시적 후보, Pi preflight, 수동 전환, 멱등 outbox 동기화와 성능 게이트 |
| Pi Q4/Q5 GGUF·dev72 결과 | [`deployment/judgment-pi5/GPU_CONVERSION_AND_DEV72_RESULT.md`](deployment/judgment-pi5/GPU_CONVERSION_AND_DEV72_RESULT.md) | Q4 계약 1건 미달, Q5 구조·GPU 판단 72/72 통과, Pi 성능시험 후보와 해시 |
| 문법 판단 경계 정의 | [`evaluation/judgment/BOUNDARY_GUIDELINES.md`](evaluation/judgment/BOUNDARY_GUIDELINES.md) | 필러·문체·표기·STT·문맥 판단 원칙 |
| 사람 검수 절차 | [`evaluation/judgment/REVIEW_PROCESS.md`](evaluation/judgment/REVIEW_PROCESS.md) | 사용자 검수와 전문가 검수의 구분 및 절차 |
| 최종 검수 기준·주의 사례 | [`evaluation/judgment/FINAL_REVIEW_GUIDE.md`](evaluation/judgment/FINAL_REVIEW_GUIDE.md) | 추측 교정 금지, 번역·복구·스타일 분리 원칙 |
| 72문항 전체 검수 내용 | [`evaluation/judgment/REVIEW.md`](evaluation/judgment/REVIEW.md) | 문항별 원문·판단·교정문 확인 |
| 베이스 모델 비교·최종 후보 선정 | [`evaluation/judgment/FINAL_MODEL_SELECTION.md`](evaluation/judgment/FINAL_MODEL_SELECTION.md) | 11개 모델 평가 기준, 결과와 4B·8B·14B 역할 |
| 검수용 Excel·PDF 안내 | [`evaluation/judgment/review_materials/README.md`](evaluation/judgment/review_materials/README.md) | 검수표와 배포용 검수 문서 설명 |
| 현재 구조와 목표 구조 비교 | [`docs/architecture/SYSTEM_ARCHITECTURE_FUTURE_VS_GITHUB.md`](docs/architecture/SYSTEM_ARCHITECTURE_FUTURE_VS_GITHUB.md) | 운영·평가·검수 경로 분리와 단계별 전환 설계 |

문서 갱신 원칙은 다음과 같습니다.

1. 작업을 완료할 때마다 `PROGRESS.md`의 완료 상태와 다음 단계를 갱신합니다.
2. 평가 데이터·계약·실행 방법이 바뀌면 `evaluation/judgment/README.md`를 함께 갱신합니다.
3. 모델을 추가 실행하거나 후보 판단이 바뀌면 `FINAL_MODEL_SELECTION.md`와 모델별 `results/*.json`을 갱신합니다.
4. 운영 구조·API·DB 경계가 바뀔 때만 아키텍처 Markdown과 PDF를 다시 생성합니다.
5. 이 루트 README에는 최신 요약과 문서 경로만 유지하고, 상세 실험 기록은 각 기준 문서에 남깁니다.

## 역할 요약

- 라즈베리파이: 음성 녹음, 음성 전처리, STT 실행
- `stt_api`: STT 결과 저장, 세션/발화 조회, 전처리 결과 업데이트, 일본어 문장 분석
- 로컬 LLM 서버: 일본어 문장 교정 및 피드백 생성
- SQLite DB: 사용자, 세션, 발화, 분석 결과 저장

## 주요 기능

- 사용자 생성
- 회화 세션 생성
- STT 발화 저장
- 세션별 발화 조회
- 특정 발화 조회
- 텍스트 전처리 결과 업데이트
- 일본어 문장 타입 분류
- RAG 기반 문법/단어/예문/오류 패턴 참고 자료 검색
- 로컬 OpenAI 호환 LLM을 통한 문장 교정
- 분석 결과 저장 및 조회

- 기능 플래그 기반 3단계 판단 실행 및 별도 이력 조회
## 디렉터리 구조

```text
stt_api/
├── main.py                    # FastAPI 앱 진입점 및 API 라우트
├── database.py                # SQLite 연결 및 DB 세션 관리
├── models.py                  # SQLAlchemy ORM 모델
├── schemas.py                 # Pydantic 요청/응답 스키마
├── crud.py                    # DB 생성/조회/수정 로직
├── stt_data.db                # SQLite 데이터베이스
├── requirements.txt           # Python 의존성
├── analyzer/
│   ├── pipeline.py            # 전체 분석 파이프라인
│   ├── rule_filter.py         # 입력 검증 및 정규화
│   ├── sentence_classifier.py # 문장 타입 분류
│   ├── vocab_retriever.py     # 단어 DB 검색
│   ├── grammar_retriever.py   # 문법 규칙 검색
│   ├── error_retriever.py     # 오류 패턴 검색
│   ├── example_retriever.py   # TF-IDF 기반 예문 검색
│   ├── prompt_builder.py      # LLM 프롬프트 생성
│   ├── llm_client.py          # OpenAI 호환 LLM 서버 호출
│   ├── llm_parser.py          # LLM 응답 JSON 파싱 및 후처리
│   ├── judgment_service.py    # D 단독 3단계 판단 호출·계약 검증
│   └── judgment_monitor.py    # 원문 없는 staging 운영 집계
├── rag_data/
│   ├── vocab/
│   │   ├── n5_raw.csv
│   │   └── word_db.json
│   ├── grammar/
│   │   └── grammar_rules.json
│   ├── errors/
│   │   └── error_patterns.json
│   └── examples/
│       ├── texts.json
│       └── tfidf.pkl
└── scripts/
    ├── build_word_db.py       # 단어 DB 생성 스크립트
    └── build_example_tfidf.py # 예문 TF-IDF 인덱스 생성 스크립트
```

## 실행 방법

가상환경이 이미 포함되어 있다면 다음처럼 실행할 수 있습니다.

```bash
cd /home/cap-minsung/stt_api
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

새 환경에서 설치하는 경우:

```bash
cd /home/cap-minsung/stt_api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

서버 실행 후 문서 페이지:

```text
http://localhost:8000/docs
```

## 의존성

주요 의존성은 다음과 같습니다.

- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `pydantic`

분석 파이프라인의 예문 검색에서는 `tfidf.pkl`을 로드합니다. 이 pickle은 생성 당시의 Python/scikit-learn 환경에 의존할 수 있으므로, 환경을 새로 구성할 때 예문 검색 쪽 의존성도 함께 확인해야 합니다.

## API 목록

### 서버 상태 확인

```http
GET /health
```

응답 예:

```json
{
  "status": "ok",
  "message": "STT API server is running"
}
```

### 사용자 생성

```http
POST /users
```

요청 예:

```json
{
  "name": "minsung",
  "level": "N5"
}
```

응답에는 `user_id`, `name`, `level`, `created_at`이 포함됩니다.

### 회화 세션 생성

```http
POST /sessions
```

요청 예:

```json
{
  "user_id": 1,
  "topic": "일상 대화",
  "description": "라즈베리파이 기반 일본어 STT 테스트 세션"
}
```

### 사용자별 세션 목록 조회

```http
GET /users/{user_id}/sessions
```

특정 사용자의 회화 세션 목록을 반환합니다.

### STT 발화 저장

```http
POST /utterances
```

요청 예:

```json
{
  "session_id": 1,
  "raw_audio_path": "/home/pi/audio/raw/utt_001.wav",
  "audio_path": "/home/pi/audio/processed/utt_001.wav",
  "stt_text": "今日学校行きました",
  "language": "ja",
  "duration": 3.42,
  "stt_model": "faster-whisper-small",
  "preprocess_status": "done",
  "sample_rate": 16000,
  "channels": 1,
  "audio_format": "wav"
}
```

이 API는 음성 인식을 수행하지 않습니다. 이미 생성된 STT 결과인 `stt_text`와 관련 메타데이터를 저장합니다.

### 특정 발화 조회

```http
GET /utterances/{utterance_id}
```

특정 발화의 STT 원문, 전처리 텍스트, 토큰, 오디오 경로, 모델 정보 등을 조회합니다.

### 세션별 발화 목록 조회

```http
GET /sessions/{session_id}/utterances
```

특정 세션에 속한 모든 발화를 반환합니다.

### 텍스트 전처리 결과 업데이트

```http
PATCH /utterances/{utterance_id}/preprocess
```

요청 예:

```json
{
  "processed_text": "今日 学校 行きました",
  "normalized_text": "今日学校行きました",
  "tokens": ["今日", "学校", "行きました"]
}
```

`tokens`는 DB에는 JSON 문자열 형태로 저장됩니다.

### 발화 분석 실행

```http
POST /utterances/{utterance_id}/analyze
```

분석 대상 텍스트는 다음 우선순위로 선택됩니다.

1. `processed_text`
2. `normalized_text`
3. `stt_text`

분석 결과는 `analyses` 테이블에 저장되고, 저장된 분석 객체가 응답으로 반환됩니다.

### 발화 분석 결과 조회

```http
GET /utterances/{utterance_id}/analysis
```

특정 발화에 대해 수행된 분석 결과 목록을 최신순으로 반환합니다.

### 판단모델 staging 상태 조회

```http
GET /health/judgment
```

프로세스 시작 이후의 요청·성공·실패·재시도·결정 분포와 최근 1,000건의 p50/p95 지연시간을 반환합니다. 원문, 발화 ID, 문맥, 원시 모델 응답과 오류 메시지는 기록하거나 반환하지 않습니다. 이 집계는 프로세스 로컬 메모리이며 재시작 시 초기화되므로 영구 감사 로그를 대신하지 않습니다.

### 발화 판단모델 실행

```http
POST /utterances/{utterance_id}/judgment
```

선택 요청 본문:

```json
{
  "context": "어제 무엇을 했는지 답하는 상황",
  "learner_level": "N5"
}
```

- 판단은 `acceptable`, `needs_correction`, `insufficient_evidence` 중 하나입니다.
- 수준은 요청값, 연결된 사용자의 `N5`/`N4`, 기본 `N5` 순서로 정합니다.
- 모델은 위치 없는 v0.2 계약을 생성하고, `edits`의 Unicode 위치는 백엔드가 원문과 교정문의 diff로 계산합니다.
- 결과는 기존 `analyses`와 분리된 `judgment_results`에 저장합니다.
- `confidence`는 생성하거나 저장하지 않습니다.
- 기능 플래그 비활성, 모델 연결 실패, 출력 계약 위반은 HTTP 503입니다.

판단 기능은 기본 비활성입니다. 라이브 모델 검증 시 다음 환경 변수를 설정합니다.

```bash
export JUDGMENT_ENABLED=true
export JUDGMENT_ENDPOINT=http://127.0.0.1:1234/v1/chat/completions
export JUDGMENT_MODEL=judgment-v02d
export JUDGMENT_ADAPTER=judgment-qwen3-4b-failure-focus-v0.2-d
export JUDGMENT_TIMEOUT_SECONDS=120
```

원본 DB를 직접 사용하지 않는 전체 실행 순서와 사전점검은 [판단모델 staging 실행 가이드](docs/JUDGMENT_STAGING_RUNBOOK.md)를 따릅니다.

### 발화 판단 결과 조회

```http
GET /utterances/{utterance_id}/judgments
```

특정 발화의 판단 결과를 최신순으로 반환합니다.

### Pi 오프라인 이벤트 동기화

```http
POST /edge/v1/sync
Authorization: Bearer <EDGE_SYNC_TOKEN>
```

이 private endpoint는 기본 비활성이고 `EDGE_SYNC_ENABLED=true`일 때만 사용합니다. Pi가 생성한 세션→발화→판단 UUID 이벤트를 최대 100개까지 순서대로 받으며, `(node_id, event_id)`와 payload SHA-256으로 재전송을 멱등 처리합니다. 같은 UUID의 내용이 바뀌면 HTTP 409, 인증 실패는 401, 기능 비활성은 503입니다. Pi 로컬 오디오 경로나 파일은 받지 않습니다. 공용 인터넷에 직접 노출하지 말고 private network/VPN과 호스트 방화벽을 사용합니다.

전체 설치·전환·복구 절차는 [Raspberry Pi 5 병행 배포 가이드](deployment/judgment-pi5/README.md)를 따릅니다.

## 데이터베이스 구조

SQLite DB 파일은 다음 경로를 사용합니다.

```text
stt_api/stt_data.db
```

기본 연결은 `sqlite:///./stt_data.db`이며, Pi 분리 DB에서는 `STT_DATABASE_URL` 환경 변수로 덮어씁니다.

### `users`

사용자 정보를 저장합니다.

| 컬럼 | 설명 |
| --- | --- |
| `id` | 사용자 ID |
| `name` | 사용자 이름 |
| `level` | 일본어 레벨 |
| `created_at` | 생성 시각 |

### `sessions`

회화 세션 정보를 저장합니다.

| 컬럼 | 설명 |
| --- | --- |
| `id` | 세션 ID |
| `user_id` | 사용자 ID |
| `topic` | 세션 주제 |
| `description` | 세션 설명 |
| `created_at` | 생성 시각 |

### `utterances`

STT 발화 데이터를 저장합니다.

| 컬럼 | 설명 |
| --- | --- |
| `id` | 발화 ID |
| `session_id` | 세션 ID |
| `raw_audio_path` | 원본 오디오 경로 |
| `audio_path` | 전처리된 오디오 경로 |
| `stt_text` | STT 결과 텍스트 |
| `processed_text` | 전처리된 텍스트 |
| `normalized_text` | 정규화된 텍스트 |
| `tokens` | 토큰 목록을 JSON 문자열로 저장 |
| `language` | 언어 코드, 기본값 `ja` |
| `duration` | 오디오 길이 |
| `stt_model` | STT 모델명 |
| `preprocess_status` | 전처리 상태 |
| `sample_rate` | 샘플레이트 |
| `channels` | 채널 수 |
| `audio_format` | 오디오 포맷 |
| `created_at` | 생성 시각 |
| `updated_at` | 수정 시각 |

### `analyses`

문장 분석 및 교정 결과를 저장합니다.

| 컬럼 | 설명 |
| --- | --- |
| `id` | 분석 ID |
| `utterance_id` | 발화 ID |
| `primary_type` | 대표 문장 타입 |
| `candidate_types` | 후보 문장 타입 목록 |
| `classification_reason` | 분류 이유 |
| `needs_deep_analysis` | LLM 분석 필요 여부 |
| `is_correct` | 문장이 자연스러운지 여부 |
| `corrected_text` | 교정 문장 |
| `error_types` | 오류 유형 목록 |
| `feedback_ko` | 한국어 피드백 |
| `feedback_ja` | 일본어 피드백 |
| `vocab_context` | 단어 RAG 문맥 |
| `grammar_context` | 문법 RAG 문맥 |
| `example_context` | 예문 RAG 문맥 |
| `error_context` | 오류 패턴 RAG 문맥 |
| `model_name` | 분석에 사용된 LLM 모델명 |
| `adapter_name` | 어댑터명 |
| `confidence` | 신뢰도 |
| `created_at` | 생성 시각 |
### `judgment_results`

3단계 판단 결과를 기존 이진 분석 결과와 분리해 저장합니다.

| 컬럼 | 설명 |
| --- | --- |
| `id`, `utterance_id` | 판단 결과 ID와 대상 발화 ID |
| `decision` | `acceptable`, `needs_correction`, `insufficient_evidence` |
| `corrected_text` | 최소 교정문 또는 계약상 유지된 원문 |
| `edits`, `error_types` | 백엔드 diff와 오류 유형을 JSON 문자열로 저장 |
| `reason_ko` | 한국어 판단 근거 |
| `classification_review_required` | diff와 오류 분류 불일치 검토 표시 |
| `strategy` | 현재 `d_only` |
| `model_name`, `adapter_name` | 사용 모델 alias와 D 어댑터 |
| `selection_reason` | D 선택 근거 식별자 |
| `contract_version` | 출력 계약 버전 |
| `latency_ms` | 모델 요청 지연시간 |

### Edge 동기화 테이블

- `edge_entity_identities`, `edge_outbox_events`: `EDGE_MODE=true`인 Pi 로컬 DB에만 생성합니다.
- `edge_sync_receipts`: `EDGE_SYNC_ENABLED=true`인 GPU DB에만 생성하며 멱등 수신과 원격 ID·GGUF provenance를 기록합니다.
- 두 플래그가 모두 꺼진 기존 GPU API startup에서는 Edge 테이블을 만들지 않습니다.
| `context`, `learner_level` | 요청 문맥과 적용 학습 수준 |
| `created_at` | 생성 시각 |


## 분석 파이프라인

분석의 중심 함수는 `analyzer/pipeline.py`의 `analyze(text)`입니다.

### 1. 입력 검증

`analyzer/rule_filter.py`에서 입력을 정규화하고 분석 가능 여부를 판단합니다.

검증 내용:

- 빈 문자열 여부
- 일본어 문자 포함 여부
- 한국어/영어만 있는 입력 여부
- 너무 짧은 STT 실패성 입력 여부

일본어 문자는 히라가나, 가타카나, 한자 범위를 기준으로 확인합니다.

### 2. 문장 타입 분류

`analyzer/sentence_classifier.py`에서 문장 타입 후보를 추출하고 대표 타입을 선택합니다.

지원 타입:

- `invalid`
- `question`
- `request`
- `greeting`
- `emotion`
- `statement`
- `fragment`

예를 들어 `こんにちは`, `おはよう`, `ありがとう` 같은 패턴은 `greeting`으로 분류됩니다.

### 3. 조기 반환

다음 타입은 LLM을 호출하지 않고 룰 기반 결과를 바로 반환합니다.

- `invalid`: 일본어 문장으로 판단하기 어려움
- `greeting`: 자연스러운 인사 표현
- `fragment`: 단어 또는 짧은 발화

이 구조는 불필요한 LLM 호출과 과교정을 줄이기 위한 장치입니다.

### 4. RAG 참고 자료 검색

일반 문장으로 판단되면 다음 참고 자료를 검색합니다.

- `vocab_retriever.py`: 입력 문장에 포함된 단어 검색
- `grammar_retriever.py`: 문법 규칙 검색
- `error_retriever.py`: 오류 패턴 검색
- `example_retriever.py`: TF-IDF 기반 유사 예문 검색

이 검색 결과들은 오류 확정이 아니라 LLM이 판단할 때 참고하는 문맥입니다.

### 5. 프롬프트 생성

`analyzer/prompt_builder.py`에서 입력 문장, 문장 타입, RAG 문맥을 합쳐 LLM 프롬프트를 생성합니다.

프롬프트는 다음 원칙을 강조합니다.

- 자연스러운 일본어인지 판단
- 의미를 바꾸지 않는 최소 교정
- 정상 문장, 인사 표현, 단편 발화 과교정 방지
- 오류 유형은 제공된 코드 안에서만 선택
- JSON만 반환

### 6. LLM 호출

`analyzer/llm_client.py`는 OpenAI 호환 Chat Completions API를 호출합니다.

기본 설정:

```text
endpoint: http://localhost:1234/v1/chat/completions
model: qwen/qwen3-4b-2507
temperature: 0.2
max_tokens: 512
timeout: 120
```

따라서 분석 API를 정상적으로 사용하려면 로컬 또는 같은 서버에서 OpenAI 호환 LLM 서버가 `localhost:1234`로 실행 중이어야 합니다.

### 7. LLM 응답 파싱 및 후처리

`analyzer/llm_parser.py`가 LLM 응답을 JSON으로 파싱하고 결과를 보정합니다.

처리 내용:

- 코드블록으로 감싸진 JSON 제거
- 앞뒤 설명문이 섞인 응답에서 JSON 객체 추출
- `is_correct`, `confidence`, `error_types` 타입 보정
- 원문과 교정문이 같으면 오류 유형 제거
- 원문과 교정문이 다르면 `is_correct = false`로 보정
- 일부 대표 패턴의 오류 유형 재분류

후처리에서 다루는 대표 오류 유형:

- `particle_omission`
- `particle_misuse`
- `verb_conjugation_error`
- `tense_error`
- `word_choice_error`
- `unnatural_expression`
- `overcorrection_risk`
- `non_japanese_input`
- `fragment`

## RAG 데이터

### 단어 데이터

```text
rag_data/vocab/word_db.json
rag_data/vocab/n5_raw.csv
```

입력 문장에 포함된 단어의 표기, 읽기, 의미, JLPT 레벨을 참고 자료로 제공합니다.

### 문법 규칙

```text
rag_data/grammar/grammar_rules.json
```

입력 문장과 관련 있을 수 있는 문법 규칙을 검색합니다. 이 결과는 교정 지시가 아니라 판단 참고 자료입니다.

### 오류 패턴

```text
rag_data/errors/error_patterns.json
```

가능한 오류 유형을 판단하기 위한 참고 자료입니다. 실제 오류 확정은 LLM과 후처리 단계에서 이루어집니다.

### 예문 검색

```text
rag_data/examples/texts.json
rag_data/examples/tfidf.pkl
```

TF-IDF cosine similarity 기반으로 입력 문장과 유사한 예문을 검색합니다.

## 일반 요청 흐름

라즈베리파이 또는 클라이언트가 사용할 때의 일반적인 흐름은 다음과 같습니다.

1. `POST /users`로 사용자 생성
2. `POST /sessions`로 회화 세션 생성
3. 라즈베리파이에서 음성 녹음 및 STT 실행
4. `POST /utterances`로 STT 결과 저장
5. 필요 시 `PATCH /utterances/{utterance_id}/preprocess`로 전처리 결과 저장
6. `POST /utterances/{utterance_id}/analyze`로 일본어 문장 분석 실행
7. `GET /utterances/{utterance_id}/analysis`로 분석 결과 조회

## 분석 결과 예시

분석 결과는 대략 다음 형태로 저장됩니다.

```json
{
  "id": 1,
  "utterance_id": 10,
  "primary_type": "statement",
  "candidate_types": "[{\"type\": \"statement\", \"score\": 0.7}]",
  "classification_reason": "후보 타입 statement 중 대표 타입을 statement으로 선택함",
  "needs_deep_analysis": true,
  "is_correct": false,
  "corrected_text": "今日学校に行きました",
  "error_types": "[\"particle_omission\"]",
  "feedback_ko": "문장에서 필요한 조사가 생략된 부분이 있어 문장 구조가 부자연스러웠습니다.",
  "feedback_ja": "文の中で必要な助詞が省略されている部分があり、文の構造が不自然でした。",
  "model_name": "qwen/qwen3-4b-2507",
  "adapter_name": null,
  "confidence": 0.85,
  "created_at": "2026-06-09T06:18:58"
}
```

## 현재 DB 상태 확인 예시

SQLite CLI로 테이블과 데이터 수를 확인할 수 있습니다.

```bash
cd /home/cap-minsung/stt_api
sqlite3 stt_data.db ".tables"
sqlite3 stt_data.db "select count(*) from utterances;"
sqlite3 stt_data.db "select count(*) from analyses;"
```

## 주의사항

- 이 서버는 실제 STT 추론을 수행하지 않습니다.
- `POST /utterances`는 이미 만들어진 STT 텍스트를 저장하는 API입니다.
- `POST /utterances/{utterance_id}/analyze`를 사용하려면 `localhost:1234`의 OpenAI 호환 LLM 서버가 필요합니다.
- `candidate_types`, `error_types`, `tokens` 등 일부 목록 데이터는 SQLite에는 JSON 문자열로 저장됩니다.
- `models.Base.metadata.create_all(bind=engine)`가 앱 시작 시 실행되므로, 없는 테이블은 자동 생성됩니다. 단, 기존 테이블 스키마 변경 마이그레이션은 처리하지 않습니다.
- 외래키 관계는 모델에 정의되어 있지만 SQLite에서 엄격한 무결성 검증을 기대하려면 별도 설정이 필요할 수 있습니다.
- `rag_data/examples/tfidf.pkl`은 pickle 파일이므로 생성 환경과 실행 환경의 패키지 호환성을 확인해야 합니다.

## 개발 메모

- API 라우트는 `main.py`에 집중되어 있어 구조가 단순합니다.
- DB 접근은 `crud.py`를 통해 수행합니다.
- 분석 로직은 `analyzer/pipeline.py`에서 계층적으로 연결됩니다.
- RAG 검색 함수들은 교정을 직접 수행하지 않고, LLM 판단을 돕는 참고 문맥만 생성합니다.
- LLM 응답이 실패하거나 JSON 파싱에 실패해도 서버가 죽지 않도록 fallback 결과를 반환하는 구조입니다.
