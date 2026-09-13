import asyncio
import json

from services.slide_text_quality import _review_speaker_notes, _speaker_note_issues


class _NotesExtractor:
    def __init__(self):
        self.calls = 0

    async def _llm_completion_plain_text(self, messages, **_kwargs):
        self.calls += 1
        payload = json.loads(messages[-1]["content"])
        narration = (
            "Chúng ta cùng phân tích nội dung trọng tâm và liên kết từng ý với mục tiêu của bài học. "
            "Khái niệm đầu tiên tạo nền tảng để người học hiểu cách áp dụng kiến thức trong tình huống thực tế. "
            "Ý tiếp theo làm rõ nguyên nhân, tác động và mối quan hệ giữa các thành phần đang được trình bày. "
            "Qua đó, các bạn có thể nhận biết điểm quan trọng, tránh nhầm lẫn và lựa chọn cách xử lý phù hợp. "
            "Phần cuối giúp kết nối kiến thức vừa học với nội dung kế tiếp một cách tự nhiên và dễ ghi nhớ."
        )
        return json.dumps(
            {
                "slides": [
                    {"index": item["index"], "notes": narration}
                    for item in payload["slides"]
                ]
            },
            ensure_ascii=False,
        )


def test_short_instructional_note_is_flagged():
    slide = {
        "title": "Cấu trúc bài thi",
        "bullets": ["Phần một", "Phần hai", "Phần ba"],
        "notes": "Giới thiệu cấu trúc bài thi và ba phần chính.",
    }

    issues = _speaker_note_issues(slide)

    assert "speaker_notes_too_short" in issues
    assert "speaker_notes_instruction_opener" in issues


def test_unresolved_speaker_placeholder_is_flagged():
    slide = {
        "title": "Mở đầu",
        "bullets": ["Giới thiệu nội dung", "Mục tiêu bài học"],
        "notes": (
            "Xin chào các bạn. Tôi là giảng viên [Tên Giảng viên/Tổ chức], rất vui được đồng hành "
            "cùng các bạn trong buổi học hôm nay. " * 5
        ),
    }

    assert "speaker_notes_unresolved_placeholder" in _speaker_note_issues(slide)


def test_all_weak_notes_are_reviewed_in_batches():
    extractor = _NotesExtractor()
    deck = {
        "slides": [
            {
                "title": f"Chủ đề {index}",
                "bullets": ["Khái niệm nền tảng", "Ứng dụng thực tế"],
                "notes": "Trình bày nội dung chính.",
            }
            for index in range(13)
        ]
    }

    improved, changed = asyncio.run(
        _review_speaker_notes(extractor, deck, source_language="vi")
    )

    assert extractor.calls == 4
    assert changed == list(range(13))
    assert all(len(slide["notes"].split()) >= 85 for slide in improved["slides"])
