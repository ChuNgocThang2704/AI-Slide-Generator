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
_PRESENTATION_REQUEST_TERMS = (
    "pitch deck", "business presentation", "sales presentation",
    "investor presentation", "executive report", "bao cao kinh doanh",
    "bao cao dieu hanh", "showcase", "pitch",
)
_NON_LECTURE_REQUEST_TERMS = (
    "khong phai bai giang", "khong theo dang bai giang", "khong can bai giang",
    "not a lecture", "non-lecture", "without lecture structure",
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

_PEDAGOGICAL_REQUIREMENT_TERMS = {
    "worked_example": (
        "vi du", "minh hoa", "tinh huong", "worked example", "example", "case study",
    ),
    "common_mistakes": (
        "loi thuong gap", "sai lam thuong gap", "loi pho bien", "common mistake",
        "common error", "pitfall", "debugging error",
    ),
    "knowledge_check": (
        "cau hoi kiem tra", "cau hoi cuoi bai", "kiem tra cuoi bai", "kiem tra kien thuc",
        "knowledge check", "review question", "quiz", "question at the end",
    ),
    "practice": (
        "bai tap", "thuc hanh", "luyen tap", "practice", "exercise", "activity",
    ),
}


def instructional_requirements(user_instruction: str) -> List[str]:
    """Return requested teaching devices without interpreting the subject matter."""
    folded = _fold(user_instruction)
    return [
        requirement
        for requirement, terms in _PEDAGOGICAL_REQUIREMENT_TERMS.items()
        if any(term in folded for term in terms)
    ]


def detect_lecture_mode(source_text: str, user_instruction: str = "") -> bool:
    """Detect teaching-oriented requests and textbook-like source material."""
    instruction = _fold(user_instruction)
    source = _fold((source_text or "")[:30000])
    # Explicit user intent outranks the shape of an uploaded textbook or the
    # educational vocabulary produced while expanding a prompt. A source can
    # provide presentation content without turning the deck into a lesson.
    if any(term in instruction for term in _NON_LECTURE_REQUEST_TERMS):
        return False
    if any(term in instruction for term in _LECTURE_REQUEST_TERMS):
        return True
    if any(term in instruction for term in _PRESENTATION_REQUEST_TERMS):
        return False
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
        "- Every abstract or technical concept must be made teachable with a concrete, source-grounded example "
        "on that slide or the immediately following slide. For programming, prefer valid code or an exact "
        "input/output trace; for mathematics, prefer a worked expression; for processes, prefer numbered steps.\n"
        "- Put source-grounded programming examples in separate bullet strings, one executable statement per "
        "string when practical. Code, formulas, commands, and exact input/output lines are exempt from prose "
        "minimum-word and sentence-ending rules; never rewrite them as explanatory prose.\n"
        "- Do not replace a useful technical example, code sample, formula, or diagram with a generic stock-photo idea.\n"
        "- Avoid unsupported absolutes such as 'always', 'never', 'unlimited', or 'only' unless the source states "
        "the precise rule. Preserve exceptions and scope conditions.\n"
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
    locked_mode: str = "",
    enforce_requirements: bool = False,
) -> Dict[str, Any]:
    """Attach reliable lecture metadata without rewriting AI-authored slide content."""
    if not isinstance(structured_content, dict):
        return structured_content
    locked = str(locked_mode or "").strip().lower()
    if locked == "presentation":
        deck = copy.deepcopy(structured_content)
        deck["presentation_mode"] = "presentation"
        deck.pop("learning_objectives", None)
        return deck
    if (
        locked != "lecture"
        and
        str(structured_content.get("presentation_mode") or "").strip().lower() != "lecture"
        and not detect_lecture_mode(source_text, user_instruction)
    ):
        return structured_content

    deck = copy.deepcopy(structured_content)
    slides = deck.get("slides")
    if not isinstance(slides, list):
        return deck

    pages = _split_source_pages(source_text)
    requirements = instructional_requirements(user_instruction)
    deck["pedagogical_requirements"] = requirements
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
    if len(objectives) < 2 or not _objectives_are_specific(objectives, slides):
        objectives = _fallback_learning_objectives(
            deck,
            [slide for slide in slides if isinstance(slide, dict)],
            vietnamese=vietnamese,
        )

    objective_title_terms = (
        "muc tieu",
        "learning objective",
        "lesson objective",
        "course objective",
    )
    objective_index = next(
        (
            idx
            for idx, slide in enumerate(slides)
            if isinstance(slide, dict)
            and (
                slide.get("pedagogical_role") == "learning_objectives"
                or any(
                    term in _fold(slide.get("title") or "")
                    for term in objective_title_terms
                )
            )
        ),
        None,
    )
    if objective_index is not None:
        objective_slide = slides[objective_index]
        objective_slide["pedagogical_role"] = "learning_objectives"
        if len(objectives) >= 2:
            objective_slide["bullets"] = objectives
    if objective_index is None and len(objectives) >= 2:
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

    wants_practice = "practice" in requirements
    has_practice = any(
        isinstance(slide, dict)
        and (
            str(slide.get("pedagogical_role") or "").strip().lower() == "practice"
            or any(
                term in _fold(slide.get("title") or "")
                for term in ("bai tap", "thuc hanh", "luyen tap", "practice", "exercise", "activity")
            )
        )
        for slide in slides
    )
    if wants_practice and not has_practice:
        synthesized_practice = False
        candidate_index = next(
            (
                idx
                for idx in range(len(slides) - 1, -1, -1)
                if isinstance(slides[idx], dict)
                and str(slides[idx].get("pedagogical_role") or "").strip().lower()
                in {"knowledge_check", "worked_example"}
            ),
            None,
        )
        if candidate_index is None:
            synthesized_practice = True
            candidate_index = next(
                (
                    idx
                    for idx in range(len(slides) - 2, 0, -1)
                    if isinstance(slides[idx], dict)
                    and str(slides[idx].get("pedagogical_role") or "").strip().lower()
                    not in {"learning_objectives", "summary", "practice"}
                    and str(slides[idx].get("layout") or "").strip().lower()
                    not in {"intro", "title", "thankyou", "thank_you"}
                ),
                None,
            )
        if candidate_index is not None:
            practice_slide = slides[candidate_index]
            original_title = str(practice_slide.get("title") or "").strip()
            practice_slide["pedagogical_role"] = "practice"
            practice_slide["title"] = (
                f"Bài tập thực hành: {original_title}"
                if vietnamese
                else f"Practice: {original_title}"
            )
            if synthesized_practice and vietnamese:
                practice_slide["bullets"] = [
                    f"Vận dụng các khái niệm chính về {original_title.lower()} vào một tình huống cụ thể.",
                    "Trình bày từng bước thực hiện và giải thích lựa chọn của bạn.",
                    "Đối chiếu kết quả với nội dung đã học và nêu một lỗi thường gặp.",
                ]
            elif synthesized_practice:
                practice_slide["bullets"] = [
                    f"Apply the key ideas from {original_title.lower()} to a concrete scenario.",
                    "Show each step and explain the choices you make.",
                    "Check the result against the lesson and identify one common mistake.",
                ]

    if enforce_requirements:
        _ensure_requested_teaching_devices(slides, requirements, vietnamese=vietnamese)

    deck["presentation_mode"] = "lecture"
    deck["learning_objectives"] = objectives
    _clean_fragmented_bullets(slides)
    return deck


def enforce_instructional_requirements(
    structured_content: Dict[str, Any],
    user_instruction: str,
) -> Dict[str, Any]:
    """Guarantee explicit teaching devices after all AI and count-repair passes."""
    if not isinstance(structured_content, dict):
        return structured_content
    if str(structured_content.get("presentation_mode") or "").strip().lower() != "lecture":
        return structured_content
    deck = copy.deepcopy(structured_content)
    slides = deck.get("slides") or []
    requirements = instructional_requirements(user_instruction)
    deck["pedagogical_requirements"] = requirements
    language_text = " ".join(
        [str(deck.get("title") or ""), str(user_instruction or "")]
        + [str(slide.get("title") or "") for slide in slides if isinstance(slide, dict)]
    )
    vietnamese = bool(re.search(r"[ăâđêôơưàáạảãèéẹẻẽìíịỉĩòóọỏõùúụủũỳýỵỷỹ]", language_text, re.I))
    _ensure_requested_teaching_devices(slides, requirements, vietnamese=vietnamese)
    return deck


def order_lecture_assessment_slides(structured_content: Dict[str, Any]) -> Dict[str, Any]:
    """Keep assessment after instruction while preserving all other narrative order."""
    if not isinstance(structured_content, dict):
        return structured_content
    if str(structured_content.get("presentation_mode") or "").strip().lower() != "lecture":
        return structured_content
    deck = copy.deepcopy(structured_content)
    slides = deck.get("slides") or []
    if len(slides) < 3:
        return deck
    first, body, last = slides[0], slides[1:-1], slides[-1]
    objectives = [
        slide for slide in body if isinstance(slide, dict)
        and str(slide.get("pedagogical_role") or "").strip().lower() == "learning_objectives"
    ]
    assessments = [
        slide for slide in body if isinstance(slide, dict)
        and str(slide.get("pedagogical_role") or "").strip().lower() in {"practice", "knowledge_check"}
    ]
    middle = [slide for slide in body if slide not in objectives and slide not in assessments]
    deck["slides"] = [first, *objectives, *middle, *assessments, last]
    return deck


def _slide_fulfills_requirement(slide: Dict[str, Any], requirement: str) -> bool:
    role = str(slide.get("pedagogical_role") or "").strip().lower()
    text = _fold(" ".join(
        [str(slide.get("title") or "")]
        + [str(item) for item in (slide.get("bullets") or [])]
    ))
    terms = _PEDAGOGICAL_REQUIREMENT_TERMS.get(requirement, ())
    if requirement == "worked_example" and role in {"worked_example", "demonstration"}:
        return True
    if requirement == "knowledge_check" and role == "knowledge_check":
        return "?" in str(slide.get("title") or "") or any(
            "?" in str(item) for item in (slide.get("bullets") or [])
        ) or any(term in text for term in terms)
    if requirement == "practice" and role == "practice":
        return True
    return any(term in text for term in terms)


def missing_instructional_requirements(
    structured_content: Dict[str, Any],
    user_instruction: str,
) -> List[str]:
    """Return unsatisfied requirements, assigning at most one device per slide."""
    slides = [slide for slide in (structured_content.get("slides") or []) if isinstance(slide, dict)]
    used: set[int] = set()
    missing: List[str] = []
    for requirement in instructional_requirements(user_instruction):
        match = next((
            index for index, slide in enumerate(slides)
            if index not in used and _slide_fulfills_requirement(slide, requirement)
        ), None)
        if match is None:
            missing.append(requirement)
        else:
            used.add(match)
    return missing


def _ensure_requested_teaching_devices(
    slides: List[Any],
    requirements: Sequence[str],
    *,
    vietnamese: bool,
) -> None:
    """Apply conservative fallbacks after AI review while preserving slide count."""
    missing = missing_instructional_requirements(
        {"slides": slides},
        " ".join(_PEDAGOGICAL_REQUIREMENT_TERMS[item][0] for item in requirements),
    )
    reserved: set[int] = set()
    for requirement in missing:
        candidate_index = next((
            index
            for index in range(len(slides) - 2, 0, -1)
            if index not in reserved
            and isinstance(slides[index], dict)
            and str(slides[index].get("pedagogical_role") or "").strip().lower()
            not in {"learning_objectives", "summary", "practice", "knowledge_check"}
            and str(slides[index].get("layout") or "").strip().lower()
            not in {"intro", "title", "thankyou", "thank_you"}
        ), None)
        if candidate_index is None:
            continue
        reserved.add(candidate_index)
        slide = slides[candidate_index]
        topic = str(slide.get("title") or "").strip()
        if requirement == "knowledge_check":
            slide["pedagogical_role"] = "knowledge_check"
            slide["title"] = "Câu hỏi kiểm tra cuối bài" if vietnamese else "Knowledge Check"
            slide["bullets"] = [
                f"Hãy giải thích ý chính của {topic.lower()}?" if vietnamese
                else f"What is the key idea behind {topic.lower()}?",
                f"Bạn sẽ vận dụng {topic.lower()} trong tình huống nào?" if vietnamese
                else f"When would you apply {topic.lower()}?",
            ]
        elif requirement == "worked_example":
            slide["pedagogical_role"] = "worked_example"
            slide["title"] = f"Ví dụ: {topic}" if vietnamese else f"Worked Example: {topic}"
        elif requirement == "common_mistakes":
            slide["pedagogical_role"] = "demonstration"
            slide["title"] = f"Lỗi thường gặp: {topic}" if vietnamese else f"Common Mistakes: {topic}"


def attach_source_page_provenance(
    structured_content: Dict[str, Any],
    source_text: str,
) -> Dict[str, Any]:
    """Attach source pages to any document-backed deck without changing content."""
    if not isinstance(structured_content, dict):
        return structured_content
    pages = _split_source_pages(source_text or "")
    if not pages:
        return structured_content
    deck = copy.deepcopy(structured_content)
    slides = deck.get("slides")
    if not isinstance(slides, list):
        return deck
    valid_pages = {page for page, _text in pages}
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        explicit = _normalize_page_numbers(slide.get("source_pages"), valid_pages=valid_pages)
        slide["source_pages"] = explicit or _match_source_pages(slide, pages)
    return deck


def select_relevant_source_excerpt(
    source_text: str,
    user_instruction: str = "",
    *,
    max_chars: int = 9000,
) -> str:
    """Choose source pages most relevant to the user's requested scope."""
    source = str(source_text or "")
    pages = _split_source_pages(source)
    folded_instruction = _fold(user_instruction)
    requested_chapter = re.search(
        r"\b(?:chapter|chuong)\s+(\d+)\b",
        folded_instruction,
    )
    if requested_chapter and pages:
        chapter_number = requested_chapter.group(1)
        active_chapter: Optional[str] = None
        chapter_pages: List[Tuple[int, str]] = []
        for page_number, page_text in pages:
            chapter_heading = re.search(
                r"\b(?:chapter|chuong)\s+(\d+)\b",
                _fold(page_text),
            )
            if chapter_heading:
                active_chapter = chapter_heading.group(1)
            if active_chapter == chapter_number:
                chapter_pages.append((page_number, page_text))
        if chapter_pages:
            parts: List[str] = []
            used = 0
            for page_number, page_text in chapter_pages:
                part = (
                    f"{SOURCE_PAGE_MARKER.format(page=page_number)}\n"
                    f"{page_text.strip()}"
                )
                if parts and used + len(part) > max_chars:
                    break
                if not parts and len(part) > max_chars:
                    part = part[:max_chars]
                parts.append(part)
                used += len(part)
            if parts:
                return "\n\n".join(parts)

    if len(source) <= max_chars:
        return source

    query_tokens = _tokens(user_instruction)
    if not pages or not query_tokens:
        return source[:max_chars]

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


def has_explicit_structural_scope(user_instruction: str) -> bool:
    """Return whether the request names a deterministic document boundary."""
    folded = _fold(user_instruction)
    return bool(
        re.search(
            r"\b(?:chapter|chuong|section|unit|module|lesson|bai|page|trang)"
            r"\s+\d+(?:\.\d+)*\b",
            folded,
        )
    )


def build_source_page_index(source_text: str, *, max_chars: int = 22000) -> str:
    """Build a compact, evenly sampled page index for semantic scope selection."""
    pages = _split_source_pages(source_text)
    if not pages:
        return ""
    preview_budget = max(140, min(520, max_chars // max(1, len(pages))))
    entries: List[str] = []
    used = 0
    for page_number, page_text in pages:
        compact = re.sub(r"\s+", " ", str(page_text or "")).strip()
        entry = f"PAGE {page_number}: {compact[:preview_budget]}"
        if entries and used + len(entry) + 1 > max_chars:
            break
        entries.append(entry)
        used += len(entry) + 1
    return "\n".join(entries)


def excerpt_from_source_pages(
    source_text: str,
    selected_pages: Sequence[int],
    *,
    max_chars: int = 30000,
    include_neighbors: bool = True,
) -> str:
    """Materialize an ordered source excerpt from an AI-selected page set."""
    pages = _split_source_pages(source_text)
    page_map = {page: text for page, text in pages}
    wanted = {int(page) for page in selected_pages if int(page) in page_map}
    if include_neighbors:
        for page in list(wanted):
            if page - 1 in page_map:
                wanted.add(page - 1)
            if page + 1 in page_map:
                wanted.add(page + 1)
    parts: List[str] = []
    used = 0
    ordered_pages = sorted(wanted)
    for index, page in enumerate(ordered_pages):
        part = f"{SOURCE_PAGE_MARKER.format(page=page)}\n{page_map[page].strip()}"
        remaining_pages = len(ordered_pages) - index
        remaining_budget = max(0, max_chars - used)
        fair_budget = max(160, remaining_budget // max(1, remaining_pages))
        if len(part) > fair_budget:
            part = part[:fair_budget].rstrip()
        parts.append(part)
        used += len(part)
    return "\n\n".join(parts)


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


def _fallback_learning_objectives(
    deck: Dict[str, Any],
    slides: Sequence[Dict[str, Any]],
    *,
    vietnamese: bool,
) -> List[str]:
    structural_terms = (
        "muc tieu",
        "learning objective",
        "tong ket",
        "ket luan",
        "summary",
        "conclusion",
        "bai tap",
        "thuc hanh",
        "practice",
        "exercise",
        "kiem tra",
        "knowledge check",
        "quiz",
    )
    topics: List[str] = []
    seen_topics: set[str] = set()
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        layout = str(slide.get("layout") or "").strip().lower()
        role = str(slide.get("pedagogical_role") or "").strip().lower()
        title = str(slide.get("title") or "").strip()
        folded = _fold(title)
        if (
            not title
            or layout in {"intro", "title", "thankyou", "thank_you"}
            or role in {"learning_objectives", "summary", "practice", "knowledge_check"}
            or any(term in folded for term in structural_terms)
            or folded in seen_topics
        ):
            continue
        topics.append(title)
        seen_topics.add(folded)
        if len(topics) >= 3:
            break

    if not topics:
        deck_title = str(deck.get("title") or "").strip()
        topics = [deck_title] if deck_title else []
    verbs = (
        ("Giải thích", "Phân tích", "Vận dụng kiến thức về")
        if vietnamese
        else ("Explain", "Analyze", "Apply knowledge of")
    )
    return [
        f"{verbs[index]} {topic[:1].lower() + topic[1:]}."
        for index, topic in enumerate(topics[:3])
        if topic
    ]


def _objectives_are_specific(objectives: Sequence[str], slides: Sequence[Dict[str, Any]]) -> bool:
    """Require objectives to name at least one real body-slide concept."""
    objective_tokens = _tokens(" ".join(str(item) for item in objectives))
    topic_tokens: set[str] = set()
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        role = str(slide.get("pedagogical_role") or "").strip().lower()
        layout = str(slide.get("layout") or "").strip().lower()
        if role in {"learning_objectives", "summary", "knowledge_check", "practice"}:
            continue
        if layout in {"intro", "title", "thankyou", "thank_you"}:
            continue
        topic_tokens.update(_tokens(str(slide.get("title") or "")))
    return bool(objective_tokens & topic_tokens) if topic_tokens else len(objectives) >= 2
