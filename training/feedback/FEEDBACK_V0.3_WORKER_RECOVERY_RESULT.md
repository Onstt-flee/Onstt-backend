# feedback-v0.3 worker 장애 복구 훈련 결과

실행일: 2026-10-15
범위: 합성 200건 SQLite의 격리 복사본
판정: **lease 회수·재시도·terminal 격리 통과**

## 시나리오별 결과

| 시나리오 | 최종 상태 | 시도 | audit |
| --- | --- | ---: | ---: |
| 실행 중 worker 종료 후 만료된 lease | `succeeded` | 1 | 1 |
| 최초 계약 실패 후 다음 worker 재시작에서 성공 | `succeeded` | 2 | 1 |
| 전송 실패 반복 | `failed` | 3 | 0 |

- 각 `process_one` 호출은 새 DB session으로 실행해 worker 프로세스 재시작 경계를 모사했다.
- 3개의 훈련 job이 추가됐고 성공 2건만 audit으로 저장됐다.
- 훈련 audit 중복은 0건이다.
- terminal 실패는 내용 없는 `transport` 범주만 남겼다.
- 판단 snapshot 전후 SHA-256은
  `862aa09a18ba24bd227a6e4d588f37e89485f98cb8cf84c46ca50ab9540e2d47`로 같다.
- 원본 합성 DB는 변경하지 않았고 훈련은 별도 복사본에서만 수행했다.

## 산출물

- 원본 DB SHA-256:
  `e3f6e1090fbf8b29927647344adad2e143e07576aced7c26daf8f5e25d5f7ec1`
- 훈련용 DB SHA-256:
  `152256694a147861bef5cb91d4fb6c78cc7570ab32c07bde08f420ef157b93ce`
- 추적 결과에는 입력 문장·판단·추천문을 포함하지 않는다.

## 제한

이번 훈련은 queue 상태 전이와 DB 무결성 검증이다. 실제 프로세스 강제 종료나 네트워크
장애 시간을 재현한 부하 시험은 아니며 언어 품질 근거도 아니다. 기능 플래그 기본 비활성,
학습자 노출 금지와 실제 데이터 shadow 보류 상태는 유지한다.
