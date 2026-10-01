"""Provider-neutral hierarchical content planning contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence, Tuple


def _unit(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class SourceRef:
    chunk_index: int
    page_numbers: Tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"chunk_index": self.chunk_index, "page_numbers": list(self.page_numbers)}


@dataclass(frozen=True)
class ContentSection:
    id: str
    topic: str
    summary: str = field(default="", repr=False)
    importance: float = 0.5
    complexity: float = 0.5
    source_refs: Tuple[SourceRef, ...] = ()
    recommended_slides: int = 0

    @property
    def planning_weight(self) -> float:
        # Importance leads allocation; complexity earns room to explain difficult
        # material. Source length is deliberately not part of this formula.
        return max(0.01, self.importance * 0.65 + self.complexity * 0.35)

    def with_recommended_slides(self, value: int) -> "ContentSection":
        return ContentSection(
            id=self.id,
            topic=self.topic,
            summary=self.summary,
            importance=self.importance,
            complexity=self.complexity,
            source_refs=self.source_refs,
            recommended_slides=max(0, int(value)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "summary": self.summary,
            "importance": self.importance,
            "complexity": self.complexity,
            "source_refs": [ref.to_dict() for ref in self.source_refs],
            "recommended_slides": self.recommended_slides,
        }


@dataclass(frozen=True)
class ContentPlan:
    deck_goal: str
    target_slides: int
    reserved_boundary_slides: int
    sections: Tuple[ContentSection, ...]
    version: int = 1

    @property
    def content_slide_budget(self) -> int:
        return max(0, self.target_slides - self.reserved_boundary_slides)

    def validate(self) -> None:
        if self.target_slides < 2:
            raise ValueError("ContentPlan target_slides must be at least 2")
        if not self.sections:
            raise ValueError("ContentPlan requires at least one section")
        ids = [section.id for section in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("ContentPlan section IDs must be unique")
        allocated = sum(section.recommended_slides for section in self.sections)
        if allocated != self.content_slide_budget:
            raise ValueError(
                f"ContentPlan allocation mismatch: expected={self.content_slide_budget}, actual={allocated}"
            )

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "version": self.version,
            "deck_goal": self.deck_goal,
            "target_slides": self.target_slides,
            "reserved_boundary_slides": self.reserved_boundary_slides,
            "content_slide_budget": self.content_slide_budget,
            "sections": [section.to_dict() for section in self.sections],
        }


def allocate_slide_budget(
    sections: Sequence[ContentSection],
    content_slide_budget: int,
) -> Tuple[ContentSection, ...]:
    """Allocate an exact budget using weighted largest remainders.

    Every section receives one slide when the budget permits. When it does not,
    highest semantic weights win; no content is merged or rewritten here.
    """
    clean = tuple(sections)
    budget = max(0, int(content_slide_budget))
    if not clean:
        return ()
    allocations = [0] * len(clean)
    ranked = sorted(range(len(clean)), key=lambda idx: (-clean[idx].planning_weight, idx))
    for idx in ranked[: min(budget, len(clean))]:
        allocations[idx] = 1
    remaining = budget - sum(allocations)
    if remaining > 0:
        weight_total = sum(section.planning_weight for section in clean)
        quotas = [remaining * section.planning_weight / weight_total for section in clean]
        floors = [int(quota) for quota in quotas]
        allocations = [value + floors[idx] for idx, value in enumerate(allocations)]
        leftovers = budget - sum(allocations)
        remainder_order = sorted(
            range(len(clean)),
            key=lambda idx: (-(quotas[idx] - floors[idx]), -clean[idx].importance, idx),
        )
        for idx in remainder_order[:leftovers]:
            allocations[idx] += 1
    return tuple(section.with_recommended_slides(allocations[idx]) for idx, section in enumerate(clean))


def content_plan_from_sections(
    *,
    deck_goal: str,
    sections: Iterable[Mapping[str, Any]],
    target_slides: int,
    reserved_boundary_slides: int = 2,
) -> ContentPlan:
    normalized = []
    for index, raw in enumerate(sections):
        topic = str(raw.get("topic") or raw.get("title") or f"Section {index + 1}").strip()
        summary_value = raw.get("summary") or raw.get("description") or raw.get("bullets") or ""
        if isinstance(summary_value, (list, tuple)):
            summary_value = "\n".join(str(item) for item in summary_value if str(item).strip())
        pages = raw.get("source_pages") or raw.get("page_numbers") or ()
        page_numbers = tuple(sorted({int(page) for page in pages if str(page).isdigit() and int(page) > 0}))
        normalized.append(ContentSection(
            id=str(raw.get("id") or f"section-{index + 1}"),
            topic=topic,
            summary=str(summary_value or ""),
            importance=_unit(raw.get("importance")),
            complexity=_unit(raw.get("complexity")),
            source_refs=(SourceRef(chunk_index=int(raw.get("chunk_index", index)), page_numbers=page_numbers),),
        ))
    allocated = allocate_slide_budget(normalized, max(0, int(target_slides) - int(reserved_boundary_slides)))
    plan = ContentPlan(
        deck_goal=str(deck_goal or "Create a coherent presentation").strip(),
        target_slides=max(2, int(target_slides)),
        reserved_boundary_slides=max(0, int(reserved_boundary_slides)),
        sections=allocated,
    )
    plan.validate()
    return plan

