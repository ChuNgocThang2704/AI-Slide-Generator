import unittest
from unittest.mock import AsyncMock, patch

from services.content.slide_pipeline import SlidePipelineMixin
from services.images.pipeline import _score_slide_for_image_async


class RevisionPlannerExtractor(SlidePipelineMixin):
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.last_messages = None

    def _normalize_structured_content(self, structured):
        return structured

    def _llm_system_prefix(self):
        return ""

    async def _request_json_dict(self, messages, **kwargs):
        self.last_messages = messages
        if self.error:
            raise self.error
        return self.response


class RevisionPlannerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.deck = {
            "title": "AI",
            "slides": [
                {"title": "Overview", "bullets": ["Context"]},
                {"title": "Applications", "bullets": ["Examples"]},
                {"title": "Conclusion", "bullets": ["Summary"]},
            ],
        }

    async def test_selected_slide_is_context_not_forced_target(self):
        extractor = RevisionPlannerExtractor(response={
            "scope": "deck",
            "target_slide_numbers": [],
            "operations": [
                {"type": "regenerate_image", "instruction": "Add suitable visuals"},
            ],
            "preserve_unmentioned": True,
        })

        plan = await extractor.plan_slide_revision(
            self.deck,
            "Add more suitable visuals throughout the presentation",
            context_slide_number=2,
        )

        self.assertTrue(plan["planner_succeeded"])
        self.assertEqual(plan["scope"], "deck")
        self.assertEqual(plan["target_slide_numbers"], [])
        self.assertEqual(plan["operations"][0]["type"], "regenerate_image")

    async def test_prompt_target_can_differ_from_selected_slide(self):
        extractor = RevisionPlannerExtractor(response={
            "scope": "slides",
            "target_slide_numbers": [1],
            "operations": [
                {"type": "rewrite_text", "instruction": "Improve the title"},
            ],
            "preserve_unmentioned": True,
        })

        plan = await extractor.plan_slide_revision(
            self.deck,
            "Improve the title on slide 1",
            context_slide_number=3,
        )

        self.assertEqual(plan["target_slide_numbers"], [1])

    async def test_selected_slide_is_used_only_when_planner_fails(self):
        extractor = RevisionPlannerExtractor(error=RuntimeError("provider unavailable"))

        plan = await extractor.plan_slide_revision(
            self.deck,
            "Make this title clearer",
            context_slide_number=2,
        )

        self.assertFalse(plan["planner_succeeded"])
        self.assertEqual(plan["scope"], "slides")
        self.assertEqual(plan["target_slide_numbers"], [2])


class ImageSemanticPriorityTest(unittest.IsolatedAsyncioTestCase):
    async def test_confident_semantic_result_can_select_cover_image(self):
        semantic = {
            "content_type": "normal",
            "source": "qwen_vl",
            "confidence": 0.92,
        }
        slide = {
            "title": "AI transformation",
            "bullets": ["A concrete transformation story", "A visual opening"],
        }
        with patch(
            "services.images.semantics._get_image_semantic",
            new=AsyncMock(return_value=semantic),
        ):
            score = await _score_slide_for_image_async(None, slide, 0)

        self.assertEqual(score, 2)

    async def test_metadata_keywords_only_apply_to_low_confidence_fallback(self):
        semantic = {
            "content_type": "normal",
            "source": "rule",
            "confidence": 0.0,
        }
        slide = {
            "title": "Muc luc",
            "bullets": ["Part one", "Part two"],
        }
        with patch(
            "services.images.semantics._get_image_semantic",
            new=AsyncMock(return_value=semantic),
        ):
            score = await _score_slide_for_image_async(None, slide, 1)

        self.assertEqual(score, 0)


if __name__ == "__main__":
    unittest.main()
