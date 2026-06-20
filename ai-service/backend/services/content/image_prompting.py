"""Image prompt helpers used by the content extractor.

These helpers are intentionally small and rule-based.  They only support the
image side-channel of the extractor; the main text pipeline should not depend
on image-specific keyword maps.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


SLIDE_TYPE_PHOTO_CONTEXT: Dict[str, str] = {
    "intro": "Use a wide establishing shot that sets a c  onfident professional tone.",
    "data": "Show someone analyzing information: screens or documents in a focused workspace.",
    "process": "Depict a hands-on activity in progress: people doing steps, tools in use.",
    "benefit": "Show a positive outcome: satisfied people, finished product, or bright successful moment.",
    "problem": "Suggest tension: person looking concerned, an obstacle, or a cluttered situation.",
    "solution": "Show resolution: clarity, handshake, clean workspace, or a moment of relief.",
    "conclusion": "Depict closure or forward momentum: team aligning, open horizon, or confident speaker.",
    "default": "Choose the most concrete, photographable element from the slide content.",
}

SLIDE_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "intro": ["giới thiệu", "introduction", "overview", "agenda", "mục tiêu", "objective"],
    "data": ["số liệu", "thống kê", "data", "statistics", "metric", "kpi", "tỷ lệ", "percent"],
    "process": ["quy trình", "process", "bước", "step", "workflow", "pipeline", "giai đoạn"],
    "benefit": ["lợi ích", "benefit", "advantage", "ưu điểm", "hiệu quả", "result", "outcome"],
    "problem": ["vấn đề", "problem", "challenge", "thách thức", "risk", "rủi ro", "hạn chế"],
    "solution": ["giải pháp", "solution", "cách", "approach", "strategy", "chiến lược"],
    "conclusion": ["kết luận", "conclusion", "tóm tắt", "summary", "next step", "kế hoạch tiếp"],
}

DOMAIN_OBJECTS: Dict[str, str] = {
    "ui_product": "smartphone mockup and wireframe printouts",
    "startup_business": "pitch deck printouts and team around a laptop",
    "data_analytics": "analytics screens and printed performance report",
    "education_training": "lesson materials and notebook on a desk",
    "general": "documents and practical tools on desk",
}

SDXL_NOISY_RE = re.compile(
    r"\b(infographic|flowchart|flow\s+chart|user\s+interface|bar\s+chart|line\s+chart|"
    r"pie\s+chart|screenshot|dashboard|diagram\s+with|presentation\s+slide|"
    r"neural\s+network\s+diagram|labeled\s+chart|mind\s*map|whiteboard)\b",
    re.IGNORECASE,
)


def detect_slide_type_for_image(slide: Dict[str, Any]) -> str:
    title = (slide.get("title") or "").lower()
    bullets = slide.get("bullets") or slide.get("content") or []
    body = " ".join(str(b) for b in (bullets if isinstance(bullets, list) else [bullets])[:4]).lower()
    text = f"{title} {body}"
    for stype, keywords in SLIDE_TYPE_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return stype
    return "default"


def build_slide_context_for_image(slide: Dict[str, Any], max_chars: int = 600) -> str:
    title = (slide.get("title") or "").strip()
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        points = [bullets.strip()]
    else:
        points = [str(b).strip() for b in bullets[:5] if str(b).strip()]
    lines = []
    if title:
        lines.append(f"Title: {title}")
    if points:
        lines.append("Bullets:")
        lines.extend(f"  - {point}" for point in points)
    return "\n".join(lines)[:max_chars]


def scrub_sdxl_prompt(text: str) -> str:
    cleaned = SDXL_NOISY_RE.sub(" ", (text or "").strip())
    return " ".join(cleaned.split())
