"""Keep visible slide text short enough to read: long bullets are condensed, never truncated.

The author prompt asks for bullets of at most MAX_WORDS_PER_BULLET words, but nothing checked the
result, so a typical deck came back with bullets of 25-45 words and the editor had to shrink the
text to fit. One LLM call rewrites only the bullets that are too long; every rewrite is validated
(shorter, keeps its label and its numbers) and the original is kept when it is not.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from services.content.json_utils import parse_json_response
from services.content.prompts import MAX_WORDS_PER_BULLET

# A bullet is rewritten when it runs past this; the target stays MAX_WORDS_PER_BULLET.
_FLAG_WORDS = MAX_WORDS_PER_BULLET + 4
_ACCEPT_WORDS = MAX_WORDS_PER_BULLET + 4
_COLUMN_PREFIX = re.compile(r"^(.{1,48}?)\s[—–-]\s(?=\S)")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _clean_json(text: str) -> str:
    return str(text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def _split_prefix(bullet: str, layout: str) -> Tuple[str, str]:
    """A two-column bullet carries its column heading in front ("Heading - point"); keep it apart."""
    if layout != "split_columns":
        return "", bullet
    match = _COLUMN_PREFIX.match(bullet)
    if not match:
        return "", bullet
    return bullet[: match.end()], bullet[match.end():]


def _words(text: str) -> int:
    return len(str(text or "").split())


def _is_code_like(text: str) -> bool:
    return bool(re.search(r"[{};=]|^\s*[$>#]\s|\(\)|->|=>", text)) and _words(text) <= 14


def long_bullets(deck: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The bullets that need condensing, with where they are."""
    found: List[Dict[str, Any]] = []
    slides = deck.get("slides") if isinstance(deck, dict) else None
    for slide_index, slide in enumerate(slides or []):
        if not isinstance(slide, dict) or slide_index == 0:
            continue
        layout = str(slide.get("layout") or "").strip().lower()
        if layout in {"big_quote", "quote"}:
            continue
        for bullet_index, bullet in enumerate(slide.get("bullets") or []):
            if not isinstance(bullet, str) or _is_code_like(bullet):
                continue
            prefix, body = _split_prefix(bullet, layout)
            if _words(body) > _FLAG_WORDS:
                found.append({"slide": slide_index, "bullet": bullet_index, "prefix": prefix, "text": body})
    return found


def _acceptable(original: str, rewritten: str) -> bool:
    new = str(rewritten or "").strip()
    if not new or _words(new) > _ACCEPT_WORDS or _words(new) >= _words(original):
        return False
    if _words(new) < 4:
        return False
    # A "Label: explanation" bullet keeps its label.
    if ":" in original[:60]:
        label = original.split(":", 1)[0].strip().casefold()
        if not new.casefold().startswith(label):
            return False
    # No number may appear that the original did not have.
    return set(_NUMBER.findall(new)) <= set(_NUMBER.findall(original))


async def condense_long_bullets(content_extractor, deck: Dict[str, Any]) -> Dict[str, Any]:
    """Rewrite over-long bullets in place (one LLM call). The speaker notes already carry the detail."""
    items = long_bullets(deck)
    if not items or not hasattr(content_extractor, "_llm_completion_plain_text"):
        return deck
    payload = [{"id": index, "text": item["text"]} for index, item in enumerate(items)]
    messages = [
        {
            "role": "system",
            "content": (
                "You shorten slide bullets so they can be read on a projected slide. For each item, rewrite the "
                f"text as ONE complete line of at most {MAX_WORDS_PER_BULLET} words, in the same language. Keep the "
                "leading 'Label:' exactly when there is one, keep every number, name and unit that carries the "
                "point, and keep the main claim; drop examples, asides, and second clauses. Never add facts or "
                "numbers. Do not end with an ellipsis. Return strict JSON only: "
                '{"items":[{"id":number,"text":string}]} with every id present.'
            ),
        },
        {"role": "user", "content": json.dumps({"items": payload}, ensure_ascii=False)},
    ]
    try:
        raw = await content_extractor._llm_completion_plain_text(
            messages,
            max_tokens=min(6000, 400 + len(items) * 70),
            temperature=0.0,
            json_mode=True,
        )
        parsed = parse_json_response(raw, clean_result_text=_clean_json)
    except Exception as error:  # the deck is still valid, only wordier
        print(f"[slide_density] condense failed: {error!r}")
        return deck
    rewritten = {}
    for entry in (parsed.get("items") if isinstance(parsed, dict) else None) or []:
        if isinstance(entry, dict):
            try:
                rewritten[int(entry.get("id"))] = str(entry.get("text") or "")
            except (TypeError, ValueError):
                continue
    slides = deck["slides"]
    applied = 0
    for index, item in enumerate(items):
        new = rewritten.get(index, "").strip()
        if not _acceptable(item["text"], new):
            continue
        slide = slides[item["slide"]]
        slide["bullets"][item["bullet"]] = item["prefix"] + new
        applied += 1
    print(f"[slide_density] condensed {applied}/{len(items)} long bullets")
    return deck
