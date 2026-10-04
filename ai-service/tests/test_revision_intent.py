import asyncio
import json
import unittest

from services.revision_intent import added_indices, parse_intent
from services.visual_translate import translate_visual_text


class RevisionIntentTests(unittest.TestCase):
    def test_valid_fields_are_read_and_slide_numbers_become_zero_based(self):
        intent = parse_intent({
            "add_slides": {"count": 2, "after_slide": 3},
            "delete_slides": [2, 99, "x"],
            "titles": [{"slide": 4, "title": ' "Vận động đúng cách" '}, {"slide": 50, "title": "bỏ"}],
            "visuals": [{"slide": 5, "visual": "chart", "chart_type": "bar", "keep_text": True},
                        {"slide": 1, "visual": "video"}],
            "language": "EN", "bullet_count": 3,
        }, slide_count=6)
        self.assertEqual((intent.add_count, intent.add_after), (2, 3))
        self.assertEqual(intent.delete, [1])
        self.assertEqual(intent.titles, {3: "Vận động đúng cách"})
        self.assertEqual(intent.visuals, {4: "chart"})
        self.assertEqual(intent.chart_types, {4: "bar"})
        self.assertEqual(intent.keep_text, {4: True})
        self.assertEqual((intent.language, intent.bullet_count), ("en", 3))

    def test_garbage_yields_an_empty_intent(self):
        for raw in (None, "x", {"add_slides": {"count": 500}}, {"delete_slides": [1, 2, 3]}, {"language": "fr"}):
            intent = parse_intent(raw, slide_count=3)
            self.assertEqual((intent.add_count, intent.delete, intent.language), (0, [], None))

    def test_new_slides_sit_after_the_named_slide(self):
        intent = parse_intent({"add_slides": {"count": 2, "after_slide": 3}}, 6)
        self.assertEqual(added_indices(intent, 6, 8), [3, 4])
        self.assertEqual(added_indices(parse_intent({"add_slides": {"count": 1, "after_slide": 0}}, 6), 6, 7), [0])
        self.assertIsNone(added_indices(parse_intent({"add_slides": {"count": 1}}, 6), 6, 7))


class VisualTranslateTests(unittest.TestCase):
    def test_table_and_chart_strings_are_translated_and_numbers_kept(self):
        class Extractor:
            async def _llm_completion_plain_text(self, messages, **kwargs):
                items = json.loads(messages[1]["content"])["items"]
                table = {"Tiêu chí": "Criterion", "Sách giấy": "Print book", "Giá 120 nghìn": "Price 999 thousand", "Số sách": "Books"}
                return json.dumps({"items": [table.get(i, i) for i in items]})

        deck = {"slides": [
            {"table": {"headers": ["Tiêu chí", "Sách giấy"], "rows": [["Giá 120 nghìn", "12%"]]}},
            {"chart": {"type": "bar", "title": "Số sách", "labels": ["2021", "2022"], "series": [{"name": "Số sách", "values": [5, 8]}]}},
        ]}
        changed = asyncio.run(translate_visual_text(Extractor(), deck, "en"))
        self.assertEqual(deck["slides"][0]["table"]["headers"], ["Criterion", "Print book"])
        # A translation that changes a number is refused; numeric cells and the chart type are untouched.
        self.assertEqual(deck["slides"][0]["table"]["rows"], [["Giá 120 nghìn", "12%"]])
        self.assertEqual(deck["slides"][1]["chart"]["title"], "Books")
        self.assertEqual(deck["slides"][1]["chart"]["type"], "bar")
        self.assertEqual(deck["slides"][1]["chart"]["series"][0]["values"], [5, 8])
        self.assertEqual(changed, 4)


class SplitColumnLimitTests(unittest.TestCase):
    def test_extra_and_adjacent_two_column_slides_go_back_to_plain_bullets(self):
        from services.slide_quality import limit_split_columns
        col = lambda: {"layout": "split_columns", "bullets": ["Nên - a: x", "Nên - b: y", "Tránh - c: z"]}
        slides = [{"layout": "intro", "bullets": ["s"]}, col(), col(), col(), {"layout": "text_only", "bullets": ["p"]}, col(), {"layout": "thankyou", "bullets": ["k"]}]
        changed = limit_split_columns(slides)
        layouts = [s["layout"] for s in slides]
        self.assertEqual(layouts, ["intro", "split_columns", "text_only", "split_columns", "text_only", "text_only", "thankyou"])
        self.assertEqual(changed, 2)
        self.assertEqual(slides[2]["bullets"], ["a: x", "b: y", "c: z"])
        self.assertEqual(slides[1]["bullets"][0], "Nên - a: x")
