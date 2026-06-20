from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Callable, Awaitable

import httpx

from config import (
    IMAGE_DIR,
    IMAGE_GEN_API_BASE_URL,
    IMAGE_GEN_API_KEY,
    IMAGE_GEN_TIMEOUT_SEC,
    IMAGE_GUIDANCE_SCALE,
    IMAGE_HEIGHT,
    IMAGE_CLIP_MIN_SCORE,
    IMAGE_MAX_SLIDES_WITH_IMAGES,
    IMAGE_GEN_CONCURRENCY,
    IMAGE_MODEL_TYPE,
    IMAGE_NEGATIVE_PROMPT,
    IMAGE_STEPS,
    IMAGE_STYLE_LOCKED,
    IMAGE_WIDTH,
)
from .semantics import (
    _build_deck_context,
    _classify_risk,
    _detect_slide_type,
    _get_image_semantic,
    _is_catastrophic_risk,
    _visual_policy,
)
from .prompts import (
    _CORE_NEGATIVE_TERMS,
    _DEFAULT_NEGATIVE,
    _ILLUSTRATION_NEGATIVE,
    _merge_negative_prompt,
    _select_best_scene,
    _simplify_prompt_for_retry,
    _vlm_reasons_to_negative,
)
from .validation import (
    _clip_score_image,
    _estimate_clip_tokens,
    _validate_output_image,
    _vlm_judge_image,
    _write_debug_json,
    _write_image_quality_report,
)
from .providers import (
    _try_secondary_ai_image_fallback,
    _try_stock_photo_fallback,
)





def _is_continuation_slide(slide: Dict[str, Any], prev_slide: Optional[Dict[str, Any]] = None) -> bool:
    title = str(slide.get("title") or "").strip()
    if not title:
        return False
    if re.search(r"\s*\((?:tiếp|tiep|continued)\)\s*$", title, re.IGNORECASE):
        return True
    if prev_slide:
        prev_title = str(prev_slide.get("title") or "").strip()
        def _base_title(t: str) -> str:
            return re.sub(r"\s*\((?:tiếp|tiep|continued)\)\s*$", "", t, flags=re.IGNORECASE).strip().lower()
        if _base_title(title) == _base_title(prev_title):
            return True
    return False


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



# Premium quality prompt suffix for Ultra tier
_ULTRA_PROMPT_SUFFIX = ", exceptionally detailed, masterpiece, highly realistic, cinematic lighting, 8k resolution"


async def _process_single_slide(
    idx: int,
    client: httpx.AsyncClient,
    content_extractor,
    structured: Dict[str, Any],
    slides: List[Dict[str, Any]],
    table_specs: Optional[Dict[int, Dict[str, Any]]],
    chart_specs: Optional[Dict[int, Dict[str, Any]]],
    deck_title: str,
    task_id: str,
    base: str,
    headers: Dict[str, str],
    negative: str,
    url: str,
    should_stop: Optional[Any],
    plan_tier: str = "pro",
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    if should_stop is not None and await should_stop():
        return None, None

    slide = _normalize_slide_content(slides[idx])

    # Continuation slide check
    prev_slide = _normalize_slide_content(slides[idx - 1]) if idx > 0 else None
    if _is_continuation_slide(slide, prev_slide):
        print(f"[slide_images] skip image for continuation slide {idx} ({slide.get('title')})")
        rec = {
            "slide_index": idx,
            "title": str(slide.get("title") or ""),
            "status": "skipped_continuation_slide",
        }
        return None, rec

    if "title" in slide:
        slide["title"] = re.sub(r"\s*\((?:tiếp|tiep|continued)\)\s*$", "", str(slide["title"]), flags=re.IGNORECASE).strip()

    tried_candidates = []
    if deck_title and not slide.get("_deck_title"):
        slide["_deck_title"] = re.sub(r"\s*\((?:tiếp|tiep|continued)\)\s*$", "", deck_title, flags=re.IGNORECASE).strip()

    # Table skip
    if table_specs and idx in table_specs:
        print(f"[slide_images] skip image for table slide {idx}")
        rec = {
            "slide_index": idx,
            "title": str(slide.get("title") or ""),
            "status": "skipped_table_spec_route",
            "table_spec": table_specs[idx],
        }
        return None, rec

    # Chart skip
    if chart_specs and idx in chart_specs:
        print(f"[slide_images] skip image for chart slide {idx}")
        rec = {
            "slide_index": idx,
            "title": str(slide.get("title") or ""),
            "status": "skipped_chart_spec_route",
            "chart_spec": chart_specs[idx],
        }
        return None, rec

    # Slide type / semantic / data skip
    slide_type = _detect_slide_type(slide)
    semantic = await _get_image_semantic(content_extractor, slide)
    content_type = str(semantic.get("content_type") or "normal")
    if content_type == "data":
        print(f"[slide_images] skip image for data slide {idx}")
        rec = {
            "slide_index": idx,
            "title": str(slide.get("title") or ""),
            "status": "skipped_data_chart_route",
            "content_type": content_type,
            "semantic": semantic,
        }
        return None, rec

    # Catastrophic risk check
    catastrophic = _is_catastrophic_risk(slide)
    if catastrophic:
        print(
            f"[slide_images] skip image for catastrophic-risk slide {idx} "
            f"(reason={catastrophic})"
        )
        rec = {
            "slide_index": idx,
            "title": str(slide.get("title") or ""),
            "status": "skipped_catastrophic_risk",
            "catastrophic_reason": catastrophic,
            "content_type": content_type,
            "semantic": semantic,
        }
        return None, rec

    # Free tier: skip all AI generation, go straight to stock photo
    if plan_tier == "free":
        print(f"[slide_images] slide {idx} plan=free -> skip AI generation, use stock photo only")
        rec = {
            "slide_index": idx,
            "title": str(slide.get("title") or ""),
            "status": "pending_stock_only",
            "plan_tier": "free",
            "content_type": content_type,
            "semantic": semantic,
        }
        # Still need full_prompt for VLM validation of stock photos
        domain = str(semantic.get("domain") or "general")
        risk = _classify_risk(slide, semantic, content_type)
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
        full_prompt = str(best_candidate.get("prompt") or "")
        # Go directly to stock photo fallback
        async def _external_vlm_validate_free(img_bytes: bytes, meta: Dict[str, Any]) -> bool:
            vlm_judge_res = await _vlm_judge_image(
                client,
                image_bytes=img_bytes,
                prompt=full_prompt,
                slide=slide,
                semantic=semantic,
                min_relevance=0.45,
                is_stock_photo=True,
            )
            vlm_judge_dict = vlm_judge_res if vlm_judge_res is not None else {
                "relevance_score": 0.0, "artifact_score": 1.0,
                "style_match_score": 0.0,
                "reasons": ["VLM judge timed out or failed; rejecting unverified fallback"],
                "pass": False, "severe_failure": True,
            }
            meta["vlm_judge"] = vlm_judge_dict
            tried_candidates.append({
                "type": "external",
                "bytes": img_bytes,
                "relevance_score": float(vlm_judge_dict.get("relevance_score") or 0.0),
                "artifact_score": float(vlm_judge_dict.get("artifact_score") or 1.0),
                "severe_failure": bool(vlm_judge_dict.get("severe_failure") or False),
                "extension": str(meta.get("extension") or ".jpg"),
                "meta": {
                    "status": "saved_external_fallback",
                    "external_source": meta.get("source"),
                    "external_query": meta.get("query"),
                    "external_page_url": meta.get("page_url"),
                    "external_vlm_judge": vlm_judge_dict,
                    "external_license": meta.get("license"),
                    "external_license_url": meta.get("license_url"),
                    "external_author": meta.get("author")
                }
            })
            return bool(vlm_judge_dict.get("pass"))

        external = await _try_stock_photo_fallback(
            client, slide, semantic, content_type, risk,
            vlm_validate_fn=_external_vlm_validate_free,
        )
        if not external:
            external_candidates = [c for c in tried_candidates if c.get("type") == "external"]
            if external_candidates:
                external_candidates.sort(key=lambda c: (not c.get("severe_failure", False), c.get("relevance_score", 0.0)), reverse=True)
                best_c = external_candidates[0]
                best_vlm = ((best_c.get("meta") or {}).get("external_vlm_judge") or {})
                if best_c.get("relevance_score", 0.0) >= 0.30 and bool(best_vlm.get("pass")):
                    print(f"[slide_images] slide {idx} (free) recovering best stock candidate with relevance={best_c.get('relevance_score')}")
                    external = {
                        "bytes": best_c["bytes"],
                        "extension": best_c["extension"],
                        **best_c["meta"]
                    }

        if external:
            validation = _validate_output_image(external["bytes"], prompt_text=full_prompt, strict=False)
            if validation.get("ok"):
                ext = str(external.get("extension") or ".jpg").lower()
                if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                    ext = ".jpg"
                dest = IMAGE_DIR / f"{task_id}_{idx}_external{ext}"
                dest.write_bytes(external["bytes"])
                image_path = str(dest.resolve())
                rec["status"] = "saved_external_fallback"
                rec["image_path"] = image_path
                rec["external_source"] = external.get("source")
                rec["external_query"] = external.get("query")
                rec["external_vlm_judge"] = external.get("external_vlm_judge") or external.get("vlm_judge")
                print(f"[slide_images] slide {idx} (free) saved stock photo (source={external.get('source')})")
                return image_path, rec
        rec["status"] = "failed"
        print(f"[slide_images] slide {idx} (free) no stock photo found")
        return None, rec

    # Risk and Scene selection
    domain = str(semantic.get("domain") or "general")
    risk = _classify_risk(slide, semantic, content_type)
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

    # Ultra tier: append premium quality suffix to boost image detail
    if plan_tier == "ultra" and full_prompt:
        full_prompt = full_prompt.rstrip(", ") + _ULTRA_PROMPT_SUFFIX
        print(f"[slide_images] slide {idx} plan=ultra -> premium prompt suffix applied")

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
    skip_ai_generation = (
        bool(prompt_quality)
        and prompt_quality.get("coverage_ok") is False
        and content_type not in {"historical"}
    )
    if skip_ai_generation:
        debug_record["ai_generation_skipped"] = "prompt_coverage_failed"
        print(
            f"[slide_images] slide {idx} skip AI generation: prompt coverage failed "
            f"(score={prompt_quality.get('score_after')}, threshold={prompt_quality.get('threshold')})"
        )

    # Ultra tier: boost steps by 30% for higher detail and sharpness
    effective_steps = IMAGE_STEPS
    if plan_tier == "ultra":
        effective_steps = max(IMAGE_STEPS, int(IMAGE_STEPS * 1.3))
        print(f"[slide_images] slide {idx} plan=ultra -> steps boosted {IMAGE_STEPS} -> {effective_steps}")

    base_payload = {
        "width": IMAGE_WIDTH,
        "height": IMAGE_HEIGHT,
        "steps": effective_steps,
        "guidance_scale": float(IMAGE_GUIDANCE_SCALE),
        "return_base64": False,
    }

    attempts_plan = [
        {
            "label": "primary",
            "prompt": full_prompt,
            "negative": slide_negative,
        },
    ]
    debug_record["attempts"] = []

    dest = IMAGE_DIR / f"{task_id}_{idx}.png"
    saved = False
    last_error: Optional[str] = None
    image_path: Optional[str] = None

    try:
        for attempt_idx, plan in enumerate(attempts_plan):
            if skip_ai_generation:
                last_error = "prompt_coverage_failed"
                debug_record["status"] = "low_prompt_coverage"
                break
            if should_stop is not None and await should_stop():
                return None, None
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
                min_relevance=0.70,
            )
            if vlm_judge is not None:
                attempt_record["vlm_judge"] = vlm_judge
                tried_candidates.append({
                    "type": f"ai_attempt_{plan['label']}",
                    "bytes": raw,
                    "relevance_score": float(vlm_judge.get("relevance_score") or 0.0),
                    "artifact_score": float(vlm_judge.get("artifact_score") or 1.0),
                    "severe_failure": bool(vlm_judge.get("severe_failure") or False),
                    "extension": ".png",
                    "meta": {
                        "status": "saved",
                        "used_attempt": plan["label"]
                    }
                })
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
            image_path = str(dest.resolve())
            debug_record["status"] = "saved"
            debug_record["image_path"] = image_path
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
            saved = True
            if plan["label"] != "primary":
                print(f"[slide_images] slide {idx} saved by retry attempt: {plan['label']}")
            break
    except Exception as e:
        print(f"[slide_images] slide {idx} error: {e}")
        last_error = str(e)
        debug_record["status"] = "exception"
        debug_record["error"] = str(e)

    # Fallback to secondary AI
    if not saved and not skip_ai_generation:
        if should_stop is not None and await should_stop():
            return None, None
        secondary_raw = await _try_secondary_ai_image_fallback(
            client,
            prompt=full_prompt,
            negative_prompt=slide_negative,
            payload_template=base_payload,
        )
        if secondary_raw:
            validation = _validate_output_image(secondary_raw, prompt_text=full_prompt, strict=False)
            debug_record["ai_fallback_output_validation"] = validation
            if validation.get("ok"):
                clip_score = await _clip_score_image(
                    client,
                    base_url=base,
                    image_bytes=secondary_raw,
                    text=full_prompt,
                )
                if clip_score is not None:
                    debug_record["ai_fallback_clip_score"] = clip_score
                vlm_judge = await _vlm_judge_image(
                    client,
                    image_bytes=secondary_raw,
                    prompt=full_prompt,
                    slide=slide,
                    semantic=semantic,
                    min_relevance=0.65,
                )
                if vlm_judge is not None:
                    debug_record["ai_fallback_vlm_judge"] = vlm_judge
                    tried_candidates.append({
                        "type": "ai_fallback",
                        "bytes": secondary_raw,
                        "relevance_score": float(vlm_judge.get("relevance_score") or 0.0),
                        "artifact_score": float(vlm_judge.get("artifact_score") or 1.0),
                        "severe_failure": bool(vlm_judge.get("severe_failure") or False),
                        "extension": ".png",
                        "meta": {
                            "status": "saved_ai_fallback",
                            "ai_fallback_provider": "secondary_generate_api"
                        }
                    })
                vlm_pass = bool(vlm_judge and vlm_judge.get("pass"))
                if (clip_score is None or clip_score >= float(IMAGE_CLIP_MIN_SCORE)) and vlm_pass:
                    dest = IMAGE_DIR / f"{task_id}_{idx}_ai_fallback.png"
                    dest.write_bytes(secondary_raw)
                    image_path = str(dest.resolve())
                    debug_record["status"] = "saved_ai_fallback"
                    debug_record["image_path"] = image_path
                    debug_record["response_len"] = len(secondary_raw)
                    debug_record["ai_fallback_provider"] = "secondary_generate_api"
                    saved = True
                    print(f"[slide_images] slide {idx} saved via secondary AI fallback")
                else:
                    if clip_score is not None and clip_score < float(IMAGE_CLIP_MIN_SCORE):
                        print(
                            f"[slide_images] slide {idx} secondary AI fallback rejected by CLIP "
                            f"(score={clip_score:.3f} < {float(IMAGE_CLIP_MIN_SCORE):.3f})"
                        )
                        debug_record["ai_fallback_rejection"] = f"clip_mismatch (score={clip_score:.3f})"
                    elif vlm_judge is not None and not vlm_judge.get("pass"):
                        print(
                            f"[slide_images] slide {idx} secondary AI fallback rejected by VLM "
                            f"(relevance={vlm_judge.get('relevance_score')}, "
                            f"artifact={vlm_judge.get('artifact_score')})"
                        )
                        debug_record["ai_fallback_rejection"] = f"vlm_reject (relevance={vlm_judge.get('relevance_score')}, artifact={vlm_judge.get('artifact_score')})"
                    elif vlm_judge is None:
                        print(f"[slide_images] slide {idx} secondary AI fallback rejected: VLM judge unavailable")
                        debug_record["ai_fallback_rejection"] = "vlm_unavailable"
            else:
                print(
                    f"[slide_images] slide {idx} secondary AI fallback rejected "
                    f"(reasons={validation.get('reasons')})"
                )
                debug_record["ai_fallback_rejection"] = f"output_validation_failed (reasons={validation.get('reasons')})"
        else:
            print(f"[slide_images] slide {idx} secondary AI fallback returned no usable image")
            debug_record["ai_fallback_rejection"] = "returned no usable image"

    # Fallback to stock photo
    if not saved:
        if should_stop is not None and await should_stop():
            return None, None
        async def _external_vlm_validate(img_bytes: bytes, meta: Dict[str, Any]) -> bool:
            vlm_judge_res = await _vlm_judge_image(
                client,
                image_bytes=img_bytes,
                prompt=full_prompt,
                slide=slide,
                semantic=semantic,
                min_relevance=0.45,
                is_stock_photo=True,
            )
            vlm_judge_dict = vlm_judge_res if vlm_judge_res is not None else {
                "relevance_score": 0.0,
                "artifact_score": 1.0,
                "style_match_score": 0.0,
                "reasons": ["VLM judge timed out or failed; rejecting unverified fallback"],
                "pass": False,
                "severe_failure": True,
            }
            meta["vlm_judge"] = vlm_judge_dict
            tried_candidates.append({
                "type": "external",
                "bytes": img_bytes,
                "relevance_score": float(vlm_judge_dict.get("relevance_score") or 0.0),
                "artifact_score": float(vlm_judge_dict.get("artifact_score") or 1.0),
                "severe_failure": bool(vlm_judge_dict.get("severe_failure") or False),
                "extension": str(meta.get("extension") or ".jpg"),
                "meta": {
                    "status": "saved_external_fallback",
                    "external_source": meta.get("source"),
                    "external_query": meta.get("query"),
                    "external_page_url": meta.get("page_url"),
                    "external_vlm_judge": vlm_judge_dict,
                    "external_license": meta.get("license"),
                    "external_license_url": meta.get("license_url"),
                    "external_author": meta.get("author")
                }
            })
            return bool(vlm_judge_dict.get("pass"))

        external = await _try_stock_photo_fallback(
            client,
            slide,
            semantic,
            content_type,
            risk,
            vlm_validate_fn=_external_vlm_validate,
        )
        if not external:
            external_candidates = [c for c in tried_candidates if c.get("type") == "external"]
            if external_candidates:
                external_candidates.sort(key=lambda c: (not c.get("severe_failure", False), c.get("relevance_score", 0.0)), reverse=True)
                best_c = external_candidates[0]
                best_vlm = ((best_c.get("meta") or {}).get("external_vlm_judge") or {})
                if best_c.get("relevance_score", 0.0) >= 0.30 and bool(best_vlm.get("pass")):
                    print(f"[slide_images] slide {idx} recovering best stock candidate with relevance={best_c.get('relevance_score')}")
                    external = {
                        "bytes": best_c["bytes"],
                        "extension": best_c["extension"],
                        **best_c["meta"]
                    }

        if external:
            validation = _validate_output_image(external["bytes"], prompt_text=full_prompt, strict=False)
            debug_record["external_output_validation"] = validation
            if not validation.get("ok"):
                debug_record["status"] = "external_output_validation_failed"
                if last_error and not debug_record.get("error"):
                    debug_record["error"] = last_error
                print(
                    f"[slide_images] slide {idx} external fallback rejected "
                    f"(reasons={validation.get('reasons')})"
                )
            else:
                print(
                    f"[slide_images] slide {idx} found valid external fallback candidate "
                    f"(source={external.get('source')}, query={external.get('query')})"
                )
                ext = str(external.get("extension") or ".jpg").lower()
                if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
                    ext = ".jpg"
                dest = IMAGE_DIR / f"{task_id}_{idx}_external{ext}"
                dest.write_bytes(external["bytes"])
                image_path = str(dest.resolve())
                debug_record["status"] = "saved_external_fallback"
                debug_record["image_path"] = image_path
                debug_record["response_len"] = len(external["bytes"])
                debug_record["external_source"] = external.get("source")
                debug_record["external_query"] = external.get("query")
                debug_record["external_page_url"] = external.get("page_url")
                debug_record["external_vlm_judge"] = external.get("external_vlm_judge") or external.get("vlm_judge")
                debug_record["external_license"] = external.get("license")
                debug_record["external_license_url"] = external.get("license_url")
                debug_record["external_author"] = external.get("author")
                saved = True
        else:
            debug_record["external_fallback_rejection"] = "no stock photo found"
            if not debug_record.get("status") or debug_record["status"] == "pending":
                debug_record["status"] = "failed"
            if last_error and not debug_record.get("error"):
                debug_record["error"] = last_error
 
    # Do not recover failed candidates. If they failed validation, leave the slide without an image.
    if not saved:
        debug_record["status"] = "failed_validation"
        if last_error and not debug_record.get("error"):
            debug_record["error"] = last_error
        print(f"[slide_images] slide {idx} failed all validations. No image will be included.")

    return image_path, debug_record


async def build_image_paths_for_slides(
    content_extractor,
    structured: Dict[str, Any],
    task_id: str,
    *,
    chart_specs: Optional[Dict[int, Dict[str, Any]]] = None,
    table_specs: Optional[Dict[int, Dict[str, Any]]] = None,
    image_limit: Optional[int] = None,
    progress_cb: Optional[Any] = None,
    should_stop: Optional[Any] = None,
    plan: str = "pro",
) -> Dict[int, str]:
    import asyncio
    plan_tier = (plan or "pro").strip().lower()
    base = (IMAGE_GEN_API_BASE_URL or "").strip().rstrip("/")
    # Free tier uses stock photos only — no AI generation API needed
    if not base and plan_tier != "free":
        print("[slide_images] skip: IMAGE_GEN_API_BASE_URL is empty")
        return {}
    if not base and plan_tier == "free":
        print("[slide_images] plan=free: IMAGE_GEN_API_BASE_URL empty but stock photos still attempted")

    slides = structured.get("slides") or []
    if not slides:
        return {}

    configured_limit = max(1, IMAGE_MAX_SLIDES_WITH_IMAGES)
    if image_limit is not None:
        configured_limit = min(configured_limit, max(0, int(image_limit)))
    if configured_limit <= 0:
        print("[slide_images] skip: image_limit <= 0")
        return {}
    n = min(len(slides), configured_limit)
    print(f"[slide_images] POST {base}/generate - {n} slide(s) in parallel (concurrency={IMAGE_GEN_CONCURRENCY})")

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
        negative = _merge_negative_prompt(_CORE_NEGATIVE_TERMS, negative, max_words=42)

    timeout = httpx.Timeout(IMAGE_GEN_TIMEOUT_SEC, connect=30.0)
    url = f"{base}/generate"
    deck_title = str(structured.get("title") or "").strip()

    concurrency = max(1, IMAGE_GEN_CONCURRENCY)
    sem = asyncio.Semaphore(concurrency)
    done_count = 0
    progress_lock = asyncio.Lock()




    async with httpx.AsyncClient(timeout=timeout) as client:
        async def worker(idx: int):
            if should_stop is not None and await should_stop():
                return idx, None, None
            async with sem:
                if should_stop is not None and await should_stop():
                    return idx, None, None
                try:
                    path, debug_rec = await _process_single_slide(
                        idx=idx,
                        client=client,
                        content_extractor=content_extractor,
                        structured=structured,
                        slides=slides,
                        table_specs=table_specs,
                        chart_specs=chart_specs,
                        deck_title=deck_title,
                        task_id=task_id,
                        base=base,
                        headers=headers,
                        negative=negative,
                        url=url,
                        should_stop=should_stop,
                        plan_tier=plan_tier,
                    )
                    nonlocal done_count
                    async with progress_lock:
                        done_count += 1
                        if progress_cb is not None:
                            try:
                                await progress_cb(done_count, n)
                            except Exception:
                                pass
                    return idx, path, debug_rec
                except Exception as e:
                    print(f"[slide_images] Task exception for slide {idx}: {e}")
                    return idx, None, None

        tasks = [worker(i) for i in range(n)]
        results = await asyncio.gather(*tasks)

    # Sort results to maintain slide index order in debug records and output
    results.sort(key=lambda x: x[0])
    for idx, path, debug_rec in results:
        if path:
            out[idx] = path
        if debug_rec:
            debug_records.append(debug_rec)

    print(f"[slide_images] done: {len(out)}/{n} images saved to {IMAGE_DIR}")
    _write_debug_json(task_id, "images", debug_records)
    _write_image_quality_report(task_id, debug_records)
    return out
