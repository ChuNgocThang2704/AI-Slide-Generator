import asyncio
import json
import unittest

from services.slide_density import condense_long_bullets, long_bullets

LONG = "Tư duy liên ngành: Kết hợp tri thức từ lịch sử, kinh tế, tâm lý học và văn học để hình thành góc nhìn đa chiều và toàn diện cho sinh viên năm 2025 trong mọi hoàn cảnh học tập"


class Extractor:
    def __init__(self, answers):
        self.answers = answers
        self.calls = 0

    async def _llm_completion_plain_text(self, messages, **kwargs):
        self.calls += 1
        items = json.loads(messages[1]["content"])["items"]
        return json.dumps({"items": [{"id": i["id"], "text": self.answers[i["id"]]} for i in items]})


def deck(bullets, layout="text_only"):
    return {"slides": [{"title": "Bìa", "bullets": [LONG]}, {"title": "A", "layout": layout, "bullets": list(bullets), "notes": "n"}]}


class SlideDensityTests(unittest.TestCase):
    def test_only_long_body_bullets_are_flagged_and_the_cover_is_left(self):
        found = long_bullets(deck([LONG, "Một dòng ngắn gọn."]))
        self.assertEqual([(f["slide"], f["bullet"]) for f in found], [(1, 0)])

    def test_a_valid_rewrite_replaces_the_bullet_and_keeps_the_label(self):
        d = deck([LONG])
        ex = Extractor(["Tư duy liên ngành: Kết hợp nhiều lĩnh vực để có góc nhìn đa chiều năm 2025"])
        out = asyncio.run(condense_long_bullets(ex, d))
        self.assertTrue(out["slides"][1]["bullets"][0].startswith("Tư duy liên ngành:"))
        self.assertLess(len(out["slides"][1]["bullets"][0].split()), 20)

    def test_a_rewrite_that_adds_a_number_or_drops_the_label_is_refused(self):
        for bad in ["Tư duy liên ngành: tăng 68% hiệu quả học tập", "Kết hợp nhiều lĩnh vực để có góc nhìn đa chiều"]:
            d = deck([LONG])
            out = asyncio.run(condense_long_bullets(Extractor([bad]), d))
            self.assertEqual(out["slides"][1]["bullets"][0], LONG)

    def test_a_column_heading_stays_in_front(self):
        d = deck(["Kênh bán - " + LONG], layout="split_columns")
        ex = Extractor(["Tư duy liên ngành: Kết hợp nhiều lĩnh vực để có góc nhìn đa chiều năm 2025"])
        out = asyncio.run(condense_long_bullets(ex, d))
        self.assertTrue(out["slides"][1]["bullets"][0].startswith("Kênh bán - Tư duy liên ngành:"))

    def test_no_call_when_nothing_is_long(self):
        ex = Extractor([])
        asyncio.run(condense_long_bullets(ex, deck(["Ngắn gọn thôi."])))
        self.assertEqual(ex.calls, 0)


class LabelledSeriesTests(unittest.TestCase):
    def test_quarters_in_parentheses_and_years_after_a_colon_are_series(self):
        from services.slide_charts import labelled_value_series
        quarters = ["Quý 1 (12 tỷ VNĐ): Khởi động ấn tượng", "Quý 2 (15 tỷ VNĐ): Bứt phá", "Quý 3 (14 tỷ VNĐ): Hạ nhiệt", "Quý 4 (21 tỷ VNĐ): Bùng nổ"]
        self.assertEqual([v for _, v, _ in labelled_value_series(quarters)], [12.0, 15.0, 14.0, 21.0])
        years = ["2021: 5 cuốn", "2022: 8 cuốn", "2023: 12 cuốn"]
        self.assertEqual(len(labelled_value_series(years)), 3)

    def test_prose_bullets_and_mixed_units_are_not(self):
        from services.slide_charts import labelled_value_series
        self.assertIsNone(labelled_value_series(["Y tế: hỗ trợ chẩn đoán", "Giáo dục: cá nhân hóa", "Tài chính: phát hiện gian lận"]))
        self.assertIsNone(labelled_value_series(["A (12 tỷ): x", "B (15 %): y", "C (3 người): z"]))
        self.assertIsNone(labelled_value_series(["A (12 tỷ): x", "B (15 tỷ): y"]))
