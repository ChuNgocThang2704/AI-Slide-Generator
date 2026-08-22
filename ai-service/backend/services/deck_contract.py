from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Optional

from services.deck_coherence import (
    enforce_user_instruction_coverage,
    improve_deck_coherence,
    improve_locked_outline_deck,
)
from services.lecture_quality import (
    attach_source_page_provenance,
    enforce_instructional_requirements,
    enrich_lecture_deck,
    missing_instructional_requirements,
    order_lecture_assessment_slides,
)
from services.content.json_utils import parse_json_response
from services.plan_limits import enforce_plan_slide_limit
from services.slide_text_quality import improve_final_slide_quality
from services.presentation_mode import lock_presentation_mode
from services.technical_quality import repair_technical_content, validate_technical_content


def _stable_slide_id(slide: Dict[str, Any], index: int, seen: set[str]) -> str:
    existing = str(slide.get("slide_id") or slide.get("id") or "").strip()
    if existing and existing not in seen:
        return existing

    identity = json.dumps(
        {
            "title": str(slide.get("title") or "").strip(),
            "role": str(slide.get("pedagogical_role") or "").strip(),
            "layout": str(slide.get("layout") or "").strip(),
            "bullets": [str(item).strip() for item in (slide.get("bullets") or [])],
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
    candidate = f"slide-{index + 1:03d}-{digest}"
    suffix = 2
    while candidate in seen:
        candidate = f"slide-{index + 1:03d}-{digest}-{suffix}"
        suffix += 1
    return candidate


def assign_stable_slide_ids(structured: Dict[str, Any]) -> Dict[str, Any]:
    slides = structured.get("slides") or []
    seen: set[str] = set()
    for index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        slide_id = _stable_slide_id(slide, index, seen)
        slide["slide_id"] = slide_id
        seen.add(slide_id)
    return structured


def deck_structure_signature(structured: Dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(slide.get("slide_id") or "")
        for slide in (structured.get("slides") or [])
        if isinstance(slide, dict)
    )


def assert_deck_structure_locked(
    structured: Dict[str, Any],
    expected_signature: Optional[tuple[str, ...]] = None,
) -> tuple[str, ...]:
    signature = deck_structure_signature(structured)
    expected = expected_signature or tuple(structured.get("_structure_signature") or ())
    if expected and signature != expected:
        raise RuntimeError(
            "Deck structure changed after visual generation was locked: "
            f"expected={expected}, actual={signature}"
        )
    return signature


def _boundary_visual_issues(deck: Dict[str, Any]) -> list[Dict[str, Any]]:
    slides = deck.get("slides") or []
    issues: list[Dict[str, Any]] = []
    for index in {0, len(slides) - 1}:
        if not (0 <= index < len(slides)) or not isinstance(slides[index], dict):
            continue
        slide = slides[index]
        if isinstance(slide.get("table"), dict) or isinstance(slide.get("chart"), dict):
            issues.append({
                "index": index,
                "type": "role_mismatch",
                "severity": "high",
                "instruction": (
                    "Intro and closing slides cannot use table or chart objects because their boundary layout does "
                    "not render those objects. Rewrite every required item as complete, concise visible bullets. "
                    "For a knowledge check, preserve every requested question verbatim enough to stand alone."
                ),
            })
    return issues


def _flatten_boundary_visuals(deck: Dict[str, Any]) -> Dict[str, Any]:
    """Keep boundary content visible even if a provider ignores its visual contract."""
    slides = deck.get("slides") or []
    for index in {0, len(slides) - 1}:
        if not (0 <= index < len(slides)) or not isinstance(slides[index], dict):
            continue
        slide = slides[index]
        table = slide.pop("table", None)
        slide.pop("chart", None)
        if not isinstance(table, dict):
            continue
        headers = [str(value or "").strip() for value in (table.get("headers") or [])]
        visible = [str(value).strip() for value in (slide.get("bullets") or []) if str(value).strip()]
        for row in (table.get("rows") or [])[:4]:
            if not isinstance(row, list):
                continue
            cells = [str(value or "").strip() for value in row]
            if not any(cells):
                continue
            # The first column normally carries the question/key statement;
            # secondary hint/answer columns belong in speaker notes.
            statement = cells[0]
            if statement and statement not in visible:
                visible.append(statement)
            if len(cells) > 1 and cells[1]:
                label = headers[1] if len(headers) > 1 else "Gợi ý"
                note = f"{label}: {cells[1]}"
                current_notes = str(slide.get("notes") or "").strip()
                if note not in current_notes:
                    slide["notes"] = f"{current_notes}\n{note}".strip()
        slide["bullets"] = visible[:8]
    return deck


async def finalize_deck_for_visuals(
    content_extractor,
    structured: Dict[str, Any],
    *,
    raw_content: str,
    user_instruction: str,
    task_id: str,
    plan: str,
    target_slides: Optional[int],
) -> Dict[str, Any]:
    """Run the final structure-changing passes, then lock slide order and identity."""
    deck = copy.deepcopy(structured or {})
    mode_decision = getattr(content_extractor, "_mode_decision", None)
    locked_mode = str(getattr(content_extractor, "_presentation_mode", "") or "")
    deck = lock_presentation_mode(deck, mode_decision)
    original_count = len(deck.get("slides") or [])

    if deck.get("_outline_locked"):
        return await _finalize_locked_outline_deck(
            content_extractor,
            deck,
            raw_content=raw_content,
            user_instruction=user_instruction,
            task_id=task_id,
            plan=plan,
            target_slides=target_slides,
        )

    deck = await improve_final_slide_quality(
        content_extractor,
        deck,
        task_id=task_id,
        source_language=(getattr(content_extractor, "_slide_lang_hint", "auto") or "auto"),
    )
    # Coherence review needs the reliable mode, roles, objectives and source
    # provenance supplied by lecture enrichment. Running it afterwards also
    # lets the judge repair a weak concept/example sequence selectively.
    deck = lock_presentation_mode(deck, mode_decision)
    deck = enrich_lecture_deck(
        deck, raw_content or "", user_instruction or "", locked_mode=locked_mode
    )
    deck = attach_source_page_provenance(deck, raw_content or "")
    deck = enforce_plan_slide_limit(deck, plan)
    deck, technical_issues = validate_technical_content(deck)
    technical_issues.extend(_boundary_visual_issues(deck))
    deck = await improve_deck_coherence(
        content_extractor,
        deck,
        task_id=task_id,
        precomputed_issues=technical_issues,
    )
    # A review pass may accidentally remove a requested practice/activity role.
    # Re-apply the pedagogical contract before locking the structure.
    deck = lock_presentation_mode(deck, mode_decision)
    deck = enrich_lecture_deck(
        deck, raw_content or "", user_instruction or "", locked_mode=locked_mode
    )
    deck = attach_source_page_provenance(deck, raw_content or "")

    desired_count = int(target_slides) if target_slides else original_count
    desired_count = max(2, desired_count)
    if len(deck.get("slides") or []) != desired_count:
        deck = await content_extractor._force_slide_count_exact(deck, desired_count)
    deck = content_extractor._ensure_deck_boundaries(deck, desired_count)
    if len(deck.get("slides") or []) != desired_count:
        deck = await content_extractor._force_slide_count_exact(deck, desired_count)
    deck = lock_presentation_mode(deck, mode_decision)
    deck = await enforce_user_instruction_coverage(
        content_extractor, deck, max_passes=2
    )
    deck = await _repair_instructional_requirements(
        content_extractor, deck, raw_content or "", user_instruction or ""
    )
    deck = enforce_instructional_requirements(deck, user_instruction or "")
    deck = order_lecture_assessment_slides(deck)
    # Count repair and boundary normalization may create replacement slides.
    # Reattach provenance only after the final slide set is stable.
    deck = attach_source_page_provenance(deck, raw_content or "")
    deck, remaining_technical = await repair_technical_content(
        content_extractor, deck, source_text=raw_content or ""
    )
    deck = _flatten_boundary_visuals(deck)
    if remaining_technical:
        print(f"[deck_contract] unresolved technical issues={len(remaining_technical)}")
    deck = assign_stable_slide_ids(deck)

    signature = deck_structure_signature(deck)
    if len(signature) != len(set(signature)):
        raise RuntimeError("Deck contains duplicate slide_id values")
    if not signature:
        raise RuntimeError("Cannot lock an empty deck")
    if target_slides and len(signature) != int(target_slides):
        raise RuntimeError(
            f"Locked deck count mismatch: expected={int(target_slides)}, actual={len(signature)}"
        )

    slides = deck.get("slides") or []
    first_layout = str((slides[0] or {}).get("layout") or "").strip().lower()
    last_layout = str((slides[-1] or {}).get("layout") or "").strip().lower()
    if first_layout not in {"intro", "title"}:
        raise RuntimeError("Locked deck must begin with an intro slide")
    if last_layout not in {"thankyou", "thank_you"}:
        raise RuntimeError("Locked deck must end with a closing slide")

    deck["_structure_locked"] = True
    deck["_structure_signature"] = list(signature)
    return deck


async def _finalize_locked_outline_deck(
    content_extractor,
    deck: Dict[str, Any],
    *,
    raw_content: str,
    user_instruction: str,
    task_id: str,
    plan: str,
    target_slides: Optional[int],
) -> Dict[str, Any]:
    """Finalize an outline-first deck without allowing late structural rewrites."""
    mode_decision = getattr(content_extractor, "_mode_decision", None)
    deck = enforce_plan_slide_limit(copy.deepcopy(deck), plan)
    desired_count = int(target_slides) if target_slides else len(deck.get("slides") or [])
    if len(deck.get("slides") or []) != desired_count:
        raise RuntimeError(
            f"Locked outline count changed before review: expected={desired_count}, "
            f"actual={len(deck.get('slides') or [])}"
        )
    slides = deck.get("slides") or []
    slides[0]["layout"] = "intro"
    slides[-1]["layout"] = "thankyou"
    deck = lock_presentation_mode(deck, mode_decision)
    deck = attach_source_page_provenance(deck, raw_content or "")
    deck, technical_issues = validate_technical_content(deck)
    technical_issues.extend(_boundary_visual_issues(deck))
    deck = await improve_locked_outline_deck(
        content_extractor,
        deck,
        task_id=task_id,
        precomputed_issues=technical_issues,
    )
    deck = await enforce_user_instruction_coverage(
        content_extractor, deck, max_passes=1
    )
    # The single review may edit prose, but never count/order/layout.
    if len(deck.get("slides") or []) != desired_count:
        raise RuntimeError("Coherence review changed the locked outline structure")
    deck = lock_presentation_mode(deck, mode_decision)
    deck = attach_source_page_provenance(deck, raw_content or "")
    deck, remaining_technical = await repair_technical_content(
        content_extractor, deck, source_text=raw_content or ""
    )
    deck = _flatten_boundary_visuals(deck)
    if remaining_technical:
        print(f"[deck_contract] unresolved locked technical issues={len(remaining_technical)}")
    slides = deck.get("slides") or []
    slides[0]["layout"] = "intro"
    slides[-1]["layout"] = "thankyou"
    deck = assign_stable_slide_ids(deck)
    signature = deck_structure_signature(deck)
    slides = deck.get("slides") or []
    if len(signature) != desired_count or len(signature) != len(set(signature)):
        raise RuntimeError("Locked outline produced an invalid slide identity set")
    first_layout = str((slides[0] or {}).get("layout") or "").strip().lower()
    last_layout = str((slides[-1] or {}).get("layout") or "").strip().lower()
    if first_layout not in {"intro", "title"}:
        raise RuntimeError("Locked outline must begin with an intro slide")
    if last_layout not in {"thankyou", "thank_you"}:
        raise RuntimeError("Locked outline must end with a closing slide")
    deck["_structure_locked"] = True
    deck["_structure_signature"] = list(signature)
    print("[deck_contract] outline-first deck finalized with one contract-only review")
    return deck


async def _repair_instructional_requirements(
    content_extractor,
    deck: Dict[str, Any],
    source_text: str,
    user_instruction: str,
) -> Dict[str, Any]:
    missing = missing_instructional_requirements(deck, user_instruction)
    slides = deck.get("slides") or []
    if not missing or len(slides) < 3:
        return deck
    candidates = [
        index for index in range(1, len(slides) - 1)
        if isinstance(slides[index], dict)
        and str(slides[index].get("pedagogical_role") or "").lower()
        not in {"learning_objectives", "summary", "knowledge_check", "practice"}
    ]
    targets = candidates[-len(missing):]
    if len(targets) < len(missing):
        return deck
    payload = {
        "user_instruction": user_instruction,
        "missing_requirements": [
            {"requirement": requirement, "target_index": index}
            for requirement, index in zip(missing, targets)
        ],
        "source_evidence": source_text[:30000],
        "deck_outline": [
            {"index": i, "title": str(slide.get("title") or "")}
            for i, slide in enumerate(slides) if isinstance(slide, dict)
        ],
    }
    messages = [{
        "role": "system",
        "content": (
            "Repair the specified lecture slides so every explicit teaching requirement is genuinely fulfilled. "
            "Use a distinct target slide for each requirement and source_evidence as authority. A worked example "
            "must contain the complete concrete example, not merely an example label. A common-mistakes slide must "
            "name actual mistakes and their corrections. A knowledge check must contain real question marks. "
            "Honor all details in user_instruction, including requested parameters, return values, examples, and "
            "language. Preserve slide count and return only strict JSON: "
            "{\"slides\":[{\"index\":0,\"title\":\"...\",\"bullets\":[\"...\"],\"notes\":\"...\","
            "\"pedagogical_role\":\"worked_example|demonstration|practice|knowledge_check\"}]}"
        ),
    }, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    try:
        raw = await content_extractor._llm_completion_plain_text(
            messages, max_tokens=2200, temperature=0.1, json_mode=True
        )
        parsed = parse_json_response(raw, clean_result_text=lambda value: str(value).strip())
    except Exception as error:
        print(f"[deck_contract] instructional repair failed: {error}")
        return deck
    repaired = copy.deepcopy(deck)
    allowed = set(targets)
    for item in (parsed.get("slides") if isinstance(parsed, dict) else []) or []:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        bullets = [str(value).strip() for value in (item.get("bullets") or []) if str(value).strip()]
        if index not in allowed or not bullets or not str(item.get("title") or "").strip():
            continue
        repaired["slides"][index].update({
            "title": str(item["title"]).strip(),
            "bullets": bullets[:8],
            "notes": str(item.get("notes") or "").strip(),
            "pedagogical_role": str(item.get("pedagogical_role") or "demonstration").strip(),
        })
    return repaired


def specs_by_slide_id(
    structured: Dict[str, Any],
    specs_by_index: Optional[Dict[int, Any]],
) -> Dict[str, Any]:
    slides = structured.get("slides") or []
    result: Dict[str, Any] = {}
    for raw_index, spec in (specs_by_index or {}).items():
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if not (0 <= index < len(slides)) or not isinstance(slides[index], dict):
            continue
        slide_id = str(slides[index].get("slide_id") or "").strip()
        if slide_id:
            result[slide_id] = spec
    return result


def paths_by_slide_id(
    structured: Dict[str, Any],
    paths_by_index: Optional[Dict[int, str]],
) -> Dict[str, str]:
    return {
        slide_id: str(path)
        for slide_id, path in specs_by_slide_id(structured, paths_by_index).items()
    }
