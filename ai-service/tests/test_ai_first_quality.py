import json
import unittest

from services.content.slide_normalizer import SlideNormalizerMixin
from services.slide_quality import build_visual_plan
from services.slide_text_quality import improve_slide_titles_quality
from routes.api import _detect_generate_images_request
from services.revision_rules import revision_prompt_mentions_image, revision_prompt_mentions_table


class SlideCountExtractor(SlideNormalizerMixin):
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    async def _request_json_dict(self, messages, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


class VisualExtractor:
    def __init__(self, visual):
        self.visual = visual

    async def _llm_completion_plain_text(self, messages, **kwargs):
        return json.dumps({"slides": [{"slide_index": 0, "visual": self.visual}]})


class AllNoneVisualExtractor:
    async def _llm_completion_plain_text(self, messages, **kwargs):
        payload = json.loads(messages[-1]["content"])
        return json.dumps({
            "slides": [
                {"slide_index": slide["slide_index"], "visual": "none"}
                for slide in payload["slides"]
            ],
        })


class FailingTitleExtractor:
    async def _llm_completion_plain_text(self, messages, **kwargs):
        raise RuntimeError("provider unavailable")


class AiFirstQualityTest(unittest.IsolatedAsyncioTestCase):
    async def test_exact_slide_count_does_not_call_ai(self):
        deck = {"title": "Deck", "slides": [{"title": "Only", "bullets": ["One idea"]}]}
        extractor = SlideCountExtractor(error=AssertionError("AI should not be called"))

        result = await extractor._force_slide_count_exact(deck, 1)

        self.assertIs(result, deck)
        self.assertEqual(extractor.calls, 0)

    async def test_ai_recomposes_wrong_slide_count_without_cloning(self):
        original = {
            "title": "Deck",
            "slides": [{"title": "Only", "bullets": ["One idea"], "notes": "Note"}],
        }
        response = {
            "title": "Deck",
            "slides": [
                {"title": "Context", "bullets": ["Problem context"], "notes": "Explain context"},
                {"title": "Solution", "bullets": ["Proposed solution"], "notes": "Explain solution"},
            ],
        }
        extractor = SlideCountExtractor(response=response)

        result = await extractor._force_slide_count_exact(original, 2)

        self.assertEqual(len(result["slides"]), 2)
        self.assertNotEqual(result["slides"][0]["title"], result["slides"][1]["title"])
        self.assertEqual(extractor.calls, 1)

    async def test_slide_count_failure_keeps_original_deck(self):
        original = {"title": "Deck", "slides": [{"title": "Only", "bullets": ["One idea"]}]}
        extractor = SlideCountExtractor(error=RuntimeError("provider unavailable"))

        result = await extractor._force_slide_count_exact(original, 2)

        self.assertIs(result, original)
        self.assertEqual(len(result["slides"]), 1)

    async def test_llm_can_override_keyword_heuristic(self):
        deck = {"slides": [{
            "title": "Comparison",
            "bullets": ["Criterion: qualitative discussion; option A versus option B"],
            "layout": "text_only",
        }]}

        plan = await build_visual_plan(VisualExtractor("none"), deck, "", want_images=False)

        self.assertEqual(plan[0], "none")

    async def test_existing_table_contract_cannot_be_overridden(self):
        deck = {"slides": [{
            "title": "Comparison",
            "bullets": ["Structured comparison"],
            "layout": "text_table",
            "table": {"headers": ["A", "B"], "rows": [["1", "2"]]},
        }]}

        plan = await build_visual_plan(VisualExtractor("none"), deck, "", want_images=False)

        self.assertEqual(plan[0], "table")

    async def test_requested_images_rejects_degenerate_all_none_plan(self):
        deck = {"slides": [{
            "title": "Historical context",
            "bullets": ["A concrete event that benefits from an illustration"],
            "layout": "text_only",
        }]}

        plan = await build_visual_plan(VisualExtractor("none"), deck, "", want_images=True)

        self.assertEqual(plan[0], "image")

    async def test_requested_images_enforces_deck_level_minimum(self):
        deck = {
            "slides": [
                {"title": f"Topic {index}", "bullets": ["One", "Two"], "layout": "text_only"}
                for index in range(10)
            ],
        }

        plan = await build_visual_plan(AllNoneVisualExtractor(), deck, "", want_images=True)

        self.assertGreaterEqual(sum(visual == "image" for visual in plan.values()), 3)
        longest_none_run = 0
        current_none_run = 0
        for index in range(len(deck["slides"])):
            if plan[index] == "none":
                current_none_run += 1
                longest_none_run = max(longest_none_run, current_none_run)
            else:
                current_none_run = 0
        self.assertLessEqual(longest_none_run, 4)

    async def test_title_review_failure_does_not_rewrite_from_bullets(self):
        deck = {"slides": [{
            "title": "API",
            "bullets": ["The API coordinates all system integrations"],
        }]}

        result = await improve_slide_titles_quality(FailingTitleExtractor(), deck)

        self.assertEqual(result["slides"][0]["title"], "API")

    def test_image_generation_negation_wins_over_image_keyword(self):
        self.assertFalse(_detect_generate_images_request("Tạo 6 slide, không sinh ảnh"))
        self.assertFalse(_detect_generate_images_request("Create 6 slides without images"))
        self.assertTrue(_detect_generate_images_request("Tạo 6 slide có hình minh họa"))

    def test_revision_negation_does_not_trigger_visual_operation(self):
        self.assertFalse(revision_prompt_mentions_image("Giữ nguyên ảnh slide 3"))
        self.assertFalse(revision_prompt_mentions_table("Không dùng bảng, chỉ trình bày bằng text"))

    def test_normalizer_does_not_write_notes_or_cut_long_bullet(self):
        extractor = SlideCountExtractor()
        long_bullet = " ".join(f"word{index}" for index in range(45))
        long_title = "A complete presentation title " + "with important context " * 8
        deck = {"title": "Deck", "slides": [{
            "title": long_title,
            "bullets": [long_bullet],
            "notes": "",
        }]}

        result = extractor._normalize_structured_content(deck)

        self.assertEqual(result["slides"][0]["notes"], "")
        self.assertIn("word44", result["slides"][0]["bullets"][0])
        self.assertEqual(result["slides"][0]["title"], long_title.strip())


if __name__ == "__main__":
    unittest.main()
