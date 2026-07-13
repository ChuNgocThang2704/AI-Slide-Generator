from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid
import html
import json
import httpx
import re
import unicodedata

from services.file_processor import FileProcessor
from services.content_extractor import ContentExtractor, TaskCancelledError
from services.slide_generator import SlideGenerator
from services.redis_queue import RedisQueue, exc_to_error_message
from config import (
    LLM_MODEL,
    VLLM_API_BASE_URL,
    VLLM_BASIC_AUTH_USER,
    VLLM_BASIC_AUTH_PASS,
    REDIS_OFFLOAD_WHEN_WORKER_ALIVE,
    REDIS_QUEUE_MIN_CHARS,
    IMAGE_GEN_API_BASE_URL,
    FREE_IMAGE_LIMIT,
    PRO_IMAGE_LIMIT_MAX,
    ULTRA_IMAGE_LIMIT_MAX,
    FREE_SLIDE_LIMIT,
    PRO_SLIDE_LIMIT_MAX,
    ULTRA_SLIDE_LIMIT_MAX,
    FREE_CHAR_LIMIT,
    PRO_CHAR_LIMIT,
    ULTRA_CHAR_LIMIT,
)
from filename_utils import pptx_path_for_task, resolve_pptx_by_task_id
from services.slide_charts import build_chart_specs_for_slides
from services.slide_tables import build_table_specs_for_slides
from services.images import build_image_paths_for_slides
from services.slide_text_quality import improve_slide_text_quality
from services.slide_quality import build_visual_plan, improve_deck_source_grounding

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

file_processor = FileProcessor()
content_extractor = ContentExtractor(model_name=LLM_MODEL)
slide_generator = SlideGenerator()
redis_queue = RedisQueue()


def _plain_slide_text(value: Any) -> str:
    """Return user-visible slide text without markdown formatting markers."""
    t = unicodedata.normalize("NFKC", html.unescape(str(value or ""))).strip()
    if not t:
        return ""
    t = t.translate(str.maketrans({
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2026": "...",
    }))
    t = re.sub(r"<[^>\n]{1,80}>", " ", t)
    t = re.sub(r"[•◦▪▫■□●○◆◇★☆✓✔✗✘➜→←↑↓↔]", " ", t)
    cleaned_chars: List[str] = []
    symbol_keep = set("$€£¥₫%‰+-=<>±×÷°")
    for ch in t:
        if ch == "\ufffd":
            continue
        cat = unicodedata.category(ch)
        if cat[0] == "C":
            cleaned_chars.append(" ")
            continue
        if cat[0] == "S" and ch not in symbol_keep:
            cleaned_chars.append(" ")
            continue
        cleaned_chars.append(ch)
    t = "".join(cleaned_chars)
    t = re.sub(r"^\s*(?:[-+*]|•)\s+", "", t)
    t = re.sub(r"^\s*\*+", "", t)
    t = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", t)
    t = re.sub(r"__([^_\n]+)__", r"\1", t)
    t = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", t)
    t = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", t)
    t = re.sub(r"\*{2,}", "", t)
    t = re.sub(r"_{2,}", "", t)
    t = re.sub(r"\*+\s*:", ":", t)
    t = re.sub(r":\s*\*+\s*", ": ", t)
    t = re.sub(r"\s+\*+\s+", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def _form_wants_slide_images(generate_images: Optional[str]) -> bool:
    s = (generate_images or "true").strip().lower()
    if s in ("0", "false", "no", "off"):
        return False
    if not (IMAGE_GEN_API_BASE_URL or "").strip():
        print("[main] generate_images=true but IMAGE_GEN_API_BASE_URL is empty, skip SDXL.")
        return False
    return True


def _resolve_plan_image_limit(
    plan: Optional[str],
    slide_count: Optional[int],
    image_limit: Optional[int] = None,
) -> int:
    plan_norm = (plan or "pro").strip().lower()
    if plan_norm == "free":
        max_limit = max(0, int(FREE_IMAGE_LIMIT))
        ratio = 0.5
    elif plan_norm == "ultra":
        max_limit = max(0, int(ULTRA_IMAGE_LIMIT_MAX))
        ratio = 0.7
    else:
        max_limit = max(0, int(PRO_IMAGE_LIMIT_MAX))
        ratio = 0.5

    total = int(slide_count or 10)
    calculated_limit = max(1, round(total * ratio))

    requested = None
    if image_limit is not None:
        try:
            requested = int(image_limit)
        except Exception:
            requested = None

    if requested is not None:
        return max(0, min(requested, calculated_limit, max_limit))
    return max(0, min(calculated_limit, max_limit))


def _detect_requested_slide_count(text: str) -> Optional[int]:
    import re
    if not text:
        return None
    # Tìm kiếm các mẫu như: "15 slide", "12 trang", "10 pages", "12 slides"
    matches = re.findall(r"\b(\d+)\s*(?:slide|trang|page)s?\b", text.lower())
    if matches:
        try:
            return int(matches[-1]) # Lấy giá trị khớp cuối cùng
        except ValueError:
            return None
    return None


def _explicit_visual_targets_from_prompt(text: str, slide_count: int) -> Dict[int, str]:
    folded = _fold_revision_text(text)
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


def _explicit_chart_type_targets_from_prompt(text: str, slide_count: int) -> Dict[int, str]:
    folded = _fold_revision_text(text)
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


def _explicit_slide_instruction_from_prompt(text: str, slide_index: int) -> str:
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


def _apply_explicit_chart_type_targets(chart_specs: Optional[dict], targets: Dict[int, str]) -> None:
    if not chart_specs or not targets:
        return
    for idx, chart_type in targets.items():
        spec = chart_specs.get(idx)
        if isinstance(spec, dict) and chart_type:
            spec["chart_type"] = chart_type
            spec["type"] = chart_type


def _detect_generate_images_request(text: str) -> bool:
    """Tự động phát hiện xem người dùng có yêu cầu sinh ảnh trong câu lệnh không (ví dụ: 'kèm ảnh', 'có hình', 'sinh ảnh')"""
    if not text:
        return False
    t = text.lower()
    return any(key in t for key in ("kem anh", "kèm ảnh", "co hinh", "có hình", "sinh anh", "sinh ảnh", "generate image", "with image"))


def _validate_plan_limits(
    plan: str,
    slide_count: Optional[int],
    raw_content: Optional[str] = None
) -> Tuple[Optional[int], Optional[int]]:
    """
    Validates limits based on selected plan (free, pro, ultra).
    Returns: (target_slides_override, resolved_slide_count)
    Raises HTTPException 400 if validation fails.
    """
    plan_norm = (plan or "pro").strip().lower()
    
    # 1. Validate plan and character limits
    if plan_norm == "free":
        char_limit = FREE_CHAR_LIMIT
        slide_limit_max = FREE_SLIDE_LIMIT
    elif plan_norm == "ultra":
        char_limit = ULTRA_CHAR_LIMIT
        slide_limit_max = ULTRA_SLIDE_LIMIT_MAX
    else: # pro
        char_limit = PRO_CHAR_LIMIT
        slide_limit_max = PRO_SLIDE_LIMIT_MAX
        
    if raw_content and len(raw_content) > char_limit:
        raise HTTPException(
            status_code=400,
            detail=f"Độ dài nội dung vượt quá giới hạn của gói {plan_norm.upper()} ({len(raw_content)} > {char_limit} ký tự)."
        )
        
    # 2. Resolve slide count & check slide limits
    if plan_norm == "free" and not (slide_count and slide_count > 0):
        target_slides_override = FREE_SLIDE_LIMIT
        resolved_slide_count = FREE_SLIDE_LIMIT
    else:
        # Check if slide_count is requested. If slide_count is 0 or None, try to detect from raw_content
        actual_slide_count = slide_count
        if (actual_slide_count is None or actual_slide_count <= 0) and raw_content:
            detected = _detect_requested_slide_count(raw_content)
            if detected and 1 <= detected <= slide_limit_max:
                print(f"[api] Detected requested slide count in prompt: {detected}")
                actual_slide_count = detected

        # For pro and ultra, slide_count is optional.
        if actual_slide_count and actual_slide_count > 0:
            if actual_slide_count > slide_limit_max:
                raise HTTPException(
                    status_code=400,
                    detail=f"Số slide yêu cầu vượt quá giới hạn tối đa của gói {plan_norm.upper()} ({actual_slide_count} > {slide_limit_max} slides)."
                )
            target_slides_override = actual_slide_count
            resolved_slide_count = actual_slide_count
        else:
            target_slides_override = None
            resolved_slide_count = None
            
    return target_slides_override, resolved_slide_count


def _as_bool_flag(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _image_url_from_path(path_str: str) -> Optional[str]:
    try:
        p = Path(path_str).resolve()
        rel = p.relative_to(OUTPUT_DIR.resolve())
        return "/outputs/" + str(rel).replace("\\", "/")
    except Exception:
        return None


# Khớp phụ đề / footer trong `slide_generator` (PPTX).
_TITLE_SLIDE_SUBTITLE = "Tạo bởi AI Slide Generator"
_CONTENT_SLIDE_FOOTER = "AI Slide Generator"
# `SlideGenerator.create_slide`: tách slide khi nhiều bullet (max 6 / slide vật lý).
_MAX_BULLETS_BEFORE_PPTX_SPLIT = 6

_SLIDE_SPEC_VERSION = "1.2"


def _mime_from_image_path(path_str: str) -> Optional[str]:
    ext = Path(path_str or "").suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".webp":
        return "image/webp"
    return None


def _resolve_visual_theme(structured_content: dict, slide_theme: Optional[str]) -> Tuple[str, Optional[str]]:
    """Trả về (color_theme_key, slide_preset_or_none) — logic tương tự create_slide."""
    preset_raw = (slide_theme or "").strip().lower() or None
    resolved = SlideGenerator.normalize_slide_preset(preset_raw)
    if resolved:
        return resolved, resolved
    return slide_generator._detect_theme(structured_content.get("title", "")), None


def _infer_slide_layout(
    chart: Optional[Dict[str, Any]],
    image: Optional[Dict[str, Any]],
    table: Optional[Dict[str, Any]] = None,
    slide_spec: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Optional[str]]:
    """
    Ưu tiên đọc layout do AI tự phân loại từ slide spec trước (nếu có).
    Nếu không có, fallback sang khớp dựa trên visual element (bảng full-width; ảnh/chart cột phải).
    """
    # 1. Ưu tiên layout do AI chỉ định
    if False and slide_spec and isinstance(slide_spec, dict) and slide_spec.get("layout"):
        ai_layout = str(slide_spec.get("layout")).strip().lower()
        valid_layouts = {"text_only", "text_image", "text_table", "text_chart", "split_columns", "timeline", "big_quote", "hero_stat", "intro", "normal"}
        if ai_layout in valid_layouts:
            primary = None
            if "image" in ai_layout or image:
                primary = "image"
            elif "table" in ai_layout or table:
                primary = "table"
            elif "chart" in ai_layout or chart:
                primary = "chart"
            return ai_layout, primary

    # 2. Fallback
    if table and table.get("headers") and table.get("rows"):
        return "text_table", "table"
    has_img = bool(image and (image.get("path") or image.get("url")))
    has_chart = chart is not None
    if has_img and has_chart:
        return "text_image", "image"
    if has_img:
        return "text_image", "image"
    if has_chart:
        return "text_chart", "chart"
    return "text_only", None


def _build_slide_spec_payload(
    *,
    task_id: str,
    structured_content: dict,
    chart_specs: Optional[dict],
    table_specs: Optional[dict],
    image_paths: Optional[dict],
    slide_theme: Optional[str] = None,
    **kwargs,
) -> dict:
    slides = structured_content.get("slides") or []
    color_theme, slide_preset = _resolve_visual_theme(structured_content, slide_theme)
    out_slides: List[Dict[str, Any]] = []
    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        row: Dict[str, Any] = {
            "index": idx,
            "title": _plain_slide_text(slide.get("title") or ""),
            "bullets": [_plain_slide_text(x) for x in (slide.get("bullets") or slide.get("content") or []) if _plain_slide_text(x)],
            "notes": _plain_slide_text(slide.get("notes") or slide.get("script") or ""),
            "chart": None,
            "table": None,
            "image": None,
        }
        if chart_specs and idx in chart_specs:
            c_spec = dict(chart_specs[idx])
            c_spec["type"] = c_spec.get("chart_type")
            c_spec["categories"] = c_spec.get("labels")
            row["chart"] = c_spec
        elif isinstance(slide.get("chart"), dict):
            row["chart"] = slide.get("chart")
        if table_specs and idx in table_specs:
            row["table"] = table_specs[idx]
        elif isinstance(slide.get("table"), dict):
            row["table"] = slide.get("table")
        if image_paths and idx in image_paths:
            img_path = str(image_paths[idx])
            img_url = _image_url_from_path(img_path)
            img = {
                "path": img_path,
                "url": img_url,
                "mime": _mime_from_image_path(img_path),
            }
            row["image"] = img
        elif slide.get("image_url"):
            row["image"] = {
                "path": None,
                "url": _plain_slide_text(slide.get("image_url")),
                "mime": None,
                "source": "user_url",
            }
        layout, primary = _infer_slide_layout(row.get("chart"), row.get("image"), row.get("table"), slide_spec=slide)
        row["layout"] = layout
        row["primary_visual"] = primary
        n_bullets = len(row["bullets"])
        row["likely_multi_pptx_slides"] = bool(n_bullets > _MAX_BULLETS_BEFORE_PPTX_SPLIT)
        out_slides.append(row)

    deck_title = str(structured_content.get("title") or "")
    return {
        "task_id": task_id,
        "status": "completed",
        "mode": "json_spec",
        "spec_version": _SLIDE_SPEC_VERSION,
        "slide_preset": slide_preset,
        "color_theme": color_theme,
        "title_slide": {
            "title": deck_title,
            "subtitle": _TITLE_SLIDE_SUBTITLE,
        },
        "content_slide_footer": _CONTENT_SLIDE_FOOTER,
        "deck": {
            "title": deck_title,
            "slides": out_slides,
        },
    }


def _structured_content_from_spec_payload(spec_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a completed JSON-spec response back into the internal slide-deck shape."""
    deck = (spec_payload or {}).get("deck") if isinstance(spec_payload, dict) else None
    if not isinstance(deck, dict):
        raise ValueError("Previous task result does not contain a deck")

    slides_out: List[Dict[str, Any]] = []
    for idx, slide in enumerate(deck.get("slides") or []):
        if not isinstance(slide, dict):
            continue
        row: Dict[str, Any] = {
            "title": _plain_slide_text(slide.get("title") or f"Slide {idx + 1}"),
            "bullets": [
                _plain_slide_text(x)
                for x in (slide.get("bullets") or [])
                if _plain_slide_text(x)
            ],
            "notes": _plain_slide_text(slide.get("notes") or ""),
        }
        layout = str(slide.get("layout") or "").strip()
        if layout:
            row["layout"] = layout
        image = slide.get("image")
        if isinstance(image, dict) and image.get("url"):
            row["image_url"] = str(image.get("url"))
        table = slide.get("table")
        if isinstance(table, dict):
            row["table"] = table
        chart = slide.get("chart")
        if isinstance(chart, dict):
            row["chart"] = chart
        slides_out.append(row)

    if not slides_out:
        raise ValueError("Previous task deck has no slides")
    return {
        "title": _plain_slide_text(deck.get("title") or "Bài thuyết trình"),
        "slides": slides_out,
    }


def _parse_revision_target_indices(
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


def _fold_revision_text(text: str) -> str:
    folded = unicodedata.normalize("NFD", str(text or "").lower())
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Mn")
    return folded.replace("đ", "d").replace("Ä‘", "d")


def _revision_prompt_mentions_image(text: str) -> bool:
    folded = _fold_revision_text(text)
    return bool(
        re.search(
            r"\b(?:anh|hinh|visual|picture|photo|image|illustration)\b|\bminh\s+hoa\b",
            folded,
            flags=re.IGNORECASE,
        )
    )


def _revision_prompt_mentions_table(text: str) -> bool:
    folded = _fold_revision_text(text)
    return bool(
        re.search(
            r"\b(?:bang|table|comparison\s+table)\b|\bdu\s+lieu\s+bang\b|\bso\s+sanh\b",
            folded,
            flags=re.IGNORECASE,
        )
    )


def _revision_prompt_add_slide_count(text: str) -> int:
    folded = _fold_revision_text(text)
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


def _revision_prompt_delete_slide_indices(text: str, slide_count: int) -> List[int]:
    folded = _fold_revision_text(text)
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


def _revision_prompt_preserve_slide_indices(text: str, slide_count: int) -> List[int]:
    folded = _fold_revision_text(text)
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


def _revision_prompt_title_overrides(text: str, slide_count: int) -> Dict[int, str]:
    raw = str(text or "")
    folded = _fold_revision_text(raw)
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
            title = _plain_slide_text(match.group(2)).strip(" .:-\"'")
            if 0 <= idx < slide_count and title:
                overrides[idx] = title
    return overrides


def _split_revision_list(value: str) -> List[str]:
    parts = re.split(r"[,;|/]+|\s+-\s+|\s+\bva\b\s+|\s+\band\b\s+", str(value or ""), flags=re.IGNORECASE)
    return [p.strip(" .:-") for p in parts if p and p.strip(" .:-")]


def _fallback_table_from_revision_prompt(prompt: str) -> Optional[Dict[str, Any]]:
    text = str(prompt or "")
    folded = _fold_revision_text(text)
    if not _revision_prompt_mentions_table(text):
        return None

    headers: List[str] = []
    rows: List[str] = []

    header_match = re.search(
        r"(?i)(?:headers?|cot|columns?)\s*(?:gom|la|:)?\s*([^.;\n]+)",
        text,
    )
    if header_match:
        headers = _split_revision_list(header_match.group(1))

    row_match = re.search(
        r"(?i)(?:rows?|hang|cac\s+hang|them\s+hang)\s*(?:gom|la|:)?\s*([^.;\n]+)",
        text,
    )
    if row_match:
        rows = _split_revision_list(row_match.group(1))

    if len(headers) < 2:
        headers = ["Tieu chi", "Noi dung"]
    if not rows:
        rows = ["Noi dung can sua"]

    def value_for(header: str, criterion: str) -> str:
        h = _fold_revision_text(header)
        c = _fold_revision_text(criterion)
        if h in {"tieu chi", "criterion", "criteria"} or "tieu chi" in h:
            return criterion
        if "thu cong" in h or "manual" in h:
            if "toc do" in c:
                return "Cham, phu thuoc thao tac con nguoi"
            if "chinh xac" in c:
                return "Thap hon, de sai sot"
            if "chi phi" in c:
                return "Cao do ton nhan su va thoi gian"
            if "trai nghiem" in c:
                return "Bat tien, phai cho doi"
            return "Phu thuoc con nguoi"
        if "thong minh" in h or "smart" in h or "tu dong" in h:
            if "toc do" in c:
                return "Nhanh, xu ly tu dong"
            if "chinh xac" in c:
                return "Cao, dua tren du lieu thoi gian thuc"
            if "chi phi" in c:
                return "Toi uu hon ve dai han"
            if "trai nghiem" in c:
                return "Thuan tien, minh bach"
            return "Tu dong hoa va co du lieu"
        if "nhan xet" in h or "note" in h or "comment" in h:
            return "He thong thong minh co loi the hon"
        return ""

    table_rows = [[value_for(header, criterion) for header in headers] for criterion in rows]
    return {"title": "Bang so sanh", "headers": headers, "rows": table_rows}


def _internal_slide_to_spec_row(idx: int, slide: Dict[str, Any]) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "index": idx,
        "title": _plain_slide_text(slide.get("title") or f"Slide {idx + 1}"),
        "bullets": [
            _plain_slide_text(x)
            for x in (slide.get("bullets") or [])
            if _plain_slide_text(x)
        ],
        "notes": _plain_slide_text(slide.get("notes") or ""),
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


def _review_revised_spec_payload(
    spec_payload: Dict[str, Any],
    *,
    previous_structured_content: Dict[str, Any],
    revision_prompt: str,
    plan_targets: List[int],
    wants_deck_restructure: bool,
    forced_table_targets: set[int],
    fallback_table: Optional[Dict[str, Any]],
    chart_type_targets: Dict[int, str],
    wants_image_revision: bool,
    image_instruction_targets: List[int],
) -> Dict[str, Any]:
    """Final deterministic QA gate for revise output before BE/FE receive it."""
    deck = spec_payload.get("deck") if isinstance(spec_payload, dict) else None
    slides = deck.get("slides") if isinstance(deck, dict) else None
    if not isinstance(slides, list):
        return spec_payload

    old_slides = [
        s for s in (previous_structured_content.get("slides") or [])
        if isinstance(s, dict)
    ]
    issues: List[Dict[str, Any]] = []
    fixes: List[Dict[str, Any]] = []
    target_set = set(plan_targets or [])

    if not wants_deck_restructure and old_slides:
        if len(slides) != len(old_slides):
            issues.append({
                "type": "slide_count_changed",
                "expected": len(old_slides),
                "actual": len(slides),
            })
            normalized: List[Dict[str, Any]] = []
            for idx, old_slide in enumerate(old_slides):
                if idx < len(slides) and idx in target_set and isinstance(slides[idx], dict):
                    normalized.append(slides[idx])
                else:
                    normalized.append(_internal_slide_to_spec_row(idx, old_slide))
            slides[:] = normalized
            fixes.append({"type": "restored_slide_count", "count": len(slides)})

        for idx, old_slide in enumerate(old_slides):
            if idx in target_set or idx >= len(slides):
                continue
            if not isinstance(slides[idx], dict):
                slides[idx] = _internal_slide_to_spec_row(idx, old_slide)
                fixes.append({"type": "restored_non_target_slide", "slide": idx + 1})
                continue
            old_row = _internal_slide_to_spec_row(idx, old_slide)
            comparable_keys = ("title", "bullets", "notes", "layout", "table", "chart", "image")
            if any(slides[idx].get(k) != old_row.get(k) for k in comparable_keys):
                slides[idx] = old_row
                fixes.append({"type": "restored_non_target_slide", "slide": idx + 1})

    for idx in sorted(forced_table_targets or set()):
        if not (0 <= idx < len(slides)) or not isinstance(slides[idx], dict):
            continue
        table = slides[idx].get("table")
        if fallback_table and not (
            isinstance(table, dict) and table.get("headers") and table.get("rows")
        ):
            slides[idx]["table"] = fallback_table
            table = fallback_table
            fixes.append({"type": "enforced_table_from_prompt", "slide": idx + 1})
        if (
            not isinstance(table, dict)
            or not table.get("headers")
            or not table.get("rows")
            or any(
                not isinstance(row, list)
                or len(row) != len(table.get("headers") or [])
                or any(not str(cell or "").strip() for cell in row)
                for row in (table.get("rows") or [])
            )
        ):
            issues.append({"type": "missing_or_invalid_table", "slide": idx + 1})
        slides[idx].pop("chart", None)
        slides[idx].pop("image", None)
        slides[idx]["layout"] = "text_table"
        slides[idx]["primary_visual"] = "table"

    for idx, chart_type in (chart_type_targets or {}).items():
        if not (0 <= idx < len(slides)) or not isinstance(slides[idx], dict):
            continue
        chart = slides[idx].get("chart")
        if isinstance(chart, dict):
            chart["chart_type"] = chart_type
            chart["type"] = chart_type
            slides[idx]["layout"] = "text_chart"
            slides[idx]["primary_visual"] = "chart"
            fixes.append({"type": "enforced_chart_type", "slide": idx + 1, "chart_type": chart_type})
        else:
            issues.append({"type": "missing_chart_for_requested_chart_type", "slide": idx + 1})

    if wants_image_revision:
        for idx in image_instruction_targets or []:
            if not (0 <= idx < len(slides)) or not isinstance(slides[idx], dict):
                continue
            slides[idx].pop("table", None)
            slides[idx].pop("chart", None)
            slides[idx]["layout"] = "text_image"
            slides[idx]["primary_visual"] = "image"
            if not isinstance(slides[idx].get("image"), dict):
                issues.append({"type": "missing_image_after_image_revision", "slide": idx + 1})

    for idx, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        slide["index"] = idx
        if slide.get("table"):
            slide["layout"] = "text_table"
            slide["primary_visual"] = "table"
        elif slide.get("chart"):
            slide["layout"] = "text_chart"
            slide["primary_visual"] = "chart"
        elif slide.get("image"):
            slide["layout"] = "text_image"
            slide["primary_visual"] = "image"
        else:
            slide["primary_visual"] = None

    spec_payload["post_review"] = {
        "kind": "revise_contract_qa",
        "prompt_excerpt": str(revision_prompt or "")[:300],
        "issues": issues,
        "fixes": fixes,
        "ok": not issues,
    }
    return spec_payload


async def _build_revised_slide_spec_payload(
    *,
    task_id: str,
    previous_structured_content: Dict[str, Any],
    revision_prompt: str,
    slide_theme: Optional[str],
    want_images: bool,
    image_limit: int,
    plan: str,
    should_stop,
    target_slide_indices: Optional[List[int]] = None,
) -> Dict[str, Any]:
    old_slides = previous_structured_content.get("slides") or []
    explicit_add_count = _revision_prompt_add_slide_count(revision_prompt)
    explicit_delete_targets = _revision_prompt_delete_slide_indices(
        revision_prompt,
        len(old_slides),
    )
    explicit_preserve_targets = set(_revision_prompt_preserve_slide_indices(
        revision_prompt,
        len(old_slides),
    ))
    explicit_title_overrides = _revision_prompt_title_overrides(
        revision_prompt,
        len(old_slides),
    )
    explicit_preserve_targets.difference_update(explicit_title_overrides.keys())
    revision_plan = await content_extractor.plan_slide_revision(
        previous_structured_content,
        revision_prompt,
    )
    plan_targets = [
        int(n) - 1
        for n in (revision_plan.get("target_slide_numbers") or [])
        if isinstance(n, int) or str(n).isdigit()
    ]
    plan_targets = [
        idx
        for idx in plan_targets
        if 0 <= idx < len(previous_structured_content.get("slides") or [])
    ]
    # The semantic revision plan owns the edit scope. Preserve hints are applied
    # later by restoring every slide outside plan_targets; a heuristic parser must
    # never erase a target that the planner identified explicitly.
    if not plan_targets and target_slide_indices:
        plan_targets = list(target_slide_indices)
    if not plan_targets and explicit_title_overrides:
        plan_targets = sorted(explicit_title_overrides.keys())

    op_types = {
        str(op.get("type") or "").strip().lower()
        for op in (revision_plan.get("operations") or [])
        if isinstance(op, dict)
    }
    if explicit_add_count or explicit_delete_targets:
        op_types.add("restructure_deck")
    if explicit_title_overrides:
        op_types.add("rewrite_text")
    if _revision_prompt_mentions_image(revision_prompt):
        op_types.add("regenerate_image")
    text_ops = {"rewrite_text", "change_layout", "restructure_deck"}
    wants_text_revision = bool(op_types & text_ops)
    wants_image_revision = "regenerate_image" in op_types
    wants_deck_restructure = "restructure_deck" in op_types or (
        revision_plan.get("scope") == "deck" and not plan_targets
    )
    changed_fields: List[str] = []

    if wants_deck_restructure:
        revised = await content_extractor.revise_slide_deck(
            previous_structured_content,
            revision_prompt,
        )
        changed_fields.append("deck")
    elif wants_text_revision and plan_targets:
        revised = await content_extractor.revise_selected_slides(
            previous_structured_content,
            revision_prompt,
            plan_targets,
        )
        changed_fields.append("text")
    elif wants_text_revision:
        revised = await content_extractor.revise_slide_deck(
            previous_structured_content,
            revision_prompt,
        )
        changed_fields.append("text")
    else:
        revised = {
            "title": previous_structured_content.get("title") or "Bài thuyết trình",
            "slides": [dict(s) for s in (previous_structured_content.get("slides") or []) if isinstance(s, dict)],
        }

    if wants_deck_restructure and old_slides:
        revised_slides = [
            slide for slide in (revised.get("slides") or []) if isinstance(slide, dict)
        ]
        if explicit_delete_targets:
            revised_slides = [
                dict(slide)
                for idx, slide in enumerate(old_slides)
                if idx not in set(explicit_delete_targets) and isinstance(slide, dict)
            ]
        if explicit_add_count:
            generated_additions = (
                revised_slides[-explicit_add_count:]
                if len(revised_slides) > len(old_slides)
                else []
            )
            revised_slides = [dict(slide) for slide in old_slides if isinstance(slide, dict)]
            for add_idx in range(explicit_add_count):
                generated = generated_additions[add_idx] if add_idx < len(generated_additions) else None
                revised_slides.append(
                    dict(generated) if isinstance(generated, dict) else {
                        "title": "Loi ich trien khai" if explicit_add_count == 1 else f"Loi ich trien khai {add_idx + 1}",
                        "bullets": [
                            "Tang hieu qua van hanh va giam thoi gian xu ly.",
                            "Cai thien trai nghiem nguoi dung nho du lieu thoi gian thuc.",
                            "Ho tro nha truong ra quyet dinh dua tren so lieu minh bach.",
                        ],
                        "notes": "Slide bo sung theo yeu cau cua nguoi dung.",
                        "layout": "text_only",
                    }
                )
        revised["slides"] = revised_slides

    if plan_targets and old_slides and not wants_deck_restructure:
        revised_slides = [
            slide for slide in (revised.get("slides") or []) if isinstance(slide, dict)
        ]
        selected_slide_map: Dict[int, Dict[str, Any]] = {}
        if len(revised_slides) == len(plan_targets) and len(revised_slides) != len(old_slides):
            selected_slide_map = {
                target_idx: revised_slides[pos]
                for pos, target_idx in enumerate(plan_targets)
                if pos < len(revised_slides)
            }

        normalized_slides: List[Dict[str, Any]] = []
        for idx, old_slide in enumerate(old_slides):
            if not isinstance(old_slide, dict):
                continue
            candidate = selected_slide_map.get(idx)
            if candidate is None and idx < len(revised_slides):
                candidate = revised_slides[idx]
            normalized_slides.append(
                dict(candidate) if idx in plan_targets and isinstance(candidate, dict) else dict(old_slide)
            )
        revised["slides"] = normalized_slides

    if explicit_title_overrides:
        for idx, title in explicit_title_overrides.items():
            slides = revised.get("slides") or []
            if 0 <= idx < len(slides) and isinstance(slides[idx], dict):
                if idx < len(old_slides) and isinstance(old_slides[idx], dict):
                    slides[idx] = dict(old_slides[idx])
                slides[idx]["title"] = title

    for idx, slide in enumerate(revised.get("slides") or []):
        if not isinstance(slide, dict):
            continue
        if idx < len(old_slides) and isinstance(old_slides[idx], dict):
            old_slide = old_slides[idx]
            if plan_targets and idx not in plan_targets:
                revised["slides"][idx] = dict(old_slide)
                continue
            if not slide.get("image_url") and old_slide.get("image_url"):
                slide["image_url"] = old_slide.get("image_url")
            if idx not in plan_targets:
                if "table" not in slide and isinstance(old_slide.get("table"), dict):
                    slide["table"] = old_slide.get("table")
                if "chart" not in slide and isinstance(old_slide.get("chart"), dict):
                    slide["chart"] = old_slide.get("chart")

    if wants_image_revision:
        image_instruction_targets = plan_targets or list(range(len(revised.get("slides") or [])))
        for idx in image_instruction_targets:
            slides = revised.get("slides") or []
            if 0 <= idx < len(slides) and isinstance(slides[idx], dict):
                slides[idx]["_image_revision_instruction"] = revision_prompt

    if await should_stop():
        raise TaskCancelledError()

    visual_plan = await build_visual_plan(
        content_extractor,
        revised,
        revision_prompt or "",
        want_images=want_images,
    )
    explicit_visual_targets = _explicit_visual_targets_from_prompt(
        revision_prompt,
        len(revised.get("slides") or []),
    )
    for idx in explicit_title_overrides:
        if idx in explicit_visual_targets or idx >= len(old_slides):
            continue
        old_slide = old_slides[idx] if isinstance(old_slides[idx], dict) else {}
        if isinstance(old_slide.get("table"), dict):
            visual_plan[idx] = "table"
        elif isinstance(old_slide.get("chart"), dict):
            visual_plan[idx] = "chart"
        elif old_slide.get("image_url") or "image" in str(old_slide.get("layout") or "").lower():
            visual_plan[idx] = "image"
        else:
            visual_plan[idx] = "none"
    if explicit_add_count:
        for idx, old_slide in enumerate(old_slides):
            if not isinstance(old_slide, dict):
                continue
            if isinstance(old_slide.get("table"), dict):
                visual_plan[idx] = "table"
            elif isinstance(old_slide.get("chart"), dict):
                visual_plan[idx] = "chart"
            elif old_slide.get("image_url") or "image" in str(old_slide.get("layout") or "").lower():
                visual_plan[idx] = "image"
            else:
                visual_plan[idx] = "none"
    forced_table_targets: set[int] = set()
    for idx, visual in explicit_visual_targets.items():
        visual_plan[idx] = visual
        if visual == "table":
            forced_table_targets.add(idx)

    if _revision_prompt_mentions_table(revision_prompt) and not wants_image_revision:
        table_targets = plan_targets or list(target_slide_indices or [])
        if not table_targets and len(revised.get("slides") or []) == 1:
            table_targets = [0]
        for idx in table_targets:
            if 0 <= idx < len(revised.get("slides") or []):
                visual_plan[idx] = "table"
                forced_table_targets.add(idx)
    if wants_image_revision:
        for idx in image_instruction_targets:
            visual_plan[idx] = "image"
            slides = revised.get("slides") or []
            if 0 <= idx < len(slides) and isinstance(slides[idx], dict):
                slides[idx].pop("table", None)
                slides[idx].pop("chart", None)
                slides[idx]["layout"] = "text_image"

    table_specs = await build_table_specs_for_slides(
        content_extractor,
        revised,
        task_id=task_id,
        should_stop=should_stop,
        raw_content=revision_prompt or "",
        visual_plan=visual_plan,
    )
    if forced_table_targets:
        from services.slide_tables import normalize_table_spec
        for idx in forced_table_targets:
            if not (0 <= idx < len(revised.get("slides") or [])):
                continue
            old_table = (
                old_slides[idx].get("table")
                if idx < len(old_slides) and isinstance(old_slides[idx], dict)
                else None
            )
            if not isinstance(old_table, dict):
                continue
            repaired_raw = await content_extractor.extract_table_spec(
                {
                    "slide": revised["slides"][idx],
                    "context": (
                        "Revise the existing table according to the user request. Preserve every existing header and row "
                        "unless the request explicitly changes or removes it. Return the complete final table, never only the delta.\n\n"
                        f"Existing table JSON:\n{json.dumps(old_table, ensure_ascii=False)}\n\n"
                        f"User request:\n{revision_prompt}"
                    ),
                }
            )
            repaired_spec = normalize_table_spec(repaired_raw)
            if repaired_spec:
                headers = repaired_spec.get("headers") or []
                for row in repaired_spec.get("rows") or []:
                    criterion = str(row[0] or "tiêu chí này").strip() if row else "tiêu chí này"
                    for col_idx, cell in enumerate(row):
                        if str(cell or "").strip():
                            continue
                        header = str(headers[col_idx] or "Nội dung").strip() if col_idx < len(headers) else "Nội dung"
                        row[col_idx] = (
                            f"So sánh hai phương án theo tiêu chí {criterion}."
                            if col_idx == len(row) - 1
                            else f"Chưa có thông tin cho {header} theo tiêu chí {criterion}."
                        )
                table_specs[idx] = repaired_spec
    fallback_table = _fallback_table_from_revision_prompt(revision_prompt)
    if fallback_table:
        for idx in forced_table_targets:
            if idx not in table_specs:
                table_specs[idx] = fallback_table
    chart_specs = await build_chart_specs_for_slides(
        content_extractor,
        revised,
        task_id=task_id,
        should_stop=should_stop,
        table_indices=set(table_specs.keys()),
        raw_content=revision_prompt or "",
        visual_plan=visual_plan,
    )
    explicit_chart_type_targets = _explicit_chart_type_targets_from_prompt(
        revision_prompt,
        len(revised.get("slides") or []),
    )
    _apply_explicit_chart_type_targets(
        chart_specs,
        explicit_chart_type_targets,
    )

    from services.slide_text_quality import improve_slide_titles_quality, improve_speaker_notes_quality
    note_slides = revised.get("slides") or []
    for idx, spec in table_specs.items():
        if 0 <= idx < len(note_slides) and isinstance(note_slides[idx], dict):
            note_slides[idx]["table"] = spec
    for idx, spec in chart_specs.items():
        if 0 <= idx < len(note_slides) and isinstance(note_slides[idx], dict):
            note_slides[idx]["chart"] = spec
    revised = await improve_slide_titles_quality(
        content_extractor,
        revised,
        source_language=(getattr(content_extractor, "_slide_lang_hint", "auto") or "auto"),
    )
    revised = await improve_speaker_notes_quality(
        content_extractor,
        revised,
        source_language=(getattr(content_extractor, "_slide_lang_hint", "auto") or "auto"),
    )

    image_paths = None
    if want_images and wants_image_revision:
        try:
            image_paths = await build_image_paths_for_slides(
                content_extractor,
                revised,
                task_id,
                chart_specs=chart_specs,
                table_specs=table_specs,
                image_limit=image_limit,
                should_stop=should_stop,
                plan=plan,
                target_indices=plan_targets or None,
                force_target_indices=sorted(
                    idx
                    for idx, visual in explicit_visual_targets.items()
                    if str(visual or "").strip().lower() == "image"
                ),
                force_instructions={
                    idx: _explicit_slide_instruction_from_prompt(revision_prompt, idx)
                    for idx, visual in explicit_visual_targets.items()
                    if str(visual or "").strip().lower() == "image"
                },
                visual_plan=visual_plan,
            )
            if image_paths:
                changed_fields.append("image")
        except Exception as image_error:
            print(f"[revise-spec] image generation failed, continue without images: {image_error!r}")
            image_paths = None

        missing_image_targets = [
            idx for idx in image_instruction_targets if idx not in (image_paths or {})
        ]
        if missing_image_targets:
            slide_numbers = ", ".join(str(idx + 1) for idx in missing_image_targets)
            raise RuntimeError(
                f"Không thể tạo ảnh mới đạt yêu cầu cho slide {slide_numbers}; "
                "bản sửa không được áp dụng để tránh báo thành công nhưng vẫn dùng ảnh cũ."
            )

    spec_payload = _build_slide_spec_payload(
        task_id=task_id,
        structured_content=revised,
        chart_specs=chart_specs,
        table_specs=table_specs,
        image_paths=image_paths,
        slide_theme=slide_theme,
    )
    spec_payload = _review_revised_spec_payload(
        spec_payload,
        previous_structured_content=previous_structured_content,
        revision_prompt=revision_prompt,
        plan_targets=plan_targets,
        wants_deck_restructure=wants_deck_restructure,
        forced_table_targets=forced_table_targets,
        fallback_table=fallback_table,
        chart_type_targets=explicit_chart_type_targets,
        wants_image_revision=wants_image_revision,
        image_instruction_targets=image_instruction_targets if wants_image_revision else [],
    )
    spec_payload["revision_plan"] = revision_plan
    spec_payload["revision_scope"] = "deck" if wants_deck_restructure else ("slide" if plan_targets else str(revision_plan.get("scope") or "deck"))
    spec_payload["target_slide_indices"] = plan_targets
    spec_payload["changed_fields"] = sorted(set(changed_fields))
    return spec_payload


@router.get("/")
async def root():
    return {"message": "AI Slide Generator API", "version": "1.0.0"}


@router.get("/api/vllm-status")
async def vllm_status():
    base = (VLLM_API_BASE_URL or "").strip().rstrip("/")
    if not base:
        return {"ok": False, "base_url": "", "error": "VLLM_API_BASE_URL not set"}
    auth = (
        httpx.BasicAuth(VLLM_BASIC_AUTH_USER, VLLM_BASIC_AUTH_PASS)
        if (VLLM_BASIC_AUTH_USER and VLLM_BASIC_AUTH_PASS)
        else None
    )
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{base}/v1/models", auth=auth)
            resp.raise_for_status()
            data = resp.json()
        raw = data.get("data") or []
        models = [m.get("id") for m in raw if isinstance(m, dict)]
        return {"ok": True, "base_url": base, "models": models}
    except Exception as e:
        return {"ok": False, "base_url": base, "error": str(e)}


@router.post("/api/upload-text")
async def upload_text(text: str = Form(...)):
    try:
        task_id = str(uuid.uuid4())
        temp_file = UPLOAD_DIR / f"{task_id}.txt"
        temp_file.write_text(text, encoding="utf-8")
        return {
            "task_id": task_id,
            "message": "Text received successfully",
            "status": "pending",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/upload-file")
async def upload_file(file: UploadFile = File(...)):
    try:
        allowed_extensions = [".docx", ".pdf", ".txt"]
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}",
            )

        task_id = str(uuid.uuid4())
        file_path = UPLOAD_DIR / f"{task_id}{file_ext}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        return {
            "task_id": task_id,
            "filename": file.filename,
            "message": "File uploaded successfully",
            "status": "pending",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/extract-content")
async def extract_content(task_id: str = Form(...)):
    try:
        file_path = None
        for ext in [".txt", ".docx", ".pdf"]:
            potential_path = UPLOAD_DIR / f"{task_id}{ext}"
            if potential_path.exists():
                file_path = potential_path
                break

        if not file_path:
            raise HTTPException(status_code=404, detail="File not found")

        content = await file_processor.process_file(file_path)
        structured_content = await content_extractor.extract_and_structure(content)

        return {
            "task_id": task_id,
            "content": structured_content,
            "status": "completed",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/generate-slide-spec")
async def generate_slide_spec(
    background_tasks: BackgroundTasks,
    text: Optional[str] = Form(None),
    file: UploadFile = File(None),
    plan: str = Form("pro"),
    slide_count: Optional[int] = Form(None),
    image_limit: Optional[int] = Form(None),
    generate_images: str = Form("true"),
):
    """Generate AI slide output as JSON spec (no PPTX rendering)."""
    try:
        task_id = str(uuid.uuid4())
        plan_norm = (plan or "pro").strip().lower()
        slide_preset = "modern"
        want_images_flag = False

        raw_content = None
        structured_content = None

        file_content = ""
        if file:
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in [".docx", ".pdf", ".txt"]:
                raise HTTPException(status_code=400, detail="File type not supported")
            file_path = UPLOAD_DIR / f"{task_id}{file_ext}"
            with open(file_path, "wb") as f:
                f.write(await file.read())
            file_content = await file_processor.process_file(file_path)

        user_instruction: Optional[str] = None
        if file_content and text:
            raw_content = file_content
            user_instruction = text  # Text là lệnh điều hướng, inject vào system prompt LLM
        elif file_content:
            raw_content = file_content
        elif text:
            raw_content = text
        else:
            raise HTTPException(status_code=400, detail="Provide at least one of: text, file")

        # Quét số slide từ prompt text của người dùng trước, nếu không có mới dùng content để tính
        text_for_detection = text or raw_content
        target_slides_override, resolved_slide_count = _validate_plan_limits(plan_norm, slide_count, raw_content=text_for_detection)
        force_exact_slide_count = bool(plan_norm == "free" or (target_slides_override is not None))

        # Tự động phát hiện yêu cầu sinh ảnh từ prompt text nếu tham số generate_images là false
        want_images_flag = _form_wants_slide_images(generate_images)
        if not want_images_flag and text:
            want_images_flag = _detect_generate_images_request(text)

        resolved_image_limit = _resolve_plan_image_limit(plan_norm, target_slides_override, image_limit)

        worker_ready = bool(redis_queue.redis_client and await redis_queue.has_active_worker())

        async def _process_spec_in_background(
            task_id_bg: str,
            raw_content_bg: Optional[str],
            structured_content_bg: Optional[dict],
            slide_theme_bg: str,
            want_images_bg: bool,
            image_limit_bg: int,
        ):
            try:
                await redis_queue.update_task_status(task_id_bg, "processing", progress=10)

                async def should_stop() -> bool:
                    return await redis_queue.is_task_cancelled(task_id_bg)

                if structured_content_bg:
                    structured = structured_content_bg
                    if force_exact_slide_count and target_slides_override and isinstance(structured, dict):
                        structured = await content_extractor._force_slide_count_exact(structured, int(target_slides_override))
                    if not structured.get("_explicit_slide_mode"):
                        structured = await improve_slide_text_quality(
                            content_extractor,
                            structured,
                            task_id=task_id_bg,
                            max_refines=8,
                            source_language=(
                                content_extractor._detect_output_language_hint(raw_content_bg or "")
                                if raw_content_bg
                                else getattr(content_extractor, "_slide_lang_hint", "auto")
                            ),
                        )
                        if force_exact_slide_count and target_slides_override and isinstance(structured, dict):
                            structured = await content_extractor._force_slide_count_exact(
                                structured, int(target_slides_override)
                            )
                else:
                    async def on_chunk(done: int, total: int):
                        if total <= 0:
                            return
                        progress = 10 + int(55 * done / total)
                        await redis_queue.update_task_status(
                            task_id_bg,
                            "processing",
                            progress=progress,
                            result={"chunks": {"done": done, "total": total}},
                        )

                    structured = await content_extractor.extract_and_structure(
                        raw_content_bg,
                        progress_cb=on_chunk,
                        should_stop=should_stop,
                        target_slides_override=target_slides_override,
                        force_exact_slide_count=force_exact_slide_count,
                        user_instruction=user_instruction,
                    )

                    if await should_stop():
                        return

                    if not structured.get("_explicit_slide_mode"):
                        structured = await improve_slide_text_quality(
                            content_extractor,
                            structured,
                            task_id=task_id_bg,
                            max_refines=8,
                            source_language=(
                                content_extractor._detect_output_language_hint(raw_content_bg or "")
                                if raw_content_bg
                                else getattr(content_extractor, "_slide_lang_hint", "auto")
                            ),
                        )
                        if force_exact_slide_count and target_slides_override and isinstance(structured, dict):
                            structured = await content_extractor._force_slide_count_exact(
                                structured, int(target_slides_override)
                            )

                if not structured.get("_explicit_slide_mode"):
                    structured = await improve_deck_source_grounding(
                        content_extractor,
                        structured,
                        raw_content_bg or "",
                        task_id=task_id_bg,
                    )
                    if force_exact_slide_count and target_slides_override and isinstance(structured, dict):
                        structured = await content_extractor._force_slide_count_exact(
                            structured, int(target_slides_override)
                        )

                await redis_queue.update_task_status(task_id_bg, "processing", progress=68)
                visual_plan_bg = await build_visual_plan(
                    content_extractor,
                    structured,
                    raw_content_bg or "",
                    want_images=want_images_bg,
                )
                visual_plan_bg.update(
                    _explicit_visual_targets_from_prompt(
                        raw_content_bg or "",
                        len(structured.get("slides") or []),
                    )
                )
                table_specs_bg = await build_table_specs_for_slides(
                    content_extractor,
                    structured,
                    task_id=task_id_bg,
                    should_stop=should_stop,
                    raw_content=raw_content_bg or "",
                    visual_plan=visual_plan_bg,
                )
                chart_specs_bg = await build_chart_specs_for_slides(
                    content_extractor,
                    structured,
                    task_id=task_id_bg,
                    should_stop=should_stop,
                    table_indices=set(table_specs_bg.keys()),
                    raw_content=raw_content_bg or "",
                    visual_plan=visual_plan_bg,
                )
                _apply_explicit_chart_type_targets(
                    chart_specs_bg,
                    _explicit_chart_type_targets_from_prompt(
                        raw_content_bg or "",
                        len(structured.get("slides") or []),
                    ),
                )
                image_paths_bg = None
                if want_images_bg:
                    await redis_queue.update_task_status(
                        task_id_bg, "processing", progress=68,
                        result={"images": {"done": 0, "total": 0}},
                    )
                    async def on_image_progress(done: int, total: int):
                        pct = 68 + int(11 * done / total) if total > 0 else 68
                        await redis_queue.update_task_status(
                            task_id_bg, "processing", progress=pct,
                            result={"images": {"done": done, "total": total}},
                        )
                    try:
                        image_paths_bg = await build_image_paths_for_slides(
                            content_extractor,
                            structured,
                            task_id_bg,
                            chart_specs=chart_specs_bg,
                            table_specs=table_specs_bg,
                            image_limit=image_limit_bg,
                            should_stop=should_stop,
                            progress_cb=on_image_progress,
                            plan=plan_norm,
                            force_target_indices=sorted(
                                idx
                                for idx, visual in _explicit_visual_targets_from_prompt(
                                    raw_content_bg or "",
                                    len(structured.get("slides") or []),
                                ).items()
                                if str(visual or "").strip().lower() == "image"
                            ),
                            force_instructions={
                                idx: _explicit_slide_instruction_from_prompt(raw_content_bg or "", idx)
                                for idx, visual in _explicit_visual_targets_from_prompt(
                                    raw_content_bg or "",
                                    len(structured.get("slides") or []),
                                ).items()
                                if str(visual or "").strip().lower() == "image"
                            },
                            visual_plan=visual_plan_bg,
                        )
                    except Exception as image_error:
                        print(
                            f"[generate-spec:bg] image generation failed, continue without images: {image_error!r}"
                        )
                        image_paths_bg = None

                if await should_stop():
                    return

                await redis_queue.update_task_status(task_id_bg, "processing", progress=80)
                spec_payload = _build_slide_spec_payload(
                    task_id=task_id_bg,
                    structured_content=structured,
                    chart_specs=chart_specs_bg,
                    table_specs=table_specs_bg,
                    image_paths=image_paths_bg,
                    slide_theme=slide_theme_bg,
                )

                if await should_stop():
                    return

                await redis_queue.update_task_status(
                    task_id_bg,
                    "completed",
                    progress=100,
                    result=spec_payload,
                )
            except TaskCancelledError:
                await redis_queue.update_task_status(
                    task_id_bg,
                    "cancelled",
                    progress=0,
                    result={"message": "Task cancelled by user"},
                )
            except Exception as e:
                await redis_queue.update_task_status(
                    task_id_bg,
                    "error",
                    progress=0,
                    result={"error": exc_to_error_message(e)},
                )

        if worker_ready and REDIS_OFFLOAD_WHEN_WORKER_ALIVE:
            task_data = {
                "action": "generate_slide_spec",
                "raw_content": raw_content,
                "user_instruction": user_instruction,
                "content": structured_content,
                "plan": plan_norm,
                "slide_count": target_slides_override,
                "slide_theme": slide_preset,
                "generate_images": "true" if want_images_flag else "false",
                "image_limit": resolved_image_limit,
            }
            await redis_queue.add_task(task_id, task_data)
            return {
                "task_id": task_id,
                "status": "processing",
                "message": "Processing JSON Spec via Redis worker...",
                "check_status_url": f"/api/status/{task_id}",
            }

        await redis_queue.update_task_status(task_id, "pending", progress=0)
        background_tasks.add_task(
            _process_spec_in_background,
            task_id,
            raw_content,
            structured_content,
            slide_preset,
            want_images_flag,
            resolved_image_limit,
        )
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Processing JSON Spec asynchronously in BackgroundTasks.",
            "check_status_url": f"/api/status/{task_id}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/revise-slide-spec")
async def revise_slide_spec(
    background_tasks: BackgroundTasks,
    source_task_id: str = Form(...),
    revision_prompt: str = Form(...),
    plan: str = Form("pro"),
    slide_count: Optional[int] = Form(None),
    image_limit: Optional[int] = Form(None),
    generate_images: str = Form("true"),
    revision_scope: str = Form("auto"),
    slide_index: Optional[int] = Form(None),
    slide_number: Optional[int] = Form(None),
    target_slide_indices: Optional[str] = Form(None),
    target_slide_numbers: Optional[str] = Form(None),
):
    """Revise a completed JSON slide spec using a follow-up user instruction."""
    try:
        prompt = (revision_prompt or "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="revision_prompt is required")

        source_status = await redis_queue.get_task_status(source_task_id)
        if source_status.get("status") != "completed":
            raise HTTPException(
                status_code=400,
                detail="source_task_id must reference a completed slide spec task",
            )
        source_result = source_status.get("result")
        if not isinstance(source_result, dict) or source_result.get("mode") != "json_spec":
            raise HTTPException(
                status_code=400,
                detail="source_task_id does not contain a JSON slide spec result",
            )

        previous_structured = _structured_content_from_spec_payload(source_result)
        plan_norm = (plan or "pro").strip().lower()
        source_slide_count = len(previous_structured.get("slides") or [])
        target_indices = _parse_revision_target_indices(
            revision_prompt=prompt,
            slide_count=source_slide_count,
            slide_index=slide_index,
            slide_number=slide_number,
            target_slide_indices=target_slide_indices,
            target_slide_numbers=target_slide_numbers,
        )
        has_explicit_target_fields = any(
            value is not None and str(value).strip()
            for value in (slide_index, slide_number, target_slide_indices, target_slide_numbers)
        )
        preserve_indices = set(_revision_prompt_preserve_slide_indices(prompt, source_slide_count))
        if preserve_indices and not has_explicit_target_fields:
            target_indices = [idx for idx in target_indices if idx not in preserve_indices]
        explicit_title_targets = set(_revision_prompt_title_overrides(prompt, source_slide_count))
        if explicit_title_targets:
            target_indices = sorted(set(target_indices) | explicit_title_targets)
        scope_norm = (revision_scope or "auto").strip().lower()
        if scope_norm in {"deck", "full", "all"}:
            target_indices = []
        elif scope_norm in {"slide", "partial"} and not target_indices:
            raise HTTPException(
                status_code=400,
                detail="revision_scope=slide requires slide_number, slide_index, target_slide_numbers, or a prompt mentioning a slide.",
            )

        requested_slide_count = slide_count if slide_count is not None else source_slide_count
        target_slides_override, _resolved_slide_count = _validate_plan_limits(
            plan_norm,
            requested_slide_count,
            raw_content=prompt,
        )
        if not target_indices and target_slides_override and target_slides_override != source_slide_count:
            previous_structured = await content_extractor._force_slide_count_exact(
                previous_structured,
                int(target_slides_override),
            )

        task_id = str(uuid.uuid4())
        slide_preset = str(source_result.get("slide_preset") or "modern")
        want_images_flag = _form_wants_slide_images(generate_images)
        if not want_images_flag:
            want_images_flag = _detect_generate_images_request(prompt)
        resolved_image_limit = _resolve_plan_image_limit(
            plan_norm,
            target_slides_override or source_slide_count,
            image_limit,
        )

        worker_ready = bool(redis_queue.redis_client and await redis_queue.has_active_worker())

        async def _process_revision_in_background(
            task_id_bg: str,
            previous_structured_bg: Dict[str, Any],
            revision_prompt_bg: str,
            slide_theme_bg: str,
            want_images_bg: bool,
            image_limit_bg: int,
        ):
            try:
                await redis_queue.update_task_status(task_id_bg, "processing", progress=10)

                async def should_stop() -> bool:
                    return await redis_queue.is_task_cancelled(task_id_bg)

                await redis_queue.update_task_status(task_id_bg, "processing", progress=35)
                spec_payload = await _build_revised_slide_spec_payload(
                    task_id=task_id_bg,
                    previous_structured_content=previous_structured_bg,
                    revision_prompt=revision_prompt_bg,
                    slide_theme=slide_theme_bg,
                    want_images=want_images_bg,
                    image_limit=image_limit_bg,
                    plan=plan_norm,
                    should_stop=should_stop,
                    target_slide_indices=target_indices,
                )
                spec_payload["source_task_id"] = source_task_id
                spec_payload["revision_prompt"] = revision_prompt_bg

                if await should_stop():
                    return
                await redis_queue.update_task_status(
                    task_id_bg,
                    "completed",
                    progress=100,
                    result=spec_payload,
                )
            except TaskCancelledError:
                await redis_queue.update_task_status(
                    task_id_bg,
                    "cancelled",
                    progress=0,
                    result={"message": "Task cancelled by user"},
                )
            except Exception as e:
                await redis_queue.update_task_status(
                    task_id_bg,
                    "error",
                    progress=0,
                    result={"error": exc_to_error_message(e)},
                )

        if worker_ready and REDIS_OFFLOAD_WHEN_WORKER_ALIVE:
            await redis_queue.add_task(
                task_id,
                {
                    "action": "revise_slide_spec",
                    "source_task_id": source_task_id,
                    "previous_content": previous_structured,
                    "revision_prompt": prompt,
                    "target_slide_indices": target_indices,
                    "plan": plan_norm,
                    "slide_theme": slide_preset,
                    "generate_images": "true" if want_images_flag else "false",
                    "image_limit": resolved_image_limit,
                },
            )
            return {
                "task_id": task_id,
                "source_task_id": source_task_id,
                "revision_scope": "slide" if target_indices else "deck",
                "target_slide_indices": target_indices,
                "status": "processing",
                "message": "Revising JSON Spec via Redis worker...",
                "check_status_url": f"/api/status/{task_id}",
            }

        await redis_queue.update_task_status(task_id, "pending", progress=0)
        background_tasks.add_task(
            _process_revision_in_background,
            task_id,
            previous_structured,
            prompt,
            slide_preset,
            want_images_flag,
            resolved_image_limit,
        )
        return {
            "task_id": task_id,
            "source_task_id": source_task_id,
            "revision_scope": "slide" if target_indices else "deck",
            "target_slide_indices": target_indices,
            "status": "processing",
            "message": "Revising JSON Spec asynchronously in BackgroundTasks.",
            "check_status_url": f"/api/status/{task_id}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/view-slide/{task_id}")
async def view_slide(task_id: str):
    slide_path = resolve_pptx_by_task_id(OUTPUT_DIR, task_id)
    if not slide_path or not slide_path.is_file():
        raise HTTPException(status_code=404, detail="Slide not found")

    return FileResponse(
        slide_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=slide_path.name,
    )


@router.get("/api/status/{task_id}")
async def get_status(task_id: str):
    status = await redis_queue.get_task_status(task_id)
    return status


@router.post("/api/cancel/{task_id}")
async def cancel_task(task_id: str):
    status = await redis_queue.cancel_task(task_id)
    return {
        "task_id": task_id,
        "status": status.get("status", "unknown"),
        "message": "Task cancellation requested",
    }


@router.post("/api/generate-slide-full")
async def generate_slide_full(
    background_tasks: BackgroundTasks,
    text: Optional[str] = Form(None),
    file: UploadFile = File(None),
    plan: str = Form("pro"),
    slide_count: Optional[int] = Form(None),
    image_limit: Optional[int] = Form(None),
    slide_theme: str = Form("modern"),
    generate_images: str = Form("true"),
):
    try:
        task_id = str(uuid.uuid4())
        plan_norm = (plan or "pro").strip().lower()
        target_slides_override, resolved_slide_count = _validate_plan_limits(plan_norm, slide_count)
        force_exact_slide_count = bool(plan_norm == "free" or (target_slides_override is not None))
        resolved_image_limit = _resolve_plan_image_limit(plan_norm, target_slides_override, image_limit)
        slide_preset = SlideGenerator.normalize_slide_preset(slide_theme) or "modern"

        file_content = ""
        if file:
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in [".docx", ".pdf", ".txt"]:
                raise HTTPException(status_code=400, detail="File type not supported")
            file_path = UPLOAD_DIR / f"{task_id}{file_ext}"
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            file_content = await file_processor.process_file(file_path)

        user_instruction: Optional[str] = None
        if file_content and text:
            raw_content = file_content
            user_instruction = text  # Text là lệnh điều hướng, inject vào system prompt LLM
        elif file_content:
            raw_content = file_content
        elif text:
            raw_content = text
        else:
            raise HTTPException(status_code=400, detail="Either text or file must be provided")

        # Quét số slide từ prompt text của người dùng trước, nếu không có mới dùng content để tính
        text_for_detection = text or raw_content
        target_slides_override, resolved_slide_count = _validate_plan_limits(plan_norm, slide_count, raw_content=text_for_detection)
        force_exact_slide_count = bool(plan_norm == "free" or (target_slides_override is not None))

        # Tự động phát hiện yêu cầu sinh ảnh từ prompt text nếu tham số generate_images là false
        want_images_flag = _form_wants_slide_images(generate_images)
        if not want_images_flag and text:
            want_images_flag = _detect_generate_images_request(text)

        resolved_image_limit = _resolve_plan_image_limit(plan_norm, target_slides_override, image_limit)

        doc_title_hint = None
        if file:
            doc_title_hint = Path(file.filename).stem

        content_length = len(raw_content)
        worker_ready = bool(redis_queue.redis_client and await redis_queue.has_active_worker())

        async def _process_in_background(
            task_id_bg: str,
            raw_content_bg: str,
            slide_preset_bg: str,
            want_images_bg: bool,
            image_limit_bg: int,
            doc_title_hint_bg: Optional[str] = None,
        ):
            try:
                await redis_queue.update_task_status(task_id_bg, "processing", progress=10)

                async def should_stop() -> bool:
                    return await redis_queue.is_task_cancelled(task_id_bg)

                async def on_chunk(done: int, total: int):
                    if total <= 0:
                        return
                    progress = 10 + int(55 * done / total)
                    await redis_queue.update_task_status(
                        task_id_bg,
                        "processing",
                        progress=progress,
                        result={"chunks": {"done": done, "total": total}},
                    )

                structured = await content_extractor.extract_and_structure(
                    raw_content_bg,
                    progress_cb=on_chunk,
                    should_stop=should_stop,
                    target_slides_override=target_slides_override,
                    force_exact_slide_count=force_exact_slide_count,
                    user_instruction=user_instruction,
                    doc_title_hint=doc_title_hint_bg,
                )

                if await should_stop():
                    return

                if not structured.get("_explicit_slide_mode"):
                    structured = await improve_slide_text_quality(
                        content_extractor,
                        structured,
                        task_id=task_id_bg,
                        max_refines=8,
                        source_language=(
                            content_extractor._detect_output_language_hint(raw_content_bg or "")
                            if raw_content_bg
                            else getattr(content_extractor, "_slide_lang_hint", "auto")
                        ),
                    )

                if not structured.get("_explicit_slide_mode"):
                    structured = await improve_deck_source_grounding(
                        content_extractor,
                        structured,
                        raw_content_bg or "",
                        task_id=task_id_bg,
                    )

                await redis_queue.update_task_status(task_id_bg, "processing", progress=68)
                visual_plan_bg = await build_visual_plan(
                    content_extractor,
                    structured,
                    raw_content_bg or "",
                    want_images=want_images_bg,
                )
                visual_plan_bg.update(
                    _explicit_visual_targets_from_prompt(
                        raw_content_bg or "",
                        len(structured.get("slides") or []),
                    )
                )
                table_specs_bg = await build_table_specs_for_slides(
                    content_extractor,
                    structured,
                    task_id=task_id_bg,
                    should_stop=should_stop,
                    raw_content=raw_content_bg or "",
                    visual_plan=visual_plan_bg,
                )
                chart_specs_bg = await build_chart_specs_for_slides(
                    content_extractor,
                    structured,
                    task_id=task_id_bg,
                    should_stop=should_stop,
                    table_indices=set(table_specs_bg.keys()),
                    raw_content=raw_content_bg or "",
                    visual_plan=visual_plan_bg,
                )
                _apply_explicit_chart_type_targets(
                    chart_specs_bg,
                    _explicit_chart_type_targets_from_prompt(
                        raw_content_bg or "",
                        len(structured.get("slides") or []),
                    ),
                )
                image_paths_bg = None
                if want_images_bg:
                    await redis_queue.update_task_status(
                        task_id_bg, "processing", progress=68,
                        result={"images": {"done": 0, "total": 0}},
                    )
                    async def on_image_progress(done: int, total: int):
                        pct = 68 + int(11 * done / total) if total > 0 else 68
                        await redis_queue.update_task_status(
                            task_id_bg, "processing", progress=pct,
                            result={"images": {"done": done, "total": total}},
                        )
                    try:
                        image_paths_bg = await build_image_paths_for_slides(
                            content_extractor,
                            structured,
                            task_id_bg,
                            chart_specs=chart_specs_bg,
                            table_specs=table_specs_bg,
                            image_limit=image_limit_bg,
                            should_stop=should_stop,
                            progress_cb=on_image_progress,
                            plan=plan_norm,
                            force_target_indices=sorted(
                                idx
                                for idx, visual in _explicit_visual_targets_from_prompt(
                                    raw_content_bg or "",
                                    len(structured.get("slides") or []),
                                ).items()
                                if str(visual or "").strip().lower() == "image"
                            ),
                            force_instructions={
                                idx: _explicit_slide_instruction_from_prompt(raw_content_bg or "", idx)
                                for idx, visual in _explicit_visual_targets_from_prompt(
                                    raw_content_bg or "",
                                    len(structured.get("slides") or []),
                                ).items()
                                if str(visual or "").strip().lower() == "image"
                            },
                            visual_plan=visual_plan_bg,
                        )
                    except Exception as image_error:
                        print(
                            f"[generate:bg] image generation failed, continue without images: {image_error!r}"
                        )
                        image_paths_bg = None

                if await should_stop():
                    return

                await redis_queue.update_task_status(task_id_bg, "processing", progress=75)
                output_bg = pptx_path_for_task(OUTPUT_DIR, structured.get("title", ""), task_id_bg)
                await slide_generator.create_slide(
                    structured,
                    output_bg,
                    generate_images=bool(image_paths_bg),
                    image_paths=image_paths_bg,
                    chart_specs=chart_specs_bg,
                    table_specs=table_specs_bg,
                    preset=slide_preset_bg,
                )

                if await should_stop():
                    return

                await redis_queue.update_task_status(
                    task_id_bg,
                    "completed",
                    progress=100,
                    result={
                        "download_url": f"/outputs/{output_bg.name}",
                        "view_url": f"/api/view-slide/{task_id_bg}",
                    },
                )
            except TaskCancelledError:
                await redis_queue.update_task_status(
                    task_id_bg,
                    "cancelled",
                    progress=0,
                    result={"message": "Task cancelled by user"},
                )
            except Exception as e:
                await redis_queue.update_task_status(
                    task_id_bg,
                    "error",
                    progress=0,
                    result={"error": exc_to_error_message(e)},
                )

        if worker_ready and REDIS_OFFLOAD_WHEN_WORKER_ALIVE:
            task_data = {
                "action": "generate_slide_full",
                "raw_content": raw_content,
                "user_instruction": user_instruction,
                "plan": plan_norm,
                "slide_count": target_slides_override,
                "slide_theme": slide_preset,
                "generate_images": "true" if want_images_flag else "false",
                "image_limit": resolved_image_limit,
                "doc_title_hint": doc_title_hint,
            }
            await redis_queue.add_task(task_id, task_data)
            return {
                "task_id": task_id,
                "status": "processing",
                "message": "Processing via Redis worker (vLLM)...",
                "check_status_url": f"/api/status/{task_id}",
            }

        # Luôn chạy bất đồng bộ qua BackgroundTasks nếu không có Redis worker
        await redis_queue.update_task_status(task_id, "pending", progress=0)
        background_tasks.add_task(
            _process_in_background,
            task_id,
            raw_content,
            slide_preset,
            want_images_flag,
            resolved_image_limit,
            doc_title_hint,
        )
        return {
            "task_id": task_id,
            "status": "processing",
            "message": "Processing asynchronously in BackgroundTasks.",
            "check_status_url": f"/api/status/{task_id}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
