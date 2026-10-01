"""Offline benchmark scorer; it never calls an LLM.

Usage: python benchmarks/evaluate.py CASE_ID path/to/result.json
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path


def fold(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = unicodedata.normalize("NFD", text.lower())
    return re.sub(r"[\u0300-\u036f]", "", text).replace("đ", "d")


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python benchmarks/evaluate.py CASE_ID result.json")
        return 2
    cases = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
    case = next((item for item in cases if item["id"] == sys.argv[1]), None)
    if case is None:
        print(f"Unknown case: {sys.argv[1]}")
        return 2
    result = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    slides = result.get("slides") or []
    searchable = fold(result)
    coverage = {term: fold(term) in searchable for term in case.get("must_cover", [])}
    preservation = {term: str(term) in json.dumps(result, ensure_ascii=False) for term in case.get("must_preserve", [])}
    report = {
        "case_id": case["id"],
        "slide_count": len(slides),
        "target_slides": case["target_slides"],
        "slide_count_exact": len(slides) == case["target_slides"],
        "empty_slides": sum(not (s.get("title") and (s.get("bullets") or s.get("table") or s.get("chart"))) for s in slides if isinstance(s, dict)),
        "coverage": coverage,
        "preservation": preservation,
        "presentation_mode_ok": not case.get("expected_presentation_mode") or result.get("presentation_mode") == case["expected_presentation_mode"],
        "llm_calls": (
            len(result["_llm_call_ledger"])
            if isinstance(result.get("_llm_call_ledger"), list)
            else None
        ),
        "source_faithfulness_assessed": False,
    }
    report["passed_static_checks"] = (
        report["slide_count_exact"]
        and report["empty_slides"] == 0
        and all(coverage.values())
        and all(preservation.values())
        and report["presentation_mode_ok"]
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["passed_static_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
