"""Trích xuất bối cảnh ảnh / ngữ nghĩa / biểu đồ / bảng biểu từ slide.

ImageExtractionMixin cung cấp các phương thức để trích xuất prompt ảnh, siêu dữ liệu 
ngữ nghĩa (semantic metadata), cấu trúc biểu đồ (chart specs) và cấu trúc bảng (table specs) từ nội dung slide bằng LLM.
Các hằng số cấp mô-đun và hàm bổ trợ để nhận diện loại slide cũng như làm sạch prompt FLUX cũng được định nghĩa ở đây.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from services.content.prompts import (
    CHART_SPEC_SYSTEM as _CHART_SPEC_SYSTEM,
    IMAGE_SEMANTIC_SYSTEM as _IMAGE_SEMANTIC_SYSTEM,
    ONE_PASS_IMAGE_SCENE_SYSTEM as _ONE_PASS_SYSTEM,
    TABLE_CREATE_SYSTEM as _TABLE_CREATE_SYSTEM,
    TABLE_SPEC_SYSTEM as _TABLE_SPEC_SYSTEM,
)

_SLIDE_TYPE_PHOTO_CONTEXT: Dict[str, str] = {
    "intro": "Use a wide establishing shot that sets a confident professional tone.",
    "data": "Show someone analyzing information: screens or documents in a focused workspace.",
    "process": "Depict a hands-on activity in progress: people doing steps, tools in use.",
    "benefit": "Show a positive outcome: satisfied people, finished product, or bright successful moment.",
    "problem": "Suggest tension: person looking concerned, an obstacle, or a cluttered situation.",
    "solution": "Show resolution: clarity, handshake, clean workspace, or a moment of relief.",
    "conclusion": "Depict closure or forward momentum: team aligning, open horizon, or confident speaker.",
    "default": "Choose the most concrete, photographable element from the slide content.",
}

_SLIDE_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "intro": ["giới thiệu", "introduction", "overview", "agenda", "mục tiêu", "objective"],
    "data": ["số liệu", "thống kê", "data", "statistics", "metric", "kpi", "tỷ lệ", "percent"],
    "process": ["quy trình", "process", "bước", "step", "workflow", "pipeline", "giai đoạn"],
    "benefit": ["lợi ích", "benefit", "advantage", "ưu điểm", "hiệu quả", "result", "outcome"],
    "problem": ["vấn đề", "problem", "challenge", "thách thức", "risk", "rủi ro", "hạn chế"],
    "solution": ["giải pháp", "solution", "cách", "approach", "strategy", "chiến lược"],
    "conclusion": ["kết luận", "conclusion", "tóm tắt", "summary", "next step", "kế hoạch tiếp"],
}

_DOMAIN_OBJECTS: Dict[str, str] = {
    "ui_product": "smartphone mockup and wireframe printouts",
    "startup_business": "pitch deck printouts and team around a laptop",
    "data_analytics": "analytics screens and printed performance report",
    "education_training": "lesson materials and notebook on a desk",
    "general": "documents and practical tools on desk",
}

_FLUX_NOISY_RE = re.compile(
    r"\b(infographic|flowchart|flow\s+chart|user\s+interface|bar\s+chart|line\s+chart|"
    r"pie\s+chart|screenshot|dashboard|diagram\s+with|presentation\s+slide|"
    r"neural\s+network\s+diagram|labeled\s+chart|mind\s*map|whiteboard)\b",
    re.IGNORECASE,
)

def _detect_slide_type_for_image(slide: Dict[str, Any]) -> str:
    title = (slide.get("title") or "").lower()
    bullets = slide.get("bullets") or slide.get("content") or []
    body = " ".join(str(b) for b in (bullets if isinstance(bullets, list) else [bullets])[:4]).lower()
    text = f"{title} {body}"
    for stype, kws in _SLIDE_TYPE_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return stype
    return "default"


def _build_slide_context_for_image(slide: Dict[str, Any], max_chars: int = 600) -> str:
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
        lines.extend(f"  - {p}" for p in points)
    return "\n".join(lines)[:max_chars]





def _scrub_flux_prompt(text: str) -> str:
    t = _FLUX_NOISY_RE.sub(" ", (text or "").strip())
    return " ".join(t.split())

class ImageExtractionMixin:
    @staticmethod
    def _scrub_flux_positive(text: str) -> str:
        """Loại bỏ một số từ khóa dễ khiến model sinh ra sơ đồ/infographic/chữ viết trong positive prompt."""
        t = (text or "").strip()
        if not t:
            return t
        t = _FLUX_NOISY_RE.sub(" ", t)
        return " ".join(t.split())

    @staticmethod
    def _sanitize_flux_prompt(text: str) -> str:
        t = (text or "").strip()
        for prefix in (
            "Prompt:",
            "Image:",
            "English image prompt:",
            "Sure,",
            "Certainly!",
            "Here is",
        ):
            low = t.lower()
            if low.startswith(prefix.lower()):
                t = t[len(prefix) :].strip()
                break
        t = t.strip().strip('"').strip("'")
        return " ".join(t.split())

    def _fallback_flux_prompt(
        self, title: str, content_points: List[Any]
    ) -> str:
        """Tạo prompt FLUX dự phòng khi không gọi được LLM."""
        topic = (title or "presentation").strip()
        extra = ""
        if content_points:
            first = str(content_points[0]).strip()
            if first:
                extra = " " + first[:220]
        topic_en = (f"{topic}{extra}")[:200].strip()
        # Ánh xạ đơn giản: lấy noun phrase đầu, thêm ngôn ngữ stock photography
        return self._scrub_flux_positive(
            f"calm workspace scene representing {topic_en}, "
            "soft window light, clean minimal background, single subject"
        )[:300]

    def _unwrap_slide_content(self, slide_content: Dict[str, Any]):
        """Mở gói {slide, context} hoặc trả về trực tiếp. Trả về (slide, context)."""
        wrapper = slide_content if isinstance(slide_content, dict) else {}
        nested_slide = wrapper.get("slide")
        if isinstance(nested_slide, dict):
            slide = nested_slide
            ctx = wrapper.get("context")
            context = ctx if isinstance(ctx, str) else _build_slide_context_for_image(slide)
        else:
            slide = wrapper
            context = _build_slide_context_for_image(slide)
        return slide, context

    async def _extract_json_from_slide(
        self,
        slide_content: Dict[str, Any],
        system: str,
        max_tokens: int,
        label: str,
    ) -> Dict[str, Any]:
        """Triển khai dùng chung cho các hàm extract_image_semantic / chart_spec / table_spec."""
        _slide, context = self._unwrap_slide_content(slide_content)
        if not self.vllm_available and not self.gemini_available:
            return {}
        try:
            language_rule = ""
            if hasattr(self, "_output_language_instruction"):
                language_rule = str(self._output_language_instruction() or "")
            raw = await self._llm_completion_plain_text(
                [
                    {
                        "role": "system",
                        "content": (
                            system
                            + "\n"
                            + language_rule
                            + "Apply the target language to every human-readable title, header, label, "
                            "definition, and table/chart cell. Preserve code, formulas, identifiers, "
                            "proper names, and standard technical symbols exactly.\n"
                        ),
                    },
                    {"role": "user", "content": f"Slide:\n{context}\n\nJSON:"},
                ],
                max_tokens=max_tokens,
                temperature=0.1,
                json_mode=True,
            )
            match = re.search(r"\{.*\}", raw or "", flags=re.DOTALL)
            if not match:
                return {}
            data = json.loads(match.group(0))
            if not isinstance(data, dict):
                return {}
            return data
        except Exception as e:
            print(f"[{label}] LLM error: {e}")
            return {}

    async def extract_image_semantic(self, slide_content: Dict[str, Any]) -> Dict[str, Any]:
        """Trích xuất JSON ngữ nghĩa thu gọn để phục vụ phân loại ảnh và tạo prompt."""
        return await self._extract_json_from_slide(
            slide_content, _IMAGE_SEMANTIC_SYSTEM, 320, "extract_image_semantic"
        )

    async def extract_chart_spec(self, slide_content: Dict[str, Any]) -> Dict[str, Any]:
        """Trích xuất dữ liệu biểu đồ có thể chỉnh sửa từ slide có nhiều dữ liệu số."""
        return await self._extract_json_from_slide(
            slide_content, _CHART_SPEC_SYSTEM, 220, "extract_chart_spec"
        )

    async def extract_table_spec(self, slide_content: Dict[str, Any]) -> Dict[str, Any]:
        """Trích xuất tiêu đề + hàng của bảng từ nội dung slide (dạng markdown/dấu gạch đứng)."""
        return await self._extract_json_from_slide(
            slide_content, _TABLE_SPEC_SYSTEM, 900, "extract_table_spec"
        )

    async def create_table_spec(self, slide_content: Dict[str, Any]) -> Dict[str, Any]:
        """Tạo bảng mới hoàn toàn theo yêu cầu của người dùng (không phải trích xuất từ slide cũ).
        Dùng prompt CREATE thay vì EXTRACT — LLM được chỉ dẫn phải sinh ra đủ cột/hàng theo yêu cầu,
        không bao giờ trả về empty.
        """
        return await self._extract_json_from_slide(
            slide_content, _TABLE_CREATE_SYSTEM, 900, "create_table_spec"
        )

    async def extract_image_scene(
        self, slide_content: Dict[str, Any], system_prompt: str = ""
    ) -> str:
        """Tạo mô tả bối cảnh ảnh (scene) trong một lượt gọi duy nhất từ nội dung slide.

        Hỗ trợ cả hai dạng cấu trúc đầu vào để tương thích ngược:
        - Dict slide trực tiếp: {"title", "bullets"/"content", ...}
        - Dict wrapper: {"slide": {...}, "context": "..."}
        """
        wrapper = slide_content if isinstance(slide_content, dict) else {}
        slide, context = self._unwrap_slide_content(slide_content)
        if not isinstance(slide, dict):
            slide = {}
            context = ""
        domain = (
            wrapper.get("domain")
            if isinstance(wrapper.get("domain"), str) and wrapper.get("domain")
            else "general"
        )
        domain_object = (
            wrapper.get("domain_object")
            if isinstance(wrapper.get("domain_object"), str) and wrapper.get("domain_object")
            else _DOMAIN_OBJECTS.get(domain, _DOMAIN_OBJECTS["general"])
        )

        raw_bullets = slide.get("bullets") or slide.get("content") or []
        content_points = [raw_bullets] if isinstance(raw_bullets, str) else list(raw_bullets or [])
        title = (slide.get("title") or "").strip()

        if not self.vllm_available:
            return self._fallback_flux_prompt(title, content_points)

        slide_type = _detect_slide_type_for_image(slide)
        photo_hint = _SLIDE_TYPE_PHOTO_CONTEXT.get(slide_type, _SLIDE_TYPE_PHOTO_CONTEXT["default"])
        sys_msg = system_prompt.strip() if system_prompt.strip() else _ONE_PASS_SYSTEM
        hint_tag = f"COMPOSITION HINT ({slide_type.upper()})"
        if hint_tag not in sys_msg:
            sys_msg = f"{sys_msg.rstrip()}\n\n{hint_tag}: {photo_hint}"
        sys_msg = (
            f"{sys_msg.rstrip()}\n"
            f"\nDOMAIN HINT: {domain.upper()}"
            f"\nREQUIRED OBJECT: {domain_object}"
        )

        revision_instruction = str(slide.get("_image_revision_instruction") or "").strip()

        if revision_instruction:
            # Khi có yêu cầu sửa ảnh cụ thể từ user, đưa thẳng vào user_msg dưới dạng constraint bắt buộc.
            # Đây là fix tổng quát — hoạt động với mọi domain/yêu cầu, không cần keyword hardcoded.
            user_msg = (
                f"{context}\n\n"
                f"USER IMAGE REQUEST (MANDATORY — build the scene around this, translate to English visuals):\n"
                f"{revision_instruction}\n\n"
                f"Domain: {domain}\n"
                f"Must include object: {domain_object}\n\n"
                "Scene description (15-25 English words, real photographable scene matching the user request, no text/diagrams):"
            )
        else:
            user_msg = (
                f"{context}\n\n"
                f"Domain: {domain}\n"
                f"Must include object: {domain_object}\n\n"
                "Scene description (15-25 English words, real photographable scene, no text/diagrams):"
            )

        try:
            raw = await self._llm_completion_plain_text(
                [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
                max_tokens=80,
                temperature=0.2,
            )
            result = _scrub_flux_prompt(self._sanitize_flux_prompt(raw))
            if len(result.split()) >= 8:
                return result[:500]
        except Exception as e:
            print(f"[extract_image_scene] LLM error: {e}")

        fallback = _scrub_flux_prompt(
            f"{photo_hint} Include {domain_object}. The scene is related to: {title}."
        )
        return fallback[:300]

    async def extract_keywords_for_image(self, slide_content: Dict[str, Any]) -> str:
        """Hàm bọc (wrapper) tương thích ngược cho các phần gọi cũ."""
        return await self.extract_image_scene(slide_content, system_prompt="")
