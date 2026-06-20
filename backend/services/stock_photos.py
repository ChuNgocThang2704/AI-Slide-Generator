"""Fetch external stock/reference images as a fallback when SDXL fails."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Callable, Awaitable

import httpx

import io
from PIL import Image

_WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
_PEXELS_API = "https://api.pexels.com/v1/search"
_ALLOWED_MIME_PREFIXES = ("image/jpeg", "image/png", "image/webp")


def _normalize_query(query: str) -> str:
    return " ".join(str(query or "").strip().split())


def _guess_extension(mime: str, url: str) -> str:
    mime_l = (mime or "").lower()
    url_l = (url or "").lower()
    if "png" in mime_l or url_l.endswith(".png"):
        return ".png"
    if "webp" in mime_l or url_l.endswith(".webp"):
        return ".webp"
    return ".jpg"


async def _download_image(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    if not url:
        return None
    req_headers = dict(headers) if headers else {}
    if "wikimedia.org" in url and "User-Agent" not in req_headers:
        req_headers["User-Agent"] = "DemoDoanSlideGenerator/1.0 (nguyen@demodoan.edu.vn)"
    try:
        r = await client.get(url, headers=req_headers, timeout=15.0)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    mime = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    if mime and not any(mime.startswith(prefix) for prefix in _ALLOWED_MIME_PREFIXES):
        return None
    raw = r.content
    if len(raw) < 32:
        return None
    
    # Filter out tiny thumbnails/icons
    try:
        with Image.open(io.BytesIO(raw)) as img:
            w, h = img.size
            if w < 400 or h < 400:
                return None
    except Exception:
        return None

    return {
        "bytes": raw,
        "mime": mime or "image/jpeg",
        "extension": _guess_extension(mime, url),
    }


async def _search_wikimedia(
    client: httpx.AsyncClient,
    query: str,
) -> List[Dict[str, Any]]:
    params = {
        "action": "query",
        "format": "json",
        "origin": "*",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": "5",
        "prop": "imageinfo|info",
        "iiprop": "url|mime|extmetadata",
        "inprop": "url",
    }
    headers = {
        "User-Agent": "DemoDoanSlideGenerator/1.0 (nguyen@demodoan.edu.vn)"
    }
    try:
        r = await client.get(_WIKIMEDIA_API, params=params, headers=headers, timeout=10.0)
        data = r.json() if r.status_code == 200 else {}
    except Exception:
        return []
    pages = (data.get("query") or {}).get("pages") or {}
    if not isinstance(pages, dict):
        return []
    
    results = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        image_url = str(info.get("url") or "").strip()
        mime = str(info.get("mime") or "").strip().lower()
        if not image_url or not any(mime.startswith(prefix) for prefix in _ALLOWED_MIME_PREFIXES):
            continue
        ext = info.get("extmetadata") or {}
        results.append({
            "source": "wikimedia",
            "query": query,
            "image_url": image_url,
            "mime": mime,
            "extension": _guess_extension(mime, image_url),
            "page_url": str(page.get("fullurl") or "").strip(),
            "license": str((ext.get("LicenseShortName") or {}).get("value") or "").strip(),
            "license_url": str((ext.get("LicenseUrl") or {}).get("value") or "").strip(),
            "author": str((ext.get("Artist") or {}).get("value") or "").strip(),
        })
    return results


async def _search_pexels(
    client: httpx.AsyncClient,
    query: str,
    *,
    api_key: str,
) -> List[Dict[str, Any]]:
    if not api_key:
        return []
    params = {
        "query": query,
        "per_page": "5",
        "orientation": "landscape",
    }
    headers = {"Authorization": api_key}
    try:
        r = await client.get(_PEXELS_API, params=params, headers=headers, timeout=10.0)
        data = r.json() if r.status_code == 200 else {}
    except Exception:
        return []
    photos = data.get("photos") or []
    results = []
    for photo in photos:
        src = photo.get("src") or {}
        image_url = str(src.get("large") or src.get("large2x") or src.get("original") or "").strip()
        if not image_url:
            continue
        results.append({
            "source": "pexels",
            "query": query,
            "image_url": image_url,
            "mime": "image/jpeg",
            "extension": _guess_extension("image/jpeg", image_url),
            "page_url": str(photo.get("url") or "").strip(),
            "author": str(photo.get("photographer") or "").strip(),
            "license": "Pexels License",
            "license_url": "https://www.pexels.com/license/",
        })
    return results


async def fetch_external_image(
    client: httpx.AsyncClient,
    *,
    queries: List[str],
    providers: List[str],
    pexels_api_key: str = "",
    vlm_validate_fn: Optional[Callable[[bytes, Dict[str, Any]], Awaitable[bool]]] = None,
) -> Optional[Dict[str, Any]]:
    """Try external providers in order and return binary + metadata."""
    query_list = []
    seen = set()
    for raw in queries:
        q = _normalize_query(raw)
        if not q:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        query_list.append(q)
    if not query_list:
        return None

    # Limit to top 5 queries to keep it fast and robust
    query_list = query_list[:5]

    for provider in providers:
        provider_l = str(provider or "").strip().lower()
        for query in query_list:
            candidates: List[Dict[str, Any]] = []
            if provider_l == "wikimedia":
                candidates = await _search_wikimedia(client, query)
            elif provider_l == "pexels":
                candidates = await _search_pexels(client, query, api_key=pexels_api_key)
            
            # Limit to top 3 candidates per query to keep it fast
            candidates = candidates[:3]
            
            for meta in candidates:
                downloaded = await _download_image(client, str(meta.get("image_url") or ""))
                if not downloaded:
                    continue
                
                # Check VLM relevance/safety callback if provided
                if vlm_validate_fn is not None:
                    is_valid = await vlm_validate_fn(downloaded["bytes"], meta)
                    if not is_valid:
                        continue
                        
                return {
                    **meta,
                    **downloaded,
                }
    return None

