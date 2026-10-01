"""Aggregate content-free `[quality_pass]` JSON events from an application log."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


PREFIX = "[quality_pass] "


def parse_events(lines: Iterable[str]) -> list[dict]:
    events = []
    for line in lines:
        marker = line.find(PREFIX)
        if marker < 0:
            continue
        try:
            value = json.loads(line[marker + len(PREFIX):].strip())
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(value, dict) and value.get("pass"):
            events.append(value)
    return events


def summarize(events: Iterable[dict]) -> dict:
    grouped = defaultdict(list)
    for event in events:
        grouped[str(event.get("pass"))].append(event)
    passes = {}
    for name, values in sorted(grouped.items()):
        runs = len(values)
        skipped = sum(bool(value.get("skipped")) for value in values)
        executed = runs - skipped
        no_effect = sum(
            bool(value.get("no_effect")) and not bool(value.get("skipped"))
            for value in values
        )
        passes[name] = {
            "runs": runs,
            "executed_runs": executed,
            "skipped_runs": skipped,
            "llm_calls": sum(int(value.get("llm_calls") or 0) for value in values),
            "no_effect_runs": no_effect,
            "no_effect_rate": round(no_effect / executed, 4) if executed else 0.0,
            "changed_slide_events": sum(int(value.get("changed_slide_count") or 0) for value in values),
            "latency_ms": round(sum(float(value.get("latency_ms") or 0.0) for value in values), 1),
        }
    return {"total_events": sum(len(values) for values in grouped.values()), "passes": passes}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python benchmarks/summarize_quality_passes.py path/to/application.log")
        return 2
    path = Path(sys.argv[1])
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    print(json.dumps(summarize(parse_events(lines)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
