import asyncio
import json

import pytest

from services.deck_planner import generate_outline_first_deck


class FakeExtractor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = []

    async def _llm_completion_plain_text(self, messages, **_kwargs):
        self.messages.append(messages)
        return json.dumps(self.responses.pop(0), ensure_ascii=False)


def test_outline_first_locks_exact_count_and_requirements():
    outline = [
        {"index": index, "title": f"Slide {index + 1}", "purpose": "Teach one idea", "required_components": [], "pedagogical_role": "concept", "layout_hint": "text_only"}
        for index in range(5)
    ]
    outline[0]["layout_hint"] = "intro"
    outline[-1]["layout_hint"] = "thankyou"
    outline[-1]["pedagogical_role"] = "summary"
    authored_slides = [
        {"title": f"Slide {index + 1}", "bullets": ["Complete content."], "notes": "Notes.", "layout": "text_only", "pedagogical_role": "concept"}
        for index in range(5)
    ]
    authored_slides[-1]["pedagogical_role"] = "summary"
    extractor = FakeExtractor([
        {
            "deck_title": "Python Functions",
            "requirement_spec": [{"id": "r1", "description": "Show return", "required_components": ["return"], "assigned_slide_indices": [3]}],
            "outline": outline,
        },
        {
            "title": "Python Functions",
            "presentation_mode": "lecture",
            "learning_objectives": ["Explain return values."],
            "slides": authored_slides,
        },
    ])
    deck = asyncio.run(generate_outline_first_deck(
        extractor,
        source_text="Functions may return values.",
        user_instruction="Create five lecture slides with a return example.",
        target_slides=5,
        presentation_mode="lecture",
        language="en",
    ))
    assert len(deck["slides"]) == 5
    assert deck["slides"][0]["layout"] == "intro"
    assert deck["slides"][-1]["layout"] == "thankyou"
    assert deck["requirement_spec"][0]["required_components"] == ["return"]
    assert deck["_outline_locked"] is True
    assert len(extractor.messages) == 2


def test_outline_first_rejects_wrong_outline_count():
    invalid_plan = {
        "deck_title": "Bad",
        "requirement_spec": [],
        "outline": [{"index": 0, "title": "Only one", "purpose": "Too short"}],
    }
    extractor = FakeExtractor([invalid_plan, invalid_plan])
    with pytest.raises(ValueError, match="exact-count structure contract"):
        asyncio.run(generate_outline_first_deck(
            extractor,
            source_text="Source",
            user_instruction="Create five slides",
            target_slides=5,
            presentation_mode="presentation",
            language="en",
        ))


def test_repaired_lecture_outline_keeps_exact_structure_when_role_labels_are_weak():
    invalid_plan = {
        "deck_title": "Functions",
        "requirement_spec": [],
        "outline": [{"index": 1, "title": "Only one", "purpose": "Invalid"}],
    }
    repaired_outline = [
        {
            "index": index + 1,
            "title": f"Slide {index + 1}",
            "purpose": "Teach one coherent part",
            "required_components": [],
            "pedagogical_role": "body",
            "layout_hint": "text_only",
        }
        for index in range(6)
    ]
    repaired_outline[0]["layout_hint"] = "intro"
    repaired_outline[-1]["layout_hint"] = "thankyou"
    repaired_outline[-1]["pedagogical_role"] = "summary"
    authored = [
        {
            "title": item["title"],
            "bullets": ["Substantive content."],
            "notes": "Speaker notes.",
            "layout": item["layout_hint"],
            "pedagogical_role": item["pedagogical_role"],
        }
        for item in repaired_outline
    ]
    extractor = FakeExtractor([
        invalid_plan,
        {"deck_title": "Functions", "requirement_spec": [], "outline": repaired_outline},
        {
            "title": "Functions",
            "presentation_mode": "lecture",
            "learning_objectives": [],
            "slides": authored,
        },
    ])

    deck = asyncio.run(generate_outline_first_deck(
        extractor,
        source_text="Functions group reusable behavior.",
        user_instruction="Create six lecture slides about functions.",
        target_slides=6,
        presentation_mode="lecture",
        language="en",
    ))

    assert len(deck["slides"]) == 6
    assert deck["_outline_locked"] is True
    assert len(extractor.messages) == 3
