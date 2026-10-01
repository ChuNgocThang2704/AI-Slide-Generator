import asyncio

from services.content.chunking import ChunkingMixin
from services.content_plan import content_plan_from_sections


class PlanningHarness(ChunkingMixin):
    _user_instruction = "Explain clearly"
    _presentation_mode = "lecture"
    _generation_context = None

    def __init__(self):
        self.legacy_calls = 0

    async def _expand_group_generate_refine_pipeline(self, merged_summary, target_slides):
        self.legacy_calls += 1
        return {"title": "Fallback", "slides": [{"title": "Body", "bullets": ["Fact"]}]}

    async def _force_slide_count_exact(self, result, target_slides):
        result["slides"] = result["slides"] * target_slides
        return result


def test_content_plan_pipeline_falls_back_without_losing_plan(monkeypatch):
    async def fail_planner(*args, **kwargs):
        raise TimeoutError("planner unavailable")

    monkeypatch.setattr("services.deck_planner.generate_outline_first_deck", fail_planner)
    harness = PlanningHarness()
    plan = content_plan_from_sections(
        deck_goal="Teach the source",
        target_slides=4,
        sections=[{"title": "Core", "bullets": ["Fact"], "chunk_index": 2}],
    )

    result = asyncio.run(
        harness._generate_from_content_plan(
            {"title": "Source", "content": "## Core\n- Fact"}, 4, plan
        )
    )

    assert harness.legacy_calls == 1
    assert len(result["slides"]) == 4
    assert result["_content_plan_fallback"] is True
    assert result["_content_plan"]["sections"][0]["source_refs"][0]["chunk_index"] == 2
