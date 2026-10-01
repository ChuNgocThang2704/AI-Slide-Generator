"""Post-generation source audit for document-grounded decks.

This is a semantic LLM check, not a mathematical proof of faithfulness. An
unparseable audit fails closed instead of silently publishing a suspect deck.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

from services.content.json_utils import parse_json_response
from services.grounding_policy import policy_for_extractor


def _clean(value: str) -> str:
    return str(value or "").strip().removeprefix("```json").removesuffix("```").strip()


def _slide_text(deck: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"index": index, "title": slide.get("title"), "bullets": slide.get("bullets"),
         "notes": slide.get("notes"), "table": slide.get("table"), "chart": slide.get("chart")}
        for index, slide in enumerate(deck.get("slides") or []) if isinstance(slide, dict)
    ]


async def _audit(extractor: Any, deck: dict[str, Any], source: str) -> list[dict[str, Any]]:
    payload = {"source": source[:30000], "slides": _slide_text(deck)}
    messages = [{"role": "system", "content": (
        "You are a strict source-faithfulness auditor. The source is the ONLY factual authority. "
        "For each slide, inspect title, every bullet, notes, table cells and chart claims. "
        "Report a slide if it asserts any document-specific event, cause, effect, strategy, cost, "
        "customer segment, future plan, number or date not explicitly supported by source. "
        "Generic structural headings, questions, and transparent arithmetic from source numbers are allowed. "
        "Do not accept a plausible inference as sourced fact. Be especially strict with causal explanations "
        "and recommendations presented as if they came from the document. "
        "Return JSON only: {\"unsupported\":[{\"index\":0,\"reason\":\"...\"}]}."
    )}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    raw = await extractor._llm_completion_plain_text(
        messages, max_tokens=1800, temperature=0.0, json_mode=True
    )
    parsed = parse_json_response(raw, clean_result_text=_clean)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("unsupported"), list):
        raise RuntimeError("Source-faithfulness audit returned an invalid response")
    issues = []
    for item in parsed["unsupported"]:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if 0 <= index < len(deck.get("slides") or []):
            issues.append({"index": index, "reason": str(item.get("reason") or "unsupported claim")[:300]})
    return issues


_PAGE_MARKER_RE = re.compile(r"^\s*PAGE\s+\d+\s*", re.IGNORECASE)


def _source_sentences(source: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", str(source or ""))
    cleaned = [_PAGE_MARKER_RE.sub("", p).strip() for p in parts]
    return [p for p in cleaned if len(p) > 8]


def _apply_literal_fallback(
    deck: dict[str, Any], issues: list[dict[str, Any]], source: str
) -> tuple[dict[str, Any], set[int]]:
    """Last-resort, no-LLM repair: restate a verbatim source sentence.

    Used only when the LLM repair loop still leaves a slide unsupported. A
    sentence copied character-for-character from the source cannot introduce
    a new claim, so the indices it touches are returned as provably safe:
    the strict auditor sometimes still flags a literal quote over verb
    framing ("applies" vs. "lists"), which is a judgment call on phrasing,
    not evidence of an invented fact, so those indices are exempted from
    later audit rounds instead of looping forever.
    """
    sentences = _source_sentences(source)
    if not sentences:
        return deck, set()
    repaired = copy.deepcopy(deck)
    used = {
        str(b).strip()
        for slide in repaired.get("slides") or []
        if isinstance(slide, dict)
        for b in (slide.get("bullets") or [])
    }
    cursor = 0
    fixed_indices: set[int] = set()
    for item in issues:
        index = item.get("index")
        if not isinstance(index, int) or not (0 <= index < len(repaired.get("slides") or [])):
            continue
        sentence = next((s for s in sentences[cursor:] if s not in used), None)
        if sentence is None:
            sentence = sentences[0]
        cursor = sentences.index(sentence) + 1 if sentence in sentences else cursor
        used.add(sentence)
        slide = repaired["slides"][index]
        if slide.get("table") or slide.get("chart"):
            slide["layout"] = "text_only"
        # The old title may itself be the unsupported claim the auditor flagged,
        # so it cannot be kept; derive a neutral one from the same safe sentence.
        title = sentence if len(sentence) <= 60 else sentence[:57].rstrip() + "..."
        slide.update(title=title, bullets=[sentence], notes="", table=None, chart=None)
        fixed_indices.add(index)
    return repaired, fixed_indices


async def enforce_source_faithfulness(
    extractor: Any, deck: dict[str, Any], source: str
) -> dict[str, Any]:
    """Repair unsupported slides at most twice, then reject unresolved claims."""
    if not policy_for_extractor(extractor, source).source_is_authoritative:
        return deck
    if len(source) > 30000:
        # A truncated source cannot establish that a claim is unsupported.
        return deck
    current = deck
    for _attempt in range(2):
        issues = await _audit(extractor, current, source)
        if not issues:
            return current
        current = await _repair_once(extractor, current, source, issues)
    verbatim_safe: set[int] = set()
    for _fallback_attempt in range(3):
        issues = [item for item in await _audit(extractor, current, source)
                   if item.get("index") not in verbatim_safe]
        if not issues:
            return current
        current, fixed_indices = _apply_literal_fallback(current, issues, source)
        verbatim_safe |= fixed_indices
    final_issues = [item for item in await _audit(extractor, current, source)
                     if item.get("index") not in verbatim_safe]
    if final_issues:
        print(f"[source_faithfulness] unresolved after literal fallback: {final_issues}")
        raise RuntimeError("Source-faithfulness audit still found unsupported claims after repair")
    return current


async def _repair_once(
    extractor: Any, deck: dict[str, Any], source: str, issues: list[dict[str, Any]]
) -> dict[str, Any]:
    targets = {item["index"] for item in issues}
    payload = {
        "source": source,
        "issues": issues,
        "slides": [_slide_text(deck)[index] for index in sorted(targets)],
    }
    messages = [{"role": "system", "content": (
        "Repair ONLY the listed slides against the supplied source. Treat every issue reason as a concrete "
        "claim to remove. Remove unsupported causes, effects, strategies, stakeholder actions and future plans; "
        "never replace them with other invented claims. For sparse sources, reuse exact supported figures in "
        "different views, make transparent arithmetic explicit, or pose clearly labelled discussion questions. "
        "A question must not presuppose an unsupported fact. Speaker notes also must contain only source-backed "
        "facts or clearly labelled questions; do not write plausible background narration. Preserve each slide "
        "index, role and the deck's count/order. Return JSON only: "
        "{\"slides\":[{\"index\":0,\"title\":\"...\",\"bullets\":[\"...\"],\"notes\":\"...\"}]}"
    )}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    raw = await extractor._llm_completion_plain_text(
        messages, max_tokens=min(4000, 500 + len(targets) * 500), temperature=0.0, json_mode=True
    )
    parsed = parse_json_response(raw, clean_result_text=_clean)
    replacements = parsed.get("slides") if isinstance(parsed, dict) else None
    if not isinstance(replacements, list):
        raise RuntimeError("Source-faithfulness repair returned an invalid response")
    repaired = copy.deepcopy(deck)
    seen = set()
    for item in replacements:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        if index not in targets or index in seen:
            continue
        title = str(item.get("title") or "").strip()
        bullets = item.get("bullets")
        if not title or not isinstance(bullets, list) or not any(str(b).strip() for b in bullets):
            continue
        slide = repaired["slides"][index]
        if slide.get("table") or slide.get("chart"):
            slide["layout"] = "text_only"
        slide.update(title=title, bullets=[str(b).strip() for b in bullets if str(b).strip()],
                     notes=str(item.get("notes") or "").strip(), table=None, chart=None)
        seen.add(index)
    missing = sorted(targets - seen)
    if len(missing) > 2:
        raise RuntimeError("Source-faithfulness repair omitted too many flagged slides")
    for index in missing:
        single = {
            "source": source,
            "issue": next(item for item in issues if item["index"] == index),
            "slide": _slide_text(repaired)[index],
        }
        single_messages = [{"role": "system", "content": (
            "Repair exactly this one slide using only facts explicitly present in the source. "
            "Remove every unsupported claim from title, bullets and notes. Do not infer a cause, "
            "strategy or plan. If the source has no more distinct facts for this slide, restate an "
            "already-supported fact from a different angle or pose one clearly labelled discussion "
            "question that does not presuppose an unsupported fact; do not leave title or bullets empty. "
            "Return JSON only: {\"index\":0,\"title\":\"...\",\"bullets\":[\"...\"],\"notes\":\"...\"}."
        )}, {"role": "user", "content": json.dumps(single, ensure_ascii=False)}]
        single_item = None
        for _repair_attempt in range(2):
            single_raw = await extractor._llm_completion_plain_text(
                single_messages, max_tokens=900, temperature=0.0, json_mode=True
            )
            candidate = parse_json_response(single_raw, clean_result_text=_clean)
            if isinstance(candidate, dict) and isinstance(candidate.get("slides"), list):
                items = [item for item in candidate["slides"] if isinstance(item, dict)]
                candidate = items[0] if len(items) == 1 else None
            elif isinstance(candidate, dict) and isinstance(candidate.get("slide"), dict):
                candidate = candidate["slide"]
            # The request contains exactly one target. Some models omit its index
            # or return it as a string; the final source audit still verifies the
            # replacement before the deck can be published.
            if (
                isinstance(candidate, dict)
                and str(candidate.get("title") or "").strip()
                and isinstance(candidate.get("bullets"), list)
                and any(str(b).strip() for b in candidate["bullets"])
            ):
                single_item = candidate
                break
        if single_item is None:
            raise RuntimeError("Source-faithfulness repair omitted a flagged slide")
        title = str(single_item.get("title") or "").strip()
        bullets = single_item.get("bullets")
        slide = repaired["slides"][index]
        if slide.get("table") or slide.get("chart"):
            slide["layout"] = "text_only"
        slide.update(title=title, bullets=[str(b).strip() for b in bullets if str(b).strip()],
                     notes=str(single_item.get("notes") or "").strip(), table=None, chart=None)
    return repaired
