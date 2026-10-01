"""Content-free measurements for deck quality and repair passes."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Awaitable, Callable, Dict


_TRACKED_FIELDS = (
    "title", "bullets", "notes", "pedagogical_role", "layout", "table", "chart", "source_pages"
)


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def _slide_changes(before: Dict[str, Any], after: Dict[str, Any]) -> tuple[list[int], list[str]]:
    previous = before.get("slides") or []
    current = after.get("slides") or []
    changed_indices = []
    changed_fields = set()
    for index in range(max(len(previous), len(current))):
        left = previous[index] if index < len(previous) and isinstance(previous[index], dict) else {}
        right = current[index] if index < len(current) and isinstance(current[index], dict) else {}
        fields = [field for field in _TRACKED_FIELDS if _digest(left.get(field)) != _digest(right.get(field))]
        if fields:
            changed_indices.append(index)
            changed_fields.update(fields)
    return changed_indices, sorted(changed_fields)


async def run_measured_deck_pass(
    owner: Any,
    name: str,
    deck: Dict[str, Any],
    operation: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    *,
    skip_reason: str = "",
) -> Dict[str, Any]:
    """Run one existing pass unchanged and record only structural metadata."""
    started = time.perf_counter()
    llm_before = len(getattr(owner, "_llm_call_ledger", []) or [])
    result = deck if skip_reason else await operation(deck)
    llm_after = len(getattr(owner, "_llm_call_ledger", []) or [])
    changed_indices, changed_fields = _slide_changes(deck, result)
    event = {
        "pass": str(name),
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "llm_calls": max(0, llm_after - llm_before),
        "input_slides": len(deck.get("slides") or []),
        "output_slides": len(result.get("slides") or []),
        "changed_slide_count": len(changed_indices),
        "changed_slide_indices": changed_indices,
        "changed_fields": changed_fields,
        "no_effect": not changed_indices and len(deck.get("slides") or []) == len(result.get("slides") or []),
        "skipped": bool(skip_reason),
    }
    if skip_reason:
        event["skip_reason"] = str(skip_reason)[:120]
    ledger = getattr(owner, "_quality_pass_ledger", None)
    if not isinstance(ledger, list):
        ledger = []
        setattr(owner, "_quality_pass_ledger", ledger)
    ledger.append(event)
    if len(ledger) > 200:
        del ledger[:-200]
    print("[quality_pass] " + json.dumps(event, ensure_ascii=False, sort_keys=True))
    return result


def quality_pass_summary(owner: Any) -> dict[str, Any]:
    ledger = list(getattr(owner, "_quality_pass_ledger", []) or [])
    return {
        "passes": len(ledger),
        "llm_calls": sum(int(event.get("llm_calls") or 0) for event in ledger),
        "skipped_passes": sum(bool(event.get("skipped")) for event in ledger),
        "no_effect_passes": sum(
            bool(event.get("no_effect")) and not bool(event.get("skipped"))
            for event in ledger
        ),
        "changed_slide_events": sum(int(event.get("changed_slide_count") or 0) for event in ledger),
        "latency_ms": round(sum(float(event.get("latency_ms") or 0.0) for event in ledger), 1),
        "by_pass": {event.get("pass"): event for event in ledger},
    }
