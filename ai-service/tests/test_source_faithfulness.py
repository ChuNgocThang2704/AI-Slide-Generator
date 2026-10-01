import asyncio
import json

import pytest

from services.source_faithfulness import enforce_source_faithfulness


class FakeExtractor:
    _is_document_mode = True
    _user_instruction = "Make slides from the source"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    async def _llm_completion_plain_text(self, *_args, **_kwargs):
        self.calls += 1
        return json.dumps(next(self.responses))


def deck():
    return {"slides": [
        {"title": "Revenue", "layout": "intro", "bullets": ["Revenue 2024"]},
        {"title": "Quarter 1", "layout": "text_only", "bullets": ["Marketing drove 2.1 billion"], "notes": "Campaign success"},
        {"title": "Summary", "layout": "thankyou", "bullets": ["Revenue grew"]},
    ]}


def test_repair_and_reaudit_document_claims():
    extractor = FakeExtractor([
        {"unsupported": [{"index": 1, "reason": "marketing not in source"}]},
        {"slides": [{"index": 1, "title": "Quarter 1", "bullets": ["Revenue: 2.1 billion"], "notes": "Source reports 2.1 billion."}]},
        {"unsupported": []},
    ])
    result = asyncio.run(enforce_source_faithfulness(extractor, deck(), "Quarter 1 revenue was 2.1 billion."))
    assert result["slides"][1]["bullets"] == ["Revenue: 2.1 billion"]
    assert extractor.calls == 3


def test_unresolved_document_claims_fail_closed():
    # A slide the literal fallback already fixed is exempt from later audit
    # rounds (a verbatim quote can't newly become "unsupported"), so a
    # genuinely unresolved deck needs a *new* flagged index each round —
    # mirroring a live case where the strict auditor kept finding fresh
    # phrasing complaints on different slides each pass.
    big_deck = {"slides": [
        {"title": f"Slide {i}", "layout": "text_only", "bullets": [f"Claim {i}"]}
        for i in range(5)
    ]}
    extractor = FakeExtractor([
        {"unsupported": [{"index": 1, "reason": "not supported"}]},
        {"slides": [{"index": 1, "title": "Slide 1", "bullets": ["Marketing drove growth"], "notes": ""}]},
        {"unsupported": [{"index": 1, "reason": "still unsupported"}]},
        {"slides": [{"index": 1, "title": "Slide 1", "bullets": ["Campaigns drove growth"], "notes": ""}]},
        # Fallback loop: a different index is flagged each round, so the
        # verbatim-safe exemption never lets the loop converge.
        {"unsupported": [{"index": 1, "reason": "still unsupported"}]},
        {"unsupported": [{"index": 2, "reason": "still unsupported"}]},
        {"unsupported": [{"index": 3, "reason": "still unsupported"}]},
        # Final confirmation audit: index 4 was never fixed.
        {"unsupported": [{"index": 4, "reason": "still unsupported"}]},
    ])
    with pytest.raises(RuntimeError, match="still found unsupported"):
        asyncio.run(enforce_source_faithfulness(extractor, big_deck, "Quarter 1 revenue was 2.1 billion."))


def test_literal_fallback_resolves_a_slide_the_llm_repair_could_not():
    extractor = FakeExtractor([
        {"unsupported": [{"index": 1, "reason": "not supported"}]},
        {"slides": [{"index": 1, "title": "Quarter 1", "bullets": ["Marketing drove growth"], "notes": ""}]},
        {"unsupported": [{"index": 1, "reason": "still unsupported"}]},
        {"slides": [{"index": 1, "title": "Quarter 1", "bullets": ["Campaigns drove growth"], "notes": ""}]},
        {"unsupported": [{"index": 1, "reason": "still unsupported"}]},
        # After the deterministic literal-sentence fallback, the re-audit passes.
        {"unsupported": []},
    ])
    result = asyncio.run(enforce_source_faithfulness(extractor, deck(), "Quarter 1 revenue was 2.1 billion."))
    assert result["slides"][1]["bullets"] == ["Quarter 1 revenue was 2.1 billion."]


def test_second_bounded_repair_can_resolve_remaining_claim():
    extractor = FakeExtractor([
        {"unsupported": [{"index": 1, "reason": "marketing not in source"}]},
        {"slides": [{"index": 1, "title": "Quarter 1", "bullets": ["Campaigns raised revenue"], "notes": ""}]},
        {"unsupported": [{"index": 1, "reason": "campaigns not in source"}]},
        {"slides": [{"index": 1, "title": "Quarter 1", "bullets": ["Revenue was 2.1 billion"], "notes": ""}]},
        {"unsupported": []},
    ])
    result = asyncio.run(enforce_source_faithfulness(extractor, deck(), "Quarter 1 revenue was 2.1 billion."))
    assert result["slides"][1]["bullets"] == ["Revenue was 2.1 billion"]
    assert extractor.calls == 5


def test_missing_batch_slide_is_repaired_individually():
    extractor = FakeExtractor([
        {"unsupported": [{"index": 1, "reason": "marketing not in source"}]},
        {"slides": []},
        {"index": 1, "title": "Quarter 1", "bullets": ["Revenue was 2.1 billion"], "notes": ""},
        {"unsupported": []},
    ])
    result = asyncio.run(enforce_source_faithfulness(extractor, deck(), "Quarter 1 revenue was 2.1 billion."))
    assert result["slides"][1]["bullets"] == ["Revenue was 2.1 billion"]
    assert extractor.calls == 4


def test_single_slide_repair_accepts_one_item_wrapper_without_integer_index():
    extractor = FakeExtractor([
        {"unsupported": [{"index": 1, "reason": "marketing not in source"}]},
        {"slides": []},
        {"slides": [{"index": "1", "title": "Quarter 1", "bullets": ["Revenue was 2.1 billion"], "notes": ""}]},
        {"unsupported": []},
    ])
    result = asyncio.run(enforce_source_faithfulness(extractor, deck(), "Quarter 1 revenue was 2.1 billion."))
    assert result["slides"][1]["bullets"] == ["Revenue was 2.1 billion"]


def test_prompt_mode_does_not_call_auditor():
    extractor = FakeExtractor([])
    extractor._is_document_mode = False
    result = asyncio.run(enforce_source_faithfulness(extractor, deck(), "Topic"))
    assert result == deck()
    assert extractor.calls == 0
