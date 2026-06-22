from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from services.content.prompts import (
    ANTI_TRUNCATION_TOKEN_RULE,
    MAX_BULLETS_PER_SLIDE,
    MAX_WORDS_PER_BULLET,
)

# Config flags used by pipeline steps â€” imported lazily to avoid circular deps.
# These are resolved at runtime via the enclosing ContentExtractor's module scope.
try:
    from config import (
        LLM_REFINE_EXTRA_IF_TRUNCATED,
        LLM_REFINE_MAX_EXTRA_PASSES,
        LLM_BULLET_POLISH_PASS,
        LLM_FINAL_QUALITY_GATE,
        LLM_FINAL_QUALITY_GATE_MAX_FIXES,
        LLM_FINAL_DENSITY_GATE,
        LLM_FINAL_DENSITY_MIN_BULLETS,
        LLM_FINAL_DENSITY_MAX_REWRITES,
    )
except Exception:
    LLM_REFINE_EXTRA_IF_TRUNCATED = False
    LLM_REFINE_MAX_EXTRA_PASSES = 1
    LLM_BULLET_POLISH_PASS = True
    LLM_FINAL_QUALITY_GATE = True
    LLM_FINAL_QUALITY_GATE_MAX_FIXES = 12
    LLM_FINAL_DENSITY_GATE = True
    LLM_FINAL_DENSITY_MIN_BULLETS = 3
    LLM_FINAL_DENSITY_MAX_REWRITES = 10


class SlidePipelineMixin:
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
            "- Each slide MUST have 3â€“4 bullets.\n"
            "- Never fewer than 3 bullets.\n"
            "- If the section is thin, invent substantive expansion (still faithful to the topic).\n\n"
            "3) BULLET QUALITY:\n"
            "- Each bullet MUST be a detailed, rich, complete sentence of 15 to 25 words (Vietnamese/English).\n"
            "- Do NOT write short, fragmented bullet points or labels (e.g. write a full sentence, not just a keyword phrase).\n"
            "- No fake endings like \"...\", \"vÃ .\", \"bao gá»“m.\" before the idea is finished.\n"
            "- Each bullet MUST explain the context, the core action/event, and its outcome, result, or significance.\n\n"
            "CRITICAL:\n"
            "- Explain the idea fully and academicallyâ€”do not write shallow or overly brief points.\n"
            "- Avoid generic statements. Use concrete information to fill the slide space professionally.\n\n"
            "ANTI-TRUNCATION:\n"
            "- NEVER end a sentence unfinished.\n"
            "- NEVER output incomplete phrases.\n"
            "- If you are near the token limit: end the current bullet with a period, then output fewer bullets per slide if needed, and ALWAYS close valid JSON.\n\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + "\n"
            "4) ANTI-LAZY:\n"
            "- No keyword-only bullets; write full explanatory sentences.\n\n"
            "4b) SPEAKER NOTES:\n"
            "- Fill notes with a natural presenter script for each slide, 45-90 words, same language as the slide.\n"
            "- Do not repeat bullets verbatim; explain how the presenter should talk through the slide.\n\n"
            "5) STRUCTURE:\n"
            "- Group related points on the same slide.\n"
            "- No \"(continued)\" / \"(tiáº¿p)\" slides.\n\n"
            "5b) SLIDE TITLES:\n"
            "- Each slide title must be specific, descriptive, and meaningful (3-8 words).\n"
            "- NEVER use generic placeholder titles like 'Ná»™i dung', 'Ná»™i dung X', 'Slide X', 'Tiáº¿p theo', or similar.\n\n"
            "6) NO REPETITION:\n"
            "- Different slides must add different information.\n\n"
            + high_slide_block
            + self._output_language_instruction()
            + "OUTPUT: JSON only. Schema:\n"
            "{\"title\":\"...\",\"slides\":[{\"title\":\"...\",\"bullets\":[\"...\",\"...\",\"...\"],\"notes\":\"speaker script\"}]}\n"
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
        target_slides = max(5, int(target_slides or 10))
        if len(sections) > target_slides:
            original_count = len(sections)
            merged_sections: List[Dict[str, str]] = []
            for bucket_idx in range(target_slides):
                start = round(bucket_idx * original_count / target_slides)
                end = round((bucket_idx + 1) * original_count / target_slides)
                group = sections[start:end] or [sections[min(bucket_idx, original_count - 1)]]
                title = str(group[0].get("title") or f"Section {bucket_idx + 1}").strip()
                content_parts: List[str] = []
                for sec in group:
                    sec_title = str(sec.get("title") or "").strip()
                    sec_content = str(sec.get("content") or "").strip()
                    if sec_title:
                        content_parts.append(sec_title)
                    if sec_content:
                        content_parts.append(sec_content)
                merged_sections.append(
                    {
                        "title": title,
                        "content": "\n\n".join(content_parts).strip(),
                    }
                )
            print(
                f"[slide_pipeline] merged sections for target slides: "
                f"{original_count} -> {len(merged_sections)}"
            )
            sections = merged_sections
        # Allocate slide count per section proportionally by content length.
        lengths = [max(50, len(s.get("content") or "")) for s in sections]
        total = sum(lengths)
        alloc = [max(1, round(target_slides * l / total)) for l in lengths]
        # Adjust to exact total.
        diff = target_slides - sum(alloc)
        idx = 0
        while diff != 0 and alloc:
            if diff < 0 and all(x <= 1 for x in alloc):
                break
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
                    fallback_text = "\n\n".join(
                        str(x).strip()
                        for x in (sec.get("title"), sec.get("content"))
                        if str(x or "").strip()
                    )
                    try:
                        fallback = self._fallback_structure(fallback_text)
                        fallback_slides = fallback.get("slides") or []
                        if n and len(fallback_slides) > int(n):
                            fallback["slides"] = fallback_slides[: int(n)]
                        return self._normalize_structured_content(fallback)
                    except Exception as fallback_error:
                        print(
                            f"Section fallback generation failed ({sec.get('title')!r}): {fallback_error}"
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

        if not slides_all:
            fallback_text = "\n\n".join(
                str(x).strip()
                for sec in sections
                for x in (sec.get("title"), sec.get("content"))
                if str(x or "").strip()
            )
            fallback = self._fallback_structure(fallback_text)
            return self._normalize_structured_content(fallback)

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
            "- Each bullet MUST be a detailed, rich, complete sentence of 15 to 25 words. Avoid overly short or paragraph-like bullets.\n"
            "- Valid JSON and fully closed sentences matter more than making every bullet longerâ€”do not \"expand\" length at the expense of truncation or broken JSON.\n"
            "- Each bullet: context + explanation + impact or significanceâ€”in rich wording.\n"
            "- Rewrite shallow/short bullets into clear complete statements of 15-25 words; fix vague bullets with concrete detail.\n"
            "- Ensure each bullet carries meaningful informationâ€”not filler or labels.\n"
            "- Fix thin or broken bullets; do not only fix spelling.\n"
            "- Merge slides with fewer than 2 bullets into the previous slide.\n"
            "- Each slide should have 3â€“4 bullets.\n"
            "- Remove duplication.\n"
            "- No \"(continued)\" / \"(tiáº¿p)\" slides.\n"
            "- SLIDE TITLES: Rewrite any generic slide title (such as 'Nội dung', 'Nội dung 1', 'Slide 1', 'Tiếp theo', or similar placeholders) into a specific, meaningful, descriptive title derived from the slide's bullet points.\n\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + "\n"
            + self._output_language_instruction()
            + "Return ONLY JSON. Schema:\n"
            "{\"title\":\"...\",\"slides\":[{\"title\":\"...\",\"bullets\":[\"...\"],\"notes\":\"speaker script\"}]}\n"
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
        has_slides = isinstance(refined, dict) and isinstance(refined.get("slides"), list) and len(refined.get("slides")) > 0
        return self._normalize_structured_content(refined if has_slides else structured)

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
        structured = self._canonicalize_continued_titles(structured)
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

    def _strip_continued_suffix(self, title: str) -> str:
        t = (title or "").strip()
        if not t:
            return t
        pattern = re.compile(
            r"\s*\([^)]*(?:tiếp|tiep|continued|cont\.?|tiáº|tiÃ|tiÃ¡)[^)]*\)\s*$",
            flags=re.IGNORECASE,
        )
        prev = None
        while t and prev != t:
            prev = t
            t = pattern.sub("", t).strip()
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
            "- Each bullet must be a detailed, complete sentence of 15 to 25 words.\n"
            "- Each bullet must explain context, action, and significance/result.\n"
            "- Do not write short keyword-only phrases or fragmented labels.\n"
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

    # -----------------------------
    # FINAL SPEC: Title repair (LLM semantic check)
    # -----------------------------

    def _build_title_repair_messages(self, structured: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build prompt để LLM review tiêu đề từng slide và sửa nếu generic/không khớp nội dung."""
        slides = structured.get("slides") or []
        compact = []
        for i, s in enumerate(slides):
            if not isinstance(s, dict):
                continue
            bullets = [str(b).strip() for b in (s.get("bullets") or [])[:3] if str(b).strip()]
            compact.append({"index": i, "title": str(s.get("title") or ""), "bullets": bullets})
        payload = json.dumps(compact, ensure_ascii=False)
        system_msg = (
            self._llm_system_prefix()
            + "You are a slide title quality reviewer.\n\n"
            "TASK: For each slide, decide if the title is GOOD or needs REWRITING.\n\n"
            "REWRITE the title if it:\n"
            "- Contains continuation markers like '(tiếp)', '(tiep)', '(continued)', or repeats the same base title as another slide.\n"
            "- Is a generic placeholder: 'Nội dung', 'Nội dung 1', 'Slide 1', 'Tiêu đề', "
            "'Tiếp theo', 'Content', 'Title', 'Untitled', 'Next', or any numbered variant "
            "(Phần 2, Chương 3, Section 4...).\n"
            "- Does NOT reflect what the bullets actually describe (semantically mismatched).\n\n"
            "KEEP the title if it:\n"
            "- Is specific and matches the bullet content — even short titles like 'Kết luận', "
            "'Giới thiệu', 'Tổng quan' are fine when the bullets support them.\n\n"
            "New title: 3-8 words, specific, derived from the bullet content, same language as bullets.\n\n"
            + self._output_language_instruction()
            + "Return ONLY JSON listing slides that need a new title:\n"
            "{\"fixes\": [{\"index\": 0, \"title\": \"New specific title\"}]}\n"
            "If all titles are already good, return {\"fixes\": []}.\n"
        )
        user_msg = (
            "Review these slide titles against their bullets:\n\n"
            f"{payload}\n\n"
            "Return JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    def _canonicalize_continued_titles(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        slides = structured.get("slides") if isinstance(structured, dict) else None
        if not isinstance(slides, list):
            return structured
        title_counts: Dict[str, int] = {}
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            base_title = self._strip_continued_suffix(str(slide.get("title") or "Nội dung"))
            title_counts[base_title] = title_counts.get(base_title, 0) + 1
            count = title_counts[base_title]
            slide["title"] = base_title if count == 1 else f"{base_title} - Phần {count}"
        final_seen_titles: set[str] = set()
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            current_title = str(slide.get("title") or "").strip()
            key = re.sub(r"\W+", " ", current_title.lower()).strip()
            if " - Ph" in current_title or key in final_seen_titles:
                slide["title"] = self._derive_slide_title_from_bullets(
                    slide.get("bullets") or [],
                    fallback=current_title,
                )
                key = re.sub(r"\W+", " ", str(slide.get("title") or "").lower()).strip()
            final_seen_titles.add(key)
        return structured

    async def _repair_slide_titles(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        """Dùng LLM để phát hiện và sửa tiêu đề slide generic hoặc không khớp nội dung."""
        structured = self._canonicalize_continued_titles(structured)
        slides = structured.get("slides") or []
        if not slides:
            return structured
        try:
            msgs = self._build_title_repair_messages(structured)
            data = await self._request_json_dict(
                msgs,
                target_slides=len(slides),
                fast_mode=True,
                compose_mode=False,
                structured_output="fixes",
            )
            fixes = data.get("fixes") if isinstance(data, dict) else None
            if not isinstance(fixes, list) or not fixes:
                return structured
            fix_map: Dict[int, str] = {}
            for fix in fixes:
                if not isinstance(fix, dict):
                    continue
                idx = fix.get("index")
                new_title = str(fix.get("title") or "").strip()
                if isinstance(idx, int) and new_title and 0 <= idx < len(slides):
                    fix_map[idx] = new_title
            if not fix_map:
                return structured
            import copy
            result = copy.deepcopy(structured)
            for idx, new_title in fix_map.items():
                old = slides[idx].get("title", "")
                result["slides"][idx]["title"] = new_title
                print(f"[title_repair] slide {idx}: {old!r} → {new_title!r}")
            return self._canonicalize_continued_titles(result)
        except Exception as e:
            print(f"[title_repair] skipped (error): {e}")
            return self._canonicalize_continued_titles(structured)



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
        print("[slide_pipeline] expand start")
        expanded = await self._expand_content_final(
            merged_summary["content"], target_slides=target_slides
        )
        print(f"[slide_pipeline] expand done chars={len(str(expanded or ''))}")
        print("[slide_pipeline] group start")
        sections = await self._group_content_final(expanded)
        print(f"[slide_pipeline] group done sections={len(sections or [])}")
        print("[slide_pipeline] generate sections start")
        structured = await self._generate_slides_for_sections(
            sections, target_slides=target_slides
        )
        print(
            f"[slide_pipeline] generate sections done slides={len((structured or {}).get('slides') or [])}"
        )
        try:
            print("[slide_pipeline] refine start")
            structured = await self._refine_deck_with_optional_second(structured)
            print("[slide_pipeline] targeted repair start")
            structured = await self._repair_truncated_bullets_targeted(structured)
            if LLM_BULLET_POLISH_PASS:
                print("[slide_pipeline] bullet polish start")
                structured = await self._polish_slide_bullets_quality(structured)
                print("[slide_pipeline] bullet polish done")
            if LLM_FINAL_QUALITY_GATE:
                print("[slide_pipeline] final quality gate start")
                structured = await self._run_final_quality_gate(structured)
                print("[slide_pipeline] final quality gate done")
            if LLM_FINAL_DENSITY_GATE:
                print("[slide_pipeline] final density gate start")
                structured = await self._run_final_density_gate(structured)
                print("[slide_pipeline] final density gate done")
        except Exception:
            print("[slide_pipeline] refine path failed; fallback refine start")
            structured = await self._refine_slides_final(structured)
            structured = await self._repair_truncated_bullets_targeted(structured)
            if LLM_BULLET_POLISH_PASS:
                print("[slide_pipeline] fallback bullet polish start")
                structured = await self._polish_slide_bullets_quality(structured)
                print("[slide_pipeline] fallback bullet polish done")
            if LLM_FINAL_QUALITY_GATE:
                print("[slide_pipeline] fallback final quality gate start")
                structured = await self._run_final_quality_gate(structured)
                print("[slide_pipeline] fallback final quality gate done")
            if LLM_FINAL_DENSITY_GATE:
                print("[slide_pipeline] fallback final density gate start")
                structured = await self._run_final_density_gate(structured)
                print("[slide_pipeline] fallback final density gate done")
        print("[slide_pipeline] title repair start")
        structured = await self._repair_slide_titles(structured)
        print("[slide_pipeline] title repair done")
        print(
            f"[slide_pipeline] done slides={len((structured or {}).get('slides') or [])}"
        )
        return self._normalize_structured_content(structured)
