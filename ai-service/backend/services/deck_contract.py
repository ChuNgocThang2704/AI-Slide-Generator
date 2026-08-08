from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Optional

from services.deck_coherence import improve_deck_coherence
from services.lecture_quality import attach_source_page_provenance, enrich_lecture_deck
from services.plan_limits import enforce_plan_slide_limit
from services.slide_text_quality import improve_final_slide_quality


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
    original_count = len(deck.get("slides") or [])

    deck = await improve_final_slide_quality(
        content_extractor,
        deck,
        task_id=task_id,
        source_language=(getattr(content_extractor, "_slide_lang_hint", "auto") or "auto"),
    )
    # Coherence review needs the reliable mode, roles, objectives and source
    # provenance supplied by lecture enrichment. Running it afterwards also
    # lets the judge repair a weak concept/example sequence selectively.
    deck = enrich_lecture_deck(deck, raw_content or "", user_instruction or "")
    deck = attach_source_page_provenance(deck, raw_content or "")
    deck = enforce_plan_slide_limit(deck, plan)
    deck = await improve_deck_coherence(
        content_extractor,
        deck,
        task_id=task_id,
    )
    # A review pass may accidentally remove a requested practice/activity role.
    # Re-apply the pedagogical contract before locking the structure.
    deck = enrich_lecture_deck(deck, raw_content or "", user_instruction or "")
    deck = attach_source_page_provenance(deck, raw_content or "")

    desired_count = int(target_slides) if target_slides else original_count
    desired_count = max(2, desired_count)
    if len(deck.get("slides") or []) != desired_count:
        deck = await content_extractor._force_slide_count_exact(deck, desired_count)
    deck = content_extractor._ensure_deck_boundaries(deck, desired_count)
    if len(deck.get("slides") or []) != desired_count:
        deck = await content_extractor._force_slide_count_exact(deck, desired_count)
    # Count repair and boundary normalization may create replacement slides.
    # Reattach provenance only after the final slide set is stable.
    deck = attach_source_page_provenance(deck, raw_content or "")
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
