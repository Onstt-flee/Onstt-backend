# feedback two-stage v0.1 계약 설계

기준일: 2026-10-18

## 목표

피드백 검수의 두 역할을 분리한다.

1. stage 1은 제출된 판단의 `agree / disagree / unreviewable`과 문제 유형만 결정한다.
2. stage 2는 유효한 `disagree`일 때만 권장 판단과 최소 교정문을 생성한다.

기존 판단 결과를 덮어쓰지 않는 비동기 감사 구조와 저장 스키마는 유지한다. 이 설계는
오프라인 계약 구현이며 worker, DB, 공개 API, 기능 플래그에는 아직 연결하지 않는다.

## stage 1 계약

```json
{
  "verdict": "agree | disagree | unreviewable",
  "issue_codes": [],
  "review_reason_ko": "검수 근거"
}
```

- agree와 unreviewable은 `issue_codes=[]`
- disagree는 한 개 이상의 허용 issue code 필수
- 권장 판단, 교정문, confidence, edit 위치, 추가 필드 금지
- temperature 0, top-p 1, 최대 192토큰

## stage 2 계약

```json
{
  "decision": "acceptable | needs_correction | insufficient_evidence",
  "corrected_text": "원문 또는 최소 교정문",
  "error_types": [],
  "reason_ko": "권장 판단 근거"
}
```

- 유효한 stage 1 disagree 이후에만 호출
- false negative, false positive, should abstain, unnecessary abstention의 decision 의미 규칙 유지
- 비교정 판단은 원문 보존, 교정 판단은 변경된 최소 교정과 오류 유형 필수
- edit 위치는 백엔드가 결정론적으로 계산
- temperature 0, top-p 1, 최대 384토큰

## 결합과 기존 호환성

두 결과는 기존 `feedback-v0.1` 저장 형태로 결합한다.

```json
{
  "verdict": "disagree",
  "issue_codes": ["false_negative"],
  "recommended_judgment": {},
  "review_reason_ko": "검수 근거"
}
```

agree와 unreviewable은 stage 2를 호출하지 않고 `recommended_judgment=null`을 유지한다.
따라서 기존 `feedback_audits` 저장 구조를 바꾸지 않고 실험할 수 있다.

## 안전 경계

- 모델 추론: 아직 0회
- 운영·shadow worker 연결: 안 함
- holdout v0.7 결과 노출: 안 함
- `feedback-verifier-v0.3` 관리자 shadow 정책: 변경 없음
- 승인 피드백모델: 없음
- v0.7 실행 전 후보 모델명·어댑터·프롬프트·실행기·채점기 해시를 추가 고정해야 함

## 오프라인 실행기와 채점기

- 실행기는 stage 1을 항상 한 번 호출하고, 계약을 통과한 `disagree`에만 stage 2를 정확히
  한 번 호출한다. stage 1 계약 실패 시 stage 2를 호출하지 않고 fail-closed한다.
- 실행 전 별도 execution plan의 후보 모델·어댑터 해시, 코드 해시, 단일 실행·미소비
  상태를 검사한다. 선봉인 protocol 자체는 수정하지 않는다.
- 채점기는 ID 집합의 완전 일치, 단계별 계약 성공률, 허위 불일치, 불일치 정밀도·재현율,
  stage 2 호출 규율, 권장 decision·허용 교정문과 조건부 총 p95를 계산한다.
- 원시 출력은 Git 제외 경로에만 두며 결과 파일 덮어쓰기를 거부한다.

고정된 구현 SHA-256:

| 구현 | SHA-256 |
| --- | --- |
| 계약 | `d9e5e4d1c7faa4a032f9f0b5073552f088f34dab00083be31160b5062ce20e68` |
| 실행기 | `d11efec2d5f370570f2fb4299227e851c759326db9e09ad94283f4f1190fc3af` |
| 채점기 | `845fd2706984e357f11c2e954a23246bbfa6d96ca3cb6c5febd57d6856fc4bda` |

구현과 단일 실행 결과는 전체 414개 회귀 테스트와 두 환경 `pip check`를 통과했다. v0.7
단일 실행에서는 기존 결합 출력용 v0.5가 단계별 라벨 공간을 혼동해 미채택됐다. 결과와
소비 상태는 `FEEDBACK_TWO_STAGE_V0.1_HOLDOUT_V0.7_RESULT.md`를 따른다.

실행계획은 endpoint와 결과·claim·receipt 절대 경로를 함께 고정했다. 실행 시작 시 claim을
원자적으로 생성했으며 완료 receipt까지 남아 있으므로 이 시험지는 다시 실행할 수 없다.
