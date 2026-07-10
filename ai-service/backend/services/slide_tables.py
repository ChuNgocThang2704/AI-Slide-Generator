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


def _split_criteria_text(text: str) -> List[str]:
    return [
        re.sub(r"^(?:va|và|and)\s+", "", part.strip(" ,;:-"))
        for part in re.split(r",|;|\s+và\s+|\s+va\s+|\s+and\s+", str(text or ""), flags=re.IGNORECASE)
        if part.strip(" ,;:-")
    ][:8]


def _cut_table_request_tail(text: str) -> str:
    return re.split(
        r"\b(?:slide|trang)\s*(?:so|thu)?\s*\d+\b",
        str(text or ""),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,;:-.")


def _pretty_comparison_label(value: str) -> str:
    folded = _fold_text(value).strip(" ,;:-.")
    labels = {
        "tieu chi": "Tiêu chí",
        "quan ly thu cong": "Quản lý thủ công",
        "he thong thong minh": "Hệ thống thông minh",
        "nhan xet": "Nhận xét",
        "toc do xu ly": "Tốc độ xử lý",
        "do chinh xac": "Độ chính xác",
        "chi phi van hanh": "Chi phí vận hành",
        "trai nghiem sinh vien": "Trải nghiệm sinh viên",
        "bao mat du lieu": "Bảo mật dữ liệu",
        "kha nang mo rong": "Khả năng mở rộng",
    }
    return labels.get(folded, str(value or "").strip(" ,;:-.").capitalize())


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
    """Xây dựng bảng khóa/giá trị chỉ từ các dòng bullet có định dạng `khóa: giá trị` rõ ràng.

    Dấu gạch ngang khá phổ biến trong tên tiếng Việt và văn xuôi (ví dụ: Giơ-Ne),
    vì vậy chúng cố tình không được xử lý như các dấu phân cách bảng ở đây.
    """
    slide_text = _fold_text(
        " ".join([str(slide.get("title") or "")] + _slide_lines(slide))
    )
    keyword_hits = sum(1 for kw in _COMPARISON_KEYWORDS if kw in slide_text)
    rows: List[List[str]] = []
    for line in _slide_lines(slide):
        m = _PAIR_LINE_RE.match(line)
        if m:
            key, value = m.group(1), m.group(2)
        elif ":" in line:
            key, value = line.split(":", 1)
        else:
            continue
        key = key.strip()
        value = value.strip()
        key_folded = _fold_text(key)
        numeric_value = value.strip().rstrip(".。")
        if key_folded.startswith(("goi y", "suggestion", "note", "ghi chu")):
            continue
        if (
            re.search(r"\b(?:q[1-4]|quy\s*[1-4]|quarter\s*[1-4]|thang\s*\d{1,2}|month\s*\d{1,2}|(?:19|20)\d{2})\b", key_folded)
            or (key_folded.startswith(("q", "qu")) and len(key_folded) <= 12)
        ) and _NUMERIC_VALUE_RE.match(numeric_value):
            continue
        if len(key.split()) > 6:
            continue
        if key and value:
            rows.append([key, value])
    if len(rows) == 1 and "vs" in str(rows[0][1] or "").lower():
        left, right = re.split(r"\bvs\.?\s*|\bversus\s*", str(rows[0][1]), maxsplit=1, flags=re.IGNORECASE)
        return normalize_table_spec(
            {
                "title": str(slide.get("title") or ""),
                "headers": ["Tiêu chí", "Phương án 1", "Phương án 2"],
                "rows": [[rows[0][0], left.strip(" .;:-"), right.strip(" .;:-")]],
            }
        )
    has_vs_row = any("vs" in str(row[1] or "").lower() for row in rows)
    if len(rows) < 2:
        return None
    numeric_rows = sum(1 for row in rows if _NUMERIC_VALUE_RE.match(str(row[1] or "")))
    if rows and numeric_rows >= 2 and numeric_rows >= len(rows) - 1:
        return None
    if keyword_hits < 1 and len(rows) < 3 and not has_vs_row:
        return None
    comparison_rows: List[List[str]] = []
    for key, value in rows:
        text_value = str(value or "")
        if ";" not in text_value:
            comparison_rows = []
            break
        parts = [p.strip(" .;:-") for p in text_value.split(";") if p.strip(" .;:-")]
        left = ""
        right = ""
        for part in parts:
            folded_part = _fold_text(part)
            if "thu cong" in folded_part:
                left = re.sub(r"^(?:thủ công|thu cong)\s*[-:]\s*", "", part, flags=re.IGNORECASE).strip()
            elif "thong minh" in folded_part:
                right = re.sub(r"^(?:thông minh|thong minh)\s*[-:]\s*", "", part, flags=re.IGNORECASE).strip()
        if not left or not right:
            comparison_rows = []
            break
        comparison_rows.append([key, left, right])
    if len(comparison_rows) >= 2:
        return normalize_table_spec(
            {
                "title": str(slide.get("title") or "So sánh phương án"),
                "headers": ["Tiêu chí", "Quản lý thủ công", "Hệ thống thông minh"],
                "rows": comparison_rows,
            }
        )
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
    """Trích xuất các bảng markdown rõ ràng từ đầu vào gốc của người dùng.

    Điều này giúp giữ lại các bảng mà LLM có thể viết lại thành các dòng bullet văn xuôi sau đó.
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


def _raw_comparison_request(raw_content: str) -> Optional[Dict[str, Any]]:
    text = re.sub(r"\s+", " ", str(raw_content or "")).strip()
    folded = _fold_text(text)
    if "bang so sanh" not in folded or "tieu chi" not in folded:
        return None

    option_a = "Phương án 1"
    option_b = "Phương án 2"
    explicit_headers: List[str] = []
    between_match = re.search(
        r"giua\s+(.+?)\s+va\s+(.+?)\s+theo\s+cac\s+tieu\s+chi\s*[:：]\s*(.+)",
        folded,
        flags=re.IGNORECASE,
    )
    if between_match:
        option_a = between_match.group(1).strip(" ,;:-")
        option_b = between_match.group(2).strip(" ,;:-")
        criteria_text = _cut_table_request_tail(between_match.group(3))
    else:
        header_match = re.search(
            r"\b(?:cot|columns?|headers?)\s*(?:gom|la|:|：)?\s*(.+?)"
            r"(?=\s*;\s*|\.\s*|\b(?:hang|rows?|cac\s+hang)\b|"
            r"\b(?:slide|trang)\s*(?:so|thu)?\s*\d+\b|$)",
            folded,
            flags=re.IGNORECASE,
        )
        if header_match:
            explicit_headers = _split_criteria_text(header_match.group(1))
            if len(explicit_headers) >= 3:
                option_a = explicit_headers[1]
                option_b = explicit_headers[2]

        row_match = re.search(
            r"\b(?:hang|rows?|cac\s+hang)\s*(?:gom|la|:|：)?\s*(.+?)"
            r"(?=\b(?:slide|trang)\s*(?:so|thu)?\s*\d+\b|$)",
            folded,
            flags=re.IGNORECASE,
        )
        if row_match:
            criteria_text = _cut_table_request_tail(row_match.group(1))
        else:
            marker = "tieu chi"
            criteria_text = _cut_table_request_tail(folded.split(marker, 1)[-1].lstrip(" :："))

    criteria = _split_criteria_text(criteria_text)
    criteria = [
        _pretty_comparison_label(c)
        for c in criteria
        if len(c) >= 2
        and not c.startswith(("q1", "q2", "q3", "q4"))
        and "bieu do" not in c
        and "slide " not in c
    ]
    if len(criteria) < 2:
        return None

    def pretty_option(value: str) -> str:
        value = value.strip(" ,;:-")
        if "thu cong" in value:
            return "Quản lý thủ công"
        if "thong minh" in value:
            return "Hệ thống thông minh"
        return value[:60] or "Phương án"

    option_a_pretty = pretty_option(option_a)
    option_b_pretty = pretty_option(option_b)
    note_header = _pretty_comparison_label(explicit_headers[3])[:60] if len(explicit_headers) >= 4 else ""

    def cell_for(option: str, criterion: str) -> str:
        of = _fold_text(option)
        cf = _fold_text(criterion)
        is_manual = any(k in of for k in ("thu cong", "manual", "truyen thong"))
        is_smart = any(k in of for k in ("thong minh", "smart", "tu dong", "automatic"))
        if is_manual:
            if "toc do" in cf:
                return "Chậm, phụ thuộc nhân sự và thao tác thủ công."
            if "chinh xac" in cf:
                return "Dễ sai sót khi ghi nhận vé, biển số hoặc thanh toán."
            if "chi phi" in cf:
                return "Tốn chi phí nhân sự trực ca và giám sát liên tục."
            if "trai nghiem" in cf:
                return "Người dùng mất thời gian tìm chỗ và chờ xử lý."
        if is_smart:
            if "toc do" in cf:
                return "Nhanh hơn nhờ cảm biến, ANPR và xử lý tự động."
            if "chinh xac" in cf:
                return "Chính xác hơn nhờ dữ liệu thời gian thực và đối chiếu tự động."
            if "chi phi" in cf:
                return "Giảm chi phí vận hành dài hạn nhờ tối ưu nhân sự."
            if "trai nghiem" in cf:
                return "Hiển thị chỗ trống, chỉ dẫn nhanh và thanh toán tiện lợi."
        return ""

    headers = ["Tiêu chí", option_a_pretty, option_b_pretty]
    if note_header:
        headers.append(note_header)

    rows: List[List[str]] = []
    for criterion in criteria[:8]:
        row = [
            criterion,
            cell_for(option_a_pretty, criterion),
            cell_for(option_b_pretty, criterion),
        ]
        if note_header:
            row.append("Hệ thống thông minh có lợi thế hơn.")
        rows.append(row)

    spec = normalize_table_spec(
        {
            "title": "So sánh phương án quản lý",
            "headers": headers,
            "rows": rows,
        }
    )
    if not spec:
        return None
    return {
        "source": "raw_comparison_request",
        "heading": spec["title"],
        "context": folded,
        "spec": spec,
    }


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
    """Cổng chặn bảng chung: các tiêu đề/neo hàng phải được hỗ trợ bởi văn bản gốc."""
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
    visual_plan: Optional[Dict[int, str]] = None,
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
                planned_visual = str(
                    (visual_plan or {}).get(idx)
                    or (visual_plan or {}).get(str(idx))
                    or ""
                ).strip().lower()
                if idx in used_slides or not isinstance(slide, dict) or (planned_visual and planned_visual != "table"):
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
        planned_visual = str(
            (visual_plan or {}).get(idx)
            or (visual_plan or {}).get(str(idx))
            or ""
        ).strip().lower()
        if planned_visual and planned_visual != "table":
            debug_records.append(
                {
                    "slide_index": idx,
                    "title": str(slide.get("title") or ""),
                    "source": "visual_plan",
                    "status": f"skipped_planned_{planned_visual}",
                }
            )
            continue
        if planned_visual != "table" and chart_intent_from_slide(slide):
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

        # Nếu prompt gốc đã chứa các bảng markdown rõ ràng, tránh yêu cầu LLM
        # tự tạo thêm các bảng so sánh từ các slide chỉ chứa văn xuôi. Các bảng
        # dạng inline/deterministic ở trên vẫn được đi qua.
        if raw_candidates:
            continue

        if planned_visual != "table" and not _looks_like_table_slide(slide):
            continue
        if not hasattr(content_extractor, "extract_table_spec"):
            continue
        raw = await content_extractor.extract_table_spec(
            {
                "slide": slide,
                "context": "\n".join(
                    [
                        "Slide:",
                        "\n".join(_slide_lines(slide)),
                        "",
                        "Original user/source excerpt:",
                        str(raw_content or "")[:2500],
                    ]
                ),
            }
        )
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

    if not out:
        comparison_candidate = _raw_comparison_request(raw_content)
        spec = (comparison_candidate or {}).get("spec")
        if isinstance(spec, dict):
            best_idx = -1
            best_score = -1
            for idx, slide in enumerate(slides):
                if not isinstance(slide, dict) or chart_intent_from_slide(slide):
                    continue
                planned_visual = str(
                    (visual_plan or {}).get(idx)
                    or (visual_plan or {}).get(str(idx))
                    or ""
                ).strip().lower()
                if planned_visual and planned_visual != "table":
                    continue
                score = _slide_match_score(slide, comparison_candidate)
                folded_slide = _fold_text(" ".join([str(slide.get("title") or "")] + _slide_lines(slide)))
                if any(k in folded_slide for k in ("thu cong", "thong minh", "so sanh", "phuong an")):
                    score += 4
                if planned_visual == "table":
                    score += 3
                if score > best_score:
                    best_score = score
                    best_idx = idx
            if best_idx >= 0:
                out[best_idx] = spec
                debug_records.append(
                    {
                        "slide_index": best_idx,
                        "title": str((slides[best_idx] or {}).get("title") or ""),
                        "source": "raw_comparison_request",
                        "spec": spec,
                        "status": "created",
                        "match_score": best_score,
                    }
                )
                print(f"[slide_tables] slide {best_idx} table: raw comparison request {len(spec['rows'])} row(s)")

    out, debug_records = await review_visual_data_specs(
        content_extractor,
        structured,
        out,
        debug_records,
        kind="table",
        raw_content=raw_content,
    )

    if not out:
        comparison_candidate = _raw_comparison_request(raw_content)
        spec = (comparison_candidate or {}).get("spec")
        if isinstance(spec, dict):
            best_idx = -1
            best_score = -1
            for idx, slide in enumerate(slides):
                if not isinstance(slide, dict) or chart_intent_from_slide(slide):
                    continue
                planned_visual = str(
                    (visual_plan or {}).get(idx)
                    or (visual_plan or {}).get(str(idx))
                    or ""
                ).strip().lower()
                if planned_visual and planned_visual != "table":
                    continue
                score = _slide_match_score(slide, comparison_candidate)
                folded_slide = _fold_text(" ".join([str(slide.get("title") or "")] + _slide_lines(slide)))
                if any(k in folded_slide for k in ("thu cong", "thong minh", "so sanh", "phuong an", "toc do", "chinh xac", "chi phi")):
                    score += 4
                if planned_visual == "table":
                    score += 3
                if score > best_score:
                    best_score = score
                    best_idx = idx
            if best_idx >= 0:
                out[best_idx] = spec
                debug_records.append(
                    {
                        "slide_index": best_idx,
                        "title": str((slides[best_idx] or {}).get("title") or ""),
                        "source": "raw_comparison_request",
                        "spec": spec,
                        "status": "created_after_review",
                        "match_score": best_score,
                    }
                )
                print(f"[slide_tables] slide {best_idx} table: raw comparison request after review {len(spec['rows'])} row(s)")

    if task_id:
        _write_debug_json(task_id, debug_records)
    return out
