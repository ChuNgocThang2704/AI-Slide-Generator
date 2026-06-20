"""JSON parsing and repair helpers for LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Optional

MAX_JSON_REPAIR_CHARS = 120_000


def try_fix_json(json_str: str) -> Optional[str]:
    """Best-effort repair for common truncated/malformed JSON responses."""
    try:
        json_str = (json_str or "").strip()
        if not json_str:
            return None
        if len(json_str) > MAX_JSON_REPAIR_CHARS:
            print(
                f"Skip JSON repair: response too large ({len(json_str)} chars > {MAX_JSON_REPAIR_CHARS})"
            )
            return None

        # Fix split-array bullets: "bullets": ["a"], ["b"] -> "bullets": ["a", "b"]
        json_str = re.sub(r"\]\s*,\s*\[", ", ", json_str)

        open_braces = json_str.count("{")
        close_braces = json_str.count("}")
        if open_braces > close_braces:
            missing = open_braces - close_braces
            if json_str.rstrip().endswith(","):
                json_str = json_str.rstrip().rstrip(",")
            if ('"bullets":' in json_str or '"content":' in json_str) and not json_str.rstrip().endswith("]"):
                json_str += "]"
            json_str += "}" * missing

        json.loads(json_str)
        return json_str
    except Exception as exc:
        print(f"Failed to fix JSON: {exc}")
        return None


def parse_json_response(
    result_text: str,
    *,
    clean_result_text: Callable[[str], str],
) -> Optional[Dict[str, Any]]:
    """Extract and parse the first JSON object returned by a model."""
    result_text = clean_result_text(result_text)
    if not result_text:
        return None

    decoder = json.JSONDecoder()
    first_json_error: Optional[str] = None
    for i, ch in enumerate(result_text):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(result_text, i)
            if isinstance(obj, dict):
                return obj
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                return obj[0]
        except json.JSONDecodeError as exc:
            if first_json_error is None:
                first_json_error = str(exc)
            continue

    json_start = result_text.find("{")
    if json_start >= 0:
        if first_json_error:
            print(f"JSON raw decode failed: {first_json_error}")
        fixed = try_fix_json(result_text[json_start:])
        if fixed:
            try:
                parsed = json.loads(fixed)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError as exc:
                print(f"JSON decode after try_fix_json: {exc}")

    return None
