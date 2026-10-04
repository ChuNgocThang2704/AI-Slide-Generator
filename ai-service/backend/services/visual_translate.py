"""Translate the text inside tables and charts when a deck is translated.

A translation request rewrites titles, bullets and notes; the table and chart of each slide are
carried over as they were, so they stayed in the old language. One LLM call translates every
string they hold; the structure and the numbers are never touched.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from services.content.json_utils import parse_json_response

_SKIP_KEYS = {"type", "chart_type", "unit", "id", "color", "colors", "source", "status"}
_NUMERIC = re.compile(r"^[\s\d.,%+\-–$€£₫/:()]*$")
_LANG_NAME = {"vi": "Vietnamese", "en": "English"}


def _collect(node: Any, path: Tuple, out: List[Tuple[Tuple, str]]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key) in _SKIP_KEYS:
                continue
            _collect(value, path + (key,), out)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _collect(value, path + (index,), out)
    elif isinstance(node, str) and node.strip() and not _NUMERIC.match(node):
        out.append((path, node))


def _assign(root: Any, path: Tuple, value: str) -> None:
    node = root
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def _clean(text: str) -> str:
    return str(text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


async def translate_strings(content_extractor, strings: List[str], language: str, kind: str) -> Optional[List[str]]:
    """Translate `strings` one for one into `language`; None when the model does not return the same count."""
    if language not in _LANG_NAME or not strings or not hasattr(content_extractor, "_llm_completion_plain_text"):
        return None
    messages = [
        {
            "role": "system",
            "content": (
                f"Translate each string into {_LANG_NAME[language]}. They are {kind}: keep numbers, units, code and "
                "proper names exactly, keep any **bold** markers, and leave a string unchanged when it is already in "
                "that language. Do not merge, drop or summarise. Return strict JSON only: "
                '{"items":[string]} with exactly the same number of items in the same order.'
            ),
        },
        {"role": "user", "content": json.dumps({"items": strings}, ensure_ascii=False)},
    ]
    try:
        raw = await content_extractor._llm_completion_plain_text(
            messages, max_tokens=min(6000, 300 + sum(len(text) for text in strings)), temperature=0.0, json_mode=True,
        )
        parsed = parse_json_response(raw, clean_result_text=_clean)
    except Exception as error:
        print(f"[visual_translate] failed: {error!r}")
        return None
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list) or len(items) != len(strings):
        print("[visual_translate] ignored: item count mismatch")
        return None
    return [str(item or "").strip() for item in items]


_TEXT_KEYS = ("title", "subtitle", "notes", "speaker_notes")
_BATCH_CHARS = 3500


async def translate_deck_text(
    content_extractor, deck: Dict[str, Any], language: str, only: Optional[List[int]] = None,
) -> Optional[Dict[str, Any]]:
    """A copy of `deck` with every title, bullet and note translated one for one into `language`.

    Asking the model to rewrite a whole deck "in English" lets it reorder, merge and invent slides.
    Here it only ever sees a flat list of strings and must return the same number of them, so a
    slide cannot change place or lose a point. None when any batch fails (the caller then falls
    back to the ordinary revision path)."""
    slides = deck.get("slides") if isinstance(deck, dict) else None
    if language not in _LANG_NAME or not isinstance(slides, list) or not slides:
        return None
    out = {**deck, "slides": [dict(slide) if isinstance(slide, dict) else slide for slide in slides]}
    wanted = set(only) if only else None
    slots: List[Tuple[int, str, Optional[int]]] = []
    texts: List[str] = []
    for index, slide in enumerate(out["slides"]):
        if not isinstance(slide, dict) or (wanted is not None and index not in wanted):
            continue
        for key in _TEXT_KEYS:
            value = slide.get(key)
            if isinstance(value, str) and value.strip() and not _NUMERIC.match(value):
                slots.append((index, key, None))
                texts.append(value)
        bullets = slide.get("bullets")
        if isinstance(bullets, list):
            slide["bullets"] = list(bullets)
            for position, bullet in enumerate(bullets):
                if isinstance(bullet, str) and bullet.strip() and not _NUMERIC.match(bullet):
                    slots.append((index, "bullets", position))
                    texts.append(bullet)
    if not texts:
        return None

    translated: List[str] = []
    start = 0
    while start < len(texts):
        end, size = start, 0
        while end < len(texts) and (end == start or size + len(texts[end]) <= _BATCH_CHARS):
            size += len(texts[end])
            end += 1
        batch = texts[start:end]
        result = None
        for _ in range(2):
            result = await translate_strings(
                content_extractor, batch, language, "slide titles, bullet points and speaker notes of one deck",
            )
            if result and all(result):
                break
            result = None
        if result is None:
            print(f"[visual_translate] deck text translation failed on strings {start}-{end}")
            return None
        translated.extend(result)
        start = end

    for (index, key, position), text in zip(slots, translated):
        if position is None:
            out["slides"][index][key] = text
        else:
            out["slides"][index]["bullets"][position] = text
    if wanted is None and isinstance(out.get("title"), str) and out["slides"] and isinstance(out["slides"][0], dict):
        out["title"] = out["slides"][0].get("title") or out["title"]
    print(f"[visual_translate] translated {len(texts)} deck strings to {language} one for one")
    return out


async def restore_dropped_bullets(content_extractor, deck: Dict[str, Any], old_slides: List[Any], language: str) -> List[int]:
    """Last guard of a translation: a slide that still has fewer bullets than before gets its
    original bullets translated one for one. Returns the slide indices that were repaired."""
    slides = deck.get("slides") if isinstance(deck, dict) else None
    if not isinstance(slides, list) or len(slides) != len(old_slides):
        return []
    repaired = []
    for index, (new_slide, old_slide) in enumerate(zip(slides, old_slides)):
        if not isinstance(new_slide, dict) or not isinstance(old_slide, dict):
            continue
        old_bullets = [str(b) for b in (old_slide.get("bullets") or []) if str(b).strip()]
        new_bullets = [b for b in (new_slide.get("bullets") or []) if str(b).strip()]
        if len(new_bullets) >= len(old_bullets):
            continue
        translated = await translate_strings(content_extractor, old_bullets, language, "the bullet points of one slide")
        if translated and all(translated):
            new_slide["bullets"] = translated
            repaired.append(index)
    if repaired:
        print(f"[visual_translate] restored dropped bullets on slides {repaired}")
    return repaired


async def translate_visual_text(content_extractor, deck: Dict[str, Any], language: str) -> int:
    """Translate table/chart strings of every slide into `language`; returns how many were changed."""
    if language not in _LANG_NAME or not hasattr(content_extractor, "_llm_completion_plain_text"):
        return 0
    slides = deck.get("slides") if isinstance(deck, dict) else None
    found: List[Tuple[Tuple, str]] = []
    for index, slide in enumerate(slides or []):
        if not isinstance(slide, dict):
            continue
        for key in ("table", "chart"):
            if isinstance(slide.get(key), dict):
                _collect(slide[key], (index, key), found)
    if not found:
        return 0
    unique = list(dict.fromkeys(text for _, text in found))
    messages = [
        {
            "role": "system",
            "content": (
                f"Translate each string into {_LANG_NAME[language]}. They are table headers, table cells and chart "
                "labels: keep them short, keep numbers, units, code and proper names exactly, and leave a string "
                "unchanged when it is already in that language. Return strict JSON only: "
                '{"items":[string]} with exactly the same number of items in the same order.'
            ),
        },
        {"role": "user", "content": json.dumps({"items": unique}, ensure_ascii=False)},
    ]
    try:
        raw = await content_extractor._llm_completion_plain_text(
            messages, max_tokens=min(6000, 300 + sum(len(text) for text in unique)), temperature=0.0, json_mode=True,
        )
        parsed = parse_json_response(raw, clean_result_text=_clean)
    except Exception as error:
        print(f"[visual_translate] failed: {error!r}")
        return 0
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list) or len(items) != len(unique):
        print("[visual_translate] ignored: item count mismatch")
        return 0
    mapping = {}
    for source, target in zip(unique, items):
        target = str(target or "").strip()
        # The digits of a cell are data: a translation that changes them is refused.
        if target and re.findall(r"\d+", target) == re.findall(r"\d+", source):
            mapping[source] = target
    changed = 0
    for path, text in found:
        new = mapping.get(text)
        if new and new != text:
            _assign(slides, path, new)
            changed += 1
    print(f"[visual_translate] translated {changed}/{len(found)} table/chart strings to {language}")
    return changed
