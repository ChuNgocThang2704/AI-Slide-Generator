import pytest

from services.content_plan import ContentPlan, ContentSection, allocate_slide_budget, content_plan_from_sections
from services.content.chunking import _planning_score


def test_allocation_uses_importance_and_complexity_and_matches_budget():
    sections = [
        ContentSection(id="core", topic="Core", importance=1.0, complexity=0.9),
        ContentSection(id="context", topic="Context", importance=0.4, complexity=0.2),
        ContentSection(id="detail", topic="Detail", importance=0.2, complexity=0.3),
    ]
    allocated = allocate_slide_budget(sections, 7)

    assert sum(section.recommended_slides for section in allocated) == 7
    assert allocated[0].recommended_slides > allocated[1].recommended_slides
    assert all(section.recommended_slides >= 1 for section in allocated)


def test_small_budget_reports_unallocated_sections_without_rewriting_them():
    sections = [
        ContentSection(id="a", topic="A", importance=0.1),
        ContentSection(id="b", topic="B", importance=0.9),
        ContentSection(id="c", topic="C", importance=0.5),
    ]
    allocated = allocate_slide_budget(sections, 2)

    assert [section.topic for section in allocated] == ["A", "B", "C"]
    assert sum(section.recommended_slides for section in allocated) == 2
    assert allocated[1].recommended_slides == 1
    assert allocated[2].recommended_slides == 1


def test_plan_serializes_source_references_and_exact_body_budget():
    plan = content_plan_from_sections(
        deck_goal="Explain the source",
        target_slides=6,
        sections=[
            {"title": "First", "bullets": ["A", "B"], "source_pages": [2, 1, 2], "importance": 0.8},
            {"title": "Second", "description": "C", "source_pages": [9], "complexity": 0.9},
        ],
    )
    payload = plan.to_dict()

    assert payload["content_slide_budget"] == 4
    assert sum(section["recommended_slides"] for section in payload["sections"]) == 4
    assert payload["sections"][0]["source_refs"][0]["page_numbers"] == [1, 2]


def test_plan_preserves_original_chunk_index_and_clamps_planning_scores():
    plan = content_plan_from_sections(
        deck_goal="Trace the source",
        target_slides=4,
        sections=[
            {
                "title": "Split subsection",
                "chunk_index": 7,
                "source_pages": [11, 12],
                "importance": 3,
                "complexity": -1,
            }
        ],
    )
    section = plan.to_dict()["sections"][0]

    assert section["source_refs"] == [{"chunk_index": 7, "page_numbers": [11, 12]}]
    assert section["importance"] == 1.0
    assert section["complexity"] == 0.0
    assert _planning_score("not-a-number", 0.7) == 0.7


def test_invalid_duplicate_ids_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        ContentPlan(
            deck_goal="Test", target_slides=4, reserved_boundary_slides=2,
            sections=(
                ContentSection(id="same", topic="A", recommended_slides=1),
                ContentSection(id="same", topic="B", recommended_slides=1),
            ),
        ).validate()
