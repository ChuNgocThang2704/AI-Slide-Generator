"""Tên file PPTX an toàn cho filesystem (Windows) và dễ đọc từ tiêu đề bài."""
import re
from pathlib import Path
from typing import Optional


def sanitize_presentation_stem(title: str, max_len: int = 80) -> str:
    """
    Chuỗi dùng làm phần tên file (không có extension), không chứa ký tự cấm.
    """
    if not title or not str(title).strip():
        return "presentation"
    s = str(title).strip()
    # Loại bỏ ký tự cấm của Windows và ký tự gây lỗi URL (#, %, &)
    for c in '<>:"/\\|?*#%&':
        s = s.replace(c, "")
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_. ")
    if not s:
        return "presentation"
    return s[:max_len]


def pptx_path_for_task(output_dir: Path, title: str, task_id: str) -> Path:
    """{Tiêu_đề}_{uuid}.pptx — vẫn unique nhờ task_id, phần đầu đọc được."""
    stem = sanitize_presentation_stem(title)
    return Path(output_dir) / f"{stem}_{task_id}.pptx"


def resolve_pptx_by_task_id(output_dir: Path, task_id: str) -> Optional[Path]:
    """
    Tìm file pptx theo task_id: ưu tiên legacy {task_id}.pptx, sau đó *_{task_id}.pptx.
    """
    output_dir = Path(output_dir)
    legacy = output_dir / f"{task_id}.pptx"
    if legacy.is_file():
        return legacy
    matches = list(output_dir.glob(f"*_{task_id}.pptx"))
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    return max(matches, key=lambda p: p.stat().st_mtime)
