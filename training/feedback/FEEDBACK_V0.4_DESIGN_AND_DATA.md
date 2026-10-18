# feedback-v0.4 설계 및 학습 데이터

기준일: 2026-10-16

## 결론

강화 프롬프트 신규 진단 v0.2에서 확인된 존재 장소 오류 누락, 의미 모순, 정상 문장 과민
반응을 보강하는 `feedback-v0.4` 학습 준비를 완료했다. 모델 학습 전에 별도 holdout v0.5
120건을 먼저 봉인했으며, 기존 학습·holdout·진단과 원문 및 완전 입력 중복은 모두 0건이다.

## 봉인 holdout v0.5

| 구분 | 건수 |
| --- | ---: |
| 전체 | 120 |
| agree | 50 |
| disagree | 60 |
| unreviewable | 10 |
| 정상 근거 표현 다양화 | 30 |
| false negative 의미 고정 | 20 |
| false positive 의미 고정 | 20 |
| 올바른 교정 동의 | 20 |
| reason mismatch | 10 |
| 불필요한 보류 | 10 |
| STT 표기·음성 근거 경계 | 10 |

holdout은 `generated_validated`이며 사람 또는 일본어 전문가 검수 자료가 아니다. v0.4 학습
산출물 해시를 결합해 `ready_for_inference=true`, `consumed=false`로 전환했다. 계획된 추론은
Qwen3-8B 베이스라인 1회와 v0.4 LoRA 1회뿐이었으며, 두 실행을 마친 뒤
`consumed=true`로 잠갔다.

## 학습 데이터 v0.4

v0.3 1,782건을 그대로 기반으로 사용하고 새 템플릿 300건을 추가했다.

| 구분 | 건수 |
| --- | ---: |
| 전체 | 2,082 |
| train | 1,868 |
| eval | 214 |
| 정상 판단 근거 다양화 | 100 |
| false negative 일관성 | 75 |
| false positive 일관성 | 75 |
| 불필요한 보류 일관성 | 50 |

소비된 조사 진단 v0.1·v0.2의 문장을 학습에 넣지 않았다. 실패 유형만 다른 명사·장소·동작
템플릿으로 일반화했으며 두 진단 및 holdout v0.5와 원문·완전 입력 중복이 모두 0건이다.

## 학습 조건

- 베이스: `Qwen/Qwen3-8B`
- LoRA: rank 16, alpha 32, dropout 0.05
- seed: 42
- epoch: 1
- learning rate: 0.0002
- 출력: `feedback-v0.1` 계약과 강화된 issue/decision 의미 규칙
- 출력 위치: `/home/cap-minsung/lora-adapter-bank/adapters/feedback-verifier-v0.4`

v0.3과 데이터·산출물 경로 이외의 학습 조건은 동일하다. 실제 학습은 234 step으로 완료됐고
train loss는 `0.1764722679220299`, eval loss는 `0.00603330135345459`였다.

## 해시

- holdout v0.5 데이터: `b41e4ee0553e57051c7381c95151a885ffb41979a408078e8923f723352d59fc`
- holdout manifest: `51f015dc2a20227a6b7d460aac2ad977559c221fddac20a6d6747a24de645ad4`
- 학습 원본: `b9bee0df8d341e83d96d1475e07a15c095cd3ef89ae9ef009f56669cc008cd8c`
- train ChatML: `e85bfa7e2f1fbf0479f609b66b77d4cda186f179f40a93ff5ab7a456b20c048b`
- eval ChatML: `249fcc0c62c5cfb63d94fecd512954d45d09b771909c77f205550e64938c24d7`
- 학습 manifest: `3eba228be03a43fc2ad00623bf68712fadea0785d7c27e6267a04f40910a0d37`
- 학습 설정: `bc09eed0b73265a610cb5ac291109248fff59f6de6dd8a458246f20b1c8e3e53`
- LoRA 어댑터: `2af21a821c1f3ad816fc28035479d3525f7aa22eac70c028b1e8a752cdebc78a`
- 어댑터 설정: `4f2279d22200ba5d64990982f0ce5361f825acbf4d4059526aa8ffad55889765`
- 학습 실행 manifest: `62f7ac5bd0863ca77e5b9b681835d65f6f3a812833de184b9f4ee7d087290d09`

holdout protocol 해시는 계획 실행 정보 및 최종 결과를 기록할 때마다 갱신하며, 소비 완료
보고서에서 최종값을 고정한다.

## 다음 실행

1. 최종 결과는 `FEEDBACK_V0.4_RESULT.md`를 참고한다.
2. 전체 회귀 테스트와 해시 감사를 통과시킨다.
3. v0.4는 두 필수 기준 미달로 운영 경고 및 자동 학습에 사용하지 않는다.
