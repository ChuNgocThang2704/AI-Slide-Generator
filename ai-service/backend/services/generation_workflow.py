"""Shared application workflow seams for slide generation.

HTTP and Redis remain transport adapters. This module owns only behavior that
was already duplicated by both paths; visual artifact orchestration stays out
until its current behavior has characterization coverage.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from services.deck_contract import assert_deck_structure_locked, finalize_deck_for_visuals
from services.slide_quality import improve_deck_source_grounding
from services.design_profile import build_design_plan


async def ground_finalize_and_lock(
    content_extractor,
    structured: Dict[str, Any],
    *,
    raw_content: str,
    user_instruction: str,
    task_id: str,
    plan: str,
    target_slides: Optional[int],
    restore_exact_count_after_grounding: bool = False,
) -> Tuple[Dict[str, Any], tuple[str, ...]]:
    """Apply the common pre-visual grounding/finalization contract.

    `restore_exact_count_after_grounding` preserves the small historical
    difference between existing adapters while they are migrated incrementally.
    """
    deck = structured
    if not deck.get("_explicit_slide_mode") and not deck.get("_outline_locked"):
        deck = await improve_deck_source_grounding(
            content_extractor,
            deck,
            raw_content or "",
            task_id=task_id,
        )
        if restore_exact_count_after_grounding and target_slides and isinstance(deck, dict):
            deck = await content_extractor._force_slide_count_exact(deck, int(target_slides))

    deck = await finalize_deck_for_visuals(
        content_extractor,
        deck,
        raw_content=raw_content or "",
        user_instruction=user_instruction or "",
        task_id=task_id,
        plan=plan,
        target_slides=target_slides,
    )
    signature = assert_deck_structure_locked(deck)
    # Observational extension boundary only: renderer and public deck stay unchanged.
    try:
        content_extractor._design_plan = build_design_plan(deck)
    except ValueError as error:
        # Design preparation must never break an otherwise valid content deck.
        content_extractor._design_plan = None
        print(f"[design_profile] planning skipped: {error}")
    return deck, signature
