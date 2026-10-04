"""Internal quality helpers for slide decks.

These functions improve the AI output before BE/FE receive the same JSON
contract as before. They do not add required fields for clients.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from services.content.json_utils import parse_json_response
from services.grounding_policy import policy_for_extractor


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


def _is_dense_for_image(slide: Dict[str, Any]) -> bool:
    """Return whether an image would make the visible content unreadably tight."""
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        items = [line.strip() for line in bullets.splitlines() if line.strip()]
    else:
        items = [str(item).strip() for item in bullets if str(item).strip()]
    visible_chars = sum(len(item) for item in items)
    longest_item = max((len(item) for item in items), default=0)
    return (
        len(items) > 7
        or visible_chars > 760
        or (len(items) >= 6 and visible_chars > 560)
        or (len(items) >= 5 and longest_item > 190)
    )


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
    user_instruction = str(getattr(content_extractor, "_user_instruction", "") or "").strip()
    focused_source = str(
        getattr(content_extractor, "_focused_source_content", "") or ""
    )
    source_excerpt = (focused_source or source)[:12000]
    grounding_policy = policy_for_extractor(content_extractor, focused_source or source)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a strict source-grounded presentation editor.\n"
                "Revise the slide deck only to improve fidelity to the source and professional slide quality.\n"
                f"{grounding_policy.instruction_block()}\n"
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
                "- Never put internal messages such as 'not supported by the source', 'insufficient evidence', "
                "or comments about retrieval/grounding into slide titles, bullets, or notes.\n"
                "- If a mandatory requested topic has limited direct source support, keep the topic and add only "
                "stable foundational explanation, clearly illustrative examples, or a practice question. "
                "Never invent statistics, quotations, citations, named findings, or document-specific claims.\n"
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
    from services.technical_quality import slide_has_code_content

    if slide_has_code_content(slide):
        return "none"
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
    if _is_dense_for_image(slide):
        return "none"
    if want_images:
        return "image"
    return "none"


def _declared_visual(slide: Dict[str, Any]) -> Optional[str]:
    """Return only an explicit visual contract already present on the slide."""
    layout = str(slide.get("layout") or "").strip().lower()
    # Models sometimes encode chart-ready category/value data as an inline
    # table. A clear chart title is the stronger semantic contract; keeping the
    # table here would prevent the chart builder from ever seeing the slide.
    if isinstance(slide.get("table"), dict):
        from services.slide_charts import chart_intent_from_slide
        if chart_intent_from_slide(slide, slide_spec=slide):
            return "chart"
    if isinstance(slide.get("table"), dict) or "table" in layout:
        return "table"
    if isinstance(slide.get("chart"), dict) or slide.get("chart_type") or "chart" in layout:
        return "chart"
    if slide.get("image") or slide.get("image_url") or "image" in layout:
        return "image"
    return None


_FILLER_HEADINGS = {
    "noi dung chinh", "noi dung", "goc nhin bo sung", "bo sung", "khac", "y chinh", "y khac", "phan 1", "phan 2",
    "nhom 1", "nhom 2", "main content", "main points", "content", "additional perspective", "additional",
    "other", "others", "group 1", "group 2", "part 1", "part 2",
}


def _is_filler_heading(heading: str) -> bool:
    import unicodedata
    folded = unicodedata.normalize("NFD", str(heading or "").casefold().replace("đ", "d"))
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return " ".join(folded.replace(":", " ").split()) in _FILLER_HEADINGS


def _apply_planned_composition(slide: Dict[str, Any], item: Dict[str, Any], visual: str) -> None:
    """Apply a renderer-supported non-asset composition without losing content."""
    if visual != "none":
        return
    current_layout = str(slide.get("layout") or "").strip().lower()
    # A slide already composed in columns carries its headings in its bullets ("Heading — point");
    # composing it again prefixed every bullet once more, and the headings piled up with each edit.
    if current_layout in {"intro", "title", "thankyou", "thank_you", "text_table", "text_chart", "text_image", "split_columns"}:
        return
    if str(item.get("composition") or "standard").strip().lower() != "split_columns":
        return

    bullets = slide.get("bullets") or slide.get("content") or []
    if not isinstance(bullets, list) or not 4 <= len(bullets) <= 8:
        return

    def valid_indices(value: Any) -> List[int]:
        if not isinstance(value, list):
            return []
        result: List[int] = []
        for raw_index in value:
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(bullets) and index not in result:
                result.append(index)
        return result

    left_indices = valid_indices(item.get("left_indices"))
    right_indices = valid_indices(item.get("right_indices"))
    if not left_indices or not right_indices or set(left_indices) & set(right_indices):
        return
    assigned = set(left_indices) | set(right_indices)
    for index in range(len(bullets)):
        if index not in assigned:
            (left_indices if len(left_indices) <= len(right_indices) else right_indices).append(index)

    left_heading = str(item.get("left_heading") or "").strip()[:48]
    right_heading = str(item.get("right_heading") or "").strip()[:48]
    if not left_heading or not right_heading or left_heading.casefold() == right_heading.casefold():
        return
    # A heading that says nothing about its group would be printed in front of every bullet.
    if _is_filler_heading(left_heading) or _is_filler_heading(right_heading):
        return

    slide["bullets"] = [
        *[f"{left_heading} — {str(bullets[index]).strip()}" for index in left_indices],
        *[f"{right_heading} — {str(bullets[index]).strip()}" for index in right_indices],
    ]
    slide["layout"] = "split_columns"


_COLUMN_PREFIX_RE = re.compile(r"^(.{1,48}?)\s[—–-]\s(?=\S)")


def limit_split_columns(slides: List[Dict[str, Any]]) -> int:
    """Keep two-column slides to about a third of the deck and never two in a row.

    The author and the visual planner both reach for the two-column layout, and a deck came back
    with five of its eight slides in it. The extra ones go back to plain bullets (their column
    heading is taken off the front of each bullet). Returns how many were changed.
    """
    content = [i for i, s in enumerate(slides) if isinstance(s, dict)
               and str(s.get("layout") or "").lower() not in {"intro", "title", "thankyou", "thank_you"}]
    split = [i for i in content if str(slides[i].get("layout") or "").lower() == "split_columns"]
    allowed = max(1, (len(content) + 2) // 3)
    kept: List[int] = []
    changed = 0
    for index in split:
        if len(kept) < allowed and (not kept or index - kept[-1] > 1):
            kept.append(index)
            continue
        bullets = [str(b) for b in (slides[index].get("bullets") or [])]
        matches = [_COLUMN_PREFIX_RE.match(b) for b in bullets]
        headings = {m.group(1).strip().casefold() for m in matches if m}
        if bullets and all(matches) and len(headings) <= 2:
            slides[index]["bullets"] = [b[m.end():] for b, m in zip(bullets, matches)]
        slides[index]["layout"] = "text_only"
        changed += 1
    if changed:
        print(f"[slide_quality] two-column layout limited: {changed} slide(s) back to plain bullets")
    return changed


_CHART_REQUEST = re.compile(r"biểu đồ|đồ thị|\bcharts?\b|\bgraphs?\b", re.IGNORECASE)


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
        idx: (_declared_visual(slide) or _heuristic_visual(slide, want_images=want_images))
        for idx, slide in enumerate(slides)
        if isinstance(slide, dict)
    }
    if not hasattr(content_extractor, "_llm_completion_plain_text"):
        return fallback

    payload = {
        "raw_input_excerpt": str(raw_content or "")[:5000],
        "want_images": bool(want_images),
        "slides": [
            {
                "slide_index": idx,
                "title": str(slide.get("title") or ""),
                "bullets": slide.get("bullets") or slide.get("content") or [],
                "layout": str(slide.get("layout") or ""),
                "text": _slide_text(slide, max_chars=700),
            }
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
                "- chart: only for explicit comparable numeric data with at least two meaningful points. When the "
                "user request asks for a chart of some data, the slide carrying that data is a chart, not a table.\n"
                "- table: for comparisons, before/after, pros/cons, options, criteria, status, or repeated key-value structure.\n"
                "- image: for conceptual/story/domain slides when images are requested and chart/table is not better.\n"
                "- none: for title, conclusion, thin, or abstract slides where a visual would add little value.\n"
                "- none: also for dense slides with over 7 bullets or roughly over 760 visible characters; "
                "readability is more important than decorative image coverage.\n"
                "- When want_images=true, keep the whole deck visually balanced: roughly half of the content "
                "slides should use an image, chart, or table when suitable, and at least 35% should use images "
                "when chart/table coverage is low. Do not count cover or closing slides toward this target.\n"
                "- Avoid more than two consecutive none slides when a relevant, non-dense image candidate exists.\n"
                "- For a none slide with 4-8 bullets that naturally forms exactly two meaningful groups, set "
                "composition=split_columns and return concise left_heading/right_heading plus zero-based "
                "left_indices/right_indices covering the bullets. Otherwise use composition=standard.\n"
                "- Evaluate composition as a fallback for every slide, including image candidates, because deck-level "
                "balancing may later remove a lower-priority image.\n"
                "- Return image_priority from 0.0 to 1.0 for every image choice: use higher values only when the "
                "image materially explains the slide rather than merely decorating it.\n"
                "- Do not force split columns merely for variety; both groups must have distinct meanings, and each "
                "heading must name what its group is about (never a filler such as Main content, Additional "
                "perspective, Nội dung chính or Góc nhìn bổ sung).\n"
                "- Do not choose chart/table from prose if the data structure is weak.\n"
                "Return strict JSON only: {\"slides\":[{\"slide_index\":number,"
                "\"visual\":\"none|image|chart|table\",\"composition\":\"standard|split_columns\","
                "\"image_priority\":number,"
                "\"left_heading\":string,\"right_heading\":string,"
                "\"left_indices\":[number],\"right_indices\":[number]}]}."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    try:
        raw = await content_extractor._llm_completion_plain_text(
            messages,
            max_tokens=min(2600, 300 + len(fallback) * 115),
            temperature=0.05,
            json_mode=True,
        )
        parsed = parse_json_response(raw, clean_result_text=_clean_json_text)
        items = parsed.get("slides") if isinstance(parsed, dict) else None
        if not isinstance(items, list):
            return fallback
        plan = dict(fallback)
        items_by_index: Dict[int, Dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                idx = int(item.get("slide_index"))
            except Exception:
                continue
            visual = str(item.get("visual") or "").strip().lower()
            if idx in plan and visual in _VISUAL_VALUES:
                items_by_index[idx] = item
                from services.technical_quality import slide_has_code_content
                if slide_has_code_content(slides[idx]):
                    plan[idx] = "none"
                    continue
                declared = _declared_visual(slides[idx]) if isinstance(slides[idx], dict) else None
                if declared in {"chart", "table"} and visual != declared:
                    continue
                if visual == "image" and not want_images:
                    visual = "none"
                if visual == "image" and _is_dense_for_image(slides[idx]):
                    visual = "none"
                plan[idx] = visual
        if want_images:
            boundary_indices = {
                idx for idx, slide in enumerate(slides)
                if str((slide or {}).get("layout") or "").strip().lower()
                in {"intro", "title", "thankyou", "thank_you"}
            }
            for idx in boundary_indices:
                plan[idx] = "none"
            fallback_candidates = [
                idx for idx, visual in fallback.items()
                if (
                    idx not in boundary_indices
                    and visual == "image"
                    and plan.get(idx) not in {"chart", "table"}
                )
            ]
            content_indices = [idx for idx in range(len(slides)) if idx not in boundary_indices]
            maximum_images = max(1, (len(content_indices) * 55 + 99) // 100)
            planned_image_indices = [idx for idx in content_indices if plan.get(idx) == "image"]
            while len(planned_image_indices) > maximum_images:
                def removal_key(candidate: int) -> tuple[float, int, int]:
                    item = items_by_index.get(candidate) or {}
                    try:
                        priority = max(0.0, min(1.0, float(item.get("image_priority") or 0.0)))
                    except (TypeError, ValueError):
                        priority = 0.0
                    others = [idx for idx in planned_image_indices if idx != candidate]
                    nearest = min((abs(candidate - idx) for idx in others), default=len(slides))
                    return priority, nearest, candidate

                removed = min(planned_image_indices, key=removal_key)
                plan[removed] = "none"
                planned_image_indices.remove(removed)
                print(
                    "[slide_quality] visual plan capped: "
                    f"demoted slide {removed}, maximum_images={maximum_images}"
                )
            structured_visuals = sum(
                1 for idx in content_indices if plan.get(idx) in {"chart", "table"}
            )
            image_floor = (len(content_indices) * 35 + 99) // 100
            visual_target = (len(content_indices) + 1) // 2
            minimum_images = min(
                len(fallback_candidates),
                max(1, image_floor, visual_target - structured_visuals),
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
                if run_end - run_start + 1 > 2:
                    eligible = [
                        idx for idx in fallback_candidates
                        if run_start <= idx <= run_end and plan.get(idx) == "none"
                    ]
                    if eligible and planned_images < maximum_images:
                        midpoint = (run_start + run_end) / 2
                        chosen = min(eligible, key=lambda idx: abs(idx - midpoint))
                        plan[chosen] = "image"
                        planned_images += 1
                        continue
                run_start = run_end + 1

        # A slide whose bullets are a labelled series of comparable values (four quarters, yearly
        # totals) reads far better as a chart, and the planner often leaves it as plain text.
        # When the request itself asks for a chart, the same series wins over a table the planner chose.
        from services.slide_charts import labelled_value_series
        chart_asked = bool(_CHART_REQUEST.search(str(raw_content or "")))
        for idx, slide in enumerate(slides):
            replaceable = {"none", "table"} if chart_asked else {"none"}
            if plan.get(idx) not in replaceable or not isinstance(slide, dict):
                continue
            if str(slide.get("layout") or "").strip().lower() in {"intro", "title", "thankyou", "thank_you"}:
                continue
            if labelled_value_series(slide.get("bullets") or []):
                plan[idx] = "chart"
                print(f"[slide_quality] visual plan: slide {idx} has a labelled value series -> chart")
        # A series the user dictated for a chart ("biểu đồ doanh thu theo quý: Quý 1 là 320, ...")
        # belongs on the slide that talks about it, whatever visual the planner picked there.
        from services.slide_charts import _inline_series_candidates, _slide_match_score
        dictated: set = set()
        for candidate in _inline_series_candidates(raw_content):
            scores = {
                idx: _slide_match_score(slide, candidate)
                for idx, slide in enumerate(slides)
                if isinstance(slide, dict) and idx not in dictated
                and str(slide.get("layout") or "").strip().lower() not in {"intro", "title", "thankyou", "thank_you"}
            }
            if not scores:
                continue
            best = max(scores, key=lambda idx: (scores[idx], plan.get(idx) == "chart"))
            if scores[best] < 2:
                continue
            dictated.add(best)
            if plan.get(best) != "chart":
                print(f"[slide_quality] visual plan: slide {best} carries a chart the request dictated ({plan.get(best)} -> chart)")
                plan[best] = "chart"
        for idx, item in items_by_index.items():
            if 0 <= idx < len(slides) and isinstance(slides[idx], dict):
                _apply_planned_composition(slides[idx], item, plan.get(idx, "none"))
        limit_split_columns(slides)
        print(f"[slide_quality] visual plan: {plan}")
        return plan
    except Exception as e:
        print(f"[slide_quality] visual plan fallback: {e}")
        return fallback
