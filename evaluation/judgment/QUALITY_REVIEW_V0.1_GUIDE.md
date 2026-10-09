# 실제 STT 30건 독립 품질 검수 가이드 v0.1

기준일: 2026-10-06
상태: **표본 봉인 완료·익명 텍스트 검수 대기**

## 목적과 한계

이 검수는 실제 저장 STT에서 판단모델의 문법 판단·최소 교정 품질을 최소 비용으로 확인하기 위한 독립 표본이다. 기존 shadow v0.1 50건과 v0.2 100건을 모두 제외한 190건에서 30건을 고정 층화 추출했다. 표본 선택에는 문장 내용, 정답 또는 모델 출력이 사용되지 않았고 현재 모델 추론 횟수는 0회다.

DB에 음성 경로는 남아 있지만 실제 음성 파일이 서버에 없으므로 다음 항목은 평가하지 않는다.

- 학습자 발음이 맞았는지
- STT가 음성을 정확히 전사했는지
- 표기 문제가 학습자와 STT 중 누구에게서 발생했는지

이 검수만으로 일본어 전문가 인증이나 운영 기본값 승격을 주장하지 않는다.

## 검수 파일

- 검수 대상: `evaluation/judgment/runs/quality_review_v0.1/review.jsonl`
- 비공개 매핑: `evaluation/judgment/runs/quality_review_v0.1/mapping.jsonl`
- 공개 manifest: `evaluation/judgment/quality_review_v0.1.manifest.json`

두 JSONL은 원문 또는 DB 연결 정보가 있으므로 Git에 넣지 않는다. 검수자는 `review.jsonl`만 사용한다. `mapping.jsonl`의 발화 ID와 STT 모델을 검수 전에 보지 않는다.

## 문항별 작성 방법

각 줄은 JSON 객체 하나다. 입력 필드 `id`, `text`, `context`, `learner_level`, `audio_review`는 수정하지 않는다.

작성할 필드는 다음과 같다.

- `grammar_decision`: `acceptable`, `needs_correction`, `insufficient_evidence` 중 하나
- `corrected_text`:
  - `acceptable`: 원문과 문자 단위로 동일
  - `insufficient_evidence`: 누락 내용을 추측하지 말고 원문과 동일
  - `needs_correction`: 의미·시제·말투를 보존한 최소 교정문
- `error_types`: 교정이 필요할 때만 아래 허용 유형을 중복 없이 기록
  - `particle_misuse`
  - `verb_conjugation`
  - `adjective_conjugation`
  - `copula_conjugation`
  - `modifier_connection`
  - `tense_mismatch`
- `reason_ko`: 판단과 교정에 직접 대응하는 짧은 한국어 근거
- `review_status`: `independently_reviewed`
- `reviewed_at`: `YYYY-MM-DD`

개인 이름·학번·이메일·서명 등 검수자 식별자는 기록하지 않는다. 실제 일본어 전문가가 검수하지 않았다면 전문가 검수라고 표시하지 않는다.

## 판단할 때 주의할 점

1. 더 자연스러운 표현이 있다는 이유만으로 교정하지 않는다.
2. 캐주얼 표현, 필러, 조사 생략, 축약을 자동으로 오류 처리하지 않는다.
3. 문장이 끊겼거나 핵심 단어가 불분명하면 내용을 만들어 넣지 않는다.
4. 질문 문맥이 없으므로 동문서답 여부를 추측하지 않는다.
5. STT 텍스트만 보고 발음 오류라고 단정하지 않는다.
6. 명확한 문법 오류만 최소 교정하며 번역·문체 개선·대화 복구문을 교정문에 넣지 않는다.
7. 판단하기 어렵다는 이유만으로 문법적으로 완전한 문장을 `insufficient_evidence`로 보내지 않는다.

## 작성 예시

문법상 허용:

```json
{
  "grammar_decision": "acceptable",
  "corrected_text": "来月は公園に行きます。",
  "error_types": [],
  "reason_ko": "목적지 조사와 동사 활용이 문법적으로 허용됩니다.",
  "review_status": "independently_reviewed",
  "reviewed_at": "2026-10-06"
}
```

교정 필요:

```json
{
  "grammar_decision": "needs_correction",
  "corrected_text": "学校に行きます。",
  "error_types": ["particle_misuse"],
  "reason_ko": "이동 목적지에는 조사 に를 사용합니다.",
  "review_status": "independently_reviewed",
  "reviewed_at": "2026-10-06"
}
```

근거 부족:

```json
{
  "grammar_decision": "insufficient_evidence",
  "corrected_text": "昨日、駅で友達に",
  "error_types": [],
  "reason_ko": "서술어가 누락되어 문법 판단에 필요한 정보가 부족합니다.",
  "review_status": "independently_reviewed",
  "reviewed_at": "2026-10-06"
}
```

예시의 문장은 작성 형식을 설명할 뿐 현재 30건 표본의 정답이 아니다.

## 완료 검사

30건을 모두 작성한 뒤 아래 명령을 실행한다.

```bash
venv/bin/python -B -m evaluation.judgment.validate_quality_review_v0_1
```

검사 항목:

- 30개 ID의 순서·중복·누락
- 봉인 이후 입력 문장·문맥·수준 불변
- 익명성 및 개인 식별자 필드 부재
- 세 판단 상태와 최소 교정 계약
- 오류 유형 allowlist
- 검수일·검수 상태 완료
- 오디오/STT/발음 판단 불가 상태 유지

검사가 성공해야만 라벨 SHA-256을 고정하고 이 30건에 v0.2-D를 정확히 한 번 실행한다.

## 모델 평가 후 제한적 통과 조건

- 30건 모두 독립 라벨 완료, 미해결 0건
- 시스템·출력 계약 실패 최대 1건
- 정상 문장의 과교정 0건
- 의미를 바꾸는 교정 0건
- 모든 실패와 이견을 문항 수와 함께 보고

작은 표본이므로 백분율만으로 품질을 과장하지 않는다. 이 조건을 통과해도 제한적 staging/shadow 후보 상태만 유지하며, 학습자 노출 승인은 별도 결정한다.
