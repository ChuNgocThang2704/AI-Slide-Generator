"""Gemini-backed review for chart/table specs before rendering/returning.

The reviewer is intentionally conservative: it may reject a candidate, but it
does not create new chart/table specs. The source of truth is explicit evidence
in the user's input or slide text; extraction heuristics and LLM proposals are
only candidates that must pass the same contract.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from services.content.json_utils import parse_json_response

VISUAL_DATA_REVIEW_ENABLE = os.getenv("VISUAL_DATA_REVIEW_ENABLE", "true").lower() in ("1", "true", "yes")
VISUAL_DATA_REVIEW_MAX_CANDIDATES = int(os.getenv("VISUAL_DATA_REVIEW_MAX_CANDIDATES", "12"))


def _clean_json_text(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _slide_text(slide: Dict[str, Any], max_chars: int = 900) -> str:
    title = str(slide.get("title") or "").strip()
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        parts = [bullets]
    else:
        parts = [str(x) for x in bullets if str(x).strip()]
    return "\n".join([title] + parts)[:max_chars]


def _reviewable_records(
    structured: Dict[str, Any],
    specs: Dict[int, Dict[str, Any]],
    debug_records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    slides = structured.get("slides") or []
    records: List[Dict[str, Any]] = []
    for rec in debug_records:
        if rec.get("status") != "created":
            continue
        idx_raw = rec.get("slide_index")
        if not isinstance(idx_raw, int) or idx_raw not in specs:
            continue
        source = str(rec.get("source") or rec.get("context") or "")
        if source == "user_json":
            continue
        slide = slides[idx_raw] if idx_raw < len(slides) and isinstance(slides[idx_raw], dict) else {}
        records.append(
            {
                "slide_index": idx_raw,
                "title": str((slide or {}).get("title") or rec.get("title") or ""),
                "source": source,
                "slide_text": _slide_text(slide),
                "spec": specs[idx_raw],
                "match_score": rec.get("match_score"),
            }
        )
        if len(records) >= max(1, VISUAL_DATA_REVIEW_MAX_CANDIDATES):
            break
    return records


def _decision_map(parsed: Optional[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    decisions = (parsed or {}).get("decisions") if isinstance(parsed, dict) else None
    if not isinstance(decisions, list):
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for item in decisions:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("slide_index"))
        except Exception:
            continue
        out[idx] = {
            "pass": bool(item.get("pass")),
            "confidence": float(item.get("confidence") or 0.0),
            "reason": str(item.get("reason") or "").strip()[:240],
        }
    return out


async def review_visual_data_specs(
    content_extractor,
    structured: Dict[str, Any],
    specs: Dict[int, Dict[str, Any]],
    debug_records: List[Dict[str, Any]],
    *,
    kind: str,
    raw_content: str = "",
) -> Tuple[Dict[int, Dict[str, Any]], List[Dict[str, Any]]]:
    """Return filtered specs and updated debug records."""
    if not specs or not VISUAL_DATA_REVIEW_ENABLE:
        return specs, debug_records
    if not getattr(content_extractor, "gemini_available", False):
        return specs, debug_records
    if not hasattr(content_extractor, "_gemini_completion_plain_text"):
        return specs, debug_records

    candidates = _reviewable_records(structured, specs, debug_records)
    if not candidates:
        return specs, debug_records

    kind_norm = "chart" if str(kind).lower() == "chart" else "table"
    if kind_norm == "chart":
        review_rule = (
            "PASS only if the chart spec is supported by explicit numeric data in the raw input or slide, "
            "and there is clear chart/data intent or a clearly comparable numeric set. Reject if values or labels are inferred from prose, "
            "if there are fewer than two meaningful numeric points, or if a table would be more appropriate."
        )
    else:
        review_rule = (
            "PASS only if the table spec is supported by an explicit markdown/grid table or repeated structured "
            "key-value/comparison data. Reject prose summaries converted into a two-column table, especially "
            "history/theory paragraphs with no table intent."
        )

    payload = {
        "kind": kind_norm,
        "raw_input_excerpt": str(raw_content or "")[:6500],
        "candidates": candidates,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are a strict presentation data-visualization QA reviewer.\n"
                f"{review_rule}\n"
                "Use evidence, not topic assumptions. A new domain should be judged by the same schema/data contract.\n"
                "Do not create or repair specs. Only decide whether each candidate should be kept.\n"
                "When uncertain, set pass=false.\n"
                "Return strict JSON only: "
                "{\"decisions\":[{\"slide_index\":number,\"pass\":boolean,\"confidence\":number,\"reason\":string}]}."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    try:
        raw = await content_extractor._gemini_completion_plain_text(
            messages,
            max_tokens=1400,
            temperature=0.05,
            json_mode=True,
        )
        decisions = _decision_map(parse_json_response(raw, clean_result_text=_clean_json_text))
    except Exception as e:
        print(f"[visual_data_review] {kind_norm} review failed: {e}")
        return specs, debug_records

    if not decisions:
        return specs, debug_records

    filtered = dict(specs)
    for rec in debug_records:
        idx = rec.get("slide_index")
        if not isinstance(idx, int) or idx not in decisions:
            continue
        decision = decisions[idx]
        rec[f"{kind_norm}_review"] = decision
        if not decision.get("pass"):
            filtered.pop(idx, None)
            rec["status"] = "gemini_rejected"
            rec["reject_reason"] = decision.get("reason") or "Gemini reviewer rejected ambiguous visual data"

    rejected = sorted(set(specs) - set(filtered))
    if rejected:
        print(f"[visual_data_review] rejected {kind_norm} specs for slides: {rejected}")
    return filtered, debug_records
