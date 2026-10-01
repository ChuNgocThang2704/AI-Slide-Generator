"""Post-lock design intent; renderer geometry remains deterministic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Tuple


CONTROLLED_LAYOUTS = frozenset({
    "intro", "title_content", "two_columns", "comparison", "text_image",
    "timeline", "text_chart", "text_table", "big_quote", "thankyou",
})

_LEGACY_LAYOUTS = {
    "text_only": "title_content", "normal": "title_content",
    "split_columns": "two_columns", "hero_stat": "title_content",
    "title": "intro", "thank_you": "thankyou", "closing": "thankyou",
}


@dataclass(frozen=True)
class DesignProfile:
    theme: str
    palette: str
    typography: str
    background_style: str
    visual_language: str
    density: str

    def to_dict(self) -> dict[str, str]:
        return {
            "theme": self.theme,
            "palette": self.palette,
            "typography": self.typography,
            "background_style": self.background_style,
            "visual_language": self.visual_language,
            "density": self.density,
        }


@dataclass(frozen=True)
class SlideDesignIntent:
    slide_id: str
    layout: str
    visual_type: str
    visual_weight: str
    variant: str = "default"

    def to_dict(self) -> dict[str, str]:
        return {
            "slide_id": self.slide_id,
            "layout": self.layout,
            "visual_type": self.visual_type,
            "visual_weight": self.visual_weight,
            "variant": self.variant,
        }


@dataclass(frozen=True)
class DesignPlan:
    profile: DesignProfile
    slides: Tuple[SlideDesignIntent, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "slides": [slide.to_dict() for slide in self.slides],
        }


def _controlled_layout(slide: Mapping[str, Any], index: int, count: int) -> str:
    if index == 0:
        return "intro"
    if index == count - 1:
        return "thankyou"
    if isinstance(slide.get("table"), dict):
        return "text_table"
    if isinstance(slide.get("chart"), dict):
        return "text_chart"
    raw = str(slide.get("layout") or "").strip().lower()
    layout = _LEGACY_LAYOUTS.get(raw, raw)
    return layout if layout in CONTROLLED_LAYOUTS and layout not in {"intro", "thankyou"} else "title_content"


def build_design_plan(locked_deck: Mapping[str, Any], *, theme: str = "auto") -> DesignPlan:
    """Read a locked deck and derive safe intent without changing its content."""
    if not locked_deck.get("_structure_locked"):
        raise ValueError("Design planning requires a structure-locked deck")
    slides = locked_deck.get("slides") or []
    if not isinstance(slides, list) or not slides:
        raise ValueError("Design planning requires slides")
    signature = tuple(locked_deck.get("_structure_signature") or ())
    if len(signature) != len(slides):
        raise ValueError("Locked slide signature does not match slide count")
    density = "spacious" if len(slides) <= 6 else "balanced"
    mode = str(locked_deck.get("presentation_mode") or "presentation").lower()
    profile = DesignProfile(
        theme=str(theme or "auto"),
        palette="preset",  # Existing renderer owns exact colors.
        typography="educational" if mode == "lecture" else "professional",
        background_style="preset",
        visual_language="instructional" if mode == "lecture" else "editorial",
        density=density,
    )
    intents = []
    for index, slide in enumerate(slides):
        if not isinstance(slide, dict) or str(slide.get("slide_id") or "") != signature[index]:
            raise ValueError("Slide identity changed after structure lock")
        layout = _controlled_layout(slide, index, len(slides))
        visual_type = (
            "table" if layout == "text_table" else
            "chart" if layout == "text_chart" else
            "image" if slide.get("image") or slide.get("image_url") or layout == "text_image" else
            "none"
        )
        intents.append(SlideDesignIntent(
            slide_id=signature[index],
            layout=layout,
            visual_type=visual_type,
            visual_weight="high" if visual_type in {"chart", "table"} else "medium" if visual_type == "image" else "low",
        ))
    return DesignPlan(profile=profile, slides=tuple(intents))
