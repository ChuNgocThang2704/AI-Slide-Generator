import asyncio

from services.content.extractor import ContentExtractor


def test_gemini_only_document_uses_full_generation_pipeline(monkeypatch):
    extractor = ContentExtractor.__new__(ContentExtractor)
    extractor.model_name = "Qwen3-VL-8B"
    extractor.vllm_available = False
    extractor.gemini_available = True
    extractor._slide_lang_hint = "auto"
    extractor._lecture_mode = False
    extractor._source_content = ""
    extractor._focused_source_content = ""
    extractor._extract_progress = None

    monkeypatch.setattr(extractor, "_is_prompt_input", lambda _content: False)
    monkeypatch.setattr(extractor, "_strip_meta_instruction_lines", lambda content: content)
    monkeypatch.setattr(extractor, "_resolve_output_language_hint", lambda *_args: "vi")

    calls = []

    async def run_pipeline(merged_summary, target_slides):
        calls.append((merged_summary, target_slides))
        return {
            "title": "Bao cao nghien cuu",
            "slides": [
                {
                    "title": "Ket qua chinh",
                    "bullets": ["Do chinh xac dat 95,76% tren tap kiem thu."],
                }
            ],
        }

    async def keep_slide_count(structured, **_kwargs):
        return structured

    monkeypatch.setattr(extractor, "_expand_group_generate_refine_pipeline", run_pipeline)
    monkeypatch.setattr(extractor, "_ensure_auto_min_slide_count", keep_slide_count)
    monkeypatch.setattr(
        extractor,
        "_resolve_deck_title",
        lambda candidate, **_kwargs: candidate or "Bao cao nghien cuu",
    )

    result = asyncio.run(
        extractor.extract_and_structure(
            "Bao cao nghien cuu gom boi canh, phuong phap, du lieu va ket qua. " * 20,
            target_slides_override=8,
            user_instruction="Tao bao cao ket qua nghien cuu bang tieng Viet.",
        )
    )

    assert len(calls) == 1
    assert calls[0][1] == 8
    assert result["slides"][0]["title"] == "Ket qua chinh"
