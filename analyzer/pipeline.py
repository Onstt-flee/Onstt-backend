from typing import Dict, Any

from analyzer.rule_filter import validate_input
from analyzer.sentence_classifier import classify_sentence
from analyzer.grammar_retriever import retrieve_grammar_rules
from analyzer.vocab_retriever import retrieve_vocab
from analyzer.error_retriever import retrieve_error_patterns
from analyzer.example_retriever import retrieve_examples
from analyzer.prompt_builder import build_prompt
from analyzer.llm_client import call_llm
from analyzer.llm_parser import parse_llm_response


def analyze(text: str) -> Dict[str, Any]:
    """
    현재 연결된 계층:
    - Layer 1: 입력 검증
    - Layer 2: 문장 타입 분류
    - Layer 3: 단어 RAG 참고 검색
    - Layer 4: 문법 RAG 참고 규칙 검색
    - Layer 5: 예문 RAG 참고 검색
    - Layer 6: 오류 패턴 RAG 참고 검색
    - LLM 프롬프트 생성
    - LLM 호출
    - LLM 응답 JSON 파싱
    - invalid / greeting / fragment 조기 반환
    """

    validation_result = validate_input(text)
    normalized_text = validation_result["normalized_text"]

    classification_result = classify_sentence(
        normalized_text,
        is_valid=validation_result["is_valid"],
    )

    primary_type = classification_result["primary_type"]

    if not validation_result["is_valid"]:
        return {
            "primary_type": primary_type,
            "candidate_types": classification_result["candidate_types"],
            "classification_reason": classification_result["classification_reason"],
            "needs_deep_analysis": False,
            "is_correct": False,
            "corrected_text": normalized_text,
            "error_types": ["non_japanese_input"],
            "feedback_ko": "일본어 문장으로 판단하기 어려운 입력입니다. 일본어 문장을 다시 입력해 주세요.",
            "feedback_ja": "日本語の文として判断しにくい入力です。日本語の文をもう一度入力してください。",
            "vocab_context": "",
            "grammar_context": "",
            "example_context": "",
            "error_context": "",
            "model_name": "rule_based_pipeline",
            "adapter_name": None,
            "confidence": 0.95,
        }

    if primary_type == "greeting":
        return {
            "primary_type": primary_type,
            "candidate_types": classification_result["candidate_types"],
            "classification_reason": classification_result["classification_reason"],
            "needs_deep_analysis": False,
            "is_correct": True,
            "corrected_text": normalized_text,
            "error_types": [],
            "feedback_ko": "자연스러운 일본어 인사 표현입니다. 별도의 교정이 필요하지 않습니다.",
            "feedback_ja": "自然な日本語のあいさつ表現です。特に修正する必要はありません。",
            "vocab_context": "",
            "grammar_context": "",
            "example_context": "",
            "error_context": "",
            "model_name": "rule_based_pipeline",
            "adapter_name": None,
            "confidence": 0.9,
        }

    if primary_type == "fragment":
        return {
            "primary_type": primary_type,
            "candidate_types": classification_result["candidate_types"],
            "classification_reason": classification_result["classification_reason"],
            "needs_deep_analysis": False,
            "is_correct": False,
            "corrected_text": normalized_text,
            "error_types": ["fragment"],
            "feedback_ko": "단어 또는 짧은 발화로 보여 전체 문장 교정은 어렵습니다. 완전한 문장으로 입력하면 더 정확히 분석할 수 있습니다.",
            "feedback_ja": "単語または短い発話のため、文全体の添削は難しいです。完全な文で入力すると、より正確に分析できます。",
            "vocab_context": "",
            "grammar_context": "",
            "example_context": "",
            "error_context": "",
            "model_name": "rule_based_pipeline",
            "adapter_name": None,
            "confidence": 0.85,
        }


    vocab_result = retrieve_vocab(
        normalized_text,
        top_k=20,
    )

    grammar_result = retrieve_grammar_rules(
        normalized_text,
        sentence_type=primary_type,
        top_k=5,
    )

    error_result = retrieve_error_patterns(
        normalized_text,
        primary_type=primary_type,
        top_k=5,
    )

    example_result = retrieve_examples(
        normalized_text,
        top_k=5,
    )

    prompt = build_prompt(
        original_text=normalized_text,
        primary_type=primary_type,
        candidate_types=classification_result["candidate_types"],
        vocab_context=vocab_result["vocab_context"],
        grammar_context=grammar_result["grammar_context"],
        example_context=example_result["example_context"],
        error_context=error_result["error_context"],
    )

    llm_result = call_llm(prompt)


    if not llm_result.get("success"):
        return {
            "primary_type": primary_type,
            "candidate_types": classification_result["candidate_types"],
            "classification_reason": classification_result["classification_reason"],
            "needs_deep_analysis": classification_result["needs_deep_analysis"],
            "is_correct": None,
            "corrected_text": normalized_text,
            "error_types": [],
            "feedback_ko": f"입력 검증과 RAG 검색은 완료되었지만 LLM 호출에 실패했습니다. 원인: {llm_result.get('error')}",
            "feedback_ja": "入力検証とRAG検索は完了しましたが、LLMの呼び出しに失敗しました。",
            "vocab_context": vocab_result["vocab_context"],
            "grammar_context": grammar_result["grammar_context"],
            "example_context": example_result["example_context"],
            "error_context": error_result["error_context"],
            "model_name": llm_result.get("model_name"),
            "adapter_name": llm_result.get("adapter_name"),
            "confidence": 0.0,
        }

    parsed_result = parse_llm_response(
        raw_text=llm_result.get("raw_text", ""),
        original_text=normalized_text,
        model_name=llm_result.get("model_name"),
        adapter_name=llm_result.get("adapter_name"),
    )

    return {
        "primary_type": primary_type,
        "candidate_types": classification_result["candidate_types"],
        "classification_reason": classification_result["classification_reason"],
        "needs_deep_analysis": classification_result["needs_deep_analysis"],
        "is_correct": parsed_result["is_correct"],
        "corrected_text": parsed_result["corrected_text"],
        "error_types": parsed_result["error_types"],
        "feedback_ko": parsed_result["feedback_ko"],
        "feedback_ja": parsed_result["feedback_ja"],
        "vocab_context": vocab_result["vocab_context"],
        "grammar_context": grammar_result["grammar_context"],
        "example_context": example_result["example_context"],
        "error_context": error_result["error_context"],
        "model_name": parsed_result["model_name"],
        "adapter_name": parsed_result["adapter_name"],
        "confidence": parsed_result["confidence"],
    }