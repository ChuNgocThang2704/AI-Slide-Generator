"""Internal quality helpers for slide decks.

These functions improve the AI output before BE/FE receive the same JSON
contract as before. They do not add required fields for clients.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from services.content.json_utils import parse_json_response


_VISUAL_VALUES = {"none", "image", "chart", "table"}
_CHART_HINT_RE = re.compile(
    r"(%|\b(?:chart|graph|bieu\s*do|biểu\s*đồ|kpi|metric|statistics|thống\s*kê|"
    r"doanh\s*thu|revenue|cost|chi\s*phí|profit|lợi\s*nhuận|growth|tăng\s*trưởng|"
    r"survey|score|rate|ratio)\b)",
    re.IGNORECASE,
)
_TABLE_HINT_RE = re.compile(
    r"\b(?:compare|comparison|versus|vs|before|after|pros|cons|criteria|option|"
    r"current|target|solution|problem|feature|benefit|risk|impact|status|"
    r"so\s*sánh|so\s*sanh|tiêu\s*chí|tieu\s*chi|ưu\s*điểm|uu\s*diem|"
    r"nhược\s*điểm|nhuoc\s*diem|phương\s*án|phuong\s*an|"
    r"hiện\s*trạng|hien\s*trang|giải\s*pháp|giai\s*phap)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?\s*(?:%|k|m|tr|triệu|tỷ|ty)?", re.IGNORECASE)


def _slide_text(slide: Dict[str, Any], max_chars: int = 900) -> str:
    title = str(slide.get("title") or "").strip()
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        parts = [bullets]
    else:
        parts = [str(x) for x in bullets if str(x).strip()]
    notes = str(slide.get("notes") or slide.get("script") or "").strip()
    return "\n".join([title] + parts + ([notes] if notes else []))[:max_chars]


def _clean_json_text(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _valid_deck(candidate: Any, expected_slides: int) -> bool:
    if not isinstance(candidate, dict):
        return False
    slides = candidate.get("slides")
    if not isinstance(slides, list) or len(slides) != expected_slides:
        return False
    for slide in slides:
        if not isinstance(slide, dict):
            return False
        title = str(slide.get("title") or "").strip()
        bullets = slide.get("bullets")
        if not title or not isinstance(bullets, list) or not any(str(b).strip() for b in bullets):
            return False
    return True


async def improve_deck_source_grounding(
    content_extractor,
    structured: Dict[str, Any],
    raw_content: str,
    *,
    task_id: str = "",
) -> Dict[str, Any]:
    """Review the final deck against source text without changing API shape."""
    if not isinstance(structured, dict) or structured.get("_explicit_slide_mode"):
        return structured
    slides = structured.get("slides") or []
    if not isinstance(slides, list) or not slides:
        return structured
    source = str(raw_content or "").strip()
    if len(source) < 160:
        return structured
    if not hasattr(content_extractor, "_request_json_dict"):
        return structured

    expected = len(slides)
    deck_excerpt = {
        "title": structured.get("title") or "Presentation",
        "slides": [
            {
                "title": str(s.get("title") or ""),
                "bullets": [str(b) for b in (s.get("bullets") or [])[:5]],
                "notes": str(s.get("notes") or ""),
            }
            for s in slides
            if isinstance(s, dict)
        ],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are a strict source-grounded presentation editor.\n"
                "Revise the slide deck only to improve fidelity to the source and professional slide quality.\n"
                "Rules:\n"
                f"- Keep EXACTLY {expected} slides and keep the same JSON schema.\n"
                "- Remove or rewrite unsupported claims that are not grounded in the source.\n"
                "- Add missing important source details only when they clearly fit an existing slide.\n"
                "- Improve vague bullets by replacing them with concrete terms, numbers, names, or results from the source.\n"
                "- Keep related numeric series together on one suitable slide. For example Q1/Q2/Q3/Q4 values must not be split across unrelated slides.\n"
                "- Keep requested comparison/table content together on the same slide; do not mix one comparison row with chart series data.\n"
                "- Preserve all technical terms, proper nouns, numbers, and user intent.\n"
                "- Do not add chart/table/image fields. Return only title, slides, title/bullets/notes fields.\n"
                "Return ONLY valid JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                "SOURCE EXCERPT:\n"
                f"{source[:9000]}\n\n"
                "CURRENT DECK JSON:\n"
                f"{json.dumps(deck_excerpt, ensure_ascii=False)}"
            ),
        },
    ]
    try:
        reviewed = await content_extractor._request_json_dict(
            messages,
            target_slides=expected,
            fast_mode=False,
            compose_mode=True,
            structured_output="slide_deck",
        )
        if not _valid_deck(reviewed, expected):
            print(f"[slide_quality] source grounding skipped: invalid deck for task {task_id}")
            return structured
        normalized = content_extractor._normalize_structured_content(reviewed)
        from services.slide_text_quality import improve_speaker_notes_quality
        normalized = await improve_speaker_notes_quality(
            content_extractor,
            normalized,
            source_language=(getattr(content_extractor, "_slide_lang_hint", "auto") or "auto"),
        )
        print(f"[slide_quality] source grounding applied for task {task_id}")
        return normalized
    except Exception as e:
        print(f"[slide_quality] source grounding failed for task {task_id}: {e}")
        return structured


def _heuristic_visual(slide: Dict[str, Any], *, want_images: bool) -> str:
    layout = str(slide.get("layout") or "").strip().lower()
    if isinstance(slide.get("table"), dict) or "table" in layout:
        return "table"
    if isinstance(slide.get("chart"), dict) or slide.get("chart_type") or "chart" in layout:
        return "chart"
    text = _slide_text(slide, max_chars=1400)
    numbers = _NUMBER_RE.findall(text)
    if _TABLE_HINT_RE.search(text) and (
        ":" in text or re.search(r"\bvs\.?\b|\bversus\b", text, re.IGNORECASE) or text.count(";") >= 1
    ):
        return "table"
    if len(numbers) >= 2 and _CHART_HINT_RE.search(text):
        return "chart"
    if _TABLE_HINT_RE.search(text) and (text.count(":") >= 2 or len(numbers) >= 1):
        return "table"
    if want_images and layout in {"text_image", "split_columns", "timeline", "big_quote", "hero_stat", "intro"}:
        return "image"
    if want_images:
        return "image"
    return "none"


async def build_visual_plan(
    content_extractor,
    structured: Dict[str, Any],
    raw_content: str,
    *,
    want_images: bool = False,
) -> Dict[int, str]:
    """Decide the preferred visual route per slide: none/image/chart/table."""
    slides = structured.get("slides") or [] if isinstance(structured, dict) else []
    if not isinstance(slides, list) or not slides:
        return {}

    fallback: Dict[int, str] = {
        idx: _heuristic_visual(slide, want_images=want_images)
        for idx, slide in enumerate(slides)
        if isinstance(slide, dict)
    }
    if not hasattr(content_extractor, "_llm_completion_plain_text"):
        return fallback

    payload = {
        "raw_input_excerpt": str(raw_content or "")[:5000],
        "want_images": bool(want_images),
        "slides": [
            {"slide_index": idx, "text": _slide_text(slide, max_chars=700)}
            for idx, slide in enumerate(slides)
            if isinstance(slide, dict)
        ],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are a presentation visual-routing planner.\n"
                "Choose the best primary visual for each slide: none, image, chart, or table.\n"
                "Rules:\n"
                "- chart: only for explicit comparable numeric data with at least two meaningful points.\n"
                "- table: for comparisons, before/after, pros/cons, options, criteria, status, or repeated key-value structure.\n"
                "- image: for conceptual/story/domain slides when images are requested and chart/table is not better.\n"
                "- none: for title, conclusion, thin, or abstract slides where a visual would add little value.\n"
                "- Do not choose chart/table from prose if the data structure is weak.\n"
                "Return strict JSON only: {\"slides\":[{\"slide_index\":number,\"visual\":\"none|image|chart|table\"}]}."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    try:
        raw = await content_extractor._llm_completion_plain_text(
            messages,
            max_tokens=min(1800, 240 + len(fallback) * 70),
            temperature=0.05,
            json_mode=True,
        )
        parsed = parse_json_response(raw, clean_result_text=_clean_json_text)
        items = parsed.get("slides") if isinstance(parsed, dict) else None
        if not isinstance(items, list):
            return fallback
        plan = dict(fallback)
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get("slide_index"))
            except Exception:
                continue
            visual = str(item.get("visual") or "").strip().lower()
            if idx in plan and visual in _VISUAL_VALUES:
                if fallback.get(idx) in {"chart", "table"} and visual != fallback.get(idx):
                    continue
                if visual == "image" and not want_images:
                    visual = "none"
                plan[idx] = visual
        print(f"[slide_quality] visual plan: {plan}")
        return plan
    except Exception as e:
        print(f"[slide_quality] visual plan fallback: {e}")
        return fallback
