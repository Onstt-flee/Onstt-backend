# feedback-v0.3 커밋 전 체크포인트 감사

감사일: 2026-10-15
상태: **통과, 스테이징·커밋·푸시 미실행**

## 범위 분리

전용 감사 실행 시 변경 54개를 다음과 같이 분류했다.

- feedback-v0.3 체크포인트 후보: 50개
- Pi 후속 작업으로 보류: 4개
- 분류되지 않은 변경: 0개

보류 파일:

- `deployment/feedback-staging/finalize-runtime-pairs.sh`
- `deployment/judgment-pi5/run-feedback-pairs-50.sh`
- `evaluation/feedback/RUNTIME_PAIR_INTAKE.md`
- `tests/test_pi5_deployment_templates.py`

이 4개는 삭제하지 않고 작업 트리에 그대로 두되 feedback-v0.3 체크포인트에는 포함하지 않는다.

## 안전 검사

| 검사 | 결과 |
| --- | ---: |
| 이미 스테이징된 파일 | 0 |
| 금지된 DB·가중치·오디오·원시 run 경로 | 0 |
| 10MiB 초과 변경 파일 | 0 |
| 대표 private key·AWS·GitHub·Hugging Face 토큰 패턴 | 0 |
| 핵심 내부 해시 불일치 | 0 |
| 외부 어댑터·원시 run·격리 DB 해시 불일치 | 0 |
| private artifact Git ignore 누락 | 0 |

기존 전체 저장소 체크포인트 감사도 통과했고 보호 대상 `stt_data.db`와 판단
`holdout_v0.4` 해시는 유지됐다.

## 고정된 핵심 외부 산출물

- feedback-v0.3 adapter:
  `3bcbc80d1559dacf60a84c708a8ab4c51ee4bd33532acf2ab134394aa2dcd1ad`
- holdout v0.4 raw run:
  `6d3fe9032251403e05d2c8ab970ee7bd7f1ddb11c6f9c5d2afa9e1aeab4abf32`
- synthetic judgment raw run:
  `d2a581992f4efb1a7129883a5c220dac3d7e69bdab8728c565e53fe5c296106c`
- synthetic isolated SQLite:
  `e3f6e1090fbf8b29927647344adad2e143e07576aced7c26daf8f5e25d5f7ec1`

가중치, 원시 모델 출력과 SQLite는 Git 밖에 유지하며 추적 파일에는 해시와 내용 없는
집계만 둔다.

## 다음 작업

현재 상태는 커밋 준비가 가능하지만 사용자 지시에 따라 커밋하지 않는다. 커밋할 때는
전용 감사의 `checkpoint_paths`만 명시적으로 추가하고 Pi 보류 4개가 staged 목록에 없는지
재검사해야 한다.
