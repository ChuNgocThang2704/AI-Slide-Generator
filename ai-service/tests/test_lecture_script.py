import asyncio
import io
import json
import unittest

from services.lecture_script import (
    NOTE_PRESENTER, SCENE_INTRO, SCENE_OUTRO, assemble_rows, estimated_minutes, has_cover, tidy_script, write_script,
)
from services.lecture_script_xlsx import build_workbook, sheet_name

LONG = "Mời các em quan sát nội dung này và ghi nhớ ý chính của phần học hôm nay nhé."


def _slides(count=4, cover=True):
    slides = [{"number": 1, "title": "Chương 2", "text": "Chương 2\nCác dạng tấn công" if cover else "từ " * 80, "notes": "", "has_figure": False}]
    for number in range(2, count + 1):
        slides.append({
            "number": number, "title": f"Mục {number}", "text": f"Nội dung tiếng Việt của mục {number} về mối đe dọa và lỗ hổng",
            "notes": "", "has_figure": number == 3,
        })
    return slides


class _Extractor:
    """Answers the slide batches and the intro/outro call; `skip` leaves those slides out."""

    def __init__(self, skip=()):
        self.skip = set(skip)
        self.calls = []

    async def _llm_completion_plain_text(self, messages, **kwargs):
        self.calls.append(kwargs.get("call_purpose"))
        payload = json.loads(messages[1]["content"])
        if kwargs.get("call_purpose") == "lecture_script_frame":
            return json.dumps({"title": "Mối đe dọa và Lỗ hổng", "intro": "Chào các em.\n\n" + LONG, "outro": LONG})
        return json.dumps({"items": [
            {"slide": slide["slide"], "script": f"**Slide {slide['slide']}** mới.\n- {LONG}"}
            for slide in payload["slides"] if slide["slide"] not in self.skip
        ]})


class LectureScriptTests(unittest.TestCase):
    def test_spoken_text_loses_markdown_bullets_and_stage_directions(self):
        self.assertEqual(tidy_script("**Chào** các em.\n- ý một\n\n\n[cười] Hai."), "Chào các em.\n\ný một\n\nHai.")

    def test_title_slide_becomes_the_opening_scene(self):
        slides = _slides()
        self.assertTrue(has_cover(slides))
        rows = assemble_rows(slides, {2: "a", 3: "b", 4: "c"}, {"intro": "i", "outro": "o"})
        self.assertEqual([row["scene"] for row in rows], [SCENE_INTRO, "Slide 2", "Slide 3", "Slide 4", SCENE_OUTRO])
        self.assertEqual([row["note"] for row in rows], [NOTE_PRESENTER, "", "Hình 3", "", NOTE_PRESENTER])

    def test_a_first_slide_with_real_content_keeps_its_own_scene(self):
        slides = _slides(cover=False)
        self.assertFalse(has_cover(slides))
        rows = assemble_rows(slides, {}, {})
        self.assertEqual([row["scene"] for row in rows][:2], [SCENE_INTRO, "Slide 1"])

    def test_duration_follows_the_speaking_pace(self):
        self.assertEqual(estimated_minutes([{"script": "từ " * 1120}]), 8)
        self.assertEqual(estimated_minutes([{"script": ""}]), 0)

    def test_script_is_written_for_every_slide(self):
        script = asyncio.run(write_script(_Extractor(), _slides(8), filename="bai.pptx"))
        self.assertEqual(script["title"], "Mối đe dọa và Lỗ hổng")
        self.assertEqual(script["language"], "vi")
        self.assertEqual(len(script["rows"]), 9)
        self.assertEqual(script["missing"], [])
        self.assertTrue(script["rows"][1]["script"].startswith("Slide 2 mới."))
        self.assertNotIn("**", script["rows"][1]["script"])

    def test_a_slide_the_model_skips_is_reported_and_left_for_the_user(self):
        script = asyncio.run(write_script(_Extractor(skip={3}), _slides(5)))
        self.assertEqual(script["missing"], ["Slide 3"])
        self.assertEqual(script["rows"][2]["script"], "")

    def test_rewriting_keeps_the_old_text_of_a_slide_the_model_skips(self):
        previous = [
            {"scene": SCENE_INTRO, "slide": 1, "script": "Lời cũ mở đầu"},
            {"scene": "Slide 2", "slide": 2, "script": "Lời cũ slide hai"},
            {"scene": "Slide 3", "slide": 3, "script": "Lời cũ slide ba"},
            {"scene": SCENE_OUTRO, "slide": None, "script": "Lời cũ kết"},
        ]
        script = asyncio.run(write_script(_Extractor(skip={3}), _slides(3), prompt="ngắn hơn", previous_rows=previous))
        by_scene = {row["scene"]: row["script"] for row in script["rows"]}
        self.assertTrue(by_scene["Slide 2"].startswith("Slide 2 mới."))
        self.assertEqual(by_scene["Slide 3"], "Lời cũ slide ba")
        self.assertEqual(script["missing"], [])


class LectureScriptWorkbookTests(unittest.TestCase):
    def test_workbook_has_the_layout_of_a_production_script(self):
        try:
            from openpyxl import load_workbook
        except ImportError:
            self.skipTest("openpyxl is not installed")
        data = build_workbook({
            "title": "Video 4: Mối đe dọa / Lỗ hổng", "duration_minutes": 8,
            "rows": [
                {"scene": SCENE_INTRO, "script": "Chào các em.\n\nHôm nay…", "note": NOTE_PRESENTER},
                {"scene": "Slide 2", "script": "Nội dung.", "note": ""},
            ],
        })
        sheet = load_workbook(io.BytesIO(data)).active
        self.assertEqual(sheet["A1"].value, "Video 4: Mối đe dọa / Lỗ hổng")
        self.assertEqual(sheet["A2"].value, "Thời lượng dự kiến: 8 phút")
        self.assertEqual([sheet[f"{column}4"].value for column in "ABC"], ["PHÂN CẢNH", "LỜI THOẠI", "LƯU Ý DỰNG"])
        self.assertEqual(sheet["A5"].value, SCENE_INTRO)
        self.assertEqual(sheet["B5"].value, "Chào các em.\n\nHôm nay…")
        self.assertEqual(sheet["C5"].value, NOTE_PRESENTER)
        self.assertIsNone(sheet["C6"].value)
        self.assertEqual(sheet["B5"].font.name, "Times New Roman")
        self.assertTrue(sheet["B5"].alignment.wrap_text)
        self.assertEqual({str(cells) for cells in sheet.merged_cells.ranges}, {"A1:C1", "A2:C2"})

    def test_sheet_name_is_legal_in_excel(self):
        self.assertEqual(sheet_name("Video 4: A/B [x]"), "Video 4  A B  x")
        self.assertLessEqual(len(sheet_name("a" * 80)), 31)


if __name__ == "__main__":
    unittest.main()
