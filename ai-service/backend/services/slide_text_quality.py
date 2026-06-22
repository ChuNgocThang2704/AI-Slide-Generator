"""Quality checks and limited refinement for generated slide text."""
from __future__ import annotations

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
_WEAK_TAIL_WORDS = {
    "và", "hoặc", "của", "cho", "với", "từ", "đến", "trong", "nhằm",
    "and", "or", "of", "for", "with", "to", "from", "in", "by",
}
_STOP_TERMS = {
    "và", "hoặc", "của", "cho", "với", "trong", "những", "các", "một",
    "and", "or", "of", "for", "with", "from", "into", "this", "that",
}
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


def _is_weak_tail(text: str) -> bool:
    tokens = _words(text.lower())
    return bool(tokens and tokens[-1] in _WEAK_TAIL_WORDS)


def _clean_json_text(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _sanitize_inline_markup(text: str) -> str:
    """Normalize any AI-written slide text to plain text."""
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
    t = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", t)
    t = re.sub(r"__([^_\n]+)__", r"\1", t)
    t = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", t)
    t = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", t)
    t = re.sub(r"\*{2,}", "", t)
    t = re.sub(r"_{2,}", "", t)
    t = re.sub(r"\*+\s*:", ":", t)
    t = re.sub(r":\s*\*+\s*", ": ", t)
    t = re.sub(r"\s+\*+\s+", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def _sanitize_structured_text(structured: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the plain-text contract to every user-visible text field."""
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
        script = _sanitize_inline_markup(slide.get("script") or slide.get("notes") or "")
        if script:
            slide["script"] = script
            slide["notes"] = script
    return structured


def _is_suspicious_title(title: str) -> bool:
    t = re.sub(r"\s+", " ", str(title or "").strip())
    if not t:
        return True
    tokens = _words(t.lower())
    if len(tokens) < 3:
        return True
    if len(tokens) > 14:
        return True
    if _is_weak_tail(t):
        return True
    if re.search(r"[,;:/\\\-–—]\s*$", t):
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
    for raw in bullets or []:
        cand = _candidate_title_from_text(str(raw or ""))
        key = _norm_title_key(cand)
        if len(_words(cand)) >= 3 and key and key not in seen and not _is_suspicious_title(cand):
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
        needs_fix = not key or key in seen or _is_suspicious_title(title)
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
        if len(t) < 3 or t in _STOP_TERMS or t.isdigit():
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
        # A Vietnamese deck may contain brands/tech terms, but long prose with no
        # Vietnamese diacritics and many English function words is likely drift.
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
    if _is_suspicious_title(title):
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

    seen = set()
    for idx, bullet in enumerate(bullets):
        wc = len(_words(bullet))
        key = re.sub(r"\W+", " ", bullet.lower()).strip()
        if wc < 6:
            score -= 0.08
            issues.append(f"short_bullet_{idx}")
        if wc > 32:
            score -= 0.08
            issues.append(f"long_bullet_{idx}")
        if _is_weak_tail(bullet) or bullet.endswith(("...", "…")):
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
    """Lightweight deck-level checks without extra LLM calls."""
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


def _slide_subset_for_review(structured: Dict[str, Any], records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    slides = structured.get("slides") or []
    selected: List[Dict[str, Any]] = []
    for rec in records:
        idx = int(rec.get("slide_index") or 0)
        if idx >= len(slides) or not isinstance(slides[idx], dict):
            continue
        issues = set(rec.get("issues") or [])
        score = float(rec.get("score") or 0.0)
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


async def _gemini_review_slide_text(
    content_extractor,
    structured: Dict[str, Any],
    records: List[Dict[str, Any]],
    source_language: str = "auto",
) -> Tuple[Dict[str, Any], List[int]]:
    """Ask Gemini to review weak/cut-off slides as a second-opinion critic."""
    if not _GEMINI_REVIEW_ENABLE or not getattr(content_extractor, "gemini_available", False):
        return structured, []
    if not hasattr(content_extractor, "_gemini_completion_plain_text"):
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
        raw = await content_extractor._gemini_completion_plain_text(
            messages,
            max_tokens=1800,
            temperature=0.15,
            json_mode=True,
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
        if item.get("script"):
            slides[idx]["script"] = item["script"]
            slides[idx]["notes"] = item["script"]
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
    if not fixed or _looks_corrupted_text(fixed):
        return None
    return {
        "index": idx,
        "pass": bool(item.get("pass")),
        "fixed_title": fixed[:120],
        "reason": str(item.get("reason") or "").strip()[:200],
    }


async def _gemini_repair_titles_after_review(
    content_extractor,
    structured: Dict[str, Any],
    source_language: str = "auto",
) -> Tuple[Dict[str, Any], List[int]]:
    """Use Gemini as a semantic title reviewer for the whole deck.

    This avoids brittle word-list fixes for incomplete titles like a proper noun
    or technical phrase being cut in half. The fallback deterministic repair is
    still available when Gemini is not configured or fails.
    """
    if not _GEMINI_REVIEW_ENABLE or not getattr(content_extractor, "gemini_available", False):
        fallback = copy.deepcopy(structured)
        return fallback, _repair_titles_after_review(fallback)
    if not hasattr(content_extractor, "_gemini_completion_plain_text"):
        fallback = copy.deepcopy(structured)
        return fallback, _repair_titles_after_review(fallback)

    slides = structured.get("slides") or []
    if not isinstance(slides, list) or not slides:
        return structured, []

    payload = {
        "deck_title": str(structured.get("title") or ""),
        "source_language": source_language,
        "slides": [
            {
                "index": idx,
                "title": str(slide.get("title") or ""),
                "bullets": _slide_bullets_preview(slide),
            }
            for idx, slide in enumerate(slides)
            if isinstance(slide, dict)
        ],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You are a strict slide-title QA reviewer.\n"
                "Review every title for semantic completeness, uniqueness, and fit to its bullets.\n"
                "A title must be a complete phrase, not a cut-off fragment, not a dangling prepositional phrase, "
                "not the first half of a proper noun or technical term, and not duplicated from another slide unless the content is truly identical.\n"
                "If a title is already complete and unique, keep it exactly.\n"
                "If it is incomplete, duplicated, too vague, or mismatched, rewrite only the title using the slide bullets.\n"
                f"{_language_instruction(source_language)}\n"
                "Return plain text titles only: no Markdown, no bold/italic markers, no list markers.\n"
                "Do not add new facts. Prefer concise titles of 4-12 words.\n"
                "Return strict JSON only: {\"titles\":[{\"index\":number,\"pass\":boolean,\"fixed_title\":string,\"reason\":string}]}."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    try:
        raw = await content_extractor._gemini_completion_plain_text(
            messages,
            max_tokens=1600,
            temperature=0.05,
            json_mode=True,
        )
        parsed = parse_json_response(raw, clean_result_text=_clean_json_text)
    except Exception as e:
        print(f"[slide_text_quality] Gemini title review failed: {e}")
        fallback = copy.deepcopy(structured)
        return fallback, _repair_titles_after_review(fallback)

    decisions = (parsed or {}).get("titles") if isinstance(parsed, dict) else None
    if not isinstance(decisions, list):
        fallback = copy.deepcopy(structured)
        return fallback, _repair_titles_after_review(fallback)

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
        if not key or key in seen or _is_suspicious_title(fixed):
            fixed = _derive_title_from_bullets(
                out_slides[idx].get("bullets") or out_slides[idx].get("content") or [],
                fallback=current or fixed,
                seen=seen,
            )
            key = _norm_title_key(fixed)
        if key and key not in seen:
            if fixed != current:
                out_slides[idx]["title"] = fixed
                changed.append(idx)
            seen.add(key)

    # Catch any slide omitted by Gemini or duplicate introduced by the model.
    changed.extend(i for i in _repair_titles_after_review(improved) if i not in changed)
    return _sanitize_structured_text(improved), sorted(set(changed))


async def improve_slide_text_quality(
    content_extractor,
    structured: Dict[str, Any],
    *,
    task_id: str = "",
    max_refines: int = 3,
    source_language: str = "auto",
) -> Dict[str, Any]:
    """Evaluate slide text and polish at most a few weak slides."""
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
    gemini_refined: List[int] = []
    try:
        improved, gemini_refined = await _gemini_review_slide_text(
            content_extractor,
            improved,
            mid,
            source_language=source_language,
        )
    except Exception as e:
        print(f"[slide_text_quality] Gemini review pass failed: {e}")

    improved, title_refined = await _gemini_repair_titles_after_review(
        content_extractor,
        improved,
        source_language=source_language,
    )
    improved = _sanitize_structured_text(improved)
    after = _evaluate_deck(improved, source_language=source_language)
    all_refined = sorted(set(refined + gemini_refined + title_refined))
    _write_text_quality_report(task_id, after, all_refined, source_language=source_language)
    if gemini_refined:
        print(f"[slide_text_quality] Gemini reviewed/refined slides: {gemini_refined}")
    if title_refined:
        print(f"[slide_text_quality] title post-check refined slides: {title_refined}")
    return improved
