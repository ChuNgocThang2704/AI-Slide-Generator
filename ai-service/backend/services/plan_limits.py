import re
from typing import Optional, Tuple

from fastapi import HTTPException
from config import (
    IMAGE_GEN_API_BASE_URL,
    FREE_IMAGE_LIMIT, PRO_IMAGE_LIMIT_MAX, ULTRA_IMAGE_LIMIT_MAX,
    FREE_SLIDE_LIMIT, PRO_SLIDE_LIMIT_MAX, ULTRA_SLIDE_LIMIT_MAX,
    FREE_CHAR_LIMIT, PRO_CHAR_LIMIT, ULTRA_CHAR_LIMIT,
)


def form_wants_slide_images(generate_images: Optional[str]) -> bool:
    s = (generate_images or "true").strip().lower()
    if s in ("0", "false", "no", "off"):
        return False
    if not (IMAGE_GEN_API_BASE_URL or "").strip():
        print("[main] generate_images=true but IMAGE_GEN_API_BASE_URL is empty, skip SDXL.")
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

def detect_requested_slide_count(text: str) -> Optional[int]:
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

def validate_plan_limits(
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
            detected = detect_requested_slide_count(raw_content)
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

def as_bool_flag(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")
