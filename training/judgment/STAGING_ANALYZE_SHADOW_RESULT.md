# 기존 `/analyze` 판단모델 shadow 통합 결과

- 상태: **응답 비간섭·판단 무저장 shadow 실기동 통과, 학습자 노출 미승인**
- 일시: 2026-10-08 KST
- 모델: Qwen3-4B + `judgment-qwen3-4b-failure-focus-v0.2-d`
- 실행: sudo 없는 사용자 systemd, FastAPI 1 worker, 동시 판단 상한 2

## 구현 경계

별도 `JUDGMENT_SHADOW_ENABLED=false` 플래그를 추가했다. shadow는 `JUDGMENT_ENABLED`와 shadow 플래그가 모두 true일 때만 기존 `POST /utterances/{id}/analyze` 응답이 완성된 뒤 FastAPI background task로 예약된다.

- 기존 분석 결과와 `analyses` 저장 계약은 유지한다.
- 판단 결과는 `judgment_results`에 저장하지 않는다.
- shadow 성공·실패는 기존 공개 판단 요청 통계와 분리된 익명 집계에만 기록한다.
- 모델 오류, 계약 오류, 과부하, 종료 중 상태와 설정 오류는 `/analyze` 응답을 실패시키지 않는다.
- shadow는 공개 교정문·판단·근거를 `/analyze` 응답에 추가하지 않는다.
- 직접 판단 API와 shadow는 같은 프로세스 로컬 용량 제한을 공유한다.

`GET /health/judgment` 계약은 `judgment-monitor-v0.2`로 올리고 `shadow` 하위 집계를 추가했다. 원문·발화 ID·문맥·교정문·원시 오류는 집계하지 않는다.

## live 검증

기존 분석기의 외부 LLM alias 변수를 배제하기 위해 규칙 기반으로 처리되는 합성 발화 `おはようございます！`를 격리 DB에 넣었다. 사용자 관리기를 `start --shadow --timeout 180`으로 실행했고 모델 alias·API·OpenAPI 전체 live 사전점검이 통과했다.

`POST /utterances/900000002/analyze` 결과:

- HTTP: 200
- 응답 wall time: 34.087ms
- 기존 결과: `primary_type=greeting`, `is_correct=true`, 원문 유지
- judgment 전용 `decision`, `strategy`, `contract_version`, `edits`, `reason_ko`: 모두 응답에 없음

background shadow 결과:

- 예약·모델 호출·성공: 각각 1건
- 실패·재시도: 0건
- 판단 분포: `acceptable` 1건
- 모델 지연시간 p95: 742.162ms
- `persists_results=false`
- `affects_analyze_response=false`
- `contains_request_content=false`
- `judgment_results`: 0건

`/analyze`의 기존 `analyses` 행 1건은 정상적으로 생성됐다. 이 결과는 합성 인사 한 건의 배선·격리 검증이며 일반 문장 품질·실제 사용자 트래픽·발음 성능 근거가 아니다.

## 종료와 복원

관리기 `stop`으로 API→모델 순서로 중단했고 두 기능 플래그를 false로 복원했다. 합성 데이터가 있던 격리 DB는 원본 snapshot으로 교체했다.

- 사용자 모델/API 서비스: inactive
- 원본·격리 DB SHA-256: `ef3b42b92516c5332f2ed1dcd63ffe1a9c2ff8a53650c24a32205a0161ff09c9`
- 양쪽 `judgment_results`: 0
- 합성 사용자: 0
- 8001/1234 listener와 GPU process: 없음
- 임시 응답·모니터 파일 2개: 삭제

기능 플래그 기본 비활성, 학습자 노출 미승인, 사람·음성 검수 보류와 `holdout_v0.4` 추론 0회를 유지한다.
