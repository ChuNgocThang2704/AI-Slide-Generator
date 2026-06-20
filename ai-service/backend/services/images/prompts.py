from __future__ import annotations
import re
from typing import Any, Dict, List, Optional

from config import (
    IMAGE_MODEL_TYPE,
    IMAGE_PROMPT_SUFFIX,
    IMAGE_STYLE_LOCKED,
)
from .semantics import (
    _ACTION_DETAIL_MAP,
    _DOMAIN_OBJECT_HINTS,
    _EMOTION_MAP,
    _METAPHOR_VISUAL_RE,
    _SLIDE_TYPE_HINTS,
    _SOFT_REPLACEMENTS,
    _classify_risk,
    _coverage_threshold,
    _detect_emotion,
    _is_mostly_ascii,
    _missed_anchors,
    _normalize_brand_terms,
    _override_scene_by_content_type,
    _risk_style_override,
    _scene_from_semantic,
    _score_prompt_quality,
    _semantic_anchors,
    _semantic_context,
    _semantic_list,
    _slide_prompt_context,
    _visual_policy,
)



_MIN_SCENE_CHARS = 12



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


_SCENE_SYSTEM_PROMPT = """Convert the slide into a REAL-WORLD PHOTOGRAPHABLE SCENE.

STRICT RULES:
- MUST include people, objects, and environment
- MUST include at least one human subject, one physical object, and one environment
- MUST visually represent the main idea of the slide
- DO NOT use abstract words alone (system, architecture, process, performance, solution)
- If the slide is abstract, convert it into a concrete real-life situation
- Use concrete nouns (engineer, computer, device, office, machine, document, meeting room, etc.)
- If the slide refers to a specific country or culture (e.g., Vietnam), the people depicted MUST match that country or culture (e.g., specify 'Vietnamese people', 'Vietnamese soldiers' or 'Vietnamese diplomats' instead of generic 'people', 'soldiers' or 'diplomats').
- Scene must be specific and vivid, not generic
- Output must be ENGLISH only

Output: comma-separated phrases only, no sentence, no explanation."""



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
    txt = str(prompt or "").strip()
    for k, v in _SOFT_REPLACEMENTS.items():
        txt = re.sub(rf"\b{re.escape(k)}\b", v, txt, flags=re.IGNORECASE)
    words = txt.split()
    txt = " ".join(words[:max_words])
    txt = re.sub(r"\s+,", ",", txt)
    txt = re.sub(r",\s*,+", ", ", txt)
    txt = re.sub(r"\s+", " ", txt).strip(" ,")
    return txt



def _dedupe_prompt_phrases(prompt: str) -> str:
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



# Các cụm PHẢI luôn có mặt trong negative prompt — đặt trước để không bị trim cắt.
_CORE_NEGATIVE_TERMS = (
    "text, typography, letters, words, watermark, logo, "
    "infographic, diagram, chart, graph, "
    "powerpoint slide, screenshot, UI interface, whiteboard, "
    "blurry, low quality, bad anatomy"
)



def _is_metaphor_visual(text: str) -> bool:
    """Detect abstract / metaphor terms LLMs propose as visual_objects."""
    s = str(text or "").strip()
    if not s:
        return False
    return bool(_METAPHOR_VISUAL_RE.search(s))



def _anchor_phrase(anchors: List[str], top_n: int = 3) -> str:
    """Build the head anchor phrase using English-friendly tokens only."""
    ascii_anchors = [str(a).strip() for a in anchors if str(a).strip() and _is_mostly_ascii(str(a))]
    return ", ".join(ascii_anchors[:top_n])



def _max_words_for_model() -> int:
    """Word budget cho prompt gửi vào SDXL/FLUX."""
    model_type = (IMAGE_MODEL_TYPE or "").strip().lower()
    return 50 if model_type == "sdxl" else 60



def _enforce_anchor_coverage(
    prompt: str,
    semantic: Dict[str, Any],
    slide: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    """Enforce that the final prompt contains required content anchors."""
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
    """Build a short, anchor-focused prompt used for retry after a generation failure."""
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
    """Build a prompt where mandatory anchors are LOCKED at the front."""
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
    if len(text.split()) < 6:
        return True
    for pat in _SCENE_BAD_PATTERNS:
        if pat.search(text):
            return True
    return False



def _vlm_reasons_to_negative(reasons: List[str]) -> str:
    """Chuyển đổi lý do reject từ VLM judge thành cụm negative prompt."""
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
