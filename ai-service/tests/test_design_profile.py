import copy

import pytest

from services.design_profile import build_design_plan


def _locked_deck():
    return {
        "title": "AI systems",
        "presentation_mode": "lecture",
        "_structure_locked": True,
        "_structure_signature": ["s1", "s2", "s3", "s4"],
        "slides": [
            {"slide_id": "s1", "layout": "intro", "title": "AI systems"},
            {"slide_id": "s2", "layout": "split_columns", "title": "Compare"},
            {"slide_id": "s3", "layout": "text_only", "title": "Results", "chart": {"values": [1, 2]}},
            {"slide_id": "s4", "layout": "thankyou", "title": "Thanks"},
        ],
    }


def test_design_intent_maps_existing_layouts_without_changing_locked_deck():
    deck = _locked_deck()
    original = copy.deepcopy(deck)

    plan = build_design_plan(deck)

    assert deck == original
    assert [slide.layout for slide in plan.slides] == [
        "intro", "two_columns", "text_chart", "thankyou"
    ]
    assert [slide.visual_type for slide in plan.slides] == ["none", "none", "chart", "none"]
    assert plan.profile.typography == "educational"
    assert all("x" not in slide.to_dict() and "y" not in slide.to_dict() for slide in plan.slides)


def test_design_intent_requires_structure_lock_and_stable_ids():
    deck = _locked_deck()
    deck["_structure_locked"] = False
    with pytest.raises(ValueError, match="structure-locked"):
        build_design_plan(deck)

    deck = _locked_deck()
    deck["slides"][1]["slide_id"] = "changed"
    with pytest.raises(ValueError, match="identity changed"):
        build_design_plan(deck)
