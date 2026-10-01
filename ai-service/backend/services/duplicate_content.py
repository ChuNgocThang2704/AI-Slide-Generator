"""Deterministic-first duplicate detection for authored slide content."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable, Dict, Optional, Sequence

from services.source_retrieval import cosine_similarity, embed_texts


_PROTECTED_ROLES = {"learning_objectives", "objectives", "summary"}
_PROTECTED_LAYOUTS = {"intro", "title", "thankyou", "thank_you", "closing"}


def _fold(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_like = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^\w]+", " ", ascii_like.casefold()).strip()


def _slide_text(slide: Dict[str, Any]) -> str:
    bullets = slide.get("bullets") or []
    if isinstance(bullets, str):
        bullets = [bullets]
    return "\n".join([
        str(slide.get("title") or ""),
        *(str(value) for value in bullets if str(value).strip()),
    ]).strip()


def _candidate_indices(deck: Dict[str, Any]) -> list[int]:
    result = []
    for index, slide in enumerate(deck.get("slides") or []):
        if not isinstance(slide, dict):
            continue
        role = str(slide.get("pedagogical_role") or "").strip().lower()
        layout = str(slide.get("layout") or "").strip().lower()
        if role in _PROTECTED_ROLES or layout in _PROTECTED_LAYOUTS:
            continue
        if len(_fold(_slide_text(slide))) >= 24:
            result.append(index)
    return result


def _issue(duplicate: int, original: int, method: str, score: float) -> dict[str, Any]:
    return {
        "index": duplicate,
        "slide_index": duplicate,
        "type": "duplicate_content",
        "severity": "high" if method == "exact" else "medium",
        "target_fields": ["title", "bullets", "notes"],
        "instruction": (
            f"Rewrite this slide to fulfill its own outline purpose without repeating slide {original + 1}. "
            "Preserve source-grounded facts and do not modify the original slide."
        ),
        "evidence": f"duplicate_of={original}; method={method}; similarity={score:.4f}",
    }


def detect_duplicate_content(
    deck: Dict[str, Any],
    *,
    model_name: str,
    semantic_enabled: bool = True,
    semantic_threshold: float = 0.92,
    embedder: Optional[Callable[[Sequence[str]], Sequence[Sequence[float]]]] = None,
) -> list[dict[str, Any]]:
    """Return issues for later duplicates, failing closed if embeddings are unavailable."""
    indices = _candidate_indices(deck)
    slides = deck.get("slides") or []
    texts = [_slide_text(slides[index]) for index in indices]
    fingerprints = [_fold(text) for text in texts]
    issues = []
    owners: dict[str, int] = {}
    for position, fingerprint in enumerate(fingerprints):
        if fingerprint in owners:
            original_position = owners[fingerprint]
            issues.append(_issue(indices[position], indices[original_position], "exact", 1.0))
        else:
            owners[fingerprint] = position

    if not semantic_enabled or len(texts) < 2:
        return issues
    try:
        vectors = embed_texts(texts, model_name=model_name, embedder=embedder)
    except Exception as error:
        print(f"[duplicate_content] embedding unavailable; exact-only: {error}")
        return issues
    if len(vectors) != len(texts):
        return issues
    already_targeted = {issue["index"] for issue in issues}
    for later in range(1, len(indices)):
        if indices[later] in already_targeted:
            continue
        best_position = None
        best_score = -1.0
        for earlier in range(later):
            earlier_role = str(slides[indices[earlier]].get("pedagogical_role") or "").lower()
            later_role = str(slides[indices[later]].get("pedagogical_role") or "").lower()
            teaching_roles = {"worked_example", "demonstration", "practice", "knowledge_check"}
            if earlier_role != later_role and ({earlier_role, later_role} & teaching_roles):
                continue
            score = cosine_similarity(vectors[earlier], vectors[later])
            if score > best_score:
                best_position, best_score = earlier, score
        if best_position is not None and best_score >= semantic_threshold:
            issues.append(_issue(indices[later], indices[best_position], "embedding", best_score))
            already_targeted.add(indices[later])
    return issues
