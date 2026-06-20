"""TrÃ­ch xuáº¥t vÃ  cáº¥u trÃºc hÃ³a ná»™i dung sá»­ dá»¥ng LLM"""
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable, Awaitable
import re
# pyrefly: ignore [missing-import]
import httpx

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


class TaskCancelledError(Exception):
    """Raised when a running extraction task is cancelled by user."""

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
    "intro": ["giá»›i thiá»‡u", "introduction", "overview", "agenda", "má»¥c tiÃªu", "objective"],
    "data": ["sá»‘ liá»‡u", "thá»‘ng kÃª", "data", "statistics", "metric", "kpi", "tá»· lá»‡", "percent"],
    "process": ["quy trÃ¬nh", "process", "bÆ°á»›c", "step", "workflow", "pipeline", "giai Ä‘oáº¡n"],
    "benefit": ["lá»£i Ã­ch", "benefit", "advantage", "Æ°u Ä‘iá»ƒm", "hiá»‡u quáº£", "result", "outcome"],
    "problem": ["váº¥n Ä‘á»", "problem", "challenge", "thÃ¡ch thá»©c", "risk", "rá»§i ro", "háº¡n cháº¿"],
    "solution": ["giáº£i phÃ¡p", "solution", "cÃ¡ch", "approach", "strategy", "chiáº¿n lÆ°á»£c"],
    "conclusion": ["káº¿t luáº­n", "conclusion", "tÃ³m táº¯t", "summary", "next step", "káº¿ hoáº¡ch tiáº¿p"],
}

_DOMAIN_OBJECTS: Dict[str, str] = {
    "ui_product": "smartphone mockup and wireframe printouts",
    "startup_business": "pitch deck printouts and team around a laptop",
    "data_analytics": "analytics screens and printed performance report",
    "education_training": "lesson materials and notebook on a desk",
    "general": "documents and practical tools on desk",
}

_SDXL_NOISY_RE = re.compile(
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





def _scrub_sdxl_prompt(text: str) -> str:
    t = _SDXL_NOISY_RE.sub(" ", (text or "").strip())
    return " ".join(t.split())

# Tá»«/cá»¥m káº¿t thÆ°á»ng lÃ m bullet bá»‹ cá»¥t khi cáº¯t theo sá»‘ tá»« (Viá»‡t + Anh).
_BULLET_WEAK_TAIL_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "and",
        "or",
        "for",
        "to",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "that",
        "this",
        "cá»§a",
        "cho",
        "nhÆ°",
        "vá»›i",
        "tá»«",
        "theo",
        "mÃ ",
        "Ä‘á»ƒ",
        "vÃ ",
        "hoáº·c",
        "trong",
        "ngoÃ i",
        "bá»Ÿi",
        "cÃ¡c",
        "má»™t",
        "Ä‘áº·c",
        "biá»‡t",
        # Connector-words that always need continuation to form a complete idea.
        "nháº±m",  # "in order to" â€” always precedes a verb phrase
        "gá»“m",   # "includes" â€” always precedes its items
        "nhá»",   # "thanks to / through" â€” always precedes the means
    }
)

# Sino-Vietnamese bound morphemes that NEVER legitimately end a sentence alone.
# Each entry is the FIRST syllable of a common compound that must be followed
# by its complement (e.g. "trung" â†’ trung thÃ nh / trung tÃ¢m / trung thá»±c).
# Detected in _repair_incomplete_tail and _is_truncated_bullet.
_VN_BOUND_PREFIXES = frozenset({
    "trung",   # trung thÃ nh, trung tÃ¢m, trung thá»±c, trung bÃ¬nh, trung láº­p
    "báº¥t",     # báº¥t ká»³, báº¥t ngá», báº¥t há»£p (phÃ¡p)
    "vÃ´",      # vÃ´ cÃ¹ng, vÃ´ Ã­ch, vÃ´ lÃ½, vÃ´ hiá»‡u
    "siÃªu",    # siÃªu thá»‹, siÃªu tá»‘c, siÃªu Ã¢m
    "tiá»ƒu",    # tiá»ƒu thuyáº¿t, tiá»ƒu há»c, tiá»ƒu Ä‘Æ°á»ng
    "Ä‘áº¡i",     # Ä‘áº¡i há»c, Ä‘áº¡i diá»‡n, Ä‘áº¡i dÆ°Æ¡ng  (as sentence-final: extremely rare)
    "phi",     # phi lá»£i nhuáº­n, phi táº­p trung
    "há»£p",     # há»£p phÃ¡p, há»£p lá»‡, há»£p Ä‘á»“ng  (standalone: rare in slide context)
    "tÆ°Æ¡ng",   # tÆ°Æ¡ng tÃ¡c, tÆ°Æ¡ng lai, tÆ°Æ¡ng Ä‘Æ°Æ¡ng
    "thá»±c",    # thá»±c táº¿, thá»±c hÃ nh, thá»±c hiá»‡n  (standalone ending: odd in slides)
    "chÃ­nh",   # chÃ­nh sÃ¡ch, chÃ­nh xÃ¡c  (only when clearly the first morpheme)
})

# Comprehensive Vietnamese + English function words.
# These words carry no standalone meaning at sentence END: prepositions,
# conjunctions, determiners, auxiliaries. Used to detect dangling tails
# without enumerating specific phrase patterns.
_VN_FUNCTION_WORDS = frozenset({
    # Vietnamese prepositions (always need NP/VP after them)
    "cá»§a", "cho", "vá»›i", "tá»«", "theo", "Ä‘á»ƒ", "nháº±m", "gá»“m", "nhá»", "qua",
    "vá»", "Ä‘áº¿n", "thÃ nh", "trong", "ngoÃ i", "bá»Ÿi", "sau", "trÆ°á»›c", "giá»¯a",
    "Ä‘á»‘i", "táº¡i", "vÃ o", "ra", "lÃªn", "xuá»‘ng", "suá»‘t", "trÃªn", "dÆ°á»›i",
    "cáº¡nh", "ngang", "dá»c", "tá»›i", "cÃ¹ng",
    # Vietnamese conjunctions (connect to what follows)
    "vÃ ", "hoáº·c", "hay", "mÃ ", "nhÆ°ng", "song", "vá»«a",
    "khi", "náº¿u", "tuy", "dÃ¹", "há»…", "miá»…n", "vÃ¬",
    # Vietnamese determiners / quantifiers (require following noun)
    "cÃ¡c", "nhá»¯ng", "má»™t", "má»i", "tá»«ng", "nhiá»u", "Ã­t", "vÃ i", "máº¥y",
    # English equivalents
    "the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "at",
    "by", "with", "from", "as", "but", "nor", "yet", "so", "when", "if",
    "including", "through", "via", "based", "such", "than", "rather",
    "which", "that", "this", "these", "those",
})

# Belt-and-suspenders: specific multi-word dangling connectors for extra coverage.
_DANGLING_TAIL_RE = re.compile(
    r"[\s,]+"
    r"(?:"
    r"nháº±m(?:\s+\S+)?"
    r"|bao\s+gá»“m(?:\s+\S+)?"
    r"|dá»±a\s+trÃªn(?:\s+\S+)?"
    r"|dá»±a\s+vÃ o(?:\s+\S+)?"
    r"|thÃ´ng\s+qua(?:\s+\S+)?"
    r"|hÆ°á»›ng\s+tá»›i(?:\s+\S+)?"
    r"|nhá»\s+vÃ o(?:\s+\S+)?"
    r"|káº¿t\s+há»£p\s+vá»›i(?:\s+\S+)?"
    r"|in\s+order\s+to(?:\s+\S+)?"
    r"|based\s+on(?:\s+\S+)?"
    r"|including(?:\s+\S+)?"
    r"|such\s+as(?:\s+\S+)?"
    r")"
    r"\s*[.,]?\s*$",
    re.IGNORECASE | re.UNICODE,
)

# Fallback when khÃ´ng Ä‘oÃ¡n Ä‘Æ°á»£c ngÃ´n ngá»¯ tá»« vÄƒn báº£n.
_DECK_LANG_RULE = (
    "LANGUAGE: Match the source: English input â†’ English slides; Vietnamese â†’ Vietnamese. "
    "If mixed, use the dominant language. Do not translate the whole deck to another language.\n"
)

# KÃ½ tá»± cÃ³ dáº¥u tiáº¿ng Viá»‡t (heuristic Ä‘oÃ¡n input).
_VN_DIACRITIC_RE = re.compile(
    r"[Ã Ã¡áº£Ã£áº¡Äƒáº±áº¯áº³áºµáº·Ã¢áº§áº¥áº©áº«áº­Ã¨Ã©áº»áº½áº¹Ãªá»áº¿á»ƒá»…á»‡Ã¬Ã­á»‰Ä©á»‹Ã²Ã³á»Ãµá»Ã´á»“á»‘á»•á»—á»™Æ¡á»á»›á»Ÿá»¡á»£Ã¹Ãºá»§Å©á»¥Æ°á»«á»©á»­á»¯á»±á»³Ã½á»·á»¹á»µÄ‘Ä]"
)

class ContentExtractor:
    """Sá»­ dá»¥ng LLM Ä‘á»ƒ trÃ­ch xuáº¥t vÃ  cáº¥u trÃºc hÃ³a ná»™i dung thÃ nh slides"""
    
    def __init__(self, model_name: str = "Qwen3-8B"):
        """Khá»Ÿi táº¡o vá»›i model name trÃ¹ng `--served-model-name` trÃªn vLLM (OpenAI-compatible)."""
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
                "Warning: VLLM_API_BASE_URL khÃ´ng set â€” extract slide chá»‰ dÃ¹ng heuristic/fallback."
            )
        self._slide_lang_hint: str = "auto"
        # Tiáº¿n Ä‘á»™ extract (progress_cb): Ä‘áº¿m má»—i láº§n vLLM tráº£ JSON há»£p lá»‡.
        self._extract_progress: Optional[Dict[str, Any]] = None

    async def _progress_track_bump(self) -> None:
        """TÄƒng tiáº¿n Ä‘á»™ (done/total) sau má»—i láº§n gá»i LLM thÃ nh cÃ´ng + parse JSON OK."""
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
        """Æ¯á»›c lÆ°á»£ng ban Ä‘áº§u 18 bÆ°á»›c; total tá»± giÃ£n náº¿u pipeline gá»i nhiá»u LLM hÆ¡n."""
        self._extract_progress = {"cb": cb, "done": 0, "total": 18}

    async def _progress_track_finalize(self) -> None:
        """Chá»‘t done=total trong Ä‘oáº¡n [0,1] Ä‘á»ƒ callback map lÃªn 100% cá»§a phase extract."""
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
        """'vi' | 'en' | 'auto' â€” dÃ¹ng Ä‘á»ƒ báº¯t model khÃ´ng láº­t sang Anh khi input Viá»‡t."""
        t = (text or "").strip()[:12000]
        if len(t) < 24:
            return "auto"
        vn_hits = len(_VN_DIACRITIC_RE.findall(t))
        letters = sum(1 for c in t if c.isalpha())
        if letters < 15:
            return "auto"
        # CÃ³ dáº¥u tiáº¿ng Viá»‡t â†’ Æ°u tiÃªn output Viá»‡t (ká»ƒ cáº£ Ä‘oáº¡n ngáº¯n).
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
        """Nháº¯c á»Ÿ user message â€” bá»• sung cho system (trÃ¡nh model tráº£ Anh khi input Viá»‡t)."""
        h = getattr(self, "_slide_lang_hint", "auto") or "auto"
        if h == "vi":
            return "\n\nReminder: all titles and bullets must be in Vietnamese (tiáº¿ng Viá»‡t)."
        if h == "en":
            return "\n\nReminder: all titles and bullets must be in English."
        return ""

    def _llm_system_prefix(self) -> str:
        """Qwen3: táº¯t thinking náº¿u model há»— trá»£ (trÃ¡nh cháº­m/timeout khi cáº§n JSON ngáº¯n)."""
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
            "- Keep each bullet around 8â€“16 words (up to 18 when needed).\n"
            "- Avoid repetitive opening patterns across bullets.\n"
            "- Use varied slide intent across the deck: definition, impact, process, risk, solution, takeaway.\n"
            f"- With {max(1, int(n_slides))} slides target, ensure neighboring slides differ in angle.\n\n"
        )

    def _normalize_structured_content(self, structured_content: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize to canonical slide JSON format.

        Canonical format:
        {
          "title": str,
          "slides": [{"title": str, "bullets": [str], "notes": str}]
        }

        Backward compat: accepts legacy "content" as bullets.
        """
        if not isinstance(structured_content, dict):
            return {"title": "BÃ i thuyáº¿t trÃ¬nh", "slides": []}

        title = structured_content.get("title")
        if not isinstance(title, str) or not title.strip():
            title = "BÃ i thuyáº¿t trÃ¬nh"

        slides_in = structured_content.get("slides", [])
        if not isinstance(slides_in, list):
            slides_in = []

        def _clean_bullet(text: str, _max_words: int) -> str:
            """Strip artifacts, repair tails, hard-cut táº¡i _max_words Ä‘á»ƒ giá»¯ bullet sÃºc tÃ­ch."""
            t = (text or "").strip()
            # Remove accidental markdown/heading markers inside bullets
            t = re.sub(r"^\s*#{1,6}\s*", "", t)
            t = re.sub(r"^\s*[-*â€¢]\s*", "", t)
            t = re.sub(r"^\s*[â†’>]+\s*", "", t)
            # Remove leading numbering like "1.", "2.3", "1-"
            t = re.sub(r"^\s*\d+(\.\d+)*\s*[-:.)]\s*", "", t)
            # Strip trailing ... or â€¦ (model's copy-paste artifact)
            t = re.sub(r'[â€¦\.]{2,}\s*$', '', t).strip()
            t = t.rstrip(',(').strip()
            t = re.sub(r'\s+', ' ', t)
            # Length cap: respect sentence boundaries to avoid mid-sentence cuts.
            if _max_words and _max_words > 0:
                words = t.split()
                if len(words) > _max_words:
                    # Strategy A: sentence boundary BEFORE the limit (ideal).
                    candidate = " ".join(words[:_max_words])
                    cut = None
                    for sep in (".", "!", "?", ";"):
                        pos = candidate.rfind(sep)
                        if pos > len(candidate) // 2:
                            cut = candidate[: pos + 1].strip()
                            break

                    if cut is None:
                        # Strategy B: no boundary before limit â€” try to extend up to
                        # _max_words + 8 to find where the current sentence naturally ends.
                        # This avoids raw mid-sentence cuts entirely.
                        extended = " ".join(words[: _max_words + 8])
                        ext_cut = None
                        for sep in (".", "!", "?"):
                            pos = extended.find(sep, len(candidate))
                            if pos != -1:
                                ext_cut = extended[: pos + 1].strip()
                                break
                        if ext_cut:
                            cut = ext_cut
                        else:
                            # Strategy C: no sentence boundary at all â€” cut at last
                            # clause boundary (comma) to keep at least one full clause.
                            pos = candidate.rfind(",")
                            if pos > len(candidate) // 3:
                                cut = candidate[:pos].strip()
                            else:
                                cut = candidate.rstrip(",").strip()

                    t = cut
                    # Sau khi cáº¯t, náº¿u káº¿t quáº£ váº«n bá»‹ phÃ¡t hiá»‡n lÃ  cá»¥t bá»Ÿi
                    # _is_truncated_bullet, má»Ÿ rá»™ng thÃªm 1 tá»« má»—i láº§n cho Ä‘áº¿n khi
                    # bullet trÃ´ng hoÃ n chá»‰nh hoáº·c cháº¡m giá»›i háº¡n an toÃ n (+6 tá»«).
                    # CÃ¡ch nÃ y tá»•ng quÃ¡t: khÃ´ng cáº§n liá»‡t kÃª tá»«ng tiá»n tá»‘ cá»¥ thá»ƒ.
                    wcut = t.split()
                    MAX_EXTEND = 6
                    extended_count = 0
                    while (
                        extended_count < MAX_EXTEND
                        and len(wcut) < len(words)
                        and self._is_truncated_bullet(" ".join(wcut))
                    ):
                        wcut.append(words[len(wcut)])
                        extended_count += 1
                    if extended_count:
                        t = " ".join(wcut)
            t = self._repair_incomplete_tail(t)
            if t and not re.search(r'[\.!?]$', t):
                t += '.'
            return t

        slides_out: List[Dict[str, Any]] = []
        for slide in slides_in:
            if not isinstance(slide, dict):
                continue

            slide_title = slide.get("title")
            if not isinstance(slide_title, str) or not slide_title.strip():
                slide_title = "Ná»™i dung"

            bullets = slide.get("bullets")
            if bullets is None:
                bullets = slide.get("content")  # legacy

            if isinstance(bullets, str):
                bullets_list = [bullets.strip()] if bullets.strip() else []
            elif isinstance(bullets, list):
                bullets_list = [str(b).strip() for b in bullets if str(b).strip()]
            else:
                bullets_list = []

            def _norm_compare(s: str) -> str:
                # Normalize for approximate equality checks (avoid accepting bullet duplicated title).
                t = (s or "").strip().lower()
                t = re.sub(r"\s+", " ", t)
                t = t.strip(" \t\n\r\"'â€œâ€â€˜â€™.,;:!?-â€”â€“()[]{}")
                return t

            # Enforce spec: Ä‘á»§ bullet dÃ i Ä‘á»ƒ slide cÃ³ Ã½; bá» bullet cá»¥t ngay (khÃ´ng Ä‘Æ°a vÃ o deck).
            cleaned_bullets: List[str] = []
            for b in bullets_list:
                if not b.strip():
                    continue
                cb = _clean_bullet(b.strip(), MAX_WORDS_PER_BULLET)
                if not cb or self._is_truncated_bullet(cb):
                    continue
                cleaned_bullets.append(cb)
            cleaned_bullets = cleaned_bullets[:MAX_BULLETS_PER_SLIDE]

            def _bullet_ok(s: str) -> bool:
                """Loáº¡i bullet kiá»ƒu vÃ i chá»¯ / khÃ´ng Ä‘á»§ ngá»¯ cáº£nh (hay gáº·p khi model lÆ°á»i)."""
                s = (s or "").strip()
                w = len(s.split())
                c = len(s)
                # NgÆ°á»¡ng strict: náº¿u bullet quÃ¡ ngáº¯n thÃ¬ bá».
                # Fix theo yÃªu cáº§u: náº¿u c < 25 hoáº·c w < 4 => reject.
                # (Giáº£m nguy cÆ¡ "1 slide 1 dÃ²ng" do filter quÃ¡ gáº¯t.)
                if c < 25:
                    return False
                if w < 4:
                    return False
                return True

            strict_filtered = [b for b in cleaned_bullets if b and _bullet_ok(b)]

            # Recovery: trÃ¡nh tÃ¬nh tráº¡ng slide rÆ¡i xuá»‘ng 1 bullet sau khi lá»c strict.
            # Má»¥c tiÃªu lÃ  giá»¯ máº­t Ä‘á»™ chá»¯/Ã½ á»•n Ä‘á»‹nh; náº¿u strict khÃ´ng Ä‘á»§ 3 bullet,
            # hÃ£y ná»›i ngÆ°á»¡ng Ä‘á»ƒ giá»¯ láº¡i bullet cÃ³ Ã­t nháº¥t Ä‘á»™ dÃ i â€œtá»‘i thiá»ƒuâ€.
            if len(strict_filtered) >= 3:
                bullets_list = strict_filtered
            else:
                def _bullet_loose_ok(s: str) -> bool:
                    s = (s or "").strip()
                    w = len(s.split())
                    c = len(s)
                    # Ná»›i nháº¹ thÃªm Ä‘á»ƒ trÃ¡nh rÆ¡i vÃ o tráº¡ng thÃ¡i chá»‰ cÃ²n 1 bullet/slide.
                    return (c >= 20 and w >= 4) or (c >= 25 and w >= 3)

                recovered = [b for b in cleaned_bullets if b and _bullet_loose_ok(b)]
                bullets_list = recovered if len(recovered) >= 3 else cleaned_bullets

            # Remove bullets that duplicate the slide title (common failure mode).
            title_norm = _norm_compare(slide_title)
            dedup_by_text: List[str] = []
            seen_norm: set[str] = set()
            for b in bullets_list:
                b = (b or "").strip()
                if not b:
                    continue
                bn = _norm_compare(b)
                if not bn:
                    continue
                if title_norm and bn == title_norm:
                    continue
                # Also dedup bullets approximately to avoid repeated lines.
                if bn in seen_norm:
                    continue
                seen_norm.add(bn)
                dedup_by_text.append(b)
            bullets_list = dedup_by_text

            bullets_list = [b for b in bullets_list if b and b.strip()]
            if not bullets_list:
                continue

            notes = slide.get("notes", "")
            if not isinstance(notes, str):
                notes = str(notes)

            slides_out.append({
                "title": self._sanitize_title(slide_title.strip())[:120],
                "bullets": bullets_list,
                "notes": notes.strip()
            })

        slides_out = self._balance_deck(slides_out)
        # Global bullet dedup across the whole deck (reduce "repetition across slides").
        try:
            global_seen: set[str] = set()
            for s in slides_out:
                bs = s.get("bullets") or []
                if not isinstance(bs, list):
                    continue
                new_bs: List[str] = []
                for b in bs:
                    if not isinstance(b, str):
                        continue
                    bn = _norm_compare(b)
                    if not bn:
                        continue
                    if bn in global_seen:
                        continue
                    global_seen.add(bn)
                    new_bs.append(b)
                s["bullets"] = new_bs
        except Exception:
            # Never fail the request because of dedup heuristics.
            pass
        return {"title": self._sanitize_title(title.strip())[:120], "slides": slides_out}

    def _sanitize_title(self, text: str) -> str:
        """Remove non-Vietnamese/Latin characters (e.g., stray Chinese/Japanese chars)
        that may appear when source documents are multilingual.
        Keeps: Latin, Vietnamese diacritics (Unicode block 0080-024F + 1E00-1EFF),
        digits, common punctuation.
        """
        if not text:
            return text
        # Keep Latin + Latin Extended + Vietnamese supplement + digits + basic punct
        cleaned = re.sub(
            r'[^\x00-\u024F\u1E00-\u1EFF\u0020-\u007E\s]', '', text
        ).strip()
        # Collapse extra spaces
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if cleaned else text

    @staticmethod
    def _slide_content_tokens(slide: Dict[str, Any]) -> set:
        """Táº­p tá»« Ä‘Ã£ chuáº©n hoÃ¡ (title + bullets) Ä‘á»ƒ so sÃ¡nh má»©c Ä‘á»™ trÃ¹ng ná»™i dung."""
        parts = [slide.get("title") or ""]
        parts += [str(b) for b in (slide.get("bullets") or [])]
        text = " ".join(parts).lower()
        text = re.sub(r"[^\w\s]", " ", text)
        stopwords = {
            "lÃ ", "cá»§a", "vÃ ", "cÃ¡c", "trong", "vá»›i", "Ä‘á»ƒ", "cho", "má»™t", "cÃ³",
            "Ä‘Æ°á»£c", "khi", "tá»«", "khÃ´ng", "nÃ y", "Ä‘Ã³", "giÃºp", "theo", "hÆ¡n",
            "the", "a", "an", "of", "in", "to", "and", "for", "is", "are", "with",
        }
        return {w for w in text.split() if len(w) > 2 and w not in stopwords}

    def _balance_deck(self, slides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Post-process slide list: dedup by title + semantic similarity, drop empties, rescue sparse slides."""
        if not slides:
            return slides

        # 1. Dedup by exact title: keep first, merge bullets if duplicate found
        seen_titles: Dict[str, int] = {}
        deduped: List[Dict[str, Any]] = []
        for slide in slides:
            title_key = (slide["title"] or "").strip().lower()
            if title_key in seen_titles:
                existing = deduped[seen_titles[title_key]]
                extra = [b for b in slide["bullets"] if b not in existing["bullets"]]
                existing["bullets"] = (existing["bullets"] + extra)[:MAX_BULLETS_PER_SLIDE]
            else:
                seen_titles[title_key] = len(deduped)
                deduped.append(dict(slide))
        slides = deduped

        # 1b. Dedup slides cÃ³ ná»™i dung quÃ¡ trÃ¹ng (token overlap > 65%) â€”
        #     Ã¡p dá»¥ng khi deck >= 6 slide, gá»™p bullet vÃ o slide trÆ°á»›c thay vÃ¬ xoÃ¡ háº³n.
        if len(slides) >= 6:
            kept: List[Dict[str, Any]] = []
            for slide in slides:
                tok_new = self._slide_content_tokens(slide)
                merged_into = None
                for existing in kept:
                    tok_ex = self._slide_content_tokens(existing)
                    union = tok_ex | tok_new
                    if not union:
                        continue
                    overlap = len(tok_ex & tok_new) / len(union)
                    if overlap >= 0.65:
                        merged_into = existing
                        break
                if merged_into is not None:
                    # Gá»™p bullet má»›i vÃ o slide Ä‘Ã£ cÃ³ (bá» trÃ¹ng)
                    extra = [
                        b for b in (slide.get("bullets") or [])
                        if b not in (merged_into.get("bullets") or [])
                    ]
                    merged_into["bullets"] = (
                        (merged_into.get("bullets") or []) + extra
                    )[:MAX_BULLETS_PER_SLIDE]
                else:
                    kept.append(dict(slide))
            slides = kept

        # 2. Drop slides with 0 bullets
        slides = [s for s in slides if s["bullets"]]

        # 3. Rescue thin slides: Ä‘áº£m báº£o má»—i slide cÃ³ Ã­t nháº¥t 3 bullets (Ä‘Ãºng spec),
        #    báº±ng cÃ¡ch "cho mÆ°á»£n" bullet tá»« slide lÃ¢n cáº­n náº¿u chÃºng cÃ³ dÆ° > 3.
        min_required = 3
        changed = True
        while changed:
            changed = False
            for i in range(len(slides)):
                bs_i = slides[i].get("bullets") or []
                if not isinstance(bs_i, list):
                    continue
                if len(bs_i) >= min_required:
                    continue
                # Take from previous if previous has dÆ°
                if i - 1 >= 0:
                    bs_prev = slides[i - 1].get("bullets") or []
                    if isinstance(bs_prev, list) and len(bs_prev) > min_required:
                        donated = bs_prev.pop()
                        slides[i]["bullets"].insert(0, donated)
                        changed = True
                        continue
                # Take from next if previous khÃ´ng Ä‘á»§
                if i + 1 < len(slides):
                    bs_next = slides[i + 1].get("bullets") or []
                    if isinstance(bs_next, list) and len(bs_next) > min_required:
                        donated = bs_next.pop(0)
                        slides[i]["bullets"].append(donated)
                        changed = True

        # 4. Merge pairs of consecutive 1-bullet slides into one
        merged: List[Dict[str, Any]] = []
        i = 0
        while i < len(slides):
            if (
                i + 1 < len(slides)
                and len(slides[i]["bullets"]) == 1
                and len(slides[i + 1]["bullets"]) == 1
            ):
                merged.append({
                    "title": slides[i]["title"],
                    "bullets": (slides[i]["bullets"] + slides[i + 1]["bullets"])[:MAX_BULLETS_PER_SLIDE],
                    "notes": slides[i]["notes"] or slides[i + 1]["notes"],
                })
                i += 2
            else:
                merged.append(slides[i])
                i += 1

        # 5. Gá»™p slide chá»‰ cÃ²n 1 bullet vÃ o slide trÆ°á»›c náº¿u cÃ²n chá»— (trÃ¡nh "má»™t dÃ²ng má»™t slide")
        changed = True
        while changed:
            changed = False
            out_m: List[Dict[str, Any]] = []
            for s in merged:
                bs = s.get("bullets") or []
                if (
                    out_m
                    and len(bs) == 1
                    and len(out_m[-1].get("bullets") or []) < MAX_BULLETS_PER_SLIDE
                ):
                    prev = out_m[-1]
                    prev["bullets"] = (list(prev.get("bullets") or []) + [bs[0]])[
                        :MAX_BULLETS_PER_SLIDE
                    ]
                    changed = True
                else:
                    out_m.append(dict(s))
            merged = out_m

        # FINAL SPEC: sau khi merge, cháº¡y láº¡i pass Ä‘áº£m báº£o má»—i slide cÃ³ >= 3 bullets.
        min_required = 3
        changed = True
        while changed:
            changed = False
            for i in range(len(merged)):
                bs_i = merged[i].get("bullets") or []
                if not isinstance(bs_i, list):
                    continue
                if len(bs_i) >= min_required:
                    continue
                if i - 1 >= 0:
                    bs_prev = merged[i - 1].get("bullets") or []
                    if isinstance(bs_prev, list) and len(bs_prev) > min_required:
                        donated = bs_prev.pop()
                        merged[i]["bullets"].insert(0, donated)
                        changed = True
                        continue
                if i + 1 < len(merged):
                    bs_next = merged[i + 1].get("bullets") or []
                    if isinstance(bs_next, list) and len(bs_next) > min_required:
                        donated = bs_next.pop(0)
                        merged[i]["bullets"].append(donated)
                        changed = True

        return merged

    def _clean_result_text(self, text: str) -> str:
        """Strip thinking blocks and markdown fences before JSON parsing."""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = text.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
            if m:
                text = m.group(1).strip()
        return text

    def _has_balanced_delimiters(self, text: str) -> bool:
        """Check simple delimiter balance to catch half-open phrases."""
        if not text:
            return True
        stack: List[str] = []
        pairs = {")": "(", "]": "[", "}": "{"}
        for ch in text:
            if ch in "([{":
                stack.append(ch)
            elif ch in ")]}":
                if not stack or stack[-1] != pairs[ch]:
                    return False
                stack.pop()
        if stack:
            return False

        # Quote balance (ignore apostrophes inside words).
        clean = re.sub(r"(?<=\w)'(?=\w)", "", text)
        clean = re.sub(r'(?<=\w)"(?=\w)', "", clean)
        if clean.count('"') % 2 != 0:
            return False
        if clean.count("'") % 2 != 0:
            return False
        return True

    @staticmethod
    def _count_content_words(phrase: str) -> int:
        """Count words NOT in the function-word set (carry real semantic meaning)."""
        return sum(
            1 for w in phrase.split()
            if re.sub(r"[^\w]+", "", w).lower() not in _VN_FUNCTION_WORDS
        )

    def _repair_incomplete_tail(self, text: str) -> str:
        """Trim dangling tail clauses using content-word density + specific patterns.

        General principle: after the last , or ; the remaining tail must contain
        â‰¥ 3 content words (non-function-words) to be considered meaningful.
        This catches ANY dangling pattern regardless of specific word choice.
        """
        t = re.sub(r"\s+", " ", (text or "").strip())
        if not t:
            return t

        # Remove hanging delimiters first.
        t = re.sub(r"[,;:\-â€“â€”/]\s*$", "", t).strip()

        # â”€â”€ General content-word check (language-agnostic) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # If the last clause (after , or ;) has < 3 content words it is dangling.
        # Examples that get trimmed:
        #   "... ká»¹ thuáº­t, thiáº¿t bá»‹ di Ä‘á»™ng vÃ ."    â†’ tail has 2 content words â†’ drop
        #   "... tá»‘i Æ°u hÃ³a thÃ´ng qua cÃ¡c cÃ´ng cá»¥." â†’ tail has 3+ content words â†’ keep
        m = re.search(r"([,;])\s*(.+)$", t)
        if m:
            tail_raw = m.group(2).strip().rstrip(".!?")
            content_count = self._count_content_words(tail_raw)
            tail_word_count = len(tail_raw.split())
            if content_count < 3 and tail_word_count <= 7:
                head = t[: m.start()].strip()
                if len(head.split()) >= 4:
                    t = head

        # â”€â”€ Belt-and-suspenders: specific multi-word dangling connectors â”€â”€â”€â”€â”€â”€â”€â”€
        bare = t.rstrip(".!?").rstrip()
        m2 = _DANGLING_TAIL_RE.search(bare)
        if m2:
            head = bare[: m2.start()].strip()
            if len(head.split()) >= 4:
                t = head

        # â”€â”€ Sino-Vietnamese bound morpheme ending â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # e.g. "...xÃ¢y dá»±ng cá»™ng Ä‘á»“ng trung." â†’ LLM wrote "trung" but meant
        # "trung thÃ nh"; the morpheme cannot stand alone â†’ drop it.
        words = t.rstrip(".!?").split()
        if words:
            last = re.sub(r"[^\w]+", "", words[-1]).lower()
            if last in _VN_BOUND_PREFIXES and len(words) >= 4:
                t = " ".join(words[:-1]).strip()
                words = t.rstrip(".!?").split()  # refresh for next check

        # â”€â”€ Single function-word ending â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if words:
            last = re.sub(r"[^\w]+", "", words[-1]).lower()
            if last in _VN_FUNCTION_WORDS and len(words) >= 5:
                t = " ".join(words[:-1]).strip()

        t = t.strip()
        if t and not re.search(r"[.!?]$", t):
            t += "."
        return t

    def _is_truncated_bullet(self, text: str) -> bool:
        """Score-based truncated detection, mostly language-agnostic."""
        raw = (text or "").strip()
        if not raw:
            return False
        t = re.sub(r"\s+", " ", raw)
        score = 0

        # Strong signals.
        if re.search(r"(?:\.\.\.|â€¦)\s*$", t):
            score += 3
        if re.search(r"[,;:\-â€“â€”/]\s*$", t):
            score += 2
        if len(t) >= 32 and not re.search(r"[\.!?]$", t):
            score += 2
        if not self._has_balanced_delimiters(t):
            score += 2

        # General: last clause (after , or ;) has too few content words â†’ dangling.
        _mc = re.search(r"[,;]\s*(.+)$", t)
        if _mc:
            _tail = _mc.group(1).strip().rstrip(".!?")
            _cc = self._count_content_words(_tail)
            _tw = len(_tail.split())
            if _cc < 3 and _tw <= 7:
                score += 3

        # Specific multi-word dangling connector at end (belt-and-suspenders).
        if _DANGLING_TAIL_RE.search(t.rstrip(".!?")):
            score += 3

        # Sino-Vietnamese bound morpheme at sentence end (never valid standalone).
        _w = t.rstrip(".!?").split()
        if _w:
            _last = re.sub(r"[^\w]+", "", _w[-1]).lower()
            if _last in _VN_BOUND_PREFIXES and len(_w) >= 4:
                score += 4
            elif _last in _VN_FUNCTION_WORDS and len(_w) >= 4:
                score += 3

        # Weak signal: tail clause after separator is too short to form meaning.
        m = re.search(r"[,;:]\s*([^,;:]+)$", t)
        if m:
            tail = m.group(1).strip().rstrip(".!?")
            tail_words = tail.split()
            if len(t) >= 18 and (len(tail_words) <= 3 or len(tail) <= 14):
                score += 2

        # Very short bullets tend to be labels, but keep room for genuine short facts.
        words = t.rstrip(".!?").split()
        if len(words) <= 2 and len(t) >= 12:
            score += 1

        return score >= 2

    def _deck_has_truncated_bullets(self, structured: Dict[str, Any]) -> bool:
        slides = structured.get("slides") or []
        if not isinstance(slides, list):
            return False
        for s in slides:
            if not isinstance(s, dict):
                continue
            for b in s.get("bullets") or []:
                if isinstance(b, str) and self._is_truncated_bullet(b):
                    return True
        return False

    # -----------------------------
    # FINAL SPEC: Expand + Grouping
    # -----------------------------

    def _build_expand_messages(self, content: str, enable_deep: bool) -> List[Dict[str, str]]:
        """Expansion step: MUST expand (not summarize). Output: {"expanded_text": "..."}"""
        normalized = self._normalize_for_llm(content or "")
        preview = normalized[:7000] if len(normalized) > 7000 else normalized
        deep_rule = (
            "- Target slide count is high: expand deeplyâ€”split into sub-ideas, add why/how, impact, and examples.\n"
            if enable_deep
            else "- Expand enough: add why/how, impact, and examples where appropriate.\n"
        )
        system_msg = self._llm_system_prefix() + (
            "You are an expert educator.\n\n"
            "TASK: EXPAND the source material into a richer, more detailed version.\n\n"
            "REQUIREMENTS:\n"
            "- Explain and clarify concepts.\n"
            "- Add reasoning, consequences, and significance.\n"
            "- Add examples when possible.\n"
            "- Break large ideas into smaller points suitable for slides.\n\n"
            "CRITICAL:\n"
            "- DO NOT summarize. Do not compress.\n"
            "- DO NOT shorten. The expanded_text must be LONGER and richer than the input.\n"
            "- Expand every idea into deeper explanationâ€”not a light touch.\n"
            "- If an idea is short, elaborate with causes, effects, mechanisms, and examples.\n"
            "- The expanded_text MUST be significantly longer than the input (substance, not padding).\n"
            + deep_rule
            + self._output_language_instruction()
            + "Return ONLY valid JSON. Schema:\n"
            "{\"expanded_text\": \"...\"}\n"
        )
        user_msg = (
            "Expand this source text:\n\n"
            f"{preview}\n\n"
            "Return JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def _expand_content_final(self, content: str, target_slides: int) -> str:
        enable_deep = bool(target_slides and int(target_slides) >= 15)
        msgs = self._build_expand_messages(content, enable_deep=enable_deep)
        try:
            data = await self._request_json_dict(
                msgs,
                target_slides=max(8, min(int(target_slides or 12), 18)),
                fast_mode=False,
                compose_mode=False,
                structured_output="expanded_text",
            )
        except Exception as e:
            print(f"Expand step JSON failed; fallback to merged content. Error: {e}")
            return content or ""
        expanded = (data.get("expanded_text") if isinstance(data, dict) else "") or ""
        expanded = str(expanded).strip()
        return expanded if expanded else (content or "")

    def _build_group_messages(self, expanded_text: str) -> List[Dict[str, str]]:
        """Grouping step: Output JSON {"sections":[{"title":"...","content":"..."}]}"""
        normalized = self._normalize_for_llm(expanded_text or "")
        preview = normalized[:7000] if len(normalized) > 7000 else normalized
        system_msg = self._llm_system_prefix() + (
            "You are a content architect.\n\n"
            "TASK: Group the material into thematic sections.\n\n"
            "RULES:\n"
            "- Merge related ideas into the same section.\n"
            "- Each section is one major topic.\n"
            "- Do not split one topic across many sections.\n"
            "- No duplicated ideas across sections.\n\n"
            + self._output_language_instruction()
            + "Return ONLY JSON. Schema:\n"
            "{\"sections\": [{\"title\": \"...\", \"content\": \"...\"}]}\n"
        )
        user_msg = (
            "Group this content into sections:\n\n"
            f"{preview}\n\n"
            "Return JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def _group_content_final(self, expanded_text: str) -> List[Dict[str, str]]:
        msgs = self._build_group_messages(expanded_text)
        data = await self._request_json_dict(
            msgs,
            target_slides=10,
            fast_mode=True,
            compose_mode=False,
            structured_output="sections",
        )
        secs = data.get("sections") if isinstance(data, dict) else None
        if not isinstance(secs, list):
            return []
        out: List[Dict[str, str]] = []
        for s in secs:
            if not isinstance(s, dict):
                continue
            t = str(s.get("title") or "").strip()
            c = str(s.get("content") or "").strip()
            if not t or not c:
                continue
            out.append({"title": t[:80], "content": c})
        return out

    # -----------------------------
    # FINAL SPEC: Slide generation
    # -----------------------------

    def _build_generate_section_messages(self, section: Dict[str, str], target_slides: int) -> List[Dict[str, str]]:
        title = str(section.get("title") or "Ná»™i dung").strip()
        content = str(section.get("content") or "").strip()
        normalized = self._normalize_for_llm(content)
        preview = normalized[:7000] if len(normalized) > 7000 else normalized
        n_slides = int(target_slides)
        high_slide_block = (
            "7) HIGH SLIDE COUNT:\n"
            "- Expand ideas deeper; split into sub-points where it helps clarity.\n"
            "- Add explanations and examples so every slide stays substantive.\n\n"
        ) if n_slides >= 6 else ""
        system_msg = (
            self._llm_system_prefix()
            + "You are an expert presentation designer.\n\n"
            + f"TASK: Generate EXACTLY {n_slides} slides from the section content.\n\n"
            + self._presentation_style_block(n_slides)
            + "RULES:\n"
            "1) CONTENT EXPANSION:\n"
            "- Go beyond the source: add explanation, reasoning, and supporting detailâ€”not paraphrase only.\n"
            "- Do not summarize away substance.\n\n"
            "2) SLIDE DENSITY:\n"
            "- Each slide MUST have 3â€“5 bullets.\n"
            "- Never fewer than 3 bullets.\n"
            "- If the section is thin, invent substantive expansion (still faithful to the topic).\n\n"
            "3) BULLET QUALITY:\n"
            "- Each bullet is a complete sentence: subjectâ€“predicate; do not stop mid-phrase (no missing object after a preposition).\n"
            "- No fake endings like \"...\", \"vÃ .\", \"bao gá»“m.\" before the idea is finished.\n"
            "- Prefer short presentation bullets; split long ideas into 2 bullets.\n"
            "- If an idea needs more words, split into two bulletsâ€”never one endless line.\n"
            "- Each bullet still needs context + why/how or significance, but stay compact.\n\n"
            "CRITICAL:\n"
            "- Explain the idea fullyâ€”not a labelâ€”but do not inflate length; density over word count.\n"
            "- Add reasoning and implications in tight wording.\n"
            "- Avoid generic or shallow statements.\n\n"
            "ANTI-TRUNCATION:\n"
            "- NEVER end a sentence unfinished.\n"
            "- NEVER output incomplete phrases.\n"
            "- If you are near the token limit: end the current bullet with a period, then output fewer bullets per slide if needed, and ALWAYS close valid JSON.\n\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + "\n"
            "4) ANTI-LAZY:\n"
            "- No keyword-only bullets; write full explanatory sentences.\n\n"
            "5) STRUCTURE:\n"
            "- Group related points on the same slide.\n"
            "- No \"(continued)\" / \"(tiáº¿p)\" slides.\n\n"
            "6) NO REPETITION:\n"
            "- Different slides must add different information.\n\n"
            + high_slide_block
            + self._output_language_instruction()
            + "OUTPUT: JSON only. Schema:\n"
            "{\"title\":\"...\",\"slides\":[{\"title\":\"...\",\"bullets\":[\"...\",\"...\",\"...\"],\"notes\":\"\"}]}\n"
        )
        user_msg = (
            f"SECTION TOPIC: {title}\n\n"
            f"SECTION SOURCE TEXT:\n{preview}\n\n"
            "Return JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def _generate_slides_for_sections(self, sections: List[Dict[str, str]], target_slides: int) -> Dict[str, Any]:
        """Generate slides by section, then merge."""
        if not sections:
            # Fallback: treat whole content as one section.
            sections = [{"title": "Ná»™i dung", "content": ""}]
        target_slides = max(4, int(target_slides or 10))
        # Allocate slide count per section proportionally by content length.
        lengths = [max(50, len(s.get("content") or "")) for s in sections]
        total = sum(lengths)
        alloc = [max(1, round(target_slides * l / total)) for l in lengths]
        # Adjust to exact total.
        diff = target_slides - sum(alloc)
        idx = 0
        while diff != 0 and alloc:
            i = idx % len(alloc)
            if diff > 0:
                alloc[i] += 1
                diff -= 1
            else:
                if alloc[i] > 1:
                    alloc[i] -= 1
                    diff += 1
            idx += 1

        deck_title = "BÃ i thuyáº¿t trÃ¬nh"
        slides_all: List[Dict[str, Any]] = []
        # Song song hÃ³a theo section (giá»›i háº¡n 3 request cÃ¹ng lÃºc Ä‘á»ƒ trÃ¡nh quÃ¡ táº£i vLLM 1 GPU).
        sem = asyncio.Semaphore(3)

        async def _one_section(sec: Dict[str, str], n: int) -> Optional[Dict[str, Any]]:
            async with sem:
                try:
                    msgs = self._build_generate_section_messages(sec, target_slides=int(n))
                    part = await self._request_json_dict(
                        msgs,
                        target_slides=int(n),
                        fast_mode=False,
                        compose_mode=False,
                        structured_output="slide_deck",
                    )
                    if isinstance(part, dict):
                        return self._normalize_structured_content(part)
                except Exception as e:
                    print(
                        f"Section slide generation failed ({sec.get('title')!r}): {e}"
                    )
                return None

        results = await asyncio.gather(
            *[_one_section(sec, int(n)) for sec, n in zip(sections, alloc)]
        )
        for part_norm in results:
            if part_norm and isinstance(part_norm.get("slides"), list):
                if deck_title == "BÃ i thuyáº¿t trÃ¬nh" and part_norm.get("title"):
                    deck_title = str(part_norm.get("title") or deck_title)
                slides_all.extend(part_norm.get("slides") or [])

        return self._normalize_structured_content({"title": deck_title, "slides": slides_all})

    # -----------------------------
    # FINAL SPEC: Refine (final compose)
    # -----------------------------

    def _build_refine_messages(self, structured: Dict[str, Any]) -> List[Dict[str, str]]:
        payload = json.dumps(structured, ensure_ascii=False)
        system_msg = (
            self._llm_system_prefix()
            + "You are an expert slide editor.\n\n"
            + "TASK: Improve the existing slide deck JSON.\n\n"
            + self._presentation_style_block(len(structured.get("slides") or []))
            + "REQUIREMENTS:\n"
            "- For each bullet: if a reader cannot answer what happens next, what the concrete referent is, or what the conclusion isâ€”rewrite until complete. Do not patch with fixed phrases; fix any domain.\n"
            "- Fix truncated or incomplete sentences (even if they end with a period): no missing complements after prepositions; no fake endings like \"...\", \"vÃ .\", \"bao gá»“m.\".\n"
            "- Vietnamese: never end a bullet with only a function word + period (invalid: \"cá»§a.\", \"cho.\", \"vá»›i.\", \"tá»«.\", \"nhÆ°.\", \"mÃ .\") or a comma then one short stray word + period; complete the thought.\n"
            "- Keep bullets concise and scannable for presentation; avoid paragraph-like bullets.\n"
            "- Valid JSON and fully closed sentences matter more than making every bullet longerâ€”do not \"expand\" length at the expense of truncation or broken JSON.\n"
            "- Each bullet: context + explanation + impact or significanceâ€”in compact wording.\n"
            "- Rewrite shallow bullets into clear complete statements; fix vague bullets with concrete detail without rambling.\n"
            "- Ensure each bullet carries meaningful informationâ€”not filler or labels.\n"
            "- Fix thin or broken bullets; do not only fix spelling.\n"
            "- Merge slides with fewer than 2 bullets into the previous slide.\n"
            "- Each slide should have 3â€“5 bullets.\n"
            "- Remove duplication.\n"
            "- No \"(continued)\" / \"(tiáº¿p)\" slides.\n\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + "\n"
            + self._output_language_instruction()
            + "Return ONLY JSON. Schema:\n"
            "{\"title\":\"...\",\"slides\":[{\"title\":\"...\",\"bullets\":[\"...\"],\"notes\":\"\"}]}\n"
        )
        user_msg = (
            "Current deck (JSON). Refine per instructions:\n\n"
            f"{payload}\n\n"
            "Return JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def _refine_slides_final(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        msgs = self._build_refine_messages(structured)
        refined = await self._request_json_dict(
            msgs,
            target_slides=max(8, min(len(structured.get("slides") or []) or 10, 20)),
            fast_mode=False,
            compose_mode=True,
            structured_output="slide_deck",
        )
        return self._normalize_structured_content(refined if isinstance(refined, dict) else structured)

    def _build_repair_bullet_messages(
        self,
        deck_title: str,
        slide_title: str,
        bullet: str,
    ) -> List[Dict[str, str]]:
        """Targeted repair for one suspicious bullet."""
        system_msg = self._llm_system_prefix() + (
            "You repair ONE slide bullet sentence.\n\n"
            "RULES:\n"
            "- Keep original meaning; do not add unrelated facts.\n"
            "- Return one complete sentence only (no fragments, no ellipsis).\n"
            "- Same language as input.\n"
            "- Keep concise, ideally around 10-18 words, hard max 24 words.\n"
            "- No markdown or extra commentary.\n"
            "Return ONLY JSON with schema: {\"bullet\": \"...\"}\n"
        )
        user_msg = (
            f"Deck title: {deck_title}\n"
            f"Slide title: {slide_title}\n"
            f"Broken bullet: {bullet}\n\n"
            "Rewrite this bullet so it is complete and meaningful."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def _repair_truncated_bullets_targeted(
        self,
        structured: Dict[str, Any],
        max_repairs: int = 18,
    ) -> Dict[str, Any]:
        """Repair only bullets that still look truncated after refine."""
        if not isinstance(structured, dict):
            return structured
        slides = structured.get("slides") or []
        if not isinstance(slides, list) or not slides:
            return structured

        deck_title = str(structured.get("title") or "BÃ i thuyáº¿t trÃ¬nh")
        repaired = 0
        for slide in slides:
            if repaired >= max_repairs:
                break
            if not isinstance(slide, dict):
                continue
            slide_title = str(slide.get("title") or "Ná»™i dung")
            bullets = slide.get("bullets") or []
            if not isinstance(bullets, list):
                continue

            out_bullets: List[str] = []
            for b in bullets:
                bt = str(b or "").strip()
                if not bt:
                    continue
                # Always run tail repair first (cheap/local).
                bt = self._repair_incomplete_tail(bt)
                if self._is_truncated_bullet(bt) and repaired < max_repairs:
                    try:
                        msgs = self._build_repair_bullet_messages(deck_title, slide_title, bt)
                        fixed = await self._request_json_dict(
                            msgs,
                            target_slides=1,
                            fast_mode=False,
                            compose_mode=False,
                            structured_output="bullet",
                        )
                        cand = str((fixed or {}).get("bullet") or "").strip()
                        if cand:
                            cand = self._repair_incomplete_tail(cand)
                        # Accept repaired bullet if it resolves truncation, else keep local repaired text.
                        if cand and not self._is_truncated_bullet(cand):
                            bt = cand
                        repaired += 1
                    except Exception as e:
                        print(f"Targeted bullet repair failed: {e}")
                out_bullets.append(bt)

            slide["bullets"] = out_bullets[:MAX_BULLETS_PER_SLIDE]
        return structured

    def _build_polish_slide_messages(
        self,
        deck_title: str,
        slide_title: str,
        bullets: List[str],
    ) -> List[Dict[str, str]]:
        """Polish all bullets in one slide for completeness/clarity."""
        bullets_payload = json.dumps(bullets, ensure_ascii=False)
        system_msg = (
            self._llm_system_prefix()
            + "You are a strict slide-writing editor.\n\n"
            + "TASK: Rewrite bullets to be complete and meaningful.\n\n"
            + self._presentation_style_block(max(1, len(bullets)))
            + "RULES:\n"
            "- Keep original meaning and facts. Do not invent new facts.\n"
            "- Every bullet must be a complete sentence (no dangling tails).\n"
            "- Fix vague/truncated endings (e.g., ending after conjunction/preposition).\n"
            "- Keep concise: roughly 10-18 words, hard max 24 words each bullet.\n"
            "- Keep exactly the same number of bullets as input.\n"
            "- Same language as input.\n"
            "- Return ONLY JSON with schema: {\"bullets\": [\"...\", \"...\"]}\n"
        )
        user_msg = (
            f"Deck title: {deck_title}\n"
            f"Slide title: {slide_title}\n"
            f"Input bullets JSON: {bullets_payload}\n\n"
            "Rewrite all bullets following the rules."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def _polish_slide_bullets_quality(
        self,
        structured: Dict[str, Any],
        max_slides: int = 24,
    ) -> Dict[str, Any]:
        """Quality-first pass: rewrite bullets slide-by-slide to reduce semantic truncation."""
        if not isinstance(structured, dict):
            return structured
        slides = structured.get("slides") or []
        if not isinstance(slides, list) or not slides:
            return structured

        deck_title = str(structured.get("title") or "BÃ i thuyáº¿t trÃ¬nh")
        processed = 0
        for slide in slides:
            if processed >= max_slides:
                break
            if not isinstance(slide, dict):
                continue
            slide_title = str(slide.get("title") or "Ná»™i dung")
            bullets = slide.get("bullets") or []
            if not isinstance(bullets, list) or not bullets:
                continue
            in_bullets = [str(b or "").strip() for b in bullets if str(b or "").strip()]
            if not in_bullets:
                continue

            try:
                msgs = self._build_polish_slide_messages(deck_title, slide_title, in_bullets)
                data = await self._request_json_dict(
                    msgs,
                    target_slides=1,
                    fast_mode=False,
                    compose_mode=False,
                    structured_output="bullets",
                )
                out = data.get("bullets") if isinstance(data, dict) else None
                if isinstance(out, list) and out:
                    polished = [self._repair_incomplete_tail(str(x or "").strip()) for x in out if str(x or "").strip()]
                    # Keep exact count if model over/under-generates.
                    if len(polished) < len(in_bullets):
                        polished.extend(in_bullets[len(polished):])
                    polished = polished[: len(in_bullets)]
                    slide["bullets"] = polished[:MAX_BULLETS_PER_SLIDE]
            except Exception as e:
                print(f"Slide bullet polish failed ({slide_title!r}): {e}")

            processed += 1
        return structured

    def _bullet_needs_final_fix(self, text: str) -> bool:
        """Conservative final gate: fix only bullets that are very likely broken."""
        t = re.sub(r"\s+", " ", (text or "").strip())
        if not t:
            return False
        if self._is_truncated_bullet(t):
            return True
        if re.search(r"[,;:\-â€“â€”/]\s*$", t):
            return True
        if not re.search(r"[.!?]$", t):
            return True
        # Too short and ends abruptly often indicates low-information or broken phrase.
        words = t.rstrip(".!?").split()
        if len(words) < 4 and len(t) >= 18:
            return True
        return False

    async def _run_final_quality_gate(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        """Last-pass quality gate: targeted bullet fixes, accept only if improved."""
        if not isinstance(structured, dict):
            return structured
        slides = structured.get("slides") or []
        if not isinstance(slides, list) or not slides:
            return structured

        max_fixes = max(0, int(LLM_FINAL_QUALITY_GATE_MAX_FIXES))
        if max_fixes <= 0:
            return structured

        deck_title = str(structured.get("title") or "BÃ i thuyáº¿t trÃ¬nh")
        fixed = 0
        for slide in slides:
            if fixed >= max_fixes:
                break
            if not isinstance(slide, dict):
                continue
            slide_title = str(slide.get("title") or "Ná»™i dung")
            bullets = slide.get("bullets") or []
            if not isinstance(bullets, list):
                continue

            new_bullets: List[str] = []
            for b in bullets:
                bt = str(b or "").strip()
                if not bt:
                    continue
                if fixed < max_fixes and self._bullet_needs_final_fix(bt):
                    original = bt
                    try:
                        msgs = self._build_repair_bullet_messages(deck_title, slide_title, original)
                        data = await self._request_json_dict(
                            msgs,
                            target_slides=1,
                            fast_mode=False,
                            compose_mode=False,
                            structured_output="bullet",
                        )
                        cand = str((data or {}).get("bullet") or "").strip()
                        if cand:
                            cand = self._repair_incomplete_tail(cand)
                        # Accept only if candidate passes stricter final gate.
                        if cand and not self._bullet_needs_final_fix(cand):
                            bt = cand
                            fixed += 1
                    except Exception as e:
                        print(f"Final quality gate repair failed: {e}")
                        bt = self._repair_incomplete_tail(original)
                new_bullets.append(bt)

            slide["bullets"] = new_bullets[:MAX_BULLETS_PER_SLIDE]
        return structured

    def _strip_continued_suffix(self, title: str) -> str:
        t = (title or "").strip()
        if not t:
            return t
        t = re.sub(r"\s*\((?:tiáº¿p|tiep|continued)\)\s*$", "", t, flags=re.IGNORECASE).strip()
        return t or (title or "").strip()

    def _build_densify_slide_messages(
        self,
        deck_title: str,
        slide_title: str,
        bullets: List[str],
        target_count: int,
    ) -> List[Dict[str, str]]:
        bullets_payload = json.dumps(bullets, ensure_ascii=False)
        system_msg = self._llm_system_prefix() + (
            "You densify one slide's bullets for presentation quality.\n\n"
            "RULES:\n"
            "- Keep the same topic and facts; do not invent unrelated claims.\n"
            f"- Return EXACTLY {target_count} bullets.\n"
            "- Each bullet must be a complete sentence.\n"
            "- Use concise presentation style; avoid paragraph-like bullets.\n"
            "- Prefer keyword-first phrasing when natural.\n"
            "- Same language as input.\n"
            "Return ONLY JSON with schema: {\"bullets\": [\"...\", \"...\"]}\n"
        )
        user_msg = (
            f"Deck title: {deck_title}\n"
            f"Slide title: {slide_title}\n"
            f"Current bullets JSON: {bullets_payload}\n\n"
            "Densify this slide to reach the required bullet count."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def _run_final_density_gate(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure each slide has at least configured bullet density."""
        if not isinstance(structured, dict):
            return structured
        slides = structured.get("slides") or []
        if not isinstance(slides, list) or not slides:
            return structured

        min_b = max(2, int(LLM_FINAL_DENSITY_MIN_BULLETS))
        max_rw = max(0, int(LLM_FINAL_DENSITY_MAX_REWRITES))
        rewrites = 0
        deck_title = str(structured.get("title") or "BÃ i thuyáº¿t trÃ¬nh")

        # 1) Clean "(tiáº¿p)" suffix from titles first.
        for s in slides:
            if isinstance(s, dict):
                s["title"] = self._strip_continued_suffix(str(s.get("title") or "Ná»™i dung"))

        # 2) Borrow bullets from neighbor slides before invoking LLM.
        for i, s in enumerate(slides):
            if not isinstance(s, dict):
                continue
            bs = s.get("bullets") or []
            if not isinstance(bs, list):
                bs = []
            while len(bs) < min_b:
                moved = False
                if i - 1 >= 0 and isinstance(slides[i - 1], dict):
                    prev = slides[i - 1].get("bullets") or []
                    if isinstance(prev, list) and len(prev) > min_b:
                        bs.insert(0, prev.pop())
                        moved = True
                if not moved and i + 1 < len(slides) and isinstance(slides[i + 1], dict):
                    nxt = slides[i + 1].get("bullets") or []
                    if isinstance(nxt, list) and len(nxt) > min_b:
                        bs.append(nxt.pop(0))
                        moved = True
                if not moved:
                    break
            s["bullets"] = bs[:MAX_BULLETS_PER_SLIDE]

        # 3) LLM densify only remaining thin slides.
        for s in slides:
            if rewrites >= max_rw:
                break
            if not isinstance(s, dict):
                continue
            title = str(s.get("title") or "Ná»™i dung")
            bullets = s.get("bullets") or []
            if not isinstance(bullets, list):
                bullets = []
            bullets = [str(b or "").strip() for b in bullets if str(b or "").strip()]
            if len(bullets) >= min_b:
                s["bullets"] = bullets[:MAX_BULLETS_PER_SLIDE]
                continue
            try:
                msgs = self._build_densify_slide_messages(deck_title, title, bullets, target_count=min_b)
                data = await self._request_json_dict(
                    msgs,
                    target_slides=1,
                    fast_mode=False,
                    compose_mode=False,
                    structured_output="bullets",
                )
                cand = data.get("bullets") if isinstance(data, dict) else None
                if isinstance(cand, list) and cand:
                    fixed = [self._repair_incomplete_tail(str(x or "").strip()) for x in cand if str(x or "").strip()]
                    # Accept only if density is improved and bullets are reasonably clean.
                    if len(fixed) >= min_b and sum(1 for x in fixed if self._bullet_needs_final_fix(x)) <= 1:
                        s["bullets"] = fixed[:MAX_BULLETS_PER_SLIDE]
                        rewrites += 1
            except Exception as e:
                print(f"Final density gate failed ({title!r}): {e}")

        return structured

    async def _refine_deck_with_optional_second(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        """Refine láº§n 1, sau Ä‘Ã³ láº·p thÃªm tá»‘i Ä‘a LLM_REFINE_MAX_EXTRA_PASSES khi váº«n cÃ³ bullet cá»¥t."""
        structured = await self._refine_slides_final(structured)
        if not LLM_REFINE_EXTRA_IF_TRUNCATED:
            return structured
        extra = 0
        max_extra = max(0, int(LLM_REFINE_MAX_EXTRA_PASSES))
        while extra < max_extra and self._deck_has_truncated_bullets(structured):
            extra += 1
            print(f"Extra refine pass {extra}/{max_extra} (truncated bullets still detected)...")
            structured = await self._refine_slides_final(structured)
        return structured

    def _merged_body_from_raw(self, raw_content: str) -> Dict[str, str]:
        """Chuáº©n hÃ³a ná»™i dung ngáº¯n thÃ nh dáº¡ng merged summary (## + bullet) khÃ´ng qua LLM."""
        norm = self._normalize_for_llm(raw_content or "")
        doc_title = "BÃ i thuyáº¿t trÃ¬nh"
        for ln in norm.split("\n"):
            s = ln.strip()
            if s.startswith("#"):
                doc_title = re.sub(r"^#+\s*", "", s).strip()[:120] or doc_title
                break
        body = (norm.strip() or (raw_content or "").strip())
        if not body:
            body = " "
        return {"title": doc_title, "content": body}

    async def _expand_group_generate_refine_pipeline(
        self,
        merged_summary: Dict[str, str],
        target_slides: int,
    ) -> Dict[str, Any]:
        """Luá»“ng slide duy nháº¥t sau khi cÃ³ báº£n merged: expand â†’ group â†’ generate â†’ refine â†’ normalize."""
        print(
            f"Slide pipeline: expand â†’ group â†’ generate â†’ refine (target ~{target_slides} slides)"
        )
        expanded = await self._expand_content_final(
            merged_summary["content"], target_slides=target_slides
        )
        sections = await self._group_content_final(expanded)
        structured = await self._generate_slides_for_sections(
            sections, target_slides=target_slides
        )
        try:
            structured = await self._refine_deck_with_optional_second(structured)
            structured = await self._repair_truncated_bullets_targeted(structured)
            if LLM_BULLET_POLISH_PASS:
                structured = await self._polish_slide_bullets_quality(structured)
            if LLM_FINAL_QUALITY_GATE:
                structured = await self._run_final_quality_gate(structured)
            if LLM_FINAL_DENSITY_GATE:
                structured = await self._run_final_density_gate(structured)
        except Exception:
            structured = await self._refine_slides_final(structured)
            structured = await self._repair_truncated_bullets_targeted(structured)
            if LLM_BULLET_POLISH_PASS:
                structured = await self._polish_slide_bullets_quality(structured)
            if LLM_FINAL_QUALITY_GATE:
                structured = await self._run_final_quality_gate(structured)
            if LLM_FINAL_DENSITY_GATE:
                structured = await self._run_final_density_gate(structured)
        return self._normalize_structured_content(structured)

    async def extract_and_structure(
        self,
        raw_content: str,
        target_slides_override: Optional[int] = None,
        force_exact_slide_count: bool = False,
        progress_cb: Optional[Callable[[int, int], Awaitable[None]]] = None,
        should_stop: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> Dict[str, Any]:
        """
        TrÃ­ch xuáº¥t vÃ  cáº¥u trÃºc hÃ³a ná»™i dung thÃ nh format phÃ¹ há»£p cho slide.

        Má»™t luá»“ng xá»­ lÃ½ LLM sau khi cÃ³ merged/summary: expand â†’ group â†’ generate â†’ refine
        (hÃ m `_expand_group_generate_refine_pipeline`), dÃ¹ng chung cho ná»™i dung ngáº¯n vÃ  chunking.

        progress_cb (done, total):
            Khi cÃ³ backend LLM, má»—i láº§n gá»i thÃ nh cÃ´ng vÃ  parse Ä‘Æ°á»£c JSON (Ollama/vLLM)
            tÄƒng done; total Æ°á»›c lÆ°á»£ng ban Ä‘áº§u vÃ  giÃ£n náº¿u pipeline gá»i nhiá»u láº§n hÆ¡n.
            Worker map Ä‘oáº¡n nÃ y lÃªn ~30â€“70% tá»•ng job.

        Returns:
            {
                "title": "TiÃªu Ä‘á» chÃ­nh",
                "slides": [
                    {
                        "title": "TiÃªu Ä‘á» slide",
                        "bullets": ["Äiá»ƒm 1", "Äiá»ƒm 2", ...],
                        "notes": "Ghi chÃº (optional)"
                    },
                    ...
                ]
            }
        """
        self._slide_lang_hint = self._detect_output_language_hint(raw_content or "")
        if self._slide_lang_hint in ("vi", "en"):
            print(f"Slide language hint: {self._slide_lang_hint} (match source)")
        # Náº¿u khÃ´ng cÃ³ vLLM, dÃ¹ng fallback ngay
        if not self.vllm_available:
            structured = self._normalize_structured_content(self._fallback_structure(raw_content))
            if force_exact_slide_count and target_slides_override:
                structured = self._force_slide_count_exact(structured, target_slides_override)
            if progress_cb:
                await progress_cb(1, 1)
            return structured

        if progress_cb:
            self._progress_track_begin(progress_cb)
        try:
            # Náº¿u content quÃ¡ dÃ i, dÃ¹ng chunking.
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
                    structured = self._force_slide_count_exact(structured, target_slides_override)
                return structured

            if should_stop and await should_stop():
                raise TaskCancelledError("Task cancelled by user")

            # FINAL SPEC (short content): cÃ³ thá»ƒ bá» summarize Ä‘á»ƒ tiáº¿t kiá»‡m 1 vÃ²ng LLM.
            merged_summary: Dict[str, str]
            if LLM_SHORT_PATH_SKIP_SUMMARIZE:
                print(
                    "Short content: skip summarize (LLM_SHORT_PATH_SKIP_SUMMARIZE); "
                    "merged body â†’ pipeline"
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
                structured = self._force_slide_count_exact(structured, target_slides_override)
            return structured
        finally:
            if progress_cb:
                await self._progress_track_finalize()
                self._progress_track_clear()

    def _force_slide_count_exact(self, structured_content: Dict[str, Any], desired_slides: int) -> Dict[str, Any]:
        """Force deck slide count to exactly `desired_slides`.

        - If too many slides: trim.
        - If too few: split bullets from the slide with most bullets.
        """
        if not isinstance(structured_content, dict):
            return structured_content
        desired_slides = int(desired_slides)
        if desired_slides <= 0:
            return structured_content

        slides = structured_content.get("slides") or []
        if not isinstance(slides, list):
            return structured_content

        # Drop empty/broken slides first.
        slides = [s for s in slides if isinstance(s, dict) and (s.get("bullets") or [])]
        structured_content["slides"] = slides

        def _split_one(slides_list: List[Dict[str, Any]]) -> bool:
            # Pick slide with max bullets (>1) to split.
            candidates = [
                (idx, len(s.get("bullets") or []))
                for idx, s in enumerate(slides_list)
                if isinstance(s, dict) and len(s.get("bullets") or []) > 1
            ]
            if not candidates:
                # Recovery: náº¿u táº¥t cáº£ slide Ä‘á»u chá»‰ cÃ²n 1 bullet, khÃ´ng muá»‘n láº·p slide,
                # ta thá»­ tÃ¡ch 1 bullet dÃ i thÃ nh 2 bullet Ä‘á»ƒ táº¡o thÃªm slide.
                single_candidates = [
                    (idx, len((s.get("bullets") or [None])[0] or ""))
                    for idx, s in enumerate(slides_list)
                    if isinstance(s, dict) and len(s.get("bullets") or []) == 1
                ]
                if not single_candidates:
                    return False
                idx = max(single_candidates, key=lambda x: x[1])[0]
                slide = slides_list[idx]
                bullets = list(slide.get("bullets") or [])
                if len(bullets) != 1:
                    return False
                b = (bullets[0] or "").strip()
                # Need Ä‘á»§ dÃ i Ä‘á»ƒ tÃ¡ch
                if len(b) < 80:
                    return False

                # Prefer split by sentence end.
                sentences = re.split(r'(?<=[\.!?])\s+', b)
                sentences = [s.strip() for s in sentences if s.strip()]

                if len(sentences) >= 2:
                    # Take first N sentences until half length
                    half = len(b) // 2
                    left_parts: List[str] = []
                    left_len = 0
                    for snt in sentences:
                        if left_len >= half:
                            break
                        left_parts.append(snt)
                        left_len += len(snt) + 1
                    right_parts = sentences[len(left_parts):]
                    if not left_parts or not right_parts:
                        return False
                    left = " ".join(left_parts).strip()
                    right = " ".join(right_parts).strip()
                else:
                    # Fallback split by comma/semicolon/colon
                    parts = re.split(r'[,;:]\s+', b, maxsplit=1)
                    if len(parts) < 2:
                        return False
                    left = parts[0].strip()
                    right = parts[1].strip()

                # Validate parts
                lw = len(left.split())
                rw = len(right.split())
                if lw < 5 or rw < 5:
                    return False

                slide["bullets"] = [left]
                new_slide = dict(slide)
                new_slide["title"] = f"{slide.get('title', 'Ná»™i dung')} (tiáº¿p)"
                new_slide["bullets"] = [right]
                slides_list.insert(idx + 1, new_slide)
                return True

            idx = max(candidates, key=lambda x: x[1])[0]
            slide = slides_list[idx]
            bullets = list(slide.get("bullets") or [])
            if len(bullets) <= 1:
                return False
            mid = max(1, len(bullets) // 2)
            left = bullets[:mid]
            right = bullets[mid:]
            if not left or not right:
                return False

            slide["bullets"] = left
            new_slide = dict(slide)
            new_slide["title"] = f"{slide.get('title', 'Ná»™i dung')} (tiáº¿p)"
            new_slide["bullets"] = right
            # Insert after current slide.
            slides_list.insert(idx + 1, new_slide)
            return True

        # Trim if too many.
        if len(slides) > desired_slides:
            structured_content["slides"] = slides[:desired_slides]
            return structured_content

        # Split until enough.
        while len(slides) < desired_slides:
            ok = _split_one(slides)
            if not ok:
                # If we can't split further (mostly 1-bullet slides), pad by duplicating last slide.
                if not slides:
                    break
                last = dict(slides[-1])
                last["title"] = f"{last.get('title', 'Ná»™i dung')} (tiáº¿p)"
                slides.append(last)
                break

        if len(slides) > desired_slides:
            slides = slides[:desired_slides]
        structured_content["slides"] = slides

        # HARD FIX: náº¿u slide cÃ³ <2 bullets thÃ¬ chuyá»ƒn 1 bullet tá»« slide lÃ¢n cáº­n sang
        # (giá»¯ nguyÃªn slide count, chá»‰ "bÆ¡m chá»¯" Ä‘á»ƒ trÃ¡nh 1 slide 1 dÃ²ng).
        try:
            for i in range(len(slides)):
                if not isinstance(slides[i], dict):
                    continue
                bs = slides[i].get("bullets") or []
                if not isinstance(bs, list):
                    continue
                if len(bs) >= 2:
                    continue

                # Try from previous
                if i - 1 >= 0:
                    prev = slides[i - 1].get("bullets") or []
                    if isinstance(prev, list) and len(prev) > 1 and len(bs) < MAX_BULLETS_PER_SLIDE:
                        # Move one bullet
                        bs.insert(0, prev.pop())

                # Try from next
                if len(bs) < 2 and i + 1 < len(slides):
                    nxt = slides[i + 1].get("bullets") or []
                    if isinstance(nxt, list) and len(nxt) > 1 and len(bs) < MAX_BULLETS_PER_SLIDE:
                        bs.append(nxt.pop(0))

                slides[i]["bullets"] = bs[:MAX_BULLETS_PER_SLIDE]
        except Exception:
            pass

        return structured_content

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
                    # Retry crashed â†’ preserve attempt 0 result, don't fall to fallback
                    if best_result is not None:
                        print(
                            f"Retry failed; returning saved result from attempt 1 "
                            f"({len(best_result.get('slides', []))} slides)"
                        )
                        return best_result
                    continue  # attempt 0 failed, still try attempt 1

                # Soft-validate â€” skip invalid structure silently
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
        """Gá»i vLLM chat vÃ  parse JSON object Ä‘áº§u tiÃªn trong response.

        structured_output:
            None â€” khÃ´ng guided JSON.
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
            print(f"vLLM request failed, fallback to Gemini: {vllm_err}")
            result_text = await self._gemini_completion_plain_text(
                _msgs,
                max_tokens=max_tokens,
                temperature=float(_opts.get("temperature", 0.1)),
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
        result_text = self._clean_result_text(result_text)
        if not result_text:
            return None

        # DÃ¹ng JSONDecoder.raw_decode Ä‘á»ƒ khÃ´ng Ä‘áº¿m nháº§m { } náº±m trong chuá»—i JSON.
        decoder = json.JSONDecoder()
        for i, ch in enumerate(result_text):
            if ch != "{":
                continue
            try:
                obj, _end = decoder.raw_decode(result_text, i)
                if isinstance(obj, dict):
                    return obj
                if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                    return obj[0]
            except json.JSONDecodeError:
                continue

        json_start = result_text.find("{")
        if json_start >= 0:
            tail = result_text[json_start:]
            fixed = self._try_fix_json(tail)
            if fixed:
                try:
                    parsed = json.loads(fixed)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError as e:
                    print(f"JSON decode after _try_fix_json: {e}")

        return None

    def _estimate_summary_bullets(self, content: str, fast_mode: bool = False) -> int:
        """Estimate summary bullet count for the map step."""
        length = len(content or "")
        if fast_mode:
            return 5
        if length < 1800:
            return 5
        if length < 4000:
            return 6
        return 7

    def _build_summary_messages(self, content: str, fast_mode: bool = False) -> List[Dict[str, str]]:
        """Build messages for chunk summarization before final slide composition."""
        normalized = self._normalize_for_llm(content)
        # Balance speed/quality: trim prefill a bit for non-fast path.
        content_limit = 5000 if fast_mode else 5800
        content_preview = normalized[:content_limit] if len(normalized) > content_limit else normalized
        bullet_limit = self._estimate_summary_bullets(content, fast_mode=fast_mode)
        if fast_mode:
            word_limit = 16
        else:
            word_limit = 22 if LLM_QUALITY_MODE else 18

        system_msg = self._llm_system_prefix() + (
            "You extract key points from long documents for later slide generation.\n\n"
            + self._output_language_instruction()
            + "TASK:\n"
            "- Extract only important ideas; drop redundant examples and filler.\n"
            "- Paraphrase in your own words; keep proper names, numbers, dates, and technical terms.\n"
            "- Each bullet is a complete sentence with enough context for a slide (not a few words).\n"
            f"- Target ~12â€“16 words per bullet, max {word_limit} words; prefer finishing the sentence over filling length.\n"
            "- Do not use double-quote characters inside title/bullets (breaks JSON).\n"
            "- One idea per bulletâ€”do not merge unrelated ideas.\n"
            f"- For long passages: return at least 4 bullets. At most {bullet_limit} bullets.\n"
            "- Return ONLY JSON, no markdown fences or extra commentary.\n"
            "- Schema: {\"title\": \"section name\", \"bullets\": [\"...\"]}\n"
        )
        user_msg = (
            "Summarize this document chunk for the final slide step.\n\n"
            f"TEXT:\n{content_preview}\n\n"
            "Return JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def _fallback_summary(self, content: str, max_bullets: int = 5) -> Dict[str, Any]:
        """Build a summary section from fallback extraction when LLM summary fails."""
        fallback = self._fallback_structure(content)
        title = fallback.get("title") or "Ná»™i dung chÃ­nh"
        bullets: List[str] = []
        for slide in fallback.get("slides", []):
            for bullet in slide.get("bullets", []):
                clean = str(bullet).strip()
                if clean:
                    bullets.append(clean)
                if len(bullets) >= max_bullets:
                    break
            if len(bullets) >= max_bullets:
                break
        return {
            "title": title,
            "bullets": bullets[:max_bullets],
        }

    async def _summarize_chunk(self, chunk_content: str, fast_mode: bool = False) -> Dict[str, Any]:
        """Map step: summarize one chunk into a compact set of bullets."""
        messages = self._build_summary_messages(chunk_content, fast_mode=fast_mode)
        max_bullets = self._estimate_summary_bullets(chunk_content, fast_mode=fast_mode)
        try:
            summary = await self._request_json_dict(
                messages,
                target_slides=max(2, max_bullets // 2),
                fast_mode=fast_mode,
            )
            title = str(summary.get("title") or "Ná»™i dung chÃ­nh").strip()[:120]
            raw_bullets = summary.get("bullets", [])
            if isinstance(raw_bullets, str):
                raw_bullets = [raw_bullets]
            if not isinstance(raw_bullets, list):
                raise ValueError("Summary bullets missing")
            bullets = [str(b).strip() for b in raw_bullets if str(b).strip()][:max_bullets]
            if not bullets:
                raise ValueError("Summary bullets empty")
            # Model Ä‘Ã´i khi tráº£ quÃ¡ Ã­t bullet (Ä‘áº·c biá»‡t 1-2 bullet) cho cáº£ Ä‘oáº¡n dÃ i
            # â†’ deck sau bá»‹ "má»™t dÃ²ng má»™t slide"
            if len(bullets) < 4 and len(chunk_content or "") > 900 and not fast_mode:
                try:
                    base_msgs = self._build_summary_messages(chunk_content, fast_mode=False)
                    retry_msgs = [
                        {
                            "role": "system",
                            "content": base_msgs[0]["content"]
                            + "\n\nMANDATORY: Long passageâ€”return at least 4 distinct bullets; "
                            "do not merge everything into one bullet; each bullet must be one independent idea.\n",
                        },
                        base_msgs[1],
                    ]
                    summary2 = await self._request_json_dict(
                        retry_msgs,
                        target_slides=max(2, max_bullets // 2),
                        fast_mode=False,
                    )
                    rb2 = summary2.get("bullets", [])
                    if isinstance(rb2, str):
                        rb2 = [rb2]
                    if isinstance(rb2, list):
                        b2 = [str(b).strip() for b in rb2 if str(b).strip()][:max_bullets]
                        if len(b2) >= len(bullets):
                            title = str(summary2.get("title") or title).strip()[:120]
                            bullets = b2
                            print(f"  (chunk summary retry â†’ {len(bullets)} bullets)")
                except Exception as re:
                    print(f"  (chunk summary retry skipped: {re})")
            return {"title": title or "Ná»™i dung chÃ­nh", "bullets": bullets}
        except Exception as e:
            print(f"Summary fallback due to error: {e}")
            return self._fallback_summary(chunk_content, max_bullets=max_bullets)

    def _merge_chunk_summaries(self, summaries: List[Dict[str, Any]]) -> Dict[str, str]:
        """Reduce step input: merge chunk summaries into one compact markdown-like document."""
        lines: List[str] = []
        doc_title = "BÃ i thuyáº¿t trÃ¬nh"
        for idx, summary in enumerate(summaries, start=1):
            title = str(summary.get("title") or f"Pháº§n {idx}").strip()
            if idx == 1 and title:
                doc_title = title[:120]
            lines.append(f"## {title or f'Pháº§n {idx}'}")
            for bullet in summary.get("bullets", []):
                clean = str(bullet).strip()
                if clean:
                    lines.append(f"- {clean}")
            lines.append("")
        return {
            "title": doc_title,
            "content": "\n".join(lines).strip(),
        }

    def _partition_bullets(self, bullets: List[str], slide_count: int) -> List[List[str]]:
        """Split bullets into contiguous groups while preserving order."""
        clean_bullets = [str(b).strip() for b in bullets if str(b).strip()]
        if not clean_bullets:
            return []

        slide_count = max(1, min(slide_count, len(clean_bullets)))
        base_size = len(clean_bullets) // slide_count
        remainder = len(clean_bullets) % slide_count

        parts: List[List[str]] = []
        start = 0
        for idx in range(slide_count):
            size = base_size + (1 if idx < remainder else 0)
            end = start + size
            part = clean_bullets[start:end]
            if part:
                parts.append(part)
            start = end
        return parts

    def _expand_compact_slides(
        self,
        slides: List[Dict[str, Any]],
        min_slides: int,
    ) -> List[Dict[str, Any]]:
        """Split rich slides until reaching the minimum target or no useful split remains."""
        expanded = [
            {
                "title": str(slide.get("title") or "Ná»™i dung"),
                "bullets": list(slide.get("bullets", [])),
                "notes": str(slide.get("notes") or ""),
            }
            for slide in slides
            if slide.get("bullets")
        ]

        while len(expanded) < min_slides:
            split_index = -1
            split_size = 0
            for idx, slide in enumerate(expanded):
                bullet_count = len(slide.get("bullets", []))
                if bullet_count > split_size and bullet_count >= MAX_BULLETS_PER_SLIDE:
                    split_index = idx
                    split_size = bullet_count

            if split_index == -1:
                break

            source = expanded[split_index]
            bullets = list(source["bullets"])
            mid = max(2, len(bullets) // 2)
            if mid >= len(bullets):
                break

            left = bullets[:mid]
            right = bullets[mid:]
            if len(right) < 2:
                break

            source["bullets"] = left
            expanded.insert(
                split_index + 1,
                {
                    "title": f"{source['title']} (tiáº¿p)",
                    "bullets": right,
                    "notes": source["notes"],
                },
            )

        return expanded

    def _build_deck_from_chunk_summaries(
        self,
        summaries: List[Dict[str, Any]],
        slide_plan: Dict[str, int],
        outline: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create the final deck directly from chunk summaries without a final LLM compose step."""
        if not summaries:
            return {"title": "BÃ i thuyáº¿t trÃ¬nh", "slides": []}

        slides: List[Dict[str, Any]] = []
        doc_title = "BÃ i thuyáº¿t trÃ¬nh"

        for idx, summary in enumerate(summaries):
            raw_title = str(summary.get("title") or f"Pháº§n {idx + 1}").strip()
            section_title = self._sanitize_title(raw_title)[:120] or f"Pháº§n {idx + 1}"
            if idx == 0 and section_title:
                doc_title = section_title

            bullets_raw = summary.get("bullets", [])
            if isinstance(bullets_raw, str):
                bullets_raw = [bullets_raw]

            bullets: List[str] = []
            seen: set[str] = set()
            for bullet in bullets_raw:
                clean = str(bullet).strip()
                key = clean.lower()
                if clean and key not in seen:
                    bullets.append(clean)
                    seen.add(key)

            if not bullets:
                continue

            desired_slides = 1
            if outline and idx < len(outline):
                desired_slides = max(1, int(outline[idx].get("slides") or 1))
            elif len(bullets) >= 5:
                desired_slides = 2

            # Outline thÆ°á»ng phÃ¢n bá»• nhiá»u slide hÆ¡n sá»‘ bullet thá»±c táº¿ â†’ má»—i slide 1 dÃ²ng.
            # Giá»›i háº¡n: trung bÃ¬nh ~â‰¥3 bullet/slide khi chia (ceil(n/3) slide tá»‘i Ä‘a).
            max_slides_for_bullets = max(1, (len(bullets) + 2) // 3)
            desired_slides = min(desired_slides, max_slides_for_bullets)

            for part_idx, part in enumerate(self._partition_bullets(bullets, desired_slides), start=1):
                slide_title = section_title if part_idx == 1 else f"{section_title} (tiáº¿p)"
                slides.append({"title": slide_title, "bullets": part, "notes": ""})

        min_slides = max(1, int(slide_plan.get("min") or 1))
        expanded_slides = self._expand_compact_slides(slides, min_slides=min_slides)
        return self._normalize_structured_content({"title": doc_title, "slides": expanded_slides})

    def _estimate_reduce_slide_plan(self, summaries: List[Dict[str, Any]], merged_content: str) -> Dict[str, int]:
        """Estimate target/min/max slides for final compose from reduced summaries."""
        section_count = max(1, len(summaries))
        bullet_count = sum(len(section.get("bullets", [])) for section in summaries)
        content_len = len(merged_content or "")

        target_from_sections = section_count + max(1, section_count // 3)
        target_from_bullets = ((bullet_count + 1) // 3) + 2
        target_from_length = 8
        if content_len >= 3000:
            target_from_length = 10
        if content_len >= 5000:
            target_from_length = 12
        if content_len >= 8000:
            target_from_length = 14

        target = max(target_from_sections, target_from_bullets, target_from_length)

        # Heavier summaries deserve a slightly broader deck.
        if bullet_count >= 36:
            target += 1
        if content_len >= 9000:
            target += 1

        # Khi cháº¡y server máº¡nh, cho phÃ©p deck dÃ y hÆ¡n vÃ  â€œthoáº£i mÃ¡iâ€ sá»‘ slide hÆ¡n.
        # TrÃ¡nh tÃ¬nh tráº¡ng bá»‹ káº¹p quÃ¡ cháº·t quanh ~10 slide.
        # Keep quality mode broad, but avoid overly large decks that slow generation.
        upper_cap = 22 if LLM_QUALITY_MODE else 18
        target = max(section_count, min(upper_cap, target))
        min_slides = max(
            section_count,
            (target - 1) if LLM_QUALITY_MODE else (target - 3),
        )
        max_slides = min(
            28 if LLM_QUALITY_MODE else 20,
            target + (5 if LLM_QUALITY_MODE else 2),
        )
        return {
            "target": target,
            "min": min_slides,
            "max": max_slides,
        }

    def _plan_outline_rule_based(
        self,
        summaries: List[Dict[str, Any]],
        slide_plan: Dict[str, int],
    ) -> List[Dict[str, Any]]:
        """Rule-based outline: allocate slides proportionally by bullet count.

        Runs instantly (no LLM call). Gives near-identical results to LLM planning
        because the LLM also does weighted proportional allocation.
        """
        target = slide_plan["target"]
        min_s = slide_plan["min"]
        max_s = slide_plan["max"]
        n = len(summaries)

        bullet_counts = [max(1, len(s.get("bullets", []))) for s in summaries]
        total_bullets = sum(bullet_counts)

        # Proportional allocation, minimum 1 per section
        raw_alloc = [max(1, round(target * bc / total_bullets)) for bc in bullet_counts]

        # Adjust to hit target exactly
        total = sum(raw_alloc)
        diff = target - total
        if diff != 0:
            # Sort by fractional remainder to decide who gets +1 or -1
            remainders = [
                (target * bullet_counts[i] / total_bullets) - raw_alloc[i]
                for i in range(n)
            ]
            order = sorted(range(n), key=lambda i: -remainders[i])
            for k in range(abs(diff)):
                idx = order[k % n]
                raw_alloc[idx] += 1 if diff > 0 else (-1 if raw_alloc[idx] > 1 else 0)

        # Clamp to [min_s, max_s] by distributing excess
        total = sum(raw_alloc)
        if total < min_s:
            for i in range(min_s - total):
                raw_alloc[i % n] += 1
        elif total > max_s:
            over = total - max_s
            big = sorted(range(n), key=lambda i: -raw_alloc[i])
            for k in range(over):
                idx = big[k % n]
                if raw_alloc[idx] > 1:
                    raw_alloc[idx] -= 1

        return [
            {"section": str(summaries[i].get("title") or f"Pháº§n {i+1}"), "slides": raw_alloc[i]}
            for i in range(n)
        ]

    async def _plan_outline(
        self,
        summaries: List[Dict[str, Any]],
        merged_content: str,
        slide_plan: Dict[str, int],
    ) -> Optional[List[Dict[str, Any]]]:
        """Outline planning: rule-based (instant) with no LLM call needed.

        Returns list like [{"section": "X", "slides": 2}] or None if < 2 sections.
        """
        if len(summaries) < 2:
            return None
        plan = self._plan_outline_rule_based(summaries, slide_plan)
        return plan if plan else None

    def _build_outline_sections_messages(
        self,
        merged_content: str,
        min_sections: int = 5,
        max_sections: int = 8,
    ) -> List[Dict[str, str]]:
        """FINAL SPEC - Outline step.

        Input: merged_summary["content"] (Ä‘Ã£ lÃ  báº£n tÃ³m táº¯t theo ##)
        Output: JSON thuáº§n {"sections":[{"title": "...", "description": "..."}]}
        """
        normalized = self._normalize_for_llm(merged_content)
        preview = normalized[:7000] if len(normalized) > 7000 else normalized
        system_msg = self._llm_system_prefix() + (
            "You design content structure for a slide deck.\n\n"
            "RULES:\n"
            "- Return ONLY valid JSONâ€”no text outside JSON.\n"
            + self._output_language_instruction()
            + f"- Produce EXACTLY between {min_sections} and {max_sections} sections (inclusive).\n"
            "- Each section is a DISTINCT topic (no duplicated ideas).\n"
            "- description: 1â€“2 sentences on why the section matters and what it covers.\n"
            "- No overlap: one idea must not appear in multiple sections.\n\n"
            "Schema:\n"
            "{\"sections\": [{\"title\": \"...\", \"description\": \"...\"}]}"
        )
        user_msg = (
            "Summary by major headingsâ€”build an outline:\n\n"
            f"{preview}\n\n"
            "Return JSON matching the schema."
            + self._user_lang_reminder()
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    async def _plan_outline_sections(
        self,
        merged_content: str,
        min_sections: int = 5,
        max_sections: int = 8,
    ) -> List[Dict[str, Any]]:
        messages = self._build_outline_sections_messages(
            merged_content,
            min_sections=min_sections,
            max_sections=max_sections,
        )
        data = await self._request_json_dict(
            messages,
            target_slides=max_sections,
            fast_mode=True,
            compose_mode=False,
        )
        sections = data.get("sections") if isinstance(data, dict) else None
        if not isinstance(sections, list):
            return []
        cleaned: List[Dict[str, Any]] = []
        for s in sections:
            if not isinstance(s, dict):
                continue
            title = str(s.get("title") or "").strip()
            desc = str(s.get("description") or "").strip()
            if not title or not desc:
                continue
            cleaned.append({"title": title[:80], "description": desc})
        # Clamp sá»‘ section vá» [min,max] (náº¿u model tráº£ lá»‡ch).
        if len(cleaned) > max_sections:
            cleaned = cleaned[:max_sections]
        if len(cleaned) < min_sections and cleaned:
            # Náº¿u Ã­t hÆ¡n, duplicate description Ä‘á»ƒ Ä‘á»§ sá»‘ section theo Ä‘Ãºng schema.
            while len(cleaned) < min_sections:
                cleaned.append(dict(cleaned[-1]))
        return cleaned

    def _build_expansion_messages(
        self,
        merged_content: str,
        outline_sections: List[Dict[str, Any]],
        target_slides: int,
    ) -> List[Dict[str, str]]:
        """FINAL SPEC - Expansion step (lÃ m content phong phÃº hÆ¡n, KHÃ”NG summarize)."""
        normalized = self._normalize_for_llm(merged_content)
        preview = normalized[:7000] if len(normalized) > 7000 else normalized
        # Khi user chá»n nhiá»u slide: má»Ÿ rá»™ng sÃ¢u hÆ¡n + thÃªm vÃ­ dá»¥/phÃ¢n rÃ£.
        depth_rule = (
            "High target slide count: expand deeplyâ€”split ideas, add examples and explanations per part."
            if target_slides >= 12
            else "Expand enough so each point has context plus supporting examples."
        )
        outline_json = json.dumps(outline_sections, ensure_ascii=False)
        system_msg = self._llm_system_prefix() + (
            "You EXPAND material for slide generation.\n\n"
            "RULES:\n"
            "- DO NOT summarize. Do not compress.\n"
            "- Always expand: add explanations, examples, and supporting detail.\n"
            "- Each outline section must be clearly expandedâ€”not keyword lists.\n\n"
            + self._output_language_instruction()
            + "Schema:\n"
            "{\"expanded_content\": \"...\"}\n\n"
            "expanded_content format:\n"
            "- Use headings: ## <section_title>\n"
            "- Under each heading, write 2â€“4 paragraphs (explanation + examples).\n"
        )
        user_msg = (
            f"OUTLINE (distinct topics):\n{outline_json}\n\n"
            "SOURCE SUMMARY (expand from this; do not summarize it shorter):\n"
            f"{preview}\n\n"
            f"{depth_rule}\n"
            "Produce expanded_content per schema."
            + self._user_lang_reminder()
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    async def _expand_content(
        self,
        merged_content: str,
        outline_sections: List[Dict[str, Any]],
        target_slides: int,
    ) -> str:
        if not outline_sections:
            # Náº¿u outline fail, váº«n fallback báº±ng ná»™i dung Ä‘Ã£ cÃ³ Ä‘á»ƒ khÃ´ng cháº¿t pipeline.
            return merged_content
        messages = self._build_expansion_messages(
            merged_content,
            outline_sections=outline_sections,
            target_slides=target_slides,
        )
        data = await self._request_json_dict(
            messages,
            target_slides=max(8, min(target_slides, 16)),
            fast_mode=True,
            compose_mode=False,
        )
        expanded = data.get("expanded_content") if isinstance(data, dict) else None
        expanded = str(expanded or "").strip()
        return expanded if expanded else merged_content

    async def _outline_expand_generate(
        self,
        merged_content: str,
        slide_plan: Dict[str, int],
        target_slides_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        """FINAL SPEC pipeline after summary:
        outline -> expand -> generate slides -> normalize/balance
        """
        target_slides = int(target_slides_override or slide_plan.get("target") or 10)
        min_sections, max_sections = 5, 8
        print("Planning outline sections (5â€“8)...")
        outline_sections = await self._plan_outline_sections(
            merged_content,
            min_sections=min_sections,
            max_sections=max_sections,
        )
        print(f"Outline sections: {len(outline_sections)}")
        expanded_content = await self._expand_content(
            merged_content,
            outline_sections=outline_sections,
            target_slides=target_slides,
        )
        # Generate slides from expanded content (khÃ´ng compose_mode).
        final_result = await self._extract_compact_content(
            expanded_content,
            target_slides=target_slides,
            chunk_mode=False,
            fast_mode=LLM_FAST_MODE,
            compose_mode=False,
        )
        # FINAL SPEC: Ä‘áº£m báº£o slide count Ä‘Ãºng {N} ká»ƒ cáº£ khi post-process
        # (lá»c/dedup/merge) lÃ m trÆ°á»£t sá»‘ slide.
        final_result = self._force_slide_count_exact(final_result, target_slides)
        return final_result

    async def _summarize_chunk_with_retries(
        self,
        chunk: str,
        chunk_idx: int,
        total_chunks: int,
        should_stop: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> List[Dict[str, Any]]:
        """Map step: má»™t chunk â†’ má»™t hoáº·c nhiá»u summary dict (subchunk khi timeout)."""
        print(f"Summarizing chunk {chunk_idx + 1}/{total_chunks} ({len(chunk)} chars)...")
        parts: List[Dict[str, Any]] = []
        try:
            summary_result = await asyncio.wait_for(
                self._summarize_chunk(chunk),
                timeout=LLM_CHUNK_TIMEOUT_SEC,
            )
            bullets_got = len(summary_result.get("bullets", []))
            print(f"  âœ“ Chunk {chunk_idx + 1} summary done â†’ {bullets_got} bullets")
            parts.append(summary_result)
        except asyncio.TimeoutError:
            print(
                f"  ! Chunk {chunk_idx + 1} summary timeout (>{LLM_CHUNK_TIMEOUT_SEC:.0f}s), retry fast mode"
            )
            try:
                summary_result = await asyncio.wait_for(
                    self._summarize_chunk(chunk, fast_mode=True),
                    timeout=LLM_CHUNK_FAST_TIMEOUT_SEC,
                )
                bullets_got = len(summary_result.get("bullets", []))
                print(f"  âœ“ Chunk {chunk_idx + 1} fast summary done â†’ {bullets_got} bullets")
                parts.append(summary_result)
            except asyncio.TimeoutError:
                print(
                    f"  ! Chunk {chunk_idx + 1} still timeout (>{LLM_CHUNK_FAST_TIMEOUT_SEC:.0f}s), split smaller for summary"
                )
                subchunks = self._split_chunk_by_size(chunk, max_chars=3200)
                for sub_idx, subchunk in enumerate(subchunks):
                    if should_stop and await should_stop():
                        raise TaskCancelledError("Task cancelled by user")
                    try:
                        sub_result = await asyncio.wait_for(
                            self._summarize_chunk(subchunk, fast_mode=True),
                            timeout=LLM_SUBCHUNK_TIMEOUT_SEC,
                        )
                        parts.append(sub_result)
                        print(
                            f"    âœ“ Subchunk {sub_idx + 1}/{len(subchunks)} summary done"
                        )
                    except asyncio.TimeoutError:
                        print(
                            f"    âœ— Subchunk {sub_idx + 1}/{len(subchunks)} timeout, skipping"
                        )
                    except Exception as e:
                        print(
                            f"    âœ— Subchunk {sub_idx + 1}/{len(subchunks)} error: {e}"
                        )
        except TaskCancelledError:
            raise
        except Exception as e:
            print(f"  âœ— Chunk {chunk_idx + 1} error: {e}")
        return parts

    async def _extract_with_chunking(
        self,
        raw_content: str,
        should_stop: Optional[Callable[[], Awaitable[bool]]] = None,
        target_slides_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Chunking strategy: chia content theo Heading; summary map theo LLM_CHUNK_PARALLEL;
        merge rá»“i cÃ¹ng má»™t luá»“ng `_expand_group_generate_refine_pipeline` nhÆ° ná»™i dung ngáº¯n.
        """
        chunks = self._split_by_headings(raw_content)
        
        if len(chunks) == 1:
            if should_stop and await should_stop():
                raise TaskCancelledError("Task cancelled by user")
            # Má»™t chunk: summary â†’ merge â†’ cÃ¹ng pipeline slide chuáº©n.
            summary_result = await self._summarize_chunk(chunks[0], fast_mode=LLM_FAST_MODE)
            merged_summary = self._merge_chunk_summaries([summary_result])
            slide_plan = self._estimate_reduce_slide_plan([summary_result], merged_summary["content"])
            target_slides = int(target_slides_override or slide_plan.get("target") or 10)
            final_result = await self._expand_group_generate_refine_pipeline(
                merged_summary, target_slides
            )
            final_result = self._force_slide_count_exact(final_result, target_slides)
            if merged_summary.get("title") and final_result.get("title") == "BÃ i thuyáº¿t trÃ¬nh":
                final_result["title"] = merged_summary["title"]
            return final_result
        
        n_chunks = len(chunks)
        print(
            f"Split into {n_chunks} chunks based on headings "
            f"(LLM_CHUNK_PARALLEL={max(1, int(LLM_CHUNK_PARALLEL))})"
        )

        summary_sections: List[Dict[str, Any]] = []
        parallel = max(1, int(LLM_CHUNK_PARALLEL))
        sem = asyncio.Semaphore(parallel)

        async def _run_chunk(idx: int, chunk: str) -> tuple:
            if should_stop and await should_stop():
                raise TaskCancelledError("Task cancelled by user")
            async with sem:
                if should_stop and await should_stop():
                    raise TaskCancelledError("Task cancelled by user")
                plist = await self._summarize_chunk_with_retries(
                    chunk, idx, n_chunks, should_stop=should_stop
                )
            return idx, plist

        indexed = await asyncio.gather(
            *[_run_chunk(i, c) for i, c in enumerate(chunks)]
        )
        indexed = sorted(indexed, key=lambda x: x[0])
        for _i, plist in indexed:
            summary_sections.extend(plist)

        if should_stop and await should_stop():
            raise TaskCancelledError("Task cancelled by user")

        if not summary_sections:
            print("Warning: No chunk summaries available, using fallback structure")
            return self._normalize_structured_content(self._fallback_structure(raw_content))

        merged_summary = self._merge_chunk_summaries(summary_sections)
        slide_plan = self._estimate_reduce_slide_plan(summary_sections, merged_summary["content"])
        reduce_target_slides = slide_plan["target"]
        print(
            f"Reducing {len(summary_sections)} summaries into final deck (~{reduce_target_slides} slides, min {slide_plan['min']})..."
        )

        if should_stop and await should_stop():
            raise TaskCancelledError("Task cancelled by user")
        target_slides = int(target_slides_override or slide_plan.get("target") or 10)

        final_result = await self._expand_group_generate_refine_pipeline(
            merged_summary, target_slides
        )
        final_result = self._force_slide_count_exact(final_result, target_slides)
        if merged_summary.get("title") and final_result.get("title") == "BÃ i thuyáº¿t trÃ¬nh":
            final_result["title"] = merged_summary["title"]

        print(f"Done: {len(final_result.get('slides', []))} slides total")
        return final_result

    def _detect_heading_level(self, line: str) -> Optional[int]:
        """Detect heading level from markdown or common document patterns.

        Returns:
            1 | 2 | 3 for heading levels, or None if not heading.
        """
        text = (line or "").strip()
        if not text:
            return None

        # Markdown headings
        if text.startswith("### "):
            return 3
        if text.startswith("## "):
            return 2
        if text.startswith("# "):
            return 1

        # Vietnamese/English structural headings (must be followed by number or space+text)
        if re.match(r"^(CHÆ¯Æ NG|ChÆ°Æ¡ng)\s+[\dIVXivx]+", text):
            return 1
        if re.match(r"^(PHáº¦N|Pháº§n)\s+[\dIVXivx]+", text):
            return 1
        if re.match(r"^(Má»¤C|Má»¥c)\s+\d+", text):
            return 2
        if re.match(r"^(TIá»‚U\s*Má»¤C|Tiá»ƒu\s*má»¥c)\s+", text):
            return 3

        # Numbered headings â€” require >= 6 chars of content after the number
        # to avoid treating bullet items like "1. ok" as headings
        if re.match(r"^\d+\.\d+\.\d+\s+.{5,}", text) and len(text) <= 80:
            return 3
        if re.match(r"^\d+\.\d+\s+.{5,}", text) and len(text) <= 80:
            return 2
        # Single-level numbered heading ONLY if it looks like a real heading (not a bullet)
        # Must have >= 10 chars of title text and be short overall
        if re.match(r"^\d+\.\s+.{9,}$", text) and len(text) <= 70:
            return 2

        # ALL-CAPS short lines (>= 6 chars, no commas/semicolons)
        if text.isupper() and 6 <= len(text) <= 50 and not re.search(r"[,;]", text):
            return 2

        return None

    def _strip_heading_marker(self, line: str) -> str:
        """Strip common heading prefixes and markers."""
        text = (line or "").strip()
        text = re.sub(r"^#{1,3}\s+", "", text)
        text = re.sub(r"^(slide|silde)\s*\d+\s*[:\-â€“]\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(\d+\.\d+\.\d+|\d+\.\d+|\d+[\.)])\s+", "", text)
        return text.rstrip(":").strip()

    def _split_chunk_by_size(self, chunk_text: str, max_chars: int = 9000) -> List[str]:
        """Split an oversized chunk while preserving heading context."""
        if len(chunk_text) <= max_chars:
            return [chunk_text]

        lines = chunk_text.split("\n")
        heading_lines = [ln for ln in lines if ln.startswith("#")]
        heading_prefix = "\n".join(heading_lines).strip()

        # Keep non-heading body as paragraphs
        body_lines = [ln for ln in lines if not ln.startswith("#")]
        body = "\n".join(body_lines)
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]

        parts: List[str] = []
        current = heading_prefix + ("\n\n" if heading_prefix else "")
        for para in paragraphs:
            candidate = f"{current}{para}\n\n"
            if len(candidate) > max_chars and len(current.strip()) > 0:
                parts.append(current.strip())
                current = heading_prefix + ("\n\n" if heading_prefix else "") + para + "\n\n"
            else:
                current = candidate

        if current.strip():
            parts.append(current.strip())

        return parts if parts else [chunk_text]
    
    def _split_by_headings(self, content: str) -> List[str]:
        """
        Chia content theo phÃ¢n cáº¥p heading H1/H2/H3.
        Há»— trá»£ cáº£ markdown (#, ##, ###) vÃ  heading dáº¡ng sá»‘/chÆ°Æ¡ng/pháº§n/má»¥c.
        LÆ°u Ã½: KHÃ”NG normalize láº¡i á»Ÿ Ä‘Ã¢y Ä‘á»ƒ trÃ¡nh double-processing;
        normalize chá»‰ xáº£y ra 1 láº§n (khÃ´ng double-process).
        """
        # Chá»‰ clean line endings, khÃ´ng gá»™p/biáº¿n Ä‘á»•i ná»™i dung
        cleaned = content.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        lines = [ln.strip() for ln in cleaned.split("\n")]

        sections: List[Dict[str, Any]] = []
        h1 = ""
        h2 = ""
        h3 = ""
        body: List[str] = []

        def flush_section():
            nonlocal body
            if body:
                sections.append({
                    "h1": h1,
                    "h2": h2,
                    "h3": h3,
                    "body": "\n".join(body).strip()
                })
                body = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if body and body[-1] != "":
                    body.append("")
                continue

            level = self._detect_heading_level(stripped)
            if level:
                title = self._strip_heading_marker(stripped)
                flush_section()
                if level == 1:
                    h1 = title
                    h2 = ""
                    h3 = ""
                elif level == 2:
                    h2 = title
                    h3 = ""
                else:
                    h3 = title
                continue

            body.append(stripped)

        flush_section()

        if not sections:
            return [cleaned.strip() or content]

        # Build chunk text with heading context for each section
        raw_chunks: List[str] = []
        for sec in sections:
            header_lines: List[str] = []
            if sec.get("h1"):
                header_lines.append(f"# {sec['h1']}")
            if sec.get("h2"):
                header_lines.append(f"## {sec['h2']}")
            if sec.get("h3"):
                header_lines.append(f"### {sec['h3']}")

            chunk = "\n".join(header_lines)
            if sec.get("body"):
                chunk = f"{chunk}\n\n{sec['body']}" if chunk else sec["body"]
            raw_chunks.append(chunk.strip())

        # Merge small trailing sections into the previous chunk to cut LLM round-trips
        # (important on low-VRAM GPUs). Cap size so we stay near _split_chunk_by_size limits.
        merged_chunks: List[str] = []
        min_chunk_chars = 2200
        max_merged_len = 8000
        for chunk in raw_chunks:
            if merged_chunks and len(chunk) < min_chunk_chars:
                candidate = f"{merged_chunks[-1]}\n\n{chunk}".strip()
                if len(candidate) <= max_merged_len:
                    merged_chunks[-1] = candidate
                else:
                    merged_chunks.append(chunk)
            else:
                merged_chunks.append(chunk)

        # Enforce max chunk size
        final_chunks: List[str] = []
        for chunk in merged_chunks:
            final_chunks.extend(self._split_chunk_by_size(chunk, max_chars=7000))

        return final_chunks if final_chunks else [cleaned.strip() or content]
    
    async def _extract_single_chunk(self, chunk_content: str, fast_mode: bool = False) -> Dict[str, Any]:
        """Xá»­ lÃ½ 1 chunk vá»›i LLM (vLLM)."""
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

        Token budget per slide (JSON): keep bullets ~10â€“14 words to reduce finish_reason=length / cá»¥t cÃ¢u.
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
        # When quality mode: allow a bit more diversity to get "thoáº£i mÃ¡i" wording.
        # Giá»¯ temperature tháº¥p Ä‘á»ƒ háº¡n cháº¿ sinh bullet quÃ¡ ngáº¯n / sai schema.
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
        # Single-pass: Ä‘Æ°a nhiá»u kÃ½ tá»± hÆ¡n Ä‘á»ƒ khá»i chunk (nhanh); cÃ¢n vá»›i LLM_NUM_CTX
        content_limit = 9000 if chunk_mode else LLM_SINGLE_PASS_CHAR_LIMIT
        content_preview = normalized[:content_limit] if len(normalized) > content_limit else normalized
        if fast_mode:
            bullet_limit = 16
            bullet_chars = "35â€“65"
        else:
            # Æ¯u tiÃªn bullet ngáº¯n-hoÃ n-chá»‰nh Ä‘á»ƒ giáº£m cá»¥t cÃ¢u / cá»¥t JSON khi max_tokens cháº¡m tráº§n.
            bullet_limit = 18
            bullet_chars = "35â€“90"
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
            "1. Return ONLY valid JSONâ€”no text before or after the JSON object.\n"
            "2. No markdown code fences.\n"
            "3. Schema:\n"
            "{\"title\": \"...\", \"slides\": [{\"title\": \"...\", \"bullets\": [\"...\"], \"notes\": \"\"}]}\n\n"
            "BULLETS:\n"
            "- Paraphrase in your own words; keep proper names, places, numbers, dates, and technical terms from the source.\n"
            "- Each bullet: full sentence with subject and predicate; ends with a period.\n"
            f"- Each bullet: min ~10 words and ~{bullet_chars} characters (same language as source); max {bullet_limit} words. One bullet = one complete idea with contextâ€”not a label.\n"
            "- No double-quote characters inside titles/bullets.\n"
            "- No empty label-only bullets (e.g. single-word section titles).\n"
            "- Never end with ... or â€¦\n"
            f"- Each slide: 3â€“5 bullets. Slide title: 3â€“8 words.\n"
            f"- You MUST return EXACTLY {target_slides} slides. If running out of tokens: close JSON cleanlyâ€”do not leave half sentences.\n"
            "- No duplicated content across slides.\n"
            "- If token budget is tight, finish the JSON structure; never truncate mid-sentence inside a bullet.\n"
            "- Each slide = one clear subtopic.\n\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + "\n"
            "GOOD bullet examples (illustrative styleâ€”use the source language in actual output):\n"
            "\"Má»¹ viá»‡n trá»£ tÃ i chÃ­nh lá»›n cho PhÃ¡p trong chiáº¿n tranh ÄÃ´ng DÆ°Æ¡ng.\"\n"
            "\"Hiá»‡p Ä‘á»‹nh GiÆ¡-ne chia cáº¯t Ä‘áº¥t nÆ°á»›c táº¡m thá»i.\"\n\n"
            "BAD examples (copy, cut off, too short):\n"
            "\"Táº¡i Ä‘Ã´ng dÆ°Æ¡ng, Má»¹ lÃ  nguá»“n tÃ i trá»£ chÃ­nh vÃ  to lá»›n cá»§a PhÃ¡p (ThÃ¡ng 10 nÄƒm 1953, phÃ³ tá»•ng...\"\n"
            "\"Tháº¯ng lá»£i quÃ¢n sá»±.\" â€” too short, no context."
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
        # Cap at 7000 chars â€” merged summaries are already compact, 12000 was overkill
        # and caused unnecessarily long prefill time on low-VRAM GPUs.
        content_preview = normalized[:7000] if len(normalized) > 7000 else normalized
        if LLM_QUALITY_MODE:
            # Khi cháº¡y server máº¡nh: cho AI khoáº£ng dao Ä‘á»™ng rá»™ng hÆ¡n vá» sá»‘ slide
            min_slides = max(8, min(target_slides, max(section_count, target_slides - 4)))
            max_slides = target_slides + 6
        else:
            min_slides = max(8, min(target_slides, max(section_count, target_slides - 2)))
            max_slides = target_slides + 2
        expansion_rule = (
            f"- Each '##' section must produce at least one slide.\n"
            f"- Total slide count MUST be exactly {target_slides}.\n"
            f"- If a slide is thin, add related bullets so each slide has 3â€“{MAX_BULLETS_PER_SLIDE} substantive bullets.\n"
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
                "Follow this allocationâ€”each section must get its assigned slide count.\n"
            )
        else:
            outline_rule = ""

        system_msg = self._llm_system_prefix() + (
            "You compose the final slide deck from intermediate summaries.\n\n"
            + self._output_language_instruction()
            + "HARD RULES:\n"
            "1. Return ONLY JSONâ€”no text outside the JSON object.\n"
            "2. Schema: {\"title\": \"...\", \"slides\": [{\"title\": \"...\", \"bullets\": [\"...\"], \"notes\": \"\"}]}\n"
            f"3. Each bullet: complete sentence, min ~10 words and ~45 chars, target ~10â€“18 words, hard max {MAX_WORDS_PER_BULLET} words, ends with a period; keep names, numbers, terms; if an idea is long, use two bullets.\n"
            f"4. Each slide: 3â€“{MAX_BULLETS_PER_SLIDE} bullets (prefer 3â€“4 when tight on length); use {MAX_BULLETS_PER_SLIDE} only when every bullet stays short and complete.\n"
            f"5. The source has about {section_count} major sections.\n"
            f"6. {expansion_rule}"
            "7. Paraphraseâ€”do not copy verbatim; stay concise but complete.\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + "\n"
            + (f"8. {outline_rule}" if outline_rule else "")
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
        """Thá»­ fix JSON bá»‹ lá»—i format"""
        try:
            # Loáº¡i bá» text ngoÃ i JSON
            json_str = json_str.strip()

            # Fix split-array bullets: "bullets": ["a"], ["b"] â†’ "bullets": ["a", "b"]
            # Model sometimes generates multiple separate arrays instead of one.
            json_str = re.sub(r'\]\s*,\s*\[', ', ', json_str)

            # Náº¿u JSON bá»‹ cáº¯t giá»¯a chá»«ng (khÃ´ng cÃ³ closing brace)
            open_braces = json_str.count('{')
            close_braces = json_str.count('}')
            
            if open_braces > close_braces:
                # ThÃªm closing braces cÃ²n thiáº¿u
                missing = open_braces - close_braces
                # TÃ¬m vá»‹ trÃ­ cuá»‘i cÃ¹ng cÃ³ ná»™i dung há»£p lá»‡
                # Thá»­ Ä‘Ã³ng array trÆ°á»›c
                if json_str.rstrip().endswith(','):
                    json_str = json_str.rstrip().rstrip(',')
                
                if ('"bullets":' in json_str or '"content":' in json_str) and not json_str.rstrip().endswith(']'):
                    json_str += ']'
                
                json_str += '}' * missing
            
            # Thá»­ parse
            json.loads(json_str)
            return json_str
            
        except Exception as e:
            print(f"Failed to fix JSON: {e}")
            return None
    
    def _normalize_for_llm(self, content: str) -> str:
        """Normalize content Ä‘á»ƒ LLM hiá»ƒu tá»‘t hÆ¡n - GIá»® NGUYÃŠN markup headings"""
        if not content:
            return ""
        
        # Normalize line breaks
        text = content.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("_x000D_", " ")
        
        # Split into lines
        lines = [ln.strip() for ln in text.split("\n")]
        lines = [ln for ln in lines if ln]
        
        # Gá»™p cÃ¡c dÃ²ng ngáº¯n thÃ nh paragraph
        paragraphs = []
        current_para = []
        
        for line in lines:
            # Náº¿u lÃ  markdown heading (tá»« DOCX styles)
            if line.startswith("#"):
                if current_para:
                    paragraphs.append(" ".join(current_para))
                    current_para = []
                paragraphs.append(line)  # Giá»¯ nguyÃªn markdown heading
                continue

            level = self._detect_heading_level(line)
            if level:
                if current_para:
                    paragraphs.append(" ".join(current_para))
                clean_heading = self._strip_heading_marker(line)
                paragraphs.append(f"{'#' * level} {clean_heading}".strip())
                current_para = []
            elif len(line) < 40 and not re.search(r"[\.\?\!:]$", line):
                # DÃ²ng ngáº¯n, gá»™p vá»›i paragraph hiá»‡n táº¡i
                current_para.append(line)
            else:
                # DÃ²ng dÃ i hoáº·c káº¿t thÃºc báº±ng dáº¥u cÃ¢u
                if current_para:
                    current_para.append(line)
                    paragraphs.append(" ".join(current_para))
                    current_para = []
                else:
                    paragraphs.append(line)
        
        if current_para:
            paragraphs.append(" ".join(current_para))
        
        # Join vá»›i double newline
        result = "\n\n".join(paragraphs)
        result = re.sub(r" +", " ", result)
        return result.strip()
    
    def _fallback_structure(self, content: str) -> Dict[str, Any]:
        """Cáº¥u trÃºc fallback náº¿u LLM khÃ´ng kháº£ dá»¥ng"""
        text = (content or "").strip()
        if not text:
            return {"title": "BÃ i thuyáº¿t trÃ¬nh", "slides": [{"title": "Ná»™i dung", "bullets": ["(trá»‘ng)"], "notes": ""}]}

        # Normalize newlines/spaces
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Remove docx artifacts
        text = text.replace("_x000D_", "\n")
        text = re.sub(r"[ \t]+", " ", text)

        lines = [ln.strip() for ln in text.split("\n")]
        lines = [ln for ln in lines if ln]

        def is_slide_heading(line: str) -> bool:
            return bool(re.match(r"^(slide|silde)\s*\d+\s*[:\-â€“]\s*.+$", line, flags=re.IGNORECASE))

        def clean_heading(line: str) -> str:
            # Remove common prefixes like "Slide 1: "
            line = line.lstrip("# ").strip()
            line = re.sub(r"^(slide|silde)\s*\d+\s*[:\-â€“]\s*", "", line, flags=re.IGNORECASE).strip()
            return line.rstrip(":").strip()

        # Guess document title from first non-slide heading line (avoid "Slide 1: ...")
        doc_title = "BÃ i thuyáº¿t trÃ¬nh"
        for ln in lines[:10]:
            if not is_slide_heading(ln) and len(ln) >= 6:
                doc_title = ln[:80]
                break

        def is_heading(line: str) -> bool:
            if len(line) > 80:
                return False
            if line.startswith(("#", "CHÆ¯Æ NG", "ChÆ°Æ¡ng", "PHáº¦N", "Pháº§n")):
                return True
            # Common pattern: "Slide 1:", "Slide 2 -", ...
            if is_slide_heading(line):
                return True
            if re.match(r"^(\d+(\.\d+)*)\s+.+$", line):
                return True
            # heading-ish: ends with ":" and not too long
            if line.endswith(":") and len(line) <= 60:
                return True
            return False

        def to_bullets(paragraph: str) -> List[str]:
            # split by sentence-ish, keep short bullets
            # IMPORTANT: don't split by ":" because it breaks lines like "Má»¥c tiÃªu: ..."
            parts = re.split(r"(?<=[\.\?\!])\s+|;\s+", paragraph.strip())
            bullets = []
            for p in parts:
                p = p.strip(" -â€¢\t")
                if not p:
                    continue
                # If there's a " + " joiner, split into multiple bullets
                if " + " in p and len(p) <= 120:
                    subparts = [sp.strip() for sp in p.split(" + ") if sp.strip()]
                else:
                    subparts = [p]
                for sp in subparts:
                    if not sp:
                        continue
                    if len(sp) > 180:
                        sp = sp[:177].rstrip() + "..."
                    bullets.append(sp)
            return bullets

        # Build sections
        sections: List[Dict[str, Any]] = []
        current = {"title": None, "bullets": []}

        for ln in lines:
            bullet_match = re.match(r"^(\-|\*|â€¢|\u2022|\d+\)|\d+\.)\s+(.*)$", ln)
            if is_heading(ln):
                if current["title"] or current["bullets"]:
                    sections.append(current)
                current = {"title": clean_heading(ln) or ln.lstrip("# ").rstrip(":"), "bullets": []}
                continue
            if bullet_match:
                current["bullets"].append(bullet_match.group(2).strip())
            else:
                # treat as paragraph -> bullets
                current["bullets"].extend(to_bullets(ln))

        if current["title"] or current["bullets"]:
            sections.append(current)

        # Convert sections -> slides
        slides: List[Dict[str, Any]] = []
        slide_idx = 1
        for sec in sections:
            title = sec["title"] or f"Ná»™i dung {slide_idx}"
            bullets = [b for b in sec["bullets"] if b]

            # chunk bullets into multiple slides if too many
            chunk_size = 5
            for chunk_i in range(0, len(bullets), chunk_size):
                chunk = bullets[chunk_i : chunk_i + chunk_size]
                if not chunk:
                    continue
                chunk_title = title if chunk_i == 0 else f"{title} (tiáº¿p)"
                slides.append({"title": chunk_title[:80], "bullets": chunk, "notes": ""})
                slide_idx += 1

        if not slides:
            slides = [{"title": "Ná»™i dung", "bullets": to_bullets(text)[:5] or ["(khÃ´ng tÃ¡ch Ä‘Æ°á»£c ná»™i dung)"], "notes": ""}]

        # cap for sanity
        return {"title": doc_title, "slides": slides[:20]}

    async def _llm_completion_plain_text(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int = 200,
        temperature: float = 0.55,
    ) -> str:
        """Má»™t láº§n chat completion, tráº£ vá» chá»¯ thÆ°á»ng (khÃ´ng parse JSON). DÃ¹ng cho prompt áº£nh SDXL.

        Qwen3 máº·c Ä‘á»‹nh báº­t thinking (<think>...</think>) â€” thÃªm /nothink vÃ o Ä‘áº§u system Ä‘á»ƒ táº¯t,
        trÃ¡nh model gá»­i cáº£ Ä‘oáº¡n suy nghÄ© dÃ i cho SDXL thay vÃ¬ output ngáº¯n gá»n.
        """
        _model = self.model_name
        if self.vllm_available:
            # Táº¯t thinking cho Qwen3 â€” chá»‰ cáº§n output ngáº¯n
            nothink_msgs = list(messages)
            if "qwen3" in (_model or "").lower() and nothink_msgs:
                first = dict(nothink_msgs[0])
                if first.get("role") == "system":
                    content = first.get("content", "")
                    if not content.startswith("/nothink"):
                        first["content"] = "/nothink\n" + content
                    nothink_msgs[0] = first

            # Strip pháº§n <think>...</think> náº¿u model váº«n tráº£ vá»
            def _strip_think(t: str) -> str:
                t = t.strip()
                while "<think>" in t and "</think>" in t:
                    s = t.find("<think>")
                    e = t.find("</think>") + len("</think>")
                    t = (t[:s] + t[e:]).strip()
                return t

            tsec = min(120.0, float(VLLM_TIMEOUT_SEC))
            timeout_cfg = httpx.Timeout(tsec, connect=25.0)
            payload: Dict[str, Any] = {
                "model": _model,
                "messages": nothink_msgs,
                "temperature": float(temperature),
                "top_p": 0.92,
                "max_tokens": int(max_tokens),
            }
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                resp = await client.post(
                    f"{self.vllm_base_url}/v1/chat/completions",
                    json=payload,
                    auth=self.vllm_basic_auth,
                )
                resp.raise_for_status()
                data = resp.json()
            txt = (data.get("choices", [{}])[0].get("message") or {}).get("content", "") or ""
            return _strip_think(txt)
        if self.gemini_available:
            return await self._gemini_completion_plain_text(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        return ""

    @staticmethod
    def _messages_to_gemini_text(messages: List[Dict[str, str]]) -> str:
        parts: List[str] = []
        for msg in messages or []:
            role = str(msg.get("role") or "user").strip().upper()
            content = str(msg.get("content") or "").strip()
            if content:
                parts.append(f"{role}:\n{content}")
        return "\n\n".join(parts).strip()

    async def _gemini_completion_plain_text(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        if not self.gemini_available:
            raise RuntimeError("Gemini fallback is not configured.")
        prompt_text = self._messages_to_gemini_text(messages)
        if not prompt_text:
            return ""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={self.gemini_api_key}"
        )
        timeout_cfg = httpx.Timeout(float(GEMINI_TIMEOUT_SEC), connect=25.0)
        payload: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "temperature": float(temperature),
                "topP": 0.92,
                "maxOutputTokens": max(128, int(max_tokens)),
            },
        }
        async with httpx.AsyncClient(timeout=timeout_cfg) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        content = (candidates[0] or {}).get("content") or {}
        text_chunks: List[str] = []
        for part in content.get("parts") or []:
            txt = (part or {}).get("text")
            if txt:
                text_chunks.append(str(txt))
        return "\n".join(text_chunks).strip()

    @staticmethod
    def _scrub_sdxl_positive(text: str) -> str:
        """Gá»¡ vÃ i keyword hay Ä‘áº©y model sang sÆ¡ Ä‘á»“/infographic/typo trong positive prompt."""
        t = (text or "").strip()
        if not t:
            return t
        t = _SDXL_NOISY_RE.sub(" ", t)
        return " ".join(t.split())

    @staticmethod
    def _sanitize_sdxl_prompt(text: str) -> str:
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

    def _fallback_sdxl_prompt(
        self, title: str, content_points: List[Any]
    ) -> str:
        """Khi khÃ´ng gá»i Ä‘Æ°á»£c LLM: gom Ä‘á» má»¥c + Ã½ Ä‘áº§u, thÃªm style cho SDXL (tiáº¿ng Anh)."""
        topic = (title or "presentation").strip()
        extra = ""
        if content_points:
            first = str(content_points[0]).strip()
            if first:
                extra = " " + first[:220]
        topic_en = (f"{topic}{extra}")[:200].strip()
        # Ãnh xáº¡ Ä‘Æ¡n giáº£n: láº¥y noun phrase Ä‘áº§u, thÃªm ngÃ´n ngá»¯ stock photography
        return self._scrub_sdxl_positive(
            f"calm workspace scene representing {topic_en}, "
            "soft window light, clean minimal background, single subject"
        )[:300]

    def _unwrap_slide_content(self, slide_content: Dict[str, Any]):
        """Unwrap {slide, context} wrapper hoáº·c dÃ¹ng trá»±c tiáº¿p. Tráº£ (slide, context)."""
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
        """Shared implementation cho extract_image_semantic / chart_spec / table_spec."""
        _slide, context = self._unwrap_slide_content(slide_content)
        if not self.vllm_available and not self.gemini_available:
            return {}
        try:
            raw = await self._llm_completion_plain_text(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Slide:\n{context}\n\nJSON:"},
                ],
                max_tokens=max_tokens,
                temperature=0.1,
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
        """Extract compact semantic JSON for image routing and prompt building."""
        return await self._extract_json_from_slide(
            slide_content, _IMAGE_SEMANTIC_SYSTEM, 180, "extract_image_semantic"
        )

    async def extract_chart_spec(self, slide_content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract editable chart data from a data-heavy slide."""
        return await self._extract_json_from_slide(
            slide_content, _CHART_SPEC_SYSTEM, 220, "extract_chart_spec"
        )

    async def extract_table_spec(self, slide_content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract table headers + rows from slide content (pipe/markdown style)."""
        return await self._extract_json_from_slide(
            slide_content, _TABLE_SPEC_SYSTEM, 900, "extract_table_spec"
        )

    async def extract_image_scene(
        self, slide_content: Dict[str, Any], system_prompt: str = ""
    ) -> str:
        """One-pass scene generation from slide content.

        Supports both input shapes for backward compatibility:
        - Direct slide dict: {"title", "bullets"/"content", ...}
        - Wrapper dict: {"slide": {...}, "context": "..."}
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
            return self._fallback_sdxl_prompt(title, content_points)

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
            result = _scrub_sdxl_prompt(self._sanitize_sdxl_prompt(raw))
            if len(result.split()) >= 8:
                return result[:500]
        except Exception as e:
            print(f"[extract_image_scene] LLM error: {e}")

        fallback = _scrub_sdxl_prompt(
            f"{photo_hint} Include {domain_object}. The scene is related to: {title}."
        )
        return fallback[:300]

    async def extract_keywords_for_image(self, slide_content: Dict[str, Any]) -> str:
        """Backward-compatible wrapper for legacy callers."""
        return await self.extract_image_scene(slide_content, system_prompt="")

