from __future__ import annotations
import base64
import json
import re
from typing import Any, Dict, List, Optional
import httpx
from pathlib import Path
import io
from PIL import Image, ImageChops, ImageFilter, ImageStat
from config import (
    IMAGE_VALIDATION_HUMAN_MIN_EDGE_MEAN,
    IMAGE_VALIDATION_MAX_NEAR_BLACK_RATIO,
    IMAGE_VALIDATION_MAX_NEAR_WHITE_RATIO,
    IMAGE_VALIDATION_MIN_CONTRAST,
    IMAGE_VALIDATION_MIN_EDGE_MEAN,
    IMAGE_VALIDATION_MIN_EDGE_STDDEV,
    IMAGE_VALIDATION_MIN_ENTROPY,
    IMAGE_VALIDATION_MIN_SYMMETRY_ERROR,
    IMAGE_CLIP_SCORE_TIMEOUT_SEC,
    IMAGE_CLIP_VALIDATE_ENABLE,
    IMAGE_VLM_JUDGE_ENABLE,
    IMAGE_VLM_JUDGE_MAX_ARTIFACT,
    IMAGE_VLM_JUDGE_MIN_RELEVANCE,
    IMAGE_VLM_JUDGE_MIN_STYLE,
    IMAGE_VLM_JUDGE_MODEL,
    IMAGE_VLM_JUDGE_TIMEOUT_SEC,
    GEMINI_API_KEY,
    GCP_VERTEX_AI_ENABLE,
    GCP_PROJECT_ID,
    GCP_REGION,
)
from .semantics import (
    _COVERAGE_THRESHOLD,
    _is_mostly_ascii,
    _scoreable_anchors,
    _meaningful_terms,
    _vlm_has_severe_failure,
)


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


def _image_acceptance_policy(
    semantic: Dict[str, Any],
    *,
    is_stock_photo: bool = False,
) -> Dict[str, Any]:
    """Return broad image acceptance policy by content/domain.

    Keep this generic: rules are grouped by visual risk and expected use, not by
    individual topics. Specific topics should fall into one of these buckets.
    """
    content_type = str(semantic.get("content_type") or "normal").strip().lower()
    domain = str(semantic.get("domain") or "general").strip().lower()
    risk = str(semantic.get("risk") or "").strip().lower()
    sensitive_risks = {
        "historical",
        "person_protected",
        "religious",
        "cultural",
        "medical_diagram",
        "political_sensitive",
        "crisis_sensitive",
        "legal_sensitive",
        "identity_sensitive",
        "child_sensitive",
        "map_symbol_sensitive",
        "finance_sensitive",
    }

    if is_stock_photo:
        policy = {
            "expected_style": "stock_photo",
            "min_relevance": 0.50,
            "max_artifact": 0.65,
            "min_style": 0.55,
            "allow_soft_text_artifacts": True,
            "hard_text_reject": False,
            "notes": "stock image: tolerate real-world text, require subject fit",
        }
        if content_type in {"process", "definition"} or domain in {"technology", "cybersecurity", "software"}:
            policy["min_relevance"] = 0.55
        if content_type in {"historical", "cultural", "religious"} or risk in sensitive_risks:
            policy["min_relevance"] = 0.72
            policy["max_artifact"] = 0.50
            policy["min_style"] = 0.70
            policy["notes"] = "sensitive stock/reference image: require specific event, person, place, group, era, symbol, or domain fit, not just a broad theme"
        return policy

    if content_type in {"historical", "cultural", "religious", "medical_diagram"} or risk in sensitive_risks:
        return {
            "expected_style": "historical_or_special_illustration",
            "min_relevance": 0.82,
            "max_artifact": 0.35,
            "min_style": 0.82,
            "allow_soft_text_artifacts": True,
            "hard_text_reject": True,
            "notes": "AI-generated sensitive/special visual: require very specific context fit, respectful representation, and very clean low-artifact rendering",
        }

    if content_type in {"data"}:
        return {
            "expected_style": "data_visual",
            "min_relevance": 0.70,
            "max_artifact": 0.45,
            "min_style": 0.75,
            "allow_soft_text_artifacts": False,
            "hard_text_reject": True,
            "notes": "data slides should normally use chart/table routing",
        }

    if domain in {"technology", "cybersecurity", "software"}:
        return {
            "expected_style": "professional_photo",
            "min_relevance": 0.70,
            "max_artifact": 0.42,
            "min_style": 0.78,
            "allow_soft_text_artifacts": False,
            "hard_text_reject": True,
            "notes": "technology: reject fake UI/text and generic laptop scenes",
        }

    if domain in {"medical", "finance", "legal"}:
        return {
            "expected_style": "professional_photo",
            "min_relevance": 0.72,
            "max_artifact": 0.40,
            "min_style": 0.80,
            "allow_soft_text_artifacts": False,
            "hard_text_reject": True,
            "notes": "high-trust domain: require professional, low-artifact image",
        }

    if domain in {"education"}:
        return {
            "expected_style": "professional_photo",
            "min_relevance": 0.65,
            "max_artifact": 0.48,
            "min_style": 0.72,
            "allow_soft_text_artifacts": True,
            "hard_text_reject": True,
            "notes": "education: tolerate minor document texture, keep clear focus",
        }

    return {
        "expected_style": "professional_photo",
        "min_relevance": 0.65,
        "max_artifact": 0.45,
        "min_style": 0.75,
        "allow_soft_text_artifacts": False,
        "hard_text_reject": True,
        "notes": "general professional slide image",
    }


async def _vlm_judge_image(
    client: httpx.AsyncClient,
    *,
    image_bytes: bytes,
    prompt: str,
    slide: Dict[str, Any],
    semantic: Dict[str, Any],
    min_relevance: Optional[float] = None,
    max_artifact: Optional[float] = None,
    min_style: Optional[float] = None,
    is_stock_photo: bool = False,
) -> Optional[Dict[str, Any]]:
    if not IMAGE_VLM_JUDGE_ENABLE:
        return None
    use_vertex = GCP_VERTEX_AI_ENABLE and GCP_PROJECT_ID
    if not use_vertex and not GEMINI_API_KEY:
        return None
    model = (IMAGE_VLM_JUDGE_MODEL or "").strip()
    if not model:
        return None
    context = _slide_context_for_vlm(slide, semantic)

    policy = _image_acceptance_policy(semantic, is_stock_photo=is_stock_photo)
    base_min_rel = min_relevance if min_relevance is not None else float(IMAGE_VLM_JUDGE_MIN_RELEVANCE)
    if is_stock_photo:
        min_rel = max(float(base_min_rel), float(policy["min_relevance"]))
    else:
        min_rel = max(float(base_min_rel), float(policy["min_relevance"]))
    max_art = max_artifact if max_artifact is not None else float(policy.get("max_artifact", IMAGE_VLM_JUDGE_MAX_ARTIFACT))
    min_sty = min_style if min_style is not None else float(policy.get("min_style", IMAGE_VLM_JUDGE_MIN_STYLE))
    expected_style = str(policy["expected_style"])

    if is_stock_photo:
        instruction = (
            "You are an image quality, semantic fidelity, and historical/geographical accuracy judge for presentation slides.\n"
            "Critically evaluate if the image represents the slide context, topic, and details accurately and logically.\n"
            "Apply strict scoring and rejection rules:\n"
            "1. CULTURAL & HISTORICAL FIDELITY: If the slide refers to Vietnam (or any specific region/era) but the image shows people, clothing, architecture, or settings that belong to other cultures (e.g., modern Western students/classrooms, European medieval elements, or unrelated Asian cultures), this is a geographical mismatch. Set relevance_score below 0.40.\n"
            "2. GEOGRAPHICAL & MAP ACCURACY: If the image contains a map of a country (e.g., Vietnam) but the outline is distorted or clearly resembles a different country, set relevance_score below 0.35.\n"
            "3. LOGICAL INCONSISTENCIES: If there are logical contradictions between the slide content and the image, set relevance_score below 0.35.\n"
            "4. PRODUCT & SUBJECT RELEVANCE: The main subject in the image must match the core nouns and intent of the slide. Set relevance_score below 0.40 if completely irrelevant.\n"
            "5. HISTORICAL SPECIFICITY: For historical slides, the image must match the named event, era, country, and period implied by the slide. A modern factory, generic training room, unrelated monument, or broad thematic proxy must get relevance_score below 0.55 even if it is from the right country.\n"
            "6. TEXT & WATERMARKS: Since this is a curated stock/historical photo, visible text, labels, captions, or historical diagram elements are ALLOWED and should NOT cause rejection. Set artifact_score to 0.10.\n"
            "7. QUALITY: If the image is completely corrupt or unusable, set artifact_score to 0.80.\n\n"
            "Return JSON only with the following keys:\n"
            "{\n"
            "  \"relevance_score\": number,   // 0.0 to 1.0\n"
            "  \"artifact_score\": number,    // 0.0 to 1.0 (LOWER IS BETTER)\n"
            "  \"style_match_score\": number, // 0.0 to 1.0\n"
            "  \"reasons\": [string],          \n"
            f"  \"pass\": boolean              // true if relevance_score >= {min_rel:.2f} AND artifact_score <= {max_art:.2f} AND no severe failures (like wrong culture or completely unrelated subject)\n"
            "}"
        )
    else:
        instruction = (
            "You are an image quality, semantic fidelity, and historical/geographical accuracy judge for presentation slides.\n"
            "Critically evaluate if the image represents the slide context, topic, and details accurately and logically.\n"
            "Apply extremely strict scoring and rejection rules:\n"
            "1. CULTURAL & HISTORICAL FIDELITY: If the slide refers to Vietnam (or any specific region/era) but the image shows people, clothing, architecture, or settings that belong to other cultures (e.g., modern Western students/classrooms, European medieval elements, or unrelated Asian cultures), this is a geographical mismatch. Set relevance_score below 0.45.\n"
            "2. GEOGRAPHICAL & MAP ACCURACY: If the image contains a map of a country (e.g., Vietnam) but the outline is distorted, incorrect, or clearly resembles a different country or random blobs, it is inaccurate. Set relevance_score below 0.40.\n"
            "3. LOGICAL INCONSISTENCIES: If there are logical contradictions between the slide content and the image (e.g., the slide discusses agricultural development but the image shows a high-tech office, or the slide is about a war but the image shows a modern business meeting), set relevance_score below 0.35.\n"
            "4. PRODUCT & SUBJECT RELEVANCE: The main subject in the image must match the core nouns and intent of the slide. If the image is a generic stock photo (like a person holding a book or looking at a wall) that has no direct thematic connection to the specific points on the slide, set relevance_score below 0.50.\n"
            "5. HISTORICAL SPECIFICITY: For historical slides, the image must match the named event, era, country, and period implied by the slide. Reject invented documentary-looking scenes, modern settings, or broad proxies that only match one keyword. Set relevance_score below 0.55 or artifact_score above 0.60.\n"
            "6. TEXT & WATERMARKS: If the image contains any visible text, labels, fake words, signatures, watermarks, or infographic elements, set artifact_score to 0.70 or higher (reject).\n"
            "7. ANATOMY & QUALITY: If there are distorted faces, repeated/duplicated faces, cloned-looking people, unnatural hands/limbs, weird merged objects, or creepy anatomy, set artifact_score to 0.60 or higher.\n\n"
            "8. STYLE FIT: If Expected style is professional_photo, reject cartoon, anime, manga, comic-book, graphic-novel, hand-drawn, cel-shaded, flat illustration, painterly, or overly stylized images unless the slide explicitly asks for illustration. Set style_match_score below 0.50.\n"
            "9. CLEAR FOCUS: Reject images that are crowded, visually cluttered, contain too many people/objects, look like a synthetic collage, or have no clear focal subject. Set artifact_score to 0.60 or higher or relevance_score below 0.55.\n\n"
            "Return strict JSON only with the following keys:\n"
            "{\n"
            "  \"relevance_score\": number,   // 0.0 (irrelevant/inaccurate) to 1.0 (fully matches the slide, accurate, and relevant)\n"
            "  \"artifact_score\": number,    // 0.0 (perfectly clean, NO glitches/text/watermarks/deformations) to 1.0 (severe glitches, distorted anatomy, text/labels, corrupted rendering). LOWER IS BETTER.\n"
            "  \"style_match_score\": number, // 0.0 to 1.0 matching presentation stock/illustration style\n"
            "  \"reasons\": [string],          // Short reasons explaining the scores (be specific about any inaccuracies or failures)\n"
            f"  \"pass\": boolean              // true if relevance_score >= {min_rel:.2f} AND artifact_score <= {max_art:.2f} AND style_match_score >= {min_sty:.2f} for the expected non-stock style AND no severe failures (like wrong style, text, watermarks, creepy anatomy, clutter, or incorrect maps/cultures)\n"
            "}"
        )
    user_text = (
        f"Slide context:\n{context}\n\n"
        f"Expected style: {expected_style}\n\n"
        f"Acceptance policy: {policy.get('notes')}\n\n"
        f"Generation prompt:\n{(prompt or '')[:700]}\n\n"
        "Judge the attached image."
    )
    payload: Dict[str, Any] = {
        "contents": [
            {
                "role": "user",
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
    headers: Dict[str, str] = {}
    if use_vertex:
        payload["generationConfig"]["thinkingConfig"] = {
            "thinkingBudget": 0
        }
        from services.vertex_auth import get_vertex_access_token
        token = get_vertex_access_token()
        if not token:
            print("[slide_images] Vertex AI enabled but failed to obtain token for VLM Judge. Skipping.")
            return None
        headers["Authorization"] = f"Bearer {token}"
        url = (
            f"https://{GCP_REGION}-aiplatform.googleapis.com/v1/"
            f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}/publishers/google/models/{model}:generateContent"
        )
    else:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={GEMINI_API_KEY}"
        )
    try:
        resp = await client.post(
            url,
            json=payload,
            headers=headers,
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
        reasons_list = [str(r) for r in reasons[:5]]
        if is_stock_photo:
            reasons_for_severe = []
            for r in reasons_list:
                r_lower = r.lower()
                if any(term in r_lower for term in ("unrelated", "wrong subject", "off topic", "not related", "does not match", "irrelevant", "corrupt", "unusable")):
                    reasons_for_severe.append(r)
            severe_failure = _vlm_has_severe_failure(reasons_for_severe)
        else:
            severe_failure = _vlm_has_severe_failure(reasons_list)
        combined_reasons = " ".join(reasons_list).lower()
        hard_text_terms = (
            "visible text",
            "readable text",
            "fake words",
            "large text",
            "prominent text",
            "text dominates",
            "watermark",
            "logo",
            "caption",
            "label",
            "signature",
        )
        soft_text_terms = (
            "faint",
            "unreadable",
            "text-like",
            "text like",
            "blurred",
            "small marks",
            "paper texture",
        )
        relaxed_soft_text_artifact = (
            bool(policy.get("allow_soft_text_artifacts"))
            and relevance >= 0.75
            and artifact <= 0.50
            and any(term in combined_reasons for term in soft_text_terms)
            and not any(term in combined_reasons for term in hard_text_terms)
        )
        if severe_failure and relaxed_soft_text_artifact:
            severe_failure = False
        style_terms = (
            "cartoon",
            "anime",
            "manga",
            "comic",
            "comic-book",
            "graphic novel",
            "hand-drawn",
            "cel-shaded",
            "flat illustration",
            "painterly",
            "too stylized",
            "overly stylized",
            "wrong style",
            "style mismatch",
            "not professional",
        )
        style_reason_text = combined_reasons
        for term in style_terms:
            pattern = (
                r"\b(?:no|not|without|free of|clear of|doesn't|does not|isn't|is not|"
                r"avoid|avoids)\b[a-zA-Z0-9\s,.-]*?\b"
                + re.escape(term)
                + r"s?\b"
            )
            style_reason_text = re.sub(pattern, " ", style_reason_text)
        style_failure = (
            expected_style == "professional_photo"
            and (
                style < min_sty
                or any(term in style_reason_text for term in style_terms)
            )
        )
        strict_pass = (
            relevance >= min_rel
            and artifact <= max_art
            and (is_stock_photo or style >= min_sty)
            and not severe_failure
            and not style_failure
        )
        passed = strict_pass
        return {
            "relevance_score": round(relevance, 3),
            "artifact_score": round(artifact, 3),
            "style_match_score": round(style, 3),
            "reasons": reasons_list,
            "pass": bool(passed),
            "acceptance_rule": "strict" if strict_pass else "reject",
            "severe_failure": bool(severe_failure),
            "relaxed_soft_text_artifact": bool(relaxed_soft_text_artifact),
            "style_failure": bool(style_failure),
            "expected_style": expected_style,
            "acceptance_policy": policy,
            "model": model,
        }
    except Exception:
        return None


_DEBUG_DIR = Path("outputs") / "debug"


def _write_debug_json(task_id: str, name: str, records: List[Dict[str, Any]]) -> None:
    """Persist raw per-slide debug metadata for later inspection."""
    if not records:
        return
    try:
        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        path = _DEBUG_DIR / f"{task_id}_{name}.json"
        path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[slide_images] debug metadata: {path}")
    except Exception as e:
        print(f"[slide_images] debug metadata error: {e}")


def _write_image_quality_report(task_id: str, records: List[Dict[str, Any]]) -> None:
    """Aggregate per-slide debug records into a task-level quality summary."""
    if not records:
        return
    try:
        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        statuses: Dict[str, int] = {}
        scores: List[float] = []
        reinforced = 0
        fallback_refined = 0
        token_risk = 0
        coverage_failed = 0
        coverage_by_type: Dict[str, List[float]] = {}
        missed_counter: Dict[str, int] = {}
        low_quality: List[Dict[str, Any]] = []
        risk_counter: Dict[str, int] = {}
        catastrophic_counter: Dict[str, int] = {}
        vlm_reject_count = 0

        for record in records:
            status = str(record.get("status") or "unknown")
            statuses[status] = statuses.get(status, 0) + 1
            risk_value = record.get("risk")
            if risk_value:
                risk_counter[str(risk_value)] = risk_counter.get(str(risk_value), 0) + 1
            cat_reason = record.get("catastrophic_reason")
            if cat_reason:
                catastrophic_counter[str(cat_reason)] = catastrophic_counter.get(str(cat_reason), 0) + 1
            quality = record.get("prompt_quality") or {}
            if isinstance(quality, dict):
                score = quality.get("score_after")
                if isinstance(score, (int, float)):
                    scores.append(float(score))
                    ctype = str(quality.get("content_type") or record.get("content_type") or "normal")
                    coverage_by_type.setdefault(ctype, []).append(float(score))
                if quality.get("reinforced"):
                    reinforced += 1
                if quality.get("fallback_refined"):
                    fallback_refined += 1
                if quality.get("coverage_ok") is False:
                    coverage_failed += 1
                for missed in quality.get("missed_anchors") or []:
                    key = str(missed).strip().lower()
                    if not key:
                        continue
                    missed_counter[key] = missed_counter.get(key, 0) + 1
                threshold = float(quality.get("threshold") or 0.55)
                score_after = quality.get("score_after")
                if isinstance(score_after, (int, float)) and float(score_after) < threshold:
                    low_quality.append(
                        {
                            "slide_index": record.get("slide_index"),
                            "title": record.get("title"),
                            "content_type": record.get("content_type"),
                            "score_after": float(score_after),
                            "threshold": threshold,
                            "missed_anchors": quality.get("missed_anchors"),
                            "status": record.get("status"),
                        }
                    )
            if int(record.get("prompt_est_tokens") or 0) > 72:
                token_risk += 1
            if str(record.get("status") or "") in {"vlm_reject", "external_vlm_reject"}:
                vlm_reject_count += 1
            for att in record.get("attempts") or []:
                if isinstance(att, dict) and str(att.get("status") or "") == "vlm_reject":
                    vlm_reject_count += 1

        avg_score = round(sum(scores) / len(scores), 3) if scores else None
        coverage_per_type = {
            ctype: round(sum(vals) / len(vals), 3)
            for ctype, vals in coverage_by_type.items()
            if vals
        }
        top_missed = sorted(missed_counter.items(), key=lambda x: x[1], reverse=True)[:5]
        saved_statuses = {"saved", "saved_ai_fallback", "saved_external_fallback"}
        saved_total = sum(statuses.get(status, 0) for status in saved_statuses)

        report = {
            "task_id": task_id,
            "total_records": len(records),
            "statuses": statuses,
            "saved_images": saved_total,
            "saved_primary": statuses.get("saved", 0),
            "saved_ai_fallback": statuses.get("saved_ai_fallback", 0),
            "saved_external_fallback": statuses.get("saved_external_fallback", 0),
            "output_validation_failed": statuses.get("output_validation_failed", 0),
            "external_output_validation_failed": statuses.get("external_output_validation_failed", 0),
            "skipped_chart_or_data": statuses.get("skipped_chart_spec_route", 0)
            + statuses.get("skipped_data_chart_route", 0)
            + statuses.get("skipped_table_spec_route", 0),
            "skipped_catastrophic_risk": statuses.get("skipped_catastrophic_risk", 0),
            "risk_overrides": risk_counter,
            "catastrophic_reasons": catastrophic_counter,
            "prompt_quality_avg": avg_score,
            "prompt_coverage_by_content_type": coverage_per_type,
            "prompt_reinforced_count": reinforced,
            "prompt_fallback_refined_count": fallback_refined,
            "prompt_coverage_failed_count": coverage_failed,
            "prompt_token_risk_count": token_risk,
            "vlm_reject_count": vlm_reject_count,
            "top_missed_anchors": [
                {"anchor": k, "count": v} for k, v in top_missed
            ],
            "low_quality_records": low_quality,
        }
        path = _DEBUG_DIR / f"{task_id}_image_quality.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            f"[slide_images] quality report: {path} "
            f"(avg={avg_score}, coverage_failed={coverage_failed}, "
            f"reinforced={reinforced}, fallback={fallback_refined})"
        )
    except Exception as e:
        print(f"[slide_images] quality report error: {e}")


_HUMAN_HINTS = (
    "person",
    "people",
    "man",
    "woman",
    "human",
    "student",
    "teacher",
    "doctor",
    "worker",
    "engineer",
    "child",
    "children",
    "portrait",
    "face",
)


def _requires_human_subject(prompt_text: str) -> bool:
    t = (prompt_text or "").lower()
    return any(k in t for k in _HUMAN_HINTS)


def _estimate_symmetry_error(gray_128: Image.Image) -> float:
    """Return mean abs diff between image and horizontal mirror."""
    mirrored = gray_128.transpose(Image.FLIP_LEFT_RIGHT)
    diff = ImageChops.difference(gray_128, mirrored)
    stat = ImageStat.Stat(diff)
    return float(sum(stat.mean) / max(1, len(stat.mean)))


def _validate_output_image(raw: bytes, prompt_text: str = "", strict: bool = True) -> Dict[str, Any]:
    """Lightweight output validation for unusable generated images."""
    result: Dict[str, Any] = {
        "ok": False,
        "reasons": [],
    }
    try:
        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert("RGB")
            width, height = img.size
            result["size"] = [width, height]
            if width < 256 or height < 256:
                result["reasons"].append("too_small")

            thumb = img.resize((128, 128))
            gray = thumb.convert("L")
            gray_stat = ImageStat.Stat(gray)
            entropy = float(gray.entropy())
            stddev_mean = float(sum(gray_stat.stddev) / max(1, len(gray_stat.stddev)))
            brightness_mean = float(sum(gray_stat.mean) / max(1, len(gray_stat.mean)))

            edge = gray.filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edge)
            edge_mean = float(sum(edge_stat.mean) / max(1, len(edge_stat.mean)))
            edge_stddev = float(sum(edge_stat.stddev) / max(1, len(edge_stat.stddev)))
            symmetry_error = _estimate_symmetry_error(gray)

            hist = gray.histogram()  # 256 buckets, instant
            total = 128 * 128
            near_white = sum(hist[245:])
            near_black = sum(hist[:11])
            near_white_ratio = near_white / total
            near_black_ratio = near_black / total

            result["metrics"] = {
                "entropy": round(entropy, 3),
                "stddev_mean": round(stddev_mean, 3),
                "brightness_mean": round(brightness_mean, 3),
                "edge_mean": round(edge_mean, 3),
                "edge_stddev": round(edge_stddev, 3),
                "symmetry_error": round(symmetry_error, 3),
                "near_white_ratio": round(near_white_ratio, 3),
                "near_black_ratio": round(near_black_ratio, 3),
            }

            if strict:
                if entropy < IMAGE_VALIDATION_MIN_ENTROPY:
                    result["reasons"].append("low_entropy")
                if stddev_mean < IMAGE_VALIDATION_MIN_CONTRAST:
                    result["reasons"].append("low_contrast")
                if edge_mean < IMAGE_VALIDATION_MIN_EDGE_MEAN:
                    result["reasons"].append("low_detail")
                if edge_stddev < IMAGE_VALIDATION_MIN_EDGE_STDDEV:
                    result["reasons"].append("edge_flat")
                if near_white_ratio > IMAGE_VALIDATION_MAX_NEAR_WHITE_RATIO:
                    result["reasons"].append("mostly_white")
                if near_black_ratio > IMAGE_VALIDATION_MAX_NEAR_BLACK_RATIO:
                    result["reasons"].append("mostly_black")
                # Distorted generations often become overly symmetric with low local edge variance.
                if (
                    symmetry_error < IMAGE_VALIDATION_MIN_SYMMETRY_ERROR
                    and edge_mean < max(IMAGE_VALIDATION_MIN_EDGE_MEAN, 9.0)
                ):
                    result["reasons"].append("possible_distortion_or_artifact")
                if _requires_human_subject(prompt_text) and edge_mean < IMAGE_VALIDATION_HUMAN_MIN_EDGE_MEAN:
                    result["reasons"].append("human_subject_unclear")

            result["ok"] = not result["reasons"]
            return result
    except Exception as e:
        result["reasons"].append("decode_error")
        result["error"] = str(e)
        return result
