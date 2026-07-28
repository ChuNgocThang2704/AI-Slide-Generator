"""Kiểm tra chất lượng và tinh chỉnh giới hạn cho văn bản slide đã được tạo."""
from __future__ import annotations

import asyncio
import copy
import html
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.content.json_utils import parse_json_response

_DEBUG_DIR = Path("outputs") / "debug"
_GEMINI_REVIEW_ENABLE = os.getenv("TEXT_GEMINI_REVIEW_ENABLE", "true").lower() in ("1", "true", "yes")
_GEMINI_REVIEW_MAX_SLIDES = int(os.getenv("TEXT_GEMINI_REVIEW_MAX_SLIDES", "8"))
_SPEAKER_NOTES_REVIEW_MAX_SLIDES = int(os.getenv("SPEAKER_NOTES_REVIEW_MAX_SLIDES", "12"))


def _normalize_for_match(text: str) -> str:
    """Strip diacritics → lowercase để so sánh content-aware không phân biệt dấu."""
    nfd = unicodedata.normalize("NFD", str(text or ""))
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn").replace("đ", "d").replace("Đ", "D").lower()


def _title_is_truncated_bullet(title: str, bullets: List[str]) -> bool:
    """True nếu title là tiền tố bị cắt cụt (hoặc cắt dở từ) của một bullet.

    Giải quyết 2 kịch bản hoàn toàn sạch bóng từ cứng:
      1. Cắt dở từ cuối: "critic" vs "critical" (so khớp prefix của từ cuối).
      2. Cắt trọn từ nhưng là mảnh câu dài của bullet (độ dài >= 5 từ và là proper prefix).
    """
    title_words = re.findall(r"[\w\u00C0-\u1EF9]+", _normalize_for_match(title))
    if len(title_words) < 3:
        return False

    for bullet in (bullets or []):
        b_words = re.findall(r"[\w\u00C0-\u1EF9]+", _normalize_for_match(str(bullet or "")))
        if len(b_words) < len(title_words):
            continue

        # Kiểm tra xem tất cả các từ trước từ cuối cùng có khớp hoàn toàn không
        slice_len = len(title_words)
        match_all_except_last = True
        for i in range(slice_len - 1):
            if title_words[i] != b_words[i]:
                match_all_except_last = False
                break

        if match_all_except_last:
            last_title_word = title_words[-1]
            last_bullet_word = b_words[slice_len - 1]

            # Kịch bản 1: Trùng khít hoàn toàn tiền tố
            if last_title_word == last_bullet_word:
                # Nếu nó là proper prefix (bullet còn các từ tiếp theo phía sau)
                # và độ dài của phần trùng khớp này >= 5 từ -> chắc chắn là mảnh câu bị copy cụt
                if len(b_words) > slice_len and slice_len >= 5:
                    normalized_title = re.sub(r"\s+", " ", _normalize_for_match(title)).strip()
                    normalized_bullet = re.sub(r"\s+", " ", _normalize_for_match(str(bullet or ""))).strip()
                    if normalized_bullet.startswith(normalized_title):
                        remainder = normalized_bullet[len(normalized_title):].lstrip()
                        # Một mệnh đề kết thúc ngay trước dấu ngắt có thể là title hoàn chỉnh.
                        if remainder.startswith((",", ";", ":", "-", "–", "—")):
                            continue
                        semantic_extensions = (
                            "trong ", "voi ", "nham ", "de ", "thong qua ", "tu do ",
                            "in ", "with ", "through ", "to ", "for ",
                        )
                        dangling_tail = {"doi", "thuoc", "giua", "between", "according"}
                        if remainder.startswith(semantic_extensions) and last_title_word not in dangling_tail:
                            continue
                    return True
            # Kịch bản 2: Từ cuối của tiêu đề bị cắt dở (ví dụ: critic là tiền tố của critical)
            elif last_bullet_word.startswith(last_title_word) and len(last_title_word) >= 2:
                return True
    return False


_VN_DIACRITIC_RE = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]"
)
_EN_FUNCTION_RE = re.compile(
    r"\b(the|and|or|of|for|with|to|from|in|on|at|by|as|is|are|was|were|be|been|being|this|that|these|those|which|will|can|should|would|could)\b",
    re.IGNORECASE,
)
_VN_DIACRITIC_SAFE_RE = re.compile(
    "["
    "\u00e0\u00e1\u1ea3\u00e3\u1ea1"
    "\u0103\u1eb1\u1eaf\u1eb3\u1eb5\u1eb7"
    "\u00e2\u1ea7\u1ea5\u1ea9\u1eab\u1ead"
    "\u00e8\u00e9\u1ebb\u1ebd\u1eb9"
    "\u00ea\u1ec1\u1ebf\u1ec3\u1ec5\u1ec7"
    "\u00ec\u00ed\u1ec9\u0129\u1ecb"
    "\u00f2\u00f3\u1ecf\u00f5\u1ecd"
    "\u00f4\u1ed3\u1ed1\u1ed5\u1ed7\u1ed9"
    "\u01a1\u1edd\u1edb\u1edf\u1ee1\u1ee3"
    "\u00f9\u00fa\u1ee7\u0169\u1ee5"
    "\u01b0\u1eeb\u1ee9\u1eed\u1eef\u1ef1"
    "\u1ef3\u00fd\u1ef7\u1ef9\u1ef5"
    "\u0111\u0110"
    "]",
    re.IGNORECASE,
)


def _words(text: str) -> List[str]:
    return re.findall(r"[\wÀ-ỹ-]+", text or "", flags=re.UNICODE)


def _clean_json_text(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _sanitize_inline_markup(text: str) -> str:
    """Chuẩn hóa bất kỳ văn bản slide nào do AI viết thành văn bản thuần túy."""
    if text is None:
        return ""
    t = unicodedata.normalize("NFKC", html.unescape(str(text))).strip()
    if not t:
        return ""
    t = t.translate(str.maketrans({
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
    }))
    t = re.sub(r"<[^>\n]{1,80}>", " ", t)
    t = re.sub(r"[•◦▪▫■□●○◆◇★☆✓✔✗✘➜→←↑↓↔]", " ", t)
    cleaned_chars: List[str] = []
    symbol_keep = set("$€£¥₫%‰+-=<>±×÷°")
    for ch in t:
        if ch == "\ufffd":
            continue
        cat = unicodedata.category(ch)
        if cat[0] == "C":
            cleaned_chars.append(" ")
            continue
        if cat[0] == "S" and ch not in symbol_keep:
            cleaned_chars.append(" ")
            continue
        cleaned_chars.append(ch)
    t = "".join(cleaned_chars)
    t = re.sub(r"^\s*(?:[-+*]|•)\s+", "", t)
    t = re.sub(r"^\s*\*+", "", t)
    # Preserve programming operators and identifiers (`*`, `**`, `_`,
    # `__init__`). Removing Markdown markers here corrupted technical slides.
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def _sanitize_structured_text(structured: Dict[str, Any]) -> Dict[str, Any]:
    """Áp dụng quy tắc văn bản thuần túy cho mọi trường văn bản hiển thị với người dùng."""
    if not isinstance(structured, dict):
        return structured
    if isinstance(structured.get("title"), str):
        structured["title"] = _sanitize_inline_markup(structured["title"])
    slides = structured.get("slides") or []
    if not isinstance(slides, list):
        return structured
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        if isinstance(slide.get("title"), str):
            slide["title"] = _sanitize_inline_markup(slide["title"])
        bullets = slide.get("bullets") or slide.get("content") or []
        if isinstance(bullets, str):
            clean_bullets = [_sanitize_inline_markup(bullets)]
        elif isinstance(bullets, list):
            clean_bullets = [_sanitize_inline_markup(b) for b in bullets if _sanitize_inline_markup(b)]
        else:
            clean_bullets = []
        if clean_bullets:
            slide["bullets"] = clean_bullets
        notes = _sanitize_inline_markup(slide.get("notes") or slide.get("script") or "")
        if notes:
            slide["notes"] = notes
    return structured


def _is_suspicious_title(title: str, bullets: Optional[List[str]] = None) -> bool:
    """True nếu title có dấu hiệu bị cắt cụt hoặc không hoàn chỉnh.

    Chỉ dùng 2 loại kiểm tra, cả 2 đều không hardcode từ nào:
      1. Quy tắc cấu trúc: rỗng, quá ngắn (<3 từ), quá dài (>14 từ),
         kết thúc bằng dấu câu gây gián đoạn.
      2. Content-aware: title là tiền tố chính xác của một bullet
         → chắc chắn bị cắt, khữi quan tâm từ cuối là gì.
    Gemini review là final gate cho mọi trường hợp còn lại.
    """
    t = re.sub(r"\s+", " ", str(title or "").strip())
    if not t:
        return True
    tokens = _words(t.lower())
    if len(tokens) < 3:
        return True
    if len(tokens) > 14:
        return True
    if re.search(r"[,;:/\\\-\u2013\u2014]\s*$", t):
        return True
    if bullets and _title_is_truncated_bullet(t, bullets):
        return True
    return False


def _looks_corrupted_text(text: str) -> bool:
    t = str(text or "")
    if "\ufffd" in t:
        return True
    return t.count("?") >= 2


def _norm_title_key(title: str) -> str:
    return re.sub(r"\W+", " ", str(title or "").lower()).strip()


def _candidate_title_from_text(text: str) -> str:
    t = re.sub(r"^\s*(?:[-*•]|\d+[\).:-])\s*", "", str(text or "")).strip()
    if not t:
        return ""
    if ":" in t and t.find(":") <= 48:
        t = t.split(":", 1)[0].strip()
    else:
        first_clause = re.split(r"[.;!?]", t, maxsplit=1)[0].strip()
        comma_clause = first_clause.split(",", 1)[0].strip()
        if len(_words(comma_clause)) >= 4:
            first_clause = comma_clause
        for sep in (" với ", " nhằm ", " để ", " trong ", " thông qua ", " từ đó "):
            left = first_clause.split(sep, 1)[0].strip()
            if left != first_clause and len(_words(left)) >= 5:
                first_clause = left
                break
        t = first_clause
    return t.strip(".,;:!-–—\"' ")[:120]


def _derive_title_from_bullets(
    bullets: List[Any],
    fallback: str,
    *,
    seen: Optional[set[str]] = None,
) -> str:
    seen = seen or set()
    fallback_clean = str(fallback or "").strip()
    bullet_texts = [str(raw or "") for raw in (bullets or [])]
    for raw in bullet_texts:
        cand = _candidate_title_from_text(str(raw or ""))
        key = _norm_title_key(cand)
        if (
            len(_words(cand)) >= 3
            and key
            and key not in seen
            and not _is_suspicious_title(cand, bullets=bullet_texts)
        ):
            return cand
    return fallback_clean[:120]


def _repair_titles_after_review(structured: Dict[str, Any]) -> List[int]:
    slides = structured.get("slides") or []
    if not isinstance(slides, list):
        return []
    changed: List[int] = []
    seen: set[str] = set()
    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        title = str(slide.get("title") or "").strip()
        key = _norm_title_key(title)
        bullets_list = slide.get("bullets") or slide.get("content") or []
        needs_fix = not key or key in seen or _is_suspicious_title(title, bullets=bullets_list)
        if needs_fix:
            new_title = _derive_title_from_bullets(
                slide.get("bullets") or slide.get("content") or [],
                fallback=title or "Nội dung chính",
                seen=seen,
            )
            new_key = _norm_title_key(new_title)
            if new_key and new_key not in seen and new_title != title:
                slide["title"] = new_title
                title = new_title
                key = new_key
                changed.append(idx)
        if key:
            seen.add(key)
    return changed


def _key_terms(text: str, limit: int = 8) -> List[str]:
    out: List[str] = []
    for token in _words((text or "").lower()):
        t = token.strip("-_")
        # Lọc các từ quá ngắn (len < 4) tự động loại bỏ hầu hết các từ nối/từ dừng (và, của, cho, and, the, for...)
        if len(t) < 4 or t.isdigit():
            continue
        if t not in out:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def _language_instruction(source_language: str) -> str:
    lang = (source_language or "auto").strip().lower()
    if lang == "vi":
        return (
            "TARGET LANGUAGE (MANDATORY): Vietnamese. Rewrite all deck titles, slide titles, bullets, "
            "speaker scripts, and notes in Vietnamese. Keep proper names, brand names, model names, and "
            "technical acronyms unchanged when natural. Do not switch to English."
        )
    if lang == "en":
        return (
            "TARGET LANGUAGE (MANDATORY): English. Rewrite all deck titles, slide titles, bullets, "
            "speaker scripts, and notes in English. Keep proper names and technical acronyms unchanged."
        )
    return "TARGET LANGUAGE: Use the dominant source language consistently across the deck."


def _detect_language_issues(slide: Dict[str, Any], source_language: str) -> List[str]:
    lang = (source_language or "auto").strip().lower()
    if lang not in {"vi", "en"}:
        return []
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        bullets_text = bullets
    else:
        bullets_text = " ".join(str(b) for b in bullets[:6])
    text = " ".join(
        [
            str(slide.get("title") or ""),
            bullets_text,
            str(slide.get("script") or slide.get("notes") or ""),
        ]
    ).strip()
    if len(text) < 80:
        return []
    words = _words(text)
    if len(words) < 14:
        return []
    vn_hits = len(_VN_DIACRITIC_SAFE_RE.findall(text))
    en_function_hits = len(_EN_FUNCTION_RE.findall(text))
    if lang == "vi":
        # Một bài thuyết trình tiếng Việt có thể chứa các tên thương hiệu/thuật ngữ kỹ thuật, nhưng một đoạn văn dài
        # không có dấu tiếng Việt và chứa nhiều hư từ tiếng Anh thì có khả năng là bị lệch ngôn ngữ.
        if vn_hits < 2 and en_function_hits >= 5:
            return ["language_mismatch_vi"]
    elif lang == "en":
        if vn_hits >= 8 and en_function_hits <= 3:
            return ["language_mismatch_en"]
    return []


def _score_slide_text(slide: Dict[str, Any], source_language: str = "auto") -> Tuple[float, List[str]]:
    issues: List[str] = []
    title = str(slide.get("title") or "").strip()
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        bullets = [bullets]
    bullets = [str(b).strip() for b in bullets if str(b).strip()]

    score = 1.0
    if len(_words(title)) < 2:
        score -= 0.15
        issues.append("weak_title")
    if _is_suspicious_title(title, bullets=bullets):
        score -= 0.16
        issues.append("suspicious_title")
    if len(bullets) < 3:
        score -= 0.25
        issues.append("too_few_bullets")
    if len(bullets) > 6:
        score -= 0.1
        issues.append("too_many_bullets")

    language_issues = _detect_language_issues(slide, source_language)
    if language_issues:
        score -= 0.28
        issues.extend(language_issues)

    note_issues = _speaker_note_issues(slide)
    if note_issues:
        score -= min(0.24, 0.08 * len(note_issues))
        issues.extend(note_issues)

    seen = set()
    has_structured_visual = isinstance(slide.get("table"), dict) or isinstance(slide.get("chart"), dict)
    for idx, bullet in enumerate(bullets):
        wc = len(_words(bullet))
        key = re.sub(r"\W+", " ", bullet.lower()).strip()
        if wc < 6 and not has_structured_visual:
            score -= 0.08
            issues.append(f"short_bullet_{idx}")
        if wc > 32:
            score -= 0.08
            issues.append(f"long_bullet_{idx}")
        if bullet.endswith(("...", "…", ",", ";", ":", "-", "–", "—")):
            score -= 0.12
            issues.append(f"incomplete_bullet_{idx}")
        if key and key in seen:
            score -= 0.08
            issues.append(f"duplicate_bullet_{idx}")
        seen.add(key)

    return max(0.0, round(score, 3)), issues[:10]


def _evaluate_deck(structured: Dict[str, Any], source_language: str = "auto") -> List[Dict[str, Any]]:
    slides = structured.get("slides") or []
    records: List[Dict[str, Any]] = []
    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        score, issues = _score_slide_text(slide, source_language=source_language)
        records.append(
            {
                "slide_index": idx,
                "title": str(slide.get("title") or ""),
                "score": score,
                "issues": issues,
                "bullet_count": len(slide.get("bullets") or slide.get("content") or []),
            }
        )
    _apply_deck_consistency(structured, records)
    return records


def _apply_deck_consistency(structured: Dict[str, Any], records: List[Dict[str, Any]]) -> None:
    """Kiểm tra tính nhất quán ở cấp độ deck-level một cách nhanh chóng không cần thêm cuộc gọi LLM."""
    if not records:
        return

    deck_terms = _key_terms(str(structured.get("title") or ""), limit=10)
    seen_titles = {}
    for rec in records:
        title = str(rec.get("title") or "")
        score = float(rec.get("score") or 0.0)
        issues = list(rec.get("issues") or [])

        title_terms = _key_terms(title, limit=6)
        if deck_terms and title_terms:
            overlap = len(set(deck_terms) & set(title_terms)) / max(1, len(set(title_terms)))
            if overlap < 0.2:
                score -= 0.06
                issues.append("off_topic_title")

        normalized = re.sub(r"\W+", " ", title.lower()).strip()
        if normalized:
            seen_titles[normalized] = seen_titles.get(normalized, 0) + 1
            if seen_titles[normalized] > 1:
                score -= 0.08
                issues.append("duplicate_slide_title")

        rec["score"] = max(0.0, round(score, 3))
        rec["issues"] = issues[:12]


def _write_text_quality_report(
    task_id: str,
    records: List[Dict[str, Any]],
    refined: List[int],
    source_language: str = "auto",
) -> None:
    if not task_id:
        return
    try:
        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        scores = [float(r.get("score") or 0.0) for r in records]
        consistency_flags = {
            "off_topic_title": sum(1 for r in records if "off_topic_title" in (r.get("issues") or [])),
            "duplicate_slide_title": sum(
                1 for r in records if "duplicate_slide_title" in (r.get("issues") or [])
            ),
        }
        report = {
            "task_id": task_id,
            "source_language": source_language,
            "slide_count": len(records),
            "avg_score": round(sum(scores) / len(scores), 3) if scores else None,
            "low_quality_count": sum(1 for s in scores if s < 0.72),
            "refined_slide_indices": refined,
            "consistency_flags": consistency_flags,
            "records": records,
        }
        path = _DEBUG_DIR / f"{task_id}_text_quality.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[slide_text_quality] quality report: {path}")
    except Exception as e:
        print(f"[slide_text_quality] quality report error: {e}")


def write_final_text_quality_report(
    structured: Dict[str, Any],
    *,
    task_id: str,
    source_language: str = "auto",
) -> List[Dict[str, Any]]:
    """Evaluate the exact final JSON and overwrite any earlier interim report."""
    records = _evaluate_deck(structured, source_language=source_language)
    _write_text_quality_report(task_id, records, [], source_language=source_language)
    return records


def _slide_subset_for_review(structured: Dict[str, Any], records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    slides = structured.get("slides") or []
    selected: List[Dict[str, Any]] = []
    for rec in records:
        idx = int(rec.get("slide_index") or 0)
        if idx >= len(slides) or not isinstance(slides[idx], dict):
            continue
        issues = set(rec.get("issues") or [])
        score = float(rec.get("score") or 0.0)
        non_note_issues = {issue for issue in issues if not str(issue).startswith("speaker_notes_")}
        if issues and not non_note_issues:
            continue
        if score >= 0.88 and not (issues & {"suspicious_title", "duplicate_slide_title", "language_mismatch_vi", "language_mismatch_en"}):
            continue
        slide = slides[idx]
        selected.append(
            {
                "index": idx,
                "title": str(slide.get("title") or ""),
                "bullets": [str(x) for x in (slide.get("bullets") or slide.get("content") or [])],
                "script": str(slide.get("script") or slide.get("notes") or ""),
                "issues": sorted(issues),
            }
        )
        if len(selected) >= max(1, _GEMINI_REVIEW_MAX_SLIDES):
            break
    return selected


def _slide_bullets_preview(slide: Dict[str, Any], limit: int = 4) -> List[str]:
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        return [bullets]
    if isinstance(bullets, list):
        return [str(x) for x in bullets[:limit] if str(x).strip()]
    return []


_NOTE_META_RE = re.compile(
    r"\b(?:slide|trang)\s+(?:này|nay)\s+(?:giới\s+thiệu|gioi\s+thieu|trình\s+bày|trinh\s+bay|mô\s+tả|mo\s+ta|tóm\s+tắt|tom\s+tat|nhấn\s+mạnh|nhan\s+manh)\b"
    r"|\bthis\s+slide\s+(?:introduces|presents|describes|summarizes|highlights)\b",
    flags=re.IGNORECASE,
)


def _speaker_note_issues(slide: Dict[str, Any]) -> List[str]:
    notes = str(slide.get("notes") or slide.get("script") or "").strip()
    bullets = _slide_bullets_preview(slide, limit=6)
    source = " ".join([str(slide.get("title") or "")] + bullets)
    issues: List[str] = []
    word_count = len(_words(notes))
    if word_count < 65:
        issues.append("speaker_notes_too_short")
    elif word_count > 130:
        issues.append("speaker_notes_too_long")
    if _NOTE_META_RE.search(notes):
        issues.append("speaker_notes_meta_description")
    folded_notes = re.sub(r"\W+", " ", notes.lower()).strip()
    for bullet in bullets:
        folded_bullet = re.sub(r"\W+", " ", bullet.lower()).strip()
        if len(_words(folded_bullet)) >= 8 and folded_bullet in folded_notes:
            issues.append("speaker_notes_copy_bullets")
            break
    source_terms = set(_key_terms(source, limit=12))
    note_terms = set(_key_terms(notes, limit=20))
    if source_terms and len(source_terms & note_terms) < min(2, len(source_terms)):
        issues.append("speaker_notes_weak_grounding")
    return issues


def _ground_and_trim_speaker_notes(notes: str, source: str, max_words: int = 125) -> str:
    source_folded = unicodedata.normalize("NFKD", str(source or ""))
    source_folded = "".join(ch for ch in source_folded if not unicodedata.combining(ch)).lower()
    speculative_patterns = (
        r"\bchung toi tin\b",
        r"\btrong tuong lai\b",
        r"\bse tiep tuc mang lai\b",
        r"\bhua hen\b",
        r"\bben vung\b",
        r"\bwe believe\b",
        r"\bin the future\b",
        r"\bwill continue to deliver\b",
        r"\bpromises to\b",
        r"\bsustainable\b",
    )
    sentences = re.split(r"(?<=[.!?])\s+", _sanitize_inline_markup(notes))
    kept: List[str] = []
    word_count = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        folded = unicodedata.normalize("NFKD", sentence)
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch)).lower()
        if any(re.search(pattern, folded) and not re.search(pattern, source_folded) for pattern in speculative_patterns):
            continue
        sentence_words = len(_words(sentence))
        if kept and word_count + sentence_words > max_words:
            break
        kept.append(sentence)
        word_count += sentence_words
    return " ".join(kept).strip()


async def _review_speaker_notes(
    content_extractor,
    structured: Dict[str, Any],
    *,
    source_language: str = "auto",
    provider: str = "auto",
) -> Tuple[Dict[str, Any], List[int]]:
    if not _GEMINI_REVIEW_ENABLE:
        return structured, []
    if not hasattr(content_extractor, "_llm_completion_plain_text"):
        return structured, []

    slides = structured.get("slides") or []
    review_items: List[Dict[str, Any]] = []
    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        issues = _speaker_note_issues(slide)
        if not issues:
            continue
        review_items.append(
            {
                "index": idx,
                "title": str(slide.get("title") or ""),
                "bullets": _slide_bullets_preview(slide, limit=6),
                "table": slide.get("table"),
                "chart": slide.get("chart"),
                "current_notes": str(slide.get("notes") or slide.get("script") or ""),
                "next_slide_title": (
                    str((slides[idx + 1] or {}).get("title") or "")
                    if idx + 1 < len(slides) and isinstance(slides[idx + 1], dict)
                    else ""
                ),
                "issues": issues,
            }
        )
        if len(review_items) >= max(1, _SPEAKER_NOTES_REVIEW_MAX_SLIDES):
            break
    if not review_items:
        return structured, []

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert presentation speechwriter. Rewrite only the speaker notes.\n"
                f"{_language_instruction(source_language)}\n"
                "For each slide, write 70-120 words of natural narration that a presenter can speak directly. "
                "Use only facts, numbers, names, and claims supported by that slide's title, bullets, table, or chart. "
                "Do not invent examples, statistics, causes, or conclusions. Explain the meaning and relationship of the provided points instead of reading bullets verbatim. "
                "Never say 'Slide này giới thiệu/trình bày/mô tả' or 'This slide presents/introduces'. "
                "When next_slide_title is provided, finish with one short natural bridge to that idea without mentioning slide numbers. "
                "For the final slide, end with a concise closing thought. Plain text only, no Markdown.\n"
                "Return strict JSON only: {\"slides\":[{\"index\":number,\"notes\":string}]}"
            ),
        },
        {"role": "user", "content": json.dumps({"slides": review_items}, ensure_ascii=False)},
    ]
    try:
        raw = await content_extractor._llm_completion_plain_text(
            messages,
            max_tokens=min(6000, 700 + 450 * len(review_items)),
            temperature=0.2,
            json_mode=True,
            provider=provider,
        )
        parsed = parse_json_response(raw, clean_result_text=_clean_json_text)
    except Exception as e:
        print(f"[slide_text_quality] speaker notes review failed: {e}")
        return structured, []

    out_items = (parsed or {}).get("slides") if isinstance(parsed, dict) else None
    if not isinstance(out_items, list):
        return structured, []
    improved = copy.deepcopy(structured)
    improved_slides = improved.get("slides") or []
    changed: List[int] = []
    for item in out_items:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("index"))
        except Exception:
            continue
        if not (0 <= idx < len(improved_slides)) or not isinstance(improved_slides[idx], dict):
            continue
        source = " ".join(
            [str(improved_slides[idx].get("title") or "")]
            + _slide_bullets_preview(improved_slides[idx], limit=6)
            + [
                json.dumps(improved_slides[idx].get("table") or {}, ensure_ascii=False),
                json.dumps(improved_slides[idx].get("chart") or {}, ensure_ascii=False),
            ]
        )
        notes = _ground_and_trim_speaker_notes(item.get("notes") or "", source)
        if len(_words(notes)) < 50 or len(_words(notes)) > 130 or _NOTE_META_RE.search(notes):
            continue
        source_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", source))
        note_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", notes))
        if note_numbers - source_numbers:
            continue
        improved_slides[idx]["notes"] = notes
        changed.append(idx)
    return improved, changed


async def improve_speaker_notes_quality(
    content_extractor,
    structured: Dict[str, Any],
    *,
    source_language: str = "auto",
) -> Dict[str, Any]:
    """Re-run the notes-only QA after any downstream step that may rewrite slide text."""
    improved, changed = await _review_speaker_notes(
        content_extractor,
        structured,
        source_language=source_language,
    )
    if changed:
        print(f"[slide_text_quality] downstream speaker notes refined slides: {changed}")
    return _sanitize_structured_text(improved)


async def improve_final_slide_quality(
    content_extractor,
    structured: Dict[str, Any],
    *,
    task_id: str = "",
    source_language: str = "auto",
) -> Dict[str, Any]:
    """Run semantic QA against the exact deck that will be returned to clients."""
    if not isinstance(structured, dict):
        return structured

    improved = copy.deepcopy(structured)
    slides = improved.get("slides") or []
    # Force every final slide through semantic QA. Mechanical scoring alone cannot
    # reliably identify a grammatically incomplete sentence ending in a period.
    records = [
        {
            "slide_index": idx,
            "score": 0.0,
            "issues": ["final_semantic_review"],
        }
        for idx, slide in enumerate(slides)
        if isinstance(slide, dict)
    ]
    batch_size = max(1, _GEMINI_REVIEW_MAX_SLIDES)
    for start in range(0, len(records), batch_size):
        try:
            improved, _ = await _review_slide_text(
                content_extractor,
                improved,
                records[start : start + batch_size],
                source_language=source_language,
            )
        except Exception as e:
            print(f"[slide_text_quality] final semantic review failed: {e}")

    improved, _ = await _review_and_repair_titles(
        content_extractor,
        improved,
        source_language=source_language,
    )
    try:
        improved, _ = await _review_speaker_notes(
            content_extractor,
            improved,
            source_language=source_language,
        )
    except Exception as e:
        print(f"[slide_text_quality] final notes review failed: {e}")

    improved = _sanitize_structured_text(improved)
    write_final_text_quality_report(
        improved,
        task_id=task_id,
        source_language=source_language,
    )
    return improved


def _valid_review_slide(item: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    try:
        idx = int(item.get("index"))
    except Exception:
        return None
    title = _sanitize_inline_markup(item.get("title") or "")
    bullets = item.get("bullets")
    if not title or not isinstance(bullets, list):
        return None
    if _looks_corrupted_text(title):
        return None
    clean_bullets = [_sanitize_inline_markup(b) for b in bullets if _sanitize_inline_markup(b)]
    if any(_looks_corrupted_text(b) for b in clean_bullets):
        return None
    if len(clean_bullets) < 2:
        return None
    return {
        "index": idx,
        "title": title[:120],
        "bullets": clean_bullets[:6],
        "script": _sanitize_inline_markup(item.get("script") or ""),
    }


async def _review_slide_text(
    content_extractor,
    structured: Dict[str, Any],
    records: List[Dict[str, Any]],
    source_language: str = "auto",
    provider: str = "auto",
) -> Tuple[Dict[str, Any], List[int]]:
    """Yêu cầu Gemini đánh giá các slide yếu/bị cắt cụt với tư cách là một người phản biện độc lập."""
    if not _GEMINI_REVIEW_ENABLE:
        return structured, []
    if not hasattr(content_extractor, "_llm_completion_plain_text"):
        return structured, []

    review_items = _slide_subset_for_review(structured, records)
    if not review_items:
        return structured, []

    payload = {
        "deck_title": str(structured.get("title") or ""),
        "source_language": source_language,
        "slides": review_items,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are a strict presentation text QA reviewer.\n"
                "Fix only mechanical text-quality problems: cut-off titles, incomplete bullets, repeated wording, "
                "obvious table-like prose mistakes, and speaker script mismatch.\n"
                f"{_language_instruction(source_language)}\n"
                "All returned title, bullet, and script fields must be plain text only: no Markdown, no bold/italic markers, no list markers.\n"
                "Do not add new facts. Preserve the original meaning.\n"
                "Return strict JSON only: {\"slides\":[{\"index\":number,\"title\":string,\"bullets\":[string],\"script\":string,\"issues\":[string]}]}."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]

    try:
        raw = await content_extractor._llm_completion_plain_text(
            messages,
            max_tokens=1800,
            temperature=0.15,
            json_mode=True,
            provider=provider,
        )
        parsed = parse_json_response(raw, clean_result_text=_clean_json_text)
    except Exception as e:
        print(f"[slide_text_quality] Gemini review failed: {e}")
        return structured, []

    out_items = (parsed or {}).get("slides") if isinstance(parsed, dict) else None
    if not isinstance(out_items, list):
        return structured, []

    improved = copy.deepcopy(structured)
    slides = improved.get("slides") or []
    changed: List[int] = []
    for raw_item in out_items:
        item = _valid_review_slide(raw_item)
        if not item:
            continue
        idx = item["index"]
        if idx < 0 or idx >= len(slides) or not isinstance(slides[idx], dict):
            continue
        old = slides[idx]
        old_bullets = [str(b or "").strip() for b in (old.get("bullets") or old.get("content") or []) if str(b or "").strip()]
        if old_bullets and len(item["bullets"]) < max(2, min(len(old_bullets), 3)):
            continue
        slides[idx]["title"] = item["title"]
        slides[idx]["bullets"] = item["bullets"]
        if item.get("script") or item.get("notes"):
            slides[idx]["notes"] = item.get("script") or item.get("notes")
        changed.append(idx)

    return _sanitize_structured_text(improved), changed


def _valid_title_decision(item: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    try:
        idx = int(item.get("index"))
    except Exception:
        return None
    fixed = _sanitize_inline_markup(item.get("fixed_title") or item.get("title") or "")
    if not fixed or len(fixed) > 160 or _looks_corrupted_text(fixed):
        return None
    return {
        "index": idx,
        "pass": bool(item.get("pass")),
        "fixed_title": fixed,
        "reason": str(item.get("reason") or "").strip()[:200],
    }


async def _review_and_repair_titles(
    content_extractor,
    structured: Dict[str, Any],
    source_language: str = "auto",
    provider: str = "auto",
) -> Tuple[Dict[str, Any], List[int]]:
    """Sử dụng Gemini như một người phản biện tiêu đề theo ngữ nghĩa cho toàn bộ bài thuyết trình.

    Điều này giúp tránh các cách sửa lỗi thô cứng dựa trên danh sách từ đối với các tiêu đề chưa hoàn chỉnh như
    danh từ riêng hoặc cụm từ kỹ thuật bị cắt làm đôi. Giải pháp sửa lỗi dự phòng xác định (deterministic)
    vẫn khả dụng khi Gemini không được định cấu hình hoặc gặp lỗi.
    """
    if not _GEMINI_REVIEW_ENABLE:
        return structured, []
    if not hasattr(content_extractor, "_llm_completion_plain_text"):
        return structured, []

    slides = structured.get("slides") or []
    if not isinstance(slides, list) or not slides:
        return structured, []

    slide_records = [
        {
            "index": idx,
            "title": str(slide.get("title") or "").strip(),
            "bullets": _slide_bullets_preview(slide),
            "table": slide.get("table"),
            "chart": slide.get("chart"),
        }
        for idx, slide in enumerate(slides)
        if isinstance(slide, dict)
    ]

    # Chia nhỏ slide thành từng cụm (tối đa 5 slide/cụm) để đảm bảo độ tập trung của LLM
    # và không bao giờ lo bị tràn giới hạn đầu ra (max_tokens).
    chunk_size = 5
    chunks = [slide_records[i : i + chunk_size] for i in range(0, len(slide_records), chunk_size)]

    async def _review_chunk(chunk_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        payload = {
            "deck_title": str(structured.get("title") or ""),
            "source_language": source_language,
            "slides": chunk_items,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict slide-title QA reviewer.\n"
                    "Review every title for semantic completeness, uniqueness, and fit to its bullets, table, or chart.\n"
                    "A title must be a complete phrase, not a cut-off fragment, not a dangling prepositional phrase, "
                    "not the first half of a proper noun or technical term, and not duplicated from another slide unless the content is truly identical.\n"
                    "If a title is already complete and unique, keep it exactly.\n"
                    "If it is incomplete, duplicated, too vague, too narrow for the full table/chart, or mismatched, rewrite only the title using the provided slide content.\n"
                    f"{_language_instruction(source_language)}\n"
                    "Return plain text titles only: no Markdown, no bold/italic markers, no list markers.\n"
                    "Do not add new facts. Prefer concise titles of 4-12 words.\n"
                    "Return strict JSON only: {\"titles\":[{\"index\":number,\"pass\":boolean,\"fixed_title\":string,\"reason\":string}]}."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        try:
            raw = await content_extractor._llm_completion_plain_text(
                messages,
                max_tokens=800,  # 800 tokens là quá đủ cho 5 slide titles
                temperature=0.05,
                json_mode=True,
                provider=provider,
            )
            parsed = parse_json_response(raw, clean_result_text=_clean_json_text)
            decisions = (parsed or {}).get("titles") if isinstance(parsed, dict) else None
            if isinstance(decisions, list):
                return decisions
        except Exception as e:
            print(f"[slide_text_quality] Gemini title review chunk failed: {e}")
        return []

    # Gọi song song tất cả các cụm bằng asyncio.gather
    tasks = [_review_chunk(chunk) for chunk in chunks]
    chunk_results = await asyncio.gather(*tasks, return_exceptions=True)

    decisions: List[Dict[str, Any]] = []
    for res in chunk_results:
        if isinstance(res, list):
            decisions.extend(res)

    if not decisions:
        return structured, []

    improved = copy.deepcopy(structured)
    out_slides = improved.get("slides") or []
    changed: List[int] = []
    seen: set[str] = set()
    for raw_item in decisions:
        item = _valid_title_decision(raw_item)
        if not item:
            continue
        idx = item["index"]
        if idx < 0 or idx >= len(out_slides) or not isinstance(out_slides[idx], dict):
            continue
        current = str(out_slides[idx].get("title") or "").strip()
        fixed = item["fixed_title"]
        key = _norm_title_key(fixed)
        slide_bullets = out_slides[idx].get("bullets") or out_slides[idx].get("content") or []
        if not key or key in seen or _is_suspicious_title(fixed, bullets=slide_bullets):
            current_key = _norm_title_key(current)
            if current_key:
                seen.add(current_key)
            continue
        if key and key not in seen:
            if fixed != current:
                out_slides[idx]["title"] = fixed
                changed.append(idx)
            seen.add(key)

    # Bắt bất kỳ slide nào bị Gemini bỏ sót hoặc tiêu đề trùng lặp do mô hình tạo ra.
    return _sanitize_structured_text(improved), sorted(set(changed))


async def improve_slide_titles_quality(
    content_extractor,
    structured: Dict[str, Any],
    *,
    source_language: str = "auto",
) -> Dict[str, Any]:
    """Re-run title-only QA after downstream stages that may rewrite slide text."""
    improved, changed = await _review_and_repair_titles(
        content_extractor,
        structured,
        source_language=source_language,
    )
    if changed:
        print(f"[slide_text_quality] downstream titles refined slides: {changed}")
    return _sanitize_structured_text(improved)


async def improve_slide_text_quality(
    content_extractor,
    structured: Dict[str, Any],
    *,
    task_id: str = "",
    max_refines: int = 3,
    source_language: str = "auto",
) -> Dict[str, Any]:
    """Đánh giá văn bản slide và làm bóng (polish) tối đa một vài slide yếu."""
    if not isinstance(structured, dict):
        return structured

    source_language = (source_language or getattr(content_extractor, "_slide_lang_hint", "auto") or "auto").strip().lower()
    improved = copy.deepcopy(structured)
    improved = _sanitize_structured_text(improved)
    before = _evaluate_deck(improved, source_language=source_language)
    weak = [r for r in before if float(r.get("score") or 0.0) < 0.72]
    weak = sorted(weak, key=lambda r: float(r.get("score") or 0.0))[:max_refines]
    refined: List[int] = []

    if weak and hasattr(content_extractor, "_polish_slide_bullets_quality"):
        slides = improved.get("slides") or []
        for record in weak:
            idx = int(record["slide_index"])
            if idx >= len(slides) or not isinstance(slides[idx], dict):
                continue
            mini_deck = {
                "title": improved.get("title") or "Presentation",
                "slides": [copy.deepcopy(slides[idx])],
            }
            try:
                polished = await content_extractor._polish_slide_bullets_quality(mini_deck, max_slides=1)
                out_slide = (polished.get("slides") or [None])[0]
                if isinstance(out_slide, dict) and out_slide.get("bullets"):
                    slides[idx]["bullets"] = out_slide["bullets"]
                    refined.append(idx)
            except Exception as e:
                print(f"[slide_text_quality] refine slide {idx} failed: {e}")

    mid = _evaluate_deck(improved, source_language=source_language)
    qwen_refined: List[int] = []
    try:
        improved, qwen_refined = await _review_slide_text(
            content_extractor,
            improved,
            mid,
            source_language=source_language,
            provider="vllm",
        )
    except Exception as e:
        print(f"[slide_text_quality] Qwen review pass failed: {e}")

    gemini_refined: List[int] = []
    after_qwen = _evaluate_deck(improved, source_language=source_language)
    uncertain = [
        record for record in after_qwen
        if float(record.get("score") or 0.0) < 0.82 or record.get("issues")
    ]
    if uncertain and getattr(content_extractor, "gemini_available", False):
        try:
            print(
                f"[slide_text_quality] escalating {len(uncertain)} uncertain slide(s) "
                "from Qwen to Gemini"
            )
            improved, gemini_refined = await _review_slide_text(
                content_extractor,
                improved,
                uncertain,
                source_language=source_language,
                provider="gemini",
            )
        except Exception as e:
            print(f"[slide_text_quality] Gemini escalation failed: {e}")

    improved, qwen_title_refined = await _review_and_repair_titles(
        content_extractor,
        improved,
        source_language=source_language,
        provider="vllm",
    )
    gemini_title_refined: List[int] = []
    title_issues_remain = any(
        set(record.get("issues") or [])
        & {"weak_title", "suspicious_title", "off_topic_title", "duplicate_slide_title"}
        for record in _evaluate_deck(improved, source_language=source_language)
    )
    if title_issues_remain and getattr(content_extractor, "gemini_available", False):
        improved, gemini_title_refined = await _review_and_repair_titles(
            content_extractor,
            improved,
            source_language=source_language,
            provider="gemini",
        )

    qwen_note_refined: List[int] = []
    try:
        improved, qwen_note_refined = await _review_speaker_notes(
            content_extractor,
            improved,
            source_language=source_language,
            provider="vllm",
        )
    except Exception as e:
        print(f"[slide_text_quality] Qwen speaker notes pass failed: {e}")
    gemini_note_refined: List[int] = []
    notes_need_escalation = any(
        isinstance(slide, dict) and _speaker_note_issues(slide)
        for slide in (improved.get("slides") or [])
    )
    if notes_need_escalation and getattr(content_extractor, "gemini_available", False):
        try:
            improved, gemini_note_refined = await _review_speaker_notes(
                content_extractor,
                improved,
                source_language=source_language,
                provider="gemini",
            )
        except Exception as e:
            print(f"[slide_text_quality] Gemini speaker notes escalation failed: {e}")
    improved = _sanitize_structured_text(improved)
    after = _evaluate_deck(improved, source_language=source_language)
    title_refined = sorted(set(qwen_title_refined + gemini_title_refined))
    note_refined = sorted(set(qwen_note_refined + gemini_note_refined))
    all_refined = sorted(set(refined + qwen_refined + gemini_refined + title_refined + note_refined))
    _write_text_quality_report(task_id, after, all_refined, source_language=source_language)
    if qwen_refined:
        print(f"[slide_text_quality] Qwen reviewed/refined slides: {qwen_refined}")
    if gemini_refined:
        print(f"[slide_text_quality] Gemini escalation refined slides: {gemini_refined}")
    if title_refined:
        print(f"[slide_text_quality] title post-check refined slides: {title_refined}")
    if note_refined:
        print(f"[slide_text_quality] speaker notes refined slides: {note_refined}")
    return improved
