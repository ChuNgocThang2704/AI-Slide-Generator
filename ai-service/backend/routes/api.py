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
    s = (generate_images or "false").strip().lower()
    if s not in ("1", "true", "yes", "on"):
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
            if detected and 4 <= detected <= slide_limit_max:
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
) -> Tuple[str, Optional[str]]:
    """
    Khớp `_add_content_slide`: bảng full-width; không bảng thì ảnh/chart cột phải.
    primary_visual ∈ {"table","image","chart",None}.
    """
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
            "script": _plain_slide_text(slide.get("script") or slide.get("notes") or ""),
            "chart": None,
            "table": None,
            "image": None,
        }
        if chart_specs and idx in chart_specs:
            c_spec = dict(chart_specs[idx])
            c_spec["type"] = c_spec.get("chart_type")
            c_spec["categories"] = c_spec.get("labels")
            row["chart"] = c_spec
        if table_specs and idx in table_specs:
            row["table"] = table_specs[idx]
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
        layout, primary = _infer_slide_layout(row.get("chart"), row.get("image"), row.get("table"))
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
    generate_images: str = Form("false"),
):
    """Generate AI slide output as JSON spec (no PPTX rendering)."""
    try:
        task_id = str(uuid.uuid4())
        plan_norm = (plan or "pro").strip().lower()
        target_slides_override, resolved_slide_count = _validate_plan_limits(plan_norm, slide_count)
        force_exact_slide_count = bool(plan_norm == "free" or (target_slides_override is not None))
        resolved_image_limit = _resolve_plan_image_limit(plan_norm, target_slides_override, image_limit)
        slide_preset = "modern"
        want_images_flag = _form_wants_slide_images(generate_images)

        raw_content = None
        structured_content = None

        if file:
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in [".docx", ".pdf", ".txt"]:
                raise HTTPException(status_code=400, detail="File type not supported")
            file_path = UPLOAD_DIR / f"{task_id}{file_ext}"
            with open(file_path, "wb") as f:
                f.write(await file.read())
            raw_content = await file_processor.process_file(file_path)
        elif text:
            raw_content = text
        else:
            raise HTTPException(status_code=400, detail="Provide one of: text, file")

        target_slides_override, resolved_slide_count = _validate_plan_limits(plan_norm, slide_count, raw_content=raw_content)
        force_exact_slide_count = bool(plan_norm == "free" or (target_slides_override is not None))

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

                await redis_queue.update_task_status(task_id_bg, "processing", progress=68)
                table_specs_bg = await build_table_specs_for_slides(
                    content_extractor,
                    structured,
                    task_id=task_id_bg,
                    should_stop=should_stop,
                    raw_content=raw_content_bg or "",
                )
                chart_specs_bg = await build_chart_specs_for_slides(
                    content_extractor,
                    structured,
                    task_id=task_id_bg,
                    should_stop=should_stop,
                    table_indices=set(table_specs_bg.keys()),
                    raw_content=raw_content_bg or "",
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
                "content": structured_content,
                "plan": plan_norm,
                "slide_count": target_slides_override,
                "slide_theme": slide_preset,
                "generate_images": generate_images,
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
    generate_images: str = Form("false"),
):
    try:
        task_id = str(uuid.uuid4())
        plan_norm = (plan or "pro").strip().lower()
        target_slides_override, resolved_slide_count = _validate_plan_limits(plan_norm, slide_count)
        force_exact_slide_count = bool(plan_norm == "free" or (target_slides_override is not None))
        resolved_image_limit = _resolve_plan_image_limit(plan_norm, target_slides_override, image_limit)
        slide_preset = SlideGenerator.normalize_slide_preset(slide_theme) or "modern"

        if file:
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in [".docx", ".pdf", ".txt"]:
                raise HTTPException(status_code=400, detail="File type not supported")

            file_path = UPLOAD_DIR / f"{task_id}{file_ext}"
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            raw_content = await file_processor.process_file(file_path)
        elif text:
            raw_content = text
        else:
            raise HTTPException(status_code=400, detail="Either text or file must be provided")

        target_slides_override, resolved_slide_count = _validate_plan_limits(plan_norm, slide_count, raw_content=raw_content)
        force_exact_slide_count = bool(plan_norm == "free" or (target_slides_override is not None))
        resolved_image_limit = _resolve_plan_image_limit(plan_norm, target_slides_override, image_limit)

        content_length = len(raw_content)
        worker_ready = bool(redis_queue.redis_client and await redis_queue.has_active_worker())
        want_images_flag = _form_wants_slide_images(generate_images)

        async def _process_in_background(
            task_id_bg: str,
            raw_content_bg: str,
            slide_preset_bg: str,
            want_images_bg: bool,
            image_limit_bg: int,
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

                await redis_queue.update_task_status(task_id_bg, "processing", progress=68)
                table_specs_bg = await build_table_specs_for_slides(
                    content_extractor,
                    structured,
                    task_id=task_id_bg,
                    should_stop=should_stop,
                    raw_content=raw_content_bg or "",
                )
                chart_specs_bg = await build_chart_specs_for_slides(
                    content_extractor,
                    structured,
                    task_id=task_id_bg,
                    should_stop=should_stop,
                    table_indices=set(table_specs_bg.keys()),
                    raw_content=raw_content_bg or "",
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
                "plan": plan_norm,
                "slide_count": target_slides_override,
                "slide_theme": slide_preset,
                "generate_images": generate_images,
                "image_limit": resolved_image_limit,
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
