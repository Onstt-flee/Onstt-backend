# 판단모델 무권한 staging 서비스 검증 결과

- 상태: **사용자 systemd 설치·실기동·장애 복구·합성 판단 검증 완료, 운영·학습자 노출 미승인**
- 일시: 2026-10-08 UTC
- 범위: Qwen3-4B + v0.2-D, 단일 GPU 서버, 사용자 로그인 세션의 제한적 staging

## 구성

관리자 권한이 없으므로 root system unit은 템플릿으로만 보존하고, 다음 사용자 unit을 추가했다.

- `deployment/judgment-staging/user/judgment-vllm.service`
- `deployment/judgment-staging/user/stt-api-judgment-staging.service`
- `scripts/install_judgment_user_services.sh`
- `scripts/check_judgment_user_staging.sh`

설치기는 기존 private 환경과 staging DB를 덮어쓰지 않으며 서비스를 시작하거나 enable하지 않는다. 두 unit에는 `[Install]` 섹션이 없다. 모델과 API는 loopback `1234`, `8001`에만 bind하고 API는 Uvicorn worker 1개, 프로세스 로컬 동시 판단 2개로 고정했다.

## 설치와 live 사전점검

사용자 systemd manager는 `running`이었고 `Linger=no`였다. 사용자 설정·state 디렉터리에 다음 권한으로 설치했다.

- private 환경: `0600`, 초기 및 최종 `JUDGMENT_ENABLED=false`
- 격리 DB: `0600`
- user unit: `0644`, `static`, 자동 시작 없음

격리 DB 최초 SHA-256은 원본과 동일했다. private 환경을 staging에 한해 임시 활성화한 뒤 vLLM과 API를 수동 시작했다. 모델 목록에서 `judgment-v02d` alias를 확인했고 API `ExecStartPre`, `/health`, `/ready/judgment`, 필수 OpenAPI 경로와 읽기 전용 live 사전점검이 모두 통과했다.

첫 수동 사전점검은 실행 셸이 private 환경을 로드하지 않아 의도대로 실패했다. 서비스 설정 실패는 아니었다. 운영자 오류를 줄이기 위해 private 환경을 로드하는 `scripts/check_judgment_user_staging.sh`를 추가했고 이 경로는 `passed: true`였다.

## 장애 복구

vLLM만 중단했을 때 API 서비스는 `active`를 유지했고 `/ready/judgment`는 HTTP 503, `reason=model_unavailable`을 반환했다. 같은 user unit으로 모델을 재기동하자 API 재시작 없이 readiness가 HTTP 200, `reason=ready`로 자동 회복했다.

강한 `Requires` 종속성을 두지 않은 이유는 모델 장애 중에도 API가 readiness 실패를 제공하고 자동 회복을 관찰할 수 있게 하기 위해서다.

## 합성 판단 1건

격리 DB에 실제 사용자 내용과 구분되는 합성 발화 `明日は学校を行きます。` 한 건을 추가했다.

- POST: HTTP 200
- 판단: `needs_correction`
- 교정: `明日は学校に行きます。`
- 전략·계약: `d_only`, `judgment-v0.2`
- edit: 1개
- 모델 경로 지연시간: 840.146ms
- HTTP wall time: 875.713ms
- GET: HTTP 200, 저장 결과 1건
- monitor: 요청·모델 호출·성공 각 1, 실패·재시도 0, 요청 내용 비포함

이는 프로세스·저장 계약 확인용 합성 사례이며 일본어 품질 평가나 실제 STT·발음 성능 근거가 아니다.

## 종료와 복원

API와 모델 user service를 순서대로 중단했고 둘 다 `inactive`다. private 환경은 `JUDGMENT_ENABLED=false`로 복원했다. 합성 행이 기록된 격리 DB는 원본 snapshot으로 교체했다.

- 원본과 격리 DB SHA-256: `ef3b42b92516c5332f2ed1dcd63ffe1a9c2ff8a53650c24a32205a0161ff09c9`
- 격리 DB `judgment_results`: 0
- 8001/1234 listener: 없음
- 남은 GPU compute process: 없음
- 임시 readiness·합성 응답 파일 4개: 삭제

## 한계

`Linger=no`이므로 사용자 서비스는 로그아웃 후 상시 운영을 보장하지 않는다. 관리자 권한 없는 현재 조건에서는 로그인 세션 기반 staging 검증까지만 승인할 수 있다. 다중 worker·replica, 외부 프록시·인증, 재부팅 자동 복구와 장시간 soak를 증명하지 않는다. 자동 부팅과 학습자 노출은 계속 금지하며 `holdout_v0.4`는 추론 0회로 유지한다.

## 무권한 수명주기 관리기

수동 환경 편집과 셸 export 누락을 제거하기 위해 `scripts/manage_judgment_user_staging.py`를 추가했다.

- `start`: private 환경을 원자적으로 true로 바꾸고 모델 health·고정 alias 확인 후 API를 시작한다. 마지막으로 모델/API health, readiness와 OpenAPI 판단 경로 전체 사전점검을 통과해야 성공한다.
- `status`: 환경 활성 여부, 격리 DB 존재 여부와 두 서비스 상태만 반환하며 요청 내용을 포함하지 않는다.
- `stop`: API→모델 순서로 중단하고 private 환경을 원자적으로 false로 되돌린다.
- 시작 중 어느 단계라도 실패하면 API·모델을 모두 중단하고 환경을 false로 rollback한다.
- private 환경이 symlink, 현재 사용자 소유가 아님, group/other 접근 권한이 있음, 활성 키가 중복·비정상이면 실행을 거부한다.

실제 사용자 서비스에서 관리기 `start --timeout 180`은 두 서비스 `active`, 환경 true, `live_preflight_passed=true`를 반환했다. 이어 `status`가 같은 상태를 확인했고 `stop`은 두 서비스 inactive·환경 false·오류 0건으로 종료했다. 이 검증 중 모델 판단 요청과 DB 쓰기는 수행하지 않았으며 원본·격리 DB 해시와 판단 결과 0건이 유지됐다.
