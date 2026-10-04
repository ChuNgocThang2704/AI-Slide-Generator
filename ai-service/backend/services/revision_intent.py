"""The structured meaning of an edit request, as the revision planner (an LLM) reads it.

The keyword rules in revision_rules.py only recognise the phrasings they list, in Vietnamese and
English. The planner already reads the request to choose a scope, so it is also asked for the
concrete operations: how many slides to add and where, which to delete, new titles, tables and
charts, a translation target. Every field is validated here; the keyword rules stay as the
fallback for a field the planner leaves empty or when the planner fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PLANNER_INTENT_RULES = (
    "Also read the concrete operations out of the request and return them under \"intent\" (use null, 0 or an "
    "empty list for whatever the request does not ask for; never guess):\n"
    "- add_slides: {\"count\": number of NEW slides to add, \"after_slide\": the slide number they come after, "
    "0 for the very beginning, null when no position is given}.\n"
    "- delete_slides: slide numbers to remove.\n"
    "- titles: [{\"slide\": number, \"title\": the exact new title text the user gave}]. Only when the user "
    "dictates the title text itself.\n"
    "- visuals: [{\"slide\": number, \"visual\": \"table\"|\"chart\", \"chart_type\": \"bar\"|\"line\"|\"pie\"|null, "
    "\"keep_text\": true when the user wants the table/chart ADDED to the slide's existing content, false when "
    "the slide should be turned into / replaced by it}]. Use the selected slide when the request says 'this slide'.\n"
    "- language: \"vi\" or \"en\" when the request asks to translate the deck or slides into that language, else null.\n"
    "- translate_only: true when translating is the ONLY thing the request asks for (no shortening, rewriting, "
    "adding or removing anything), else false.\n"
    "- bullet_count: the exact number of bullets requested for the target slides, else null.\n"
)

PLANNER_INTENT_SHAPE = (
    ",\"intent\":{\"add_slides\":{\"count\":0,\"after_slide\":null},\"delete_slides\":[],\"titles\":[],"
    "\"visuals\":[],\"language\":null,\"translate_only\":false,\"bullet_count\":null}"
)

_CHART_TYPES = {"bar", "line", "pie"}


@dataclass
class RevisionIntent:
    add_count: int = 0
    add_after: Optional[int] = None          # slide number the new slides follow; 0 = at the start
    delete: List[int] = field(default_factory=list)          # zero-based
    titles: Dict[int, str] = field(default_factory=dict)     # zero-based -> title
    visuals: Dict[int, str] = field(default_factory=dict)    # zero-based -> "table" | "chart"
    chart_types: Dict[int, str] = field(default_factory=dict)
    keep_text: Dict[int, bool] = field(default_factory=dict)
    language: Optional[str] = None
    translate_only: Optional[bool] = None    # None: the planner did not say
    bullet_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "add_count": self.add_count, "add_after": self.add_after, "delete": self.delete,
            "titles": self.titles, "visuals": self.visuals, "chart_types": self.chart_types,
            "keep_text": self.keep_text, "language": self.language, "bullet_count": self.bullet_count,
        }


def _int(value: Any) -> Optional[int]:
    try:
        if isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_intent(raw: Any, slide_count: int) -> RevisionIntent:
    """Validated intent from the planner's "intent" object; anything malformed is dropped."""
    intent = RevisionIntent()
    if not isinstance(raw, dict) or slide_count <= 0:
        return intent

    add = raw.get("add_slides")
    if isinstance(add, dict):
        count = _int(add.get("count"))
        if count and 0 < count <= 10:
            intent.add_count = count
            after = _int(add.get("after_slide"))
            if after is not None and 0 <= after <= slide_count:
                intent.add_after = after

    for value in raw.get("delete_slides") or []:
        number = _int(value)
        if number and 1 <= number <= slide_count and number - 1 not in intent.delete:
            intent.delete.append(number - 1)
    intent.delete.sort()
    if len(intent.delete) >= slide_count:   # never plan to delete the whole deck
        intent.delete = []

    final_count = slide_count + intent.add_count
    for item in raw.get("titles") or []:
        if not isinstance(item, dict):
            continue
        number = _int(item.get("slide"))
        title = " ".join(str(item.get("title") or "").split()).strip(" \"'“”")
        if number and 1 <= number <= slide_count and 2 <= len(title) <= 160:
            intent.titles[number - 1] = title

    for item in raw.get("visuals") or []:
        if not isinstance(item, dict):
            continue
        number = _int(item.get("slide"))
        visual = str(item.get("visual") or "").strip().lower()
        if not number or not 1 <= number <= final_count or visual not in {"table", "chart"}:
            continue
        intent.visuals[number - 1] = visual
        chart_type = str(item.get("chart_type") or "").strip().lower()
        if visual == "chart" and chart_type in _CHART_TYPES:
            intent.chart_types[number - 1] = chart_type
        intent.keep_text[number - 1] = bool(item.get("keep_text"))

    language = str(raw.get("language") or "").strip().lower()
    if language in {"vi", "en"}:
        intent.language = language
        if isinstance(raw.get("translate_only"), bool):
            intent.translate_only = raw["translate_only"]

    bullets = _int(raw.get("bullet_count"))
    if bullets and 1 <= bullets <= 10:
        intent.bullet_count = bullets
    return intent


def added_indices(intent: RevisionIntent, old_count: int, new_count: int) -> Optional[List[int]]:
    """Zero-based slots of the new slides when the planner named a position, else None."""
    if intent.add_count <= 0 or intent.add_after is None or new_count <= old_count:
        return None
    count = min(intent.add_count, new_count - old_count)
    start = max(0, min(intent.add_after, new_count - count))
    return list(range(start, start + count))
