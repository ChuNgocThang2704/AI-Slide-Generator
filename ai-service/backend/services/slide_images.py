"""Generate slide images with semantic routing and safety guards."""
from __future__ import annotations

import base64
import json
import re
from typing import Any, Dict, List, Optional

# pyrefly: ignore [missing-import]
import httpx

from config import (
    IMAGE_DIR,
    IMAGE_GEN_API_BASE_URL,
    IMAGE_GEN_API_KEY,
    IMAGE_GEN_TIMEOUT_SEC,
    IMAGE_FALLBACK_API_BASE_URL,
    IMAGE_FALLBACK_API_KEY,
    IMAGE_FALLBACK_MODEL,
    IMAGE_FALLBACK_TIMEOUT_SEC,
    IMAGE_GUIDANCE_SCALE,
    IMAGE_HEIGHT,
    IMAGE_CLIP_MIN_SCORE,
    IMAGE_CLIP_SCORE_TIMEOUT_SEC,
    IMAGE_CLIP_VALIDATE_ENABLE,
    IMAGE_VLM_JUDGE_ENABLE,
    IMAGE_VLM_JUDGE_MAX_ARTIFACT,
    IMAGE_VLM_JUDGE_MIN_RELEVANCE,
    IMAGE_VLM_JUDGE_MODEL,
    IMAGE_VLM_JUDGE_TIMEOUT_SEC,
    IMAGE_MAX_SLIDES_WITH_IMAGES,
    IMAGE_MODEL_TYPE,
    IMAGE_NEGATIVE_PROMPT,
    IMAGE_PROMPT_SUFFIX,
    IMAGE_STEPS,
    IMAGE_STYLE_LOCKED,
    IMAGE_WIDTH,
    PEXELS_API_KEY,
    STOCK_PHOTO_ENABLE,
    GEMINI_API_KEY,
)
from services.image_semantics import (
    ACTION_DETAIL_MAP as _ACTION_DETAIL_MAP,
    ACTION_VISUAL_MAP as _ACTION_VISUAL_MAP,
    BRAND_NORMALIZATION_MAP as _BRAND_NORMALIZATION_MAP,
    CATASTROPHIC_FLAG_KEYWORDS as _CATASTROPHIC_FLAG_KEYWORDS,
    CATASTROPHIC_SACRED_KEYWORDS as _CATASTROPHIC_SACRED_KEYWORDS,
    CONTEXT_VISUAL_MAP as _CONTEXT_VISUAL_MAP,
    COVERAGE_THRESHOLD as _COVERAGE_THRESHOLD,
    CULTURAL_KEYWORDS as _CULTURAL_KEYWORDS,
    DOMAIN_OBJECT_HINTS as _DOMAIN_OBJECT_HINTS,
    EMOTION_KEYWORD_MAP as _EMOTION_KEYWORD_MAP,
    EMOTION_MAP as _EMOTION_MAP,
    HISTORICAL_REGION_KEYWORDS as _HISTORICAL_REGION_KEYWORDS,
    MEDICAL_DIAGRAM_KEYWORDS as _MEDICAL_DIAGRAM_KEYWORDS,
    OBJECT_VISUAL_MAP as _OBJECT_VISUAL_MAP,
    PERSON_HONORIFICS as _PERSON_HONORIFICS,
    PERSON_NEGATIVE_HINTS as _PERSON_NEGATIVE_HINTS,
    PERSON_PATTERN_FAMOUS as _PERSON_PATTERN_FAMOUS,
    RELIGIOUS_KEYWORDS as _RELIGIOUS_KEYWORDS,
    RISK_STYLE_OVERRIDES as _RISK_STYLE_OVERRIDES,
    SLIDE_TYPE_HINTS as _SLIDE_TYPE_HINTS,
    TYPE_KEYWORDS as _TYPE_KEYWORDS,
    VISUAL_POLICIES as _VISUAL_POLICIES,
)
from services.image_validation import (
    validate_output_image as _validate_output_image,
    write_debug_json as _write_debug_json,
    write_image_quality_report as _write_image_quality_report,
)
from services.stock_photos import fetch_external_image

_MIN_SCENE_CHARS = 12
async def _try_secondary_ai_image_fallback(
    client: httpx.AsyncClient,
    *,
    prompt: str,
    negative_prompt: str,
    payload_template: Dict[str, Any],
) -> Optional[bytes]:
    """Try Gemini Imagen as secondary image fallback.

    Replaces Together/FLUX which suffers persistent rate-limit errors.
    Uses the existing GEMINI_API_KEY — no extra credentials needed.
    Gemini Imagen does not accept negative_prompt; the arg is kept so
    all call-sites remain unchanged.
    """
    if not GEMINI_API_KEY:
        print("[slide_images] secondary AI fallback skipped: GEMINI_API_KEY not set")
        return None

    # Imagen 3 endpoint — model configurable via IMAGE_FALLBACK_MODEL
    # (set to "imagen-3.0-generate-002" or leave default below).
    model = (IMAGE_FALLBACK_MODEL or "").strip()
    if not model or model.startswith("black-forest-labs"):
        # Default: swap out the FLUX default for Imagen.
        model = "imagen-3.0-generate-002"

    width = int(payload_template.get("width") or IMAGE_WIDTH)
    height = int(payload_template.get("height") or IMAGE_HEIGHT)
    # Imagen only supports specific aspect ratios; pick the closest.
    if width >= height:
        aspect_ratio = "1:1" if abs(width - height) < 128 else "4:3"
    else:
        aspect_ratio = "3:4"

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateImages?key={GEMINI_API_KEY}"
    )
    req: Dict[str, Any] = {
        "prompt": {"text": (prompt or "")[:2000]},
        "number_of_images": 1,
        "aspect_ratio": aspect_ratio,
        "safety_filter_level": "BLOCK_MEDIUM_AND_ABOVE",
        "person_generation": "ALLOW_ADULT",
    }
    timeout = httpx.Timeout(float(IMAGE_FALLBACK_TIMEOUT_SEC), connect=25.0)
    try:
        resp = await client.post(url, json=req, timeout=timeout)
        if resp.status_code != 200:
            print(
                f"[slide_images] Gemini Imagen fallback HTTP {resp.status_code}: "
                f"{resp.text[:300]}"
            )
            return None
        data = resp.json()
        # Response shape: {"generatedImages": [{"image": {"imageBytes": "<b64>"}}]}
        generated = data.get("generatedImages") or []
        if not generated or not isinstance(generated[0], dict):
            print("[slide_images] Gemini Imagen fallback: empty generatedImages")
            return None
        image_obj = (generated[0] or {}).get("image") or {}
        b64_val = image_obj.get("imageBytes")
        if not isinstance(b64_val, str) or not b64_val.strip():
            print("[slide_images] Gemini Imagen fallback: no imageBytes in response")
            return None
        raw = base64.b64decode(b64_val)
        if not raw:
            print("[slide_images] Gemini Imagen fallback: decoded bytes empty")
            return None
        # Imagen returns JPEG by default; accept both PNG and JPEG.
        if raw.startswith(b"\x89PNG") or raw.startswith(b"\xff\xd8\xff"):
            return raw
        print(
            f"[slide_images] Gemini Imagen fallback: unexpected format "
            f"(first 4 bytes={raw[:4]!r})"
        )
        return None
    except Exception as e:
        print(f"[slide_images] Gemini Imagen fallback failed: {e}")
        return None


# Prompt and scene configuration.

_DEFAULT_NEGATIVE = (
    "text, watermark, logo, caption, subtitle, label, letters, words, "
    "ui screenshot, powerpoint slide, blurry, low quality, oversaturated, "
    "deformed, ugly, amateur, cartoon, anime, illustration artifact, "
    "worst quality, bad anatomy, malformed hands"
)

_ILLUSTRATION_NEGATIVE = (
    "text, watermark, logo, caption, subtitle, label, letters, words, "
    "ui screenshot, powerpoint slide, blurry, low quality, deformed, ugly"
)

_SOFT_REPLACEMENTS = {
    "diagram": "engineers discussing system on screens",
    "diagrams": "engineers discussing system on screens",
    "chart": "people analyzing data on screens",
    "charts": "people analyzing data on screens",
    "infographic": "documents and visuals on desk",
    "infographics": "documents and visuals on desk",
}



def _detect_emotion(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    for emotion, keywords in _EMOTION_KEYWORD_MAP.items():
        for kw in keywords:
            kw_l = kw.lower().strip()
            if not kw_l:
                continue
            if len(kw_l) <= 4 and " " not in kw_l:
                if _word_in_text(kw_l, text):
                    return emotion
            else:
                if kw_l in t:
                    return emotion
    return None


def _normalize_brand_terms(text: str) -> str:
    """Replace brand names with generic equivalents to avoid wrong logos and copyright issues."""
    if not text:
        return text
    out = text
    lower = out.lower()
    for brand, generic in _BRAND_NORMALIZATION_MAP.items():
        if brand in lower:
            pattern = re.compile(re.escape(brand), re.IGNORECASE)
            out = pattern.sub(generic, out)
            lower = out.lower()
    return out


def _word_in_text(word: str, text: str) -> bool:
    """Word-boundary match: avoid 'cu' matching inside 'cuộc/của'.

    Uses regex with Unicode word boundaries when possible. For multi-word phrases,
    falls back to substring match (multi-word phrases are rarely false positives).
    """
    if not word or not text:
        return False
    word_l = word.strip().lower()
    text_l = text.lower()
    if not word_l:
        return False
    if " " in word_l:
        return word_l in text_l
    pattern = rf"(?:^|(?<=[^\wÀ-ỹ])){re.escape(word_l)}(?=[^\wÀ-ỹ]|$)"
    try:
        return bool(re.search(pattern, text_l, flags=re.UNICODE))
    except re.error:
        return word_l in text_l


def _any_word_in_text(words: List[str], text: str) -> bool:
    return any(_word_in_text(w, text) for w in words)

def _looks_like_person_reference(text: str) -> bool:
    """Detect if text references a specific person.

    Conservative detection (only honorific + famous-name list).

    Earlier versions had a proper-noun fallback that flagged any 2-word
    capitalized phrase ("Amazon Rainforest", "Hà Nội", "Tesla", etc.) as
    a person reference, causing too many over-triggers of person_protected
    style override. We trust the LLM to mark real persons via honorifics or
    via the famous-name list; unlisted modern figures are acceptable risk.
    """
    if not text:
        return False
    t = text.lower()
    if _any_word_in_text(_PERSON_HONORIFICS, text):
        return True
    if any(name in t for name in _PERSON_PATTERN_FAMOUS):
        return True
    return False


# Routing, risk handling, and historical context.

def _classify_risk(slide: Dict[str, Any], semantic: Dict[str, Any], content_type: str) -> Optional[str]:
    """Classify whether the slide content is risky for photoreal SDXL output.

    Returns a risk tag (key into _RISK_STYLE_OVERRIDES) or None if no risk.
    Order matters: historical with person -> person_protected, otherwise historical.
    """
    title = str(slide.get("title") or "")
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, list):
        body = " ".join(str(b) for b in bullets[:4])
    else:
        body = str(bullets)
    full_text = f"{title}. {body}"

    if _any_word_in_text(_RELIGIOUS_KEYWORDS, full_text):
        return "religious"
    if _any_word_in_text(_CULTURAL_KEYWORDS, full_text):
        return "cultural"
    if _any_word_in_text(_MEDICAL_DIAGRAM_KEYWORDS, full_text):
        return "medical_diagram"
    if content_type == "historical":
        if _looks_like_person_reference(full_text):
            return "person_protected"
        return "historical"
    return None


def _risk_style_override(risk: Optional[str]) -> Optional[str]:
    if not risk:
        return None
    return _RISK_STYLE_OVERRIDES.get(risk)


def _is_catastrophic_risk(slide: Dict[str, Any]) -> Optional[str]:
    """Return reason string when slide content is catastrophic-risk for any image.

    For these cases, the safest action is to skip image entirely instead of
    rendering anything that could be wrong or disrespectful.
    """
    title = str(slide.get("title") or "")
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, list):
        body = " ".join(str(b) for b in bullets[:4])
    else:
        body = str(bullets)
    full_text = f"{title}. {body}"
    if _any_word_in_text(_CATASTROPHIC_FLAG_KEYWORDS, full_text):
        return "national_symbol"
    if _any_word_in_text(_CATASTROPHIC_SACRED_KEYWORDS, full_text):
        return "sacred_relic"
    return None

_ABSTRACT_CONCEPT_MAP: Dict[str, str] = {
    "philosophy": "people in deep thoughtful conversation, classical study with books",
    "ethics": "people debating fair decisions, calm meeting room with documents",
    "morality": "people considering right and wrong choices, contemplative real-world setting",
    "critical thinking": "person carefully examining evidence and notes",
    "logic": "person working through structured arguments on paper",
    "consciousness": "person in deep contemplation, quiet introspective scene",
    "mind": "person in deep thought, library or quiet study",
    "psychology": "researcher observing human behavior, counseling office",
    "religion": "people in spiritual practice, traditional sacred place",
    "spirituality": "person in quiet meditation, peaceful natural setting",
    "democracy": "people voting at a real polling station, civic engagement",
    "politics": "people debating in a real meeting hall",
    "law": "people reviewing legal documents in a courtroom",
    "justice": "people seeking fairness in a real courtroom setting",
    "freedom": "people gathering openly in public space, expressive scene",
    "equality": "diverse people working together as equals",
    "economy": "analysts reviewing market reports in a modern workspace",
    "finance": "people studying financial reports and screens",
    "marketing": "team planning a campaign with creative materials on table",
    "branding": "designer reviewing brand identity prints",
    "innovation": "team prototyping a creative idea hands-on",
    "creativity": "creators working on a hands-on creative project",
    "leadership": "leader guiding a team in a real workspace",
    "management": "manager coordinating team around a workspace",
    "strategy": "team mapping out plans on a large board",
    "education": "students learning with a teacher in a real classroom",
    "learning": "learners practicing skills with guidance",
    "teaching": "teacher explaining a concept to attentive students",
    "literature": "person reading and annotating a book at a desk",
    "history of": "people examining historical documents and artifacts",
    "mathematics": "student writing equations and proofs on paper",
    "math": "person working through equations with notes and references",
    "geometry": "person drawing precise geometric figures on paper",
    "physics": "researcher running an experiment with lab instruments",
    "chemistry": "scientist working with chemistry lab equipment",
    "biology": "researcher examining samples through a microscope",
    "medicine": "doctors reviewing patient records and medical equipment",
    "healthcare": "medical professionals providing care in a clinical setting",
    "blockchain": "developers reviewing connected blocks of data on screens, server room atmosphere",
    "cryptocurrency": "trader analyzing crypto charts and digital wallet on screens",
    "smart contract": "developer reviewing a contract logic on multiple screens",
    "neural network": "researcher examining interconnected nodes of data on a large display",
    "deep learning": "researchers training a model with data flowing on screens",
    "machine learning": "researcher analyzing patterns in data on screens",
    "artificial intelligence": "people working with an AI assistant interface",
    "ai model": "engineers reviewing model outputs on monitors",
    "algorithm": "developer reviewing code logic and pseudocode on a whiteboard",
    "data structure": "developer drawing data organization on a notebook",
    "compiler": "engineer inspecting code transformation on screens",
    "operating system": "engineers configuring systems in a server room",
    "cloud computing": "team managing distributed services on dashboards",
    "cybersecurity": "security analyst monitoring network alerts on screens",
    "encryption": "engineer reviewing security configuration on screens",
    "database": "engineer working with database queries on monitors",
    "api": "developers integrating services via documentation and code",
    "microservices": "engineers reviewing distributed service diagram on screens",
    "kubernetes": "engineers managing container clusters on dashboards",
    "devops": "engineers monitoring deployment pipelines on screens",
    "agile": "team in a stand-up meeting around a kanban board",
    "scrum": "team gathering around a kanban board for planning",
    "iot": "engineers configuring connected sensor devices",
    "robotics": "engineers building and testing a robot prototype",
    "blockchain technology": "developers reviewing blockchain network diagram on screens",
    "quantum computing": "scientists working with advanced research lab equipment",
    "vr": "people using VR headsets in a tech demo space",
    "ar": "person interacting with augmented reality on a tablet",
    "metaverse": "people interacting in a virtual collaboration space",
}


_ABSTRACT_CONCEPT_KEYS_SORTED: Optional[List[str]] = None


def _abstract_keys_sorted() -> List[str]:
    """Sort keys longest-first so 'machine learning' matches before 'learning'."""
    global _ABSTRACT_CONCEPT_KEYS_SORTED
    if _ABSTRACT_CONCEPT_KEYS_SORTED is None:
        _ABSTRACT_CONCEPT_KEYS_SORTED = sorted(
            _ABSTRACT_CONCEPT_MAP.keys(),
            key=lambda x: (-len(x), x),
        )
    return _ABSTRACT_CONCEPT_KEYS_SORTED


def _detect_abstract_concept(text: str) -> Optional[str]:
    """Return a concrete metaphor if the slide text matches an abstract concept.

    - Longest key matched first (so 'machine learning' beats 'learning')
    - Short keys (<=3 chars) require word-boundary match (so 'ar' won't match 'Sartre')
    """
    if not text:
        return None
    t = text.lower()
    for key in _abstract_keys_sorted():
        if len(key) <= 3:
            if _word_in_text(key, text):
                return _ABSTRACT_CONCEPT_MAP[key]
        else:
            if key in t:
                return _ABSTRACT_CONCEPT_MAP[key]
    return None


_HISTORICAL_PERIOD_HINTS: Dict[str, str] = {
    "Vietnam": "traditional Vietnamese setting, ao dai or peasant clothing, rural village or old city",
    "France": "French period setting, 18th-20th century European clothing, classical European architecture",
    "China": "traditional East Asian setting, period Chinese clothing, classical pavilion or imperial court",
    "Japan": "traditional Japanese setting, period kimono or military uniform, wooden architecture",
    "Korea": "traditional Korean setting, hanbok clothing, classical East Asian architecture",
    "Soviet Union": "early 20th century Eastern European setting, military uniform, austere architecture",
    "United States": "20th century American setting, period military or civilian clothing, urban or battlefield context",
    "Ancient Greece": "classical Greek setting, white tunics and togas, marble columns and agora",
    "Roman Empire": "ancient Roman setting, togas and legionary armor, marble forum or coliseum",
    "Ancient Egypt": "ancient Egyptian setting, linen garments and headdresses, sandstone temple or pyramid",
    "Persia": "ancient Persian setting, robes and turbans, palatial stone architecture",
    "Mesopotamia": "ancient Mesopotamian setting, woven robes, mudbrick city and ziggurat",
    "Mongol Empire": "Mongol steppe setting, leather armor and fur coats, horseback nomadic camp",
    "Ottoman Empire": "Ottoman setting, kaftans and turbans, domed mosque and bazaar",
    "Mughal Empire": "Mughal setting, ornate robes, marble palace with intricate patterns",
    "Islamic Caliphate": "medieval Islamic setting, scholarly robes, library and ornate mosque",
    "Aztec / Maya / Inca": "pre-Columbian Mesoamerican setting, feathered garments, stone pyramid temple",
    "Medieval Europe": "medieval European setting, peasant tunics or knight armor, stone castle and village",
    "Renaissance": "Renaissance European setting, period attire, classical artist studio or city plaza",
    "Industrial Revolution": "19th century industrial setting, working-class clothing, factory and steam machinery",
    "World War I": "early 20th century war setting, period military uniforms, trenches and field equipment",
    "World War II": "1940s war setting, period military uniforms, urban ruins or battlefield",
    "Cold War": "mid 20th century setting, conservative attire, austere government and surveillance atmosphere",
    "Europe": "European historical setting, period clothing, classical architecture",
}

_SCENE_SYSTEM_PROMPT = """Convert the slide into a REAL-WORLD PHOTOGRAPHABLE SCENE.

STRICT RULES:
- MUST include people, objects, and environment
- MUST include at least one human subject, one physical object, and one environment
- MUST visually represent the main idea of the slide
- DO NOT use abstract words alone (system, architecture, process, performance, solution)
- If the slide is abstract, convert it into a concrete real-life situation
- Use concrete nouns (engineer, computer, device, office, machine, document, meeting room, etc.)
- Scene must be specific and vivid, not generic
- Output must be ENGLISH only

Output: comma-separated phrases only, no sentence, no explanation."""


def _detect_slide_type(slide: Dict[str, Any]) -> str:
    title = (slide.get("title") or "").lower()
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, list):
        body = " ".join(str(b) for b in bullets[:4]).lower()
    else:
        body = str(bullets).lower()
    text = f"{title} {body}"
    for stype, keywords in _TYPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return stype
    return "default"


def _semantic_context(slide: Dict[str, Any], max_chars: int = 220) -> str:
    title = str(slide.get("title") or "").strip()
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, list):
        points = [str(b).strip() for b in bullets[:4] if str(b).strip()]
    else:
        points = [str(bullets).strip()]
    combined = ". ".join(filter(None, [title] + points))
    combined = re.sub(r"\s+", " ", combined).strip(" .")
    return combined[:max_chars]


def _slide_prompt_context(slide: Dict[str, Any], max_chars: int = 900) -> str:
    title = str(slide.get("title") or "").strip()
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, str):
        points = [bullets.strip()]
    else:
        points = [str(b).strip() for b in bullets[:5] if str(b).strip()]

    lines = []
    if title:
        lines.append(f"SLIDE TITLE: {title}")
    if points:
        lines.append("SLIDE BULLETS:")
        lines.extend(f"- {p}" for p in points)
    return "\n".join(lines)[:max_chars]


def _extract_semantic(slide: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback semantic extraction when LLM completely fails or is unavailable."""
    return {
        "source": "rule",
        "content_type": "normal",
        "domain": "general",
        "main_topic": str(slide.get("title") or "").strip()[:50] or "presentation slide",
        "action": "default",
        "object": "default",
        "context": "default",
        "actions": "default",
        "objects": "default",
        "contexts": "default",
        "entities": [],
        "visual_objects": [],
        "visual_intent": "",
        "stock_queries": [],
        "confidence": 0.0,
    }


def _semantic_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def _normalize_llm_semantic(raw: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return fallback
    try:
        confidence = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < 0.30:
        return fallback

    content_type = str(raw.get("content_type") or "normal").strip().lower()
    domain = str(raw.get("domain") or "general").strip().lower()
    action = str(raw.get("action") or "default").strip().lower()
    context = str(raw.get("context") or "default").strip().lower()

    objects = _semantic_list(raw.get("objects"))[:3]
    raw_visual_objects = _semantic_list(raw.get("visual_objects"))[:3]
    visual_objects = raw_visual_objects if raw_visual_objects else objects
    object_label = ", ".join(objects) if objects else "default"

    stock_queries = _semantic_list(raw.get("stock_queries"))[:4]

    normalized = dict(fallback)
    normalized.update(
        {
            "source": "llm",
            "content_type": content_type,
            "domain": domain,
            "main_topic": str(raw.get("main_topic") or fallback.get("main_topic") or "").strip()[:120],
            "action": action,
            "object": object_label,
            "context": context,
            "actions": action,
            "objects": object_label,
            "contexts": context,
            "entities": _semantic_list(raw.get("entities"))[:3],
            "visual_objects": visual_objects,
            "visual_intent": str(raw.get("visual_intent") or "").strip()[:160],
            "stock_queries": stock_queries,
            "confidence": confidence,
        }
    )
    return normalized


def _scene_from_semantic(semantic: Dict[str, Any]) -> str:
    action_keys = [x.strip() for x in str(semantic.get("actions") or "default").split(",") if x.strip()]
    object_keys = [x.strip() for x in str(semantic.get("objects") or "default").split(",") if x.strip()]
    context_keys = [x.strip() for x in str(semantic.get("contexts") or "default").split(",") if x.strip()]
    action_visual = ", ".join(
        _ACTION_VISUAL_MAP.get(a, _ACTION_VISUAL_MAP["default"])
        for a in (action_keys[:2] or ["default"])
    )
    visual_objects = _semantic_list(semantic.get("visual_objects"))[:2]
    object_visual = (
        ", ".join(visual_objects)
        if visual_objects
        else ", ".join(
            _OBJECT_VISUAL_MAP.get(o, _OBJECT_VISUAL_MAP["default"])
            for o in (object_keys[:2] or ["default"])
        )
    )
    context_visual = ", ".join(
        _CONTEXT_VISUAL_MAP.get(c, _CONTEXT_VISUAL_MAP["default"])
        for c in (context_keys[:2] or ["default"])
    )
    visual_intent = str(semantic.get("visual_intent") or "").strip()
    scene = f"{action_visual}, {object_visual}, in {context_visual}"
    if visual_intent:
        scene = f"{scene}, {visual_intent}"
    return scene


def _clean_entity_candidate(text: str) -> str:
    candidate = re.sub(r"\s+", " ", (text or "")).strip(" -–—:;,.\"'()[]")
    candidate = re.sub(
        r"^(title|slide|chủ đề|chu de|bài|bai|phần|phan)\s*[:.-]\s*",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    return candidate[:90].strip(" -–—:;,.\"'")


def _extract_historical_entity(text: str) -> Optional[str]:
    """Extract an open-ended historical entity from slide text.

    This intentionally avoids a fixed event list: historical entities are open-ended.
    It favors quoted names, proper-noun phrases, and phrases around year markers.
    """
    raw = re.sub(r"\s+", " ", (text or "")).strip()
    if not raw:
        return None

    quoted = re.findall(r"[\"“']([^\"”']{4,90})[\"”']", raw)
    for item in quoted:
        candidate = _clean_entity_candidate(item)
        if len(candidate.split()) >= 2:
            return candidate

    year_re = r"(?:1[5-9]\d{2}|20\d{2})(?:\s*[-–]\s*(?:1[5-9]\d{2}|20\d{2}))?"
    words = re.findall(r"[\wÀ-ỹ.-]+", raw, flags=re.UNICODE)
    for i, word in enumerate(words):
        if re.fullmatch(year_re, word):
            start = max(0, i - 8)
            end = min(len(words), i + 5)
            candidate = _clean_entity_candidate(" ".join(words[start:end]))
            if len(candidate.split()) >= 3:
                return candidate

    proper_phrases = re.findall(
        r"\b(?:[A-ZÀ-Ỹ][\wÀ-ỹ-]+(?:\s+|$)){2,8}",
        raw,
        flags=re.UNICODE,
    )
    for phrase in proper_phrases:
        candidate = _clean_entity_candidate(phrase)
        if len(candidate.split()) >= 3:
            return candidate

    first_clause = re.split(r"[.;\n]", raw, maxsplit=1)[0]
    candidate = _clean_entity_candidate(first_clause)
    if len(candidate.split()) >= 3:
        return candidate
    return None


_VN_INFERENCE_HINTS = [
    "bác", "bac",
    "việt", "viet",
    "đảng", "dang",
    "bộ chính trị", "bo chinh tri",
    "tự do", "tu do",
    "độc lập", "doc lap",
    "tuyên ngôn", "tuyen ngon",
    "đông dương", "dong duong",
    "miền bắc", "mien bac", "miền nam", "mien nam",
    "nhân dân", "nhan dan",
    "kháng chiến", "khang chien",
    "ba đình", "ba dinh",
    "quảng trường", "quang truong",
    "anh hùng", "anh hung",
]


def _has_vietnamese_diacritics(text: str) -> bool:
    """Quick heuristic: text contains Vietnamese-specific characters."""
    if not text:
        return False
    return bool(re.search(r"[ăâđêôơưĂÂĐÊÔƠƯạáàảãậấầẩẫắằẳẵặệếềểễịỉĩọóòỏõộốồổỗớờởỡợụúùủũứừửữựỳýỷỹỵ]", text))


def _detect_historical_region(text: str) -> Optional[str]:
    """Detect a likely region/country for historical content.

    Uses word-boundary for short keywords (acronyms, single words) to avoid
    'usa' matching inside 'usage', 'era' inside 'camera', etc.

    Adds a fallback: if no explicit region match and text contains VN-specific
    hints (Bác/Việt/Đảng/...) plus Vietnamese diacritics, infer Vietnam.
    """
    if not text:
        return None
    t = text.lower()
    for region, keywords in _HISTORICAL_REGION_KEYWORDS.items():
        for kw in keywords:
            kw_l = kw.lower().strip()
            if not kw_l:
                continue
            if len(kw_l) <= 5 and " " not in kw_l:
                if _word_in_text(kw_l, text):
                    return region
            else:
                if kw_l in t:
                    return region
    if _has_vietnamese_diacritics(text) and _any_word_in_text(_VN_INFERENCE_HINTS, text):
        return "Vietnam"
    return None


def _extract_year_token(text: str) -> Optional[str]:
    match = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", text or "")
    return match.group(1) if match else None


def _override_scene_by_content_type(
    content_type: str,
    title: str,
    source_text: str,
    semantic: Dict[str, Any],
    base_scene: str,
) -> str:
    """Override scene by content type while preserving the topic/entity at the front."""
    topic = (str(semantic.get("main_topic") or title or "the topic")).strip()
    full_text = f"{title}. {source_text}"
    base_scene_clean = (base_scene or "").strip()
    has_usable_scene = len(base_scene_clean) >= 30 and len(base_scene_clean.split()) >= 6

    if content_type == "historical":
        entities = _semantic_list(semantic.get("entities"))
        entity = entities[0] if entities else _extract_historical_entity(f"{title}. {source_text}")
        if entity and len(entity.split()) < 3:
            entity = None
        anchor = entity or topic

        full_hist_text = f"{full_text}. {anchor}"
        year = _extract_year_token(full_hist_text)
        region = _detect_historical_region(full_hist_text)
        has_person = _looks_like_person_reference(full_hist_text)

        bits = []
        if has_usable_scene:
            bits.append(base_scene_clean)
        elif has_person:
            bits.append(
                f"historical scene about {topic}, era of period clothing and traditional setting, "
                "no specific identifiable person rendered, generic crowd or symbolic depiction"
            )
        else:
            bits.append(anchor)
        if year:
            bits.append(f"year {year}")
        if region:
            bits.append(_HISTORICAL_PERIOD_HINTS.get(region, "period historical setting"))
        bits.extend([
            "documentary historical scene",
            "period-correct environment",
        ])
        return ", ".join(bits)

    if content_type in {"definition", "process", "normal"}:
        concrete = _detect_abstract_concept(full_text)
        if concrete:
            if has_usable_scene:
                return f"{base_scene_clean}, {concrete}"
            return f"{topic}, {concrete}"
    if content_type == "comparison":
        if has_usable_scene:
            return (
                f"{base_scene_clean}, split into two contrasting scenarios side by side, "
                "clear difference between left and right"
            )
        return (
            f"{topic}, split screen showing two contrasting scenarios, "
            "left and right comparison, clear difference"
        )
    if content_type == "definition":
        if has_usable_scene:
            return base_scene_clean
        if semantic.get("action", "default") == "default":
            return f"{topic}, people explaining concept using real-world example, practical objects, clear environment"
        return f"{topic}, people demonstrating concept in real-life situation, concrete objects and setting"
    if content_type == "process":
        if has_usable_scene:
            return f"{base_scene_clean}, sequential workflow in real setting"
        return f"{topic}, people performing clear process steps, tools in use, sequential workflow in real setting"
    if content_type == "data":
        if has_usable_scene:
            return base_scene_clean
        return f"{topic}, people analyzing with printed reports and dashboards in a real workspace"
    return base_scene


def _visual_policy(content_type: str) -> Dict[str, str]:
    return _VISUAL_POLICIES.get(content_type, _VISUAL_POLICIES["normal"])


def _truncate_at_word(text: str, max_chars: int) -> str:
    s = str(text or "").strip()
    if len(s) <= max_chars:
        return s
    cut = s[:max_chars].rstrip()
    for sep in (",", ";", "."):
        pos = cut.rfind(sep)
        if pos >= max(30, int(max_chars * 0.55)):
            return cut[:pos].strip(" ,;.")
    pos = cut.rfind(" ")
    if pos >= max(20, int(max_chars * 0.55)):
        return cut[:pos].strip(" ,;.")
    return cut.strip(" ,;.")


def _sanitize_scene(scene: str) -> str:
    t = str(scene or "").strip().lower()
    if not t:
        return ""
    # Remove common broken fragments from LLM scene text.
    t = re.sub(r"\b(with|around|on|in|at)\s+a\s+(?=,|\.|$)", " ", t)
    t = re.sub(r"\ba\s+(discussing|reviewing|showing|using)\b", r"people \1", t)
    t = re.sub(r"\bwith\s+a\s+filled\s+with\b", "with", t)
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r",\s*,+", ", ", t)
    for k, v in _SOFT_REPLACEMENTS.items():
        t = re.sub(rf"\b{re.escape(k)}\b", v, t)
    t = re.sub(r"\s+", " ", t).strip(" ,.;")
    pieces: List[str] = []
    seen = set()
    dropped_non_ascii: List[str] = []
    for piece in [p.strip() for p in t.split(",") if p.strip()]:
        if not _is_mostly_ascii(piece):
            dropped_non_ascii.append(piece)
            continue
        key = re.sub(r"\s+", " ", piece).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        pieces.append(piece)
    if not pieces and dropped_non_ascii:
        for piece in dropped_non_ascii[:2]:
            key = re.sub(r"\s+", " ", piece).strip().lower()
            if key in seen:
                continue
            seen.add(key)
            pieces.append(piece)
    t = ", ".join(pieces)
    if len(t.split()) < 5:
        t = f"{t}, realistic detailed environment with people".strip(" ,.;")
    return _truncate_at_word(t, 170)


def _trim_prompt(prompt: str, max_words: int = 50) -> str:
    words = (prompt or "").split()
    txt = " ".join(words[:max_words])
    txt = re.sub(r"\s+,", ",", txt)
    txt = re.sub(r",\s*,+", ", ", txt)
    txt = re.sub(r"\s+", " ", txt).strip(" ,")
    return txt


def _dedupe_prompt_phrases(prompt: str) -> str:
    """Drop comma-separated chunks that are duplicates or already covered by
    a longer chunk earlier in the prompt.

    Examples:
      "illustration of climate change, climate change, ..."
        -> "illustration of climate change, ..."
      "photo of A, B, photo of A, B, ..."
        -> "photo of A, B, ..."
    """
    parts = [p.strip() for p in str(prompt or "").split(",") if p.strip()]
    out: List[str] = []
    seen_keys: set[str] = set()
    seen_text: List[str] = []
    for part in parts:
        key = re.sub(r"\s+", " ", part).strip().lower()
        if key in seen_keys:
            continue
        if any(key in earlier for earlier in seen_text):
            continue
        seen_keys.add(key)
        seen_text.append(key)
        out.append(part)
    return ", ".join(out)


def _assemble_prioritized_prompt(
    prioritized: List[tuple[str, int]],
    max_words: int,
) -> str:
    """Build a prompt by joining priority-tagged parts; drop lowest priority
    parts (highest priority number) until the word budget is met. Original
    order is preserved for the surviving parts.
    """
    cleaned: List[tuple[int, str, int]] = []
    for original_index, (text, prio) in enumerate(prioritized):
        s = str(text or "").strip().strip(",")
        if not s:
            continue
        cleaned.append((original_index, s, prio))

    if not cleaned:
        return ""

    def _word_count(items: List[tuple[int, str, int]]) -> int:
        if not items:
            return 0
        joined = ", ".join(s for _, s, _ in items)
        return len(joined.split())

    surviving = list(cleaned)
    while _word_count(surviving) > max_words:
        max_prio = max(p for _, _, p in surviving)
        if max_prio <= 1:
            break
        for i in range(len(surviving) - 1, -1, -1):
            if surviving[i][2] == max_prio:
                surviving.pop(i)
                break

    surviving.sort(key=lambda x: x[0])
    full_prompt = ", ".join(s for _, s, _ in surviving)
    full_prompt = _dedupe_prompt_phrases(full_prompt)
    return _trim_prompt(full_prompt, max_words=max_words)


def _trim_negative_prompt(negative_prompt: str, max_words: int = 24) -> str:
    words = (negative_prompt or "").split()
    return " ".join(words[:max_words])


def _merge_negative_prompt(base: str, extra: str, max_words: int = 30) -> str:
    text = ", ".join(p.strip(" ,") for p in (base, extra) if p and p.strip())
    seen = set()
    terms = []
    for term in [t.strip() for t in text.split(",") if t.strip()]:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(term)
    return _trim_negative_prompt(", ".join(terms), max_words=max_words)


def _estimate_clip_tokens(text: str) -> int:
    # Approximation for SDXL CLIP token budget warning.
    # Real tokenization differs, but this is enough to flag risky prompts.
    chunks = re.findall(r"[A-Za-z0-9]+|[^\w\s]", text or "")
    return len(chunks)


async def _clip_score_image(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    image_bytes: bytes,
    text: str,
) -> Optional[float]:
    """Best-effort CLIP alignment score from image server (/clip-score).

    Returns:
      - float score when endpoint exists and succeeds
      - None when disabled/unavailable/error (do not block saving)
    """
    if not IMAGE_CLIP_VALIDATE_ENABLE:
        return None
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return None
    t = (text or "").strip()
    if not t or not image_bytes:
        return None
    try:
        payload = {
            "text": t[:600],
            "image_b64": base64.b64encode(image_bytes).decode("ascii"),
        }
        r = await client.post(
            f"{base}/clip-score",
            json=payload,
            timeout=httpx.Timeout(IMAGE_CLIP_SCORE_TIMEOUT_SEC, connect=5.0),
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if not isinstance(data, dict):
            return None
        score = data.get("score")
        return float(score) if isinstance(score, (int, float)) else None
    except Exception:
        return None


def _extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    t = (text or "").strip()
    if not t:
        return None
    decoder = json.JSONDecoder()
    for i, ch in enumerate(t):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(t, i)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _slide_context_for_vlm(slide: Dict[str, Any], semantic: Dict[str, Any]) -> str:
    title = str(slide.get("title") or "").strip()
    bullets = slide.get("bullets") or slide.get("content") or []
    bullet_lines: List[str] = []
    if isinstance(bullets, list):
        bullet_lines = [str(b).strip() for b in bullets[:4] if str(b).strip()]
    elif isinstance(bullets, str) and bullets.strip():
        bullet_lines = [bullets.strip()]
    lines = [f"Title: {title}"]
    if bullet_lines:
        lines.append("Bullets:")
        lines.extend(f"- {b}" for b in bullet_lines)
    lines.append(f"Semantic content_type: {semantic.get('content_type') or 'normal'}")
    lines.append(f"Semantic topic: {semantic.get('main_topic') or title}")
    return "\n".join(lines).strip()


async def _vlm_judge_image(
    client: httpx.AsyncClient,
    *,
    image_bytes: bytes,
    prompt: str,
    slide: Dict[str, Any],
    semantic: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not IMAGE_VLM_JUDGE_ENABLE:
        return None
    if not GEMINI_API_KEY:
        return None
    model = (IMAGE_VLM_JUDGE_MODEL or "").strip()
    if not model:
        return None
    context = _slide_context_for_vlm(slide, semantic)
    instruction = (
        "You are an image quality and semantic fidelity judge for presentation slides.\n"
        "Score from 0..1 and return strict JSON only with keys:\n"
        "{"
        "\"relevance_score\": number, "
        "\"artifact_score\": number, "
        "\"style_match_score\": number, "
        "\"reasons\": [string], "
        "\"pass\": boolean"
        "}.\n"
        "pass=true only if relevance is high and visual artifacts are acceptable."
    )
    user_text = (
        f"Slide context:\n{context}\n\n"
        f"Generation prompt:\n{(prompt or '')[:700]}\n\n"
        "Judge the attached image."
    )
    payload: Dict[str, Any] = {
        "contents": [
            {
                "parts": [
                    {"text": instruction},
                    {"text": user_text},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "topP": 0.8,
            "maxOutputTokens": 320,
        },
    }
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )
    try:
        resp = await client.post(
            url,
            json=payload,
            timeout=httpx.Timeout(float(IMAGE_VLM_JUDGE_TIMEOUT_SEC), connect=10.0),
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        txt = "\n".join(str((p or {}).get("text") or "") for p in parts).strip()
        parsed = _extract_first_json_object(txt)
        if not isinstance(parsed, dict):
            return None
        relevance = float(parsed.get("relevance_score") or 0.0)
        artifact = float(parsed.get("artifact_score") or 1.0)
        style = float(parsed.get("style_match_score") or 0.0)
        reasons = parsed.get("reasons") if isinstance(parsed.get("reasons"), list) else []
        severe_failure = _vlm_has_severe_failure([str(r) for r in reasons[:5]])
        strict_pass = (
            relevance >= float(IMAGE_VLM_JUDGE_MIN_RELEVANCE)
            and artifact <= float(IMAGE_VLM_JUDGE_MAX_ARTIFACT)
            and not severe_failure
        )
        passed = strict_pass
        return {
            "relevance_score": round(relevance, 3),
            "artifact_score": round(artifact, 3),
            "style_match_score": round(style, 3),
            "reasons": [str(r) for r in reasons[:5]],
            "pass": bool(passed),
            "acceptance_rule": "strict" if strict_pass else "reject",
            "severe_failure": bool(severe_failure),
            "model": model,
        }
    except Exception:
        return None


_GENERIC_TERMS = {
    "introduction", "intro", "overview", "agenda", "outline", "summary", "conclusion",
    "topic", "subject", "concept", "definition", "background", "context", "objective",
    "purpose", "scope", "method", "approach", "result", "discussion", "example",
    "title", "slide", "presentation", "section", "chapter", "part", "report",
    "gioi", "thieu", "tong", "quan", "noi", "dung", "ket", "luan", "muc", "tieu",
    "khai", "niem", "dinh", "nghia", "chu", "de", "phan", "chuong", "trinh", "bay",
    "tom", "tat", "vi", "du", "ban", "chat", "dac", "diem",
    "giới", "thiệu", "tổng", "quán", "nội", "dùng", "kết", "luận", "mục", "tiêu",
    "khái", "niệm", "định", "nghĩa", "chủ", "đề", "phần", "chương", "trình", "bày",
    "tóm", "tắt", "ví", "dụ", "bản", "chất", "đặc", "điểm",
}

_STOPWORDS = {
    "the", "and", "for", "with", "about", "into", "from", "that", "this",
    "have", "has", "are", "was", "were", "will", "shall", "can", "may", "might",
    "more", "most", "less", "very", "much", "many", "some", "other", "another",
    "what", "when", "where", "which", "who", "how", "why",
    "cua", "cho", "voi", "cac", "nhung", "mot", "trong", "ngoai", "khi", "neu",
    "nhu", "den", "tu", "ve", "tren", "duoi", "boi", "bang", "qua", "lai", "se",
    "đã", "sẽ", "đang", "được", "phải", "có", "không", "là", "và", "hay",
    "của", "cho", "với", "các", "những", "một", "trong", "ngoài", "khi", "nếu",
}


def _meaningful_terms(text: str, limit: int = 6, keep_generic: bool = False) -> List[str]:
    words = re.findall(r"[\wÀ-ỹ-]+", (text or "").lower(), flags=re.UNICODE)
    terms = []
    for word in words:
        cleaned = word.strip("-_")
        if len(cleaned) < 3 or cleaned.isdigit():
            continue
        if cleaned in _STOPWORDS:
            continue
        if not keep_generic and cleaned in _GENERIC_TERMS:
            continue
        if cleaned not in terms:
            terms.append(cleaned)
        if len(terms) >= limit:
            break
    return terms


def _semantic_anchors(semantic: Dict[str, Any], slide: Dict[str, Any]) -> List[str]:
    """Build content anchors with priority: entities > topic tail > visual objects > bullet nouns > deck title.

    Anchors are the *must-appear* concepts that bind a prompt to slide content.
    Generic words (overview, introduction, ...) are filtered out by default.

    For very short slides (few bullets, few words), fall back to deck title terms
    so anchors never collapse to a single word.
    """
    anchors: List[str] = []

    for entity in _semantic_list(semantic.get("entities"))[:2]:
        cleaned = str(entity or "").strip()
        if cleaned and len(cleaned) >= 3 and cleaned not in anchors:
            anchors.append(cleaned)

    topic = str(semantic.get("main_topic") or slide.get("title") or "").strip()
    topic_terms = _meaningful_terms(topic, limit=6)
    for term in topic_terms[-3:]:
        if term not in anchors:
            anchors.append(term)

    for obj in _semantic_list(semantic.get("visual_objects"))[:2]:
        for term in _meaningful_terms(obj, limit=2):
            if term not in anchors:
                anchors.append(term)

    if len(anchors) < 2:
        bullets = slide.get("bullets") or slide.get("content") or []
        if isinstance(bullets, list):
            bullet_text = " ".join(str(b) for b in bullets[:2])
        else:
            bullet_text = str(bullets or "")
        for term in _meaningful_terms(bullet_text, limit=4):
            if term not in anchors:
                anchors.append(term)
            if len(anchors) >= 4:
                break

    if len(anchors) < 2:
        deck_title = str(slide.get("_deck_title") or "").strip()
        if deck_title:
            for term in _meaningful_terms(deck_title, limit=4):
                if term not in anchors:
                    anchors.append(term)
                if len(anchors) >= 3:
                    break

    return anchors[:6]


def _scoreable_anchors(anchors: List[str]) -> List[str]:
    """Coverage check should only consider anchors SDXL can read (English/ASCII).

    Vietnamese anchors are intentionally excluded from prompt scoring because
    they cannot survive in the prompt (we filter VN tokens from the prompt
    itself) and would produce false-negative coverage failures.
    """
    ascii_anchors = [a for a in anchors if _is_mostly_ascii(str(a))]
    return ascii_anchors if ascii_anchors else anchors


def _score_prompt_quality(prompt: str, anchors: List[str]) -> float:
    scoreable = _scoreable_anchors(anchors)
    if not scoreable:
        return 1.0
    prompt_l = (prompt or "").lower()
    hits = 0
    for anchor in scoreable:
        terms = _meaningful_terms(anchor, limit=4) or [str(anchor).lower()]
        if any(term in prompt_l for term in terms):
            hits += 1
    return round(hits / max(1, len(scoreable)), 3)


def _coverage_threshold(content_type: str) -> float:
    return _COVERAGE_THRESHOLD.get(content_type, 0.5)


def _missed_anchors(prompt: str, anchors: List[str]) -> List[str]:
    prompt_l = (prompt or "").lower()
    missed: List[str] = []
    for anchor in _scoreable_anchors(anchors):
        terms = _meaningful_terms(anchor, limit=4) or [str(anchor).lower()]
        if not any(term in prompt_l for term in terms):
            missed.append(anchor)
    return missed


def _is_mostly_ascii(text: str) -> bool:
    """SDXL/CLIP only understand latin tokens well; reject any string that
    contains Vietnamese diacritics or other non-ASCII letters.

    Numbers, spaces, dashes and a few common punctuation chars are allowed
    (so "UNFCCC 1992" or "CO2/CH4" still pass) but a single accented letter
    like 'á', 'đ' is enough to disqualify the string.
    """
    s = str(text or "").strip()
    if not s:
        return False
    for ch in s:
        if ch.isalpha() and not ("a" <= ch.lower() <= "z"):
            return False
    return any(("a" <= ch.lower() <= "z") for ch in s)


# Pattern-based detector: nhóm đặc trưng thay vì liệt kê từng cụm.
# Bắt được biến thể chưa xuất hiện mà không cần thêm tay.
_METAPHOR_VISUAL_RE = re.compile(
    r"(?i)"
    # Nhóm 1: Explicit abstract label — "abstract X", "concept of X", "notion of X"
    r"\babstract\s+\w+"
    r"|\b(?:concept|notion|idea|principle|philosophy|ideology|paradigm)\b"
    # Nhóm 2: Standalone single-word metaphors LLM hay đề xuất.
    # Dùng ^ / $ hoặc word-boundary để không chặn cụm cụ thể hơn
    # (vd. "harmony hotel" không bị chặn vì "hotel" theo sau).
    r"|^(?:balance|harmony|synergy|equilibrium|imbalance|flow|cycle"
    r"|unity|diversity|integration|transformation|evolution|revolution"
    r"|innovation|alignment|momentum|resilience|sustainability"
    r"|empowerment|disruption|ecosystem|globalization|interconnection)$"
    # Nhóm 3: Planetary / cosmic symbol khi là chủ thể chính
    r"|\bthe\s+(?:world|earth|globe|planet|universe|society|humanity|civilization)\b"
    r"|^(?:the\s+)?(?:world|earth|globe|planet)$"
    # Nhóm 4: "X of Y" process metaphor — "cycle of life", "flow of information"
    r"|\b(?:cycle|flow|web|wheel|fabric|thread|tapestry)\s+of\b"
    # Nhóm 5: "global/universal + abstract noun" — "global initiative", "universal value"
    r"|\b(?:global|universal)\s+(?:initiative|concept|approach|movement|vision|mission)\b"
    # Nhóm 6: Scale / balance imagery (renders as weighing scale off-topic)
    r"|\bscales?\s+of\b|\bbalance\s+scale\b",
)


def _is_metaphor_visual(text: str) -> bool:
    """Detect abstract / metaphor terms LLMs propose as visual_objects.

    These terms render literally in SDXL (e.g. 'balance scale' -> a real
    weighing scale prop, 'harmony' -> unclear rendering) and pull the image
    away from the actual slide topic.

    Uses pattern groups instead of an enumerated list so it generalises to
    unseen LLM outputs without manual additions.
    """
    s = str(text or "").strip()
    if not s:
        return False
    return bool(_METAPHOR_VISUAL_RE.search(s))


def _anchor_phrase(anchors: List[str], top_n: int = 3) -> str:
    """Build the head anchor phrase using English-friendly tokens only.

    If no English anchor exists (e.g. a fully Vietnamese slide where the LLM
    failed to translate entities), return an empty string. The prompt builder
    then falls back to a scene-only head, which is preferable to leaking
    Vietnamese tokens that SDXL/CLIP cannot interpret.
    """
    ascii_anchors = [str(a).strip() for a in anchors if str(a).strip() and _is_mostly_ascii(str(a))]
    return ", ".join(ascii_anchors[:top_n])


# Các cụm PHẢI luôn có mặt trong negative prompt — đặt trước để không bị trim cắt.
# Chứa những cụm SDXL hay sinh nhất khi không được cấm rõ ràng.
_CORE_NEGATIVE_TERMS = (
    "text, typography, letters, words, watermark, logo, "
    "infographic, diagram, chart, graph, "
    "powerpoint slide, screenshot, UI interface, whiteboard, "
    "blurry, low quality, bad anatomy"
)


def _max_words_for_model() -> int:
    """Word budget cho prompt gửi vào SDXL/FLUX.

    SDXL CLIP hỗ trợ 77 tokens (≈ ~55-65 words thông thường).
    Trước đây giới hạn 32 words khiến nhiều chi tiết scene bị drop.
    Tăng lên 50 để tận dụng tốt hơn budget CLIP còn lại sau phần anchor.
    """
    model_type = (IMAGE_MODEL_TYPE or "").strip().lower()
    return 50 if model_type == "sdxl" else 60


def _enforce_anchor_coverage(
    prompt: str,
    semantic: Dict[str, Any],
    slide: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    """Enforce that the final prompt contains required content anchors.

    Strategy:
    1. Compute anchors and initial coverage score.
    2. If coverage below per-content-type threshold, prepend anchors at the front
       (anchor-lock) so they survive CLIP truncation.
    3. Single retry only: if still below threshold, build a strict template that
       guarantees anchors are present, then trim.
    """
    anchors = _semantic_anchors(semantic, slide)
    content_type = str(semantic.get("content_type") or "normal")
    threshold = _coverage_threshold(content_type)
    max_words = _max_words_for_model()

    score_before = _score_prompt_quality(prompt, anchors)
    reinforced = prompt
    reinforced_step = "none"

    if anchors and score_before < threshold:
        phrase = _anchor_phrase(anchors, top_n=3)
        prompt_head = (prompt or "")[:120].lower()
        already_in_head = bool(phrase) and all(
            part.strip().lower() in prompt_head
            for part in phrase.split(",")
            if part.strip()
        )
        if phrase and not already_in_head:
            reinforced = f"photo of {phrase}, {prompt}"
            reinforced_step = "anchor_lock_prefix"
    reinforced = _trim_prompt(reinforced, max_words=max_words)
    score_mid = _score_prompt_quality(reinforced, anchors)

    fallback_refined = False
    if anchors and score_mid < threshold:
        phrase = _anchor_phrase(anchors, top_n=6)
        if phrase:
            strict = f"photo of {phrase}, {reinforced}"
            reinforced = _trim_prompt(strict, max_words=max_words)
            score_mid = _score_prompt_quality(reinforced, anchors)
            fallback_refined = True
            reinforced_step = "anchor_force_prepend"

    score_after = _score_prompt_quality(reinforced, anchors)
    coverage_ok = (not anchors) or score_after >= threshold
    return reinforced, {
        "anchors": anchors,
        "missed_anchors": _missed_anchors(reinforced, anchors),
        "threshold": threshold,
        "score_before": score_before,
        "score_after": score_after,
        "reinforced": reinforced_step != "none",
        "reinforced_step": reinforced_step,
        "fallback_refined": fallback_refined,
        "coverage_ok": coverage_ok,
        "content_type": content_type,
    }


_reinforce_prompt_with_semantic = _enforce_anchor_coverage


def _simplify_prompt_for_retry(
    semantic: Dict[str, Any],
    slide: Dict[str, Any],
    content_type: str,
) -> str:
    """Build a short, anchor-focused prompt used for retry after a generation failure.

    Goals:
    - Keep only the most essential anchors + content-type required cues.
    - Drop perspective/style/emotion noise so the model focuses on the subject.
    - Stay well under CLIP budget (target ~35 words).
    """
    anchors = _semantic_anchors(semantic, slide)
    phrase = _anchor_phrase(anchors, top_n=2) or str(slide.get("title") or "the topic").strip()
    policy = _visual_policy(content_type)
    required = (policy.get("required") or "concrete subject, real-world setting").strip(", ")
    parts = [
        f"photo of {phrase}",
        required,
        "natural human interaction",
        "realistic, no text",
    ]
    simplified = ", ".join(p for p in parts if p)
    return _trim_prompt(simplified, max_words=35)


def _build_prompt(
    llm_scene: str,
    slide: Dict[str, Any],
    slide_type: str,
    content_type: str,
    idx: int,
    semantic: Dict[str, str],
    domain: str,
) -> str:
    """Build a prompt where mandatory anchors are LOCKED at the front.

    Order: anchors -> camera + scene -> composition -> mood/style -> tail.
    If CLIP truncates, anchors and core scene survive; only style is dropped.
    """
    semantic_scene = _scene_from_semantic(semantic)
    llm_sanitized = _sanitize_scene(llm_scene)
    scene = _sanitize_scene(f"{llm_sanitized}, {semantic_scene}") if llm_sanitized else _sanitize_scene(semantic_scene)
    scene = _sanitize_scene(
        _override_scene_by_content_type(
            content_type,
            str(slide.get("title") or ""),
            _semantic_context(slide, max_chars=700),
            semantic,
            scene,
        )
    )
    scene = _normalize_brand_terms(scene)
    if len(scene) < _MIN_SCENE_CHARS:
        fallback_scene = _sanitize_scene(_semantic_context(slide, max_chars=180))
        scene = (
            fallback_scene
            if len(fallback_scene) >= _MIN_SCENE_CHARS
            else f"people interacting about {slide.get('title', 'business topic')} in real environment"
        )

    visual_objects_list = [
        str(v).strip() for v in _semantic_list(semantic.get("visual_objects"))[:3]
        if str(v).strip() and _is_mostly_ascii(str(v)) and not _is_metaphor_visual(str(v))
    ]
    has_strong_visual_objects = bool(visual_objects_list)

    if content_type == "normal" and not has_strong_visual_objects:
        domain_object = _DOMAIN_OBJECT_HINTS.get(domain, _DOMAIN_OBJECT_HINTS["general"])
        scene = f"{scene}, {domain_object}"

    anchors = _semantic_anchors(semantic, slide)
    anchor_prefix = _anchor_phrase(anchors, top_n=2)

    visual_objects_phrase = ", ".join(v.lower() for v in visual_objects_list)
    if visual_objects_phrase:
        scene_lower = scene.lower()
        if not any(v in scene_lower for v in visual_objects_phrase.split(", ")):
            scene = f"{scene}, featuring {visual_objects_phrase}"

    risk = _classify_risk(slide, semantic, content_type)
    risk_style = _risk_style_override(risk)

    composition = _SLIDE_TYPE_HINTS.get(slide_type, _SLIDE_TYPE_HINTS["default"])
    if risk_style:
        style = _truncate_at_word(risk_style, 130)
    else:
        style = _truncate_at_word((IMAGE_STYLE_LOCKED or "").strip().strip(","), 90)
    suffix = _truncate_at_word((IMAGE_PROMPT_SUFFIX or "").strip().strip(","), 70)
    camera_map = {
        "intro": "wide angle shot",
        "data": "over-the-shoulder shot",
        "process": "close-up action shot",
        "default": "medium shot",
    }
    camera = camera_map.get(slide_type, "medium shot")
    perspective_map = (
        "front-facing composition",
        "over-the-shoulder composition",
        "side-angle composition",
    )
    perspective = perspective_map[idx % len(perspective_map)]
    semantic_detail = _ACTION_DETAIL_MAP.get(semantic.get("action", "default"), _ACTION_DETAIL_MAP["default"])
    detected_emotion = _detect_emotion(_semantic_context(slide, max_chars=400))
    emotion = (
        _EMOTION_MAP.get(detected_emotion)
        if detected_emotion and detected_emotion in _EMOTION_MAP
        else _EMOTION_MAP.get(content_type, _EMOTION_MAP.get(slide_type, _EMOTION_MAP["default"]))
    )
    policy = _visual_policy(content_type)

    strong_anchors = bool(anchor_prefix) and len(anchors) >= 2
    no_text_phrase = "no text" if risk_style else "realistic, no text"

    prioritized: List[tuple[str, int]] = []
    if risk_style:
        head_phrase = f"illustration of {anchor_prefix}" if anchor_prefix else f"illustration of {scene}"
        prioritized.append((head_phrase, 1))
        if anchor_prefix:
            prioritized.append((scene, 1))
    elif anchor_prefix:
        prioritized.append((f"photo of {anchor_prefix}", 1))
        prioritized.append((scene, 1))
    else:
        prioritized.append((f"{camera} photo of {scene}", 1))

    prioritized.append((policy["required"], 2))
    prioritized.append((policy["composition"], 3))
    prioritized.append((composition, 3))
    prioritized.append((semantic_detail, 4))
    prioritized.append((perspective, 5))
    prioritized.append((emotion, 6))
    if not risk_style and not strong_anchors:
        prioritized.append(("natural human interaction", 7))
        prioritized.append(("real-world situation", 7))
    elif not risk_style and strong_anchors:
        prioritized.append(("clear focus on the subject", 7))
    if style:
        prioritized.append((style, 8))
    if suffix:
        prioritized.append((suffix, 9))
    prioritized.append((no_text_phrase, 1))

    return _assemble_prioritized_prompt(prioritized, max_words=_max_words_for_model())


def _normalize_slide_content(slide: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize paragraph-like content into concise bullet list for image prompting."""
    if not isinstance(slide, dict):
        return {}
    normalized = dict(slide)
    bullets = normalized.get("bullets")
    content = normalized.get("content")
    if bullets:
        return normalized
    if isinstance(content, str):
        parts = re.split(r"[.!?;]\s+|\n+", content)
        normalized["bullets"] = [p.strip() for p in parts if len(p.strip()) > 10][:4]
    elif isinstance(content, list):
        normalized["bullets"] = [str(x).strip() for x in content if str(x).strip()][:4]
    return normalized


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
    return [q for q in queries if q and len(q.split()) >= 2]


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
) -> Optional[Dict[str, Any]]:
    if not STOCK_PHOTO_ENABLE:
        return None
    return await fetch_external_image(
        client,
        queries=_stock_photo_queries(slide, semantic, content_type, risk),
        providers=_stock_photo_providers(content_type, risk),
        pexels_api_key=PEXELS_API_KEY,
    )


async def _get_image_semantic(content_extractor, slide: Dict[str, Any]) -> Dict[str, Any]:
    fallback = _extract_semantic(slide)
    if not hasattr(content_extractor, "extract_image_semantic"):
        return fallback
    try:
        raw = await content_extractor.extract_image_semantic(
            {"context": _slide_prompt_context(slide, max_chars=900), "slide": slide}
        )
        semantic = _normalize_llm_semantic(raw, fallback)
        print(
            "[slide_images] semantic "
            f"source={semantic.get('source')} confidence={semantic.get('confidence')} "
            f"type={semantic.get('content_type')} topic={str(semantic.get('main_topic'))[:80]}"
        )
        return semantic
    except Exception as e:
        print(f"[slide_images] semantic error: {e}")
        return fallback


_SCENE_BAD_PATTERNS = [
    re.compile(r"\b(?:with|around|on|in|at|to|near|by)\s+a\s*(?:,|\.|$)", re.IGNORECASE),
    re.compile(r"\b(?:a|the)\s+(?:discussing|reviewing|showing|using|holding|examining)\b", re.IGNORECASE),
    re.compile(r"\bwith\s+a\s+filled\s+with\b", re.IGNORECASE),
    re.compile(r",\s*,", re.IGNORECASE),
]


def _scene_looks_broken(scene: str) -> bool:
    """Detect obviously broken or too-generic scene text from the LLM."""
    text = (scene or "").strip()
    if len(text) < 30:
        return True
    word_count = len(text.split())
    if word_count < 6:
        return True
    for pat in _SCENE_BAD_PATTERNS:
        if pat.search(text):
            return True
    return False


def _build_deck_context(slides: List[Any], idx: int, deck_title: str) -> str:
    """Build a short context string from deck title + adjacent slides.

    Giúp LLM hiểu presentation tổng thể là về chủ đề gì và slide này
    nằm ở vị trí nào trong luồng nội dung, tránh sinh scene trùng lặp
    hoặc quá chung chung khi chỉ nhìn 1 slide đơn lẻ.
    """
    parts: List[str] = []
    if deck_title:
        parts.append(f"Presentation title: {deck_title}")
    if idx > 0:
        prev = slides[idx - 1]
        if isinstance(prev, dict):
            prev_title = str(prev.get("title") or "").strip()
            prev_bullets = prev.get("bullets") or prev.get("content") or []
            prev_first = (
                str(prev_bullets[0]).strip()
                if isinstance(prev_bullets, list) and prev_bullets
                else ""
            )
            if prev_title:
                parts.append(
                    f"Previous slide: {prev_title}"
                    + (f" — {prev_first[:80]}" if prev_first else "")
                )
    if idx < len(slides) - 1:
        nxt = slides[idx + 1]
        if isinstance(nxt, dict):
            nxt_title = str(nxt.get("title") or "").strip()
            nxt_bullets = nxt.get("bullets") or nxt.get("content") or []
            nxt_first = (
                str(nxt_bullets[0]).strip()
                if isinstance(nxt_bullets, list) and nxt_bullets
                else ""
            )
            if nxt_title:
                parts.append(
                    f"Next slide: {nxt_title}"
                    + (f" — {nxt_first[:80]}" if nxt_first else "")
                )
    return "\n".join(parts)


def _vlm_reasons_to_negative(reasons: List[str]) -> str:
    """Chuyển đổi lý do reject từ VLM judge thành cụm negative prompt.

    Dùng để strengthen negative prompt ở những attempt retry tiếp theo,
    giúp SDXL tránh lặp lại đúng lỗi đã được Gemini phát hiện.
    Ví dụ: 'image shows a whiteboard with text' → 'whiteboard, text, writing'
    """
    if not reasons:
        return ""
    combined = " ".join(str(r) for r in reasons).lower()
    neg_terms: List[str] = []
    if any(k in combined for k in ("text", "writing", "letter", "word", "caption", "label", "typography")):
        neg_terms.append("text, writing, letters, caption")
    if any(k in combined for k in ("whiteboard", "blackboard", "chalkboard", "board with")):
        neg_terms.append("whiteboard, blackboard, chalkboard")
    if any(k in combined for k in ("diagram", "chart", "infographic", "graph", "flowchart", "mindmap")):
        neg_terms.append("diagram, chart, infographic, flowchart")
    if any(k in combined for k in ("slide", "powerpoint", "presentation layout", "split panel")):
        neg_terms.append("powerpoint slide, presentation split layout")
    if any(k in combined for k in ("screenshot", "ui ", "interface", "mockup", "dashboard")):
        neg_terms.append("screenshot, UI interface, dashboard mockup")
    if any(k in combined for k in ("blurry", "blur", "low quality", "poor quality", "out of focus")):
        neg_terms.append("blurry, low quality, out of focus")
    if any(k in combined for k in ("artifact", "distort", "deform", "malform", "glitch")):
        neg_terms.append("distorted, artifact, deformed, glitchy")
    if any(k in combined for k in ("hand", "finger", "fingers", "anatomy", "anatomical")):
        neg_terms.append("bad hands, malformed fingers, fused fingers, extra fingers")
    if any(k in combined for k in ("keyboard", "trackpad", "laptop surface")):
        neg_terms.append("broken keyboard, distorted laptop, malformed device")
    if any(k in combined for k in ("generic", "stock photo pose", "artificial light", "studio backdrop")):
        neg_terms.append("generic stock pose, artificial studio lighting")
    if any(k in combined for k in ("irrelevant", "unrelated", "wrong subject", "off topic", "not related")):
        neg_terms.append("mismatched subject, unrelated scene")
    return ", ".join(neg_terms)


def _vlm_has_severe_failure(reasons: List[str]) -> bool:
    """Return true for failures that should reject even high-relevance images.

    Gemini often assigns high artifact scores for small SDXL issues such as
    fingers or a soft keyboard while still saying the image is suitable. Those
    should not force a fallback. Severe mismatches, text-heavy images, broken
    anatomy, and unreadable/corrupt outputs still reject.
    """
    combined = " ".join(str(r) for r in reasons or []).lower()
    combined = re.sub(
        r"\b(?:no|without|does not show|doesn't show|avoids?)\s+"
        r"(?:text|diagram|diagrams|infographic|infographics|logo|watermark|screenshot)s?\b",
        " ",
        combined,
    )
    severe_terms = (
        "unrelated",
        "wrong subject",
        "off topic",
        "not related",
        "does not match",
        "irrelevant",
        "text dominates",
        "large text",
        "prominent text",
        "watermark",
        "logo",
        "caption",
        "diagram",
        "infographic",
        "flowchart",
        "screenshot",
        "ui interface",
        "severe",
        "major artifact",
        "significant artifact",
        "heavily distorted",
        "unusable",
        "unreadable",
        "corrupt",
        "multiple faces distorted",
        "extra limbs",
        "missing limb",
    )
    return any(term in combined for term in severe_terms)


def _build_scene_system_prompt(
    slide: Dict[str, Any],
    domain: str,
    semantic: Dict[str, Any],
    context: str,
    *,
    strict: bool = False,
    deck_context: str = "",
) -> str:
    base = (
        _SCENE_SYSTEM_PROMPT
        + f"\n\nDomain hint: {domain}"
        + f"\nRequired domain object: {_DOMAIN_OBJECT_HINTS.get(domain, _DOMAIN_OBJECT_HINTS['general'])}"
        + (
            f"\nSemantic core: action={semantic['action']}, "
            f"object={semantic['object']}, context={semantic['context']}"
        )
        + f"\nContent type: {semantic.get('content_type', 'normal')}"
        + f"\nNamed entities: {', '.join(_semantic_list(semantic.get('entities'))[:3]) or 'none'}"
        + (f"\n\nPresentation context (for coherence — do NOT copy, just use for tone):\n{deck_context}" if deck_context else "")
        + f"\n\nSlide content:\n{context}"
    )
    if strict:
        base += (
            "\n\nSTRICT REQUIREMENTS:"
            "\n- Write ONE complete English sentence, 18-30 words."
            "\n- Mention at least 2 concrete nouns (people, tools, place)."
            "\n- Never end with 'a', 'the', 'an', 'with', 'around', 'in'."
            "\n- Avoid the words: discussing, reviewing, showing alone (must follow a subject)."
            "\n- No bullet points, no commas-only fragments, no truncated phrases."
        )
    return base


async def _get_llm_scene(
    content_extractor,
    slide: Dict[str, Any],
    domain: str,
    semantic: Dict[str, Any],
    deck_context: str = "",
) -> str:
    try:
        context = _slide_prompt_context(slide, max_chars=900)
        if hasattr(content_extractor, "extract_image_scene"):
            scene_input = {
                "context": context,
                "slide": slide,
                "domain": domain,
                "domain_object": _DOMAIN_OBJECT_HINTS.get(domain, _DOMAIN_OBJECT_HINTS["general"]),
                "semantic": semantic,
                "deck_context": deck_context,
            }
            scene = await content_extractor.extract_image_scene(
                scene_input,
                system_prompt=_build_scene_system_prompt(
                    slide, domain, semantic, context,
                    strict=False, deck_context=deck_context,
                ),
            )
            if _scene_looks_broken(scene):
                print(f"[slide_images] scene looks broken, regenerating once: {str(scene)[:140]}")
                try:
                    scene2 = await content_extractor.extract_image_scene(
                        scene_input,
                        system_prompt=_build_scene_system_prompt(
                            slide, domain, semantic, context,
                            strict=True, deck_context=deck_context,
                        ),
                    )
                    if not _scene_looks_broken(scene2):
                        scene = scene2
                except Exception as e:
                    print(f"[slide_images] scene regenerate error: {e}")
            print(f"[slide_images] raw scene: {str(scene)[:220]}")
            return scene
        scene = await content_extractor.extract_keywords_for_image(slide)
        print(f"[slide_images] raw scene(fallback): {str(scene)[:220]}")
        return scene
    except Exception as e:
        print(f"[slide_images] LLM scene error: {e}")
        return ""


def _scene_candidate_count(content_type: str, risk: Optional[str]) -> int:
    """Use more than one scene only where it is likely to help."""
    if risk in {"person_protected", "religious"}:
        return 1
    if content_type in {"historical", "comparison", "definition", "normal", "process"}:
        return 2
    return 1


async def _select_best_scene(
    content_extractor,
    slide: Dict[str, Any],
    slide_type: str,
    content_type: str,
    idx: int,
    semantic: Dict[str, Any],
    domain: str,
    risk: Optional[str],
    deck_context: str = "",
) -> tuple[str, List[Dict[str, Any]], Optional[str]]:
    """Generate 1-2 scene candidates and choose the prompt with best anchor coverage."""
    candidate_count = _scene_candidate_count(content_type, risk)
    candidates: List[Dict[str, Any]] = []
    best_scene = ""
    best_prompt = ""
    best_quality: Optional[Dict[str, Any]] = None
    alternate_prompt: Optional[str] = None

    for candidate_idx in range(candidate_count):
        scene = await _get_llm_scene(content_extractor, slide, domain, semantic, deck_context=deck_context)
        prompt = _build_prompt(scene, slide, slide_type, content_type, idx, semantic, domain)
        prompt, quality = _enforce_anchor_coverage(prompt, semantic, slide)
        record = {
            "scene": str(scene or "")[:500],
            "prompt": prompt,
            "prompt_quality": quality,
            "candidate_index": candidate_idx,
        }
        candidates.append(record)

        score = float(quality.get("score_after") or 0.0)
        best_score = float((best_quality or {}).get("score_after") or -1.0)
        if best_quality is None or score > best_score or (
            score == best_score and len(prompt) < len(best_prompt)
        ):
            if best_prompt:
                alternate_prompt = best_prompt
            best_scene = scene
            best_prompt = prompt
            best_quality = quality
        elif not alternate_prompt:
            alternate_prompt = prompt

    return best_scene, candidates, alternate_prompt


async def build_image_paths_for_slides(
    content_extractor,
    structured: Dict[str, Any],
    task_id: str,
    *,
    chart_specs: Optional[Dict[int, Dict[str, Any]]] = None,
    table_specs: Optional[Dict[int, Dict[str, Any]]] = None,
    progress_cb: Optional[Any] = None,
    should_stop: Optional[Any] = None,
) -> Dict[int, str]:
    base = (IMAGE_GEN_API_BASE_URL or "").strip().rstrip("/")
    if not base:
        print("[slide_images] skip: IMAGE_GEN_API_BASE_URL is empty")
        return {}

    slides = structured.get("slides") or []
    if not slides:
        return {}

    n = min(len(slides), max(1, IMAGE_MAX_SLIDES_WITH_IMAGES))
    print(f"[slide_images] POST {base}/generate - {n} slide(s)")

    out: Dict[int, str] = {}
    debug_records: List[Dict[str, Any]] = []
    headers: Dict[str, str] = {}
    if IMAGE_GEN_API_KEY:
        headers["Authorization"] = f"Bearer {IMAGE_GEN_API_KEY}"

    style_value = (IMAGE_STYLE_LOCKED or "").lower()
    illustration_mode = any(k in style_value for k in ("illustration", "vector", "cartoon", "flat"))
    default_negative = _ILLUSTRATION_NEGATIVE if illustration_mode else _DEFAULT_NEGATIVE
    negative = (IMAGE_NEGATIVE_PROMPT or "").strip() or default_negative
    if (IMAGE_MODEL_TYPE or "").strip().lower() == "flux":
        negative = "text, watermark, logo"
    elif (IMAGE_MODEL_TYPE or "").strip().lower() == "sdxl":
        # Core-first strategy: đặt _CORE_NEGATIVE_TERMS lên đầu đảm bảo
        # chúng không bị trim cắt, rồi append phần còn lại từ negative config.
        # Budget 42 words ≈ ~42 CLIP tokens — an toàn trong giới hạn 77 tokens.
        negative = _merge_negative_prompt(_CORE_NEGATIVE_TERMS, negative, max_words=42)

    timeout = httpx.Timeout(IMAGE_GEN_TIMEOUT_SEC, connect=30.0)
    url = f"{base}/generate"

    deck_title = str(structured.get("title") or "").strip()

    async with httpx.AsyncClient(timeout=timeout) as client:
        for idx in range(n):
            if should_stop is not None and await should_stop():
                break

            slide = _normalize_slide_content(slides[idx])
            if deck_title and not slide.get("_deck_title"):
                slide["_deck_title"] = deck_title
            if table_specs and idx in table_specs:
                print(f"[slide_images] skip image for table slide {idx}")
                debug_records.append(
                    {
                        "slide_index": idx,
                        "title": str(slide.get("title") or ""),
                        "status": "skipped_table_spec_route",
                        "table_spec": table_specs[idx],
                    }
                )
                continue
            if chart_specs and idx in chart_specs:
                print(f"[slide_images] skip image for chart slide {idx}")
                debug_records.append(
                    {
                        "slide_index": idx,
                        "title": str(slide.get("title") or ""),
                        "status": "skipped_chart_spec_route",
                        "chart_spec": chart_specs[idx],
                    }
                )
                continue
            slide_type = _detect_slide_type(slide)
            semantic = await _get_image_semantic(content_extractor, slide)
            content_type = str(semantic.get("content_type") or "normal")
            if content_type == "data":
                print(f"[slide_images] skip image for data slide {idx}")
                debug_records.append(
                    {
                        "slide_index": idx,
                        "title": str(slide.get("title") or ""),
                        "status": "skipped_data_chart_route",
                        "content_type": content_type,
                        "semantic": semantic,
                    }
                )
                continue

            catastrophic = _is_catastrophic_risk(slide)
            if catastrophic:
                print(
                    f"[slide_images] skip image for catastrophic-risk slide {idx} "
                    f"(reason={catastrophic})"
                )
                debug_records.append(
                    {
                        "slide_index": idx,
                        "title": str(slide.get("title") or ""),
                        "status": "skipped_catastrophic_risk",
                        "catastrophic_reason": catastrophic,
                        "content_type": content_type,
                        "semantic": semantic,
                    }
                )
                continue
            domain = str(semantic.get("domain") or "general")
            risk = _classify_risk(slide, semantic, content_type)
            # Build deck context: deck title + adjacent slide titles giúp LLM
            # tạo scene đặc trưng, không trùng lặp, phù hợp vị trí trong luồng.
            deck_ctx = _build_deck_context(
                slides,
                idx,
                deck_title=str(slide.get("_deck_title") or structured.get("title") or ""),
            )
            llm_scene, scene_candidates, alternate_prompt = await _select_best_scene(
                content_extractor,
                slide,
                slide_type,
                content_type,
                idx,
                semantic,
                domain,
                risk,
                deck_context=deck_ctx,
            )
            best_candidate = max(
                scene_candidates or [{"scene": "", "prompt": "", "prompt_quality": {}}],
                key=lambda c: (
                    float((c.get("prompt_quality") or {}).get("score_after") or 0.0),
                    -len(str(c.get("prompt") or "")),
                ),
            )
            llm_scene = str(best_candidate.get("scene") or "")
            full_prompt = str(best_candidate.get("prompt") or "")
            prompt_quality = dict(best_candidate.get("prompt_quality") or {})
            if risk:
                print(
                    f"[slide_images] slide {idx} risk={risk} -> illustration style override"
                )
            if len(scene_candidates) > 1:
                scores = [
                    round(float((c.get("prompt_quality") or {}).get("score_after") or 0.0), 3)
                    for c in scene_candidates
                ]
                print(f"[slide_images] slide {idx} multi-scene scores={scores}")
            policy_negative = _visual_policy(content_type).get("negative", "")
            slide_negative = (
                # Tăng từ 30 → 50 words: policy_negative mang thêm cụm content-type-specific
                # (historical, comparison, process...) quan trọng cho từng loại slide.
                _merge_negative_prompt(negative, policy_negative, max_words=50)
                if (IMAGE_MODEL_TYPE or "").strip().lower() == "sdxl"
                else negative
            )
            est_tokens = _estimate_clip_tokens(full_prompt)
            if (IMAGE_MODEL_TYPE or "").strip().lower() == "sdxl" and est_tokens > 72:
                print(
                    f"[slide_images] slide {idx} token-risk: est_tokens={est_tokens} (>72), "
                    "CLIP may truncate prompt"
                )
            if (IMAGE_MODEL_TYPE or "").strip().lower() == "sdxl":
                neg_tokens = _estimate_clip_tokens(slide_negative or "")
                if neg_tokens > 72:
                    print(
                        f"[slide_images] slide {idx} negative token-risk: est_tokens={neg_tokens} (>72), "
                        "CLIP may truncate negative prompt"
                    )

            coverage_info = (
                f"coverage={prompt_quality.get('score_after')}/"
                f"{prompt_quality.get('threshold')} "
                f"step={prompt_quality.get('reinforced_step')}"
            )
            missed = prompt_quality.get("missed_anchors") or []
            if missed:
                coverage_info += f" missed={missed[:3]}"
            print(
                f"[slide_images] slide {idx} [{slide_type}/{content_type}/{domain}] "
                f"semantic(a/o/c={semantic.get('action')}/{semantic.get('object')}/{semantic.get('context')}) "
                f"{coverage_info} "
                f"prompt ({len(full_prompt)}c, est_tokens={est_tokens}): {full_prompt[:200]}"
            )
            debug_record: Dict[str, Any] = {
                "slide_index": idx,
                "title": str(slide.get("title") or ""),
                "status": "pending",
                "slide_type": slide_type,
                "content_type": content_type,
                "domain": domain,
                "risk": risk,
                "semantic": semantic,
                "raw_scene": str(llm_scene or "")[:500],
                "scene_candidates": scene_candidates,
                "prompt": full_prompt,
                "prompt_quality": prompt_quality,
                "prompt_chars": len(full_prompt),
                "prompt_est_tokens": est_tokens,
                "negative_prompt": slide_negative,
                "negative_est_tokens": _estimate_clip_tokens(slide_negative or ""),
                "model_type": IMAGE_MODEL_TYPE,
                "width": IMAGE_WIDTH,
                "height": IMAGE_HEIGHT,
                "steps": IMAGE_STEPS,
                "guidance_scale": float(IMAGE_GUIDANCE_SCALE),
            }

            base_payload = {
                "width": IMAGE_WIDTH,
                "height": IMAGE_HEIGHT,
                "steps": IMAGE_STEPS,
                "guidance_scale": float(IMAGE_GUIDANCE_SCALE),
                "return_base64": False,
            }

            simplified_prompt = _simplify_prompt_for_retry(semantic, slide, content_type)
            attempts_plan = [
                {
                    "label": "primary",
                    "prompt": full_prompt,
                    "negative": slide_negative,
                },
            ]
            if alternate_prompt and alternate_prompt != full_prompt:
                attempts_plan.append(
                    {
                        "label": "alternate_scene",
                        "prompt": alternate_prompt,
                        "negative": slide_negative,
                    }
                )
            attempts_plan.append(
                {
                    "label": "simplified",
                    "prompt": simplified_prompt,
                    "negative": slide_negative,
                }
            )
            debug_record["attempts"] = []

            dest = IMAGE_DIR / f"{task_id}_{idx}.png"
            saved = False
            last_error: Optional[str] = None
            try:
                for attempt_idx, plan in enumerate(attempts_plan):
                    payload = dict(base_payload)
                    payload["prompt"] = plan["prompt"]
                    if plan["negative"]:
                        payload["negative_prompt"] = plan["negative"]
                    attempt_record: Dict[str, Any] = {
                        "label": plan["label"],
                        "prompt": plan["prompt"],
                        "prompt_chars": len(plan["prompt"]),
                        "prompt_est_tokens": _estimate_clip_tokens(plan["prompt"]),
                    }
                    try:
                        r = await client.post(url, json=payload, headers=headers)
                    except Exception as e:
                        attempt_record["status"] = "exception"
                        attempt_record["error"] = str(e)
                        last_error = str(e)
                        debug_record["attempts"].append(attempt_record)
                        if attempt_idx == 0:
                            print(f"[slide_images] slide {idx} primary failed: {e} -> retry next candidate")
                            continue
                        raise

                    if r.status_code != 200:
                        attempt_record["status"] = "http_error"
                        attempt_record["http_status"] = r.status_code
                        attempt_record["error"] = r.text[:500]
                        last_error = f"HTTP {r.status_code}: {r.text[:120]}"
                        print(f"[slide_images] slide {idx} {plan['label']} HTTP {r.status_code}: {r.text[:200]}")
                        debug_record["attempts"].append(attempt_record)
                        if attempt_idx == 0:
                            continue
                        debug_record["status"] = "http_error"
                        debug_record["http_status"] = r.status_code
                        debug_record["error"] = r.text[:500]
                        break

                    raw = r.content
                    if len(raw) < 8 or not raw.startswith(b"\x89PNG"):
                        ct = (r.headers.get("content-type") or "").lower()
                        attempt_record["status"] = "invalid_png"
                        attempt_record["content_type_header"] = ct
                        attempt_record["response_len"] = len(raw)
                        last_error = f"invalid PNG (type={ct!r}, len={len(raw)})"
                        print(f"[slide_images] slide {idx} {plan['label']}: not PNG (type={ct!r}, len={len(raw)})")
                        debug_record["attempts"].append(attempt_record)
                        if attempt_idx == 0:
                            continue
                        debug_record["status"] = "invalid_png"
                        debug_record["content_type_header"] = ct
                        debug_record["response_len"] = len(raw)
                        break

                    validation = _validate_output_image(raw, prompt_text=plan["prompt"])
                    attempt_record["output_validation"] = validation
                    if not validation.get("ok"):
                        last_error = f"output_validation_failed: {validation.get('reasons')}"
                        print(
                            f"[slide_images] slide {idx} {plan['label']}: output validation failed "
                            f"(reasons={validation.get('reasons')})"
                        )
                        attempt_record["status"] = "output_validation_failed"
                        debug_record["attempts"].append(attempt_record)
                        if attempt_idx < len(attempts_plan) - 1:
                            continue
                        debug_record["status"] = "output_validation_failed"
                        debug_record["output_validation"] = validation
                        break

                    clip_score = await _clip_score_image(
                        client,
                        base_url=base,
                        image_bytes=raw,
                        text=plan["prompt"],
                    )
                    if clip_score is not None:
                        attempt_record["clip_score"] = clip_score
                        attempt_record["clip_min_score"] = float(IMAGE_CLIP_MIN_SCORE)
                        if clip_score < float(IMAGE_CLIP_MIN_SCORE):
                            last_error = f"clip_mismatch: score={clip_score} < {float(IMAGE_CLIP_MIN_SCORE)}"
                            print(
                                f"[slide_images] slide {idx} {plan['label']}: CLIP mismatch "
                                f"(score={clip_score:.3f} < {float(IMAGE_CLIP_MIN_SCORE):.3f})"
                            )
                            attempt_record["status"] = "clip_mismatch"
                            debug_record["attempts"].append(attempt_record)
                            if attempt_idx < len(attempts_plan) - 1:
                                continue
                            debug_record["status"] = "clip_mismatch"
                            debug_record["clip_score"] = clip_score
                            break

                    vlm_judge = await _vlm_judge_image(
                        client,
                        image_bytes=raw,
                        prompt=plan["prompt"],
                        slide=slide,
                        semantic=semantic,
                    )
                    if vlm_judge is not None:
                        attempt_record["vlm_judge"] = vlm_judge
                        if not vlm_judge.get("pass"):
                            last_error = (
                                "vlm_reject: "
                                f"relevance={vlm_judge.get('relevance_score')}, "
                                f"artifact={vlm_judge.get('artifact_score')}"
                            )
                            print(
                                f"[slide_images] slide {idx} {plan['label']}: VLM reject "
                                f"(relevance={vlm_judge.get('relevance_score')}, "
                                f"artifact={vlm_judge.get('artifact_score')})"
                            )
                            attempt_record["status"] = "vlm_reject"
                            debug_record["attempts"].append(attempt_record)
                            if attempt_idx < len(attempts_plan) - 1:
                                # #4 VLM feedback loop: chuyển reasons thành extra
                                # negative prompt cho các attempt retry tiếp theo.
                                vlm_reasons = vlm_judge.get("reasons") or []
                                extra_neg = _vlm_reasons_to_negative(vlm_reasons)
                                if extra_neg:
                                    print(
                                        f"[slide_images] slide {idx} VLM feedback "
                                        f"→ adding to negative: {extra_neg[:120]}"
                                    )
                                    for future_plan in attempts_plan[attempt_idx + 1:]:
                                        future_plan["negative"] = _merge_negative_prompt(
                                            future_plan.get("negative", ""),
                                            extra_neg,
                                            max_words=55,
                                        )
                                continue
                            debug_record["status"] = "vlm_reject"
                            debug_record["vlm_judge"] = vlm_judge
                            break

                    dest.write_bytes(raw)
                    out[idx] = str(dest.resolve())
                    debug_record["status"] = "saved"
                    debug_record["image_path"] = out[idx]
                    debug_record["response_len"] = len(raw)
                    debug_record["output_validation"] = validation
                    if vlm_judge is not None:
                        debug_record["vlm_judge"] = vlm_judge
                    debug_record["used_attempt"] = plan["label"]
                    if attempt_idx > 0:
                        debug_record["used_simplified_retry"] = True
                    attempt_record["status"] = "saved"
                    attempt_record["response_len"] = len(raw)
                    debug_record["attempts"].append(attempt_record)
                    debug_records.append(debug_record)
                    saved = True
                    if plan["label"] != "primary":
                        print(f"[slide_images] slide {idx} saved by retry attempt: {plan['label']}")
                    break
            except Exception as e:
                print(f"[slide_images] slide {idx} error: {e}")
                last_error = str(e)
                debug_record["status"] = "exception"
                debug_record["error"] = str(e)
            if not saved:
                secondary_raw = await _try_secondary_ai_image_fallback(
                    client,
                    prompt=full_prompt,
                    negative_prompt=slide_negative,
                    payload_template=base_payload,
                )
                if secondary_raw:
                    validation = _validate_output_image(secondary_raw, prompt_text=full_prompt)
                    if validation.get("ok"):
                        clip_score = await _clip_score_image(
                            client,
                            base_url=base,
                            image_bytes=secondary_raw,
                            text=full_prompt,
                        )
                        vlm_judge = await _vlm_judge_image(
                            client,
                            image_bytes=secondary_raw,
                            prompt=full_prompt,
                            slide=slide,
                            semantic=semantic,
                        )
                        vlm_pass = vlm_judge is None or bool(vlm_judge.get("pass"))
                        if (clip_score is None or clip_score >= float(IMAGE_CLIP_MIN_SCORE)) and vlm_pass:
                            dest = IMAGE_DIR / f"{task_id}_{idx}_ai_fallback.png"
                            dest.write_bytes(secondary_raw)
                            out[idx] = str(dest.resolve())
                            debug_record["status"] = "saved_ai_fallback"
                            debug_record["image_path"] = out[idx]
                            debug_record["response_len"] = len(secondary_raw)
                            debug_record["ai_fallback_provider"] = "secondary_generate_api"
                            debug_record["ai_fallback_output_validation"] = validation
                            if vlm_judge is not None:
                                debug_record["ai_fallback_vlm_judge"] = vlm_judge
                            if clip_score is not None:
                                debug_record["ai_fallback_clip_score"] = clip_score
                            debug_records.append(debug_record)
                            saved = True
                            print(f"[slide_images] slide {idx} saved via secondary AI fallback")
                        else:
                            if clip_score is not None and clip_score < float(IMAGE_CLIP_MIN_SCORE):
                                print(
                                    f"[slide_images] slide {idx} secondary AI fallback rejected by CLIP "
                                    f"(score={clip_score:.3f} < {float(IMAGE_CLIP_MIN_SCORE):.3f})"
                                )
                            elif vlm_judge is not None and not vlm_judge.get("pass"):
                                print(
                                    f"[slide_images] slide {idx} secondary AI fallback rejected by VLM "
                                    f"(relevance={vlm_judge.get('relevance_score')}, "
                                    f"artifact={vlm_judge.get('artifact_score')})"
                                )
                    else:
                        print(
                            f"[slide_images] slide {idx} secondary AI fallback rejected "
                            f"(reasons={validation.get('reasons')})"
                        )
                else:
                    print(f"[slide_images] slide {idx} secondary AI fallback returned no usable image")
            if not saved:
                external = await _try_stock_photo_fallback(
                    client,
                    slide,
                    semantic,
                    content_type,
                    risk,
                )
                if external:
                    # Stock photo tầng last resort: chỉ kiểm tra ảnh không bị vỡ/đen/trắng.
                    # Không chạy CLIP / VLM judge vì:
                    #   1. prompt so sánh là SDXL prompt — không phù hợp để judge ảnh stock.
                    #   2. Đây là tầng cuối cùng — reject thêm chỉ khiến slide không có ảnh.
                    # Relevance đã được handle ở cấp query (_stock_photo_queries).
                    validation = _validate_output_image(external["bytes"], prompt_text=full_prompt)
                    if not validation.get("ok"):
                        debug_record["external_output_validation"] = validation
                        debug_record["status"] = "external_output_validation_failed"
                        if last_error and not debug_record.get("error"):
                            debug_record["error"] = last_error
                        debug_records.append(debug_record)
                        print(
                            f"[slide_images] slide {idx} external fallback rejected "
                            f"(reasons={validation.get('reasons')})"
                        )
                        saved = False
                        continue
                    ext = str(external.get("extension") or ".jpg")
                    dest = IMAGE_DIR / f"{task_id}_{idx}_external{ext}"
                    dest.write_bytes(external["bytes"])
                    out[idx] = str(dest.resolve())
                    debug_record["status"] = "saved_external_fallback"
                    debug_record["image_path"] = out[idx]
                    debug_record["response_len"] = len(external["bytes"])
                    debug_record["external_source"] = external.get("source")
                    debug_record["external_query"] = external.get("query")
                    debug_record["external_page_url"] = external.get("page_url")
                    debug_record["external_license"] = external.get("license")
                    debug_record["external_license_url"] = external.get("license_url")
                    debug_record["external_author"] = external.get("author")
                    debug_record["external_output_validation"] = validation
                    debug_records.append(debug_record)
                    saved = True
                    print(
                        f"[slide_images] slide {idx} external fallback saved "
                        f"(source={external.get('source')}, query={external.get('query')})"
                    )
                else:
                    if not debug_record.get("status") or debug_record["status"] == "pending":
                        debug_record["status"] = "failed"
                    if last_error and not debug_record.get("error"):
                        debug_record["error"] = last_error
                    debug_records.append(debug_record)

            if progress_cb is not None:
                try:
                    await progress_cb(idx + 1, n)
                except Exception:
                    pass

    print(f"[slide_images] done: {len(out)}/{n} images saved to {IMAGE_DIR}")
    _write_debug_json(task_id, "images", debug_records)
    _write_image_quality_report(task_id, debug_records)
    return out
