# analyzer/llm_client.py

import json
import urllib.request
import urllib.error


DEFAULT_LLM_ENDPOINT = "http://localhost:1234/v1/chat/completions"
DEFAULT_MODEL_NAME = "qwen/qwen3-4b-2507"


def call_llm(
    prompt: str,
    endpoint: str = DEFAULT_LLM_ENDPOINT,
    model_name: str = DEFAULT_MODEL_NAME,
    temperature: float = 0.2,
    max_tokens: int = 512,
    timeout: int = 120,
) -> dict:
    """
    OpenAI 호환 LLM 서버에 프롬프트를 보내고 raw 응답 텍스트를 반환한다.
    현재는 localhost:1234 서버의 Base Qwen3 모델을 호출한다.
    """

    payload = {
        "model": model_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": "You are a strict Japanese sentence correction assistant. Return only valid JSON.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            result = json.loads(response_body)

        raw_text = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        return {
            "success": True,
            "raw_text": raw_text,
            "model_name": model_name,
            "adapter_name": None,
            "error": None,
        }

    except urllib.error.URLError as e:
        return {
            "success": False,
            "raw_text": "",
            "model_name": model_name,
            "adapter_name": None,
            "error": f"LLM connection error: {e}",
        }

    except json.JSONDecodeError as e:
        return {
            "success": False,
            "raw_text": "",
            "model_name": model_name,
            "adapter_name": None,
            "error": f"LLM server response decode error: {e}",
        }

    except Exception as e:
        return {
            "success": False,
            "raw_text": "",
            "model_name": model_name,
            "adapter_name": None,
            "error": f"Unexpected LLM error: {e}",
        }
