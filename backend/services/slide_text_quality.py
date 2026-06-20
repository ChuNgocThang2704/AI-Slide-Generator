"""Quality checks and limited refinement for generated slide text."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DEBUG_DIR = Path("outputs") / "debug"
_WEAK_TAIL_WORDS = {
    "và", "hoặc", "của", "cho", "với", "từ", "đến", "trong", "nhằm",
    "and", "or", "of", "for", "with", "to", "from", "in", "by",
}
_STOP_TERMS = {
    "và", "hoặc", "của", "cho", "với", "trong", "những", "các", "một",
    "and", "or", "of", "for", "with", "from", "into", "this", "that",
}


def _words(text: str) -> List[str]:
    return re.findall(r"[\wÀ-ỹ-]+", text or "", flags=re.UNICODE)


def _is_weak_tail(text: str) -> bool:
    tokens = _words(text.lower())
    return bool(tokens and tokens[-1] in _WEAK_TAIL_WORDS)


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


def _score_slide_text(slide: Dict[str, Any]) -> Tuple[float, List[str]]:
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
    if len(bullets) < 3:
        score -= 0.25
        issues.append("too_few_bullets")
    if len(bullets) > 6:
        score -= 0.1
        issues.append("too_many_bullets")

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


def _evaluate_deck(structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    slides = structured.get("slides") or []
    records: List[Dict[str, Any]] = []
    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        score, issues = _score_slide_text(slide)
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


def _write_text_quality_report(task_id: str, records: List[Dict[str, Any]], refined: List[int]) -> None:
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


async def improve_slide_text_quality(
    content_extractor,
    structured: Dict[str, Any],
    *,
    task_id: str = "",
    max_refines: int = 3,
) -> Dict[str, Any]:
    """Evaluate slide text and polish at most a few weak slides."""
    if not isinstance(structured, dict):
        return structured

    improved = copy.deepcopy(structured)
    before = _evaluate_deck(improved)
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

    after = _evaluate_deck(improved)
    _write_text_quality_report(task_id, after, refined)
    return improved
