"""Keep a cover as a cover after late review passes edit its prose."""

from __future__ import annotations

import re
from typing import Any


_DETAIL_PREFIX = re.compile(
    r"^(?:định nghĩa|khái niệm|definition|what is|là gì|tầm quan trọng|importance|"
    r"vai trò|role|mục tiêu|learning objectives?)\s*[:：-]",
    re.IGNORECASE,
)
_SKIP_TITLES = re.compile(
    r"^(?:mục tiêu học tập|learning objectives?|agenda|nội dung|overview|tổng quan|"
    r"giới thiệu|introduction|summary|kết luận)$",
    re.IGNORECASE,
)


def _short_title(value: str, limit: int = 50) -> str:
    value = re.sub(r"\s+", " ", value).strip(" .:;,-–—")
    if len(value) <= limit:
        return value
    return value[:limit].rsplit(" ", 1)[0].strip(" .:;,-–—")


def normalize_cover(deck: dict[str, Any]) -> dict[str, Any]:
    """Replace a verbose/definition cover with a scope preview, preserving prose in notes."""
    slides = deck.get("slides") or []
    if len(slides) < 2 or not isinstance(slides[0], dict):
        return deck
    cover = slides[0]
    if str(cover.get("layout") or "").lower() not in {"intro", "title"}:
        return deck
    bullets = [str(item).strip() for item in (cover.get("bullets") or []) if str(item).strip()]
    if len(bullets) == 1 and len(bullets[0]) <= 120 and ":" not in bullets[0] and not _DETAIL_PREFIX.search(bullets[0]):
        return deck

    cover_title = str(cover.get("title") or "").strip().casefold()
    topics = []
    for slide in slides[1:-1]:
        if not isinstance(slide, dict):
            continue
        title = _short_title(str(slide.get("title") or ""))
        if title and title.casefold() != cover_title and not _SKIP_TITLES.match(title):
            topics.append(title)
    if not topics:
        return deck  # No dependable scope to summarize without inventing content.
    vietnamese = bool(re.search(r"[À-ỹ]", str(cover.get("title") or "") + " ".join(topics)))
    if len(topics) > 1:
        subtitle = f"Từ {topics[0]} đến {topics[-1]}" if vietnamese else f"From {topics[0]} to {topics[-1]}"
    else:
        subtitle = f"Khám phá {topics[0]}" if vietnamese else f"Exploring {topics[0]}"
    subtitle = _short_title(subtitle, 120)
    if not subtitle:
        return deck
    old_notes = str(cover.get("notes") or "").strip()
    missing = [item for item in bullets if item not in old_notes]
    if missing:
        cover["notes"] = "\n".join(part for part in [old_notes, *missing] if part)
    cover["bullets"] = [subtitle]
    return deck
