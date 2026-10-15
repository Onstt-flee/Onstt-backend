# feedback-v0.3 worker 프로세스 강제 종료 복구 결과

실행일: 2026-10-15
범위: 합성 SQLite 복사본, 실제 별도 worker 프로세스, 로컬 stub 서버
판정: **프로세스 종료 후 lease 기반 정확히 한 번 저장 통과**

## 실행 결과

1. 실제 `scripts/run_feedback_worker.py` 프로세스가 피드백 HTTP 요청을 시작할 때까지 기다렸다.
2. 요청 처리 중 첫 worker를 `SIGKILL`로 종료했다.
3. 작업은 `running`, `attempts=1`, lease 보유 상태로 DB에 남았다.
4. 훈련용 DB에서 lease를 만료시킨 후 새 worker 프로세스를 시작했다.
5. 새 worker가 같은 작업을 회수해 `attempts=2`, `succeeded`로 완료했다.

| 항목 | 결과 |
| --- | ---: |
| 첫 worker 종료 코드 | -9 |
| 재기동 worker 종료 코드 | -15 |
| stub HTTP 요청 | 2 |
| 최종 audit | 1 |
| 중복 audit | 0 |
| 기존 판단 변경 | 0 |
| 원본 DB 변경 | 0 |

판단 snapshot 전후 SHA-256은
`862aa09a18ba24bd227a6e4d588f37e89485f98cb8cf84c46ca50ab9540e2d47`로 같다.
원본 DB SHA-256은 전후 모두
`e3f6e1090fbf8b29927647344adad2e143e07576aced7c26daf8f5e25d5f7ec1`이다.

## 실행 중 발견·수정한 결함

systemd 템플릿은 worker를 `python scripts/run_feedback_worker.py`로 실행한다. 기존 진입점은
프로젝트 루트를 `sys.path`에 추가하지 않아 이 방식에서 `ModuleNotFoundError: database`로
즉시 종료됐다. 진입점이 자신의 상위 프로젝트 경로를 명시적으로 추가하도록 수정했고,
`/tmp` 작업 디렉터리에서 직접 실행하는 회귀 테스트를 추가했다.

## 제한

- 실제 Qwen 피드백모델 대신 계약이 같은 로컬 stub 응답을 사용했다.
- 기본 lease 180초를 기다리지 않고 훈련용 DB에서 만료 시각을 앞당겼다.
- 운영 DB·systemd 서비스·사용자 데이터는 사용하지 않았다.
- 이는 프로세스·queue 내구성 근거이며 언어 품질이나 운영 승인 근거가 아니다.
