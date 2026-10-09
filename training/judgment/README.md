# 일본어 문법 판단 LoRA 데이터

상태: **holdout v0.4 소비 완료, D/F 모두 추가 자격 기준 실패, 운영 승격 후보 없음**. D는 기본 비활성 연구·staging 기준선으로만 유지한다. v0.4에서 D는 허용 교정문 32/50, F는 36/50으로 사전 40/50 기준에 미달했고 복합 오류는 둘 다 0/10이다. 시험지는 재실행하지 않는다.

## 목적과 격리 원칙

- 첫 학습 대상은 `Qwen/Qwen3-4B-Instruct-2507`이다.
- 기존 `evaluation/judgment/seed_v0.1.jsonl` 72문항은 개발 진단용이며 학습·few-shot·RAG에 넣지 않는다.
- 파일럿은 240개 train과 60개 dev로 구성하며 최종 test가 아니다.
- 운영 API와 DB는 이 단계에서 변경하지 않는다.

## 파일

- `data/pilot_v0.1.jsonl`: 검수 전 canonical 원본 300개
- `data/pilot_v0.1.manifest.json`: 데이터·출처·평가셋 해시와 분포·중복 검사
- `data/pilot_v0.1_review.md`: 검수 전 provisional 문항 보기
- `data/pilot_v0.1.user_review.jsonl`: 익명 사용자 검수 결과 300개
- `data/pilot_v0.1.reviewed.jsonl`: 검수 결과를 적용한 학습 canonical
- `data/pilot_v0.1.reviewed.manifest.json`: reviewed 데이터·검수 원본·중복 검사 해시
- `data/pilot_v0.1.reviewed.md`: 검수 완료 전체 문항 보기
- `data/reviewed_chatml/`: 검수 완료 train/dev ChatML
- `data/reason_control_v0.2_a/`: 판단·교정 정답은 유지하고 학습용 근거만 통제한 train/dev ChatML
- `data/reason_control_v0.2_a.manifest.json`: 근거 통제 정책·원본 해시·파생 파일 해시
- `data/hard_negatives_v0.2_b.jsonl`: 자동 검증된 정상·오류·보류 보강 240문항
- `data/pilot_v0.2_b.jsonl`: 기존 통제본과 보강본을 결합한 540문항 학습 소스
- `data/hard_negatives_v0.2_b_chatml/`: v0.2-B train/dev ChatML
- `data/hard_negatives_v0.2_b.manifest.json`: 생성 규칙·최소대립쌍·누수 검사·해시
- `data/contract_control_v0.2_b_chatml/`: 기존 540문항을 위치 없는 v0.2 출력으로 재내보낸 대조군 train/dev
- `data/contract_control_v0.2_b.manifest.json`: 정답 불변성과 파생 파일 해시
- `data/failure_focus_v0.2_d.jsonl`: 공통 실패 유형 보강 120문항
- `data/pilot_v0.2_d.jsonl`: v0.2-C 원본 628문항과 새 120문항을 결합한 748문항
- `data/failure_focus_v0.2_d_chatml/`: 위치 없는 v0.2 출력의 train/dev
- `data/failure_focus_v0.2_d.manifest.json`: 분포·누수 감사·해시
- `REVIEW_CHECKPOINT.md`: 1차 300문항·2차 228문항의 검수 순서와 주의 기준
- `sources/qwen3_14b_lexicon_v0.1.json`: 14B 원시 어휘 제안, 선별 결과와 오분류 기록
- `data/failure_focus_v0.2_e.jsonl`: 최소 교정·문체 보존·복합 오류 회귀 보강 80문항
- `data/pilot_v0.2_e.jsonl`: v0.2-D 748문항과 새 80문항을 결합한 828문항
- `data/failure_focus_v0.2_e_chatml/`: 위치 없는 v0.2 출력의 train/dev
- `data/failure_focus_v0.2_e.manifest.json`: 분포·최소대립쌍·누수 감사·해시
- `data/contract_preservation_v0.2_g.jsonl`: 실제 운영 원문 없이 만든 계약 보존 합성 108문항
- `data/pilot_v0.2_g.jsonl`: v0.2-D와 G 추가분을 결합한 856문항
- `data/contract_preservation_v0.2_g_chatml/`: 위치 없는 v0.2 출력의 train/dev
- `data/contract_preservation_v0.2_g.manifest.json`: 분포·누수 감사·운영 원문 미사용 증거와 해시
- `data/sampling_focus_v0.2_h_chatml/`: G와 같은 의미 소스에서 720개 실제 노출 순서를 고정한 H train/dev ChatML
- `data/sampling_focus_v0.2_h.manifest.json`: 고정 노출 구성·입력 해시·분포 기록
- `data/pilot_v0.2_i.jsonl`: v0.2-D 748문항과 F 보강분 120문항만 결합한 868문항
- `data/failure_focus_v0.2_i_chatml/`: D 안전 앵커를 포함해 720개 train 노출을 고정한 I train/dev ChatML
- `data/failure_focus_v0.2_i.manifest.json`: D+F 계보·노출 분포·보호 holdout 해시
- `data.py`: 학습 레코드 계약·split 격리·중복 검사
- `generate_pilot.py`: 결정론적 파일럿 생성기
- `apply_user_review.py`: 외부 검수를 익명 3단계 판단으로 정규화하고 reviewed 데이터를 생성하는 도구
- `export_chatml.py`: 검수 완료 데이터만 ChatML로 내보내는 도구
- `build_reason_control.py`: canonical을 수정하지 않고 템플릿별 통제 근거를 주입하는 `v0.2-A` 생성기
- `build_hard_negatives.py`: 8개 취약 유형의 최소대립쌍과 정상·보류 문장을 생성·검증하는 `v0.2-B` 생성기
- `build_contract_control.py`: 기존 v0.2-B 정답·분할을 유지하는 동일 계약 대조군 생성기
- `build_failure_focus_v0_2_d.py`: 공통 실패 유형의 v0.2-D 데이터·ChatML 생성 및 holdout 누수 감사
- `build_failure_focus_v0_2_e.py`: v0.2-D 교정문 회귀 보강 데이터·ChatML 생성 및 holdout 누수 감사
- `build_failure_focus_v0_2_f.py`: holdout 안전 실패 보강 120문항·ChatML 생성 및 v0.3 포함 누수 감사
- `build_contract_preservation_v0_2_g.py`: shadow 원문 없이 계약 경계 최소대립·보류 문항을 생성하는 v0.2-G 빌더
- `build_sampling_focus_v0_2_h.py`: 새 정답 없이 G train의 보류·정상 노출을 고정하는 v0.2-H 빌더
- `build_failure_focus_v0_2_i.py`: D 원본과 F 보강분만 결합하고 D 안전 앵커를 반복하는 v0.2-I 빌더
- `train_lora.py`: provisional 명시 동의와 입력 검증을 요구하는 독립 LoRA 학습기
- `configs/qwen3_4b_pilot_v0.1.json`: 기존 provisional Qwen3-4B 실험 설정
- `configs/qwen3_4b_reviewed_v0.1.json`: 검수 완료 데이터 전용 다음 학습 설정
- `configs/qwen3_4b_reason_control_v0.2_a.json`: 기존 학습 조건을 유지한 근거 통제 실험 설정
- `configs/qwen3_4b_hard_negatives_v0.2_b.json`: 데이터 증가와 무관하게 45 step으로 고정한 보강 실험 설정
- `configs/qwen3_4b_contract_control_v0.2_b.json`: v0.2-C와 동일 조건으로 학습하는 별도 대조군 설정
- `configs/qwen3_4b_failure_focus_v0.2_d.json`: 별도 어댑터에 seed 42·45-step 학습하는 v0.2-D 설정
- `PILOT_V0.1_RESULT.md`: provisional 실험 결과와 실패 분석
- `configs/qwen3_4b_failure_focus_v0.2_e.json`: 동일 조건의 별도 v0.2-E 어댑터 설정
- `configs/qwen3_4b_failure_focus_v0.2_f.json`: v0.2-E와 같은 seed 42·45-step의 별도 v0.2-F 어댑터 설정
- `configs/qwen3_4b_contract_preservation_v0.2_g.json`: v0.2-D에서 분기한 seed 42·45-step G 설정
- `configs/qwen3_4b_sampling_focus_v0.2_h.json`: H 고정 노출 ChatML을 사용하는 seed 42·45-step 설정
- `configs/qwen3_4b_failure_focus_v0.2_i.json`: D+F 통제 데이터의 seed 42·45-step I 설정
- `REVIEWED_V0.1_RESULT.md`: 검수 완료 데이터 학습·72문항 비교와 다음 실험 조건
- `CONTRACT_CONTROL_V0.2_B_RESULT.md`: 동일 출력 계약 대조군과 v0.2-C의 개발셋 비교·실패 원인
- `V0.2_D_DESIGN.md`: 새 시험지 봉인과 후속 학습·평가 순서
- `V0.2_D_DATA_RESULT.md`: 120문항 보강 데이터의 분포·해시·누수 검사 결과
- `V0.2_D_TRAIN_RESULT.md`: 45-step 학습 조건·손실·어댑터 해시와 개발셋 평가 상태
- `V0.2_D_DEV72_COMPARISON.md`: C↔D 동일 조건 개발셋 비교와 교정문 회귀 분석
- `V0.2_E_DESIGN_AND_DATA.md`: 교정문 회귀 보강 설계, 80문항 생성·누수 검사와 채택 기준
- `V0.2_E_TRAIN_AND_DEV72_RESULT.md`: v0.2-E 학습 해시, C·D·E 개발셋 비교와 채택 보류 근거
- `V0.2_DE_CANDIDATE_GATE_RESULT.md`: D 판단 고정 후보 선택 규칙, 개발셋 개선·한계와 해시
- `V0.2_DE_HOLDOUT_V0.2_RESULT.md`: 단일 실행 해시·최종 지표·운영 채택 실패와 분기 결정
- `V0.2_F_DESIGN.md`: holdout 실패 유형 중심 보강 범위와 새 시험지 사용 금지 조건
- `V0.2_F_DATA_RESULT.md`: 추가 120문항·결합 948문항, 누수 감사·ChatML·학습 설정 검증 결과
- `V0.2_F_TRAIN_AND_DEV72_RESULT.md`: 45-step 학습 해시, D/E/F 개발셋 비교와 F 단독 채택 실패 근거
- `V0.2_DF_CANDIDATE_GATE_RESULT.md`: D 판단 잠금 D+F 게이트의 개발셋 진단 결과
- `V0.2_1_PROMPT_HARDENING_RESULT.md`: 원문 보존 프롬프트 강화의 개발셋 회귀와 미채택 근거
- `V0.2_G_TRAIN_AND_DEV72_RESULT.md`: 합성 계약 보강 108문항, 45-step 학습과 D/G 개발셋 비교
- `V0.2_H_DESIGN.md`: 새 holdout v0.4 봉인과 고정 노출 샘플링의 사전 기준
- `V0.2_H_TRAIN_AND_DEV72_RESULT.md`: H 학습 해시, D/G/H 동일 서버 비교와 미채택 근거
- `V0.2_I_DESIGN.md`: D+F 통제 학습 계보와 사전 채택 기준
- `V0.2_I_TRAIN_AND_DEV72_RESULT.md`: I 학습 해시, D/I 동일 서버 비교와 안전성 회귀·미채택 근거
- `DETERMINISTIC_BOUNDARY_GATE_V0.1_RESULT.md`: 빈 입력·비일본어·STT 표기 경계의 오프라인 정책과 D/H replay 결과
- `V0.2_DF_HOLDOUT_V0.3_RESULT.md`: 봉인 시험지 단일 실행, D 단독 선택과 게이트 미채택 근거

## 데이터 구성

| 구분 | 수량 |
| --- | ---: |
| `pilot_train` | 240 |
| `pilot_dev` | 60 |
| `acceptable` | 136 |
| `needs_correction` | 119 |
| `insufficient_evidence` | 45 |
| N5 / N4 | 210 / 90 |
| 복합 오류 | 17 |

Qwen3-14B는 어휘와 상황 후보만 한 번 제안했다. 원시 제안에 동사 그룹 오분류, 형용사 분류 오류와 중복이 있어 선별 결과를 별도로 기록했다. 모델은 문장 판단·교정문·오류 위치를 확정하지 않으며, 모든 edit는 생성 코드가 Unicode 코드 포인트 기준으로 계산한다.

## 실행 및 검증

```bash
venv/bin/python -B -m training.judgment.generate_pilot

venv/bin/python -B -m training.judgment.data \
  --dataset training/judgment/data/pilot_v0.1.jsonl \
  --seed evaluation/judgment/seed_v0.1.jsonl \
  --rag-dir rag_data

venv/bin/python -B -m training.judgment.render_review \
  --dataset training/judgment/data/pilot_v0.1.jsonl \
  --output training/judgment/data/pilot_v0.1_review.md
```

`export_chatml`은 기본적으로 `provisional` 레코드를 거부한다. 이번에는 학습 파이프라인과 실패 양상을 조기에 검증하기 위한 명시적 실험에서만 `--allow-provisional`을 사용했다. 산출물은 운영·승인 모델이 아니다.

```bash
venv/bin/python -B -m training.judgment.export_chatml \
  --dataset training/judgment/data/pilot_v0.1.jsonl \
  --output-dir training/judgment/data/chatml
```

## 검수 완료본 생성 및 검증

300개 ID·원문·문맥을 대조해 불일치 0건을 확인했다. `JT-0205`의 `有名店`은 합성명사로 인정해 `acceptable`로 확정했고, `JT-0247`은 `有名店に時計があります。`로 최소 교정했다. 모든 레코드는 개인 식별자 없이 `user_reviewed`, 검수일 `2026-09-14`로 기록했다. 제공되지 않은 검수 신뢰도는 임의 생성하지 않고 `not_recorded`로 보존한다.

reviewed 데이터 SHA-256은 `ff330bb62d479c8779b80ec9fdd9b25ae074172bdc0df5759a83af8c65bff16b`다. 평가셋/RAG 정확·근접 중복은 0건이고, 승인 ChatML 해시는 train `4b1e3b9cc7735a598373b1196eb2c76b46e45d162d57ba26769da6980d2b41e6`, dev `a6a6dbd3537be8422ac93d8ef2c544f2cfe8659fa3dc94020f9c12f4baf2e5fa`다. 일본어 전문가 인증본은 아니다.

## v0.2-A 근거 통제 입력

사람의 상세 검수 근거를 학습 목표로 그대로 사용하지 않도록 43개 템플릿 가족마다 짧은 결정론적 근거를 지정했다. 기존 300문항의 `decision`, `corrected_text`, `edits`, split은 바꾸지 않았고 canonical 파일도 수정하지 않았다. 300개 학습 근거는 모두 통제 문구로 교체됐다.

```bash
venv/bin/python -B -m training.judgment.build_reason_control
venv/bin/python -B -m training.judgment.train_lora \
  --config training/judgment/configs/qwen3_4b_reason_control_v0.2_a.json \
  --validate-only
```

파생 ChatML 해시는 train `db3730f5eaa973c6c412e1a49333eb3e18bbb1a0acad72a034dddfa601700672`, dev `9e1a132b2cace3349f9ca5b98cebeaf2918146ee4b9ccf51b0ca9fca0fe9ef7b`다. 이는 일본어 전문가 재검수가 아니라 기존 확정 정답을 유지한 학습 표현 통제 실험이다.

1-step Smoke 학습은 8개 train/8개 dev로 완료했다. train loss는 `3.0525`, dev loss는 `2.6957`이며 어댑터 SHA-256은 `01cbad56ba3b2b79784a6c16601144d1b4d6dcba3ffb68b5f023478d73280f87`이다. 이 수치는 실행 경로 검증용이며 모델 품질 비교에는 사용하지 않는다.

전체 3 epoch 학습은 45 step, 240개 train/60개 dev로 완료했다. train loss는 `0.4961`, dev loss는 `0.7580`이며 어댑터 SHA-256은 `def3712525e6fe8c984e14e679080a6a116e578a582a45db74e4f544586b5d84`이다. 기존 reviewed v0.1의 dev loss `0.4914`보다 높으므로 개선으로 단정하지 않으며, 과교정 효과는 고정 72문항 평가로 확인한다.

동일한 72문항·프롬프트·생성 조건 평가에서 전송 72/72, 엄격 계약 45/72를 기록했다. 원시 내용은 판단 63/72, 교정 탐지 25/27, 허용 교정문 22/27, 올바른 보류 12/12, 과교정 4/33이다. reviewed v0.1 대비 판단과 과교정은 개선됐지만 교정 탐지와 교정문이 각각 1건 감소해 안전 우선 채택 기준을 통과하지 못했다. 남은 과교정은 JG-011·065·067·068이며 offset을 백엔드에서 재구성하면 구조 계약은 72/72가 된다. 운영 API에는 연결하지 않는다.

## v0.2-B 최소대립쌍 보강

사람 상세 검수를 추가하지 않고 결정론적 규칙으로 240문항을 생성했다. 8개 취약 유형마다 정상 12개와 대응 오류 12개를 만들고, 일반 정상 24개·판단 불충분 24개를 더했다. 오류 96개는 모두 한 개 edit만 가지며 교정하면 같은 pair의 정상문장과 정확히 일치한다.

결합본은 540문항으로 train 432/dev 108, 정상 256/교정 215/보류 69, N5 378/N4 162다. 생성 240문항은 `generated_validated`이며 사용자·전문가 검수를 주장하지 않는다. 평가셋과 문자 3-gram Jaccard 0.75 이상 유사 문장 및 평가셋/RAG 정확 중복은 0건이다.

```bash
venv/bin/python -B -m training.judgment.build_hard_negatives
venv/bin/python -B -m training.judgment.train_lora \
  --config training/judgment/configs/qwen3_4b_hard_negatives_v0.2_b.json \
  --validate-only
```

보강본 SHA-256은 `ac2633833b77e0f9a98452df4a3477cbdf448b2781865e9984a9ca121b0484e9`, 결합본은 `e6eb2eb62ff9d8cdb1fcf9c35da73334ddee24e285f0cf7ca7bb050d97180711`이다. ChatML은 train `3f5063274bbda79972957f07e4d86eb4fae2fe47e736c1789943d9c6e063d6cc`, dev `d269cf0d8009d846046588fa7bc10825fd68d74bc8b2d113620819a5b4e21eae`다. 전체 45-step 학습은 319.765초, train loss `0.6283`, dev loss `0.3138`이며 어댑터 SHA-256은 `8b558bfad937c75b31528f0c4943252eaaf29ae747adbb1442d4f8e95e2910ae`다. 동일 72문항에서 엄격 계약 48/72, 원시 판단 68/72, 교정 탐지 25/27, 허용 교정문 18/27, 보류 12/12, 과교정 2/33을 기록했다. 상세 비교는 [v0.2-B 결과](HARD_NEGATIVES_V0.2_B_RESULT.md)를 따른다.

## v0.2-C 실패 집중 보강과 blind 평가

위치 생성을 모델에서 제거한 `judgment-v0.2` 계약을 적용하고, v0.2-B 실패 11건을 겨냥한 자동 검증 88문항을 추가했다. 결합본은 628문항이며 Qwen3-4B·seed 42·45-step 조건으로 학습했다. 신규 150문항 blind holdout에서 구조 149/150, 재현율 59/66은 기준을 통과했지만 과교정 8/60과 정밀도 59/69가 안전 기준을 실패했다. 따라서 운영 API 통합은 보류한다. 상세 수치와 해시는 [v0.2-C 결과](FAILURE_FOCUS_V0.2_C_RESULT.md)를 따른다.

## v0.2-B 동일 출력 계약 대조군

기존 540문항의 정답을 바꾸지 않고 위치 없는 `judgment-v0.2` 출력으로 재내보내 별도 Qwen3-4B 어댑터를 seed 42·45-step 학습했다. 같은 72문항 개발셋에서 v0.2-C는 대조군보다 과교정 3/33→2/33, 교정 탐지 정밀도 25/29→25/27, 허용 교정문 17/27→20/27로 개선됐다. 두 모델 모두 운영 안전 기준은 실패했다. 이미 확인한 150문항 holdout은 재사용하지 않았다. 전체 해시와 공통 실패 문항은 [동일 계약 대조 결과](CONTRACT_CONTROL_V0.2_B_RESULT.md)에 기록했다.

## v0.2-D 설계 및 새 시험지

미사용 120문항 시험지를 별도 해시로 고정한 뒤, 개발셋 공통 실패를 겨냥한 120문항을 생성·검증했다. 기존 628문항을 변경하지 않고 총 748문항으로 결합했으며 train 594/dev 154다. 새 데이터와 기존 평가·학습·RAG 사이 정확·근접 중복은 설정한 기준에서 0건이다. 같은 seed 42·45-step 조건으로 별도 LoRA를 학습하고 72문항 개발셋에서 C와 비교했다. D는 판단 69/72·과교정 0/33으로 개선됐지만 교정문 일치 19/27·복합 오류 완전 탐지 0/4로 후퇴했다. 설계·봉인은 [v0.2-D 설계](V0.2_D_DESIGN.md), 데이터는 [v0.2-D 데이터 결과](V0.2_D_DATA_RESULT.md), 학습은 [v0.2-D 학습 결과](V0.2_D_TRAIN_RESULT.md), 문항별 분석은 [C↔D 개발셋 비교](V0.2_D_DEV72_COMPARISON.md)를 따른다.

## v0.2-E 교정문 회귀 보강

정중체 유지, い형용사 연결·수식, 복합 오류 전체 교정, 완결된 구어체 허용을 중심으로 80문항을 결정론적으로 생성했다. 추가분은 정상 32·교정 40·보류 8이고 복합 오류 12문항과 최소대립쌍 16개를 포함한다. 기존 748문항은 변경하지 않았으며 결합본은 828문항이다. 동일 조건 45-step 학습 뒤 E는 개발셋 교정문 20/27·복합 오류 1/4를 회복했지만 과교정 1/33·판단 66/72로 채택 기준을 실패했다. 설계·해시는 [v0.2-E 설계·데이터](V0.2_E_DESIGN_AND_DATA.md), 결과는 [v0.2-E 학습·비교](V0.2_E_TRAIN_AND_DEV72_RESULT.md)를 따른다.

## D 판단 + E 교정 후보 게이트

D의 판단을 절대 변경하지 않고 두 모델이 모두 교정을 제안할 때만 요청 의도·정중체·오류 잔존·변경량으로 후보를 선택한다. 정답을 선택 과정에 사용하지 않았다. 개발셋에서 D의 판단 정확도 69/72와 과교정 0/33을 유지하면서 허용 교정문을 19/27→22/27, 복합 오류 완전 교정을 0/4→1/4로 높였다. 상세 규칙·해시·한계는 [후보 게이트 결과](V0.2_DE_CANDIDATE_GATE_RESULT.md)를 따른다. 동결 후 `holdout_v0.2`를 단 한 번 실행했으나 D 과교정 2/50과 게이트 개선 0건으로 운영 채택에 실패했다. [최종 holdout 결과](V0.2_DE_HOLDOUT_V0.2_RESULT.md)를 따른다.

## provisional 파일럿 실험 결과

Qwen3-4B LoRA는 72문항에서 원시 판단 정답을 57건에서 63건, 허용 교정문을 17건에서 23건으로 높였다. 반면 원시 과교정은 4건에서 7건으로 늘었고, edit 위치 오류로 엄격 계약은 45건에서 37건으로 감소했다. 상세 수치와 해시는 [파일럿 결과](PILOT_V0.1_RESULT.md)를 따른다.

현재 어댑터는 데이터와 함께 `experimental_provisional`이며 운영 API에 연결하지 않는다. 엄격 계약 점수와 별개로 원시 내용만 보는 `evaluation/judgment/content_diagnostics.py`는 실패 원인 분리용 보조 도구이지 공식 채점기가 아니다.

## 다음 단계

1. 완료: 300문항 익명 사용자 검수, 3단계 판단 변환과 ChatML 내보내기.
2. 완료: 동일 원시 출력의 edit 위치를 백엔드 diff로 재구성해 엄격 구조를 37/72에서 67/72로 회복했다. 운영 계약에는 아직 적용하지 않았다.
3. 완료: reviewed 데이터로 Qwen3-4B Smoke 및 3 epoch 전체 학습을 새 경로에서 실행했다.
4. 완료: 같은 72문항·생성 조건으로 베이스·provisional·reviewed 어댑터를 비교했다.
5. reviewed LoRA는 엄격 계약 41/72, 원시 판단 60/72, 원시 과교정 8/33으로 운영 기준에 미달했다. 상세 내용은 [reviewed 결과](REVIEWED_V0.1_RESULT.md)를 따른다.
6. 완료: canonical 검수 근거와 학습용 짧은 근거를 분리한 `v0.2-A` ChatML·manifest·학습 설정을 생성하고 정답 불변성을 검증했다.
7. 완료: `v0.2-A`를 동일 조건으로 3 epoch 학습했다.
8. 완료: 고정 72문항을 동일 조건으로 실행·채점했으며 `v0.2-A`는 안전 우선 기준 미달로 채택하지 않았다.
9. 완료: 240문항 최소대립쌍·정상·보류 보강과 540문항 `v0.2-B` 결합본을 생성·자동 검증했다.
10. 완료: `v0.2-B` 1-step Smoke와 전체 45-step 학습을 실행했다.
11. 완료: 고정 72문항을 동일 조건으로 실행해 베이스·reviewed·v0.2-A와 비교했다.
12. 완료: D/E/선택기/임계값을 동결하고 `holdout_v0.2`를 단 한 번 실행했다. 안전 기준 실패로 API 통합을 중단했다.
13. 완료: 실패 유형 중심 [v0.2-F 설계](V0.2_F_DESIGN.md)를 작성하고 새 `holdout_v0.3` 120문항을 생성·중복 검사·봉인했다.
14. 완료: 봉인된 시험지를 열지 않고 v0.2-F 추가 120문항과 결합 948문항, ChatML 및 45-step 학습 설정을 생성·검증했다.
15. 완료: 별도 v0.2-F 어댑터를 45-step 학습하고 기존 72문항에서 D/E/F를 비교했다. F는 교정문을 개선했지만 안전 지표가 후퇴해 채택하지 않았다.
16. 완료: D 판단을 잠근 D+F 교정 후보 게이트를 개발셋에서 진단했다. D 안전 지표를 유지하고 허용 교정문을 2건 개선했으며 조건부 p95 1948.001ms로 사전 기준을 통과했다.
17. 완료: D/F 데이터·어댑터·프롬프트·선택기·채점기·임계값을 `holdout_v0.3.protocol.json`에 봉인하고 자동 해시 검증 테스트를 추가했다.
18. 완료: 체크포인트 `dc48d08` 상태에서 `holdout_v0.3`의 D/F를 각각 정확히 한 번 실행하고 D 단독과 D+F 게이트를 동일 채점기로 비교했다.
19. 완료: D는 안전 기준을 모두 통과했다. 게이트는 교정문 증가와 지연시간 비율 기준을 실패해 미채택하고 D 단독을 shadow 통합 후보로 선택했다.
20. 완료: 기존 `/analyze`를 변경하지 않고 기본 비활성 기능 플래그의 별도 판단 API와 저장 테이블을 구현했으며 단위·Swagger 검증을 통과했다.
21. 완료: 실제 STT 50건 D 단독 shadow에서 49/50 계약 성공, p50 801.741ms, p95 1237.647ms를 기록했다. 1건은 `insufficient_evidence`가 원문을 보존하지 않아 계약 위반으로 차단됐다.
22. 유지: 99% 구조 기준 미달로 운영 기본값 승격을 보류한다. 상세는 [실제 STT shadow 결과](JUDGMENT_D_SHADOW_V0.1_RESULT.md)를 따른다.
23. 완료: 비교정 원문 보존 지시를 강화한 v0.2.1 프롬프트를 동일 72문항에서 비교했으나 계약 69/72·판단 59/72·재현율 18/27로 후퇴해 미채택했다. [프롬프트 강화 결과](V0.2_1_PROMPT_HARDENING_RESULT.md)를 따른다.
24. 완료: 실제 shadow 원문을 사용하지 않은 v0.2-G 합성 108문항과 결합 856문항을 생성·검증하고 같은 seed 42·45-step으로 학습했다.
25. 완료: 동일 서버·프롬프트로 D/G를 72문항에서 비교했다. G는 구조 71/72, 과교정 1/33, 판단 67/72, 허용 교정 17/27로 D보다 후퇴해 미채택했다. [v0.2-G 결과](V0.2_G_TRAIN_AND_DEV72_RESULT.md)를 따른다.
26. 완료: 새 미사용 `holdout_v0.4` 120문항을 생성·중복 감사·해시 봉인했다. 모델 추론은 0회다.
27. 완료: 새 정답 없이 G의 720개 학습 노출을 고정한 H를 같은 seed 42·45-step으로 학습했다.
28. 완료: 동일 서버에서 D/G/H를 비교했다. H는 구조 71/72, 과교정 1/33, 판단 68/72, 보류 10/12로 사전 기준을 실패해 미채택했다. [v0.2-H 결과](V0.2_H_TRAIN_AND_DEV72_RESULT.md)를 따른다.
29. 완료: 빈 입력·잡음·명백한 비일본어를 사전 라우팅하고 STT 표기는 advisory로 분리하는 경계 게이트 v0.1을 구현했다.
30. 완료: D/H 기존 run에 라벨 비의존 replay를 수행했다. D는 판단 70/72·보류 12/12·과교정 0/33, H는 구조 72/72·판단 70/72·보류 12/12지만 과교정 1/33이다. [경계 게이트 결과](DETERMINISTIC_BOUNDARY_GATE_V0.1_RESULT.md)를 따른다.
31. 완료: 실제 저장 STT 적격 340건을 읽기 전용·무모델·비식별 집계로 dry-run했다. bypass와 advisory는 0건, DB 해시와 judgment_results는 불변이었다.
32. 보류: adversarial 경계 세트 확대는 실제 340건에서 개입 0건이므로 운영 핵심 경로에서 제외했다.
33. 완료: 비교정 원문 보존 위반에만 1회 재시도하고 기존 50건 snapshot을 제외한 실제 STT 100건 shadow를 실행했다. 최종 계약 99/100, 재시도 1건·회복 0건, 성공 p95 1108.711ms로 제한적 staging/shadow 기준을 통과했다. [100건 shadow 결과](JUDGMENT_D_SHADOW_V0.2_RESULT.md)를 따른다.
34. 완료: 기존 shadow 150건을 제외한 실제 STT 30건 독립 품질 검수 표본을 예측 비노출로 봉인했다. 실제 음성 파일이 없어 발음/STT 귀속은 판단 불가로 잠갔다. [검수 가이드](../../evaluation/judgment/QUALITY_REVIEW_V0.1_GUIDE.md)를 따른다.
35. 보류: private review JSONL 30건의 사람 라벨과 음성·발음 평가는 사용자 결정에 따라 후순위로 둔다. 표본은 봉인 상태와 모델 추론 0회를 유지한다.
36. 완료: 추가 학습 없이 v0.2-D의 제한적 staging 실행 안전성을 검증했다. `/tmp` 복제 DB의 live 사전점검과 POST/GET은 통과했고 원본 DB 해시·행 수는 불변이며 서버는 종료했다. 재현 절차는 [`docs/JUDGMENT_STAGING_RUNBOOK.md`](../../docs/JUDGMENT_STAGING_RUNBOOK.md)를 따른다.

현재 파일럿은 일본어 전문가 인증본이 아니며, 구조 검증 통과를 언어학적 정확성으로 해석하지 않는다.

37. 완료: 원문·발화 ID·문맥·원시 오류를 수집하지 않는 프로세스 로컬 `GET /health/judgment` 집계와 사전점검 경로를 추가했다. 기능 플래그 기본 비활성과 staging 범위는 유지한다.

38. 완료: 커밋을 학습 이후로 보류하는 동안 원시 실행·DB·가중치·오디오·대용량 파일의 혼입과 보호 해시 변경을 차단하는 읽기 전용 체크포인트 감사 도구를 추가했다.

39. 완료: 합성 1,000이벤트·16 worker로 상태 집계 동시성을 확인하고 timeout·재시도 재실패·DB 저장 실패를 주입해 503·미저장·익명 실패 집계를 검증했다. [staging 장애 결과](STAGING_RESILIENCE_RESULT.md)를 따른다.

40. 완료: 격리 SQLite와 합성 입력으로 실제 FastAPI–vLLM D LoRA 경로를 동시성 1/2/4에서 측정했다. 측정 26/26건이 HTTP 200·계약을 통과했고 동시성 4 p95 867.775ms, 4.786 req/s였다. [staging 실부하 결과](STAGING_HTTP_LOAD_RESULT.md)를 따른다.

41. 완료: 프로세스별 동시 판단 상한·즉시 429 backpressure·모델 alias readiness·종료 drain을 추가했다. 상한 2의 live 동시성 8 실험에서 2건 성공, 14건 429, 모델/DB 실패 0건을 확인했다. [staging 런타임 안전 결과](STAGING_RUNTIME_SAFETY_RESULT.md)를 따른다.

42. 완료: 동시성 2로 150건을 57.519초간 지속 실행해 150/150 계약 성공, p95 850.022ms를 확인했다. vLLM 중단 시 readiness 503, 재기동 후 API 재시작 없이 200 복구와 실제 판단 성공을 검증했다. [단기 soak·복구 결과](STAGING_SOAK_RECOVERY_RESULT.md)를 따른다.

43. 완료: sudo 없는 사용자 systemd로 vLLM과 단일-worker API를 설치·실기동했다. live 사전점검, readiness 200→503→200 복구, 합성 판단 POST/GET을 통과했고 종료 후 환경·격리 DB·포트·GPU를 초기 상태로 복원했다. `Linger=no`이므로 로그인 세션 staging 범위만 인정한다. [배포 서비스 결과](STAGING_DEPLOYMENT_TEMPLATE_RESULT.md)를 따른다.

44. 완료: 사용자 staging의 환경·서비스 전환을 원자적 fail-closed 관리기로 묶었다. start/status/stop 실기동과 전체 live 사전점검을 통과했고 판단 요청 없이 DB·포트·GPU 불변 상태로 종료했다. 상세는 [배포 서비스 결과](STAGING_DEPLOYMENT_TEMPLATE_RESULT.md)를 따른다.

45. 완료: 기존 `/analyze` 응답·분석 저장을 변경하지 않는 background shadow를 별도 기본 비활성 플래그로 연결했다. 합성 인사 live 호출에서 응답 34.087ms, shadow 성공 742.162ms, 판단 저장 0건과 익명 집계를 확인했다. [shadow 통합 결과](STAGING_ANALYZE_SHADOW_RESULT.md)를 따른다.

46. 완료: 동일 합성 입력 26건으로 shadow OFF/ON을 비교해 기존 `/analyze` HTTP·계약 26/26과 판단 저장 0건을 재확인했다. ON에서는 2건만 모델 호출에 성공하고 24건이 안전하게 `overloaded`로 폐기돼, 현재 background 방식은 응답 보호에는 성공했지만 대표성 있는 수집 용량은 부족하다. [OFF/ON 부하 결과](STAGING_ANALYZE_SHADOW_LOAD_RESULT.md)를 따른다.

47. 완료: 최대 64건·TTL 30초·단일 consumer·종료 drain을 갖는 프로세스 로컬 shadow 큐를 구현했다. 동일 burst에서 예약·enqueue·모델 성공 26/26, drop 0건이며 큐 대기 p95는 14.88초였다. [shadow 큐 결과](STAGING_ANALYZE_SHADOW_QUEUE_RESULT.md)를 따른다.

48. 완료: 0.5·1·2·10 req/s 합성 rate probe를 실행했다. 낮은 세 구간은 drop 0, 10 req/s 80건은 응답 80/80을 유지하면서 queue full 3건·TTL 만료 16건으로 제한됐다. [rate probe 결과](STAGING_ANALYZE_SHADOW_RATE_RESULT.md)를 따른다.

49. 완료: 큐 앞에 1 req/s·burst 1의 내용·사용자 비의존 token bucket을 추가했다. 0.5·1·2·10 req/s 총 100건에서 응답 100/100, shadow 성공 23건, sampled out 77건, failure/drop 0건을 확인했다. [admission 결과](STAGING_ANALYZE_SHADOW_ADMISSION_RESULT.md)를 따른다.

50. 완료: D 748문항에 F 보강분 120문항만 결합한 v0.2-I를 동일 seed 42·45-step으로 학습했다. I는 허용 교정문 20/27·복합 오류 1/4로 소폭 개선됐지만 구조 71/72·과교정 1/33·판단 67/72·보류 9/12로 안전 기준을 실패해 미채택했다. [v0.2-I 결과](V0.2_I_TRAIN_AND_DEV72_RESULT.md)를 따른다.

51. 완료: 소비된 v0.3에서 사후 관측된 F 단독 우위를 새 시험지에서 정식 검증하도록 v0.4 D/F 단독 비교 규약을 추론 전에 고정했다. 두 후보를 각 1회 실행하며 절대 안전 기준과 F 승격 조건을 결과 확인 전에 봉인했다. [실행 규약](V0.2_DF_HOLDOUT_V0.4_PROTOCOL.md)을 따른다.

52. 완료: 규약 커밋 `e84fb74` 이후 D/F를 v0.4에서 각각 정확히 한 번 실행했다. D는 구조 120/120·과교정 0/50·허용 교정 32/50, F는 구조 119/120·과교정 1/50·허용 교정 36/50이었다. 둘 다 사전 40/50 자격 기준에 미달해 선택 모델은 없다. [v0.4 결과](V0.2_DF_HOLDOUT_V0.4_RESULT.md)를 따른다.

53. 완료: v0.2-J 학습 전에 최종 `holdout_v0.5` 120문항을 생성했다. 정확 중복과 3-gram 0.85 이상 근접 중복은 0건이고 SHA-256은 `b4b7ed63ccbd9008a7fa5544a3a494af20843e3accb4f6917700504b32ae6963`다. 모델 추론은 0회다.

54. 완료: D의 기존 학습 594건에 소비된 v0.4 120건을 한 번씩 더한 v0.2-J 학습 노출 714건과 기존 개발 154건을 고정했다. v0.4의 `……` 한 건은 D와 의미 라벨이 같은 의도적 재노출로 기록했고, v0.5는 해시만 검사해 추론 0회를 유지했다.

55. 완료: v0.2-J를 seed 42·45-step으로 학습했다. train loss 0.705419, eval loss 0.321254, 어댑터 SHA-256은 `b9f5bb39069ed002690d36d850f26b8a4b1519568230bb473311c84b1a34efb6`다.

56. 다음: 어댑터 해시와 절대 기준을 포함한 v0.5 규약 체크포인트 이후 J를 정확히 한 번 실행하고, 통과 여부와 관계없이 LoRA 반복을 종료한다.
