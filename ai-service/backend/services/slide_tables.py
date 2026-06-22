"""Normalize và build table specs cho slide (PPTX + JSON spec)."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from services.images.validation import _write_debug_json as _write_debug_json_base
from services.slide_charts import chart_intent_from_slide
from services.visual_data_review import review_visual_data_specs
_MAX_COLS = 8
_MAX_DATA_ROWS = 12
_MAX_CELL_CHARS = 120
_COMPARISON_KEYWORDS = (
    "compare", "comparison", "versus", "vs", "before", "after", "pros",
    "cons", "criteria", "option", "alternative", "plan a", "plan b",
    "current", "target", "solution", "problem", "feature", "benefit",
    "cost", "risk", "impact", "priority", "status",
    "tieu chi", "hien trang", "giai phap", "truoc", "sau", "uu diem",
    "nhuoc diem", "phuong an", "so sanh",
)
_PAIR_LINE_RE = re.compile(r"^\s*([^:;\-–—]{2,48})\s*:\s*([^:]{2,})$")


def _fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "")).replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


_MD_SEPARATOR_RE = re.compile(r"^\s*:?-{2,}:?\s*$")
_NUMERIC_VALUE_RE = re.compile(
    r"^\s*[-+]?\d+(?:[.,]\d+)?\s*(?:%|/10|/100|diem|score|k|m|tr|trieu|ty)?\s*$",
    re.IGNORECASE,
)
_SENTENCE_END_RE = re.compile(r"[.!?。]\s*$")


def _slide_lines(slide: Dict[str, Any]) -> List[str]:
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        return [ln.strip() for ln in bullets.splitlines() if ln.strip()]
    return [str(b).strip() for b in bullets if str(b).strip()]


def _table_from_markdown_lines(lines: List[str]) -> Optional[Dict[str, Any]]:
    table_lines = [ln for ln in lines if ln.count("|") >= 2]
    if len(table_lines) < 2:
        return None
    rows: List[List[str]] = []
    for line in table_lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or all(_MD_SEPARATOR_RE.match(c or "") for c in cells):
            continue
        rows.append(cells)
    if len(rows) < 2:
        return None
    return normalize_table_spec({"title": "", "headers": rows[0], "rows": rows[1:]})


def _table_from_pair_lines(slide: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Build a key/value table only from explicit `key: value` bullet lines.

    Hyphens are common inside Vietnamese names and prose (for example Giơ-Ne),
    so they are intentionally not treated as table separators here.
    """
    slide_text = _fold_text(
        " ".join([str(slide.get("title") or "")] + _slide_lines(slide))
    )
    keyword_hits = sum(1 for kw in _COMPARISON_KEYWORDS if kw in slide_text)
    rows: List[List[str]] = []
    for line in _slide_lines(slide):
        m = _PAIR_LINE_RE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        key = key.strip()
        value = value.strip()
        key_folded = _fold_text(key)
        if key_folded.startswith(("goi y", "suggestion", "note", "ghi chu")):
            continue
        if len(key.split()) > 6:
            continue
        if key and value:
            rows.append([key, value])
    if len(rows) < 2:
        return None
    numeric_rows = sum(1 for row in rows if _NUMERIC_VALUE_RE.match(str(row[1] or "")))
    if rows and numeric_rows >= 2 and numeric_rows >= len(rows) - 1:
        return None
    if keyword_hits < 1 and len(rows) < 3:
        return None
    return normalize_table_spec(
        {
            "title": str(slide.get("title") or ""),
            "headers": ["Mục", "Nội dung"],
            "rows": rows,
        }
    )


def deterministic_table_spec_from_slide(slide: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return _table_from_markdown_lines(_slide_lines(slide)) or _table_from_pair_lines(slide)


def _raw_table_candidates(raw_content: str) -> List[Dict[str, Any]]:
    """Extract explicit markdown tables from the original user input.

    This preserves tables that the LLM may later rewrite into prose bullets.
    """
    lines = str(raw_content or "").splitlines()
    candidates: List[Dict[str, Any]] = []
    current_heading = ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#"):
            current_heading = line.lstrip("#").strip()
            i += 1
            continue
        if line.count("|") < 2:
            i += 1
            continue

        table_lines: List[str] = []
        start_i = i
        while i < len(lines) and lines[i].strip().count("|") >= 2:
            table_lines.append(lines[i].strip())
            i += 1

        spec = _table_from_markdown_lines(table_lines)
        if not spec:
            continue

        context_lines: List[str] = []
        j = i
        while j < len(lines):
            nxt = lines[j].strip()
            if nxt.startswith("#"):
                break
            if nxt:
                context_lines.append(nxt)
            j += 1
        context = _fold_text(" ".join([current_heading] + table_lines + context_lines[:4]))
        wants_table = any(k in context for k in ("bang", "table", "tao bang", "bang so sanh", "comparison table", "thong so ky thuat"))
        wants_chart = any(k in context for k in ("bieu do", "chart", "radar", "cot", "duong", "tron", "pie", "bar", "line"))
        if wants_chart and not wants_table:
            continue
        if not wants_table:
            continue

        if current_heading:
            spec["title"] = current_heading
        candidates.append(
            {
                "source": "raw_markdown",
                "heading": current_heading,
                "context": context,
                "spec": spec,
                "start_line": start_i,
            }
        )
    return candidates


def _slide_match_score(slide: Dict[str, Any], candidate: Dict[str, Any]) -> int:
    spec = candidate.get("spec") or {}
    slide_text = _fold_text(
        " ".join(
            [str(slide.get("title") or "")]
            + [str(x) for x in (slide.get("bullets") or slide.get("content") or [])]
        )
    )
    score = 0
    heading = _fold_text(str(candidate.get("heading") or ""))
    if heading and any(tok in slide_text for tok in heading.split() if len(tok) >= 4):
        score += 2
    for h in spec.get("headers") or []:
        hf = _fold_text(str(h))
        if hf and hf in slide_text:
            score += 2
    for row in (spec.get("rows") or [])[:8]:
        if not row:
            continue
        first = _fold_text(str(row[0]))
        if first and first in slide_text:
            score += 2
        for cell in row[1:4]:
            cf = _fold_text(str(cell))
            if cf and cf in slide_text:
                score += 1
    return score


def normalize_table_spec(raw: Any) -> Optional[Dict[str, Any]]:
    """Chuẩn hóa spec bảng từ dict (LLM hoặc JSON client). Trả None nếu không hợp lệ."""
    if not isinstance(raw, dict):
        return None
    headers_raw = raw.get("headers")
    rows_raw = raw.get("rows")
    if not isinstance(headers_raw, list) or not isinstance(rows_raw, list):
        return None
    headers = [str(h).strip()[:60] for h in headers_raw if str(h).strip()]
    if len(headers) < 2:
        return None
    headers = headers[:_MAX_COLS]
    ncols = len(headers)
    rows: List[List[str]] = []
    for row in rows_raw:
        if not isinstance(row, (list, tuple)):
            continue
        cells = [str(c).strip()[:_MAX_CELL_CHARS] for c in row[:ncols]]
        while len(cells) < ncols:
            cells.append("")
        rows.append(cells[:ncols])
        if len(rows) >= _MAX_DATA_ROWS:
            break
    if len(rows) < 1:
        return None
    title = str(raw.get("title") or "").strip()[:100]
    return {
        "title": title,
        "headers": headers,
        "rows": rows,
    }


def _table_spec_has_text_evidence(spec: Dict[str, Any], text: str) -> bool:
    """Generic table gate: headers/row anchors must be supported by source text."""
    if not isinstance(spec, dict):
        return False
    headers = [str(h).strip() for h in (spec.get("headers") or []) if str(h).strip()]
    rows = spec.get("rows") or []
    if len(headers) < 2 or not isinstance(rows, list) or len(rows) < 1:
        return False
    folded = _fold_text(text)
    header_hits = sum(1 for h in headers if _fold_text(h) and _fold_text(h) in folded)
    first_col_hits = 0
    compact_cells = 0
    total_cells = 0
    sentence_like_cells = 0
    for row in rows[:8]:
        if not isinstance(row, (list, tuple)) or not row:
            continue
        first = _fold_text(str(row[0] or ""))
        if first and (first in folded or any(tok in folded for tok in first.split() if len(tok) >= 3)):
            first_col_hits += 1
        for cell in row[: len(headers)]:
            cell_text = str(cell or "").strip()
            if not cell_text:
                continue
            total_cells += 1
            if len(cell_text) <= _MAX_CELL_CHARS:
                compact_cells += 1
            if len(cell_text.split()) >= 12 or _SENTENCE_END_RE.search(cell_text):
                sentence_like_cells += 1
    if total_cells == 0:
        return False
    if sentence_like_cells > max(2, total_cells // 2):
        return False
    has_grid = "|" in text and text.count("|") >= 4
    return has_grid or first_col_hits >= min(2, len(rows)) or header_hits >= min(2, len(headers))


def normalize_table_spec_from_slide(slide: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Đọc `slide['table']` nếu client gửi kèm deck JSON."""
    t = slide.get("table")
    if isinstance(t, dict):
        return normalize_table_spec(t)
    return None


def slide_has_table_or_body(slide: Dict[str, Any]) -> bool:
    """Slide có nội dung render được (bullet / content / bảng)."""
    if not isinstance(slide, dict):
        return False
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str) and bullets.strip():
        return True
    if isinstance(bullets, list) and any(str(b).strip() for b in bullets):
        return True
    return normalize_table_spec_from_slide(slide) is not None


def _looks_like_table_slide(slide: Dict[str, Any]) -> bool:
    """Heuristic: markdown pipe hoặc nhiều dòng có | giống bảng."""
    if normalize_table_spec_from_slide(slide):
        return False
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        lines = [ln.strip() for ln in bullets.splitlines() if ln.strip()]
    else:
        lines = [str(b).strip() for b in bullets if str(b).strip()]
    if len(lines) < 2:
        return False
    pipe_lines = sum(1 for ln in lines if ln.count("|") >= 2)
    if pipe_lines >= 2:
        return True
    if re.search(r"^\s*\|.+\|\s*$", lines[0]) and pipe_lines >= 1:
        return True
    text = _fold_text(" ".join(lines))
    keyword_hits = sum(1 for kw in _COMPARISON_KEYWORDS if kw in text)
    pair_lines = sum(1 for ln in lines if _PAIR_LINE_RE.search(ln))
    repeated_separators = sum(1 for ln in lines if ln.count(":") >= 2 or ln.count(";") >= 2)
    if keyword_hits >= 2 and (len(lines) >= 3 or pair_lines >= 2):
        return True
    if pair_lines >= 3 and keyword_hits >= 1:
        return True
    if repeated_separators >= 2 and keyword_hits >= 1:
        return True
    return False


def _write_debug_json(task_id: str, records: list[Dict[str, Any]]) -> None:
    _write_debug_json_base(task_id, "tables", records)


async def build_table_specs_for_slides(
    content_extractor,
    structured: Dict[str, Any],
    *,
    task_id: str = "",
    should_stop: Optional[Any] = None,
    raw_content: str = "",
) -> Dict[int, Dict[str, Any]]:
    """{slide_index: table spec} — ưu tiên `slide.table` từ JSON; không thì LLM khi giống bảng."""
    slides = structured.get("slides") or []
    if not slides:
        return {}

    if structured.get("_explicit_slide_mode"):
        out: Dict[int, Dict[str, Any]] = {}
        debug_records: list[Dict[str, Any]] = []
        for idx, slide in enumerate(slides):
            if not isinstance(slide, dict):
                continue
            inline = normalize_table_spec_from_slide(slide)
            if not inline:
                continue
            out[idx] = inline
            debug_records.append(
                {
                    "slide_index": idx,
                    "title": str(slide.get("title") or ""),
                    "source": "explicit_inline_table",
                    "spec": inline,
                    "status": "created",
                }
            )
            print(f"[slide_tables] slide {idx} table: explicit inline {len(inline['rows'])} row(s)")
        if task_id:
            _write_debug_json(task_id, debug_records)
        return out

    out: Dict[int, Dict[str, Any]] = {}
    debug_records: list[Dict[str, Any]] = []

    raw_candidates = _raw_table_candidates(raw_content)
    assigned_raw: Set[int] = set()
    if raw_candidates:
        used_slides: Set[int] = set()
        for cand_idx, candidate in enumerate(raw_candidates):
            best_idx = -1
            best_score = 0
            for idx, slide in enumerate(slides):
                if idx in used_slides or not isinstance(slide, dict):
                    continue
                score = _slide_match_score(slide, candidate)
                if score > best_score:
                    best_score = score
                    best_idx = idx
            if best_idx < 0 or best_score < 1:
                debug_records.append(
                    {
                        "slide_index": None,
                        "title": str(candidate.get("heading") or ""),
                        "source": "raw_markdown",
                        "spec": candidate.get("spec"),
                        "status": "unmatched",
                        "match_score": best_score,
                    }
                )
                continue
            spec = candidate.get("spec")
            evidence_text = " ".join([
                str(candidate.get("heading") or ""),
                str(candidate.get("context") or ""),
                " ".join(_slide_lines(slides[best_idx])),
                raw_content[:5000],
            ])
            if not isinstance(spec, dict) or not _table_spec_has_text_evidence(spec, evidence_text):
                debug_records.append(
                    {
                        "slide_index": best_idx,
                        "title": str((slides[best_idx] or {}).get("title") or candidate.get("heading") or ""),
                        "source": "raw_markdown",
                        "spec": spec,
                        "status": "no_text_evidence",
                        "match_score": best_score,
                    }
                )
                continue
            out[best_idx] = spec
            used_slides.add(best_idx)
            assigned_raw.add(best_idx)
            debug_records.append(
                {
                    "slide_index": best_idx,
                    "title": str((slides[best_idx] or {}).get("title") or candidate.get("heading") or ""),
                    "source": "raw_markdown",
                    "spec": spec,
                    "status": "created",
                    "match_score": best_score,
                }
            )
            print(f"[slide_tables] slide {best_idx} table: raw markdown {len(spec['rows'])} row(s)")

    for idx, slide in enumerate(slides):
        if should_stop is not None and await should_stop():
            break
        if not isinstance(slide, dict):
            continue
        if idx in assigned_raw:
            continue
        if chart_intent_from_slide(slide):
            continue
        inline = normalize_table_spec_from_slide(slide)
        if inline:
            out[idx] = inline
            debug_records.append(
                {
                    "slide_index": idx,
                    "title": str(slide.get("title") or ""),
                    "source": "inline_json",
                    "spec": inline,
                    "status": "created",
                }
            )
            print(f"[slide_tables] slide {idx} table: inline {len(inline['rows'])} row(s)")
            continue

        deterministic = deterministic_table_spec_from_slide(slide)
        if deterministic and _table_spec_has_text_evidence(deterministic, " ".join(_slide_lines(slide) + [raw_content[:2500]])):
            out[idx] = deterministic
            debug_records.append(
                {
                    "slide_index": idx,
                    "title": str(slide.get("title") or ""),
                    "source": "deterministic",
                    "spec": deterministic,
                    "status": "created",
                }
            )
            print(f"[slide_tables] slide {idx} table: deterministic {len(deterministic['rows'])} row(s)")
            continue

        # If the original prompt already contained explicit markdown tables, avoid
        # asking the LLM to invent additional comparison tables from prose-only
        # slides. Inline/deterministic tables above still pass through.
        if raw_candidates:
            continue

        if not _looks_like_table_slide(slide):
            continue
        if not hasattr(content_extractor, "extract_table_spec"):
            continue
        raw = await content_extractor.extract_table_spec({"slide": slide})
        spec = normalize_table_spec(raw)
        if spec and not _table_spec_has_text_evidence(spec, " ".join(_slide_lines(slide) + [raw_content[:2500]])):
            spec = None
        rec = {
            "slide_index": idx,
            "title": str(slide.get("title") or ""),
            "source": "llm",
            "raw": raw,
            "spec": spec,
            "status": "created" if spec else "invalid_or_empty",
        }
        debug_records.append(rec)
        if spec:
            out[idx] = spec
            print(f"[slide_tables] slide {idx} table: llm {len(spec['rows'])} row(s)")

    out, debug_records = await review_visual_data_specs(
        content_extractor,
        structured,
        out,
        debug_records,
        kind="table",
        raw_content=raw_content,
    )

    if task_id:
        _write_debug_json(task_id, debug_records)
    return out
