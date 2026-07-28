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
    r"so\s*sánh|so\s*sanh|tiêu\s*chí|tieu\s*chi|ưu\s*điểm|uu\s*diem|"
    r"nhược\s*điểm|nhuoc\s*diem|phương\s*án|phuong\s*an)\b",
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


def _preserve_lecture_density(
    reviewed: Dict[str, Any],
    original: Dict[str, Any],
) -> Dict[str, Any]:
    """Prevent a review pass from reducing teaching slides to sparse stubs."""
    if str(original.get("presentation_mode") or "").strip().lower() != "lecture":
        return reviewed
    reviewed_slides = reviewed.get("slides") or []
    original_slides = original.get("slides") or []
    if len(reviewed_slides) != len(original_slides):
        return reviewed
    compact_roles = {"knowledge_check", "practice", "summary"}
    for new_slide, old_slide in zip(reviewed_slides, original_slides):
        if not isinstance(new_slide, dict) or not isinstance(old_slide, dict):
            continue
        role = str(old_slide.get("pedagogical_role") or "").strip().lower()
        minimum = 3 if role in compact_roles else 4
        new_bullets = [str(x).strip() for x in (new_slide.get("bullets") or []) if str(x).strip()]
        old_bullets = [str(x).strip() for x in (old_slide.get("bullets") or []) if str(x).strip()]
        if len(new_bullets) < minimum and len(old_bullets) >= minimum:
            new_slide["bullets"] = old_bullets
        if old_slide.get("pedagogical_role") and not new_slide.get("pedagogical_role"):
            new_slide["pedagogical_role"] = old_slide["pedagogical_role"]
        if old_slide.get("source_pages") and not new_slide.get("source_pages"):
            new_slide["source_pages"] = old_slide["source_pages"]
    reviewed["presentation_mode"] = "lecture"
    return reviewed


def _preserve_slide_layouts(reviewed: Dict[str, Any], original: Dict[str, Any]) -> Dict[str, Any]:
    """Keep renderer contracts when a text review omits layout metadata."""
    reviewed_slides = reviewed.get("slides") or []
    original_slides = original.get("slides") or []
    if len(reviewed_slides) != len(original_slides):
        return reviewed
    for new_slide, old_slide in zip(reviewed_slides, original_slides):
        if not isinstance(new_slide, dict) or not isinstance(old_slide, dict):
            continue
        if old_slide.get("layout") and not new_slide.get("layout"):
            new_slide["layout"] = old_slide["layout"]
    return reviewed


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
    from services.lecture_quality import select_relevant_source_excerpt

    user_instruction = str(getattr(content_extractor, "_user_instruction", "") or "").strip()
    source_excerpt = select_relevant_source_excerpt(
        source,
        user_instruction,
        max_chars=9000,
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a strict source-grounded presentation editor.\n"
                "Revise the slide deck only to improve fidelity to the source and professional slide quality.\n"
                "Rules:\n"
                f"- Keep EXACTLY {expected} slides and keep the same JSON schema.\n"
                "- Treat explicit user-requested topics, order, visual types, table columns/rows, and chart series as mandatory requirements.\n"
                "- Ensure every mandatory requested topic has a suitable slide. If one is missing, replace a redundant or lower-priority slide; never silently omit it.\n"
                "- Remove or rewrite every claim, number, percentage, name, or result that is not grounded in the source.\n"
                "- Add missing important source details to the most suitable slide while preserving the requested narrative order.\n"
                "- For lecture decks, retain 4-6 substantive bullets on concept, explanation, and worked-example slides; "
                "knowledge-check, practice, and summary slides may use 3-5. Never shorten a teaching slide into a stub.\n"
                "- Improve vague bullets by replacing them with concrete terms, numbers, names, or results from the source.\n"
                "- Keep related numeric series together on one suitable slide. For example Q1/Q2/Q3/Q4 values must not be split across unrelated slides.\n"
                "- Keep requested comparison/table content together on the same slide; do not mix one comparison row with chart series data.\n"
                "- A requested comparison table must remain recognizable in title/bullets as a comparison and include every requested column or row label.\n"
                "- Preserve all technical terms, proper nouns, numbers, and user intent.\n"
                "- The explicit user instruction is the authoritative scope. Do not replace a requested chapter, "
                "section, audience, or teaching goal with a different part of the source.\n"
                "- Do not add chart/table/image fields. Preserve each existing layout value, especially intro and thankyou.\n"
                "Return ONLY valid JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                "EXPLICIT USER INSTRUCTION:\n"
                f"{user_instruction or '(none)'}\n\n"
                "SOURCE EXCERPT:\n"
                f"{source_excerpt}\n\n"
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
        reviewed = _preserve_slide_layouts(reviewed, structured)
        reviewed = _preserve_lecture_density(reviewed, structured)
        normalized = content_extractor._normalize_structured_content(reviewed)
        from services.slide_text_quality import (
            improve_slide_titles_quality,
            improve_speaker_notes_quality,
        )
        normalized = await improve_slide_titles_quality(
            content_extractor,
            normalized,
            source_language=(getattr(content_extractor, "_slide_lang_hint", "auto") or "auto"),
        )
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
    # Slide đã có object table/chart thật sự → luôn ưu tiên
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
    if want_images:
        return "image"
    return "none"


def _declared_visual(slide: Dict[str, Any]) -> Optional[str]:
    """Return only an explicit visual contract already present on the slide."""
    layout = str(slide.get("layout") or "").strip().lower()
    if isinstance(slide.get("table"), dict) or "table" in layout:
        return "table"
    if isinstance(slide.get("chart"), dict) or slide.get("chart_type") or "chart" in layout:
        return "chart"
    if slide.get("image") or slide.get("image_url") or "image" in layout:
        return "image"
    return None


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
                "- When want_images=true, route at least 30% of the deck to image unless chart/table already "
                "provides the visual. Avoid an overly text-only deck.\n"
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
                declared = _declared_visual(slides[idx]) if isinstance(slides[idx], dict) else None
                if declared in {"chart", "table"} and visual != declared:
                    continue
                if visual == "image" and not want_images:
                    visual = "none"
                plan[idx] = visual
        if want_images:
            fallback_candidates = [
                idx for idx, visual in fallback.items()
                if visual == "image" and plan.get(idx) not in {"chart", "table"}
            ]
            minimum_images = min(
                len(fallback_candidates),
                max(1, (len(slides) * 3 + 9) // 10),
            )
            planned_images = sum(1 for visual in plan.values() if visual == "image")
            if planned_images < minimum_images:
                selected = {idx for idx, visual in plan.items() if visual == "image"}
                remaining = {idx for idx in fallback_candidates if idx not in selected}
                while planned_images < minimum_images and remaining:
                    # Pick the candidate furthest from an existing image so the
                    # deck does not receive all fallback visuals at the start.
                    anchors = selected or {-1, len(slides)}
                    idx = max(
                        remaining,
                        key=lambda candidate: (
                            min(abs(candidate - anchor) for anchor in anchors),
                            len((slides[candidate].get("bullets") or slides[candidate].get("content") or [])),
                        ),
                    )
                    plan[idx] = "image"
                    selected.add(idx)
                    remaining.remove(idx)
                    planned_images += 1
                print(
                    "[slide_quality] visual plan augmented: "
                    f"{planned_images} image slide(s), minimum={minimum_images}"
                )

            # Even a sufficient total can be poor when all visuals are clustered.
            # Break long text-only runs while suitable image candidates remain.
            run_start = 0
            while run_start < len(slides):
                if plan.get(run_start) != "none":
                    run_start += 1
                    continue
                run_end = run_start
                while run_end + 1 < len(slides) and plan.get(run_end + 1) == "none":
                    run_end += 1
                if run_end - run_start + 1 > 4:
                    eligible = [
                        idx for idx in fallback_candidates
                        if run_start <= idx <= run_end and plan.get(idx) == "none"
                    ]
                    if eligible:
                        midpoint = (run_start + run_end) / 2
                        chosen = min(eligible, key=lambda idx: abs(idx - midpoint))
                        plan[chosen] = "image"
                        planned_images += 1
                        continue
                run_start = run_end + 1
        print(f"[slide_quality] visual plan: {plan}")
        return plan
    except Exception as e:
        print(f"[slide_quality] visual plan fallback: {e}")
        return fallback
