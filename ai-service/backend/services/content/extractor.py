"""Trích xuất và cấu trúc hóa nội dung sử dụng LLM

ContentExtractor orchestrates the full slide generation pipeline by
composing specialised mixins:
  - ChunkingMixin        → services.content.chunking
  - InputProcessingMixin → services.content.input_processing
  - LLMClientMixin       → services.content.llm_client
  - SlideNormalizerMixin → services.content.slide_normalizer
  - SlidePipelineMixin   → services.content.slide_pipeline
  - ImageExtractionMixin → services.content.image_extraction
"""
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable, Awaitable
import re
# pyrefly: ignore [missing-import]
import httpx

from services.content.chunking import ChunkingMixin
from services.content.errors import TaskCancelledError
from services.content.prompts import (
    ANTI_TRUNCATION_TOKEN_RULE,
    BULLETS_JSON_SCHEMA,
    BULLET_JSON_SCHEMA,
    CHART_SPEC_SYSTEM as _CHART_SPEC_SYSTEM,
    EXPANDED_TEXT_JSON_SCHEMA,
    IMAGE_SEMANTIC_SYSTEM as _IMAGE_SEMANTIC_SYSTEM,
    MAX_BULLETS_PER_SLIDE,
    MAX_WORDS_PER_BULLET,
    ONE_PASS_IMAGE_SCENE_SYSTEM as _ONE_PASS_SYSTEM,
    SECTIONS_JSON_SCHEMA,
    SLIDE_DECK_JSON_SCHEMA,
    TABLE_SPEC_SYSTEM as _TABLE_SPEC_SYSTEM,
)
from services.content.json_utils import (
    parse_json_response as _parse_json_response_util,
    try_fix_json as _try_fix_json_util,
)
from services.content.input_processing import InputProcessingMixin
from services.content.llm_client import LLMClientMixin
from services.content.slide_normalizer import SlideNormalizerMixin
from services.content.slide_pipeline import SlidePipelineMixin
from services.content.image_extraction import ImageExtractionMixin


try:
    # Optional import: keeps module usable in isolation
    from config import (
        LLM_NUM_CTX,
        LLM_REPEAT_PENALTY,
        LLM_USE_JSON_FORMAT,
        LLM_CHUNK_THRESHOLD,
        LLM_SINGLE_PASS_CHAR_LIMIT,
        LLM_FAST_MODE,
        LLM_QUALITY_MODE,
        LLM_CHUNK_TIMEOUT_SEC,
        LLM_CHUNK_FAST_TIMEOUT_SEC,
        LLM_SUBCHUNK_TIMEOUT_SEC,
        LLM_CHUNK_PARALLEL,
        VLLM_API_BASE_URL,
        VLLM_TIMEOUT_SEC,
        VLLM_BASIC_AUTH_USER,
        VLLM_BASIC_AUTH_PASS,
        GEMINI_API_KEY,
        GEMINI_MODEL,
        GEMINI_TIMEOUT_SEC,
        LLM_FINAL_COMPOSE,
        LLM_FINAL_COMPOSE_ENFORCE_OUTLINE,
        LLM_FINAL_COMPOSE_AUTO,
        LLM_FINAL_COMPOSE_AUTO_ONE_BULLET_RATIO,
        LLM_FINAL_COMPOSE_AUTO_AVG_BULLETS_BELOW,
        LLM_REFINE_EXTRA_IF_TRUNCATED,
        LLM_REFINE_MAX_EXTRA_PASSES,
        LLM_BULLET_POLISH_PASS,
        LLM_FINAL_QUALITY_GATE,
        LLM_FINAL_QUALITY_GATE_MAX_FIXES,
        LLM_PRESENTATION_STYLE_MODE,
        LLM_FINAL_DENSITY_GATE,
        LLM_FINAL_DENSITY_MIN_BULLETS,
        LLM_FINAL_DENSITY_MAX_REWRITES,
        VLLM_USE_GUIDED_JSON,
        VLLM_GUIDED_DECODING_BACKEND,
        LLM_SHORT_PATH_SKIP_SUMMARIZE,
        IMAGE_STYLE_LOCKED,
    )
except Exception:
    LLM_NUM_CTX = 8192
    LLM_REPEAT_PENALTY = 1.08
    LLM_USE_JSON_FORMAT = True
    LLM_CHUNK_THRESHOLD = 28000
    LLM_SINGLE_PASS_CHAR_LIMIT = 28000
    LLM_FAST_MODE = False
    LLM_QUALITY_MODE = False
    LLM_CHUNK_TIMEOUT_SEC = 240.0
    LLM_CHUNK_FAST_TIMEOUT_SEC = 200.0
    LLM_SUBCHUNK_TIMEOUT_SEC = 120.0
    LLM_CHUNK_PARALLEL = 2
    VLLM_API_BASE_URL = ""
    VLLM_TIMEOUT_SEC = 300.0
    VLLM_BASIC_AUTH_USER = ""
    VLLM_BASIC_AUTH_PASS = ""
    GEMINI_API_KEY = ""
    GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
    GEMINI_TIMEOUT_SEC = 120.0
    LLM_FINAL_COMPOSE = True
    LLM_FINAL_COMPOSE_ENFORCE_OUTLINE = False
    LLM_FINAL_COMPOSE_AUTO = True
    LLM_FINAL_COMPOSE_AUTO_ONE_BULLET_RATIO = 0.45
    LLM_FINAL_COMPOSE_AUTO_AVG_BULLETS_BELOW = 3.2
    LLM_REFINE_EXTRA_IF_TRUNCATED = False
    LLM_REFINE_MAX_EXTRA_PASSES = 1
    LLM_BULLET_POLISH_PASS = True
    LLM_FINAL_QUALITY_GATE = True
    LLM_FINAL_QUALITY_GATE_MAX_FIXES = 12
    LLM_PRESENTATION_STYLE_MODE = True
    LLM_FINAL_DENSITY_GATE = True
    LLM_FINAL_DENSITY_MIN_BULLETS = 3
    LLM_FINAL_DENSITY_MAX_REWRITES = 10
    VLLM_USE_GUIDED_JSON = True
    VLLM_GUIDED_DECODING_BACKEND = "outlines"
    LLM_SHORT_PATH_SKIP_SUMMARIZE = True
    IMAGE_STYLE_LOCKED = (
        "soft flat vector-style illustration, gentle blue and gray gradient background, "
        "one clear focal subject, clean minimal professional look, not photorealistic"
    )


_DECK_LANG_RULE = (
    "LANGUAGE: Match the source: English input → English slides; Vietnamese → Vietnamese. "
    "If mixed, use the dominant language. Do not translate the whole deck to another language.\n"
)

# Ký tự có dấu tiếng Việt (heuristic đoán input).
_VN_DIACRITIC_RE = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]"
)


class ContentExtractor(
    ChunkingMixin,
    InputProcessingMixin,
    LLMClientMixin,
    SlideNormalizerMixin,
    SlidePipelineMixin,
    ImageExtractionMixin,
):
    """Sử dụng LLM để trích xuất và cấu trúc hóa nội dung thành slides"""
    
    def __init__(self, model_name: str = "Qwen3-8B"):
        """Khởi tạo với model name trùng `--served-model-name` trên vLLM (OpenAI-compatible)."""
        self.model_name = model_name
        self.vllm_available = bool(VLLM_API_BASE_URL)
        self.vllm_base_url = VLLM_API_BASE_URL.rstrip("/") if self.vllm_available else ""
        self.vllm_basic_auth_user = VLLM_BASIC_AUTH_USER
        self.vllm_basic_auth_pass = VLLM_BASIC_AUTH_PASS
        self.vllm_basic_auth = (
            httpx.BasicAuth(self.vllm_basic_auth_user, self.vllm_basic_auth_pass)
            if (self.vllm_basic_auth_user and self.vllm_basic_auth_pass)
            else None
        )
        self.gemini_api_key = GEMINI_API_KEY
        self.gemini_model = GEMINI_MODEL
        self.gemini_available = bool(self.gemini_api_key and self.gemini_model)

        if self.vllm_available:
            print(
                f"Using vLLM base URL: {self.vllm_base_url} | model: {model_name}"
            )
        else:
            print(
                "Warning: VLLM_API_BASE_URL không set — extract slide chỉ dùng heuristic/fallback."
            )
        self._slide_lang_hint: str = "auto"
        # Tiến độ extract (progress_cb): đếm mỗi lần vLLM trả JSON hợp lệ.
        self._extract_progress: Optional[Dict[str, Any]] = None

    async def _progress_track_bump(self) -> None:
        """Tăng tiến độ (done/total) sau mỗi lần gọi LLM thành công + parse JSON OK."""
        st = self._extract_progress
        if not st:
            return
        st["done"] = int(st["done"]) + 1
        d = st["done"]
        t = max(int(st["total"]), d + 1)
        st["total"] = t
        await st["cb"](d, t)

    def _progress_track_begin(
        self, cb: Callable[[int, int], Awaitable[None]]
    ) -> None:
        """Ước lượng ban đầu 18 bước; total tự giãn nếu pipeline gọi nhiều LLM hơn."""
        self._extract_progress = {"cb": cb, "done": 0, "total": 18}

    async def _progress_track_finalize(self) -> None:
        """Chốt done=total trong đoạn [0,1] để callback map lên 100% của phase extract."""
        st = self._extract_progress
        if not st:
            return
        d = int(st["done"])
        t = max(int(st["total"]), d)
        if d == 0:
            await st["cb"](1, 1)
        else:
            await st["cb"](t, t)

    def _progress_track_clear(self) -> None:
        self._extract_progress = None

    def _detect_output_language_hint(self, text: str) -> str:
        """'vi' | 'en' | 'auto' — dùng để bắt model không lật sang Anh khi input Việt."""
        t = (text or "").strip()[:12000]
        if len(t) < 24:
            return "auto"
        vn_hits = len(_VN_DIACRITIC_RE.findall(t))
        letters = sum(1 for c in t if c.isalpha())
        if letters < 15:
            return "auto"
        # Có dấu tiếng Việt → ưu tiên output Việt (kể cả đoạn ngắn).
        if vn_hits >= 4 or (vn_hits >= 2 and vn_hits / max(1, letters) > 0.04):
            return "vi"
        if vn_hits <= 1 and letters > 50:
            return "en"
        return "auto"

    def _output_language_instruction(self) -> str:
        h = getattr(self, "_slide_lang_hint", "auto") or "auto"
        if h == "vi":
            return (
                "OUTPUT LANGUAGE (MANDATORY): Source is Vietnamese. "
                "Write EVERY deck title, slide title, bullet, and note in Vietnamese. "
                "Do not answer in English. Keep proper names as in the source.\n"
            )
        if h == "en":
            return (
                "OUTPUT LANGUAGE (MANDATORY): Source is English. "
                "Write EVERY deck title, slide title, bullet, and note in English. "
                "Do not translate slide text to Vietnamese.\n"
            )
        return _DECK_LANG_RULE

    def _user_lang_reminder(self) -> str:
        """Nhắc ở user message — bổ sung cho system (tránh model trả Anh khi input Việt)."""
        h = getattr(self, "_slide_lang_hint", "auto") or "auto"
        if h == "vi":
            return "\n\nReminder: all titles and bullets must be in Vietnamese (tiếng Việt)."
        if h == "en":
            return "\n\nReminder: all titles and bullets must be in English."
        return ""

    def _llm_system_prefix(self) -> str:
        """Qwen3: tắt thinking nếu model hỗ trợ (tránh chậm/timeout khi cần JSON ngắn)."""
        if "qwen3" in (self.model_name or "").lower():
            return "/nothink\n"
        return ""

    def _presentation_style_block(self, n_slides: int) -> str:
        """Prompt block for concise presentation-style output."""
        if not LLM_PRESENTATION_STYLE_MODE:
            return ""
        return (
            "PRESENTATION STYLE MODE (MUST FOLLOW):\n"
            "- Output must read like real slide bullets, not mini paragraphs.\n"
            "- Prefer keyword-first bullets: \"Keyword: concise insight.\" when natural.\n"
            "- Each bullet should be concise, presentation-style, and scannable.\n"
            "- Keep each bullet around 8–16 words (up to 18 when needed).\n"
            "- Avoid repetitive opening patterns across bullets.\n"
            "- Use varied slide intent across the deck: definition, impact, process, risk, solution, takeaway.\n"
            f"- With {max(1, int(n_slides))} slides target, ensure neighboring slides differ in angle.\n\n"
        )

    def _is_prompt_input(self, text: str) -> bool:
        """Kiểm tra xem đầu vào là một câu lệnh ngắn/dàn ý hay là một tài liệu chi tiết."""
        t = (text or "").strip()
        if not t:
            return False
        # Nếu văn bản ngắn (dưới 355 ký tự), khả năng rất cao là câu lệnh/tiêu đề
        if len(t) < 355:
            return True
        # Danh sách từ khóa tiếng Việt và tiếng Anh thường gặp ở đầu câu lệnh
        prompt_indicators = [
            "tạo một", "tạo bài", "tạo slide", "viết bài", "viết slide", "hãy viết", "hãy tạo", 
            "làm một", "làm slide", "thiết kế", "soạn slide", "soạn thảo", "viết hộ",
            "create a", "create slide", "generate a", "generate slide", "make a", "make slide",
            "write a", "write slide", "design a"
        ]
        t_lower = t.lower()
        for ind in prompt_indicators:
            if t_lower.startswith(ind):
                return True
        return False

    async def _generate_content_from_prompt(self, prompt: str, target_slides: int) -> str:
        """Sử dụng LLM để sinh ra một tài liệu chi tiết từ câu lệnh của người dùng."""
        system_msg = (
            "You are an expert content writer and researcher.\n\n"
            "TASK:\n"
            "Write a detailed, comprehensive document in the same language as the user's prompt (usually Vietnamese or English) "
            "based on the prompt. This document will be used to generate a presentation slide deck.\n\n"
            "REQUIREMENTS:\n"
            "- Write in-depth content with concrete facts, details, explanations, and structure.\n"
            "- Divide the content into logical sections using '##' followed by the section title (e.g., '## 1. Giới thiệu').\n"
            "- For each section, write detailed paragraphs explaining the concepts, why/how, impacts, and examples. Do not write short placeholders.\n"
            "- If the user's prompt includes an outline or list of slides (e.g., Slide 1: ..., Slide 2: ...), you MUST follow this structure. For each slide in the outline, create a corresponding section '## Slide Title' and write a detailed paragraph of content (at least 80-150 words of rich information) explaining that slide's topic, so that the slide generator has actual content to extract bullets from.\n"
            f"- Generate enough sections and detail to cover roughly {target_slides} slides.\n"
            "- Write in a formal, informative, and engaging tone.\n"
            "- DO NOT output slide JSON or code blocks. Output ONLY raw text/markdown content."
        )
        messages = [
            {"role": "system", "content": self._llm_system_prefix() + system_msg},
            {"role": "user", "content": f"Prompt:\n{prompt}"}
        ]
        # Set a high max_tokens to prevent truncation of the generated document.
        return await self._llm_completion_plain_text(
            messages,
            max_tokens=3500,
            temperature=0.7,
        )

    async def extract_and_structure(
        self,
        raw_content: str,
        target_slides_override: Optional[int] = None,
        force_exact_slide_count: bool = False,
        progress_cb: Optional[Callable[[int, int], Awaitable[None]]] = None,
        should_stop: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> Dict[str, Any]:
        """
        Trích xuất và cấu trúc hóa nội dung thành format phù hợp cho slide.

        Một luồng xử lý LLM sau khi có merged/summary: expand → group → generate → refine
        (hàm `_expand_group_generate_refine_pipeline`), dùng chung cho nội dung ngắn và chunking.

        progress_cb (done, total):
            Khi có backend LLM, mỗi lần gọi thành công và parse được JSON (Ollama/vLLM)
            tăng done; total ước lượng ban đầu và giãn nếu pipeline gọi nhiều lần hơn.
            Worker map đoạn này lên ~30–70% tổng job.

        Returns:
            {
                "title": "Tiêu đề chính",
                "slides": [
                    {
                        "title": "Tiêu đề slide",
                        "bullets": ["Điểm 1", "Điểm 2", ...],
                        "notes": "Ghi chú (optional)"
                    },
                    ...
                ]
            }
        """
        target_slides = int(target_slides_override or 10)

        # Nếu đầu vào là câu lệnh ngắn/dàn ý, tự động sinh nội dung chi tiết trước
        if (self.vllm_available or self.gemini_available) and self._is_prompt_input(raw_content):
            print(f"Detected prompt/outline input. Pre-generating detailed content for {target_slides} slides...")
            if progress_cb:
                await progress_cb(1, 18)
            try:
                generated_doc = await self._generate_content_from_prompt(raw_content, target_slides)
                if generated_doc and len(generated_doc.strip()) > 50:
                    raw_content = generated_doc
                    print(f"Pre-generation complete. Document length: {len(raw_content)} chars.")
            except Exception as e:
                print(f"Failed to pre-generate content from prompt: {e}. Proceeding with raw prompt.")

        self._slide_lang_hint = self._detect_output_language_hint(raw_content or "")
        if self._slide_lang_hint in ("vi", "en"):
            print(f"Slide language hint: {self._slide_lang_hint} (match source)")
        # Nếu không có vLLM, dùng fallback ngay
        if not self.vllm_available:
            structured = self._normalize_structured_content(self._fallback_structure(raw_content))
            if force_exact_slide_count and target_slides_override:
                structured = await self._force_slide_count_exact(structured, target_slides_override)
            if progress_cb:
                await progress_cb(1, 1)
            return structured

        if progress_cb:
            self._progress_track_begin(progress_cb)
        try:
            # Nếu content quá dài, dùng chunking.
            if len(raw_content) > LLM_CHUNK_THRESHOLD:
                print(
                    f"Content long ({len(raw_content)} chars > {LLM_CHUNK_THRESHOLD}), "
                    "using chunking strategy"
                )
                structured = self._normalize_structured_content(
                    await self._extract_with_chunking(
                        raw_content,
                        should_stop=should_stop,
                        target_slides_override=target_slides_override,
                    )
                )
                if force_exact_slide_count and target_slides_override:
                    structured = await self._force_slide_count_exact(structured, target_slides_override)
                return structured

            if should_stop and await should_stop():
                raise TaskCancelledError("Task cancelled by user")

            # FINAL SPEC (short content): có thể bỏ summarize để tiết kiệm 1 vòng LLM.
            merged_summary: Dict[str, str]
            if LLM_SHORT_PATH_SKIP_SUMMARIZE:
                print(
                    "Short content: skip summarize (LLM_SHORT_PATH_SKIP_SUMMARIZE); "
                    "merged body → pipeline"
                )
                merged_summary = self._merged_body_from_raw(raw_content)
                slide_plan = self._estimate_reduce_slide_plan([], merged_summary["content"])
            else:
                summary_result = await self._summarize_chunk(
                    raw_content, fast_mode=LLM_FAST_MODE
                )
                merged_summary = self._merge_chunk_summaries([summary_result])
                slide_plan = self._estimate_reduce_slide_plan(
                    [summary_result], merged_summary["content"]
                )
            target_slides = int(target_slides_override or slide_plan.get("target") or 10)

            structured = await self._expand_group_generate_refine_pipeline(
                merged_summary, target_slides
            )
            if force_exact_slide_count and target_slides_override:
                structured = await self._force_slide_count_exact(structured, target_slides_override)
            return structured
        finally:
            if progress_cb:
                await self._progress_track_finalize()
                self._progress_track_clear()

    async def _extract_compact_content(
        self,
        raw_content: str,
        target_slides: int,
        chunk_mode: bool,
        fast_mode: bool = False,
        compose_mode: bool = False,
        min_slides: Optional[int] = None,
        section_count: int = 0,
        outline: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run one chat call that returns final slide JSON for already-compact content.

        Safe retry policy:
        - Attempt 0: normal call, result is saved as best_result.
        - Attempt 1 (compose mode only): use fast_mode to reduce num_predict/VRAM pressure.
          If attempt 1 crashes, return best_result from attempt 0 instead of fallback.
        """
        best_result: Optional[Dict[str, Any]] = None

        try:
            for attempt in range(2):
                messages = self._build_compose_messages(
                    raw_content,
                    target_slides=target_slides,
                    section_count=section_count,
                    enforce_expansion=(compose_mode and attempt == 1),
                    outline=outline,
                ) if compose_mode else self._build_messages(
                    raw_content,
                    target_slides=target_slides,
                    chunk_mode=chunk_mode,
                    fast_mode=fast_mode,
                )

                # Retry uses fast_mode to cut num_predict and lower VRAM pressure.
                _fast = fast_mode or (attempt == 1 and compose_mode)

                try:
                    structured_content = await self._request_json_dict(
                        messages,
                        target_slides=target_slides,
                        fast_mode=_fast,
                        compose_mode=compose_mode,
                        structured_output=(
                            "slide_deck" if compose_mode else None
                        ),
                    )
                except TaskCancelledError:
                    raise
                except Exception as req_err:
                    print(f"LLM call attempt {attempt + 1} failed: {req_err}")
                    # Retry crashed → preserve attempt 0 result, don't fall to fallback
                    if best_result is not None:
                        print(
                            f"Retry failed; returning saved result from attempt 1 "
                            f"({len(best_result.get('slides', []))} slides)"
                        )
                        return best_result
                    continue  # attempt 0 failed, still try attempt 1

                # Soft-validate — skip invalid structure silently
                if not isinstance(structured_content, dict):
                    continue
                if "title" not in structured_content or "slides" not in structured_content:
                    continue
                if not isinstance(structured_content["slides"], list):
                    continue

                slide_count = len(structured_content.get("slides", []))
                normalized = self._normalize_structured_content(structured_content)

                # Always keep the richest valid result seen so far
                if best_result is None or slide_count > len(best_result.get("slides", [])):
                    best_result = normalized

                if compose_mode and min_slides and slide_count < min_slides and attempt == 0:
                    print(
                        f"Compose returned only {slide_count} slides (< {min_slides}), "
                        f"retrying with stronger expansion prompt"
                    )
                    continue

                print(f"Successfully parsed JSON: {slide_count} slides")
                return normalized

        except TaskCancelledError:
            raise
        except Exception as e:
            print(f"Error extracting content with LLM: {e}")

        if best_result is not None:
            print(f"Returning best saved result: {len(best_result.get('slides', []))} slides")
            return best_result
        return self._normalize_structured_content(self._fallback_structure(raw_content))


    async def _request_json_dict(
        self,
        messages: List[Dict[str, str]],
        target_slides: int,
        fast_mode: bool = False,
        compose_mode: bool = False,
        structured_output: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gọi vLLM chat và parse JSON object đầu tiên trong response.

        structured_output:
            None — không guided JSON.
            \"slide_deck\" | \"expanded_text\" | \"sections\" | \"bullet\" | \"bullets\".
        """
        _model, _msgs, _opts = self.model_name, messages, self._build_llm_options(
            target_slides=target_slides,
            fast_mode=fast_mode,
            compose_mode=compose_mode,
        )
        finish_reason: Optional[str] = None
        if not self.vllm_available and not self.gemini_available:
            raise RuntimeError(
                "No LLM backend available (vLLM/Gemini). Configure VLLM_API_BASE_URL or GEMINI_API_KEY."
            )

        ts_eff = max(1, int(target_slides or 1))
        tokens_per_slide = 200 if compose_mode else 180
        cap = 10000 if compose_mode else 6000
        max_tokens = min(ts_eff * tokens_per_slide + 300, cap)
        max_tokens = max(512, max_tokens)

        base_payload: Dict[str, Any] = {
            "model": _model,
            "messages": _msgs,
            "temperature": float(_opts.get("temperature", 0.1)),
            "top_p": float(_opts.get("top_p", 0.9)),
            "max_tokens": max_tokens,
        }
        schema_map: Dict[str, Dict[str, Any]] = {
            "slide_deck": SLIDE_DECK_JSON_SCHEMA,
            "expanded_text": EXPANDED_TEXT_JSON_SCHEMA,
            "sections": SECTIONS_JSON_SCHEMA,
            "bullet": BULLET_JSON_SCHEMA,
            "bullets": BULLETS_JSON_SCHEMA,
        }
        guided_schema = schema_map.get(structured_output or "")
        use_guided = bool(VLLM_USE_GUIDED_JSON) and guided_schema is not None
        guided_active = use_guided

        _vllm_timeout = float(VLLM_TIMEOUT_SEC)
        _vllm_connect = min(60.0, _vllm_timeout)
        timeout_cfg = httpx.Timeout(
            connect=_vllm_connect,
            read=_vllm_timeout,
            write=_vllm_timeout,
            pool=_vllm_connect,
        )

        async def _vllm_chat_once(p: Dict[str, Any]) -> tuple:
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                resp = await client.post(
                    f"{self.vllm_base_url}/v1/chat/completions",
                    json=p,
                    auth=self.vllm_basic_auth,
                )
                resp.raise_for_status()
                data = resp.json()
            choice0 = data.get("choices", [{}])[0]
            txt = (choice0.get("message") or {}).get("content", "") or ""
            fr = choice0.get("finish_reason")
            return txt.strip(), fr

        payload = dict(base_payload)
        if guided_active:
            payload["guided_json"] = guided_schema
            payload["guided_decoding_backend"] = VLLM_GUIDED_DECODING_BACKEND

        result_text = ""
        try:
            if self.vllm_available:
                try:
                    result_text, finish_reason = await _vllm_chat_once(payload)
                except httpx.HTTPStatusError as e:
                    code = e.response.status_code if e.response is not None else 0
                    if use_guided and code in (400, 422, 404):
                        print(
                            f"vLLM guided_json/backend not accepted (HTTP {code}); "
                            "retrying without guided decoding"
                        )
                        guided_active = False
                        result_text, finish_reason = await _vllm_chat_once(dict(base_payload))
                    else:
                        raise
            else:
                raise RuntimeError("vLLM unavailable")
        except Exception as vllm_err:
            if not self.gemini_available:
                raise
            
            # Detect connection failure or timeouts to disable vLLM for the rest of the session
            is_connection_error = (
                isinstance(vllm_err, httpx.RequestError)
                or "connection" in str(vllm_err).lower()
                or "timeout" in str(vllm_err).lower()
            )
            if is_connection_error and self.vllm_available:
                print(f"[ContentExtractor] vLLM connection failed: {vllm_err}. Disabling vLLM and switching to Gemini fallback.")
                self.vllm_available = False
            else:
                print(f"vLLM request failed, fallback to Gemini: {vllm_err}")

            result_text = await self._gemini_completion_plain_text(
                _msgs,
                max_tokens=max_tokens,
                temperature=float(_opts.get("temperature", 0.1)),
                json_mode=True,
            )
            finish_reason = "stop"

        if self.vllm_available and self._parse_json_response(result_text) is None and finish_reason == "length":
            payload_retry = dict(base_payload)
            retry_mt = min(
                int(max(int(base_payload["max_tokens"]), 1) * 1.5),
                10000,
            )
            payload_retry["max_tokens"] = retry_mt
            if guided_active:
                payload_retry["guided_json"] = guided_schema
                payload_retry["guided_decoding_backend"] = VLLM_GUIDED_DECODING_BACKEND
            print(
                f"vLLM JSON parse failed (finish_reason=length); "
                f"retry once with max_tokens={retry_mt}"
            )
            try:
                result_text, finish_reason = await _vllm_chat_once(payload_retry)
            except Exception:
                # Keep original result_text for JSON parsing fallback below.
                pass

        parsed = self._parse_json_response(result_text)
        if parsed is None:
            preview = (result_text or "")[:900].replace("\n", " ")
            print(f"No valid JSON parsed. finish_reason={finish_reason!r} Preview: {preview!r}")
            raise ValueError("No valid JSON found in model response")
        await self._progress_track_bump()
        return parsed

    def _parse_json_response(self, result_text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse the first JSON object returned by the model."""
        return _parse_json_response_util(
            result_text,
            clean_result_text=self._clean_result_text,
        )

    async def _extract_single_chunk(self, chunk_content: str, fast_mode: bool = False) -> Dict[str, Any]:
        """Xử lý 1 chunk với LLM (vLLM)."""
        target_slides = self._estimate_target_slides(chunk_content, chunk_mode=True)
        if fast_mode:
            target_slides = max(2, target_slides - 1)
        messages = self._build_messages(
            chunk_content,
            target_slides=target_slides,
            chunk_mode=True,
            fast_mode=fast_mode,
        )

        try:
            structured_content = await self._request_json_dict(
                messages,
                target_slides=target_slides,
                fast_mode=fast_mode,
                compose_mode=False,
                structured_output="slide_deck",
            )
            return self._normalize_structured_content(structured_content)
        except TaskCancelledError:
            raise
        except Exception as e:
            print(f"Error extracting chunk: {e}")
            return self._normalize_structured_content(self._fallback_structure(chunk_content))

    def _estimate_target_slides(self, content: str, chunk_mode: bool) -> int:
        """Estimate target slide count to keep output within token budget."""
        length = len(content or "")
        if chunk_mode:
            # For chunk flow, keep output compact enough for speed but dense enough per slide.
            if length < 2500:
                return 2
            if length < 5000:
                return 3
            return 3

        if length < 3500:
            n = 6
        elif length < 9000:
            n = 8
        else:
            n = 10

        if LLM_QUALITY_MODE:
            n = min(12, n + 1)
        if LLM_FAST_MODE:
            n = min(n, 6)
        return n

    def _build_llm_options(
        self,
        target_slides: int,
        fast_mode: bool = False,
        compose_mode: bool = False,
    ) -> Dict[str, Any]:
        """Adaptive decoding budget: enough for JSON, not too long to spill.

        Token budget per slide (JSON): keep bullets ~10–14 words to reduce finish_reason=length / cụt câu.
        """
        if fast_mode:
            num_predict = max(1000, min(1600, 520 + target_slides * 100))
        elif compose_mode:
            num_predict = max(1300, min(2600, 680 + target_slides * 155))
        else:
            num_predict = max(1450, min(2800, 800 + target_slides * 175))
        if LLM_FAST_MODE and not compose_mode:
            num_predict = int(num_predict * 0.82)
            num_predict = max(800, num_predict)
        # When quality mode: allow a bit more diversity to get "thoải mái" wording.
        # Giữ temperature thấp để hạn chế sinh bullet quá ngắn / sai schema.
        temperature = 0.05
        top_p = 0.9
        repeat_penalty = LLM_REPEAT_PENALTY
        if LLM_QUALITY_MODE:
            temperature = 0.05
            top_p = 0.95
            repeat_penalty = max(1.01, LLM_REPEAT_PENALTY - 0.02)

        if compose_mode and LLM_QUALITY_MODE:
            temperature = 0.05
            top_p = 0.95

        return {
            "temperature": temperature,
            "num_predict": num_predict,
            "top_p": top_p,
            "repeat_penalty": repeat_penalty,
            "num_ctx": LLM_NUM_CTX,
        }

    def _build_messages(
        self,
        content: str,
        target_slides: int = 8,
        chunk_mode: bool = False,
        fast_mode: bool = False,
    ) -> list:
        """Build chat messages (system + user) cho Ollama client.chat()."""
        normalized = self._normalize_for_llm(content)
        # Single-pass: đưa nhiều ký tự hơn để khỏi chunk (nhanh); cân với LLM_NUM_CTX
        content_limit = 9000 if chunk_mode else LLM_SINGLE_PASS_CHAR_LIMIT
        content_preview = normalized[:content_limit] if len(normalized) > content_limit else normalized
        if fast_mode:
            bullet_limit = 16
            bullet_chars = "35–65"
        else:
            # Ưu tiên bullet ngắn-hoàn-chỉnh để giảm cụt câu / cụt JSON khi max_tokens chạm trần.
            bullet_limit = 18
            bullet_chars = "35–90"
        if fast_mode:
            slide_range = "2-3"
        else:
            if chunk_mode:
                slide_range = "2-4"
            else:
                slide_range = f"{target_slides}-{target_slides + 2}"

        system_msg = self._llm_system_prefix() + (
            "You build presentation slides from expanded source text.\n\n"
            + self._presentation_style_block(target_slides)
            + self._output_language_instruction()
            + "HARD RULES:\n"
            "1. Return ONLY valid JSON—no text before or after the JSON object.\n"
            "2. No markdown code fences.\n"
            "3. Schema:\n"
            "{\"title\": \"...\", \"slides\": [{\"title\": \"...\", \"bullets\": [\"...\"], \"notes\": \"\"}]}\n\n"
            "BULLETS:\n"
            "- Paraphrase in your own words; keep proper names, places, numbers, dates, and technical terms from the source.\n"
            "- Each bullet: full sentence with subject and predicate; ends with a period.\n"
            f"- Each bullet: min ~10 words and ~{bullet_chars} characters (same language as source); max {bullet_limit} words. One bullet = one complete idea with context—not a label.\n"
            "- No double-quote characters inside titles/bullets.\n"
            "- No empty label-only bullets (e.g. single-word section titles).\n"
            "- Never end with ... or …\n"
            f"- Each slide: 3–5 bullets. Slide title: 3–8 words.\n"
            f"- You MUST return EXACTLY {target_slides} slides. If running out of tokens: close JSON cleanly—do not leave half sentences.\n"
            "- No duplicated content across slides.\n"
            "- If token budget is tight, finish the JSON structure; never truncate mid-sentence inside a bullet.\n"
            "- Each slide = one clear subtopic.\n"
            "- SLIDE TITLES: Never use generic placeholders ('Nội dung', 'Nội dung 1', 'Slide 1', 'Tiếp theo'). Each slide title must be specific and descriptive of its content.\n\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + "\n"
            "GOOD bullet examples (illustrative style—use the source language in actual output):\n"
            "\"Mỹ viện trợ tài chính lớn cho Pháp trong chiến tranh Đông Dương.\"\n"
            "\"Hiệp định Giơ-ne chia cắt đất nước tạm thời.\"\n\n"
            "BAD examples (copy, cut off, too short):\n"
            "\"Tại đông dương, Mỹ là nguồn tài trợ chính và to lớn của Pháp (Tháng 10 năm 1953, phó tổng...\"\n"
            "\"Thắng lợi quân sự.\" — too short, no context."
        )
        user_msg = (
            "Create slides from the expanded text below. Paraphrase; do not copy verbatim.\n\n"
            f"TEXT:\n{content_preview}\n\n"
            "If near token limit, close JSON properly: correct slide count, full bullets, no broken sentences.\n"
            "Return JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def _build_compose_messages(
        self,
        content: str,
        target_slides: int,
        section_count: int,
        enforce_expansion: bool = False,
        outline: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, str]]:
        """Build a stronger prompt for composing final slides from merged section summaries."""
        normalized = self._normalize_for_llm(content)
        # Cap at 7000 chars — merged summaries are already compact, 12000 was overkill
        # and caused unnecessarily long prefill time on low-VRAM GPUs.
        content_preview = normalized[:7000] if len(normalized) > 7000 else normalized
        if LLM_QUALITY_MODE:
            # Khi chạy server mạnh: cho AI khoảng dao động rộng hơn về số slide
            min_slides = max(8, min(target_slides, max(section_count, target_slides - 4)))
            max_slides = target_slides + 6
        else:
            min_slides = max(8, min(target_slides, max(section_count, target_slides - 2)))
            max_slides = target_slides + 2
        expansion_rule = (
            f"- Each '##' section must produce at least one slide.\n"
            f"- Total slide count MUST be exactly {target_slides}.\n"
            f"- If a slide is thin, add related bullets so each slide has 3–{MAX_BULLETS_PER_SLIDE} substantive bullets.\n"
        )
        if LLM_QUALITY_MODE:
            expansion_rule += (
                "- If a '##' section has many bullets (>=5), split into at least 2 slides for that section.\n"
            )
        if enforce_expansion:
            expansion_rule += (
                "- This pass MUST use more slides than before; do not merge many '##' sections into one slide.\n"
            )

        # Inject outline blueprint so compose step follows the plan
        if outline:
            outline_lines = "\n".join(
                f"  - {item['section']}: {item['slides']} slide(s)"
                for item in outline
            )
            outline_total = sum(item["slides"] for item in outline)
            outline_rule = (
                f"MANDATORY SLIDE PLAN:\n{outline_lines}\n"
                f"Total: {outline_total} slides.\n"
                "Follow this allocation—each section must get its assigned slide count.\n"
            )
        else:
            outline_rule = ""

        system_msg = self._llm_system_prefix() + (
            "You compose the final slide deck from intermediate summaries.\n\n"
            + self._output_language_instruction()
            + "HARD RULES:\n"
            "1. Return ONLY JSON—no text outside the JSON object.\n"
            "2. Schema: {\"title\": \"...\", \"slides\": [{\"title\": \"...\", \"bullets\": [\"...\"], \"notes\": \"\"}]}\n"
            f"3. Each bullet: complete sentence, min ~10 words and ~45 chars, target ~10–18 words, hard max {MAX_WORDS_PER_BULLET} words, ends with a period; keep names, numbers, terms; if an idea is long, use two bullets.\n"
            f"4. Each slide: 3–{MAX_BULLETS_PER_SLIDE} bullets (prefer 3–4 when tight on length); use {MAX_BULLETS_PER_SLIDE} only when every bullet stays short and complete.\n"
            f"5. The source has about {section_count} major sections.\n"
            f"6. {expansion_rule}"
            "7. Paraphrase—do not copy verbatim; stay concise but complete.\n"
            "8. SLIDE TITLES: Never use generic placeholders ('Nội dung', 'Nội dung 1', 'Slide 1', 'Tiếp theo'). Every slide title must be specific and meaningful.\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + "\n"
            + (f"9. {outline_rule}" if outline_rule else "")
        )
        user_msg = (
            "Below is a summary by major sections (##). Compose the final deck.\n\n"
            f"SUMMARY:\n{content_preview}\n\n"
            "Return JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def _try_fix_json(self, json_str: str) -> Optional[str]:
        """Thử fix JSON bị lỗi format"""
        return _try_fix_json_util(json_str)
    

