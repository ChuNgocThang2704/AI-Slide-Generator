"""Build editable chart specs for data-heavy slides."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from services.visual_data_review import review_visual_data_specs

_DATA_KEYWORDS = (
    "%", "percent", "tỷ lệ", "ty le", "kpi", "metric", "statistics",
    "thống kê", "thong ke", "số liệu", "so lieu", "growth", "tăng trưởng",
    "doanh thu", "revenue", "chi phí", "cost", "profit", "lợi nhuận",
)
_DEBUG_DIR = Path("outputs") / "debug"
_DATA_KEYWORDS = _DATA_KEYWORDS + (
    "ratio", "rate", "score", "survey", "quantity", "count", "volume",
    "users", "students", "customers", "satisfaction", "baseline",
)
_CATEGORY_NUMBER_RE = re.compile(
    r"(?:^|[.;,\n\-])\s*([^\d:;,\n]{2,48}?)\s*(?:[:=\-])\s*"
    r"[-+]?\d+(?:[.,]\d+)?\s*(?:%|k|m|trieu|ty|nghin)?",
    re.IGNORECASE,
)
_TIME_VALUE_RE = re.compile(
    r"\b(?:19|20)\d{2}\b\s*[:=\-]?\s*[-+]?\d+(?:[.,]\d+)?"
    r"|\b(?:q[1-4]|quy\s*[1-4]|thang\s*\d{1,2})\b\s*[:=\-]?\s*[-+]?\d+(?:[.,]\d+)?",
    re.IGNORECASE,
)
_MD_SEPARATOR_RE = re.compile(r"^\s*:?-{2,}:?\s*$")
_NUMERIC_TOKEN_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)*(?:\s*%|\s*/\s*\d+)?", re.IGNORECASE)


def _fold_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or "")).replace("đ", "d").replace("Đ", "D")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _slide_context(slide: Dict[str, Any], max_chars: int = 700) -> str:
    title = str(slide.get("title") or "").strip()
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        points = [bullets.strip()]
    else:
        points = [str(b).strip() for b in bullets[:6] if str(b).strip()]
    return ". ".join([title] + points)[:max_chars]


def chart_intent_from_slide(slide: Dict[str, Any]) -> Optional[str]:
    text = _slide_context(slide, max_chars=1200).lower()
    if not any(k in text for k in ("chart", "biểu đồ", "bieu do", "graph")):
        return None
    if any(k in text for k in ("tròn", "tron", "pie", "thị phần", "thi phan")):
        return "pie"
    if any(k in text for k in ("đường", "duong", "line", "xu hướng", "trend")):
        return "line"
    if any(k in text for k in ("cột", "cot", "column", "bar")):
        return "bar"
    return "bar"


def chart_intent_from_slide(slide: Dict[str, Any]) -> Optional[str]:
    text = _fold_text(_slide_context(slide, max_chars=1200))
    if not any(k in text for k in ("chart", "bieu do", "graph")):
        return None
    if any(k in text for k in ("tron", "pie", "thi phan")):
        return "pie"
    if any(k in text for k in ("duong", "line", "xu huong", "trend")):
        return "line"
    if any(k in text for k in ("cot", "column", "bar")):
        return "bar"
    if "radar" in text:
        return "radar"
    return "bar"


def _parse_markdown_table(slide: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        lines = [ln.strip() for ln in bullets.splitlines() if ln.strip()]
    else:
        lines = [str(b).strip() for b in bullets if str(b).strip()]
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
    headers = rows[0]
    body = rows[1:]
    if len(headers) < 2 or not body:
        return None
    return {"headers": headers, "rows": body}


def _looks_like_data_slide(slide: Dict[str, Any]) -> bool:
    text = _slide_context(slide).lower()
    has_keyword = any(kw in text for kw in _DATA_KEYWORDS)
    number_count = len(re.findall(r"[-+]?\d+(?:[.,]\d+)?\s*%?", text))
    if has_keyword and number_count >= 2:
        return True
    if text.count("%") >= 2:
        return True
    if len(_CATEGORY_NUMBER_RE.findall(text)) >= 2:
        return True
    if len(_TIME_VALUE_RE.findall(text)) >= 2:
        return True
    return False


def _has_comparable_numeric_evidence(text: str) -> bool:
    """Generic chart gate: at least two numeric facts tied to nearby labels."""
    folded = _fold_text(text)
    if folded.count("|") >= 4:
        return True
    if len(_CATEGORY_NUMBER_RE.findall(folded)) >= 2:
        return True
    if len(_TIME_VALUE_RE.findall(folded)) >= 2:
        return True
    return len(_NUMERIC_TOKEN_RE.findall(folded)) >= 3 and any(
        token in folded for token in ("%", "ty le", "score", "diem", "doanh", "chi phi", "kpi", "growth", "rate")
    )


def _chart_spec_has_text_evidence(spec: Dict[str, Any], text: str) -> bool:
    """Validate that labels and numeric values are supported by the slide/raw text."""
    folded = _fold_text(text)
    folded_numeric = re.sub(r"[^\d%.,/\-+]", " ", folded)
    compact_numeric = re.sub(r"[^\d]", "", folded)
    labels = [str(x) for x in (spec.get("labels") or []) if str(x).strip()]
    values = spec.get("values") or []
    if len(labels) < 2 or len(values) < 2:
        return False
    label_hits = 0
    for label in labels[:8]:
        lf = _fold_text(label)
        if lf and (lf in folded or any(tok in folded for tok in lf.split() if len(tok) >= 3)):
            label_hits += 1
    numeric_hits = 0
    for value in values[:8]:
        value_text = str(value)
        parsed = _parse_float_cell(value_text)
        if parsed is None:
            continue
        candidates = {str(int(parsed)) if float(parsed).is_integer() else str(parsed).rstrip("0").rstrip(".")}
        if 0 < parsed < 1 and spec.get("is_percent"):
            candidates.add(str(int(round(parsed * 100))))
        if any(
            c and (c in folded_numeric or c.replace(".", "").replace(",", "") in compact_numeric)
            for c in candidates
        ):
            numeric_hits += 1
    return label_hits >= min(2, len(labels)) and numeric_hits >= min(2, len(values))


_ALLOWED_CHART_TYPES = frozenset(
    {
        "bar",
        "column",
        "line",
        "pie",
        "area",
        "doughnut",
        "column_stacked",
        "column_stacked_100",
        "bar_horizontal",
        "bar_stacked",
        "bar_stacked_100",
        "area_stacked",
        "line_smooth",
        "radar",
    }
)
_MAX_CATEGORIES = 12
_MAX_SERIES = 5


def _parse_float_cell(v: Any) -> Optional[float]:
    text = str(v or "").strip().replace("%", "")
    match = re.search(r"[-+]?\d+(?:[.,]\d+)*", text)
    if not match:
        return None
    raw = match.group(0)
    if "." in raw and "," in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "." in raw:
        parts = raw.split(".")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            raw = "".join(parts)
    elif "," in raw:
        parts = raw.split(",")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            raw = "".join(parts)
        else:
            raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _chart_from_markdown_table(slide: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    table = _parse_markdown_table(slide)
    if not table:
        return None
    headers = [str(h).strip() for h in table["headers"]]
    rows = table["rows"]
    best_col = -1
    best_values: List[float] = []
    best_raw: List[str] = []
    for col in range(1, min(len(headers), 5)):
        values: List[float] = []
        raw_values: List[str] = []
        for row in rows[:_MAX_CATEGORIES]:
            if len(row) <= col:
                continue
            value = _parse_float_cell(row[col])
            if value is None:
                continue
            values.append(value)
            raw_values.append(str(row[col]))
        if len(values) > len(best_values):
            best_col = col
            best_values = values
            best_raw = raw_values
    if best_col < 1 or len(best_values) < 2:
        return None

    labels = [str(row[0]).strip()[:38] for row in rows[: len(best_values)] if row and str(row[0]).strip()]
    if len(labels) < 2:
        return None
    values = best_values[: len(labels)]
    header = headers[best_col] if best_col < len(headers) else "Data"
    context = _slide_context(slide, max_chars=1200).lower()
    is_percent = "%" in " ".join(best_raw) or any(k in str(header).lower() for k in ("%", "percent", "tăng", "growth", "rate", "ratio"))
    chart_type = chart_intent_from_slide(slide) or ("pie" if any(k in context for k in ("thị phần", "thi phan")) else "bar")
    return normalize_chart_spec(
        {
            "title": str(slide.get("title") or header or "Data overview"),
            "chart_type": chart_type,
            "labels": labels,
            "values": values,
            "unit": "percent" if is_percent else "number",
            "is_percent": is_percent,
        }
    )


def _pair_chart_from_lines(title: str, lines: List[str], chart_type: str) -> Optional[Dict[str, Any]]:
    labels: List[str] = []
    values: List[float] = []
    raw_values: List[str] = []
    for line in lines:
        s = str(line or "").strip().lstrip("-• ").strip()
        if ":" not in s:
            continue
        label, value_text = s.split(":", 1)
        label = label.strip()
        value_text = value_text.strip()
        if not label or not value_text:
            continue
        if _fold_text(label).startswith(("goi y", "suggestion")):
            continue
        value = _parse_float_cell(value_text)
        if value is None:
            continue
        labels.append(label[:38])
        values.append(value)
        raw_values.append(value_text)
        if len(labels) >= _MAX_CATEGORIES:
            break
    if len(labels) < 2:
        return None
    is_percent = "%" in " ".join(raw_values)
    return normalize_chart_spec(
        {
            "title": title or "Data overview",
            "chart_type": chart_type or "bar",
            "labels": labels,
            "values": values,
            "unit": "percent" if is_percent else "number",
            "is_percent": is_percent,
        }
    )


def _raw_chart_candidates(raw_content: str) -> List[Dict[str, Any]]:
    lines = str(raw_content or "").splitlines()
    candidates: List[Dict[str, Any]] = []
    current_heading = ""
    section_lines: List[str] = []

    def flush_section() -> None:
        if not section_lines:
            return
        context = _fold_text(" ".join([current_heading] + section_lines))
        fake_slide = {"title": current_heading, "content": "\n".join(section_lines)}
        chart_type = chart_intent_from_slide(fake_slide)

        i = 0
        while i < len(section_lines):
            if section_lines[i].strip().count("|") < 2:
                i += 1
                continue
            table_lines: List[str] = []
            while i < len(section_lines) and section_lines[i].strip().count("|") >= 2:
                table_lines.append(section_lines[i].strip())
                i += 1
            table_context = _fold_text(" ".join([current_heading] + table_lines + section_lines[i:i + 4]))
            if not any(k in table_context for k in ("bieu do", "chart", "graph", "radar", "cot", "tron", "duong", "pie", "bar", "line")):
                continue
            spec = _chart_from_markdown_table({"title": current_heading, "content": "\n".join(table_lines + section_lines[i:i + 4])})
            if spec:
                candidates.append({"source": "raw_markdown", "heading": current_heading, "context": table_context, "spec": spec})

        spec = _pair_chart_from_lines(current_heading, section_lines, chart_type or "bar")
        if spec and (chart_type or len(spec.get("labels") or []) >= 2):
            candidates.append({"source": "raw_pairs", "heading": current_heading, "context": context, "spec": spec})

    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("#"):
            flush_section()
            current_heading = line.lstrip("#").strip()
            section_lines = []
            continue
        if line:
            section_lines.append(line)
    flush_section()
    return candidates


def _raw_has_table_only_intent(raw_content: str) -> bool:
    folded = _fold_text(raw_content or "")
    if folded.count("|") < 4:
        return False
    wants_table = any(k in folded for k in ("tao bang", "bang so sanh", "comparison table", "table", "thong so ky thuat"))
    wants_chart = any(k in folded for k in ("bieu do", "chart", "graph", "radar", "cot", "duong", "tron", "pie", "bar", "line"))
    return wants_table and not wants_chart


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
    for label in spec.get("labels") or []:
        lf = _fold_text(str(label))
        if lf and lf in slide_text:
            score += 2
    for value in spec.get("values") or []:
        vf = str(value)
        if vf and vf in slide_text:
            score += 1
    return score


def normalize_chart_spec(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    labels_raw = raw.get("labels") or []
    if not isinstance(labels_raw, list):
        return None
    labels = [str(x).strip()[:38] for x in labels_raw if str(x).strip()]
    if len(labels) < 2:
        return None
    labels = labels[:_MAX_CATEGORIES]

    is_percent = bool(raw.get("is_percent")) or str(raw.get("unit") or "").lower() == "percent"

    series_out: List[Dict[str, Any]] = []
    series_raw = raw.get("series")
    if isinstance(series_raw, list) and series_raw:
        for item in series_raw[:_MAX_SERIES]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "Series").strip()[:40]
            vals_raw = item.get("values") or []
            if not isinstance(vals_raw, list):
                continue
            vals: List[float] = []
            for v in vals_raw:
                f = _parse_float_cell(v)
                if f is None:
                    continue
                vals.append(f)
            n = min(len(labels), len(vals))
            if n < 2:
                continue
            vals = vals[:n]
            if is_percent:
                vals = [x / 100.0 if x > 1 else x for x in vals]
            series_out.append({"name": name, "values": vals})
    else:
        values_raw = raw.get("values") or []
        if not isinstance(values_raw, list):
            return None
        values: List[float] = []
        for value in values_raw:
            f = _parse_float_cell(value)
            if f is None:
                continue
            values.append(f)
        n = min(len(labels), len(values))
        if n < 2:
            return None
        values = values[:n]
        if is_percent:
            values = [v / 100.0 if v > 1 else v for v in values]
        sname = str(raw.get("series_name") or raw.get("title") or "Data").strip()[:40] or "Data"
        series_out.append({"name": sname, "values": values})

    if not series_out:
        return None

    n_cat = min(len(labels), min(len(s["values"]) for s in series_out))
    if n_cat < 2:
        return None
    labels = labels[:n_cat]
    for s in series_out:
        s["values"] = s["values"][:n_cat]

    chart_type = str(raw.get("chart_type") or "bar").strip().lower().replace(" ", "_")
    if chart_type == "column":
        chart_type = "bar"
    if chart_type not in _ALLOWED_CHART_TYPES:
        chart_type = "bar"

    if chart_type in {"pie", "doughnut"} and len(series_out) > 1:
        series_out = [series_out[0]]

    title = str(raw.get("title") or "Data overview").strip()[:80]
    primary_values = series_out[0]["values"]
    return {
        "title": title,
        "chart_type": chart_type,
        "labels": labels,
        "series": series_out,
        "values": primary_values,
        "unit": str(raw.get("unit") or ("percent" if is_percent else "number")).strip().lower(),
        "is_percent": is_percent,
    }


def _write_debug_json(task_id: str, records: list[Dict[str, Any]]) -> None:
    if not records:
        return
    try:
        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        path = _DEBUG_DIR / f"{task_id}_charts.json"
        path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[slide_charts] debug metadata: {path}")
    except Exception as e:
        print(f"[slide_charts] debug metadata error: {e}")


def _write_quality_report(task_id: str, records: list[Dict[str, Any]]) -> None:
    if not records:
        return
    try:
        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        statuses: Dict[str, int] = {}
        chart_types: Dict[str, int] = {}
        point_counts = []
        for record in records:
            status = str(record.get("status") or "unknown")
            statuses[status] = statuses.get(status, 0) + 1
            spec = record.get("spec") or {}
            if isinstance(spec, dict):
                chart_type = str(spec.get("chart_type") or "unknown")
                chart_types[chart_type] = chart_types.get(chart_type, 0) + 1
                labels = spec.get("labels") or []
                if isinstance(labels, list):
                    point_counts.append(len(labels))

        report = {
            "task_id": task_id,
            "total_data_candidates": len(records),
            "statuses": statuses,
            "created_charts": statuses.get("created", 0),
            "invalid_or_empty": statuses.get("invalid_or_empty", 0),
            "chart_types": chart_types,
            "avg_points_per_chart": round(sum(point_counts) / len(point_counts), 2)
            if point_counts
            else None,
            "invalid_records": [
                {
                    "slide_index": r.get("slide_index"),
                    "title": r.get("title"),
                    "raw": r.get("raw"),
                }
                for r in records
                if r.get("status") != "created"
            ],
        }
        path = _DEBUG_DIR / f"{task_id}_chart_quality.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[slide_charts] quality report: {path}")
    except Exception as e:
        print(f"[slide_charts] quality report error: {e}")


def _user_chart_from_slide(slide: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    c = slide.get("chart")
    if isinstance(c, dict):
        return normalize_chart_spec(c)
    return None


async def build_chart_specs_for_slides(
    content_extractor,
    structured: Dict[str, Any],
    *,
    task_id: str = "",
    should_stop: Optional[Any] = None,
    table_indices: Optional[Set[int]] = None,
    raw_content: str = "",
) -> Dict[int, Dict[str, Any]]:
    """Return {slide_index: editable chart spec} for data-heavy slides."""
    slides = structured.get("slides") or []
    if not slides:
        return {}

    if structured.get("_explicit_slide_mode"):
        out: Dict[int, Dict[str, Any]] = {}
        debug_records: list[Dict[str, Any]] = []
        for idx, slide in enumerate(slides):
            if not isinstance(slide, dict):
                continue
            user = _user_chart_from_slide(slide)
            if not user:
                continue
            out[idx] = user
            debug_records.append(
                {
                    "slide_index": idx,
                    "title": str(slide.get("title") or ""),
                    "context": "explicit_inline_chart",
                    "raw": slide.get("chart"),
                    "spec": user,
                    "status": "created",
                }
            )
            print(f"[slide_charts] slide {idx} chart: explicit inline {user['chart_type']} {len(user['labels'])} point(s)")
        if task_id:
            _write_debug_json(task_id, debug_records)
            _write_quality_report(task_id, debug_records)
        return out

    skip: Set[int] = set(table_indices or ())

    out: Dict[int, Dict[str, Any]] = {}
    debug_records: list[Dict[str, Any]] = []
    assigned_raw: Set[int] = set()

    raw_candidates = _raw_chart_candidates(raw_content)
    if not raw_candidates and _raw_has_table_only_intent(raw_content):
        if task_id:
            _write_debug_json(task_id, [])
            _write_quality_report(task_id, [])
        return {}
    if raw_candidates:
        used_slides: Set[int] = set()
        for cand_idx, candidate in enumerate(raw_candidates):
            best_idx = -1
            best_score = 0
            for idx, slide in enumerate(slides):
                if idx in used_slides or idx in skip or not isinstance(slide, dict):
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
                        "context": candidate.get("context"),
                        "raw": candidate,
                        "spec": candidate.get("spec"),
                        "status": "unmatched",
                    }
                )
                continue
            spec = candidate.get("spec")
            evidence_text = " ".join([
                str(candidate.get("heading") or ""),
                str(candidate.get("context") or ""),
                _slide_context(slides[best_idx], max_chars=1200),
                raw_content[:4000],
            ])
            if not isinstance(spec, dict) or not _chart_spec_has_text_evidence(spec, evidence_text):
                debug_records.append(
                    {
                        "slide_index": best_idx,
                        "title": str((slides[best_idx] or {}).get("title") or candidate.get("heading") or ""),
                        "context": candidate.get("context"),
                        "raw": candidate,
                        "spec": spec,
                        "status": "no_text_evidence",
                        "match_score": best_score,
                    }
                )
                continue
            out[best_idx] = spec
            assigned_raw.add(best_idx)
            used_slides.add(best_idx)
            debug_records.append(
                {
                    "slide_index": best_idx,
                    "title": str((slides[best_idx] or {}).get("title") or candidate.get("heading") or ""),
                    "context": candidate.get("context"),
                    "raw": candidate,
                    "spec": spec,
                    "status": "created",
                    "match_score": best_score,
                }
            )
            print(f"[slide_charts] slide {best_idx} chart: raw {spec['chart_type']} {len(spec['labels'])} point(s)")

    for idx, slide in enumerate(slides):
        if should_stop is not None and await should_stop():
            break
        if not isinstance(slide, dict):
            continue
        if idx in assigned_raw:
            continue

        user = _user_chart_from_slide(slide)
        if user:
            out[idx] = user
            debug_records.append(
                {
                    "slide_index": idx,
                    "title": str(slide.get("title") or ""),
                    "context": "user_json",
                    "raw": slide.get("chart"),
                    "spec": user,
                    "status": "created",
                }
            )
            print(
                f"[slide_charts] slide {idx} chart: user {user['chart_type']} "
                f"{len(user['labels'])} cat, {len(user.get('series') or [])} series"
            )
            continue

        markdown_chart = _chart_from_markdown_table(slide)
        if markdown_chart and (idx not in skip or chart_intent_from_slide(slide)):
            out[idx] = markdown_chart
            debug_records.append(
                {
                    "slide_index": idx,
                    "title": str(slide.get("title") or ""),
                    "context": "markdown_table",
                    "raw": _parse_markdown_table(slide),
                    "spec": markdown_chart,
                    "status": "created",
                }
            )
            print(
                f"[slide_charts] slide {idx} chart: markdown {markdown_chart['chart_type']} "
                f"{len(markdown_chart['labels'])} point(s)"
            )
            continue

        if idx in skip:
            continue
        if raw_candidates:
            continue

        pair_chart = _pair_chart_from_lines(
            str(slide.get("title") or ""),
            [str(x) for x in (slide.get("bullets") or slide.get("content") or [])]
            if not isinstance(slide.get("bullets") or slide.get("content") or [], str)
            else str(slide.get("bullets") or slide.get("content") or "").splitlines(),
            chart_intent_from_slide(slide) or "bar",
        )
        if pair_chart:
            out[idx] = pair_chart
            debug_records.append(
                {
                    "slide_index": idx,
                    "title": str(slide.get("title") or ""),
                    "context": "pair_lines",
                    "raw": _slide_context(slide),
                    "spec": pair_chart,
                    "status": "created",
                }
            )
            print(
                f"[slide_charts] slide {idx} chart: pairs {pair_chart['chart_type']} "
                f"{len(pair_chart['labels'])} point(s)"
            )
            continue

        if not hasattr(content_extractor, "extract_chart_spec"):
            continue
        context = _slide_context(slide)
        if not _has_comparable_numeric_evidence(" ".join([context, raw_content[:1200]])):
            continue
        raw = await content_extractor.extract_chart_spec(
            {"context": context, "slide": slide}
        )
        spec = normalize_chart_spec(raw)
        if spec and not _chart_spec_has_text_evidence(spec, " ".join([context, raw_content[:4000]])):
            spec = None
        debug_record: Dict[str, Any] = {
            "slide_index": idx,
            "title": str(slide.get("title") or ""),
            "context": context,
            "raw": raw,
            "spec": spec,
            "status": "created" if spec else "invalid_or_empty",
        }
        debug_records.append(debug_record)
        if spec:
            out[idx] = spec
            print(
                f"[slide_charts] slide {idx} chart: "
                f"{spec['chart_type']} {len(spec['labels'])} point(s)"
            )
    out, debug_records = await review_visual_data_specs(
        content_extractor,
        structured,
        out,
        debug_records,
        kind="chart",
        raw_content=raw_content,
    )

    if task_id:
        _write_debug_json(task_id, debug_records)
        _write_quality_report(task_id, debug_records)
    return out
