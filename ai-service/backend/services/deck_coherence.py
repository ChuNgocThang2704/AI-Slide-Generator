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
    "incomplete_coverage",
    "weak_support",
}
_TEACHING_SUPPORT_ROLES = {
    "worked_example",
    "demonstration",
    "practice",
    "knowledge_check",
}
_ALLOWED_LECTURE_ROLES = {
    "learning_objectives",
    "concept",
    *_TEACHING_SUPPORT_ROLES,
    "summary",
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
    "missing_component": "incomplete_coverage",
    "incomplete_list": "incomplete_coverage",
    "partial_framework": "incomplete_coverage",
    "insufficient_evidence": "weak_support",
    "weak_evidence": "weak_support",
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


def _deck_profile(structured: Dict[str, Any]) -> Dict[str, Any]:
    slides = [slide for slide in (structured.get("slides") or []) if isinstance(slide, dict)]
    roles = [str(slide.get("pedagogical_role") or "").strip().lower() for slide in slides]
    support_indices = [
        index
        for index, slide in enumerate(slides)
        if str(slide.get("pedagogical_role") or "").strip().lower() in _TEACHING_SUPPORT_ROLES
    ]
    evidence_indices = [
        index
        for index, slide in enumerate(slides)
        if (
            isinstance(slide.get("table"), dict)
            or isinstance(slide.get("chart"), dict)
            or str(slide.get("pedagogical_role") or "").strip().lower()
            in {"worked_example", "demonstration"}
        )
    ]
    return {
        "slide_count": len(slides),
        "role_counts": {role: roles.count(role) for role in sorted(set(roles)) if role},
        "teaching_support_indices": support_indices,
        "teaching_support_count": len(support_indices),
        "evidence_indices": evidence_indices,
        "evidence_count": len(evidence_indices),
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
        "user_instruction": str(getattr(content_extractor, "_user_instruction", "") or ""),
        "learning_objectives": structured.get("learning_objectives") or [],
        "user_instruction": str(getattr(content_extractor, "_user_instruction", "") or ""),
        "source_evidence": str(
            getattr(content_extractor, "_focused_source_content", "")
            or getattr(content_extractor, "_source_content", "")
            or ""
        )[:12000],
        "deck_profile": _deck_profile(structured),
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
                "Use deck_profile as a deterministic coverage signal. In lecture mode, if teaching_support_count is "
                "zero, you MUST report missing_example and target a redundant or lower-priority middle slide for "
                "conversion into a source-grounded worked example, demonstration, practice, or knowledge check. "
                "In ordinary presentation mode, do not require a teaching activity, but flag a major conclusion or "
                "recommendation with no concrete example, comparison, data, or source-backed rationale as weak_support. "
                "For every mode, compare headings and declared frameworks, classifications, stages, rule sets, or "
                "named lists with source_evidence. If a slide promises the whole set but omits a material component, "
                "report incomplete_coverage. Judge semantic completeness in any domain; never rely on a hard-coded "
                "topic, acronym, language, or expected list. "
                "Learning-objective and summary slides are protected roles: never target either one to repair a "
                "different missing lecture component. If practice or a knowledge check is missing, target a "
                "redundant or lower-priority middle concept/example slide and explicitly instruct replacing it "
                "with a source-grounded activity. Do not propose adding a new slide when slide count is fixed. "
                "When the user explicitly requests an exercise, practice, activity, or knowledge check, preserve "
                "at least one such slide through every repair. Never write internal retrieval, evidence, source "
                "support, validation, or grounding messages as user-facing slide content. "
                "Do not penalize style preferences and do not invent facts. Use zero-based slide indices. "
                "The type must be exactly one of: duplicate_content, off_topic, weak_progression, "
                "missing_transition, contradiction, visual_mismatch, missing_requirement, factual_accuracy, "
                "missing_example, objective_mismatch, unsupported_claim. "
                "The remaining allowed types are incomplete_coverage and weak_support. "
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


async def _audit_instruction_coverage(
    content_extractor,
    structured: Dict[str, Any],
    allowed_indices: Optional[Set[int]],
) -> List[Dict[str, Any]]:
    """Find explicit requested topics missing from substantive body slides."""
    instruction = str(getattr(content_extractor, "_user_instruction", "") or "").strip()
    slides = structured.get("slides") or []
    if not instruction or len(slides) < 3:
        return []

    payload = {
        "user_instruction": instruction,
        "presentation_mode": str(structured.get("presentation_mode") or "presentation"),
        "slides": [
            _slide_summary(slide, index)
            for index, slide in enumerate(slides)
            if isinstance(slide, dict)
        ],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are a strict requirement-coverage auditor for presentation decks. "
                "First identify the atomic CONTENT topics explicitly required by the user, in any language. "
                "Ignore slide count, output language, audience, tone, formatting, and visual-style instructions. "
                "Preserve every explicitly named list as a requirement group with separate required_components. "
                "For example, a request naming A, B, and C is not satisfied by a slide about only A or by an "
                "umbrella title. Never collapse named components into one broad topic. "
                "Then verify that every required topic is substantively taught or explained in a BODY slide. "
                "A mention in a title/cover, agenda, learning-objectives slide, or final summary is only a promise "
                "and does NOT count as coverage. A topic needs its own meaningful explanation, example, comparison, "
                "data, process, or exercise in the body. Detect semantically equivalent wording across languages. "
                "Also identify body slides that substantially duplicate another slide. "
                "For each genuinely missing topic, target the most redundant or lowest-priority BODY slide that "
                "can be replaced. Never target the cover, learning objectives, or closing summary. "
                "Do not request a new slide and do not hard-code any domain vocabulary. "
                "For every requirement group, return required_components, covered_components, missing_components, "
                "and target_index. target_index must be a redundant or lowest-priority body slide when components "
                "are missing, otherwise null. Return no issue when all explicit content requirements are covered. "
                "Return strict JSON only: "
                "{\"requirements\":[{\"topic\":string,\"required_components\":[string],"
                "\"covered_components\":[string],\"missing_components\":[string],"
                "\"covered_by\":[number],\"target_index\":number|null}],"
                "\"issues\":[{\"index\":number,\"type\":\"missing_requirement\","
                "\"severity\":\"high|medium\",\"instruction\":string}]}."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    raw = await content_extractor._llm_completion_plain_text(
        messages,
        max_tokens=min(2200, 800 + len(slides) * 120),
        temperature=0.05,
        json_mode=True,
    )
    parsed = parse_json_response(raw, clean_result_text=_clean_json_text)
    if not isinstance(parsed, dict):
        return []
    content_extractor._last_coverage_requirements = parsed.get("requirements") or []
    issues: List[Dict[str, Any]] = []

    protected_indices = {
        index
        for index, slide in enumerate(slides)
        if isinstance(slide, dict)
        and (
            str(slide.get("layout") or "").strip().lower()
            in {"intro", "title", "thankyou", "thank_you"}
            or str(slide.get("pedagogical_role") or "").strip().lower()
            in {"learning_objectives", "summary"}
        )
    }
    for requirement in parsed.get("requirements") or []:
        if not isinstance(requirement, dict):
            continue
        required = [
            str(value or "").strip()
            for value in (requirement.get("required_components") or [])
            if str(value or "").strip()
        ]
        covered = {
            str(value or "").strip().casefold()
            for value in (requirement.get("covered_components") or [])
            if str(value or "").strip()
        }
        explicit_missing = [
            str(value or "").strip()
            for value in (requirement.get("missing_components") or [])
            if str(value or "").strip()
        ]
        missing = explicit_missing or [
            value for value in required if value.casefold() not in covered
        ]
        if not missing:
            continue
        valid_targets = [
            index
            for index, slide in enumerate(slides)
            if isinstance(slide, dict)
            and index not in protected_indices
            and (allowed_indices is None or index in allowed_indices)
        ]
        try:
            target_index = int(requirement.get("target_index"))
        except (TypeError, ValueError):
            target_index = -1
        if target_index not in valid_targets:
            covered_by: List[int] = []
            for value in requirement.get("covered_by") or []:
                try:
                    index = int(value)
                except (TypeError, ValueError):
                    continue
                if index in valid_targets:
                    covered_by.append(index)
            if covered_by:
                # Expand the slide that already teaches part of the same
                # requirement group instead of scattering the classification.
                target_index = covered_by[0]
            elif valid_targets:
                # When the auditor identifies missing content but cannot name a
                # redundant target, replace the thinnest body slide. Never
                # silently discard an explicit user requirement.
                target_index = min(
                    valid_targets,
                    key=lambda index: (
                        len(slides[index].get("bullets") or slides[index].get("content") or []),
                        -index,
                    ),
                )
            else:
                continue
        topic = str(requirement.get("topic") or "requested content").strip()
        issues.append({
            "index": target_index,
            "type": "missing_requirement",
            "severity": "high",
            "instruction": (
                f"Replace this redundant or lower-priority slide so the deck fully covers {topic}. "
                f"The replacement must substantively explain every missing component: {', '.join(missing)}. "
                "Keep all named components together when they form one requested classification or framework."
            )[:500],
        })

    for raw_issue in parsed.get("issues") or []:
        issue = _clean_issue(raw_issue, len(slides), allowed_indices)
        if (
            issue
            and issue["type"] in {"missing_requirement", "incomplete_coverage"}
            and issue["index"] not in protected_indices
        ):
            issues.append(issue)
    unique: Dict[int, Dict[str, Any]] = {}
    for issue in issues:
        unique.setdefault(issue["index"], issue)
    return list(unique.values())[:_MAX_REFINES]


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
        "source_evidence": str(
            getattr(content_extractor, "_focused_source_content", "")
            or getattr(content_extractor, "_source_content", "")
            or ""
        )[:12000],
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
                "When repairing incomplete_coverage, restore every material missing component supported by the source "
                "without padding the slide with unrelated detail. "
                "Never put messages about missing source support, evidence, retrieval, validation, or grounding "
                "inside a slide. If direct support is limited, use stable foundational explanation or a clearly "
                "illustrative example without inventing document-specific facts. "
                "For a requested chart, preserve each supported label-value pair as a separate bullet in the exact "
                "form 'Label: number'. You may create an illustrative numeric series only when user_instruction "
                "explicitly permits illustrative, sample, simulated, or hypothetical data; then clearly label one "
                "bullet as illustrative. Otherwise never invent chart values. "
                "Do not change slide count, "
                "layout, table, chart, or image. Return complete replacement title, bullets, and notes only for targets. "
                "In lecture mode you may also return pedagogical_role when the target is genuinely converted into a "
                "worked_example, demonstration, practice, or knowledge_check. In presentation mode omit that field. "
                "Use plain text, zero-based indices, and strict JSON: "
                "{\"slides\":[{\"index\":number,\"title\":string,\"bullets\":[string],\"notes\":string,"
                "\"pedagogical_role\":\"optional\"}]}"
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
        new_role = str(item.get("pedagogical_role") or "").strip().lower()
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
        if (
            str(improved.get("presentation_mode") or "").strip().lower() == "lecture"
            and new_role in _ALLOWED_LECTURE_ROLES
        ):
            improved_slides[index]["pedagogical_role"] = new_role
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
        coverage_issues = await _audit_instruction_coverage(
            content_extractor,
            structured,
            allowed,
        )
        score, issues = await _judge(content_extractor, structured, allowed)
        merged_issues: List[Dict[str, Any]] = []
        seen_indices: Set[int] = set()
        for issue in [*coverage_issues, *issues]:
            if issue["index"] in seen_indices:
                continue
            seen_indices.add(issue["index"])
            merged_issues.append(issue)
            if len(merged_issues) >= _MAX_REFINES:
                break
        issues = merged_issues
        improved, changed = await _refine(content_extractor, structured, issues)
        report: Dict[str, Any] = {
            "score": score,
            "coverage_requirements": getattr(content_extractor, "_last_coverage_requirements", []),
            "coverage_issues": coverage_issues,
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
