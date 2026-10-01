"""Explicit request context shared by slide-generation stages."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional


class GenerationMode(str, Enum):
    AUTO = "auto"
    PROMPT = "prompt"
    DOCUMENT = "document"
    EXPLICIT_SLIDES = "explicit_slides"
    REVISION = "revision"


@dataclass(frozen=True)
class GenerationContext:
    task_id: str = ""
    mode: GenerationMode = GenerationMode.AUTO
    source_text: str = field(default="", repr=False)
    focused_source_text: str = field(default="", repr=False)
    user_instruction: str = field(default="", repr=False)
    doc_title_hint: str = ""
    target_slides: int = 10
    force_exact_slide_count: bool = False
    output_language: str = "auto"
    presentation_mode: str = "presentation"
    mode_decision: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}), repr=False
    )

    def evolve(self, **changes: Any) -> "GenerationContext":
        if "mode_decision" in changes:
            changes["mode_decision"] = MappingProxyType(dict(changes["mode_decision"] or {}))
        return replace(self, **changes)


def bind_legacy_extractor_state(extractor: Any, context: GenerationContext) -> None:
    """Compatibility bridge while legacy mixins migrate to explicit context."""
    extractor._generation_context = context
    extractor._telemetry_task_id = context.task_id or getattr(extractor, "_telemetry_task_id", "")
    extractor._user_instruction = context.user_instruction
    extractor._doc_title_hint = context.doc_title_hint
    extractor._source_content = context.source_text
    extractor._focused_source_content = context.focused_source_text or context.source_text
    extractor._is_document_mode = context.mode == GenerationMode.DOCUMENT
    extractor._slide_lang_hint = context.output_language
    extractor._presentation_mode = context.presentation_mode
    extractor._lecture_mode = context.presentation_mode == "lecture"
    extractor._mode_decision = dict(context.mode_decision)


def extractor_context(extractor: Any) -> Optional[GenerationContext]:
    value = getattr(extractor, "_generation_context", None)
    return value if isinstance(value, GenerationContext) else None

