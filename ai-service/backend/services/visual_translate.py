"""Translate the text inside tables and charts when a deck is translated.

A translation request rewrites titles, bullets and notes; the table and chart of each slide are
carried over as they were, so they stayed in the old language. One LLM call translates every
string they hold; the structure and the numbers are never touched.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

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
