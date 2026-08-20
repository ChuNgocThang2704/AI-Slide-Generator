from __future__ import annotations

import json
import re
from typing import Any, Dict

from services.content.json_utils import parse_json_response
from services.lecture_quality import detect_lecture_mode


_VALID_MODES = {"lecture", "presentation"}
_MIN_CONFIDENCE = 0.72


def _source_sample(source_text: str, max_chars: int = 12000) -> str:
    text = re.sub(r"[ \t]+", " ", str(source_text or "")).strip()
    if len(text) <= max_chars:
        return text
    third = max_chars // 3
    middle = max(0, len(text) // 2 - third // 2)
    return "\n...[middle]...\n".join((text[:third], text[middle:middle + third], text[-third:]))


def _clean_decision(raw: Any, provider: str) -> Dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    mode = str(raw.get("mode") or "").strip().lower()
    if mode not in _VALID_MODES:
        return None
    try:
        confidence = max(0.0, min(1.0, float(raw.get("confidence"))))
    except (TypeError, ValueError):
        return None
    reason = str(raw.get("reason") or "").strip()[:500]
    return {"mode": mode, "confidence": confidence, "reason": reason, "provider": provider}


def _messages(source_text: str, user_instruction: str) -> list[dict[str, str]]:
    payload = {
        "user_instruction": str(user_instruction or "").strip(),
        "source_sample": _source_sample(source_text),
    }
    return [
        {
            "role": "system",
            "content": (
                "Classify the communication intent of a slide-generation request. Choose lecture when the output "
                "is intended to teach knowledge progressively with learning outcomes, explanation, examples, or "
                "practice. Choose presentation for reporting, pitching, showcasing, persuading, summarizing results, "
                "or briefing an audience. Judge semantic purpose, audience, requested treatment, and source structure; "
                "do not decide from one keyword. A textbook can be summarized as a report, and the word presentation "
                "can still describe a lecture. The explicit user purpose outranks the document genre. Return strict "
                "JSON only: {\"mode\":\"lecture|presentation\",\"confidence\":0.0," 
                "\"reason\":\"one concise evidence-based sentence\"}."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


async def classify_presentation_mode(content_extractor, source_text: str, user_instruction: str) -> Dict[str, Any]:
    messages = _messages(source_text, user_instruction)
    qwen_decision = None
    if bool(getattr(content_extractor, "vllm_available", False)):
        try:
            raw = await content_extractor._llm_completion_plain_text(
                messages, max_tokens=320, temperature=0.0, json_mode=True, provider="vllm_only"
            )
            parsed = parse_json_response(raw, clean_result_text=lambda value: str(value or "").strip())
            qwen_decision = _clean_decision(parsed, "qwen")
        except Exception as error:
            print(f"[mode_classifier] Qwen classification failed: {error}")

    if qwen_decision and qwen_decision["confidence"] >= _MIN_CONFIDENCE:
        return qwen_decision

    if bool(getattr(content_extractor, "gemini_available", False)):
        try:
            raw = await content_extractor._llm_completion_plain_text(
                messages, max_tokens=320, temperature=0.0, json_mode=True, provider="gemini"
            )
            parsed = parse_json_response(raw, clean_result_text=lambda value: str(value or "").strip())
            gemini_decision = _clean_decision(parsed, "gemini")
            if gemini_decision:
                gemini_decision["qwen_confidence"] = (
                    qwen_decision.get("confidence") if qwen_decision else None
                )
                return gemini_decision
        except Exception as error:
            print(f"[mode_classifier] Gemini classification failed: {error}")

    fallback_mode = "lecture" if detect_lecture_mode(source_text, user_instruction) else "presentation"
    return {
        "mode": fallback_mode,
        "confidence": 0.5,
        "reason": "LLM classification unavailable or uncertain; deterministic fallback used.",
        "provider": "rule_fallback",
        "qwen_confidence": qwen_decision.get("confidence") if qwen_decision else None,
    }


def lock_presentation_mode(structured: Dict[str, Any], decision: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(structured, dict) or not isinstance(decision, dict):
        return structured
    mode = str(decision.get("mode") or "").strip().lower()
    if mode not in _VALID_MODES:
        return structured
    structured["presentation_mode"] = mode
    for slide in structured.get("slides") or []:
        if isinstance(slide, dict):
            slide["presentation_mode"] = mode
    structured["mode_decision"] = {
        "mode": mode,
        "confidence": decision.get("confidence"),
        "provider": decision.get("provider"),
        "reason": decision.get("reason"),
    }
    return structured
