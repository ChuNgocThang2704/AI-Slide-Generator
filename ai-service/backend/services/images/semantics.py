from __future__ import annotations
import re
import unicodedata
from typing import Any, Dict, List, Optional




_SOFT_REPLACEMENTS = {
    "diagram": "engineers discussing system on screens",
    "diagrams": "engineers discussing system on screens",
    "chart": "people analyzing data on screens",
    "charts": "people analyzing data on screens",
    "infographic": "documents and visuals on desk",
    "infographics": "documents and visuals on desk",
    "map of vietnam": "documents and regional records on table",
    "vietnam map": "documents and regional records on table",
    "world map": "world globe and documents",
    "map": "documents on table",
    "maps": "documents on table",
}

_ABSTRACT_CONCEPT_KEYS_SORTED: Optional[List[str]] = None


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


def _vlm_has_severe_failure(reasons: List[str]) -> bool:
    """Return true for failures that should reject even high-relevance images.

    Gemini often assigns high artifact scores for small SDXL issues such as
    fingers or a soft keyboard while still saying the image is suitable. Those
    should not force a fallback. Severe mismatches, text-heavy images, broken
    anatomy, and unreadable/corrupt outputs still reject.
    """
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
        "repeated faces",
        "duplicated faces",
        "duplicate faces",
        "cloned faces",
        "cloned-looking people",
        "same face repeated",
        "synthetic collage",
        "invented documentary",
        "modern setting",
        "contemporary setting",
        "broad thematic proxy",
        "generic proxy",
        "doesn't specifically depict",
        "does not specifically depict",
        "not period-correct",
        "crowded",
        "visually cluttered",
        "too many people",
        "no clear focal subject",
        "extra limbs",
        "missing limb",
    )
    combined = " ".join(str(r) for r in reasons or []).lower()
    for term in severe_terms:
        # Match negation patterns preceding the term (with optional words in-between, e.g. "free of glitches or watermarks")
        pattern = r"\b(?:no|not|without|free of|clear of|clean of|doesn't|does not|avoid|avoids)\b[a-zA-Z0-9\s,]*?\b" + re.escape(term) + r"s?\b"
        combined = re.sub(pattern, " ", combined)
        
    return any(term in combined for term in severe_terms)






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
    if any(_word_in_text(w, text) for w in words):
        return True
    normalized_text = _strip_diacritics(text)
    if normalized_text == text:
        return False
    normalized_stop = {"phat", "phat ", "thanh"}
    for word in words:
        normalized_word = _strip_diacritics(word).strip().lower()
        if normalized_word in normalized_stop:
            continue
        if _word_in_text(normalized_word, normalized_text):
            return True
    return False


def _strip_diacritics(text: str) -> str:
    """ASCII-ish copy for robust Vietnamese keyword matching."""
    s = unicodedata.normalize("NFD", str(text or ""))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


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

    if _any_word_in_text(_MAP_SYMBOL_KEYWORDS, full_text):
        return "map_symbol_sensitive"
    if _any_word_in_text(_CHILD_KEYWORDS, full_text):
        return "child_sensitive"
    if _any_word_in_text(_POLITICAL_KEYWORDS, full_text):
        return "political_sensitive"
    if _any_word_in_text(_CRISIS_KEYWORDS, full_text):
        return "crisis_sensitive"
    if _any_word_in_text(_LEGAL_CRIME_KEYWORDS, full_text):
        return "legal_sensitive"
    if _any_word_in_text(_IDENTITY_SOCIAL_KEYWORDS, full_text):
        return "identity_sensitive"
    if _any_word_in_text(_HIGH_TRUST_FINANCE_KEYWORDS, full_text):
        return "finance_sensitive"
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


def _looks_like_historical_slide(slide: Dict[str, Any]) -> bool:
    title = str(slide.get("title") or "")
    bullets = slide.get("bullets") or slide.get("content") or []
    if isinstance(bullets, list):
        body = " ".join(str(b) for b in bullets[:5])
    else:
        body = str(bullets)
    text = f"{title}. {body}".lower()
    if re.search(r"\b(18|19|20)\d{2}\b", text):
        return True
    history_terms = (
        "history", "historical", "war", "revolution", "battle", "treaty",
        "agreement", "accord", "geneva", "indochina", "colonial",
        "chien tranh", "khang chien", "hiep dinh", "cach mang",
        "mien bac", "mien nam", "hai mien", "viet minh", "viet cong",
        "chiến tranh", "kháng chiến", "hiệp định", "cách mạng",
        "miền bắc", "miền nam", "hai miền",
        "chiáº¿n tranh", "khÃ¡ng chiáº¿n", "hiá»‡p", "cÃ¡ch máº¡ng",
        "miá»n báº¯c", "miá»n nam", "hai miá»n",
    )
    return any(term in text for term in history_terms)



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



async def _get_image_semantic(content_extractor, slide: Dict[str, Any]) -> Dict[str, Any]:
    fallback = _extract_semantic(slide)
    if not hasattr(content_extractor, "extract_image_semantic"):
        if _looks_like_historical_slide(slide):
            fallback["content_type"] = "historical"
            fallback["context"] = "historical"
            fallback["contexts"] = "historical"
            fallback["source"] = "rule_historical_heuristic"
        return fallback
    try:
        raw = await content_extractor.extract_image_semantic(
            {"context": _slide_prompt_context(slide, max_chars=900), "slide": slide}
        )
        semantic = _normalize_llm_semantic(raw, fallback)
        if semantic.get("content_type") == "normal" and _looks_like_historical_slide(slide):
            semantic["content_type"] = "historical"
            semantic["context"] = "historical"
            semantic["contexts"] = "historical"
            semantic["source"] = f"{semantic.get('source')}_historical_heuristic"
        print(
            "[slide_images] semantic "
            f"source={semantic.get('source')} confidence={semantic.get('confidence')} "
            f"type={semantic.get('content_type')} topic={str(semantic.get('main_topic'))[:80]}"
        )
        return semantic
    except Exception as e:
        print(f"[slide_images] semantic error: {e}")
        if _looks_like_historical_slide(slide):
            fallback["content_type"] = "historical"
            fallback["context"] = "historical"
            fallback["contexts"] = "historical"
            fallback["source"] = "rule_historical_heuristic"
        return fallback



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



_SLIDE_TYPE_HINTS: Dict[str, str] = {
    "intro": "wide establishing shot, confident atmosphere, bold composition",
    "data": "focused person analyzing documents or screens in a clean workspace",
    "process": "hands-on activity in progress, clear tools and step-by-step action",
    "benefit": "positive outcome moment, bright natural light, satisfied people",
    "problem": "visible obstacle or concern, tense but realistic mood",
    "solution": "resolution moment with clarity, clean professional environment",
    "conclusion": "wrap-up moment, aligned team, forward-looking tone",
    "default": "specific real-world scene, clear subject, realistic environment",
}

_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "intro": ["giới thiệu", "introduction", "overview", "agenda", "mục tiêu", "objective"],
    "data": ["số liệu", "thống kê", "data", "statistics", "metric", "kpi", "tỷ lệ", "percent"],
    "process": ["quy trình", "process", "bước", "step", "workflow", "pipeline", "giai đoạn"],
    "benefit": ["lợi ích", "benefit", "advantage", "ưu điểm", "hiệu quả", "result", "outcome"],
    "problem": ["vấn đề", "problem", "challenge", "thách thức", "risk", "rủi ro", "hạn chế"],
    "solution": ["giải pháp", "solution", "cách", "approach", "strategy", "chiến lược"],
    "conclusion": ["kết luận", "conclusion", "tóm tắt", "summary", "next step", "kế hoạch tiếp"],
}


_DOMAIN_OBJECT_HINTS: Dict[str, str] = {
    "ui_product": "smartphone mockup and wireframe printouts on desk",
    "startup_business": "pitch deck printouts and team discussion around laptop",
    "data_analytics": "performance report documents and analytics screens",
    "education_training": "notebooks, lesson materials, and instructor guiding learners",
    "general": "documents and tools relevant to the topic",
}



_ACTION_VISUAL_MAP: Dict[str, str] = {
    "analysis": "people analyzing information together",
    "design": "designer working on an interface concept",
    "discussion": "team discussing ideas around a table",
    "learning": "people learning with guidance from an instructor",
    "planning": "team planning next steps with clear priorities",
    "default": "people interacting with clear purpose",
}

_OBJECT_VISUAL_MAP: Dict[str, str] = {
    "app": "mobile app mockups and interface printouts",
    "data": "performance reports and analytics screens",
    "product": "prototype sample and supporting materials",
    "document": "documents and practical working tools",
    "default": "documents and tools related to the topic",
}

_CONTEXT_VISUAL_MAP: Dict[str, str] = {
    "business": "modern professional office",
    "education": "classroom or training space",
    "technology": "workspace with computers and technical equipment",
    "community": "real-world community setting",
    "default": "real-world professional environment",
}

_ACTION_DETAIL_MAP: Dict[str, str] = {
    "analysis": "looking at reports and comparing key results",
    "design": "sketching and reviewing interface options",
    "discussion": "talking together and aligning decisions",
    "learning": "following guidance and practicing new skills",
    "planning": "organizing tasks and setting clear milestones",
    "default": "collaborating naturally",
}

_EMOTION_MAP: Dict[str, str] = {
    "problem": "concerned expressions, tense atmosphere",
    "benefit": "happy and satisfied expressions, warm light",
    "historical": "serious and focused expressions, solemn mood",
    "comparison": "contrasting expressions on each side",
    "definition": "curious and attentive expressions",
    "process": "focused expressions with hands actively working",
    "intro": "confident and welcoming expressions",
    "solution": "relieved and confident expressions",
    "conclusion": "thoughtful and forward-looking expressions",
    "joy": "joyful expressions, bright atmosphere",
    "hope": "hopeful expressions, soft uplifting light",
    "struggle": "determined expressions in difficult conditions",
    "determination": "focused determined expressions, intense mood",
    "sorrow": "sorrowful expressions, somber dim atmosphere",
    "pride": "proud and dignified expressions",
    "awe": "expressions of awe and wonder",
    "fear": "anxious cautious expressions, dim mood",
    "gratitude": "warm grateful expressions",
    "calm": "calm focused expressions, serene atmosphere",
    "default": "natural expressions",
}

_EMOTION_KEYWORD_MAP: Dict[str, List[str]] = {
    "joy": ["happy", "joy", "vui", "hạnh phúc", "celebration", "festival", "lễ hội", "le hoi"],
    "hope": ["hope", "future", "tương lai", "tuong lai", "hy vọng", "hy vong", "aspiration"],
    "struggle": ["struggle", "khó khăn", "kho khan", "challenge", "hardship", "vất vả", "vat va"],
    "determination": ["determination", "quyết tâm", "quyet tam", "perseverance", "kiên trì", "kien tri"],
    "sorrow": ["sorrow", "đau buồn", "dau buon", "loss", "mất mát", "mat mat", "tragedy", "bi kịch"],
    "pride": ["pride", "tự hào", "tu hao", "honor", "vinh dự", "vinh du"],
    "awe": ["awe", "wonder", "kinh ngạc", "kinh ngac", "majestic", "vĩ đại", "vi dai"],
    "fear": ["fear", "nỗi sợ", "noi so", "dread", "anxiety", "lo âu", "lo au"],
    "gratitude": ["gratitude", "biết ơn", "biet on", "thanks", "appreciation"],
    "calm": ["peace", "bình yên", "binh yen", "serene", "thanh tịnh", "thanh tinh", "tranquil"],
}

_BRAND_NORMALIZATION_MAP: Dict[str, str] = {
    "apple iphone": "modern smartphone",
    "apple ipad": "modern tablet",
    "apple macbook": "modern laptop",
    "apple watch": "smart watch",
    "apple airpods": "wireless earbuds",
    "iphone": "modern smartphone",
    "ipad": "modern tablet",
    "macbook": "modern laptop",
    "mac mini": "modern desktop computer",
    "airpods": "wireless earbuds",
    "tesla model 3": "modern electric sedan",
    "tesla model y": "modern electric suv",
    "tesla": "modern electric car",
    "model 3": "modern electric sedan",
    "model y": "modern electric suv",
    "windows 11": "modern operating system interface",
    "microsoft office": "office productivity software",
    "google search": "search engine interface",
    "google chrome": "web browser interface",
    "facebook": "social media platform interface",
    "instagram": "photo sharing app interface",
    "tiktok": "short video app interface",
    "youtube": "video platform interface",
    "twitter": "microblogging social platform interface",
    "linkedin": "professional networking platform interface",
    "amazon": "online shopping platform interface",
    "netflix": "video streaming platform interface",
    "spotify": "music streaming platform interface",
    "uber": "ride sharing app interface",
    "airbnb": "vacation rental platform interface",
    "chatgpt": "AI chat assistant interface",
    "openai": "AI research lab environment",
    "github": "code collaboration platform interface",
    "coca cola": "soft drink bottle without logo",
    "pepsi": "soft drink can without logo",
    "starbucks": "coffee shop scene without logo",
    "mcdonald": "fast food restaurant without logo",
    "kfc": "fast food restaurant without logo",
    "bmw": "modern luxury car without logo",
    "mercedes": "modern luxury car without logo",
    "toyota": "modern sedan without logo",
    "honda": "modern car without logo",
    "ford": "modern car without logo",
    "nike": "athletic shoes without logo",
    "adidas": "athletic shoes without logo",
    "samsung galaxy": "modern smartphone",
    "samsung": "modern electronics device",
    "xiaomi": "modern smartphone",
}

_PERSON_HONORIFICS: List[str] = [
    "bác", "bac", "cụ", "cu", "vua", "chúa", "chua", "hoàng đế", "hoang de",
    "hoàng hậu", "hoang hau", "thái thượng hoàng", "thai thuong hoang", "chủ tịch",
    "chu tich", "tổng bí thư", "tong bi thu", "thủ tướng", "thu tuong", "đại tướng",
    "dai tuong", "thiếu tướng", "thieu tuong", "trung tướng", "trung tuong",
    "thượng tướng", "thuong tuong", "tướng quân", "tuong quan", "tổng thống",
    "tong thong", "thái sư", "thai su", "thái uý", "thai uy", "king", "queen",
    "emperor", "empress", "prince", "princess", "duke", "duchess", "president",
    "general", "captain", "admiral", "commander", "sir", "lord", "lady", "pope",
    "saint", "marshal", "chancellor", "chairman", "doctor", "professor", "father",
    "mother",
]

_PERSON_PATTERN_FAMOUS = [
    "hồ chí minh", "ho chi minh", "võ nguyên giáp", "vo nguyen giap",
    "trần hưng đạo", "tran hung dao", "lý thường kiệt", "ly thuong kiet",
    "hai bà trưng", "hai ba trung", "lê lợi", "le loi", "quang trung",
    "nguyễn trãi", "nguyen trai", "nguyễn huệ", "nguyen hue", "ngô quyền", "ngo quyen",
    "napoleon", "lincoln", "washington", "jefferson", "stalin", "lenin", "hitler",
    "churchill", "roosevelt", "caesar", "augustus", "alexander the great",
    "genghis khan", "thành cát tư hãn", "thanh cat tu han", "cleopatra",
    "tutankhamun", "ramses", "confucius", "khổng tử", "khong tu", "socrates",
    "plato", "aristotle", "leonardo da vinci", "michelangelo", "gandhi",
    "mandela", "martin luther king",
]

_PERSON_NEGATIVE_HINTS = [
    "war", "revolution", "battle", "treaty", "empire", "dynasty", "movement",
    "campaign", "uprising", "agreement", "conference", "city", "country", "region",
    "river", "mountain", "ocean", "chiến tranh", "chien tranh", "trận chiến",
    "tran chien", "hiệp định", "hiep dinh", "phong trào", "phong trao", "khởi nghĩa",
    "khoi nghia", "triều đại", "trieu dai", "đế quốc", "de quoc", "nhà nước", "nha nuoc",
]

_VISUAL_POLICIES: Dict[str, Dict[str, str]] = {
    "historical": {
        "composition": "documentary historical realism",
        "required": "period clothing, period-correct objects, archival atmosphere",
        "negative": (
            "modern laptop, smartphone, modern office, neon lights, futuristic device, "
            "modern suit, glass office, conference room, projector, presentation screen, "
            "sunglasses, sneakers, contemporary clothing"
        ),
    },
    "comparison": {
        "composition": "clear left and right split composition",
        "required": "clear left-right split composition, two separate scenes, visible contrast, balanced layout",
        "negative": "single subject only, mixed unclear scene, blended background, one-sided framing",
    },
    "definition": {
        "composition": "simple demonstration scene",
        "required": "real-world example, one clear concept, practical objects",
        "negative": "abstract symbols only, floating icons, decorative typography, conceptual diagram",
    },
    "process": {
        "composition": "sequential action scene",
        "required": "step-by-step activity, tools in use, visible progress",
        "negative": "static pose, unclear action, posed photo, frozen subject",
    },
    "normal": {
        "composition": "real-world professional scene",
        "required": "clear subject, concrete objects, natural interaction",
        "negative": "generic stock pose, empty background, plain studio backdrop",
    },
}

_COVERAGE_THRESHOLD: Dict[str, float] = {
    "historical": 0.6,
    "comparison": 0.55,
    "process": 0.55,
    "definition": 0.5,
    "normal": 0.5,
    "data": 0.0,
}

_RISK_STYLE_OVERRIDES: Dict[str, str] = {
    "historical": "vintage watercolor illustration, soft brush strokes, archival hand-painted look, warm sepia tones",
    "person_protected": "stylized vintage poster illustration, hand-drawn look, soft palette",
    "religious": "respectful illustration style, soft watercolor, calm hand-painted look",
    "cultural": "traditional folk illustration style, hand-painted look, warm hues",
    "medical_diagram": "clean educational illustration, flat hand-drawn style, soft palette",
    "political_sensitive": "neutral documentary editorial photography style",
    "crisis_sensitive": "respectful documentary editorial photography style, non-graphic",
    "legal_sensitive": "neutral professional documentary photography style",
    "identity_sensitive": "respectful documentary photography style, dignified representation",
    "child_sensitive": "safe educational stock photography style",
    "map_symbol_sensitive": "neutral documentary reference image style",
    "finance_sensitive": "neutral professional business photography style",
}

_RELIGIOUS_KEYWORDS = [
    "phật", "phat ", "phật giáo", "phat giao", "buddha", "buddhist", "thiên chúa",
    "thien chua", "công giáo", "cong giao", "catholic", "christian", "christ", "jesus",
    "chúa giê", "chua gie", "hồi giáo", "hoi giao", "islam", "muslim", "allah", "quran",
    "kinh quran", "ấn độ giáo", "an do giao", "hindu", "hinduism", "do thái giáo",
    "do thai giao", "judaism", "jewish", "đạo giáo", "dao giao", "taoism", "khổng giáo",
    "khong giao", "confucianism", "thiền", "zen", "meditation", "thánh", "thanh", "saint",
    "deity", "divine", "sacred", "tâm linh", "tam linh", "spirituality", "spiritual",
    "nhà thờ", "nha tho", "church", "cathedral", "đền chùa", "den chua", "temple",
    "pagoda", "mosque", "synagogue",
]

_CULTURAL_KEYWORDS = [
    "áo dài", "ao dai", "kimono", "hanbok", "saree", "tết", "tet", "lunar new year",
    "lễ hội", "le hoi", "festival", "đám cưới truyền thống", "dam cuoi truyen thong",
    "traditional wedding", "trang phục dân tộc", "trang phuc dan toc", "ethnic costume",
    "nhạc cụ dân tộc", "nhac cu dan toc", "đàn tranh", "dan tranh", "đàn bầu", "dan bau",
    "đàn nguyệt", "dan nguyet", "ca trù", "ca tru", "chèo", "cheo", "tuồng", "tuong",
    "quan họ", "quan ho", "cải lương", "cai luong", "thư pháp", "thu phap", "calligraphy",
]

_MEDICAL_DIAGRAM_KEYWORDS = [
    "giải phẫu", "giai phau", "anatomy", "anatomical", "cấu trúc cơ thể", "cau truc co the",
    "body structure", "dna", "rna", "tế bào", "te bao", "cell structure", "phân tử",
    "phan tu", "molecule", "công thức hóa học", "cong thuc hoa hoc", "mạch máu", "mach mau",
    "blood vessel", "neuron", "synapse", "bệnh án", "benh an", "patient case", "chẩn đoán",
    "chan doan",
]

_POLITICAL_KEYWORDS = [
    "politics", "political", "government", "state", "election", "vote", "voting",
    "campaign", "parliament", "congress", "senate", "minister", "president",
    "prime minister", "policy", "public policy", "diplomacy", "sanction",
    "political party", "communist party", "democratic party", "republican party",
    "bầu cử", "bau cu", "chính trị", "chinh tri", "nhà nước", "nha nuoc",
    "chính phủ", "chinh phu", "quốc hội", "quoc hoi", "đảng phái", "dang phai",
    "ngoại giao", "ngoai giao", "chính sách", "chinh sach",
]

_CRISIS_KEYWORDS = [
    "war", "conflict", "invasion", "attack", "terrorism", "terrorist", "bombing",
    "massacre", "genocide", "refugee", "disaster", "earthquake", "flood", "wildfire",
    "pandemic", "epidemic", "accident", "crash", "explosion", "violence", "violent",
    "weapon", "gun", "military operation", "humanitarian crisis",
    "chiến tranh", "chien tranh", "xung đột", "xung dot", "khủng bố", "khung bo",
    "thảm họa", "tham hoa", "thiên tai", "thien tai", "tai nạn", "tai nan",
    "bạo lực", "bao luc", "vũ khí", "vu khi", "người tị nạn", "nguoi ti nan",
]

_LEGAL_CRIME_KEYWORDS = [
    "law", "legal", "court", "trial", "judge", "lawsuit", "crime", "criminal",
    "police", "prison", "arrest", "fraud", "corruption", "bribery", "scam",
    "tòa án", "toa an", "pháp luật", "phap luat", "luật", "luat", "tội phạm",
    "toi pham", "cảnh sát", "canh sat", "tham nhũng", "tham nhung", "lừa đảo",
    "lua dao",
]

_IDENTITY_SOCIAL_KEYWORDS = [
    "ethnicity", "ethnic", "race", "racial", "religious minority", "minority",
    "gender", "lgbt", "lgbtq", "sexual orientation", "disability", "disabled",
    "poverty", "homeless", "migration", "migrant", "immigration", "indigenous",
    "dân tộc", "dan toc", "sắc tộc", "sac toc", "giới tính", "gioi tinh",
    "khuyết tật", "khuyet tat", "nghèo đói", "ngheo doi", "vô gia cư", "vo gia cu",
    "di cư", "di cu", "nhập cư", "nhap cu",
]

_CHILD_KEYWORDS = [
    "child", "children", "kid", "kids", "minor", "teenager", "student children",
    "trẻ em", "tre em", "thiếu nhi", "thieu nhi", "học sinh tiểu học",
    "hoc sinh tieu hoc", "mầm non", "mam non",
]

_MAP_SYMBOL_KEYWORDS = [
    "map", "territory", "border", "sovereignty", "national flag", "flag",
    "national emblem", "coat of arms", "anthem", "disputed territory",
    "bản đồ", "ban do", "lãnh thổ", "lanh tho", "biên giới", "bien gioi",
    "chủ quyền", "chu quyen", "quốc kỳ", "quoc ky", "quốc huy", "quoc huy",
]

_HIGH_TRUST_FINANCE_KEYWORDS = [
    "investment advice", "financial advice", "stock recommendation", "crypto",
    "cryptocurrency", "loan", "debt", "insurance claim", "tax", "bankruptcy",
    "đầu tư", "dau tu", "tài chính cá nhân", "tai chinh ca nhan", "tiền số",
    "tien so", "vay nợ", "vay no", "bảo hiểm", "bao hiem", "thuế", "thue",
]

_CATASTROPHIC_FLAG_KEYWORDS = [
    "quốc kỳ", "quoc ky", "quốc huy", "quoc huy", "quốc ca", "quoc ca",
    "national flag", "national emblem", "national anthem", "lá cờ", "la co",
]

_CATASTROPHIC_SACRED_KEYWORDS = [
    "kinh thánh", "kinh thanh", "holy bible", "holy quran", "kinh quran", "thánh giá",
    "thanh gia", "holy cross", "thánh tích", "thanh tich", "sacred relic", "holy relic",
    "lăng", "lang ", "tomb of", "mausoleum", "đền thiêng", "den thieng", "sacred temple",
]

_HISTORICAL_REGION_KEYWORDS: Dict[str, List[str]] = {
    "Vietnam": [
        "việt nam", "viet nam", "vietnam", "đông dương", "dong duong", "indochina",
        "hà nội", "ha noi", "huế", "hue", "sài gòn", "sai gon", "saigon", "ba đình",
        "ba dinh", "điện biên", "dien bien", "geneva", "giơ-ne-vơ", "kháng chiến",
        "khang chien", "việt minh", "viet minh", "việt cộng", "cách mạng tháng",
        "cach mang thang", "nhà nguyễn", "nha nguyen", "nhà trần", "nha tran",
        "nhà lê", "nha le", "nhà lý", "nha ly",
    ],
    "France": [
        "thực dân pháp", "thuc dan phap", "french colonial", "french indochina",
        "napoleon", "paris", "versailles", "french revolution", "cách mạng pháp",
        "bastille", "louis xvi", "robespierre",
    ],
    "China": [
        "trung quốc", "trung quoc", "china", "chinese", "nhà tống", "nha tong",
        "nhà đường", "nha duong", "nhà hán", "nha han", "nhà nguyên", "nha nguyen",
        "nhà thanh", "nha thanh", "nhà minh", "nha minh", "tang dynasty",
        "han dynasty", "ming dynasty", "qing dynasty", "great wall", "forbidden city",
        "confucius", "khổng tử", "khong tu",
    ],
    "Japan": ["nhật bản", "nhat ban", "japan", "japanese", "tokyo", "edo", "samurai", "meiji", "shogun", "kyoto", "ronin", "bushido"],
    "Korea": ["hàn quốc", "han quoc", "korea", "korean", "joseon", "goryeo", "silla", "triều tiên", "trieu tien"],
    "Soviet Union": ["liên xô", "lien xo", "soviet", "ussr", "stalin", "lenin", "russian revolution", "moscow", "leningrad", "bolshevik", "trotsky"],
    "United States": ["hoa kỳ", "hoa ky", "united states", " usa ", "american civil war", "world war ii", "world war 2", "vietnam war", "lincoln", "washington", "jefferson", "civil rights", "great depression"],
    "Ancient Greece": ["hy lạp cổ", "hy lap co", "ancient greece", "greek polis", "athens", "sparta", "peloponnesian", "alexander the great", "socrates", "plato", "aristotle", "homer", "olympus"],
    "Roman Empire": ["đế quốc la mã", "de quoc la ma", "roman empire", "ancient rome", "caesar", "augustus", "colosseum", "gladiator", "senate", "republic of rome", "punic war", "carthage"],
    "Ancient Egypt": ["ai cập cổ", "ai cap co", "ancient egypt", "pharaoh", "pyramid", "nile", "cleopatra", "ramses", "tutankhamun", "hieroglyph", "sphinx"],
    "Persia": ["ba tư", "ba tu", "persia", "persian empire", "achaemenid", "cyrus", "darius", "sassanid", "zoroaster"],
    "Mesopotamia": ["lưỡng hà", "luong ha", "mesopotamia", "sumer", "babylon", "assyria", "hammurabi", "ziggurat", "cuneiform"],
    "Mongol Empire": ["đế quốc mông cổ", "de quoc mong co", "mongol empire", "genghis khan", "thành cát tư hãn", "thanh cat tu han", "kublai khan", "yuan dynasty", "horde", "steppe"],
    "Ottoman Empire": ["đế quốc ottoman", "de quoc ottoman", "ottoman empire", "constantinople", "istanbul", "sultan", "janissary", "suleiman"],
    "Mughal Empire": ["mughal", "đế quốc mughal", "babur", "akbar", "shah jahan", "taj mahal"],
    "Islamic Caliphate": ["caliphate", "khalifate", "abbasid", "umayyad", "baghdad", "córdoba", "islamic golden age"],
    "Aztec / Maya / Inca": ["aztec", "maya", "mayan", "inca", "tenochtitlan", "machu picchu", "quetzalcoatl", "moctezuma"],
    "Medieval Europe": ["trung cổ", "trung co", "medieval", "middle ages", "feudal", "knight", "crusade", "thập tự chinh", "thap tu chinh", "monastery", "castle", "black death"],
    "Renaissance": ["phục hưng", "phuc hung", "renaissance", "leonardo da vinci", "michelangelo", "florence", "medici", "humanism"],
    "Industrial Revolution": ["cách mạng công nghiệp", "cach mang cong nghiep", "industrial revolution", "steam engine", "factory worker", "victorian era"],
    "World War I": ["world war i", "world war 1", "ww1", "wwi", "first world war", "thế chiến thứ nhất", "the chien thu nhat", "trench warfare", "western front", "treaty of versailles"],
    "World War II": ["world war ii", "world war 2", "ww2", "wwii", "second world war", "thế chiến thứ hai", "the chien thu hai", "nazi", "hitler", "holocaust", "pearl harbor", "d-day", "normandy", "stalingrad"],
    "Cold War": ["chiến tranh lạnh", "chien tranh lanh", "cold war", "iron curtain", "berlin wall", "cuban missile"],
    "Europe": ["europe", "european", "châu âu", "chau au"],
}

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

_VN_INFERENCE_HINTS = [
    "bác", "bac", "việt", "viet", "đảng", "dang", "bộ chính trị", "bo chinh tri",
    "tự do", "tu do", "độc lập", "doc lap", "tuyên ngôn", "tuyen ngon",
    "đông dương", "dong duong", "miền bắc", "mien bac", "miền nam", "mien nam",
    "nhân dân", "nhan dan", "kháng chiến", "khang chien", "ba đình", "ba dinh",
    "quảng trường", "quang truong", "anh hùng", "anh hung",
]

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
