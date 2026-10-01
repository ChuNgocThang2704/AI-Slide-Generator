"""Low-overhead, content-free telemetry for LLM calls.

This module intentionally records metadata only. Prompts and responses may contain
private source documents and must never be written to the telemetry ledger.
"""

from __future__ import annotations

import inspect
import json
import time
from typing import Any, Optional


_INTERNAL_CALLERS = {
    "_llm_completion_plain_text",
    "_gemini_completion_plain_text",
    "_request_json_dict",
    "_vllm_chat_once",
}


def infer_call_purpose(default: str = "unspecified") -> str:
    """Return the nearest pipeline function without changing every call site."""
    frame = inspect.currentframe()
    try:
        cursor = frame.f_back if frame else None
        while cursor:
            name = cursor.f_code.co_name
            if name not in _INTERNAL_CALLERS and name not in {"infer_call_purpose", "record_llm_call"}:
                return name
            cursor = cursor.f_back
    finally:
        del frame
    return default


def monotonic_start() -> float:
    return time.perf_counter()


def record_llm_call(
    owner: Any,
    *,
    purpose: str,
    provider: str,
    model: str,
    started_at: float,
    status: str,
    max_tokens: int,
    json_mode: bool,
    error: Optional[BaseException] = None,
    fallback_from: Optional[str] = None,
) -> dict[str, Any]:
    """Append a bounded per-extractor ledger and emit one grep-friendly JSON line."""
    event = {
        "purpose": purpose or "unspecified",
        "provider": provider,
        "model": model,
        "status": status,
        "latency_ms": round((time.perf_counter() - started_at) * 1000, 1),
        "max_tokens": int(max_tokens),
        "json_mode": bool(json_mode),
    }
    task_id = str(getattr(owner, "_telemetry_task_id", "") or "").strip()
    if task_id:
        event["task_id"] = task_id
    if fallback_from:
        event["fallback_from"] = fallback_from
    if error is not None:
        event["error_type"] = type(error).__name__

    ledger = getattr(owner, "_llm_call_ledger", None)
    if not isinstance(ledger, list):
        ledger = []
        setattr(owner, "_llm_call_ledger", ledger)
    ledger.append(event)
    if len(ledger) > 500:
        del ledger[:-500]
    print("[llm_telemetry] " + json.dumps(event, ensure_ascii=False, sort_keys=True))
    return event

