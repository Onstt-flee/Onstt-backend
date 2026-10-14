"""Read-only readiness probe for the isolated feedback model server."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Callable

from analyzer.feedback_service import DEFAULT_ENDPOINT
from analyzer.feedback_store import configuration_error, feedback_enabled, feedback_configuration


def _read(url: str, opener: Callable[..., Any], timeout: float):
    with opener(urllib.request.Request(url, method="GET"), timeout=timeout) as response:
        body = response.read()
    return json.loads(body.decode("utf-8")) if body else None


def readiness_snapshot(*, opener=urllib.request.urlopen) -> dict[str, Any]:
    result = {"schema_version": "feedback-readiness-v0.1", "ready": False,
              "reason": "disabled", "enabled": feedback_enabled(), "model_health": False,
              "model_alias_present": False, "contains_request_content": False}
    if not result["enabled"]: return result
    if configuration_error() is not None:
        result["reason"] = "invalid_configuration"; return result
    try:
        timeout = float(os.getenv("FEEDBACK_READINESS_TIMEOUT_SECONDS", "2"))
        if timeout <= 0: raise ValueError
        endpoint = os.getenv("FEEDBACK_ENDPOINT", DEFAULT_ENDPOINT)
        parsed = urllib.parse.urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc: raise ValueError
        base = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")
        _read(f"{base}/health", opener, timeout); result["model_health"] = True
        models = _read(f"{base}/v1/models", opener, timeout)
        ids = [item.get("id") for item in models.get("data", []) if isinstance(item, dict)] if isinstance(models, dict) else []
        result["model_alias_present"] = feedback_configuration()["model"] in ids
        if not result["model_alias_present"]:
            result["reason"] = "model_alias_missing"; return result
    except ValueError:
        result["reason"] = "invalid_configuration"; return result
    except Exception:
        result["reason"] = "model_unavailable"; return result
    result["ready"] = True; result["reason"] = "ready"
    return result
