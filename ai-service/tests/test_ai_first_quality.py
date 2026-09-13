import json
import unittest

from services.content.slide_normalizer import SlideNormalizerMixin
from services.slide_quality import build_visual_plan
from services.slide_charts import (
    _chart_from_inline_table,
    _chart_spec_has_text_evidence,
    build_chart_specs_for_slides,
    normalize_chart_spec,
)
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


class SplitColumnVisualExtractor:
    async def _llm_completion_plain_text(self, messages, **kwargs):
        return json.dumps({
            "slides": [{
                "slide_index": 0,
                "visual": "none",
                "composition": "split_columns",
                "left_heading": "Cơ hội",
                "right_heading": "Thách thức",
                "left_indices": [0, 2],
                "right_indices": [1, 3],
            }],
        })


class AllImageVisualExtractor:
    async def _llm_completion_plain_text(self, messages, **kwargs):
        payload = json.loads(messages[-1]["content"])
        return json.dumps({
            "slides": [
                {
                    "slide_index": slide["slide_index"],
                    "visual": "image",
                    "image_priority": 0.5,
                    "composition": "standard",
                }
                for slide in payload["slides"]
            ],
        })


class ChartFallbackExtractor:
    pass


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

    async def test_chart_title_converts_numeric_inline_table_to_chart(self):
        slide = {
            "title": "Biểu đồ: Thị trường AI trong giáo dục (2020-2023)",
            "bullets": ["2020: 1.5", "2021: 2.0", "2022: 2.7", "2023: 3.5"],
            "layout": "text_table",
            "table": {
                "title": "Thị trường AI",
                "headers": ["Năm", "Tỷ USD"],
                "rows": [["2020", "1.5"], ["2021", "2.0"], ["2022", "2.7"], ["2023", "3.5"]],
            },
        }

        plan = await build_visual_plan(VisualExtractor("none"), {"slides": [slide]}, "", want_images=False)
        chart = _chart_from_inline_table(slide)

        self.assertEqual(plan[0], "chart")
        self.assertIsNotNone(chart)
        self.assertEqual(chart["labels"], ["2020", "2021", "2022", "2023"])
        self.assertEqual(chart["series"][0]["values"], [1.5, 2.0, 2.7, 3.5])

    async def test_requested_images_rejects_degenerate_all_none_plan(self):
        deck = {"slides": [{
            "title": "Historical context",
            "bullets": ["A concrete event that benefits from an illustration"],
            "layout": "text_only",
        }]}

        plan = await build_visual_plan(VisualExtractor("none"), deck, "", want_images=True)

        self.assertEqual(plan[0], "image")

    async def test_visual_planner_can_apply_supported_split_column_contract(self):
        deck = {"slides": [{
            "title": "Hai góc nhìn",
            "bullets": ["Lợi ích một", "Rủi ro một", "Lợi ích hai", "Rủi ro hai"],
            "layout": "text_only",
        }]}

        plan = await build_visual_plan(SplitColumnVisualExtractor(), deck, "", want_images=False)

        self.assertEqual(plan[0], "none")
        self.assertEqual(deck["slides"][0]["layout"], "split_columns")
        self.assertEqual(deck["slides"][0]["bullets"][0], "Cơ hội — Lợi ích một")
        self.assertEqual(deck["slides"][0]["bullets"][2], "Thách thức — Rủi ro một")

    async def test_requested_images_enforces_deck_level_minimum(self):
        deck = {
            "slides": [
                {"title": f"Topic {index}", "bullets": ["One", "Two"], "layout": "text_only"}
                for index in range(10)
            ],
        }

        plan = await build_visual_plan(AllNoneVisualExtractor(), deck, "", want_images=True)

        self.assertGreaterEqual(sum(visual == "image" for visual in plan.values()), 5)
        longest_none_run = 0
        current_none_run = 0
        for index in range(len(deck["slides"])):
            if plan[index] == "none":
                current_none_run += 1
                longest_none_run = max(longest_none_run, current_none_run)
            else:
                current_none_run = 0
        self.assertLessEqual(longest_none_run, 2)

    async def test_visual_balance_excludes_cover_and_closing_from_image_target(self):
        deck = {
            "slides": [
                {"title": "Cover", "bullets": ["Subtitle"], "layout": "intro"},
                *[
                    {"title": f"Topic {index}", "bullets": ["One", "Two"], "layout": "text_only"}
                    for index in range(8)
                ],
                {"title": "Closing", "bullets": ["Thank you"], "layout": "thankyou"},
            ],
        }

        plan = await build_visual_plan(AllNoneVisualExtractor(), deck, "", want_images=True)

        self.assertEqual(plan[0], "none")
        self.assertEqual(plan[9], "none")
        self.assertGreaterEqual(
            sum(plan[index] == "image" for index in range(1, 9)),
            4,
        )

    async def test_visual_balance_caps_excessive_image_routing(self):
        deck = {
            "slides": [
                {"title": "Cover", "bullets": ["Subtitle"], "layout": "intro"},
                *[
                    {"title": f"Topic {index}", "bullets": ["One", "Two"], "layout": "text_only"}
                    for index in range(8)
                ],
                {"title": "Closing", "bullets": ["Thank you"], "layout": "thankyou"},
            ],
        }

        plan = await build_visual_plan(AllImageVisualExtractor(), deck, "", want_images=True)

        self.assertEqual(sum(plan[index] == "image" for index in range(1, 9)), 5)
        self.assertEqual(plan[0], "none")
        self.assertEqual(plan[9], "none")

    async def test_unmatched_raw_chart_does_not_block_planned_slide_pairs(self):
        deck = {
            "slides": [{
                "title": "Vietnam e-commerce growth",
                "layout": "text_chart",
                "bullets": ["2018: 8", "2019: 11", "2020: 14"],
            }],
        }
        unrelated_raw = (
            "Regional classroom attendance chart\n"
            "North: 40\nSouth: 60\n"
        )

        specs = await build_chart_specs_for_slides(
            ChartFallbackExtractor(),
            deck,
            raw_content=unrelated_raw,
            visual_plan={0: "chart"},
        )

        self.assertIn(0, specs)
        self.assertEqual(specs[0]["labels"], ["2018", "2019", "2020"])

    def test_fractional_percent_chart_matches_source_percent_text(self):
        spec = normalize_chart_spec({
            "title": "Baseline performance",
            "chart_type": "column",
            "labels": ["Accuracy", "Macro-F1"],
            "values": [0.9576, 0.9452],
            "unit": "percent",
            "is_percent": True,
        })

        self.assertIsNotNone(spec)
        self.assertTrue(
            _chart_spec_has_text_evidence(
                spec,
                "Accuracy reached 95.76% and Macro-F1 reached 94.52%.",
            )
        )

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
