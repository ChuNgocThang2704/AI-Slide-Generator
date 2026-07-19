import re
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException
from config import (
    IMAGE_GEN_API_BASE_URL,
    GEMINI_API_KEY, STOCK_PHOTO_ENABLE, PEXELS_API_KEY,
    FREE_IMAGE_LIMIT, PRO_IMAGE_LIMIT_MAX, ULTRA_IMAGE_LIMIT_MAX,
    FREE_SLIDE_LIMIT, PRO_SLIDE_LIMIT_MAX, ULTRA_SLIDE_LIMIT_MAX,
    FREE_CHAR_LIMIT, PRO_CHAR_LIMIT, ULTRA_CHAR_LIMIT,
)


def form_wants_slide_images(generate_images: Optional[str]) -> bool:
    s = (generate_images or "true").strip().lower()
    if s in ("0", "false", "no", "off"):
        return False
    has_flux = bool((IMAGE_GEN_API_BASE_URL or "").strip())
    has_gemini = bool(GEMINI_API_KEY)
    has_stock = bool(STOCK_PHOTO_ENABLE and PEXELS_API_KEY)
    if not has_flux:
        print("[main] IMAGE_GEN_API_BASE_URL is empty, FLUX skipped.")
    if not (has_flux or has_gemini or has_stock):
        print("[main] No image source available (no FLUX, no Gemini key, no Pexels key). Skip image generation.")
        return False
    return True

def resolve_plan_image_limit(
    plan: Optional[str],
    slide_count: Optional[int],
    image_limit: Optional[int] = None,
) -> int:
    plan_norm = (plan or "pro").strip().lower()
    if plan_norm == "free":
        max_limit = max(0, int(FREE_IMAGE_LIMIT))
        ratio = 0.4
    elif plan_norm == "ultra":
        max_limit = max(0, int(ULTRA_IMAGE_LIMIT_MAX))
        ratio = 0.8
    else:
        max_limit = max(0, int(PRO_IMAGE_LIMIT_MAX))
        ratio = 0.6

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

def detect_requested_slide_count(text: str) -> Optional[int]:
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

def validate_plan_limits(
    plan: str,
    slide_count: Optional[int],
    raw_content: Optional[str] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """Validate input limits and resolve only an explicitly requested count."""
    plan_norm = (plan or "pro").strip().lower()
    if plan_norm == "free":
        char_limit, slide_limit_max = FREE_CHAR_LIMIT, FREE_SLIDE_LIMIT
    elif plan_norm == "ultra":
        char_limit, slide_limit_max = ULTRA_CHAR_LIMIT, ULTRA_SLIDE_LIMIT_MAX
    else:
        char_limit, slide_limit_max = PRO_CHAR_LIMIT, PRO_SLIDE_LIMIT_MAX

    if raw_content and len(raw_content) > char_limit:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Do dai noi dung vuot qua gioi han cua goi {plan_norm.upper()} "
                f"({len(raw_content)} > {char_limit} ky tu)."
            ),
        )

    actual_slide_count = slide_count
    if (actual_slide_count is None or actual_slide_count <= 0) and raw_content:
        actual_slide_count = detect_requested_slide_count(raw_content)

    if actual_slide_count and actual_slide_count > 0:
        if actual_slide_count > slide_limit_max:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"So slide yeu cau vuot qua gioi han toi da cua goi {plan_norm.upper()} "
                    f"({actual_slide_count} > {slide_limit_max} slides)."
                ),
            )
        print(f"[api] Detected requested slide count in prompt: {actual_slide_count}")
        return actual_slide_count, actual_slide_count
    return None, None


def enforce_plan_slide_limit(content: Dict[str, Any], plan: str) -> Dict[str, Any]:
    """Apply the plan maximum without padding an automatically-sized deck."""
    plan_norm = (plan or "pro").strip().lower()
    maximum = (
        FREE_SLIDE_LIMIT
        if plan_norm == "free"
        else ULTRA_SLIDE_LIMIT_MAX
        if plan_norm == "ultra"
        else PRO_SLIDE_LIMIT_MAX
    )
    slides = content.get("slides") if isinstance(content, dict) else None
    if isinstance(slides, list) and len(slides) > maximum:
        content["slides"] = slides[:maximum]
    return content

def as_bool_flag(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")
