"""Lecture-specific planning hints and source provenance utilities."""

from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any, Dict, List, Sequence, Tuple


SOURCE_PAGE_MARKER = "[[SOURCE_PAGE:{page}]]"
_PAGE_RE = re.compile(r"\[\[SOURCE_PAGE:\s*(\d+)\s*\]\]", re.IGNORECASE)

_LECTURE_TERMS = (
    "bài giảng", "bai giang", "giáo án", "giao an", "bài học", "bai hoc",
    "sinh viên", "sinh vien", "học viên", "hoc vien", "mục tiêu học tập",
    "learning objective", "lecture", "lesson", "textbook", "chapter",
    "exercise", "course", "curriculum", "tutorial", "workshop",
)
_LECTURE_REQUEST_TERMS = (
    "bai giang", "giao an", "bai hoc", "muc tieu hoc tap",
    "learning objective", "lecture", "lesson", "course", "curriculum", "tutorial",
)
_EDUCATIONAL_SOURCE_PATTERNS = (
    r"\bchapter\s+\d+\b",
    r"\b(?:section|exercise|example)\s+\d+(?:\.\d+)*\b",
    r"\b(?:learning objectives?|chapter summary|review questions?)\b",
    r"\bchương\s+\d+\b",
    r"\b(?:bài tập|ví dụ)\s+\d+(?:\.\d+)*\b",
)
_STOPWORDS = {
    "the", "and", "for", "from", "that", "this", "with", "into", "are", "was",
    "were", "have", "has", "will", "can", "của", "và", "cho", "trong", "được",
    "với", "các", "những", "một", "này", "là", "khi", "để", "từ",
}

LECTURE_ROLES = {
    "learning_objectives",
    "concept",
    "worked_example",
    "demonstration",
    "practice",
    "knowledge_check",
    "summary",
}


def detect_lecture_mode(source_text: str, user_instruction: str = "") -> bool:
    """Detect teaching-oriented requests and textbook-like source material."""
    instruction = _fold(user_instruction)
    source = _fold((source_text or "")[:30000])
    if any(term in instruction for term in _LECTURE_REQUEST_TERMS):
        return True
    if any(term in source[:3000] for term in _LECTURE_REQUEST_TERMS):
        return True
    pattern_hits = sum(bool(re.search(pattern, source, re.IGNORECASE)) for pattern in _EDUCATIONAL_SOURCE_PATTERNS)
    pedagogical_hits = sum(source.count(term) for term in _LECTURE_TERMS)
    return pattern_hits >= 2 or pedagogical_hits >= 4


def lecture_prompt_block() -> str:
    """Contract injected into the existing AI pipeline when lecture mode is active."""
    return (
        "LECTURE MODE (pedagogical quality is mandatory):\n"
        "- Design a teachable sequence, not a generic business presentation.\n"
        "- Begin the content deck with concrete learning objectives appropriate to the source and audience.\n"
        "- Order ideas by prerequisite: prior knowledge -> core concept -> explanation -> example or demonstration "
        "-> guided practice or knowledge check -> synthesis.\n"
        "- Use worked examples, code examples, formulas, diagrams, exercises, or checks only when supported by "
        "the source or explicitly requested; never invent technical facts or source examples.\n"
        "- Prefer one instructional purpose per slide and avoid repeating the same concept across slides.\n"
        "- Speaker notes must help an instructor teach: explain misconceptions, ask a useful question, or clarify "
        "the example. Do not merely restate bullets.\n"
        "- For each slide return pedagogical_role as one of: learning_objectives, concept, worked_example, "
        "demonstration, practice, knowledge_check, summary.\n"
        "- When [[SOURCE_PAGE:n]] markers exist, return source_pages with the page numbers that substantively "
        "support that slide. Never invent page numbers.\n"
        "- Top-level JSON must include presentation_mode='lecture' and learning_objectives as 2-5 concise outcomes.\n\n"
    )


def enrich_lecture_deck(
    structured_content: Dict[str, Any],
    source_text: str,
    user_instruction: str = "",
) -> Dict[str, Any]:
    """Attach reliable lecture metadata without rewriting AI-authored slide content."""
    if not isinstance(structured_content, dict):
        return structured_content
    if (
        str(structured_content.get("presentation_mode") or "").strip().lower() != "lecture"
        and not detect_lecture_mode(source_text, user_instruction)
    ):
        return structured_content

    deck = copy.deepcopy(structured_content)
    slides = deck.get("slides")
    if not isinstance(slides, list):
        return deck

    pages = _split_source_pages(source_text)
    objectives: List[str] = []
    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        role = str(slide.get("pedagogical_role") or "").strip().lower()
        if role not in LECTURE_ROLES:
            role = _infer_role(slide, idx, len(slides))
        slide["pedagogical_role"] = role

        explicit_pages = _normalize_page_numbers(slide.get("source_pages"), valid_pages={p for p, _ in pages})
        slide["source_pages"] = explicit_pages or _match_source_pages(slide, pages)
        if role == "learning_objectives":
            objectives.extend(str(item).strip() for item in (slide.get("bullets") or []) if str(item).strip())

    raw_objectives = deck.get("learning_objectives")
    if isinstance(raw_objectives, list):
        objectives = [str(item).strip() for item in raw_objectives if str(item).strip()] + objectives
    objectives = _dedupe(objectives)[:5]

    objective_index = next(
        (
            idx
            for idx, slide in enumerate(slides)
            if isinstance(slide, dict) and slide.get("pedagogical_role") == "learning_objectives"
        ),
        None,
    )
    if objective_index is None and len(objectives) >= 2:
        language_source = " ".join(
            [str(deck.get("title") or ""), str(user_instruction or "")]
            + [str(item) for item in objectives]
        )
        vietnamese = bool(
            re.search(
                r"[ăâđêôơưàáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ]",
                language_source,
                re.IGNORECASE,
            )
        )
        objective_slide = {
            "title": "Mục tiêu học tập" if vietnamese else "Learning Objectives",
            "bullets": objectives,
            "notes": "",
            "layout": "text_only",
            "pedagogical_role": "learning_objectives",
            "source_pages": [],
        }
        intro_index = next(
            (
                idx
                for idx, slide in enumerate(slides)
                if isinstance(slide, dict)
                and str(slide.get("layout") or "").strip().lower() in {"intro", "title"}
            ),
            None,
        )
        slides.insert(1 if intro_index == 0 else 0, objective_slide)
        objective_index = 1 if intro_index == 0 else 0
    if objective_index is not None and objective_index > 1:
        objective_slide = slides.pop(objective_index)
        first_slide = slides[0] if slides and isinstance(slides[0], dict) else {}
        first_layout = str(first_slide.get("layout") or "").strip().lower()
        first_title = _fold(first_slide.get("title") or "")
        intro_terms = ("introduction", "overview", "gioi thieu", "tong quan", "title")
        has_intro = first_layout in {"intro", "title"} or any(
            term in first_title for term in intro_terms
        )
        slides.insert(1 if has_intro else 0, objective_slide)

    deck["presentation_mode"] = "lecture"
    deck["learning_objectives"] = objectives
    _clean_fragmented_bullets(slides)
    return deck


def select_relevant_source_excerpt(
    source_text: str,
    user_instruction: str = "",
    *,
    max_chars: int = 9000,
) -> str:
    """Choose source pages most relevant to the user's requested scope."""
    source = str(source_text or "")
    if len(source) <= max_chars:
        return source

    pages = _split_source_pages(source)
    query_tokens = _tokens(user_instruction)
    if not pages or not query_tokens:
        return source[:max_chars]

    folded_instruction = _fold(user_instruction)
    scope_anchors = set(
        re.findall(
            r"\b(?:chapter|chuong|section|unit|module|lesson|bai)\s+\d+(?:\.\d+)*\b",
            folded_instruction,
        )
    )
    scored: List[Tuple[float, int, str]] = []
    for page_number, page_text in pages:
        page_tokens = _tokens(page_text)
        overlap = query_tokens & page_tokens
        if not overlap:
            continue
        score = sum(2.0 if len(token) >= 6 else 1.0 for token in overlap)
        folded_page = _fold(page_text)
        score += 20.0 * sum(anchor in folded_page for anchor in scope_anchors)
        scored.append((score, page_number, page_text))

    if not scored:
        return source[:max_chars]

    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score = scored[0][0]
    focused = [item for item in scored if item[0] >= max(2.0, best_score * 0.6)]
    primary_numbers = sorted(page for _, page, _ in focused[:8])
    selected_numbers = set(primary_numbers)
    page_map = {page: text for page, text in pages}
    for page in list(selected_numbers):
        if page - 1 in page_map:
            selected_numbers.add(page - 1)
        if page + 1 in page_map:
            selected_numbers.add(page + 1)

    parts: List[str] = []
    used = 0
    ordered_numbers = primary_numbers + [
        page for page in sorted(selected_numbers) if page not in primary_numbers
    ]
    for page in ordered_numbers:
        part = f"{SOURCE_PAGE_MARKER.format(page=page)}\n{page_map[page].strip()}"
        if parts and used + len(part) > max_chars:
            break
        if not parts and len(part) > max_chars:
            part = part[:max_chars]
        parts.append(part)
        used += len(part)
    return "\n\n".join(parts) or source[:max_chars]


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-ZÀ-ỹ_][\wÀ-ỹ.-]{2,}", _fold(text))
        if token not in _STOPWORDS and not token.isdigit()
    }


def _split_source_pages(source_text: str) -> List[Tuple[int, str]]:
    matches = list(_PAGE_RE.finditer(source_text or ""))
    if not matches:
        return []
    pages: List[Tuple[int, str]] = []
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(source_text)
        text = (source_text[start:end] or "").strip()
        if text:
            pages.append((int(match.group(1)), text))
    return pages


def _match_source_pages(slide: Dict[str, Any], pages: Sequence[Tuple[int, str]]) -> List[int]:
    if not pages:
        return []
    slide_text = " ".join(
        [str(slide.get("title") or "")]
        + [str(item) for item in (slide.get("bullets") or [])]
    )
    wanted = _tokens(slide_text)
    if not wanted:
        return []
    scored: List[Tuple[float, int]] = []
    for page_number, page_text in pages:
        page_tokens = _tokens(page_text)
        overlap = len(wanted & page_tokens)
        if overlap:
            scored.append((overlap / max(4, len(wanted)), page_number))
    if not scored:
        return []
    scored.sort(reverse=True)
    best = scored[0][0]
    if best < 0.16:
        return []
    return sorted(page for score, page in scored[:3] if score >= max(0.14, best * 0.65))


def _clean_fragmented_bullets(slides: Sequence[Any]) -> None:
    """Merge dangling labels with their following explanation without rewriting facts."""
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        raw = slide.get("bullets")
        if not isinstance(raw, list):
            continue
        bullets = [re.sub(r"\s+", " ", str(item or "")).strip() for item in raw]
        bullets = [item for item in bullets if item]
        cleaned: List[str] = []
        index = 0
        while index < len(bullets):
            current = bullets[index]
            words = re.findall(r"\w+", current, flags=re.UNICODE)
            dangling_label = current.endswith(":") and len(words) <= 7
            if dangling_label and index + 1 < len(bullets):
                cleaned.append(f"{current} {bullets[index + 1]}".strip())
                index += 2
                continue
            if dangling_label:
                index += 1
                continue
            cleaned.append(current)
            index += 1
        slide["bullets"] = cleaned


def _normalize_page_numbers(value: Any, valid_pages: set[int]) -> List[int]:
    if not isinstance(value, list):
        return []
    result: List[int] = []
    for item in value:
        try:
            page = int(item)
        except (TypeError, ValueError):
            continue
        if page > 0 and (not valid_pages or page in valid_pages) and page not in result:
            result.append(page)
    return sorted(result[:3])


def _infer_role(slide: Dict[str, Any], index: int, total: int) -> str:
    text = _fold(" ".join([str(slide.get("title") or "")] + [str(x) for x in (slide.get("bullets") or [])]))
    if any(term in text for term in ("learning objective", "muc tieu hoc tap", "sau bai hoc")):
        return "learning_objectives"
    if any(term in text for term in ("quiz", "knowledge check", "review question", "cau hoi", "kiem tra")):
        return "knowledge_check"
    if any(term in text for term in ("exercise", "practice", "bai tap", "thuc hanh")):
        return "practice"
    if any(term in text for term in ("worked example", "example", "vi du", "case study")):
        return "worked_example"
    if any(term in text for term in ("demo", "demonstration", "minh hoa", "step by step")):
        return "demonstration"
    if index == total - 1 or any(term in text for term in ("summary", "key takeaway", "tong ket", "ket luan")):
        return "summary"
    return "concept"


def _dedupe(items: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        key = re.sub(r"\W+", " ", _fold(item)).strip()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result
