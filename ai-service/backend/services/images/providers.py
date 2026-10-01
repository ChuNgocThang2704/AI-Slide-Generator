from __future__ import annotations
import asyncio
import base64
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Callable, Awaitable

import httpx

from config import (
    IMAGE_FALLBACK_MODEL,
    IMAGE_FALLBACK_TIMEOUT_SEC,
    GEMINI_MODEL,
    IMAGE_HEIGHT,
    IMAGE_WIDTH,
    PEXELS_API_KEY,
    STOCK_PHOTO_ENABLE,
    GEMINI_API_KEY,
    GCP_VERTEX_AI_ENABLE,
    GCP_PROJECT_ID,
    GCP_REGION,
)

from services.stock_photos import fetch_external_image
from .semantics import (
    _semantic_context,
    _semantic_list,
    _detect_historical_region,
    _extract_year_token,
    _extract_historical_entity,
    _is_mostly_ascii,
    _has_vietnamese_diacritics,
)




# --- Image generation through the OpenAI-compatible gateway (9Router) ---------------------------
# One endpoint in front of several providers: it picks a working image-capable model itself and
# moves on when one is out of quota, which the direct Flux / Imagen calls below cannot do.
_GATEWAY_IMAGE_SLOTS = asyncio.Semaphore(2)  # a few at a time: many parallel calls trip provider rate limits


_gateway_blocked_until = 0.0  # circuit breaker: monotonic time before which the gateway is not tried


def _trip_gateway_breaker(status: int, body: str) -> None:
    """Stop hammering an image model that is out of quota (it can stay so for days)."""
    global _gateway_blocked_until
    if status not in (401, 402, 403, 404, 429, 500, 502, 503):
        return
    cooldown = float(os.getenv("IMAGE_GATEWAY_COOLDOWN_SEC", "600"))
    if "quota" in body.lower() or "exhausted" in body.lower():
        cooldown = max(cooldown, 3600.0)
    _gateway_blocked_until = time.monotonic() + cooldown
    print(f"[slide_images] gateway images paused for {int(cooldown)}s after status {status}")


def gateway_images_enabled(plan_tier: str = "") -> bool:
    if time.monotonic() < _gateway_blocked_until:
        return False
    if os.getenv("IMAGE_GATEWAY_ENABLE", "true").strip().lower() not in ("1", "true", "yes"):
        return False
    if plan_tier == "free" and os.getenv("IMAGE_GATEWAY_FOR_FREE", "true").strip().lower() not in ("1", "true", "yes"):
        return False
    from config import VLLM_API_BASE_URL
    return bool((VLLM_API_BASE_URL or "").strip() and os.getenv("VLLM_API_KEY", "").strip())


async def _try_gateway_image(client: httpx.AsyncClient, *, prompt: str, size: str = "1024x1024") -> Optional[bytes]:
    """One image from the gateway, or None (any failure — the caller falls back to stock/other AI)."""
    from config import VLLM_API_BASE_URL
    base = (VLLM_API_BASE_URL or "").strip().rstrip("/")
    key = os.getenv("VLLM_API_KEY", "").strip()
    if not base or not key:
        return None
    model = os.getenv("IMAGE_GATEWAY_MODEL", "").strip() or os.getenv("NINE_ROUTER_MODEL", "").strip() or os.getenv("LLM_MODEL", "").strip()
    try:
        async with _GATEWAY_IMAGE_SLOTS:
            resp = await client.post(
                f"{base}/v1/images/generations",
                json={"model": model, "prompt": prompt[:1800], "n": 1, "size": size},
                headers={"Authorization": f"Bearer {key}"},
                timeout=httpx.Timeout(float(os.getenv("IMAGE_GATEWAY_TIMEOUT_SEC", "120")), connect=10.0),
            )
        if resp.status_code != 200:
            print(f"[slide_images] gateway image request failed (status={resp.status_code}): {resp.text[:200]}")
            _trip_gateway_breaker(resp.status_code, resp.text)
            return None
        item = ((resp.json().get("data") or [None])[0]) or {}
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            got = await client.get(item["url"], timeout=60.0)
            return got.content if got.status_code == 200 else None
    except Exception as error:  # network, timeout, bad JSON: never break slide generation over a picture
        print(f"[slide_images] gateway image error: {type(error).__name__}: {str(error)[:160]}")
    return None


_imagen_blocked_until = 0.0  # Imagen refused us (404/403): stop retrying for an hour


async def _try_secondary_ai_image_fallback(
    client: httpx.AsyncClient,
    *,
    prompt: str,
    negative_prompt: str,
    payload_template: Dict[str, Any],
) -> Optional[bytes]:
    """Thử Gemini Imagen làm ảnh dự phòng thứ cấp.

    Thay thế Together/FLUX vốn thường xuyên gặp lỗi giới hạn tần suất (rate-limit).
    Sử dụng Google Cloud Vertex AI nếu được bật, nếu không sẽ chuyển sang AI Studio.
    """
    if gateway_images_enabled():
        gateway_raw = await _try_gateway_image(client, prompt=prompt)
        if gateway_raw:
            return gateway_raw
    global _imagen_blocked_until
    if time.monotonic() < _imagen_blocked_until:
        return None
    model = (IMAGE_FALLBACK_MODEL or "").strip()
    if not model or model.startswith("black-forest-labs") or model.startswith("imagen-3.0"):
        model = "imagen-4.0-fast-generate-001"

    width = int(payload_template.get("width") or IMAGE_WIDTH)
    height = int(payload_template.get("height") or IMAGE_HEIGHT)
    if width >= height:
        aspect_ratio = "1:1" if abs(width - height) < 128 else "4:3"
    else:
        aspect_ratio = "3:4"

    is_imagen4 = "imagen-4.0" in model
    headers: Dict[str, str] = {}
    use_vertex = GCP_VERTEX_AI_ENABLE and GCP_PROJECT_ID
    
    if use_vertex:
        from services.vertex_auth import get_vertex_access_token
        token = get_vertex_access_token()
        if not token:
            print("[slide_images] Vertex AI enabled but failed to obtain access token. Skipping.")
            return None
        headers["Authorization"] = f"Bearer {token}"
        url = (
            f"https://{GCP_REGION}-aiplatform.googleapis.com/v1/"
            f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}/publishers/google/models/{model}:predict"
        )
    else:
        if not GEMINI_API_KEY:
            print("[slide_images] secondary AI fallback skipped: GEMINI_API_KEY not set")
            return None
        url_param = "?key=" + GEMINI_API_KEY
        if is_imagen4:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:predict{url_param}"
            )
        else:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateImages{url_param}"
            )

    if use_vertex or is_imagen4:
        req: Dict[str, Any] = {
            "instances": [
                {
                    "prompt": (prompt or "")[:2000]
                }
            ],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": aspect_ratio,
                "outputMimeType": "image/png",
                "personGeneration": "ALLOW_ADULT",
            }
        }
    else:
        req = {
            "prompt": {"text": (prompt or "")[:2000]},
            "number_of_images": 1,
            "aspect_ratio": aspect_ratio,
            "safety_filter_level": "BLOCK_MEDIUM_AND_ABOVE",
            "person_generation": "ALLOW_ADULT",
        }
    def _url_for_model(model_name: str) -> str:
        if use_vertex:
            return (
                f"https://{GCP_REGION}-aiplatform.googleapis.com/v1/"
                f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}/publishers/google/models/{model_name}:predict"
            )
        url_param = "?key=" + GEMINI_API_KEY
        if "imagen-4.0" in model_name:
            return (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:predict{url_param}"
            )
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateImages{url_param}"
        )

    if model == "imagen-4.0-generate-001":
        model_attempts = ["imagen-4.0-fast-generate-001", model]
    else:
        model_attempts = [model]

    configured_timeout = float(IMAGE_FALLBACK_TIMEOUT_SEC)
    for attempt_index, attempt_model in enumerate(model_attempts):
        read_timeout = configured_timeout
        if attempt_index == 0 and len(model_attempts) > 1:
            read_timeout = min(configured_timeout, 45.0)
        timeout = httpx.Timeout(read_timeout, connect=min(25.0, read_timeout))
        try:
            resp = await client.post(
                _url_for_model(attempt_model),
                json=req,
                headers=headers,
                timeout=timeout,
            )
        except Exception as e:
            print(
                f"[slide_images] Gemini Imagen fallback failed "
                f"({attempt_model}, {type(e).__name__}): {e}"
            )
            continue

        if resp.status_code != 200:
            print(
                f"[slide_images] Gemini Imagen fallback HTTP {resp.status_code} ({attempt_model}): "
                f"{resp.text[:300]}"
            )
            if resp.status_code in (400, 401, 403, 404):
                _imagen_blocked_until = time.monotonic() + 3600.0
            continue
        data = resp.json()
        
        b64_val = None
        if "imagen-4.0" in attempt_model:
            # Định dạng phản hồi của Imagen 4: {"predictions": [{"bytesBase64Encoded": "<b64>", "mimeType": "image/png"}]}
            predictions = data.get("predictions") or []
            if predictions and isinstance(predictions[0], dict):
                b64_val = predictions[0].get("bytesBase64Encoded")
        else:
            # Định dạng phản hồi của Imagen 3: {"generatedImages": [{"image": {"imageBytes": "<b64>"}}]}
            generated = data.get("generatedImages") or []
            if generated and isinstance(generated[0], dict):
                image_obj = (generated[0] or {}).get("image") or {}
                b64_val = image_obj.get("imageBytes")

        if not isinstance(b64_val, str) or not b64_val.strip():
            print(f"[slide_images] Gemini Imagen fallback: no image data in response ({attempt_model})")
            continue
        raw = base64.b64decode(b64_val)
        if not raw:
            print(f"[slide_images] Gemini Imagen fallback: decoded bytes empty ({attempt_model})")
            continue
        # Imagen trả về JPEG/PNG; chấp nhận cả hai.
        if raw.startswith(b"\x89PNG") or raw.startswith(b"\xff\xd8\xff"):
            print(f"[slide_images] Gemini Imagen fallback succeeded ({attempt_model})")
            return raw
        print(
            f"[slide_images] Gemini Imagen fallback: unexpected format "
            f"(model={attempt_model}, first 4 bytes={raw[:4]!r})"
        )
    return None


def _remove_vietnamese_diacritics(text: str) -> str:
    mapping = {
        "à": "a", "á": "a", "ả": "a", "ã": "a", "ạ": "a",
        "ă": "a", "ằ": "a", "ắ": "a", "ẳ": "a", "ẵ": "a", "ặ": "a",
        "â": "a", "ầ": "a", "ấ": "a", "ẩ": "a", "ẫ": "a", "ậ": "a",
        "è": "e", "é": "e", "ẻ": "e", "ẽ": "e", "ẹ": "e",
        "ê": "e", "ề": "e", "ế": "e", "ể": "e", "ễ": "e", "ệ": "e",
        "ì": "i", "í": "i", "ỉ": "i", "ĩ": "i", "ị": "i",
        "ò": "o", "ó": "o", "ỏ": "o", "õ": "o", "ọ": "o",
        "ô": "o", "ồ": "o", "ố": "o", "ổ": "o", "ỗ": "o", "ộ": "o",
        "ơ": "o", "ờ": "o", "ớ": "o", "ở": "o", "ỡ": "o", "ợ": "o",
        "ù": "u", "ú": "u", "ủ": "u", "ũ": "u", "ụ": "u",
        "ư": "u", "ừ": "u", "ứ": "u", "ử": "u", "ữ": "u", "ự": "u",
        "ỳ": "y", "ý": "y", "ỷ": "y", "ỹ": "y", "ỵ": "y",
        "đ": "d",
        "À": "A", "Á": "A", "Ả": "A", "Ã": "A", "Ạ": "A",
        "Ă": "A", "Ằ": "A", "Ắ": "A", "Ẳ": "A", "Ẵ": "A", "Ặ": "A",
        "Â": "A", "Ầ": "A", "Ấ": "A", "Ẩ": "A", "Ẫ": "A", "Ậ": "A",
        "È": "E", "É": "E", "Ẻ": "E", "Ẽ": "E", "Ẹ": "E",
        "Ê": "E", "Ề": "E", "Ế": "E", "Ể": "E", "Ễ": "E", "Ệ": "E",
        "Ì": "I", "Í": "I", "Ỉ": "I", "Ĩ": "I", "Ị": "I",
        "Ò": "O", "Ó": "O", "Ỏ": "O", "Õ": "O", "Ọ": "O",
        "Ô": "O", "Ồ": "O", "Ố": "O", "Ổ": "O", "Ỗ": "O", "Ộ": "O",
        "Ơ": "O", "Ờ": "O", "Ớ": "O", "Ở": "O", "Ỡ": "O", "Ợ": "O",
        "Ù": "U", "Ú": "U", "Ủ": "U", "Ũ": "U", "Ụ": "U",
        "Ư": "U", "Ừ": "U", "Ứ": "U", "Ử": "U", "Ữ": "U", "Ự": "U",
        "Ý": "Y", "Ỳ": "Y", "Ỷ": "Y", "Ỹ": "Y", "Ỵ": "Y",
        "Đ": "D"
    }
    return "".join(mapping.get(c, c) for c in text)


def _stock_photo_queries(
    slide: Dict[str, Any],
    semantic: Dict[str, Any],
    content_type: str,
    risk: Optional[str],
) -> List[str]:
    """Xây dựng các truy vấn tìm kiếm cho các nhà cung cấp ảnh stock/tham chiếu dự phòng bên ngoài."""
    title = str(slide.get("title") or "").strip()
    context = _semantic_context(slide, max_chars=320)
    topic = str(semantic.get("main_topic") or title).strip()
    entities = _semantic_list(semantic.get("entities"))[:3]
    action = str(semantic.get("action") or "").strip()
    obj = str(semantic.get("object") or "").strip()
    queries: List[str] = []

    # Ưu tiên 1: Sử dụng các truy vấn tìm kiếm do LLM tạo ra nếu có
    llm_queries = _semantic_list(semantic.get("stock_queries"))
    if llm_queries:
        queries.extend(llm_queries)

    # Ưu tiên 2: Các truy vấn heuristic chuẩn
    if risk == "person_protected":
        queries.extend(entities[:2])
        if title:
            queries.append(title)
    elif content_type == "historical":
        region = _detect_historical_region(context) or ""
        year = _extract_year_token(context) or ""
        entity = _extract_historical_entity(context) or ""
        if entity:
            queries.append(" ".join(x for x in [entity, region, year] if x))
        if topic:
            queries.append(" ".join(x for x in [topic, region, year] if x))
        if title:
            queries.append(title)
    elif risk in {"cultural", "religious"}:
        queries.extend(entities[:1])
        if topic:
            queries.append(topic)
        if title:
            queries.append(title)
    else:
        businessish = " ".join(x for x in [topic, action, obj] if x).strip()
        if businessish:
            queries.append(businessish)
        if title:
            queries.append(title)
        if topic and obj and obj.lower() not in topic.lower():
            queries.append(f"{topic} {obj}")

    if context:
        queries.append(context)

    # Ưu tiên 3: Các phương án dự phòng đơn giản hơn (nhóm trung bình)
    if topic:
        queries.append(topic)
    for ent in entities:
        queries.append(ent)
    if obj:
        for part in obj.split(","):
            queries.append(part.strip())

    # Ưu tiên 4: Các phương án dự phòng theo domain chung (an toàn tối đa)
    is_vietnam = False
    if _has_vietnamese_diacritics(title) or _has_vietnamese_diacritics(context):
        is_vietnam = True
    elif _detect_historical_region(context) == "Vietnam":
        is_vietnam = True

    if is_vietnam:
        if content_type == "historical" or risk == "person_protected":
            queries.extend(["Vietnam history", "old Vietnam", "Vietnam traditional", "Vietnam peasant"])
        else:
            queries.extend(["Vietnam workspace", "Vietnam school", "Vietnam"])
    
    # Các truy vấn dự phòng theo domain chung
    domain = str(semantic.get("domain") or "general").strip().lower()
    if domain == "business":
        queries.extend(["business office meeting", "corporate workspace", "business professional"])
    elif domain == "technology":
        queries.extend(["technology computer coding", "digital workspace", "programming coding"])
    elif domain == "medical":
        queries.extend(["healthcare medical clinic", "doctor hospital", "medical laboratory"])
    elif domain == "education":
        queries.extend(["classroom school university", "students studying", "classroom teaching"])
    else:
        queries.extend(["workspace documentation", "office desk laptop", "office presentation"])

    # Lọc và giữ nguyên thứ tự: thử các truy vấn cụ thể (>=2 từ) trước, sau đó là các từ đơn dự phòng
    seen = set()
    ordered = []
    for q in queries:
        q_clean = " ".join(str(q or "").strip().split())
        if not q_clean:
            continue
        # Thay thế các thuật ngữ liên quan đến bản đồ bằng "documents" để tránh lấy phải ảnh stock có bản đồ quốc gia không chính xác
        q_clean = re.sub(r"\b(world map|country map|vietnam map|map of vietnam|map|maps)\b", "documents", q_clean, flags=re.IGNORECASE)
        q_clean = " ".join(q_clean.split())
        
        # Loại bỏ dấu tiếng Việt để tương thích với các công cụ tìm kiếm và kiểm tra ASCII
        q_ascii = _remove_vietnamese_diacritics(q_clean)
        
        if not q_ascii or q_ascii.lower() in seen or not _is_mostly_ascii(q_ascii):
            continue
        seen.add(q_ascii.lower())
        ordered.append(q_ascii)
        
    return ordered



def _stock_photo_providers(content_type: str, risk: Optional[str]) -> List[str]:
    """Ưu tiên Wikimedia cho nội dung thực tế/lịch sử; Pexels cho ảnh stock chung chung."""
    factual_reference_risks = {
        "person_protected",
        "cultural",
        "religious",
        "political_sensitive",
        "crisis_sensitive",
        "legal_sensitive",
        "identity_sensitive",
        "child_sensitive",
        "map_symbol_sensitive",
    }
    if risk in factual_reference_risks or content_type == "historical":
        return ["wikimedia", "pexels"]
    return ["pexels", "wikimedia"]


async def _stock_query_completion(client: httpx.AsyncClient, prompt: str) -> str:
    """Write the stock-photo search queries, through the gateway first.

    This is an ordinary text call, so it follows the same order as the rest of the pipeline: the
    9Router gateway, which holds the working quota, and a direct Gemini call only after it. It
    used to go straight to Gemini, so an exhausted or missing key left the slide searching with
    nothing but its weak keyword queries.
    """
    from config import VLLM_API_BASE_URL
    base = (VLLM_API_BASE_URL or "").strip().rstrip("/")
    key = os.getenv("VLLM_API_KEY", "").strip()
    if base and key:
        try:
            resp = await client.post(
                f"{base}/v1/chat/completions",
                json={
                    "model": os.getenv("LLM_MODEL", "").strip() or "free-combo",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 512,
                    "stream": False,
                },
                headers={"Authorization": f"Bearer {key}"},
                timeout=45.0,
            )
            if resp.status_code == 200:
                text = str(((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
                if text:
                    return text
            else:
                print(f"[stock_photos] gateway query generation failed (status={resp.status_code})")
        except Exception as error:
            print(f"[stock_photos] gateway query generation error: {type(error).__name__}")

    if not GEMINI_API_KEY:
        return ""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{(GEMINI_MODEL or 'gemini-2.5-flash').strip()}:generateContent"
    )
    req = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 512,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    try:
        resp = await client.post(url, json=req, headers={"x-goog-api-key": GEMINI_API_KEY}, timeout=20.0)
        if resp.status_code != 200:
            return ""
        parts = (((resp.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
        return "\n".join(str(p.get("text") or "") for p in parts if isinstance(p, dict)).strip()
    except Exception:
        return ""


async def _gemini_stock_photo_queries(
    client: httpx.AsyncClient,
    slide: Dict[str, Any],
    semantic: Dict[str, Any],
    content_type: str,
    risk: Optional[str],
) -> List[str]:
    """Tạo các truy vấn tìm kiếm ảnh stock/tham chiếu ngắn bằng tiếng Anh cho các trường hợp ngữ nghĩa yếu."""
    title = str(slide.get("title") or "").strip()
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        bullet_text = bullets
    else:
        bullet_text = "\n".join(str(x) for x in bullets[:5])
    prompt = (
        "Create 5 concise English search queries for Wikimedia Commons or stock photo search.\n"
        "Goal: find real reference images for a presentation slide, not generate an image.\n"
        "Prefer factual event/person/place terms, official English names, years, country names, "
        "and broad fallback queries if exact images are unlikely.\n"
        "Avoid Vietnamese diacritics. Avoid invented scene descriptions.\n"
        "Return ONLY a JSON array of strings.\n\n"
        f"content_type: {content_type}\n"
        f"risk: {risk or ''}\n"
        f"title: {title}\n"
        f"semantic_topic: {semantic.get('main_topic') or ''}\n"
        f"entities: {semantic.get('entities') or []}\n"
        f"slide_text:\n{bullet_text[:1200]}"
    )
    text = await _stock_query_completion(client, prompt)
    if not text:
        return []
    try:
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
        parsed = json.loads(text)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    queries: List[str] = []
    for item in parsed:
        q = " ".join(str(item or "").strip().split())
        if not q or not _is_mostly_ascii(q):
            continue
        queries.append(q[:120])
    return queries[:5]



async def _try_stock_photo_fallback(
    client: httpx.AsyncClient,
    slide: Dict[str, Any],
    semantic: Dict[str, Any],
    content_type: str,
    risk: Optional[str],
    vlm_validate_fn: Optional[Callable[[bytes, Dict[str, Any]], Awaitable[bool]]] = None,
) -> Optional[Dict[str, Any]]:
    if not STOCK_PHOTO_ENABLE:
        return None
    queries = _stock_photo_queries(slide, semantic, content_type, risk)
    weak_stock_queries = not _semantic_list(semantic.get("stock_queries")) or float(semantic.get("confidence") or 0.0) < 0.5
    if weak_stock_queries or content_type == "historical" or risk in {
        "person_protected",
        "cultural",
        "religious",
        "political_sensitive",
        "crisis_sensitive",
        "legal_sensitive",
        "identity_sensitive",
        "child_sensitive",
        "map_symbol_sensitive",
        "finance_sensitive",
    }:
        ai_queries = await _gemini_stock_photo_queries(client, slide, semantic, content_type, risk)
        if ai_queries:
            queries = ai_queries + queries
    return await fetch_external_image(
        client,
        queries=queries,
        providers=_stock_photo_providers(content_type, risk),
        pexels_api_key=PEXELS_API_KEY,
        vlm_validate_fn=vlm_validate_fn,
    )
