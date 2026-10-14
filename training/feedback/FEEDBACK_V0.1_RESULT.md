# feedback-v0.1 Qwen3-8B 학습·평가 결과

기준일: 2026-10-14

## 결론

`feedback-verifier-v0.1`은 공식 strict 계약을 통과하지 못해 **미채택**이다.
관리자 경고, 200건 shadow, 자동 학습 후보 생성에는 사용하지 않는다.
기능 플래그는 계속 기본 비활성으로 유지한다.

## 학습

- 베이스: Qwen3-8B BF16
- 데이터: 자동검증 600건(train 540, internal eval 60), 사람·전문가 검수 아님
- LoRA: rank 16, alpha 32, dropout 0.05, seed 42
- 3 epoch, 204 optimizer step, A6000, 1,105.494초
- train loss: 0.0928735
- internal eval loss: 0.0000216928
- adapter model: 174,655,536바이트
- adapter SHA-256: `e52050a6e06d724604820201d1a4efdf678f6e2c0c534920ea9dec87525d2aa1`
- 배포 조합 SHA-256: `efbbc9d2cf2bed81e6ce24da6070c25d7bc0755c213875224cfa204d58a22630`

학습 후반 token accuracy가 1에 수렴했고 internal eval도 같은 생성 템플릿 계열이므로
loss만으로 일반화를 주장할 수 없다.

## 봉인 holdout 공식 결과

120건 holdout SHA-256은
`21f23d97b141652d6f53dff3d02b68ad0b3ffc902660ffe88b1b7212599a1eb1`이다.
베이스와 LoRA를 temperature 0, max tokens 512, 단일 순차 조건으로 각각 한 번 실행했다.

| 지표 | 8B 베이스 | feedback-v0.1 LoRA | 필수 기준 |
| --- | ---: | ---: | ---: |
| 전송 성공 | 120/120 | 120/120 | 참고 |
| strict 계약 성공 | 0/120 | 0/120 | ≥119/120 |
| p95 | 12.230초 | 2.488초 | ≤5초 |

베이스는 장문 reasoning으로 512토큰을 소진했고, LoRA는 원하는 JSON 앞에 모든
응답에서 정확히 빈 `<think></think>` 래퍼를 출력했다. 계약은 JSON 객체 하나만
허용하고 위반 출력을 보정하지 않으므로 LoRA도 0/120이다.

## 진단 replay와 한계

모델을 다시 호출하지 않고 기존 LoRA 출력에서 정확한 빈 think 래퍼만 제거한
비공식 replay에서는 계약 120/120, 탐지 precision/recall 100%, 권장 decision과
교정문 100%, 허위 불일치 0%, p95 2.488초였다. 이 수치는 채택 결과가 아니다.

학습셋과 holdout이 원문 정확 중복은 없지만 동일한 12개 구조 템플릿에서 파생되어
진단 성능이 과대평가됐을 가능성이 높다. 따라서 새 시험지는 템플릿·어휘·문장 구조까지
분리해 생성해야 한다.

## 다음 단계

1. OpenAI 응답의 reasoning과 content를 분리하는 vLLM `--reasoning-parser` 설정을
   실행 규약에 먼저 고정한다.
2. 구조적으로 독립적인 `feedback holdout v0.2`를 모델 추론 전에 생성·봉인한다.
3. v0.1 LoRA를 새 시험지에서 딱 한 번 평가한다. 이번 v0.1 holdout은 재사용하지 않는다.
4. strict 계약과 품질 기준을 모두 통과한 경우에만 200건 shadow로 넘어간다.

원시 응답과 가중치는 Git 제외 경로에 보존하며 Git에는 해시·집계·보고서만 남긴다.
