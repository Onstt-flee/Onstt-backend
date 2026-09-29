# Japanese STT Conversation API

라즈베리파이에서 생성한 일본어 STT 결과를 GPU 서버에 저장하고, 저장된 발화를 조회하거나 일본어 문장 분석/교정 결과를 관리하는 FastAPI 기반 백엔드입니다.

이 프로젝트는 음성 파일을 직접 STT로 변환하는 서버가 아니라, 외부 STT 클라이언트가 만든 결과를 받아 저장하고 후속 분석을 수행하는 API 서버입니다.

## 현재 개발 상태와 문서 안내

기준일은 2026-09-29입니다. 기존 API 오류 수정과 Python 3.12.3 환경 재구성, 판단모델 데이터·실행기·채점기 및 D/E LoRA 실험을 완료했습니다. 동결한 `holdout_v0.2` 120문항을 단 한 번 실행한 결과, D가 과교정 2/50으로 안전 기준(최대 1/50)을 실패했고 조건부 D+E 게이트도 교정문 개선이 0건이었습니다. 따라서 운영 API 통합을 중단했으며, 실패 분석에 따른 v0.2-F 설계와 새 `holdout_v0.3` 봉인을 완료했습니다.

현재 선택은 다음과 같습니다.

- 첫 판단 전용 LoRA 학습 베이스: `Qwen/Qwen3-4B-Instruct-2507`
- 보조 스케일 비교 모델: `Qwen/Qwen3-8B`
- 고용량 정확도 상한 기준선: `Qwen/Qwen3-14B`
- 운영 투입 승인 모델: 없음
- 현재 단계: `holdout_v0.2` 소비 완료·운영 채택 실패. v0.2-F 학습 전 `holdout_v0.3` 봉인 완료

현재 운영 `analyzer`는 기존 이진 분석 계약을 사용합니다. 평가에서 사용한 3단계 판단 계약과 선택 모델은 아직 Swagger 또는 운영 API에 통합하지 않았습니다.

### 작업 단계별 기준 문서

| 작업 과정 | 우선 참고할 Markdown | 용도 |
| --- | --- | --- |
| 전체 진행 현황·완료/미완료 구분 | [`PROGRESS.md`](PROGRESS.md) | 매 작업 후 계속 갱신하는 단일 진행 현황 문서 |
| 평가셋 구성·실행기·채점기 사용법 | [`evaluation/judgment/README.md`](evaluation/judgment/README.md) | 72문항, 출력 계약, 재현 명령과 평가 이력 |
| LoRA 파일럿 데이터·검수·내보내기 | [`training/judgment/README.md`](training/judgment/README.md) | 300문항 구성, 생성 근거, 검증 명령과 검수 승인 게이트 |
| provisional LoRA 실험 결과 | [`training/judgment/PILOT_V0.1_RESULT.md`](training/judgment/PILOT_V0.1_RESULT.md) | Qwen3-4B provisional 학습 조건, 실패 분석과 해시 |
| reviewed LoRA 평가 결과 | [`training/judgment/REVIEWED_V0.1_RESULT.md`](training/judgment/REVIEWED_V0.1_RESULT.md) | 사용자 검수 데이터 학습, 3모델 비교, 과교정 분석 |
| 최소대립쌍 v0.2-B 평가 결과 | [`training/judgment/HARD_NEGATIVES_V0.2_B_RESULT.md`](training/judgment/HARD_NEGATIVES_V0.2_B_RESULT.md) | 540문항 학습, 4모델 비교, 개선·회귀 사례와 채택 판단 |
| 실패 집중 v0.2-C·blind 평가 결과 | [`training/judgment/FAILURE_FOCUS_V0.2_C_RESULT.md`](training/judgment/FAILURE_FOCUS_V0.2_C_RESULT.md) | 출력 계약 v0.2, 628문항 학습, 150문항 holdout과 운영 보류 근거 |
| 동일 계약 v0.2-B 대조군 비교 | [`training/judgment/CONTRACT_CONTROL_V0.2_B_RESULT.md`](training/judgment/CONTRACT_CONTROL_V0.2_B_RESULT.md) | 출력 계약 변경과 추가 데이터 효과 분리, 72문항 대조와 공통 실패 유형 |
| 새 미사용 시험지·v0.2-D 설계 | [`training/judgment/V0.2_D_DESIGN.md`](training/judgment/V0.2_D_DESIGN.md) | 120문항 봉인·중복 감사, 보강 범위와 평가 순서 |
| v0.2-D 학습 데이터 생성 결과 | [`training/judgment/V0.2_D_DATA_RESULT.md`](training/judgment/V0.2_D_DATA_RESULT.md) | 추가 120문항·결합 748문항, 출력 계약과 누수 감사·해시 |
| v0.2-D 45-step LoRA 학습 결과 | [`training/judgment/V0.2_D_TRAIN_RESULT.md`](training/judgment/V0.2_D_TRAIN_RESULT.md) | 동일 하이퍼파라미터, 손실·가중치 해시 |
| v0.2-C↔D 개발셋 비교·회귀 분석 | [`training/judgment/V0.2_D_DEV72_COMPARISON.md`](training/judgment/V0.2_D_DEV72_COMPARISON.md) | 동일 조건 72문항 비교, 교정문 회귀와 holdout 보류 근거 |
| v0.2-E 교정문 회귀 보강 설계·데이터 | [`training/judgment/V0.2_E_DESIGN_AND_DATA.md`](training/judgment/V0.2_E_DESIGN_AND_DATA.md) | 추가 80문항·결합 828문항, 누수 감사·해시와 사전 채택 기준 |
| v0.2-E 학습·C/D/E 개발셋 결과 | [`training/judgment/V0.2_E_TRAIN_AND_DEV72_RESULT.md`](training/judgment/V0.2_E_TRAIN_AND_DEV72_RESULT.md) | 45-step 학습 해시, 교정 회복·안전성 회귀와 채택 보류 근거 |
| D 판단+E 교정 후보 게이트 | [`training/judgment/V0.2_DE_CANDIDATE_GATE_RESULT.md`](training/judgment/V0.2_DE_CANDIDATE_GATE_RESULT.md) | 정답 비사용 선택 규칙, 개발셋 개선·한계와 holdout 전 조건 |
| 최종 holdout 실행 규약 | [`evaluation/judgment/holdout_v0.2.protocol.json`](evaluation/judgment/holdout_v0.2.protocol.json) | D/E 어댑터·프롬프트·선택기 해시와 단일 실행·채택 임계값 |
| 소비된 holdout v0.2 최종 결과 | [`training/judgment/V0.2_DE_HOLDOUT_V0.2_RESULT.md`](training/judgment/V0.2_DE_HOLDOUT_V0.2_RESULT.md) | D 안전 기준 실패, 게이트 개선 0건, API 통합 중단 근거 |
| v0.2-F 보강 설계·새 시험지 | [`training/judgment/V0.2_F_DESIGN.md`](training/judgment/V0.2_F_DESIGN.md) | 실패 유형 보강 범위와 `holdout_v0.3` 봉인·사용 금지 조건 |
| 문법 판단 경계 정의 | [`evaluation/judgment/BOUNDARY_GUIDELINES.md`](evaluation/judgment/BOUNDARY_GUIDELINES.md) | 필러·문체·표기·STT·문맥 판단 원칙 |
| 사람 검수 절차 | [`evaluation/judgment/REVIEW_PROCESS.md`](evaluation/judgment/REVIEW_PROCESS.md) | 사용자 검수와 전문가 검수의 구분 및 절차 |
| 최종 검수 기준·주의 사례 | [`evaluation/judgment/FINAL_REVIEW_GUIDE.md`](evaluation/judgment/FINAL_REVIEW_GUIDE.md) | 추측 교정 금지, 번역·복구·스타일 분리 원칙 |
| 72문항 전체 검수 내용 | [`evaluation/judgment/REVIEW.md`](evaluation/judgment/REVIEW.md) | 문항별 원문·판단·교정문 확인 |
| 베이스 모델 비교·최종 후보 선정 | [`evaluation/judgment/FINAL_MODEL_SELECTION.md`](evaluation/judgment/FINAL_MODEL_SELECTION.md) | 11개 모델 평가 기준, 결과와 4B·8B·14B 역할 |
| 검수용 Excel·PDF 안내 | [`evaluation/judgment/review_materials/README.md`](evaluation/judgment/review_materials/README.md) | 검수표와 배포용 검수 문서 설명 |
| 현재 구조와 목표 구조 비교 | [`docs/architecture/SYSTEM_ARCHITECTURE_FUTURE_VS_GITHUB.md`](docs/architecture/SYSTEM_ARCHITECTURE_FUTURE_VS_GITHUB.md) | 운영·평가·검수 경로 분리와 단계별 전환 설계 |

문서 갱신 원칙은 다음과 같습니다.

1. 작업을 완료할 때마다 `PROGRESS.md`의 완료 상태와 다음 단계를 갱신합니다.
2. 평가 데이터·계약·실행 방법이 바뀌면 `evaluation/judgment/README.md`를 함께 갱신합니다.
3. 모델을 추가 실행하거나 후보 판단이 바뀌면 `FINAL_MODEL_SELECTION.md`와 모델별 `results/*.json`을 갱신합니다.
4. 운영 구조·API·DB 경계가 바뀔 때만 아키텍처 Markdown과 PDF를 다시 생성합니다.
5. 이 루트 README에는 최신 요약과 문서 경로만 유지하고, 상세 실험 기록은 각 기준 문서에 남깁니다.

## 역할 요약

- 라즈베리파이: 음성 녹음, 음성 전처리, STT 실행
- `stt_api`: STT 결과 저장, 세션/발화 조회, 전처리 결과 업데이트, 일본어 문장 분석
- 로컬 LLM 서버: 일본어 문장 교정 및 피드백 생성
- SQLite DB: 사용자, 세션, 발화, 분석 결과 저장

## 주요 기능

- 사용자 생성
- 회화 세션 생성
- STT 발화 저장
- 세션별 발화 조회
- 특정 발화 조회
- 텍스트 전처리 결과 업데이트
- 일본어 문장 타입 분류
- RAG 기반 문법/단어/예문/오류 패턴 참고 자료 검색
- 로컬 OpenAI 호환 LLM을 통한 문장 교정
- 분석 결과 저장 및 조회

## 디렉터리 구조

```text
stt_api/
├── main.py                    # FastAPI 앱 진입점 및 API 라우트
├── database.py                # SQLite 연결 및 DB 세션 관리
├── models.py                  # SQLAlchemy ORM 모델
├── schemas.py                 # Pydantic 요청/응답 스키마
├── crud.py                    # DB 생성/조회/수정 로직
├── stt_data.db                # SQLite 데이터베이스
├── requirements.txt           # Python 의존성
├── analyzer/
│   ├── pipeline.py            # 전체 분석 파이프라인
│   ├── rule_filter.py         # 입력 검증 및 정규화
│   ├── sentence_classifier.py # 문장 타입 분류
│   ├── vocab_retriever.py     # 단어 DB 검색
│   ├── grammar_retriever.py   # 문법 규칙 검색
│   ├── error_retriever.py     # 오류 패턴 검색
│   ├── example_retriever.py   # TF-IDF 기반 예문 검색
│   ├── prompt_builder.py      # LLM 프롬프트 생성
│   ├── llm_client.py          # OpenAI 호환 LLM 서버 호출
│   └── llm_parser.py          # LLM 응답 JSON 파싱 및 후처리
├── rag_data/
│   ├── vocab/
│   │   ├── n5_raw.csv
│   │   └── word_db.json
│   ├── grammar/
│   │   └── grammar_rules.json
│   ├── errors/
│   │   └── error_patterns.json
│   └── examples/
│       ├── texts.json
│       └── tfidf.pkl
└── scripts/
    ├── build_word_db.py       # 단어 DB 생성 스크립트
    └── build_example_tfidf.py # 예문 TF-IDF 인덱스 생성 스크립트
```

## 실행 방법

가상환경이 이미 포함되어 있다면 다음처럼 실행할 수 있습니다.

```bash
cd /home/cap-minsung/stt_api
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

새 환경에서 설치하는 경우:

```bash
cd /home/cap-minsung/stt_api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

서버 실행 후 문서 페이지:

```text
http://localhost:8000/docs
```

## 의존성

주요 의존성은 다음과 같습니다.

- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `pydantic`

분석 파이프라인의 예문 검색에서는 `tfidf.pkl`을 로드합니다. 이 pickle은 생성 당시의 Python/scikit-learn 환경에 의존할 수 있으므로, 환경을 새로 구성할 때 예문 검색 쪽 의존성도 함께 확인해야 합니다.

## API 목록

### 서버 상태 확인

```http
GET /health
```

응답 예:

```json
{
  "status": "ok",
  "message": "STT API server is running"
}
```

### 사용자 생성

```http
POST /users
```

요청 예:

```json
{
  "name": "minsung",
  "level": "N5"
}
```

응답에는 `user_id`, `name`, `level`, `created_at`이 포함됩니다.

### 회화 세션 생성

```http
POST /sessions
```

요청 예:

```json
{
  "user_id": 1,
  "topic": "일상 대화",
  "description": "라즈베리파이 기반 일본어 STT 테스트 세션"
}
```

### 사용자별 세션 목록 조회

```http
GET /users/{user_id}/sessions
```

특정 사용자의 회화 세션 목록을 반환합니다.

### STT 발화 저장

```http
POST /utterances
```

요청 예:

```json
{
  "session_id": 1,
  "raw_audio_path": "/home/pi/audio/raw/utt_001.wav",
  "audio_path": "/home/pi/audio/processed/utt_001.wav",
  "stt_text": "今日学校行きました",
  "language": "ja",
  "duration": 3.42,
  "stt_model": "faster-whisper-small",
  "preprocess_status": "done",
  "sample_rate": 16000,
  "channels": 1,
  "audio_format": "wav"
}
```

이 API는 음성 인식을 수행하지 않습니다. 이미 생성된 STT 결과인 `stt_text`와 관련 메타데이터를 저장합니다.

### 특정 발화 조회

```http
GET /utterances/{utterance_id}
```

특정 발화의 STT 원문, 전처리 텍스트, 토큰, 오디오 경로, 모델 정보 등을 조회합니다.

### 세션별 발화 목록 조회

```http
GET /sessions/{session_id}/utterances
```

특정 세션에 속한 모든 발화를 반환합니다.

### 텍스트 전처리 결과 업데이트

```http
PATCH /utterances/{utterance_id}/preprocess
```

요청 예:

```json
{
  "processed_text": "今日 学校 行きました",
  "normalized_text": "今日学校行きました",
  "tokens": ["今日", "学校", "行きました"]
}
```

`tokens`는 DB에는 JSON 문자열 형태로 저장됩니다.

### 발화 분석 실행

```http
POST /utterances/{utterance_id}/analyze
```

분석 대상 텍스트는 다음 우선순위로 선택됩니다.

1. `processed_text`
2. `normalized_text`
3. `stt_text`

분석 결과는 `analyses` 테이블에 저장되고, 저장된 분석 객체가 응답으로 반환됩니다.

### 발화 분석 결과 조회

```http
GET /utterances/{utterance_id}/analysis
```

특정 발화에 대해 수행된 분석 결과 목록을 최신순으로 반환합니다.

## 데이터베이스 구조

SQLite DB 파일은 다음 경로를 사용합니다.

```text
stt_api/stt_data.db
```

연결 설정은 `database.py`의 `DATABASE_URL = "sqlite:///./stt_data.db"`에 정의되어 있습니다.

### `users`

사용자 정보를 저장합니다.

| 컬럼 | 설명 |
| --- | --- |
| `id` | 사용자 ID |
| `name` | 사용자 이름 |
| `level` | 일본어 레벨 |
| `created_at` | 생성 시각 |

### `sessions`

회화 세션 정보를 저장합니다.

| 컬럼 | 설명 |
| --- | --- |
| `id` | 세션 ID |
| `user_id` | 사용자 ID |
| `topic` | 세션 주제 |
| `description` | 세션 설명 |
| `created_at` | 생성 시각 |

### `utterances`

STT 발화 데이터를 저장합니다.

| 컬럼 | 설명 |
| --- | --- |
| `id` | 발화 ID |
| `session_id` | 세션 ID |
| `raw_audio_path` | 원본 오디오 경로 |
| `audio_path` | 전처리된 오디오 경로 |
| `stt_text` | STT 결과 텍스트 |
| `processed_text` | 전처리된 텍스트 |
| `normalized_text` | 정규화된 텍스트 |
| `tokens` | 토큰 목록을 JSON 문자열로 저장 |
| `language` | 언어 코드, 기본값 `ja` |
| `duration` | 오디오 길이 |
| `stt_model` | STT 모델명 |
| `preprocess_status` | 전처리 상태 |
| `sample_rate` | 샘플레이트 |
| `channels` | 채널 수 |
| `audio_format` | 오디오 포맷 |
| `created_at` | 생성 시각 |
| `updated_at` | 수정 시각 |

### `analyses`

문장 분석 및 교정 결과를 저장합니다.

| 컬럼 | 설명 |
| --- | --- |
| `id` | 분석 ID |
| `utterance_id` | 발화 ID |
| `primary_type` | 대표 문장 타입 |
| `candidate_types` | 후보 문장 타입 목록 |
| `classification_reason` | 분류 이유 |
| `needs_deep_analysis` | LLM 분석 필요 여부 |
| `is_correct` | 문장이 자연스러운지 여부 |
| `corrected_text` | 교정 문장 |
| `error_types` | 오류 유형 목록 |
| `feedback_ko` | 한국어 피드백 |
| `feedback_ja` | 일본어 피드백 |
| `vocab_context` | 단어 RAG 문맥 |
| `grammar_context` | 문법 RAG 문맥 |
| `example_context` | 예문 RAG 문맥 |
| `error_context` | 오류 패턴 RAG 문맥 |
| `model_name` | 분석에 사용된 LLM 모델명 |
| `adapter_name` | 어댑터명 |
| `confidence` | 신뢰도 |
| `created_at` | 생성 시각 |

## 분석 파이프라인

분석의 중심 함수는 `analyzer/pipeline.py`의 `analyze(text)`입니다.

### 1. 입력 검증

`analyzer/rule_filter.py`에서 입력을 정규화하고 분석 가능 여부를 판단합니다.

검증 내용:

- 빈 문자열 여부
- 일본어 문자 포함 여부
- 한국어/영어만 있는 입력 여부
- 너무 짧은 STT 실패성 입력 여부

일본어 문자는 히라가나, 가타카나, 한자 범위를 기준으로 확인합니다.

### 2. 문장 타입 분류

`analyzer/sentence_classifier.py`에서 문장 타입 후보를 추출하고 대표 타입을 선택합니다.

지원 타입:

- `invalid`
- `question`
- `request`
- `greeting`
- `emotion`
- `statement`
- `fragment`

예를 들어 `こんにちは`, `おはよう`, `ありがとう` 같은 패턴은 `greeting`으로 분류됩니다.

### 3. 조기 반환

다음 타입은 LLM을 호출하지 않고 룰 기반 결과를 바로 반환합니다.

- `invalid`: 일본어 문장으로 판단하기 어려움
- `greeting`: 자연스러운 인사 표현
- `fragment`: 단어 또는 짧은 발화

이 구조는 불필요한 LLM 호출과 과교정을 줄이기 위한 장치입니다.

### 4. RAG 참고 자료 검색

일반 문장으로 판단되면 다음 참고 자료를 검색합니다.

- `vocab_retriever.py`: 입력 문장에 포함된 단어 검색
- `grammar_retriever.py`: 문법 규칙 검색
- `error_retriever.py`: 오류 패턴 검색
- `example_retriever.py`: TF-IDF 기반 유사 예문 검색

이 검색 결과들은 오류 확정이 아니라 LLM이 판단할 때 참고하는 문맥입니다.

### 5. 프롬프트 생성

`analyzer/prompt_builder.py`에서 입력 문장, 문장 타입, RAG 문맥을 합쳐 LLM 프롬프트를 생성합니다.

프롬프트는 다음 원칙을 강조합니다.

- 자연스러운 일본어인지 판단
- 의미를 바꾸지 않는 최소 교정
- 정상 문장, 인사 표현, 단편 발화 과교정 방지
- 오류 유형은 제공된 코드 안에서만 선택
- JSON만 반환

### 6. LLM 호출

`analyzer/llm_client.py`는 OpenAI 호환 Chat Completions API를 호출합니다.

기본 설정:

```text
endpoint: http://localhost:1234/v1/chat/completions
model: qwen/qwen3-4b-2507
temperature: 0.2
max_tokens: 512
timeout: 120
```

따라서 분석 API를 정상적으로 사용하려면 로컬 또는 같은 서버에서 OpenAI 호환 LLM 서버가 `localhost:1234`로 실행 중이어야 합니다.

### 7. LLM 응답 파싱 및 후처리

`analyzer/llm_parser.py`가 LLM 응답을 JSON으로 파싱하고 결과를 보정합니다.

처리 내용:

- 코드블록으로 감싸진 JSON 제거
- 앞뒤 설명문이 섞인 응답에서 JSON 객체 추출
- `is_correct`, `confidence`, `error_types` 타입 보정
- 원문과 교정문이 같으면 오류 유형 제거
- 원문과 교정문이 다르면 `is_correct = false`로 보정
- 일부 대표 패턴의 오류 유형 재분류

후처리에서 다루는 대표 오류 유형:

- `particle_omission`
- `particle_misuse`
- `verb_conjugation_error`
- `tense_error`
- `word_choice_error`
- `unnatural_expression`
- `overcorrection_risk`
- `non_japanese_input`
- `fragment`

## RAG 데이터

### 단어 데이터

```text
rag_data/vocab/word_db.json
rag_data/vocab/n5_raw.csv
```

입력 문장에 포함된 단어의 표기, 읽기, 의미, JLPT 레벨을 참고 자료로 제공합니다.

### 문법 규칙

```text
rag_data/grammar/grammar_rules.json
```

입력 문장과 관련 있을 수 있는 문법 규칙을 검색합니다. 이 결과는 교정 지시가 아니라 판단 참고 자료입니다.

### 오류 패턴

```text
rag_data/errors/error_patterns.json
```

가능한 오류 유형을 판단하기 위한 참고 자료입니다. 실제 오류 확정은 LLM과 후처리 단계에서 이루어집니다.

### 예문 검색

```text
rag_data/examples/texts.json
rag_data/examples/tfidf.pkl
```

TF-IDF cosine similarity 기반으로 입력 문장과 유사한 예문을 검색합니다.

## 일반 요청 흐름

라즈베리파이 또는 클라이언트가 사용할 때의 일반적인 흐름은 다음과 같습니다.

1. `POST /users`로 사용자 생성
2. `POST /sessions`로 회화 세션 생성
3. 라즈베리파이에서 음성 녹음 및 STT 실행
4. `POST /utterances`로 STT 결과 저장
5. 필요 시 `PATCH /utterances/{utterance_id}/preprocess`로 전처리 결과 저장
6. `POST /utterances/{utterance_id}/analyze`로 일본어 문장 분석 실행
7. `GET /utterances/{utterance_id}/analysis`로 분석 결과 조회

## 분석 결과 예시

분석 결과는 대략 다음 형태로 저장됩니다.

```json
{
  "id": 1,
  "utterance_id": 10,
  "primary_type": "statement",
  "candidate_types": "[{\"type\": \"statement\", \"score\": 0.7}]",
  "classification_reason": "후보 타입 statement 중 대표 타입을 statement으로 선택함",
  "needs_deep_analysis": true,
  "is_correct": false,
  "corrected_text": "今日学校に行きました",
  "error_types": "[\"particle_omission\"]",
  "feedback_ko": "문장에서 필요한 조사가 생략된 부분이 있어 문장 구조가 부자연스러웠습니다.",
  "feedback_ja": "文の中で必要な助詞が省略されている部分があり、文の構造が不自然でした。",
  "model_name": "qwen/qwen3-4b-2507",
  "adapter_name": null,
  "confidence": 0.85,
  "created_at": "2026-06-09T06:18:58"
}
```

## 현재 DB 상태 확인 예시

SQLite CLI로 테이블과 데이터 수를 확인할 수 있습니다.

```bash
cd /home/cap-minsung/stt_api
sqlite3 stt_data.db ".tables"
sqlite3 stt_data.db "select count(*) from utterances;"
sqlite3 stt_data.db "select count(*) from analyses;"
```

## 주의사항

- 이 서버는 실제 STT 추론을 수행하지 않습니다.
- `POST /utterances`는 이미 만들어진 STT 텍스트를 저장하는 API입니다.
- `POST /utterances/{utterance_id}/analyze`를 사용하려면 `localhost:1234`의 OpenAI 호환 LLM 서버가 필요합니다.
- `candidate_types`, `error_types`, `tokens` 등 일부 목록 데이터는 SQLite에는 JSON 문자열로 저장됩니다.
- `models.Base.metadata.create_all(bind=engine)`가 앱 시작 시 실행되므로, 없는 테이블은 자동 생성됩니다. 단, 기존 테이블 스키마 변경 마이그레이션은 처리하지 않습니다.
- 외래키 관계는 모델에 정의되어 있지만 SQLite에서 엄격한 무결성 검증을 기대하려면 별도 설정이 필요할 수 있습니다.
- `rag_data/examples/tfidf.pkl`은 pickle 파일이므로 생성 환경과 실행 환경의 패키지 호환성을 확인해야 합니다.

## 개발 메모

- API 라우트는 `main.py`에 집중되어 있어 구조가 단순합니다.
- DB 접근은 `crud.py`를 통해 수행합니다.
- 분석 로직은 `analyzer/pipeline.py`에서 계층적으로 연결됩니다.
- RAG 검색 함수들은 교정을 직접 수행하지 않고, LLM 판단을 돕는 참고 문맥만 생성합니다.
- LLM 응답이 실패하거나 JSON 파싱에 실패해도 서버가 죽지 않도록 fallback 결과를 반환하는 구조입니다.
