"""Shared source-grounding policy for planning, authoring, and review."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Tuple

from services.generation_context import GenerationMode, extractor_context


_NUMBER_RE = re.compile(
    r"(?<![\w])(?:[$€£₫]\s*)?[-+]?\d+(?:[.,]\d+)*(?:\s*(?:%|‰|k|m|bn|tr|triệu|tỷ|ty))?(?![\w])",
    re.IGNORECASE,
)


class GroundingMode(str, Enum):
    PROMPT = "prompt"
    DOCUMENT = "document"


def _normalize_anchor(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def extract_numeric_anchors(text: str, *, limit: int = 120) -> Tuple[str, ...]:
    """Return stable, de-duplicated numeric/date-like claims in source order."""
    seen = set()
    anchors = []
    for match in _NUMBER_RE.finditer(str(text or "")):
        raw = match.group(0).strip()
        normalized = _normalize_anchor(raw)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        anchors.append(raw)
        if len(anchors) >= max(0, int(limit)):
            break
    return tuple(anchors)


@dataclass(frozen=True)
class GroundingPolicy:
    mode: GroundingMode
    numeric_anchors: Tuple[str, ...] = field(default_factory=tuple, repr=False)

    @property
    def source_is_authoritative(self) -> bool:
        return self.mode == GroundingMode.DOCUMENT

    def instruction_block(self) -> str:
        common = (
            "Preserve exact names, dates, quantities, units, formulas, qualifications, and causal direction. "
            "Never invent quotations, citations, research results, document-specific claims, or statistics. "
            "If evidence is absent, omit the claim or use a clearly non-factual activity/question; never expose "
            "internal messages about missing evidence in user-facing slide text."
        )
        if self.source_is_authoritative:
            return (
                "GROUNDING MODE: DOCUMENT. The supplied source is the factual authority. User instructions control "
                "scope, audience, order, and style but cannot override source facts. Every document-specific factual "
                "claim must be supported by the source. If the requested slide count exceeds the distinct source "
                "facts, vary the VIEW of supported evidence (overview, exact figures, comparison, transparent "
                "calculation, source-backed takeaway, or an explicitly labelled discussion question). Never invent "
                "causes, business actions, recommendations, future plans, stakeholders, or background events merely "
                f"to fill slides. {common}"
            )
        return (
            "GROUNDING MODE: PROMPT. The user instruction is the scope authority. You may add stable foundational "
            "knowledge needed to explain the topic, but do not fabricate precise facts or imply that generated "
            f"background came from an uploaded document. {common}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "source_is_authoritative": self.source_is_authoritative,
            "numeric_anchors": list(self.numeric_anchors),
        }


def policy_for_extractor(extractor: Any, source_text: str) -> GroundingPolicy:
    context = extractor_context(extractor)
    if context and context.mode != GenerationMode.AUTO:
        document_mode = context.mode == GenerationMode.DOCUMENT
    else:
        document_mode = bool(getattr(extractor, "_is_document_mode", False))
    instruction = context.user_instruction if context else str(
        getattr(extractor, "_user_instruction", "") or ""
    )
    anchor_text = f"{source_text}\n{instruction}" if document_mode else ""
    return GroundingPolicy(
        mode=GroundingMode.DOCUMENT if document_mode else GroundingMode.PROMPT,
        numeric_anchors=extract_numeric_anchors(anchor_text) if document_mode else (),
    )


_PAGE_MARKER_RE = re.compile(r"^\s*PAGE\s+\d+\s*", re.IGNORECASE)
_FACT_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\n+")


def sparse_document_slide_cap(source_text: str, requested_slides: int) -> int:
    """Cap the requested slide count when a document has too few distinct
    facts to fill it without duplicating content or inventing filler.

    Counts sentence/clause-sized fragments in the source (stripping "PAGE N"
    markers) as a rough proxy for distinct facts, then allows roughly one
    slide per fact plus an intro and a closing slide. Never raises the
    requested count, only lowers it.
    """
    requested = max(1, int(requested_slides or 0))
    parts = (_PAGE_MARKER_RE.sub("", p).strip() for p in _FACT_SPLIT_RE.split(str(source_text or "")))
    fact_count = sum(1 for p in parts if len(p) > 8)
    if fact_count == 0:
        return requested
    return max(3, min(requested, fact_count + 2))


def unsupported_numeric_anchors(texts: Iterable[str], policy: GroundingPolicy) -> Tuple[str, ...]:
    """Find numeric claims absent from an authoritative document's anchor set."""
    if not policy.source_is_authoritative:
        return ()
    allowed = {_normalize_anchor(value) for value in policy.numeric_anchors}
    unsupported = []
    seen = set()
    for text in texts:
        for anchor in extract_numeric_anchors(text):
            normalized = _normalize_anchor(anchor)
            if normalized not in allowed and normalized not in seen:
                seen.add(normalized)
                unsupported.append(anchor)
    return tuple(unsupported)
