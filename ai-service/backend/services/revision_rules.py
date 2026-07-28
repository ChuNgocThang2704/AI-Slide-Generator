import json
import re
import unicodedata
from typing import Any, Dict, List, Optional

from services.text_utils import plain_slide_text


def explicit_visual_targets_from_prompt(text: str, slide_count: int) -> Dict[int, str]:
    folded = fold_revision_text(text)
    if not folded or slide_count <= 0:
        return {}

    targets: Dict[int, str] = {}
    for match in re.finditer(r"\b(?:slide|trang)\s*(?:so|thu)?\s*(\d+)\b", folded):
        try:
            idx = int(match.group(1)) - 1
        except Exception:
            continue
        if not (0 <= idx < slide_count):
            continue

        window_end = min(len(folded), match.end() + 180)
        next_slide = re.search(r"\b(?:slide|trang)\s*(?:so|thu)?\s*\d+\b", folded[match.end():window_end])
        if next_slide:
            window_end = match.end() + next_slide.start()
        window = folded[match.start():window_end]
        before = folded[max(0, match.start() - 80): match.start()]
        context = before + " " + window
        if re.search(r"\b(?:giu|khong\s+doi|keep)\b", context):
            continue
        if re.search(
            r"\b(?:chi\s+(?:co\s+)?van\s+ban|text[\s_-]*only)\b"
            r"|\bkhong\s+(?:co\s+)?bang\b.{0,80}\bkhong\s+(?:co\s+)?bieu\s*do\b"
            r"|\bkhong\s+(?:co\s+)?bieu\s*do\b.{0,80}\bkhong\s+(?:co\s+)?bang\b",
            window,
        ):
            targets[idx] = "none"
        elif re.search(r"\b(?:anh|hinh|image|photo|picture|minh\s+hoa)\b", window):
            targets[idx] = "image"
        elif re.search(r"\b(?:bieu\s*do|chart|graph)\b", window):
            targets[idx] = "chart"
        elif re.search(r"\b(?:bang|table|so\s+sanh)\b", window):
            targets[idx] = "table"
    return targets

def explicit_chart_type_targets_from_prompt(text: str, slide_count: int) -> Dict[int, str]:
    folded = fold_revision_text(text)
    if not folded or slide_count <= 0:
        return {}

    targets: Dict[int, str] = {}
    for match in re.finditer(r"\b(?:slide|trang)\s*(?:so|thu)?\s*(\d+)\b", folded):
        try:
            idx = int(match.group(1)) - 1
        except Exception:
            continue
        if not (0 <= idx < slide_count):
            continue

        window_end = min(len(folded), match.end() + 220)
        next_slide = re.search(r"\b(?:slide|trang)\s*(?:so|thu)?\s*\d+\b", folded[match.end():window_end])
        if next_slide:
            window_end = match.end() + next_slide.start()
        window = folded[match.start():window_end]
        if not re.search(r"\b(?:bieu\s*do|chart|graph)\b", window):
            continue
        if re.search(r"\b(?:duong|line|xu\s+huong|trend)\b", window):
            targets[idx] = "line"
        elif re.search(r"\b(?:tron|pie|thi\s+phan)\b", window):
            targets[idx] = "pie"
        elif re.search(r"\b(?:cot|column|bar)\b", window):
            targets[idx] = "bar"
    return targets

def explicit_slide_instruction_from_prompt(text: str, slide_index: int) -> str:
    marker_re = re.compile(
        r"\b(?:slide|trang)\s*(?:(?:số|so|thứ|thu)\s*)?(?:#\s*)?(\d+)\b",
        flags=re.IGNORECASE,
    )
    markers = list(marker_re.finditer(str(text or "")))
    for pos, marker in enumerate(markers):
        if int(marker.group(1)) - 1 != int(slide_index):
            continue
        end = markers[pos + 1].start() if pos + 1 < len(markers) else len(str(text or ""))
        return str(text or "")[marker.start():end].strip()
    return ""

def apply_explicit_chart_type_targets(chart_specs: Optional[dict], targets: Dict[int, str]) -> None:
    if not chart_specs or not targets:
        return
    for idx, chart_type in targets.items():
        spec = chart_specs.get(idx)
        if isinstance(spec, dict) and chart_type:
            spec["chart_type"] = chart_type
            spec["type"] = chart_type

def parse_revision_target_indices(
    *,
    revision_prompt: str,
    slide_count: int,
    slide_index: Optional[int] = None,
    slide_number: Optional[int] = None,
    target_slide_indices: Optional[str] = None,
    target_slide_numbers: Optional[str] = None,
) -> List[int]:
    """Resolve partial-revision targets as 0-based slide indices."""
    targets = set()

    def add_index(value: Any, *, one_based: bool):
        try:
            n = int(value)
        except Exception:
            return
        idx = n - 1 if one_based else n
        if 0 <= idx < slide_count:
            targets.add(idx)

    def add_many(raw: Optional[str], *, one_based: bool):
        if not raw:
            return
        text = str(raw).strip()
        if not text:
            return
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    add_index(item, one_based=one_based)
                return
            add_index(data, one_based=one_based)
            return
        except Exception:
            pass
        for part in re.split(r"[,;\s]+", text):
            if part.strip():
                add_index(part.strip(), one_based=one_based)

    add_index(slide_index, one_based=False)
    add_index(slide_number, one_based=True)
    add_many(target_slide_indices, one_based=False)
    add_many(target_slide_numbers, one_based=True)

    prompt = str(revision_prompt or "")
    folded = unicodedata.normalize("NFD", prompt.lower())
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    folded = folded.replace("đ", "d")
    for match in re.finditer(r"\b(?:slide|trang)\s*(?:so|thu)?\s*(\d+)\b", folded):
        add_index(match.group(1), one_based=True)
    for match in re.finditer(r"\b(\d+)\s*(?:slide|trang)\b", folded):
        add_index(match.group(1), one_based=True)
    if re.search(r"\b(?:slide|trang)\s*(?:cuoi|last|final)\b", folded) and slide_count > 0:
        targets.add(slide_count - 1)
    if re.search(r"\b(?:slide|trang)\s*(?:dau|first)\b", folded) and slide_count > 0:
        targets.add(0)

    return sorted(targets)

def fold_revision_text(text: str) -> str:
    folded = unicodedata.normalize("NFD", str(text or "").lower())
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return folded.replace("đ", "d").replace("Ä‘", "d")

def revision_prompt_mentions_image(text: str) -> bool:
    folded = fold_revision_text(text)
    if re.search(
        r"\b(?:giu|khong\s+doi|khong\s+sua|dung\s+doi|keep|unchanged|do\s+not\s+change)\b.{0,40}"
        r"\b(?:anh|hinh|visual|picture|photo|image|illustration)\b",
        folded,
    ):
        return False
    return bool(
        re.search(
            r"\b(?:anh|hinh|visual|picture|photo|image|illustration)\b|\bminh\s+hoa\b",
            folded,
            flags=re.IGNORECASE,
        )
    )

def revision_prompt_mentions_table(text: str) -> bool:
    folded = fold_revision_text(text)
    if re.search(
        r"\b(?:khong|bo|dung|without|no)\s+(?:dung\s+|su\s+dung\s+|co\s+)?(?:bang|table)\b",
        folded,
    ):
        return False
    return bool(
        re.search(
            r"\b(?:bang|table|comparison\s+table)\b|\bdu\s+lieu\s+bang\b|\bso\s+sanh\b",
            folded,
            flags=re.IGNORECASE,
        )
    )

def revision_prompt_add_slide_count(text: str) -> int:
    folded = fold_revision_text(text)
    if not re.search(r"\b(?:them|add|bo\s+sung|chen)\b", folded):
        return 0
    match = re.search(r"\b(?:them|add|bo\s+sung|chen)\s*(\d+)?\s*(?:slide|trang)\b", folded)
    if match:
        try:
            return max(1, min(int(match.group(1) or "1"), 10))
        except Exception:
            return 1
    if re.search(r"\b(?:slide|trang)\s+(?:moi|cuoi)\b", folded):
        return 1
    return 0

def revision_prompt_delete_slide_indices(text: str, slide_count: int) -> List[int]:
    folded = fold_revision_text(text)
    delete_signal = r"(?:\b(?:xoa|delete|remove)\b|\bbo\s+(?:slide|trang)\b)"
    if slide_count <= 0 or not re.search(delete_signal, folded):
        return []
    targets: set[int] = set()
    for match in re.finditer(r"\b(?:xoa|delete|remove|bo)\s*(?:slide|trang)?\s*(?:so|thu)?\s*(\d+)\b", folded):
        try:
            idx = int(match.group(1)) - 1
        except Exception:
            continue
        if 0 <= idx < slide_count:
            targets.add(idx)
    for match in re.finditer(r"\b(?:slide|trang)\s*(?:so|thu)?\s*(\d+)\b", folded):
        before = folded[max(0, match.start() - 60): match.start()]
        if not re.search(delete_signal, before):
            continue
        try:
            idx = int(match.group(1)) - 1
        except Exception:
            continue
        if 0 <= idx < slide_count:
            targets.add(idx)
    if re.search(r"\b(?:xoa|delete|remove|bo).{0,30}(?:slide|trang)\s+(?:cuoi|last|final)\b", folded):
        targets.add(slide_count - 1)
    if re.search(r"\b(?:xoa|delete|remove|bo).{0,30}(?:slide|trang)\s+(?:dau|first)\b", folded):
        targets.add(0)
    return sorted(targets)

def revision_prompt_preserve_slide_indices(text: str, slide_count: int) -> List[int]:
    folded = fold_revision_text(text)
    if slide_count <= 0 or not re.search(r"\b(?:giu|khong\s+doi|keep|unchanged|nhu\s+cu)\b", folded):
        return []
    targets: set[int] = set()
    for match in re.finditer(r"\b(?:slide|trang)\s*(?:so|thu)?\s*(\d+)\b", folded):
        before = folded[max(0, match.start() - 80): match.start()]
        after = folded[match.end(): min(len(folded), match.end() + 80)]
        context = f"{before} {after}"
        if not re.search(r"\b(?:giu|khong\s+doi|keep|unchanged|nhu\s+cu)\b", context):
            continue
        try:
            idx = int(match.group(1)) - 1
        except Exception:
            continue
        if 0 <= idx < slide_count:
            targets.add(idx)
    return sorted(targets)

def revision_prompt_title_overrides(text: str, slide_count: int) -> Dict[int, str]:
    raw = str(text or "")
    folded = fold_revision_text(raw)
    if slide_count <= 0 or not re.search(r"\b(?:tieu\s*de|title)\b", folded):
        return {}
    overrides: Dict[int, str] = {}
    patterns = [
        r"(?is)(?:slide|trang)\s*(?:s[ốo]|th[ứu])?\s*(\d+).*?(?:tiêu\s*đề|title).*?(?:thành|là|to)\s*[\"']?([^\"'.\n]+)",
        r"(?is)(?:đổi|sửa|change|set).*?(?:tiêu\s*đề|title).*?(?:slide|trang)\s*(?:s[ốo]|th[ứu])?\s*(\d+).*?(?:thành|là|to)\s*[\"']?([^\"'.\n]+)",
        r"(?is)(?:slide|trang)\s*(?:so|thu)?\s*(\d+).*?(?:tieu\s*de|title).*?(?:thanh|la|to)\s*[\"'“”]?([^\"'“”.\n]+)",
        r"(?is)(?:doi|sua|change|set).*?(?:tieu\s*de|title).*?(?:slide|trang)\s*(?:so|thu)?\s*(\d+).*?(?:thanh|la|to)\s*[\"'“”]?([^\"'“”.\n]+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, raw):
            try:
                idx = int(match.group(1)) - 1
            except Exception:
                continue
            title = plain_slide_text(match.group(2)).strip(" .:-\"'")
            if 0 <= idx < slide_count and title:
                overrides[idx] = title
    return overrides

def split_revision_list(value: str) -> List[str]:
    parts = re.split(r"[,;|/]+|\s+-\s+|\s+\bva\b\s+|\s+\band\b\s+", str(value or ""), flags=re.IGNORECASE)
    return [p.strip(" .:-") for p in parts if p and p.strip(" .:-")]

def fallback_table_from_revision_prompt(prompt: str) -> Optional[Dict[str, Any]]:
    text = str(prompt or "")
    folded = fold_revision_text(text)
    if not revision_prompt_mentions_table(text):
        return None

    headers: List[str] = []
    rows: List[str] = []

    def _extract_segment_from_original(folded_match: re.Match, group: int = 1) -> str:
        """Re-find the group captured in `folded` back in the original `text`.
        folded and text can have different lengths (NFD strips combining chars),
        so we cannot safely use folded byte positions to slice text.
        Instead we anchor on the literal matched value (case-insensitive)."""
        folded_value = folded_match.group(group)
        # Try to find the same token sequence in the original text via case-insensitive search.
        # Use the folded value as a pattern anchor: build a pattern that allows arbitrary
        # Unicode between word chars (handles combining diacritics being stripped).
        escaped = re.escape(folded_value.strip())
        # Loosen the pattern: allow optional diacritic-carrying variants by using \S+
        # for each word token so that "Tieu chi" matches "Tiêu chí".
        word_tokens = folded_value.strip().split()
        if len(word_tokens) >= 2:
            # Build a flexible pattern: match each word allowing extra unicode chars
            flexible = r"[^.;\n]+"
            m2 = re.search(
                r"(?i)(?:headers?|c[aáà]c\s+c[oộ]t|c[oộ]t|columns?|g[oồ]m\s+c[aáà]c\s+c[oộ]t)"
                r"\s*(?:[gồ]m|l[aà]|:)?\s*(" + flexible + r")",
                text,
            )
            if m2:
                return m2.group(1)
        return folded_value  # fallback: use folded value (no diacritics)

    # Search on folded text (no diacritics) so "các cột", "gồm các cột" etc. all match
    header_match = re.search(
        r"(?i)(?:headers?|c[ao]c\s+c[ao]t|c[ao]t|columns?|gom\s+c[ao]c\s+c[ao]t)"
        r"\s*(?:gom|la|:)?\s*([^.;\n]+)",
        folded,
    )
    if header_match:
        raw_segment = _extract_segment_from_original(header_match, group=1)
        headers = split_revision_list(raw_segment)

    row_match = re.search(
        r"(?i)(?:rows?|c[ao]c\s+h[ao]ng|h[ao]ng|them\s+(?:c[ao]c\s+)?h[ao]ng)"
        r"\s*(?:gom|la|:)?\s*([^.;\n]+)",
        folded,
    )
    if row_match:
        # For rows, try matching in original text too
        m2 = re.search(
            r"(?i)(?:rows?|c[aáà]c\s+h[aà]ng|h[aà]ng|th[eê]m\s+(?:c[aáà]c\s+)?h[aà]ng)"
            r"\s*(?:[gồ]m|l[aà]|:)?\s*([^.;\n]+)",
            text,
        )
        rows = split_revision_list(m2.group(1) if m2 else row_match.group(1))

    if len(headers) < 2:
        headers = ["Tiêu chí", "Nội dung"]
    if not rows:
        rows = ["Nội dung cần sửa"]

    def value_for(header: str, criterion: str) -> str:
        h = fold_revision_text(header)
        c = fold_revision_text(criterion)
        if h in {"tieu chi", "criterion", "criteria"} or "tieu chi" in h:
            return criterion
        if "thu cong" in h or "manual" in h:
            if "toc do" in c:
                return "Chậm, phụ thuộc thao tác con người"
            if "chinh xac" in c:
                return "Thấp hơn, dễ sai sót"
            if "chi phi" in c:
                return "Cao do tốn nhân sự và thời gian"
            if "bao mat" in c or "bao ve" in c:
                return "Phụ thuộc quy trình thủ công"
            if "mo rong" in c or "kha nang" in c:
                return "Khó mở rộng khi quy mô tăng"
            if "trai nghiem" in c or "sinh vien" in c:
                return "Bất tiện, phải chờ đợi"
            return "Phụ thuộc con người"
        if "thong minh" in h or "smart" in h or "tu dong" in h:
            if "toc do" in c:
                return "Nhanh, xử lý tự động"
            if "chinh xac" in c:
                return "Cao, dựa trên dữ liệu thời gian thực"
            if "chi phi" in c:
                return "Tối ưu hơn về dài hạn"
            if "bao mat" in c or "bao ve" in c:
                return "Mã hoá & kiểm soát truy cập tự động"
            if "mo rong" in c or "kha nang" in c:
                return "Dễ mở rộng theo nhu cầu"
            if "trai nghiem" in c or "sinh vien" in c:
                return "Thuận tiện, minh bạch"
            return "Tự động hoá và có dữ liệu"
        if "nhan xet" in h or "note" in h or "comment" in h:
            if "toc do" in c:
                return "Hệ thống thông minh vượt trội"
            if "bao mat" in c:
                return "Hệ thống thông minh an toàn hơn"
            if "mo rong" in c:
                return "Hệ thống thông minh linh hoạt hơn"
            return "Hệ thống thông minh có lợi thế hơn"
        return ""

    table_rows = [[value_for(header, criterion) for header in headers] for criterion in rows]
    return {"title": "Bảng so sánh", "headers": headers, "rows": table_rows}

def internal_slide_to_spec_row(idx: int, slide: Dict[str, Any]) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "slide_id": str(slide.get("slide_id") or f"slide-{idx + 1:03d}"),
        "index": idx,
        "title": plain_slide_text(slide.get("title") or f"Slide {idx + 1}"),
        "bullets": [
            plain_slide_text(x)
            for x in (slide.get("bullets") or [])
            if plain_slide_text(x)
        ],
        "notes": plain_slide_text(slide.get("notes") or ""),
        "chart": slide.get("chart") if isinstance(slide.get("chart"), dict) else None,
        "table": slide.get("table") if isinstance(slide.get("table"), dict) else None,
        "image": None,
        "layout": str(slide.get("layout") or "text_only"),
        "primary_visual": None,
        "likely_multi_pptx_slides": bool(slide.get("likely_multi_pptx_slides")),
    }
    if slide.get("image_url"):
        row["image"] = {
            "url": str(slide.get("image_url")),
            "path": str(slide.get("image_url")),
            "mime": "image/jpeg",
        }
    if row["table"]:
        row["layout"] = "text_table"
        row["primary_visual"] = "table"
    elif row["chart"]:
        row["layout"] = "text_chart"
        row["primary_visual"] = "chart"
    elif row["image"]:
        row["layout"] = "text_image"
        row["primary_visual"] = "image"
    return row
