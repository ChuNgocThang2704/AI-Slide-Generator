from __future__ import annotations
import base64
import re
from typing import Any, Dict, List, Optional, Callable, Awaitable

import httpx

from config import (
    IMAGE_FALLBACK_MODEL,
    IMAGE_FALLBACK_TIMEOUT_SEC,
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




async def _try_secondary_ai_image_fallback(
    client: httpx.AsyncClient,
    *,
    prompt: str,
    negative_prompt: str,
    payload_template: Dict[str, Any],
) -> Optional[bytes]:
    """Try Gemini Imagen as secondary image fallback.

    Replaces Together/FLUX which suffers persistent rate-limit errors.
    Uses Google Cloud Vertex AI if enabled, otherwise falls back to AI Studio.
    """
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
            continue
        data = resp.json()
        
        b64_val = None
        if "imagen-4.0" in attempt_model:
            # Response shape for Imagen 4: {"predictions": [{"bytesBase64Encoded": "<b64>", "mimeType": "image/png"}]}
            predictions = data.get("predictions") or []
            if predictions and isinstance(predictions[0], dict):
                b64_val = predictions[0].get("bytesBase64Encoded")
        else:
            # Response shape for Imagen 3: {"generatedImages": [{"image": {"imageBytes": "<b64>"}}]}
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
        # Imagen returns JPEG/PNG; accept both.
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
    """Build search queries for external stock/reference fallback providers."""
    title = str(slide.get("title") or "").strip()
    context = _semantic_context(slide, max_chars=320)
    topic = str(semantic.get("main_topic") or title).strip()
    entities = _semantic_list(semantic.get("entities"))[:3]
    action = str(semantic.get("action") or "").strip()
    obj = str(semantic.get("object") or "").strip()
    queries: List[str] = []

    # Priority 1: Use LLM-generated search queries if available
    llm_queries = _semantic_list(semantic.get("stock_queries"))
    if llm_queries:
        queries.extend(llm_queries)

    # Priority 2: Standard heuristic queries
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

    # Priority 3: Simpler fallbacks (medium tier)
    if topic:
        queries.append(topic)
    for ent in entities:
        queries.append(ent)
    if obj:
        for part in obj.split(","):
            queries.append(part.strip())

    # Priority 4: Generic domain fallbacks (fail-safe)
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
    
    # Generic domain fallback queries
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

    # Filter and preserve order: try specific queries (>=2 words) first, then single-word fallbacks
    seen = set()
    ordered = []
    for q in queries:
        q_clean = " ".join(str(q or "").strip().split())
        if not q_clean:
            continue
        # Replace map-related terms with "documents" to avoid getting stock photos with incorrect country maps
        q_clean = re.sub(r"\b(world map|country map|vietnam map|map of vietnam|map|maps)\b", "documents", q_clean, flags=re.IGNORECASE)
        q_clean = " ".join(q_clean.split())
        
        # Strip Vietnamese diacritics to make it compatible with search engines and ASCII checks
        q_ascii = _remove_vietnamese_diacritics(q_clean)
        
        if not q_ascii or q_ascii.lower() in seen or not _is_mostly_ascii(q_ascii):
            continue
        seen.add(q_ascii.lower())
        ordered.append(q_ascii)
        
    return ordered



def _stock_photo_providers(content_type: str, risk: Optional[str]) -> List[str]:
    """Prefer Wikimedia for factual/historical content; Pexels for generic stock."""
    if risk in {"person_protected", "cultural", "religious"} or content_type == "historical":
        return ["wikimedia", "pexels"]
    return ["pexels", "wikimedia"]



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
    return await fetch_external_image(
        client,
        queries=_stock_photo_queries(slide, semantic, content_type, risk),
        providers=_stock_photo_providers(content_type, risk),
        pexels_api_key=PEXELS_API_KEY,
        vlm_validate_fn=vlm_validate_fn,
    )
