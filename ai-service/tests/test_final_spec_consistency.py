from routes.api import _remove_absent_chart_references
from services.deck_contract import _boundary_visual_issues, _flatten_boundary_visuals


def test_removes_vietnamese_chart_promise_when_chart_is_absent():
    bullets = [
        "Mô hình AI phân tích dữ liệu thời tiết và đất đai.",
        "Biểu đồ minh họa so sánh dữ liệu thực tế và dự báo AI.",
    ]

    assert _remove_absent_chart_references(bullets, has_chart=False) == [bullets[0]]


def test_preserves_chart_promise_when_chart_exists():
    bullets = ["The chart shows quarterly adoption rates."]

    assert _remove_absent_chart_references(bullets, has_chart=True) == bullets


def test_closing_table_is_flattened_to_visible_questions_and_notes():
    deck = {"slides": [
        {"title": "Intro", "layout": "intro", "bullets": []},
        {
            "title": "Summary and check",
            "layout": "thankyou",
            "bullets": ["Summary"],
            "table": {
                "headers": ["Question", "Hint"],
                "rows": [["What is a function?", "Think about reuse."]],
            },
        },
    ]}
    assert _boundary_visual_issues(deck)[0]["index"] == 1
    cleaned = _flatten_boundary_visuals(deck)
    closing = cleaned["slides"][1]
    assert "table" not in closing
    assert closing["bullets"] == ["Summary", "What is a function?"]
    assert "Hint: Think about reuse." in closing["notes"]
