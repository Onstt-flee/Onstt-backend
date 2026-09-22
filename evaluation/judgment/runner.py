"""Run label-free judgment inputs against an OpenAI-compatible endpoint."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request
import uuid

from evaluation.judgment.dataset import (
    DEFAULT_DATASET,
    ERROR_TYPES,
    load_records,
    model_inputs,
    validate_judgment,
    validate_records,
)


DEFAULT_ENDPOINT = "http://127.0.0.1:1234/v1/chat/completions"
PROMPT_VERSION = "judgment-v0.1"
PROMPT_VERSION_V2 = "judgment-v0.2"
SYSTEM_PROMPT = """당신은 일본어 학습자 발화의 문법 교정 필요성을 판단하는 시스템입니다.
학습자 점수를 매기거나 더 세련된 표현으로 바꾸지 말고, 주어진 텍스트와 문맥만 판단하세요.

반드시 JSON 객체 하나만 출력하고 다음 네 필드만 사용하세요.
{
  "decision": "acceptable | needs_correction | insufficient_evidence",
  "corrected_text": "원문 또는 최소 교정문",
  "edits": [
    {
      "start": 0,
      "end": 1,
      "source": "원문 구간",
      "replacement": "대체 문자열",
      "error_type": "허용 오류 유형"
    }
  ],
  "reason_ko": "짧은 한국어 판단 근거"
}

허용 오류 유형은 particle_misuse, verb_conjugation, adjective_conjugation,
copula_conjugation, modifier_connection, tense_mismatch뿐입니다.

판단 규칙:
1. acceptable이면 corrected_text는 원문과 같고 edits는 빈 배열이어야 합니다.
2. needs_correction이면 의미를 보존하는 최소 교정만 하고 모든 수정 구간을 기록하세요.
3. insufficient_evidence이면 누락된 말을 추측하지 말고 원문을 유지하며 edits를 비우세요.
4. edit 위치는 원문의 Unicode 코드 포인트 기준 0부터 시작하는 [start, end)입니다.
5. edits는 원문 순서로 정렬하고 겹치지 않아야 하며, 모두 적용하면 corrected_text가 되어야 합니다.
6. 문체 취향, 더 자연스러운 대안, 표기 조언, 발음 추정, 질문 관련성을 문법 교정과 섞지 마세요.
7. 원음이 없으면 학습자 발음 오류와 STT 전사 오류 중 하나로 단정하지 마세요.
8. 빈 입력, 잡음뿐인 입력, 누락 구간, 범위 밖 언어는 insufficient_evidence로 처리하세요.
9. JSON 밖의 설명, Markdown 코드 펜스, 추가 필드는 출력하지 마세요."""

SYSTEM_PROMPT_V2 = """당신은 일본어 학습자 발화의 문법 교정 필요성을 판단하는 시스템입니다.
학습자 점수를 매기거나 더 세련된 표현으로 바꾸지 말고, 주어진 텍스트와 문맥만 판단하세요.

반드시 JSON 객체 하나만 출력하고 다음 네 필드만 사용하세요.
{
  "decision": "acceptable | needs_correction | insufficient_evidence",
  "corrected_text": "원문 또는 최소 교정문",
  "error_types": ["허용 오류 유형"],
  "reason_ko": "짧은 한국어 판단 근거"
}

허용 오류 유형은 particle_misuse, verb_conjugation, adjective_conjugation,
copula_conjugation, modifier_connection, tense_mismatch뿐입니다.

판단 규칙:
1. acceptable 또는 insufficient_evidence이면 corrected_text는 원문과 같고 error_types는 빈 배열이어야 합니다.
2. needs_correction이면 의미와 문체를 보존하는 최소 교정만 하고 해당 오류 유형을 중복 없이 기록하세요.
3. 수정 위치는 출력하지 마세요. 위치와 변경 구간은 백엔드가 원문과 corrected_text의 차이로 계산합니다.
4. 문체 취향, 더 자연스러운 대안, 표기 조언, 발음 추정, 질문 관련성을 문법 교정과 섞지 마세요.
5. 원음이 없으면 학습자 발음 오류와 STT 전사 오류 중 하나로 단정하지 마세요.
6. 빈 입력, 잡음뿐인 입력, 누락 구간, 범위 밖 언어는 insufficient_evidence로 처리하세요.
7. JSON 밖의 설명, Markdown 코드 펜스, 추가 필드는 출력하지 마세요."""

PROMPTS = {
    PROMPT_VERSION: SYSTEM_PROMPT,
    PROMPT_VERSION_V2: SYSTEM_PROMPT_V2,
}


Transport = Callable[..., dict[str, Any]]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON constant: {value}")


def build_messages(
    model_input: dict[str, Any],
    prompt_version: str = PROMPT_VERSION,
) -> list[dict[str, str]]:
    """Build messages from the allowlisted input only; IDs and labels are excluded."""
    if set(model_input) != {"text", "context", "learner_level"}:
        raise ValueError("model_input must contain exactly text, context, learner_level")
    if not isinstance(model_input["text"], str):
        raise ValueError("model_input.text must be a string")
    if model_input["context"] is not None and not isinstance(model_input["context"], str):
        raise ValueError("model_input.context must be null or a string")
    if model_input["learner_level"] not in {"N5", "N4"}:
        raise ValueError("model_input.learner_level must be N5 or N4")
    if prompt_version not in PROMPTS:
        raise ValueError(f"unsupported prompt_version: {prompt_version}")
    return [
        {"role": "system", "content": PROMPTS[prompt_version]},
        {"role": "user", "content": _canonical_json(model_input)},
    ]


def build_request(
    model_input: dict[str, Any],
    model: str,
    *,
    temperature: float = 0.0,
    top_p: float = 1.0,
    max_tokens: int = 512,
    prompt_version: str = PROMPT_VERSION,
) -> dict[str, Any]:
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a nonblank string")
    if not 0.0 <= temperature <= 2.0:
        raise ValueError("temperature must be between 0 and 2")
    if not 0.0 < top_p <= 1.0:
        raise ValueError("top_p must be greater than 0 and at most 1")
    if type(max_tokens) is not int or max_tokens <= 0:
        raise ValueError("max_tokens must be a positive integer")
    return {
        "model": model,
        "messages": build_messages(model_input, prompt_version),
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": False,
    }


def parse_model_output(
    raw_text: str,
    original_text: str,
    prompt_version: str = PROMPT_VERSION,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate one model judgment structurally without comparing it to gold labels."""
    try:
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError("Model content is empty")
        parsed = json.loads(
            raw_text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
        if not isinstance(parsed, dict):
            raise ValueError("Model content must be one JSON object")
        if prompt_version == PROMPT_VERSION:
            validate_judgment(parsed, original_text)
            return parsed, None
        if prompt_version != PROMPT_VERSION_V2:
            raise ValueError(f"unsupported prompt_version: {prompt_version}")
        return _normalize_v2_judgment(parsed, original_text), None
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, str(exc)


def _normalize_v2_judgment(
    judgment: dict[str, Any],
    original_text: str,
) -> dict[str, Any]:
    required = {"decision", "corrected_text", "error_types", "reason_ko"}
    if set(judgment) != required:
        raise ValueError(
            "v0.2 judgment must contain exactly decision, corrected_text, "
            "error_types, reason_ko"
        )
    decision = judgment["decision"]
    corrected = judgment["corrected_text"]
    error_types = judgment["error_types"]
    reason = judgment["reason_ko"]
    if decision not in {"acceptable", "needs_correction", "insufficient_evidence"}:
        raise ValueError(f"Invalid decision: {decision!r}")
    if not isinstance(corrected, str):
        raise ValueError("corrected_text must be a string")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason_ko must be nonblank")
    if (
        not isinstance(error_types, list)
        or any(value not in ERROR_TYPES for value in error_types)
        or len(error_types) != len(set(error_types))
    ):
        raise ValueError("error_types must be a unique list of allowed values")
    if decision != "needs_correction":
        if corrected != original_text:
            raise ValueError("Non-correction decisions must preserve input text")
        if error_types:
            raise ValueError("Non-correction decisions must not contain error_types")
        return {
            **judgment,
            "edits": [],
            "classification_review_required": False,
        }
    if not original_text.strip() or not corrected.strip() or corrected == original_text:
        raise ValueError("A correction must change nonblank text")
    if not error_types:
        raise ValueError("A correction must contain at least one error_type")
    opcodes = [
        opcode
        for opcode in SequenceMatcher(
            None, original_text, corrected, autojunk=False
        ).get_opcodes()
        if opcode[0] != "equal"
    ]
    if len(error_types) == len(opcodes):
        assigned = list(error_types)
        review_required = False
    elif len(error_types) == 1:
        assigned = error_types * len(opcodes)
        review_required = False
    else:
        assigned = [
            error_types[index] if index < len(error_types) else None
            for index in range(len(opcodes))
        ]
        review_required = True
    edits = []
    for (_, start, end, target_start, target_end), error_type in zip(opcodes, assigned):
        edits.append({
            "start": start,
            "end": end,
            "source": original_text[start:end],
            "replacement": corrected[target_start:target_end],
            "error_type": error_type,
        })
    return {
        **judgment,
        "edits": edits,
        "classification_review_required": review_required,
    }


def call_endpoint(
    *,
    endpoint: str,
    request_body: dict[str, Any],
    timeout: float,
    api_key: str | None = None,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    """Call once and retain both the OpenAI envelope and assistant content."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        endpoint,
        data=_canonical_json(request_body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    started = time.perf_counter()
    try:
        with opener(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            raw_response = response.read().decode("utf-8", errors="replace")
        envelope = json.loads(
            raw_response,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
        content = envelope["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("choices[0].message.content must be a string")
        usage = envelope.get("usage") if isinstance(envelope, dict) else None
        return {
            "transport_success": True,
            "http_status": status,
            "raw_text": content,
            "raw_response": raw_response,
            "usage": usage if isinstance(usage, dict) else None,
            "error": None,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    except urllib.error.HTTPError as exc:
        raw_response = exc.read().decode("utf-8", errors="replace")
        error = f"HTTP {exc.code}: {exc.reason}"
        status = exc.code
    except urllib.error.URLError as exc:
        raw_response = ""
        error = f"Connection error: {exc.reason}"
        status = None
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        error = f"Invalid server response: {exc}"
        status = locals().get("status")
    except Exception as exc:  # pragma: no cover - defensive external boundary
        raw_response = ""
        error = f"Unexpected transport error: {exc}"
        status = None
    return {
        "transport_success": False,
        "http_status": status,
        "raw_text": "",
        "raw_response": locals().get("raw_response", ""),
        "usage": None,
        "error": error,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _validate_endpoint(endpoint: str) -> None:
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("endpoint must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("endpoint must not contain credentials, query, or fragment")


def _select_inputs(
    exported: list[dict[str, Any]],
    selected_ids: list[str] | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("limit must be a positive integer")
    if selected_ids:
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError("duplicate --id values are not allowed")
        known = {row["id"] for row in exported}
        unknown = sorted(set(selected_ids) - known)
        if unknown:
            raise ValueError("unknown IDs: " + ", ".join(unknown))
        selected_id_set = set(selected_ids)
        selected = [row for row in exported if row["id"] in selected_id_set]
    else:
        selected = list(exported)
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise ValueError("no inputs selected")
    return selected


def _safe_model_name(model: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", model).strip("-")
    return value[:64] or "model"


def _artifact_paths(output_path: Path) -> tuple[Path, Path]:
    partial = output_path.with_name(f".{output_path.name}.partial")
    manifest = output_path.with_name(f"{output_path.name}.manifest.json")
    return partial, manifest


def run_evaluation(
    *,
    dataset_path: Path,
    endpoint: str,
    model: str,
    output_path: Path,
    selected_ids: list[str] | None = None,
    limit: int | None = None,
    temperature: float = 0.0,
    top_p: float = 1.0,
    max_tokens: int = 512,
    prompt_version: str = PROMPT_VERSION,
    timeout: float = 120.0,
    api_key: str | None = None,
    overwrite: bool = False,
    transport: Transport = call_endpoint,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Execute a run and atomically publish its JSONL and manifest."""
    dataset_path = Path(dataset_path).resolve()
    output_path = Path(output_path).resolve()
    _validate_endpoint(endpoint)
    if output_path == dataset_path:
        raise ValueError("output_path must not overwrite the dataset")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
        raise ValueError("timeout must be positive")

    records = load_records(dataset_path)
    validate_records(records)
    if any(row["review"]["status"] == "provisional" for row in records):
        raise ValueError("model runs require a dataset without provisional labels")
    selected = _select_inputs(model_inputs(records), selected_ids, limit)
    generation = {
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    build_request(
        selected[0]["input"], model,
        prompt_version=prompt_version, **generation,
    )

    partial_path, manifest_path = _artifact_paths(output_path)
    existing = [
        path for path in (output_path, partial_path, manifest_path) if path.exists()
    ]
    if existing and not overwrite:
        raise FileExistsError(
            "run artifacts already exist: " + ", ".join(map(str, existing))
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for path in existing:
            path.unlink()

    started_at = datetime.now(timezone.utc)
    dataset_sha256 = _sha256_bytes(dataset_path.read_bytes())
    run_id = (
        f"{started_at.strftime('%Y%m%dT%H%M%SZ')}-"
        f"{_safe_model_name(model)}-{uuid.uuid4().hex[:8]}"
    )
    success_count = 0
    contract_valid_count = 0
    failed_count = 0

    with partial_path.open("x", encoding="utf-8") as stream:
        for index, item in enumerate(selected, 1):
            request_body = build_request(
                item["input"], model,
                prompt_version=prompt_version, **generation,
            )
            try:
                response = transport(
                    endpoint=endpoint,
                    request_body=request_body,
                    timeout=float(timeout),
                    api_key=api_key,
                )
            except Exception as exc:
                response = {
                    "transport_success": False,
                    "http_status": None,
                    "raw_text": "",
                    "raw_response": "",
                    "usage": None,
                    "error": f"Transport raised: {exc}",
                    "latency_ms": None,
                }
            if response.get("transport_success"):
                success_count += 1
                parsed, contract_error = parse_model_output(
                    response.get("raw_text", ""),
                    item["input"]["text"],
                    prompt_version,
                )
            else:
                failed_count += 1
                parsed = None
                contract_error = "Transport did not return assistant content"
            if parsed is not None:
                contract_valid_count += 1
            response_record = {
                "transport_success": bool(response.get("transport_success")),
                "http_status": response.get("http_status"),
                "raw_text": response.get("raw_text", ""),
                "raw_response": response.get("raw_response", ""),
                "usage": response.get("usage"),
                "error": response.get("error"),
                "latency_ms": response.get("latency_ms"),
                "contract_valid": parsed is not None,
                "contract_error": contract_error,
                "parsed_judgment": parsed,
            }
            result = {
                "schema_version": "0.1",
                "run_id": run_id,
                "id": item["id"],
                "input": item["input"],
                "input_sha256": _sha256_json(item["input"]),
                "request": request_body,
                "response": response_record,
            }
            stream.write(_canonical_json(result) + "\n")
            stream.flush()
            if progress:
                progress(
                    f"[{index}/{len(selected)}] {item['id']} "
                    f"transport={'ok' if response_record['transport_success'] else 'failed'} "
                    f"contract={'valid' if response_record['contract_valid'] else 'invalid'}"
                )
    os.replace(partial_path, output_path)

    completed_at = datetime.now(timezone.utc)
    manifest = {
        "schema_version": "0.1",
        "run_id": run_id,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "dataset_path": str(dataset_path),
        "dataset_sha256": dataset_sha256,
        "output_path": str(output_path),
        "output_sha256": _sha256_bytes(output_path.read_bytes()),
        "input_count": len(selected),
        "input_ids": [item["id"] for item in selected],
        "endpoint": endpoint,
        "model": model,
        "prompt_version": prompt_version,
        "prompt_sha256": _sha256_bytes(PROMPTS[prompt_version].encode("utf-8")),
        "generation": generation,
        "authentication": "bearer_env" if api_key else "none",
        "transport_success_count": success_count,
        "transport_failure_count": failed_count,
        "contract_valid_count": contract_valid_count,
        "contract_invalid_count": len(selected) - contract_valid_count,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    manifest_partial = manifest_path.with_name(f".{manifest_path.name}.partial")
    manifest_partial.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(manifest_partial, manifest_path)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--id", dest="selected_ids", action="append")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument(
        "--prompt-version", choices=sorted(PROMPTS), default=PROMPT_VERSION
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--api-key-env")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        api_key = None
        if args.api_key_env:
            api_key = os.environ.get(args.api_key_env)
            if not api_key:
                raise ValueError(
                    f"API key environment variable is unset: {args.api_key_env}"
                )
        manifest = run_evaluation(
            dataset_path=args.dataset,
            endpoint=args.endpoint,
            model=args.model,
            output_path=args.output,
            selected_ids=args.selected_ids,
            limit=args.limit,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            prompt_version=args.prompt_version,
            timeout=args.timeout,
            api_key=api_key,
            overwrite=args.overwrite,
            progress=None if args.quiet else lambda value: print(value, file=sys.stderr),
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        print(f"Run failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
