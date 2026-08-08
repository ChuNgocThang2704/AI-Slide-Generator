from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from PIL import Image

from config import IMAGE_DIR

try:
    import fitz
except ImportError:  # pragma: no cover - deployment installs PyMuPDF
    fitz = None


_CAPTION_RE = re.compile(
    r"^\s*(?:figure|fig\.?|hình|hinh|chart|biểu\s*đồ|bieu\s*do|diagram|sơ\s*đồ|so\s*do)\s*\d+[\w.-]*\s*[:.\-–—]?\s*(.*)$",
    re.IGNORECASE,
)
_TABLE_RE = re.compile(r"^\s*(?:table|bảng|bang)\s*\d+", re.IGNORECASE)
_TOKEN_STOP = {
    "and", "the", "for", "with", "from", "this", "that", "figure", "chart",
    "hinh", "bieu", "do", "slide", "trang", "cac", "cho", "cua", "trong", "voi",
}


def _fold(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_text.lower()).strip()


def _tokens(value: Any) -> Set[str]:
    return {
        token
        for token in re.sub(r"[^a-z0-9]+", " ", _fold(value)).split()
        if len(token) >= 3 and token not in _TOKEN_STOP
    }


def _block_text(block: Dict[str, Any]) -> str:
    parts: List[str] = []
    for line in block.get("lines") or []:
        for span in line.get("spans") or []:
            text = str(span.get("text") or "").strip()
            if text:
                parts.append(text)
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _visual_kind(caption: str) -> str:
    folded = _fold(caption)
    if any(term in folded for term in ("chart", "bieu do", "confusion matrix", "curve")):
        return "chart"
    if any(term in folded for term in ("diagram", "so do", "workflow", "architecture")):
        return "diagram"
    return "figure"


def _nearest_caption(
    bbox: Sequence[float],
    caption_blocks: Sequence[Dict[str, Any]],
) -> str:
    x0, y0, x1, y1 = [float(value) for value in bbox]
    best: Optional[tuple[float, str]] = None
    for item in caption_blocks:
        cx0, cy0, cx1, cy1 = item["bbox"]
        horizontal_overlap = max(0.0, min(x1, cx1) - max(x0, cx0))
        if horizontal_overlap <= 0:
            continue
        if cy0 >= y1:
            distance = cy0 - y1
        elif cy1 <= y0:
            distance = (y0 - cy1) + 25.0
        else:
            distance = 0.0
        if distance > 110:
            continue
        if best is None or distance < best[0]:
            best = (distance, item["text"])
    return best[1] if best else ""


def _save_visual_bytes(
    raw: bytes,
    destination: Path,
    *,
    min_width: int = 256,
    min_height: int = 256,
) -> Optional[tuple[int, int, str]]:
    try:
        from io import BytesIO

        with Image.open(BytesIO(raw)) as image:
            image.load()
            width, height = image.size
            if width < min_width or height < min_height:
                return None
            rgb = image.convert("RGB")
            destination.parent.mkdir(parents=True, exist_ok=True)
            rgb.save(destination, format="JPEG", quality=94, optimize=True)
        digest = hashlib.sha256(raw).hexdigest()
        return width, height, digest
    except Exception:
        return None


def extract_pdf_visual_candidates(
    pdf_path: str | Path,
    task_id: str,
    *,
    max_candidates: int = 48,
) -> List[Dict[str, Any]]:
    """Extract usable raster figures and rendered vector figures from a PDF."""
    if fitz is None:
        return []
    source = Path(pdf_path)
    if source.suffix.lower() != ".pdf" or not source.is_file():
        return []

    output_dir = IMAGE_DIR / "source" / str(task_id)
    candidates: List[Dict[str, Any]] = []
    seen_hashes: Set[str] = set()
    document = fitz.open(str(source))
    try:
        for page_index, page in enumerate(document):
            if len(candidates) >= max_candidates:
                break
            page_number = page_index + 1
            page_rect = page.rect
            page_area = max(1.0, float(page_rect.width * page_rect.height))
            page_dict = page.get_text("dict")
            blocks = page_dict.get("blocks") or []
            caption_blocks: List[Dict[str, Any]] = []
            for block in blocks:
                if int(block.get("type", 0)) != 0:
                    continue
                text = _block_text(block)
                if _CAPTION_RE.match(text):
                    caption_blocks.append({"text": text[:500], "bbox": tuple(block.get("bbox") or ())})

            page_image_rects: List[fitz.Rect] = []
            for block_index, block in enumerate(blocks):
                if int(block.get("type", 0)) != 1 or not block.get("image"):
                    continue
                bbox = tuple(float(value) for value in (block.get("bbox") or ()))
                if len(bbox) != 4:
                    continue
                rect = fitz.Rect(bbox)
                area_ratio = float(rect.width * rect.height) / page_area
                if area_ratio < 0.025 or area_ratio > 0.88:
                    continue
                raw = bytes(block["image"])
                destination = output_dir / f"p{page_number:03d}_img{block_index:02d}.jpg"
                saved = _save_visual_bytes(raw, destination)
                if not saved:
                    continue
                width, height, digest = saved
                if digest in seen_hashes:
                    destination.unlink(missing_ok=True)
                    continue
                seen_hashes.add(digest)
                page_image_rects.append(rect)
                caption = _nearest_caption(bbox, caption_blocks)
                candidates.append({
                    "path": str(destination.resolve()),
                    "page": page_number,
                    "caption": caption,
                    "kind": _visual_kind(caption),
                    "bbox": [round(value, 2) for value in bbox],
                    "width": width,
                    "height": height,
                    "source": "pdf_embedded_image",
                })

            # Vector charts/diagrams are often not image blocks. Render the drawing
            # region immediately above a Figure caption when no raster overlaps it.
            drawings = page.get_drawings()
            for caption_index, caption_item in enumerate(caption_blocks):
                if len(candidates) >= max_candidates:
                    break
                caption_rect = fitz.Rect(caption_item["bbox"])
                relevant_rects: List[fitz.Rect] = []
                for drawing in drawings:
                    rect = fitz.Rect(drawing.get("rect"))
                    if rect.is_empty or rect.y1 > caption_rect.y0 + 4:
                        continue
                    if caption_rect.y0 - rect.y1 > page_rect.height * 0.58:
                        continue
                    relevant_rects.append(rect)
                if not relevant_rects:
                    continue
                union = fitz.Rect(relevant_rects[0])
                for rect in relevant_rects[1:]:
                    union |= rect
                union.x0 = max(page_rect.x0, union.x0 - 8)
                union.x1 = min(page_rect.x1, union.x1 + 8)
                union.y0 = max(page_rect.y0, union.y0 - 8)
                union.y1 = min(caption_rect.y0 - 3, union.y1 + 8)
                area_ratio = float(union.width * union.height) / page_area
                if area_ratio < 0.04 or union.width < 160 or union.height < 100:
                    continue
                if any((union & image_rect).get_area() / max(1.0, union.get_area()) > 0.72 for image_rect in page_image_rects):
                    continue
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=union, alpha=False)
                raw = pixmap.tobytes("png")
                digest = hashlib.sha256(raw).hexdigest()
                if digest in seen_hashes:
                    continue
                destination = output_dir / f"p{page_number:03d}_fig{caption_index:02d}.jpg"
                saved = _save_visual_bytes(raw, destination)
                if not saved:
                    continue
                width, height, _ = saved
                seen_hashes.add(digest)
                candidates.append({
                    "path": str(destination.resolve()),
                    "page": page_number,
                    "caption": caption_item["text"],
                    "kind": _visual_kind(caption_item["text"]),
                    "bbox": [round(union.x0, 2), round(union.y0, 2), round(union.x1, 2), round(union.y1, 2)],
                    "width": width,
                    "height": height,
                    "source": "pdf_rendered_figure",
                })
    finally:
        document.close()
    return candidates


def match_source_visuals_to_slides(
    candidates: Sequence[Dict[str, Any]],
    slides: Sequence[Dict[str, Any]],
    *,
    eligible_indices: Optional[Iterable[int]] = None,
    max_matches: Optional[int] = None,
) -> Dict[int, Dict[str, Any]]:
    """Match each source visual once using source-page provenance and semantics."""
    eligible = set(eligible_indices) if eligible_indices is not None else set(range(len(slides)))
    matches: Dict[int, Dict[str, Any]] = {}
    used_paths: Set[str] = set()
    scored: List[tuple[int, int, int, Dict[str, Any]]] = []
    for index, slide in enumerate(slides):
        if index not in eligible or not isinstance(slide, dict):
            continue
        layout = str(slide.get("layout") or "").lower()
        if layout in {"intro", "title", "thankyou", "thank_you"} or slide.get("table") or slide.get("chart"):
            continue
        source_pages = {
            int(page) for page in (slide.get("source_pages") or [])
            if str(page).isdigit() and int(page) > 0
        }
        if not source_pages:
            continue
        slide_text = " ".join(
            [str(slide.get("title") or "")]
            + [str(item) for item in (slide.get("bullets") or [])]
        )
        slide_tokens = _tokens(slide_text)
        for candidate_index, candidate in enumerate(candidates):
            if str(candidate.get("kind") or "") == "table":
                continue
            page = int(candidate.get("page") or 0)
            if page not in source_pages:
                continue
            caption_tokens = _tokens(candidate.get("caption"))
            overlap = len(slide_tokens & caption_tokens)
            score = 10 + min(10, overlap * 2)
            if str(candidate.get("kind") or "") in {"chart", "diagram"}:
                score += 1
            scored.append((score, -index, candidate_index, candidate))

    for score, neg_index, _candidate_index, candidate in sorted(scored, reverse=True):
        index = -neg_index
        path = str(candidate.get("path") or "")
        if index in matches or not path or path in used_paths:
            continue
        matches[index] = {**candidate, "match_score": score}
        used_paths.add(path)
        if max_matches is not None and len(matches) >= max(0, int(max_matches)):
            break
    return matches


async def match_source_visuals_with_ai(
    content_extractor,
    candidates: Sequence[Dict[str, Any]],
    slides: Sequence[Dict[str, Any]],
    *,
    eligible_indices: Optional[Iterable[int]] = None,
    existing_matches: Optional[Dict[int, Dict[str, Any]]] = None,
    max_matches: Optional[int] = None,
) -> Dict[int, Dict[str, Any]]:
    """Fill deterministic misses with one constrained multilingual AI mapping pass."""
    matches = dict(existing_matches or {})
    match_cap = int(max_matches) if max_matches is not None else len(candidates)
    if len(matches) >= match_cap or not hasattr(content_extractor, "_request_json_dict"):
        return matches

    eligible = set(eligible_indices) if eligible_indices is not None else set(range(len(slides)))
    eligible -= set(matches)
    used_paths = {str(item.get("path") or "") for item in matches.values()}
    available_candidates = [
        (index, candidate)
        for index, candidate in enumerate(candidates)
        if str(candidate.get("path") or "") not in used_paths
    ]
    if not eligible or not available_candidates:
        return matches

    slide_payload = []
    for index in sorted(eligible):
        if index < 0 or index >= len(slides) or not isinstance(slides[index], dict):
            continue
        slide = slides[index]
        layout = str(slide.get("layout") or "").lower()
        if layout in {"intro", "title", "thankyou", "thank_you"} or slide.get("table") or slide.get("chart"):
            continue
        slide_payload.append({
            "slide_index": index,
            "title": str(slide.get("title") or "")[:240],
            "bullets": [str(item)[:300] for item in (slide.get("bullets") or [])[:6]],
            "source_pages": list(slide.get("source_pages") or [])[:8],
        })
    candidate_payload = [
        {
            "candidate_index": index,
            "page": int(candidate.get("page") or 0),
            "caption": str(candidate.get("caption") or "")[:500],
            "kind": str(candidate.get("kind") or "figure"),
        }
        for index, candidate in available_candidates
    ]
    if not slide_payload:
        return matches

    messages = [
        {
            "role": "system",
            "content": (
                "Match figures extracted from a source PDF to presentation slides. Captions and slides "
                "may use different languages. Match only when the figure directly supports the slide's "
                "main subject; source_pages are strong evidence but not mandatory. Use each candidate and "
                "each slide at most once. Reject decorative, generic, or weakly related figures. Return only "
                'JSON: {"matches":[{"slide_index":0,"candidate_index":1,"confidence":0.85}]}.'
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {"slides": slide_payload, "source_visuals": candidate_payload},
                ensure_ascii=False,
            ),
        },
    ]
    try:
        response = await content_extractor._request_json_dict(
            messages,
            target_slides=1,
            fast_mode=True,
        )
    except Exception as error:
        print(f"[source_visuals] AI matching skipped: {error}")
        return matches

    decisions = response.get("matches") if isinstance(response, dict) else None
    if not isinstance(decisions, list):
        return matches
    candidate_map = {index: candidate for index, candidate in available_candidates}
    used_candidate_indices: Set[int] = set()
    valid_decisions = [item for item in decisions if isinstance(item, dict)]

    def _confidence(item: Dict[str, Any]) -> float:
        try:
            return float(item.get("confidence") or 0)
        except (TypeError, ValueError):
            return 0.0

    for decision in sorted(
        valid_decisions,
        key=_confidence,
        reverse=True,
    ):
        try:
            slide_index = int(decision.get("slide_index"))
            candidate_index = int(decision.get("candidate_index"))
            confidence = float(decision.get("confidence") or 0)
        except (TypeError, ValueError):
            continue
        if (
            confidence < 0.65
            or slide_index not in eligible
            or slide_index in matches
            or candidate_index not in candidate_map
            or candidate_index in used_candidate_indices
        ):
            continue
        matches[slide_index] = {
            **candidate_map[candidate_index],
            "match_score": round(confidence * 100),
            "match_source": "ai_multilingual",
        }
        used_candidate_indices.add(candidate_index)
        if len(matches) >= match_cap:
            break
    return matches
