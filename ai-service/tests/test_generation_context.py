from dataclasses import FrozenInstanceError

from services.generation_context import (
    GenerationContext,
    GenerationMode,
    bind_legacy_extractor_state,
    extractor_context,
)


class _Extractor:
    _telemetry_task_id = "task-existing"


def test_context_evolution_is_immutable_and_mirrors_legacy_state():
    initial = GenerationContext(
        source_text="source",
        user_instruction="instruction",
        target_slides=8,
    )
    resolved = initial.evolve(
        mode=GenerationMode.DOCUMENT,
        output_language="vi",
        presentation_mode="lecture",
        mode_decision={"mode": "lecture", "confidence": 1.0},
    )
    extractor = _Extractor()
    bind_legacy_extractor_state(extractor, resolved)

    assert initial.mode == GenerationMode.AUTO
    assert extractor_context(extractor) is resolved
    assert extractor._is_document_mode is True
    assert extractor._slide_lang_hint == "vi"
    assert extractor._lecture_mode is True
    assert extractor._user_instruction == "instruction"


def test_context_does_not_expose_source_or_instruction_in_repr():
    context = GenerationContext(source_text="secret source", user_instruction="secret instruction")
    rendered = repr(context)
    assert "secret source" not in rendered
    assert "secret instruction" not in rendered
    try:
        context.mode = GenerationMode.PROMPT
        raise AssertionError("frozen context accepted mutation")
    except FrozenInstanceError:
        pass

