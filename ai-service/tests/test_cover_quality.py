from services.cover_quality import normalize_cover


def test_verbose_definition_cover_becomes_scope_preview_without_losing_detail():
    deck = {"slides": [
        {"title": "Trí tuệ nhân tạo", "layout": "intro", "bullets": [
            "Định nghĩa AI: Hệ thống mô phỏng trí tuệ con người.",
            "Tầm quan trọng: AI thay đổi cách học tập.",
        ], "notes": "Chào các bạn."},
        {"title": "Mục tiêu học tập", "layout": "text_only"},
        {"title": "Lịch sử AI", "layout": "text_only"},
        {"title": "Ứng dụng AI", "layout": "text_only"},
        {"title": "Đạo đức AI", "layout": "text_only"},
        {"title": "Kết luận", "layout": "thankyou"},
    ]}

    normalize_cover(deck)

    assert deck["slides"][0]["bullets"] == ["Từ Lịch sử AI đến Đạo đức AI"]
    assert "Định nghĩa AI:" in deck["slides"][0]["notes"]
    assert "Tầm quan trọng:" in deck["slides"][0]["notes"]


def test_short_cover_is_preserved():
    deck = {"slides": [
        {"title": "AI", "layout": "intro", "bullets": ["Từ lịch sử đến ứng dụng trong đời sống"]},
        {"title": "Body", "layout": "text_only"},
    ]}
    assert normalize_cover(deck)["slides"][0]["bullets"] == ["Từ lịch sử đến ứng dụng trong đời sống"]


def test_no_body_topic_does_not_invent_subtitle():
    deck = {"slides": [
        {"title": "AI", "layout": "intro", "bullets": ["Definition: some fact"]},
        {"title": "Summary", "layout": "thankyou"},
    ]}
    assert normalize_cover(deck)["slides"][0]["bullets"] == ["Definition: some fact"]
