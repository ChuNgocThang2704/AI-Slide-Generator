"""Input normalization and fallback structuring helpers."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


class InputProcessingMixin:
    _EXPLICIT_SLIDE_RE = re.compile(
        r"^\s*\[?\s*(?:slide|trang|page)\s*0*(\d+)(?:\s*[:\-–—]\s*([^\]\n]+))?\s*\]?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    def _parse_explicit_slide_blocks(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse user-authored [SLIDE n] blocks as a hard deck structure."""
        text = str(content or "").replace("\r\n", "\n").replace("\r", "\n")
        matches = list(self._EXPLICIT_SLIDE_RE.finditer(text))
        if len(matches) < 2:
            return None

        def clean_label(line: str) -> tuple[str, str]:
            raw = str(line or "").strip().lstrip("-").strip()
            if ":" not in raw:
                return "", raw
            key, value = raw.split(":", 1)
            return key.strip().lower(), value.strip()

        def split_pipe(line: str) -> List[str]:
            return [cell.strip() for cell in str(line or "").strip().strip("|").split("|")]

        def parse_number_cell(value: str) -> Optional[float]:
            raw = str(value or "").strip()
            m = re.search(r"[-+]?\d+(?:[.,]\d+)*", raw)
            if not m:
                return None
            num = m.group(0)
            if "." in num and "," in num:
                if num.rfind(",") > num.rfind("."):
                    num = num.replace(".", "").replace(",", ".")
                else:
                    num = num.replace(",", "")
            elif "," in num:
                parts = num.split(",")
                num = "".join(parts) if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]) else num.replace(",", ".")
            elif "." in num:
                parts = num.split(".")
                if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                    num = "".join(parts)
            try:
                return float(num)
            except Exception:
                return None

        def chart_type_from_text(value: str) -> str:
            folded = self._fold_simple(value)
            if any(k in folded for k in ("column", "cot")):
                return "bar"
            if any(k in folded for k in ("line", "duong")):
                return "line"
            if any(k in folded for k in ("pie", "tron")):
                return "pie"
            if "radar" in folded:
                return "radar"
            return "bar"

        slides: List[Dict[str, Any]] = []
        deck_title = ""

        for idx, match in enumerate(matches):
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            block_kind = (match.group(2) or "").strip()
            block = text[start:end].strip()
            if not block:
                continue

            title = block_kind or f"Slide {match.group(1)}"
            subtitle = ""
            image_url = ""
            bullets: List[str] = []
            table_headers: List[str] = []
            table_rows: List[List[str]] = []
            chart_type = ""
            chart_labels: List[str] = []
            chart_series_name = ""
            chart_values: List[float] = []
            in_content = False
            in_table = False

            for raw_line in block.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                key, value = clean_label(line)
                folded_key = self._fold_simple(key)

                if folded_key in {"tieu de", "tieu de lon", "title", "main title"} and value:
                    title = value
                    continue
                if folded_key in {"tieu de phu", "subtitle"} and value:
                    subtitle = value
                    continue
                if folded_key in {"thanh vien", "members", "member"} and value:
                    bullets.append(f"Thành viên: {value}")
                    continue
                if folded_key in {"image_url", "image url", "image"} and value:
                    image_url = value
                    continue
                if folded_key in {"noi dung", "content"}:
                    in_content = True
                    in_table = False
                    continue
                if folded_key in {"du lieu bang", "data table", "table data", "bang"}:
                    in_table = True
                    in_content = False
                    continue
                if folded_key in {"loai bieu do", "chart type"} and value:
                    chart_type = chart_type_from_text(value)
                    continue
                if folded_key in {"truc hoanh", "labels", "categories", "x axis"} and value:
                    chart_labels = [x.strip() for x in value.split("|") if x.strip()]
                    continue
                if folded_key in {"chuoi du lieu", "series", "series name"} and value:
                    chart_series_name = value
                    continue
                if folded_key in {"gia tri chuoi", "values"} and value:
                    parsed_values = [parse_number_cell(x) for x in value.split("|")]
                    chart_values = [v for v in parsed_values if v is not None]
                    continue

                if "|" in line and (in_table or not line.startswith("-")):
                    cells = split_pipe(line)
                    if len(cells) >= 2:
                        if not table_headers:
                            table_headers = cells
                        else:
                            table_rows.append(cells)
                        continue

                if line.startswith(("-", "•", "*")):
                    bullets.append(line.lstrip("-•* ").strip())
                elif in_content:
                    bullets.append(line)

            if subtitle:
                bullets.insert(0, f"Tiêu đề phụ: {subtitle}")
            if table_headers and table_rows:
                bullets.append(f"Bảng dữ liệu gồm {len(table_rows)} dòng và {len(table_headers)} cột.")
            if chart_labels and chart_values:
                bullets.append(f"Biểu đồ {chart_series_name or title} gồm {len(chart_values)} điểm dữ liệu.")

            slide: Dict[str, Any] = {
                "title": title,
                "bullets": bullets or [title],
                "notes": "",
            }
            if image_url:
                slide["image_url"] = image_url
            if table_headers and table_rows:
                slide["table"] = {
                    "title": title,
                    "headers": table_headers,
                    "rows": table_rows,
                }
            if chart_labels and chart_values and len(chart_labels) == len(chart_values):
                slide["chart"] = {
                    "title": title,
                    "chart_type": chart_type or "bar",
                    "labels": chart_labels,
                    "values": chart_values,
                    "series_name": chart_series_name or title,
                    "unit": "number",
                    "is_percent": "%" in block,
                }
            slides.append(slide)
            if not deck_title:
                deck_title = title

        if len(slides) < 2:
            return None
        return {"title": deck_title or "Bài thuyết trình", "slides": slides, "_explicit_slide_mode": True}

    def _fold_simple(self, text: str) -> str:
        s = unicodedata.normalize("NFD", str(text or ""))
        s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
        return s.replace("đ", "d").replace("Đ", "D").lower().strip()

    def _strip_meta_instruction_lines(self, content: str) -> str:
        """Remove short top-level user instructions that should not become slide content."""
        if not content:
            return ""

        def _fold(line: str) -> str:
            s = unicodedata.normalize("NFD", str(line or ""))
            s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
            return s.replace("đ", "d").replace("Đ", "D").lower()

        lines = str(content).replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out: List[str] = []
        for idx, line in enumerate(lines):
            raw = line.strip()
            folded = _fold(raw)
            is_early = idx < 8
            is_short = len(raw) <= 140
            has_meta_verb = any(
                key in folded
                for key in (
                    "yeu cau", "hay viet", "viet bang", "ngon ngu", "language",
                    "output", "tra ve", "generate in", "write in",
                )
            )
            has_lang = any(
                key in folded
                for key in (
                    "tieng viet", "vietnamese", "viet nam", "tieng anh", "english",
                )
            )
            if is_early and is_short and has_meta_verb and has_lang:
                continue
            out.append(line)
        cleaned = "\n".join(out)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _detect_heading_level(self, line: str) -> Optional[int]:
        """Detect heading level from markdown or common document patterns.

        Returns:
            1 | 2 | 3 for heading levels, or None if not heading.
        """
        text = (line or "").strip()
        if not text:
            return None

        # Markdown headings
        if text.startswith("### "):
            return 3
        if text.startswith("## "):
            return 2
        if text.startswith("# "):
            return 1

        # Vietnamese/English structural headings (must be followed by number or space+text)
        if re.match(r"^(CHƯƠNG|Chương)\s+[\dIVXivx]+", text):
            return 1
        if re.match(r"^(PHẦN|Phần)\s+[\dIVXivx]+", text):
            return 1
        if re.match(r"^(MỤC|Mục)\s+\d+", text):
            return 2
        if re.match(r"^(TIỂU\s*MỤC|Tiểu\s*mục)\s+", text):
            return 3

        # Numbered headings — require >= 6 chars of content after the number
        # to avoid treating bullet items like "1. ok" as headings
        if re.match(r"^\d+\.\d+\.\d+\s+.{5,}", text) and len(text) <= 80:
            return 3
        if re.match(r"^\d+\.\d+\s+.{5,}", text) and len(text) <= 80:
            return 2
        # Single-level numbered heading ONLY if it looks like a real heading (not a bullet)
        # Must have >= 10 chars of title text and be short overall
        if re.match(r"^\d+\.\s+.{9,}$", text) and len(text) <= 70:
            return 2

        # ALL-CAPS short lines (>= 6 chars, no commas/semicolons)
        if text.isupper() and 6 <= len(text) <= 50 and not re.search(r"[,;]", text):
            return 2

        return None

    def _strip_heading_marker(self, line: str) -> str:
        """Strip common heading prefixes and markers."""
        text = (line or "").strip()
        text = re.sub(r"^#{1,3}\s+", "", text)
        text = re.sub(r"^(slide|silde)\s*\d+\s*[:\-–]\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(\d+\.\d+\.\d+|\d+\.\d+|\d+[\.)])\s+", "", text)
        return text.rstrip(":").strip()

    def _split_chunk_by_size(self, chunk_text: str, max_chars: int = 9000) -> List[str]:
        """Split an oversized chunk while preserving heading context."""
        if len(chunk_text) <= max_chars:
            return [chunk_text]

        lines = chunk_text.split("\n")
        heading_lines = [ln for ln in lines if ln.startswith("#")]
        heading_prefix = "\n".join(heading_lines).strip()

        # Keep non-heading body as paragraphs
        body_lines = [ln for ln in lines if not ln.startswith("#")]
        body = "\n".join(body_lines)
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

        parts: List[str] = []
        current = heading_prefix + ("\n\n" if heading_prefix else "")
        for para in paragraphs:
            candidate = f"{current}{para}\n\n"
            if len(candidate) > max_chars and len(current.strip()) > 0:
                parts.append(current.strip())
                current = heading_prefix + ("\n\n" if heading_prefix else "") + para + "\n\n"
            else:
                current = candidate

        if current.strip():
            parts.append(current.strip())

        return parts if parts else [chunk_text]
    
    def _split_by_headings(self, content: str) -> List[str]:
        """
        Chia content theo phân cấp heading H1/H2/H3.
        Hỗ trợ cả markdown (#, ##, ###) và heading dạng số/chương/phần/mục.
        Lưu ý: KHÔNG normalize lại ở đây để tránh double-processing;
        normalize chỉ xảy ra 1 lần (không double-process).
        """
        # Chỉ clean line endings, không gộp/biến đổi nội dung
        cleaned = content.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        lines = [ln.strip() for ln in cleaned.split("\n")]

        sections: List[Dict[str, Any]] = []
        h1 = ""
        h2 = ""
        h3 = ""
        body: List[str] = []

        def flush_section():
            nonlocal body
            if body:
                sections.append({
                    "h1": h1,
                    "h2": h2,
                    "h3": h3,
                    "body": "\n".join(body).strip()
                })
                body = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if body and body[-1] != "":
                    body.append("")
                continue

            level = self._detect_heading_level(stripped)
            if level:
                title = self._strip_heading_marker(stripped)
                flush_section()
                if level == 1:
                    h1 = title
                    h2 = ""
                    h3 = ""
                elif level == 2:
                    h2 = title
                    h3 = ""
                else:
                    h3 = title
                continue

            body.append(stripped)

        flush_section()

        if not sections:
            return [cleaned.strip() or content]

        # Build chunk text with heading context for each section
        raw_chunks: List[str] = []
        for sec in sections:
            header_lines: List[str] = []
            if sec.get("h1"):
                header_lines.append(f"# {sec['h1']}")
            if sec.get("h2"):
                header_lines.append(f"## {sec['h2']}")
            if sec.get("h3"):
                header_lines.append(f"### {sec['h3']}")

            chunk = "\n".join(header_lines)
            if sec.get("body"):
                chunk = f"{chunk}\n\n{sec['body']}" if chunk else sec["body"]
            raw_chunks.append(chunk.strip())

        # Merge small trailing sections into the previous chunk to cut LLM round-trips
        # (important on low-VRAM GPUs). Cap size so we stay near _split_chunk_by_size limits.
        merged_chunks: List[str] = []
        min_chunk_chars = 2200
        max_merged_len = 8000
        for chunk in raw_chunks:
            if merged_chunks and len(chunk) < min_chunk_chars:
                candidate = f"{merged_chunks[-1]}\n\n{chunk}".strip()
                if len(candidate) <= max_merged_len:
                    merged_chunks[-1] = candidate
                else:
                    merged_chunks.append(chunk)
            else:
                merged_chunks.append(chunk)

        # Enforce max chunk size
        final_chunks: List[str] = []
        for chunk in merged_chunks:
            final_chunks.extend(self._split_chunk_by_size(chunk, max_chars=7000))

        return final_chunks if final_chunks else [cleaned.strip() or content]
    

    def _normalize_for_llm(self, content: str) -> str:
        """Normalize content để LLM hiểu tốt hơn - GIỮ NGUYÊN markup headings"""
        if not content:
            return ""
        
        # Normalize line breaks
        text = content.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("_x000D_", " ")
        
        # Split into lines
        lines = [ln.strip() for ln in text.split("\n")]
        lines = [ln for ln in lines if ln]
        
        # Gộp các dòng ngắn thành paragraph
        paragraphs = []
        current_para = []
        
        for line in lines:
            # Nếu là markdown heading (từ DOCX styles)
            if line.startswith("#"):
                if current_para:
                    paragraphs.append(" ".join(current_para))
                    current_para = []
                paragraphs.append(line)  # Giữ nguyên markdown heading
                continue

            level = self._detect_heading_level(line)
            if level:
                if current_para:
                    paragraphs.append(" ".join(current_para))
                clean_heading = self._strip_heading_marker(line)
                paragraphs.append(f"{'#' * level} {clean_heading}".strip())
                current_para = []
            elif len(line) < 40 and not re.search(r"[\.\?\!:]$", line):
                # Dòng ngắn, gộp với paragraph hiện tại
                current_para.append(line)
            else:
                # Dòng dài hoặc kết thúc bằng dấu câu
                if current_para:
                    current_para.append(line)
                    paragraphs.append(" ".join(current_para))
                    current_para = []
                else:
                    paragraphs.append(line)
        
        if current_para:
            paragraphs.append(" ".join(current_para))
        
        # Join với double newline
        result = "\n\n".join(paragraphs)
        result = re.sub(r" +", " ", result)
        return result.strip()
    
    def _fallback_structure(self, content: str) -> Dict[str, Any]:
        """Cấu trúc fallback nếu LLM không khả dụng"""
        text = (content or "").strip()
        if not text:
            return {"title": "Bài thuyết trình", "slides": [{"title": "Nội dung", "bullets": ["(trống)"], "notes": ""}]}

        # Normalize newlines/spaces
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Remove docx artifacts
        text = text.replace("_x000D_", "\n")
        text = re.sub(r"[ \t]+", " ", text)

        lines = [ln.strip() for ln in text.split("\n")]
        lines = [ln for ln in lines if ln]

        def is_slide_heading(line: str) -> bool:
            return bool(re.match(r"^(slide|silde)\s*\d+\s*[:\-–]\s*.+$", line, flags=re.IGNORECASE))

        def clean_heading(line: str) -> str:
            # Remove common prefixes like "Slide 1: "
            line = line.lstrip("# ").strip()
            line = re.sub(r"^(slide|silde)\s*\d+\s*[:\-–]\s*", "", line, flags=re.IGNORECASE).strip()
            return line.rstrip(":").strip()

        # Guess document title from first non-slide heading line (avoid "Slide 1: ...")
        doc_title = "Bài thuyết trình"
        for ln in lines[:10]:
            if not is_slide_heading(ln) and len(ln) >= 6:
                doc_title = ln[:80]
                break

        def is_heading(line: str) -> bool:
            if len(line) > 80:
                return False
            if line.startswith(("#", "CHƯƠNG", "Chương", "PHẦN", "Phần")):
                return True
            # Common pattern: "Slide 1:", "Slide 2 -", ...
            if is_slide_heading(line):
                return True
            if re.match(r"^(\d+(\.\d+)*)\s+.+$", line):
                return True
            # heading-ish: ends with ":" and not too long
            if line.endswith(":") and len(line) <= 60:
                return True
            return False

        def to_bullets(paragraph: str) -> List[str]:
            # split by sentence-ish, keep short bullets
            # IMPORTANT: don't split by ":" because it breaks lines like "Mục tiêu: ..."
            parts = re.split(r"(?<=[\.\?\!])\s+|;\s+", paragraph.strip())
            bullets = []
            for p in parts:
                p = p.strip(" -•\t")
                if not p:
                    continue
                # If there's a " + " joiner, split into multiple bullets
                if " + " in p and len(p) <= 120:
                    subparts = [sp.strip() for sp in p.split(" + ") if sp.strip()]
                else:
                    subparts = [p]
                for sp in subparts:
                    if not sp:
                        continue
                    if len(sp) > 180:
                        sp = sp[:177].rstrip() + "..."
                    bullets.append(sp)
            return bullets

        # Build sections
        sections: List[Dict[str, Any]] = []
        current = {"title": None, "bullets": []}

        for ln in lines:
            bullet_match = re.match(r"^(\-|\*|•|\u2022|\d+\)|\d+\.)\s+(.*)$", ln)
            if is_heading(ln):
                if current["title"] or current["bullets"]:
                    sections.append(current)
                current = {"title": clean_heading(ln) or ln.lstrip("# ").rstrip(":"), "bullets": []}
                continue
            if bullet_match:
                current["bullets"].append(bullet_match.group(2).strip())
            else:
                # treat as paragraph -> bullets
                current["bullets"].extend(to_bullets(ln))

        if current["title"] or current["bullets"]:
            sections.append(current)

        # Convert sections -> slides
        slides: List[Dict[str, Any]] = []
        slide_idx = 1
        for sec in sections:
            title = sec["title"]
            bullets = [b for b in sec["bullets"] if b]
            if not title or title.strip().lower() in ("nội dung", "noi dung"):
                if bullets:
                    first_b = bullets[0].strip()
                    if ":" in first_b and first_b.find(":") < 30:
                        title = first_b.split(":", 1)[0].strip()
                    else:
                        words = first_b.split()
                        title = " ".join(words[:5]).strip(".,;:!-“”‘’\"' ")
                if not title or not title.strip():
                    title = f"Nội dung {slide_idx}"

            # chunk bullets into multiple slides if too many
            chunk_size = 5
            for chunk_i in range(0, len(bullets), chunk_size):
                chunk = bullets[chunk_i : chunk_i + chunk_size]
                if not chunk:
                    continue
                part_no = chunk_i // chunk_size + 1
                chunk_title = title if part_no == 1 else f"{title} - Phần {part_no}"
                slides.append({"title": chunk_title[:80], "bullets": chunk, "notes": ""})
                slide_idx += 1

        if not slides:
            slides = [{"title": "Nội dung", "bullets": to_bullets(text)[:5] or ["(không tách được nội dung)"], "notes": ""}]

        title_counts: Dict[str, int] = {}
        for slide in slides:
            original_title = str(slide.get("title") or "Nội dung").strip()
            base_title = re.sub(
                r"\s*\([^)]*(?:tiếp|tiep|continued|cont\.?|tiáº|tiÃ|tiÃ¡)[^)]*\)\s*$",
                "",
                original_title,
                flags=re.IGNORECASE,
            ).strip() or original_title
            title_counts[base_title] = title_counts.get(base_title, 0) + 1
            count = title_counts[base_title]
            slide["title"] = base_title if count == 1 else f"{base_title} - Phần {count}"

        # cap for sanity
        return {"title": doc_title, "slides": slides[:20]}



