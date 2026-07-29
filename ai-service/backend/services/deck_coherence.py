from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from services.content.json_utils import parse_json_response

_ENABLED = os.getenv("DECK_COHERENCE_JUDGE_ENABLE", "true").lower() in ("1", "true", "yes")
_MAX_REFINES = max(0, int(os.getenv("DECK_COHERENCE_MAX_REFINES", "3")))
_VALIDATE_REFINES = os.getenv("DECK_COHERENCE_VALIDATE_REFINES", "true").lower() in ("1", "true", "yes")
_DEBUG_DIR = Path("outputs") / "debug"
_ALLOWED_ISSUES = {
    "duplicate_content",
    "off_topic",
    "weak_progression",
    "missing_transition",
    "contradiction",
    "visual_mismatch",
    "missing_requirement",
    "factual_accuracy",
    "missing_example",
    "objective_mismatch",
    "unsupported_claim",
}
_ISSUE_ALIASES = {
    "duplicate": "duplicate_content",
    "duplication": "duplicate_content",
    "redundancy": "duplicate_content",
    "redundant_content": "duplicate_content",
    "topic_drift": "off_topic",
    "poor_progression": "weak_progression",
    "weak_narrative": "weak_progression",
    "transition": "missing_transition",
    "inconsistency": "contradiction",
    "visual_inconsistency": "visual_mismatch",
    "missing_user_requirement": "missing_requirement",
    "missing_requested_content": "missing_requirement",
    "factual_error": "factual_accuracy",
    "incorrect_fact": "factual_accuracy",
    "inaccurate": "factual_accuracy",
    "weak_example": "missing_example",
    "missing_worked_example": "missing_example",
    "learning_objective_mismatch": "objective_mismatch",
    "unsupported_absolute": "unsupported_claim",
}


def _clean_json_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _slide_summary(slide: Dict[str, Any], index: int) -> Dict[str, Any]:
    bullets = slide.get("bullets") or slide.get("content") or []
    if not isinstance(bullets, list):
        bullets = [bullets]
    return {
        "index": index,
        "title": str(slide.get("title") or "").strip(),
        "bullets": [str(value or "").strip() for value in bullets[:6] if str(value or "").strip()],
        "notes": str(slide.get("notes") or slide.get("script") or "").strip()[:1200],
        "layout": str(slide.get("layout") or "text_only"),
        "has_table": isinstance(slide.get("table"), dict),
        "has_chart": isinstance(slide.get("chart"), dict),
        "has_image": bool(slide.get("image") or slide.get("image_url")),
        "pedagogical_role": str(slide.get("pedagogical_role") or ""),
    }


def _clean_issue(item: Any, slide_count: int, allowed_indices: Optional[Set[int]]) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    try:
        index = int(item.get("index"))
    except (TypeError, ValueError):
        return None
    if index < 0 or index >= slide_count:
        return None
    if allowed_indices is not None and index not in allowed_indices:
        return None
    issue_type = str(item.get("type") or "").strip().lower()
    issue_type = _ISSUE_ALIASES.get(issue_type, issue_type)
    severity = str(item.get("severity") or "low").strip().lower()
    instruction = str(item.get("instruction") or "").strip()[:500]
    if issue_type not in _ALLOWED_ISSUES or severity not in {"high", "medium"} or not instruction:
        return None
    return {
        "index": index,
        "type": issue_type,
        "severity": severity,
        "instruction": instruction,
    }


async def _judge(
    content_extractor,
    structured: Dict[str, Any],
    allowed_indices: Optional[Set[int]],
) -> Tuple[float, List[Dict[str, Any]]]:
    slides = structured.get("slides") or []
    payload = {
        "deck_title": str(structured.get("title") or ""),
        "presentation_mode": str(structured.get("presentation_mode") or "presentation"),
        "learning_objectives": structured.get("learning_objectives") or [],
        "user_instruction": str(getattr(content_extractor, "_user_instruction", "") or ""),
        "source_evidence": str(getattr(content_extractor, "_source_content", "") or "")[:12000],
        "slides": [_slide_summary(slide, idx) for idx, slide in enumerate(slides) if isinstance(slide, dict)],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are a presentation deck coherence judge. Evaluate the deck as one narrative. "
                "Report only material issues: duplicated ideas, off-topic slides, contradictions, weak progression, "
                "missing transitions, omitted explicit user requirements, or a table/chart/image layout that does "
                "not support the slide claim. Compare factual and technical claims against source_evidence when it "
                "is available; flag incorrect statements, lost exceptions, unsupported absolutes, and invented facts. "
                "Treat the explicit user instruction as mandatory. In lecture mode, verify that concepts follow "
                "prerequisite order, learning objectives are fulfilled, and abstract or technical concepts have a "
                "source-grounded worked example, demonstration, exact code/input-output trace, formula, or check. "
                "Do not require these teaching devices in ordinary presentation mode; there, prioritize a clear "
                "claim-evidence-conclusion narrative appropriate to the user's purpose. "
                "Learning-objective and summary slides are protected roles: never target either one to repair a "
                "different missing lecture component. If practice or a knowledge check is missing, target a "
                "redundant or lower-priority middle concept/example slide and explicitly instruct replacing it "
                "with a source-grounded activity. Do not propose adding a new slide when slide count is fixed. "
                "Do not penalize style preferences and do not invent facts. Use zero-based slide indices. "
                "The type must be exactly one of: duplicate_content, off_topic, weak_progression, "
                "missing_transition, contradiction, visual_mismatch, missing_requirement, factual_accuracy, "
                "missing_example, objective_mismatch, unsupported_claim. "
                "For a missing requirement, target the most redundant or lowest-priority slide that should be "
                "replaced or adapted to satisfy it. A score below 8 must include at least one "
                "high or medium issue with a concrete repair instruction. "
                "Return strict JSON only: {\"score\": number from 0 to 10, "
                "\"issues\":[{\"index\":number,\"type\":string,\"severity\":\"high|medium|low\","
                "\"instruction\":string}]}"
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    raw = await content_extractor._llm_completion_plain_text(
        messages,
        max_tokens=min(2600, 700 + len(slides) * 160),
        temperature=0.1,
        json_mode=True,
    )
    parsed = parse_json_response(raw, clean_result_text=_clean_json_text)
    if not isinstance(parsed, dict):
        return 0.0, []
    try:
        score = max(0.0, min(10.0, float(parsed.get("score") or 0.0)))
    except (TypeError, ValueError):
        score = 0.0
    issues = []
    for raw_issue in parsed.get("issues") or []:
        issue = _clean_issue(raw_issue, len(slides), allowed_indices)
        if issue:
            issues.append(issue)
    severity_rank = {"high": 0, "medium": 1}
    issues.sort(key=lambda value: (severity_rank.get(value["severity"], 2), value["index"]))
    unique: Dict[int, Dict[str, Any]] = {}
    for issue in issues:
        unique.setdefault(issue["index"], issue)
    return score, list(unique.values())[:_MAX_REFINES]


async def _refine(
    content_extractor,
    structured: Dict[str, Any],
    issues: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[int]]:
    if not issues:
        return structured, []
    slides = structured.get("slides") or []
    targets = []
    for issue in issues:
        index = issue["index"]
        if 0 <= index < len(slides) and isinstance(slides[index], dict):
            targets.append({**_slide_summary(slides[index], index), "instruction": issue["instruction"]})
    payload = {
        "deck_title": str(structured.get("title") or ""),
        "presentation_mode": str(structured.get("presentation_mode") or "presentation"),
        "deck_outline": [{"index": idx, "title": str(slide.get("title") or "")} for idx, slide in enumerate(slides) if isinstance(slide, dict)],
        "source_evidence": str(getattr(content_extractor, "_source_content", "") or "")[:12000],
        "targets": targets,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You refine only the listed presentation slides to resolve the supplied coherence instruction. "
                "Use source_evidence as the authority: correct inaccurate claims, retain exceptions and scope, and "
                "add a concrete example only when it is directly supported by that evidence. In lecture mode, make "
                "the target teachable with exact terminology and a concise worked example, code/input-output trace, "
                "formula, process step, or knowledge check when requested by the issue. In presentation mode, preserve "
                "the user's communication purpose and strengthen claim-to-evidence flow. Do not invent claims or numbers. "
                "Do not change slide count, "
                "layout, table, chart, or image. Return complete replacement title, bullets, and notes only for targets. "
                "Use plain text, zero-based indices, and strict JSON: "
                "{\"slides\":[{\"index\":number,\"title\":string,\"bullets\":[string],\"notes\":string}]}"
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    raw = await content_extractor._llm_completion_plain_text(
        messages,
        max_tokens=min(4000, 900 + len(targets) * 700),
        temperature=0.15,
        json_mode=True,
    )
    parsed = parse_json_response(raw, clean_result_text=_clean_json_text)
    returned = parsed.get("slides") if isinstance(parsed, dict) else None
    if not isinstance(returned, list):
        return structured, []

    improved = copy.deepcopy(structured)
    improved_slides = improved.get("slides") or []
    target_indices = {item["index"] for item in issues}
    changed: List[int] = []
    for item in returned:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if index not in target_indices or not (0 <= index < len(improved_slides)):
            continue
        title = str(item.get("title") or "").strip()
        bullets = item.get("bullets") or []
        notes = str(item.get("notes") or "").strip()
        if not title or not isinstance(bullets, list):
            continue
        clean_bullets = [str(value or "").strip() for value in bullets if str(value or "").strip()]
        old_bullets = improved_slides[index].get("bullets") or []
        if not clean_bullets or (old_bullets and len(clean_bullets) < min(2, len(old_bullets))):
            continue
        improved_slides[index]["title"] = title[:160]
        improved_slides[index]["bullets"] = clean_bullets[:8]
        if notes:
            improved_slides[index]["notes"] = notes
        changed.append(index)
    return improved, sorted(set(changed))


def _write_report(task_id: str, report: Dict[str, Any]) -> None:
    if not task_id:
        return
    try:
        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        (_DEBUG_DIR / f"{task_id}_deck_coherence.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as error:
        print(f"[deck_coherence] report error: {error}")


async def improve_deck_coherence(
    content_extractor,
    structured: Dict[str, Any],
    *,
    task_id: str = "",
    allowed_indices: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Judge the full narrative and selectively refine at most a few slides once."""
    if not _ENABLED or _MAX_REFINES <= 0 or not isinstance(structured, dict):
        return structured
    slides = structured.get("slides") or []
    if len(slides) < 2 or not hasattr(content_extractor, "_llm_completion_plain_text"):
        return structured
    allowed = set(allowed_indices) if allowed_indices is not None else None
    try:
        score, issues = await _judge(content_extractor, structured, allowed)
        improved, changed = await _refine(content_extractor, structured, issues)
        report: Dict[str, Any] = {
            "score": score,
            "issues": issues,
            "refined_slide_indices": changed,
        }
        if _VALIDATE_REFINES and changed:
            try:
                validation_score, remaining = await _judge(
                    content_extractor,
                    improved,
                    set(changed),
                )
                report["validation_score"] = validation_score
                report["remaining_issues"] = remaining
                if remaining:
                    improved, second_changed = await _refine(
                        content_extractor,
                        improved,
                        remaining,
                    )
                    report["second_refined_slide_indices"] = second_changed
            except Exception as validation_error:
                # Keep the first verified improvement if the optional validation
                # call is unavailable; provider failure must not roll it back.
                report["validation_error"] = str(validation_error)
        _write_report(task_id, report)
        print(
            f"[deck_coherence] score={score:.1f} issues={len(issues)} "
            f"refined={changed} validation={report.get('validation_score')}"
        )
        return improved
    except Exception as error:
        _write_report(task_id, {"error": str(error), "issues": [], "refined_slide_indices": []})
        print(f"[deck_coherence] judge failed: {error}")
        return structured
