import asyncio

from services.presentation_mode import classify_presentation_mode, lock_presentation_mode


class FakeExtractor:
    def __init__(self, responses=None, *, vllm=True, gemini=True):
        self.vllm_available = vllm
        self.gemini_available = gemini
        self.responses = responses or {}
        self.calls = []

    async def _llm_completion_plain_text(self, _messages, **kwargs):
        provider = kwargs.get("provider")
        self.calls.append(provider)
        return self.responses[provider]


def test_qwen_high_confidence_is_primary():
    extractor = FakeExtractor({
        "vllm_only": '{"mode":"lecture","confidence":0.91,"reason":"Teaching sequence requested."}',
        "gemini": '{"mode":"presentation","confidence":0.99,"reason":"unused"}',
    })
    decision = asyncio.run(classify_presentation_mode(extractor, "Chapter 3 Functions", "Create slides"))
    assert decision["mode"] == "lecture"
    assert decision["provider"] == "qwen"
    assert extractor.calls == ["vllm_only"]


def test_low_confidence_qwen_escalates_to_gemini():
    extractor = FakeExtractor({
        "vllm_only": '{"mode":"lecture","confidence":0.51,"reason":"Ambiguous."}',
        "gemini": '{"mode":"presentation","confidence":0.88,"reason":"Research briefing."}',
    })
    decision = asyncio.run(classify_presentation_mode(extractor, "Research paper", "Summarize findings"))
    assert decision["mode"] == "presentation"
    assert decision["provider"] == "gemini"
    assert decision["qwen_confidence"] == 0.51


def test_rule_fallback_when_no_provider():
    extractor = FakeExtractor(vllm=False, gemini=False)
    decision = asyncio.run(classify_presentation_mode(
        extractor,
        "Chapter 3 Functions. Learning objectives. Exercise 3.1.",
        "Create slides",
    ))
    assert decision["mode"] == "lecture"
    assert decision["provider"] == "rule_fallback"


def test_lock_mode_overrides_model_deck_mode():
    deck = {"presentation_mode": "presentation", "slides": [{"title": "Intro"}]}
    result = lock_presentation_mode(deck, {
        "mode": "lecture", "confidence": 0.9, "provider": "qwen", "reason": "Teaching intent"
    })
    assert result["presentation_mode"] == "lecture"
    assert result["slides"][0]["presentation_mode"] == "lecture"
    assert result["mode_decision"]["provider"] == "qwen"
