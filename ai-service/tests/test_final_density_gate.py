import asyncio

import pytest

from services.content.slide_pipeline import SlidePipelineMixin


class DensityPipeline(SlidePipelineMixin):
    _lecture_mode = False
    _slide_lang_hint = "vi"

    def _llm_system_prefix(self):
        return ""

    def _user_lang_reminder(self):
        return ""

    def _strip_continued_suffix(self, title):
        return title

    def _repair_incomplete_tail(self, bullet):
        return bullet

    def _bullet_needs_final_fix(self, bullet):
        return False

    async def _request_json_dict(self, messages, **kwargs):
        if kwargs.get("structured_output") == "slide_density":
            return {
                "bullets": [
                    "Khái niệm cốt lõi được trình bày ngắn gọn và đúng phạm vi.",
                    "Các thành phần liên quan được nhóm lại theo ý nghĩa chính.",
                    "Chi tiết hỗ trợ được chuyển sang phần ghi chú thuyết trình.",
                ],
                "notes": "Giải thích thêm các chi tiết đã được rút khỏi phần nội dung hiển thị.",
            }
        return {"bullets": ["Nội dung bổ sung đúng chủ đề.", "Ý nghĩa của nội dung.", "Ví dụ minh họa phù hợp."]}


def test_density_metrics_detect_overloaded_ordinary_slide():
    slide = {
        "layout": "text_only",
        "bullets": [f"Ý {index}: " + "nội dung giải thích " * 8 for index in range(1, 8)],
    }

    metrics = DensityPipeline._slide_density_metrics(slide)

    assert metrics["overloaded"] is True
    assert metrics["exempt"] is False


@pytest.mark.parametrize(
    "slide",
    [
        {"layout": "text_table", "table": {"headers": ["A"]}, "bullets": ["dài " * 300]},
        {"layout": "text_chart", "chart": {"type": "bar"}, "bullets": ["dài " * 300]},
        {"layout": "code", "bullets": ["def example(value):", "    return value"]},
    ],
)
def test_density_metrics_exempt_structured_and_code_slides(slide):
    metrics = DensityPipeline._slide_density_metrics(slide)

    assert metrics["overloaded"] is False
    assert metrics["exempt"] is True


def test_final_density_gate_reduces_dense_slide_without_borrowing_neighbour_content():
    pipeline = DensityPipeline()
    deck = {
        "title": "Bài kiểm thử",
        "slides": [
            {
                "title": "Slide mỏng",
                "layout": "text_only",
                "bullets": ["Chỉ có một ý riêng của slide này."],
            },
            {
                "title": "Slide dày",
                "layout": "text_only",
                "bullets": [f"Nội dung dày số {index}: " + "giải thích chi tiết " * 8 for index in range(1, 8)],
                "notes": "Ghi chú ban đầu.",
            },
        ],
    }

    result = asyncio.run(pipeline._run_final_density_gate(deck))

    assert all("Nội dung dày" not in bullet for bullet in result["slides"][0]["bullets"])
    assert len(result["slides"][1]["bullets"]) == 3
    assert result["slides"][1]["notes"].startswith("Giải thích thêm")
