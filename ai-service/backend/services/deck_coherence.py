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
_SOURCE_EVIDENCE_MAX_CHARS = max(
    12000,
    int(os.getenv("DECK_COHERENCE_SOURCE_MAX_CHARS", "30000")),
)
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
    "role_mismatch",
    "incomplete_example",
    "list_title_mismatch",
    "format_artifact",
    "weak_closing",
    "overloaded_slide",
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
    "pedagogical_role_mismatch": "role_mismatch",
    "incomplete_code_example": "incomplete_example",
    "incomplete_worked_example": "incomplete_example",
    "plural_title_mismatch": "list_title_mismatch",
    "markdown_artifact": "format_artifact",
    "weak_summary": "weak_closing",
    "excessive_density": "overloaded_slide",
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
    table = slide.get("table") if isinstance(slide.get("table"), dict) else None
    chart = slide.get("chart") if isinstance(slide.get("chart"), dict) else None
    return {
        "index": index,
        "title": str(slide.get("title") or "").strip(),
        "bullets": [str(value or "").strip() for value in bullets[:12] if str(value or "").strip()],
        "notes": str(slide.get("notes") or slide.get("script") or "").strip()[:1200],
        "layout": str(slide.get("layout") or "text_only"),
        "has_table": isinstance(slide.get("table"), dict),
        "has_chart": isinstance(slide.get("chart"), dict),
        "has_image": bool(slide.get("image") or slide.get("image_url")),
        "table": ({
            "title": str(table.get("title") or "")[:180],
            "headers": [str(value or "")[:120] for value in (table.get("headers") or [])[:8]],
            "rows": [
                [str(value or "")[:180] for value in row[:8]]
                for row in (table.get("rows") or [])[:10]
                if isinstance(row, list)
            ],
        } if table else None),
        "chart": ({
            "title": str(chart.get("title") or "")[:180],
            "type": str(chart.get("chart_type") or chart.get("type") or ""),
            "labels": [str(value or "")[:100] for value in (chart.get("labels") or chart.get("categories") or [])[:12]],
            "values": (chart.get("values") or [])[:12],
        } if chart else None),
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
        "required_teaching_devices": structured.get("pedagogical_requirements") or [],
    }


def _normalized_locked_outline(structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Expose planner's one-based outline to reviewers with deck-native indices."""
    normalized: List[Dict[str, Any]] = []
    for index, raw in enumerate(structured.get("locked_outline") or []):
        if not isinstance(raw, dict):
            continue
        item = copy.deepcopy(raw)
        item["index"] = index
        normalized.append(item)
    return normalized


def _normalized_requirement_spec(structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    slide_count = len(structured.get("slides") or [])
    for raw in structured.get("requirement_spec") or []:
        if not isinstance(raw, dict):
            continue
        item = copy.deepcopy(raw)
        values = item.get("assigned_slide_indices") or []
        parsed: List[int] = []
        for value in values:
            try:
                parsed.append(int(value))
            except (TypeError, ValueError):
                continue
        one_based = bool(parsed) and 0 not in parsed and all(1 <= value <= slide_count for value in parsed)
        item["assigned_slide_indices"] = [value - 1 if one_based else value for value in parsed]
        normalized.append(item)
    return normalized


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
        )[:_SOURCE_EVIDENCE_MAX_CHARS],
        "deck_profile": _deck_profile(structured),
        "locked_requirement_spec": _normalized_requirement_spec(structured),
        "locked_outline": _normalized_locked_outline(structured),
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
                "Treat dates and chronology in source_evidence as authoritative. Never change or flag a date merely "
                "because it appears future or past relative to an assumed current date; report it only when the deck "
                "disagrees with the supplied source. "
                "Treat the explicit user instruction as mandatory. In lecture mode, verify that concepts follow "
                "prerequisite order, learning objectives are fulfilled, and abstract or technical concepts have a "
                "source-grounded worked example, demonstration, exact code/input-output trace, formula, or check. "
                "Do not require these teaching devices in ordinary presentation mode; there, prioritize a clear "
                "claim-evidence-conclusion narrative appropriate to the user's purpose. "
                "When locked_outline is present, compare every authored slide with the outline item at the same "
                "index. Judge the actual title and bullets, not the pedagogical_role label. A worked example must "
                "show concrete inputs or starting conditions, meaningful steps or mechanism, and a result/output. "
                "A code example must be complete enough to understand or run and must not compress an entire block "
                "into an unreadable pseudo-line. A practice slide must give the learner an actionable task. A "
                "knowledge_check must contain actual questions or prompts that can be answered. A summary must "
                "synthesize prior content and must not introduce the final new lesson topic. Report role_mismatch, "
                "incomplete_example, or weak_closing when these semantic contracts fail. "
                "Check title-body fidelity: when a title promises plural types, categories, stages, methods, causes, "
                "examples, or a complete framework, the body must substantively provide at least two distinct members "
                "or the complete promised set. Report list_title_mismatch otherwise. Report format_artifact for "
                "visible Markdown fences, language labels, manual list numbering inside bullet strings, duplicated "
                "table serialization, or other internal formatting leakage. "
                "Report overloaded_slide when visible content is not presentation-ready: more than 4 bullets on a "
                "cover, more than 6 on a closing slide, more than 8 on an ordinary slide, or more than 10 concise "
                "lines on a worked example/check. Structured table rows do not count as bullets. The repair must "
                "preserve all required meaning while grouping or tightening details. "
                "Treat locked_requirement_spec as authoritative and verify its assigned components in substantive "
                "body content rather than objectives or summary mentions. Mandatory requirements must be fulfilled. "
                "Supporting requirements improve depth but must not by themselves force a score below 8. When older "
                "specs omit priority, compare them with user_instruction: explicit or scope-essential requirements "
                "are mandatory; optional source enrichment is supporting. "
                "Never report missing_requirement solely for a detail that is absent from user_instruction and is "
                "not necessary to satisfy its requested scope. The user instruction outranks generated source "
                "enrichment and planner embellishment. "
                "Do not penalize a missing image, chart, or table solely because locked_outline has a visual "
                "layout_hint: visual assets are attached after this text review. Only judge structured visual data "
                "already present in the slide payload, or an explicit visual requirement from user_instruction. "
                "Use deck_profile as a deterministic coverage signal. In lecture mode, when "
                "required_teaching_devices lists a device that is absent from the actual slide content, report "
                "missing_requirement and convert a lower-priority middle slide to satisfy it. If teaching_support_count is "
                "zero, you MUST report missing_example and target a redundant or lower-priority middle slide for "
                "conversion into a source-grounded worked example, demonstration, practice, or knowledge check. "
                "In ordinary presentation mode, do not require a teaching activity, but flag a major conclusion or "
                "recommendation with no concrete example, comparison, data, or source-backed rationale as weak_support. "
                "For every mode, compare headings and declared frameworks, classifications, stages, rule sets, or "
                "named lists with source_evidence. If a slide promises the whole set but omits a material component, "
                "report incomplete_coverage. Judge semantic completeness in any domain; never rely on a hard-coded "
                "topic, acronym, language, or expected list. "
                "For research reports, analytical reports, and case studies, identify the source's indispensable "
                "findings before scoring: primary measured results, decisive comparisons, evaluation metrics, "
                "sample/class coverage, limitations, and the evidence supporting the conclusion. Report "
                "incomplete_coverage when the deck spends space on metadata or description but omits a central "
                "result. Also report weak_progression when conclusions appear before their supporting results or "
                "when substantive slides follow what is presented as the final conclusion. "
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
                "The remaining allowed types are incomplete_coverage, weak_support, role_mismatch, "
                "incomplete_example, list_title_mismatch, format_artifact, and weak_closing. "
                "overloaded_slide is also allowed. "
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
        "locked_requirement_spec": structured.get("requirement_spec") or [],
        "locked_outline": structured.get("locked_outline") or [],
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
                "When locked_requirement_spec is present, treat it as the authoritative decomposition of the prompt "
                "and audit every listed component; do not silently reinterpret or drop it. "
                "Ignore slide count, output language, audience, tone, formatting, and visual-style instructions. "
                "Preserve every explicitly named list as a requirement group with separate required_components. "
                "For example, a request naming A, B, and C is not satisfied by a slide about only A or by an "
                "umbrella title. Never collapse named components into one broad topic. "
                "Then verify that every required topic is substantively taught or explained in a BODY slide. "
                "A mention in a title/cover, agenda, learning-objectives slide, or final summary is only a promise "
                "and does NOT count as coverage. A topic needs its own meaningful explanation, example, comparison, "
                "data, process, or exercise in the body. Detect semantically equivalent wording across languages. "
                "Check requested depth and mechanics, not keyword presence. If the user requests a complete example, "
                "a returned result, an error with its correction, a comparison criterion, a formula derivation, or "
                "any other concrete detail, that detail must appear substantively in a body slide. Merely naming it "
                "in objectives or conclusions is missing coverage. Apply this rule to every subject and language. "
                "When an example is explicitly requested alongside named central concepts or mechanics, verify that "
                "at least one example demonstrates those concepts together where pedagogically meaningful; separate "
                "definition-only slides do not make an unrelated example complete. "
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
        "locked_outline": _normalized_locked_outline(structured),
        "locked_requirement_spec": _normalized_requirement_spec(structured),
        "source_evidence": str(
            getattr(content_extractor, "_focused_source_content", "")
            or getattr(content_extractor, "_source_content", "")
            or ""
        )[:_SOURCE_EVIDENCE_MAX_CHARS],
        "targets": targets,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You refine only the listed presentation slides to resolve the supplied coherence instruction. "
                "Use source_evidence as the authority: correct inaccurate claims, retain exceptions and scope, and "
                "copy source-supported dates and years exactly; never rewrite them based on an assumed current date. "
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
                "Fulfill the corresponding locked_outline purpose, required_components, and semantic role in the "
                "actual replacement content. Do not merely change the pedagogical_role label. Remove manual bullet "
                "markers and Markdown artifacts. A plural classification title requires multiple substantive members; "
                "a worked example requires a complete mechanism and result; a knowledge check requires answerable "
                "questions; and a closing slide must synthesize instead of introducing a new topic. "
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
        role = str(improved_slides[index].get("pedagogical_role") or "").strip().lower()
        layout = str(improved_slides[index].get("layout") or "").strip().lower()
        if layout in {"intro", "title"}:
            bullet_limit = 4
        elif layout in {"thankyou", "thank_you", "closing"} or role == "summary":
            bullet_limit = 6
        elif role in _TEACHING_SUPPORT_ROLES:
            bullet_limit = 10
        else:
            bullet_limit = 8
        improved_slides[index]["bullets"] = clean_bullets[:bullet_limit]
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
    precomputed_issues: Optional[List[Dict[str, Any]]] = None,
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
        technical_issues = []
        for raw_issue in precomputed_issues or []:
            cleaned = _clean_issue(raw_issue, len(slides), allowed)
            if cleaned:
                technical_issues.append(cleaned)
        for issue in [*technical_issues, *coverage_issues, *issues]:
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
            "technical_issues": technical_issues,
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


async def improve_locked_outline_deck(
    content_extractor,
    structured: Dict[str, Any],
    *,
    task_id: str = "",
    precomputed_issues: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Score an outline-locked deck against one semantic rubric and repair once."""
    if not _ENABLED or not isinstance(structured, dict):
        return structured
    slides = structured.get("slides") or []
    if len(slides) < 2 or not hasattr(content_extractor, "_llm_completion_plain_text"):
        return structured
    try:
        allowed = set(range(len(slides)))
        score, semantic_issues = await _judge(content_extractor, structured, allowed)
        issues: List[Dict[str, Any]] = []
        seen_indices: Set[int] = set()
        for raw_issue in [*(precomputed_issues or []), *semantic_issues]:
            cleaned = _clean_issue(raw_issue, len(slides), allowed)
            if not cleaned or cleaned["index"] in seen_indices:
                continue
            seen_indices.add(cleaned["index"])
            issues.append(cleaned)
            if len(issues) >= _MAX_REFINES:
                break
        improved, changed = await _refine(content_extractor, structured, issues)
        report = {
            "mode": "locked_outline_semantic_rubric",
            "score": score,
            "technical_issues": precomputed_issues or [],
            "semantic_issues": semantic_issues,
            "issues": issues,
            "refined_slide_indices": changed,
        }
        if changed:
            try:
                validation_score, remaining = await _judge(
                    content_extractor,
                    improved,
                    set(changed),
                )
                report["validation_score"] = validation_score
                report["remaining_issues"] = remaining
                second_pass_issues = [
                    issue
                    for issue in remaining
                    if issue.get("severity") in {"high", "medium"}
                ][:_MAX_REFINES]
                if validation_score < 8.0 and second_pass_issues:
                    improved, second_changed = await _refine(
                        content_extractor,
                        improved,
                        second_pass_issues,
                    )
                    report["second_pass_issues"] = second_pass_issues
                    report["second_pass_refined_slide_indices"] = second_changed
                    changed = list(dict.fromkeys([*changed, *second_changed]))
                    if second_changed:
                        final_score, final_remaining = await _judge(
                            content_extractor,
                            improved,
                            set(second_changed),
                        )
                        report["final_score"] = final_score
                        report["final_remaining_issues"] = final_remaining
            except Exception as validation_error:
                report["validation_error"] = str(validation_error)
        _write_report(task_id, report)
        print(
            f"[deck_coherence] locked rubric score={score:.1f} issues={len(issues)} "
            f"refined={changed} validation={report.get('validation_score')}"
        )
        return improved
    except Exception as error:
        _write_report(task_id, {
            "mode": "locked_outline_semantic_rubric",
            "error": str(error),
            "issues": [],
            "refined_slide_indices": [],
        })
        print(f"[deck_coherence] locked audit failed: {error}")
        return structured


async def enforce_user_instruction_coverage(
    content_extractor,
    structured: Dict[str, Any],
    *,
    max_passes: int = 2,
) -> Dict[str, Any]:
    """Audit and repair the complete prompt after slide count/order are stable."""
    if not _ENABLED or not isinstance(structured, dict):
        return structured
    current = copy.deepcopy(structured)
    all_indices = set(range(len(current.get("slides") or [])))
    for pass_index in range(max(1, min(3, int(max_passes)))):
        try:
            issues = await _audit_instruction_coverage(content_extractor, current, all_indices)
            if not issues:
                break
            current, changed = await _refine(content_extractor, current, issues)
            print(
                f"[deck_contract] final prompt coverage pass={pass_index + 1} "
                f"issues={len(issues)} refined={changed}"
            )
            if not changed:
                break
        except Exception as error:
            print(f"[deck_contract] final prompt coverage audit failed: {error}")
            break
    return current
