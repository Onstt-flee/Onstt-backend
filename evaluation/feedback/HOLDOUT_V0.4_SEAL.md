# feedback holdout v0.4 봉인 기록

기준일: 2026-10-15

## 목적

`feedback-verifier-v0.3`의 GPU 전용 내부 후보 비교를 위한 미사용 시험지다.
`feedback-v0.2`가 정상 일본어를 비일본어로 오인한 반복 실패와 불필요한 보류,
명확한 오류 누락, 최소 교정 실패를 같은 시험지 재사용 없이 측정한다.

## 봉인 상태

- 문항: 120건
- SHA-256: `c22c5ddb0153c60d7087ef1e26580e669ea974e2bdafb0e65142f9eaeed60802`
- 기대 verdict: agree 40 / disagree 70 / unreviewable 10
- 기존 feedback 학습 v0.1·v0.2 및 holdout v0.1~v0.3과 원문 중복: 0건
- 검수 상태: `generated_validated`
- 사람 검수: 없음
- 일본어 전문가 검수: 없음
- 봉인 시 모델 추론: 0회
- 2026-10-15 공식 단일 실행: 120건
- 현재 `single_use=true`, `consumed=true`, `ready_for_inference=true`

## 사용 제한

- 이 데이터는 내부 모델 선택용이며 운영 품질을 인증하지 않는다.
- Pi 런타임 비교는 이번 범위에서 제외한다.
- 학습·프롬프트·선택 규칙 변경에 사용하지 않는다.
- v0.3 어댑터와 실행 설정 해시를 고정한 뒤 120건을 한 번 실행했고, 현재 재실행을 금지한다.
- 결과를 확인한 뒤 같은 시험지에 맞춰 재학습하거나 재실행하지 않는다.

관련 파일:

- `evaluation/feedback/holdout_v0.4.jsonl`
- `evaluation/feedback/holdout_v0.4.manifest.json`
- `evaluation/feedback/holdout_v0.4.protocol.json`
- `evaluation/feedback/build_holdout_v0_4.py`
