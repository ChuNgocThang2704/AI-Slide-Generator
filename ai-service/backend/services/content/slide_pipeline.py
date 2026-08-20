from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from services.content.prompts import (
    ANTI_TRUNCATION_TOKEN_RULE,
    MAX_BULLETS_PER_SLIDE,
    MAX_WORDS_PER_BULLET,
    MIN_WORDS_PER_BULLET,
    BULLET_WORD_RANGE,
    SLIDE_DECK_JSON_SCHEMA,
    SECTIONS_JSON_SCHEMA,
    BULLET_JSON_SCHEMA,
    BULLETS_JSON_SCHEMA,
)
from services.lecture_quality import lecture_prompt_block

# Các cờ cấu hình được sử dụng bởi các bước xử lý — được import trễ để tránh lỗi vòng lặp phụ thuộc.
# Các cấu hình này được giải quyết lúc chạy chương trình thông qua phạm vi mô-đun ContentExtractor.
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

    def _user_instruction_block(self) -> str:
        """Trả về khối hướng dẫn của người dùng để inject vào system prompt nếu có."""
        instruction = getattr(self, "_user_instruction", None)
        blocks: List[str] = []
        if getattr(self, "_lecture_mode", False):
            blocks.append(lecture_prompt_block())
        if instruction and str(instruction).strip():
            blocks.append(
                f"USER REQUIREMENT (Apply this to guide the slide structure and focus. "
                f"Do NOT create a slide about this requirement itself):\n"
                f"{str(instruction).strip()}\n\n"
            )
        return "".join(blocks)

    def _build_expand_messages(self, content: str, enable_deep: bool) -> List[Dict[str, str]]:
        """Bước mở rộng (Expansion step): BẮT BUỘC phải mở rộng (không tóm tắt). Đầu ra: {"expanded_text": "..."}"""
        normalized = self._normalize_for_llm(content or "")
        preview = normalized[:7000] if len(normalized) > 7000 else normalized
        deep_rule = (
            "- Target slide count is high: expand deeply—split into sub-ideas, add why/how, impact, and examples.\n"
            if enable_deep
            else "- Expand enough: add why/how, impact, and examples where appropriate.\n"
        )
        system_msg = self._llm_system_prefix() + (
            "You are an expert educator.\n\n"
            "TASK: EXPAND the source material into a richer, more detailed version.\n\n"
            + self._user_instruction_block()
            + "REQUIREMENTS:\n"
            "- Explain and clarify concepts.\n"
            "- Add reasoning, consequences, and significance.\n"
            "- Add examples when possible.\n"
            "- Break large ideas into smaller points suitable for slides.\n\n"
            "CRITICAL:\n"
            "- DO NOT summarize. Do not compress.\n"
            "- DO NOT shorten. The expanded_text must be LONGER and richer than the input.\n"
            "- Expand every idea into deeper explanation—not a light touch.\n"
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
        if getattr(self, "_is_document_mode", False):
            print("[pipeline] document mode: skip LLM expand step to preserve original terminology")
            return content or ""
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
        """Bước nhóm nội dung (Grouping step): Đầu ra JSON {"sections":[{"title":"...","content":"..."}]}"""
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
        try:
            data = await self._request_json_dict(
                msgs,
                target_slides=10,
                fast_mode=True,
                compose_mode=False,
                structured_output="sections",
            )
        except Exception as exc:
            print(
                "[slide_pipeline] group JSON failed; "
                f"using heading/paragraph fallback. Error: {exc}"
            )
            chunks = self._split_by_headings(expanded_text or "")
            fallback: List[Dict[str, str]] = []
            for index, chunk in enumerate(chunks):
                lines = [line.strip() for line in str(chunk or "").splitlines() if line.strip()]
                if not lines:
                    continue
                first = lines[0]
                heading = first.lstrip("#").strip()
                has_heading = first.startswith("#")
                content_lines = lines[1:] if has_heading else lines
                content = "\n".join(content_lines).strip() or first
                title = heading if has_heading else f"Phần {index + 1}"
                fallback.append({"title": title[:80], "content": content})
            if fallback:
                return fallback
            return [{"title": "Nội dung", "content": str(expanded_text or "").strip()}]
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
        title = str(section.get("title") or "Nội dung").strip()
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
            + self._user_instruction_block()
            + self._presentation_style_block(n_slides)
            + "RULES:\n"
            "1) CONTENT EXPANSION:\n"
            "- Go beyond the source: add explanation, reasoning, and supporting detail—not paraphrase only.\n"
            "- Do not summarize away substance.\n\n"
            "2) SLIDE DENSITY:\n"
            "- Each slide MUST have 3–4 bullets.\n"
            "- Never fewer than 3 bullets.\n"
            "- Keep visible slide copy near 500 characters; never exceed roughly 760 characters on a slide that "
            "uses an image. Put secondary explanation in speaker notes instead of shrinking the slide text.\n"
            "- If the section is thin, expand with stable conceptual explanation, definitions, relationships, "
            "or clearly framed teaching examples that remain faithful to the topic.\n"
            "- Never invent statistics, percentages, dates, named studies, measured outcomes, quotations, "
            "or document-specific claims. Use a numeric example only when the user explicitly allows "
            "illustrative/sample/simulated data, and label it as illustrative.\n\n"
            "3) BULLET QUALITY:\n"
            f"- Each bullet MUST be a detailed, rich, complete sentence of {BULLET_WORD_RANGE} words (Vietnamese/English).\n"
            "- Do NOT write short, fragmented bullet points or labels (e.g. write a full sentence, not just a keyword phrase).\n"
            "- No fake endings like \"...\", \"và.\", \"bao gồm.\" before the idea is finished.\n"
            "- Each bullet MUST explain the context, the core action/event, and its outcome, result, or significance.\n"
            "- SPECIFICITY (CRITICAL): Preserve technical terms, function names, algorithm names, numbers, measurements, and domain-specific vocabulary from the source. Every bullet must contain at least one concrete detail—never write generic filler sentences.\n\n"
            "3b) DECK TITLE:\n"
            "- The top-level 'title' in your JSON must describe the WHOLE section topic comprehensively.\n"
            "- NEVER use chapter/section headings like 'Mở đầu', 'Giới thiệu', 'Introduction', or 'Chapter 1' as the title.\n"
            "- If the section is introductory, name the topic it introduces (e.g. 'Phân mảnh Dữ liệu PostgreSQL' not 'Mở đầu').\n\n"
            "CRITICAL:\n"
            "- Explain the idea fully and academically—do not write shallow or overly brief points.\n"
            "- Avoid generic statements. Use concrete technical information to fill the slide space professionally.\n\n"
            "ANTI-TRUNCATION:\n"
            "- NEVER end a sentence unfinished.\n"
            "- NEVER output incomplete phrases.\n"
            "- If you are near the token limit: end the current bullet with a period, then output fewer bullets per slide if needed, and ALWAYS close valid JSON.\n\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + "\n"
            "4) ANTI-LAZY:\n"
            "- No keyword-only bullets; write full explanatory sentences.\n\n"
            "4b) SPEAKER NOTES:\n"
            "- Write 70-120 words of ready-to-speak presenter narration for every slide, in the slide's language.\n"
            "- Ground every statement in that slide's title, bullets, numbers, table, or chart; never invent facts.\n"
            "- Explain meaning, significance, and relationships instead of reading bullets verbatim.\n"
            "- Do not use meta narration such as 'Slide này giới thiệu/trình bày...' or 'This slide presents...'.\n"
            "- End with a short, natural bridge to the next idea when appropriate; do not mention slide numbers.\n\n"
            "5) STRUCTURE:\n"
            "- Group related points on the same slide.\n"
            "- When content naturally contains categories, stages, criteria, or techniques, expose hierarchy with "
            "2-4 bullets in 'Short label: complete explanation' form. Do not force labels onto a simple narrative.\n"
            "- Never present a long flat list of equally weighted details; retain the main ideas visibly and move "
            "supporting detail to speaker notes.\n"
            "- No \"(continued)\" / \"(tiếp)\" slides.\n\n"
            "5b) SLIDE TITLES:\n"
            "- Each slide title must be specific, descriptive, and meaningful (3-8 words).\n"
            "- NEVER use generic placeholder titles like 'Nội dung', 'Nội dung X', 'Slide X', 'Tiếp theo', or similar.\n\n"
            "5c) SLIDE LAYOUT SELECTION:\n"
            "- Assign a layout for each slide based on its content pattern:\n"
            "  * 'intro': Use ONLY for title slide, cover page, or team/member introduction slide.\n"
            "  * 'timeline': Use when slide content describes sequential steps, stages, roadmap, history, or a chronological workflow.\n"
            "  * 'split_columns': Use when comparing options, pros/cons, before/after, or listing parallel components.\n"
            "  * 'big_quote': Use when presenting a singular key quote, vision statement, or main focal slogan.\n"
            "  * 'text_image': Use when the slide explains visual concepts, physical items, design mockups, or needs a supporting illustration.\n"
            "  * 'text_chart': Use when the slide has numeric data, performance metrics, growth rates, or comparisons suitable for charts.\n"
            "  * 'text_table': Use when the slide lists attributes, feature grids, option matrices, or distinct categories suitable for a table.\n"
            "  * 'normal': Standard text layout for typical bullet points.\n\n"
            "6) NO REPETITION:\n"
            "- Different slides must add different information.\n\n"
            + high_slide_block
            + self._output_language_instruction()
            + "OUTPUT: JSON only. Schema:\n"
            "{\"title\":\"...\",\"presentation_mode\":\"presentation|lecture\",\"learning_objectives\":[\"...\"],"
            "\"slides\":[{\"title\":\"...\",\"bullets\":[\"...\",\"...\",\"...\"],\"notes\":\"speaker script\","
            "\"layout\":\"intro|timeline|split_columns|text_image|normal|thankyou\",\"pedagogical_role\":\"concept\","
            "\"source_pages\":[1]}]}\n"
        )
        user_msg = (
            f"SECTION TOPIC: {title}\n\n"
            f"SECTION SOURCE TEXT:\n{preview}\n\n"
            "Return JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def _generate_slides_for_sections(self, sections: List[Dict[str, str]], target_slides: int) -> Dict[str, Any]:
        """Tạo slide theo từng phần (section), sau đó gộp lại."""
        if not sections:
            # Dự phòng: coi toàn bộ nội dung như là một phần duy nhất.
            sections = [{"title": "Nội dung", "content": ""}]
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
        # Phân bổ số lượng slide cho từng phần tỷ lệ thuận theo độ dài nội dung.
        lengths = [max(50, len(s.get("content") or "")) for s in sections]
        total = sum(lengths)
        alloc = [max(1, round(target_slides * l / total)) for l in lengths]
        # Hard-cap: section có content gốc ngắn (< 300 chars) → tối đa 1 slide,
        # tránh expand làm phồng "Lời cảm ơn" hoặc các section lễtản khác.
        _SHORT_SECTION_CHARS = 300
        alloc = [
            min(a, 1 if len(str(s.get("content") or "")) < _SHORT_SECTION_CHARS else 999)
            for a, s in zip(alloc, sections)
        ]
        # Tái điều chỉnh tổng sau hard-cap
        diff = target_slides - sum(alloc)
        idx = 0
        while diff != 0 and alloc:
            if diff < 0 and all(x <= 1 for x in alloc):
                break
            i = idx % len(alloc)
            # Chỉ tăng slide cho section không bị hard-cap
            content_len = len(str(sections[i].get("content") or ""))
            if diff > 0 and content_len >= _SHORT_SECTION_CHARS:
                alloc[i] += 1
                diff -= 1
            elif diff < 0 and alloc[i] > 1:
                alloc[i] -= 1
                diff += 1
            idx += 1
            if idx > len(alloc) * 10:
                break

        # Tổng hợp tiêu đề bao quát từ các section thay vì lấy tiêu đề section đầu
        _INTRO_TITLES = {"mở đầu", "giới thiệu", "introduction", "chapter 1", "chương 1", "overview", "tổng quan"}
        all_section_titles = [str(s.get("title") or "").strip() for s in sections if str(s.get("title") or "").strip()]
        # Chọn tiêu đề bao quát: ưu tiên section không phải "Mở đầu" + join các chủ đề chính
        meaningful_titles = [t for t in all_section_titles if t.lower() not in _INTRO_TITLES]
        if meaningful_titles:
            # Lấy tối đa 2 tiêu đề chính để ghép thành deck title bao quát
            deck_title = " — ".join(meaningful_titles[:2]) if len(meaningful_titles) >= 2 else meaningful_titles[0]
        elif all_section_titles:
            deck_title = all_section_titles[0]
        else:
            deck_title = "Bài thuyết trình"

        slides_all: List[Dict[str, Any]] = []
        # Song song hóa theo section (giới hạn 3 request cùng lúc để tránh quá tải vLLM 1 GPU).
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
        seen_keys: set = set()
        for part_norm in results:
            if part_norm and isinstance(part_norm.get("slides"), list):
                for slide in (part_norm.get("slides") or []):
                    if not isinstance(slide, dict):
                        continue
                    deduped = []
                    for b in (slide.get("bullets") or []):
                        # Chuẩn hóa để so khớp tương đồng (bỏ dấu cách, chữ thường)
                        key = re.sub(r'\W+', ' ', str(b).lower().strip())[:80]
                        if key not in seen_keys:
                            deduped.append(b)
                            seen_keys.add(key)
                    slide["bullets"] = deduped or slide.get("bullets", [])
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
            "- For each bullet: if a reader cannot answer what happens next, what the concrete referent is, or what the conclusion is—rewrite until complete. Do not patch with fixed phrases; fix any domain.\n"
            "- Fix truncated or incomplete sentences (even if they end with a period): no missing complements after prepositions; no fake endings like \"...\", \"và.\", \"bao gồm.\".\n"
            "- Vietnamese: never end a bullet with only a function word + period (invalid: \"của.\", \"cho.\", \"với.\", \"từ.\", \"như.\", \"mà.\") or a comma then one short stray word + period; complete the thought.\n"
            "- Each bullet MUST be a detailed, rich, complete sentence of 15 to 25 words. Avoid overly short or paragraph-like bullets.\n"
            "- Valid JSON and fully closed sentences matter more than making every bullet longer—do not \"expand\" length at the expense of truncation or broken JSON.\n"
            "- Each bullet: context + explanation + impact or significance—in rich wording.\n"
            f"- Rewrite shallow/short bullets into clear complete statements of {BULLET_WORD_RANGE} words; fix vague bullets with concrete detail.\n"
            "- Ensure each bullet carries meaningful information—not filler or labels.\n"
            "- Code, formulas, commands, and exact input/output lines are exempt from prose length rules. Keep them exact and in separate bullet strings; never expand executable syntax into prose.\n"
            "- Fix thin or broken bullets; do not only fix spelling.\n"
            "- Merge slides with fewer than 2 bullets into the previous slide.\n"
            "- Each slide should have 3–4 bullets.\n"
            "- Remove duplication.\n"
            "- No \"(continued)\" / \"(tiếp)\" slides.\n"
            "- SLIDE TITLES: Rewrite any generic slide title (such as 'Nội dung', 'Nội dung 1', 'Slide 1', 'Tiếp theo', or similar placeholders) into a specific, meaningful, descriptive title derived from the slide's bullet points.\n"
            "- DECK TITLE: Rewrite the top-level deck title if it is a generic chapter heading ('Mở đầu', 'Giới thiệu', 'Introduction'). The deck title must describe the WHOLE presentation's core subject (e.g. 'Phân mảnh CSDL Phân tán — Nhóm 17', 'AI in Healthcare Applications').\n"
            "- SPECIFICITY: Any bullet that contains no concrete fact, number, function name, or technical term is considered generic filler—rewrite it with a specific detail from the slide context.\n\n"
            "- SPEAKER NOTES: Write 70-120 words per slide as natural ready-to-speak narration. Keep notes strictly grounded in that slide's title and bullets, explain rather than repeat them, avoid meta phrases such as 'Slide này trình bày'/'This slide presents', and add a brief transition when appropriate.\n"
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

    def _build_revision_messages(
        self,
        structured: Dict[str, Any],
        revision_prompt: str,
    ) -> List[Dict[str, str]]:
        payload = json.dumps(structured, ensure_ascii=False)
        system_msg = (
            self._llm_system_prefix()
            + "You are an expert presentation editor.\n\n"
            + "TASK: Revise an existing slide deck JSON according to the user's follow-up request.\n\n"
            + self._presentation_style_block(len(structured.get("slides") or []))
            + "REVISION RULES:\n"
            "- Apply the user's request directly while preserving useful content from the current deck.\n"
            "- Keep the same topic unless the user explicitly asks to change it.\n"
            "- Keep exactly the same slide count unless the user explicitly asks to add, remove, merge, split, or set a different count.\n"
            "- You may rewrite titles, bullets, notes, and layout fields when needed.\n"
            "- Each slide should have 3-4 concise, complete, presentation-style bullets.\n"
            "- Remove duplication and fix vague, broken, or generic bullets.\n"
            "- Do not mention that this is a revision; output the final deck only.\n\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + "\n"
            + self._output_language_instruction()
            + "Return ONLY JSON. Schema:\n"
            "{\"title\":\"...\",\"slides\":[{\"title\":\"...\",\"bullets\":[\"...\"],\"notes\":\"speaker script\",\"layout\":\"text_only\"}]}\n"
        )
        user_msg = (
            "Current deck JSON:\n"
            f"{payload}\n\n"
            "User revision request:\n"
            f"{revision_prompt}\n\n"
            "Return the revised deck JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def revise_slide_deck(
        self,
        structured: Dict[str, Any],
        revision_prompt: str,
    ) -> Dict[str, Any]:
        """Revise an existing normalized slide deck using a follow-up user prompt."""
        base = self._normalize_structured_content(structured)
        prompt = str(revision_prompt or "").strip()
        if not prompt:
            return base
        self._slide_lang_hint = self._detect_output_language_hint(
            "\n\n".join(
                [
                    str(base.get("title") or ""),
                    "\n".join(str(s.get("title") or "") for s in base.get("slides") or [] if isinstance(s, dict)),
                    prompt,
                ]
            )
        )
        msgs = self._build_revision_messages(base, prompt)
        target = max(1, min(len(base.get("slides") or []) or 8, 30))
        revised = await self._request_json_dict(
            msgs,
            target_slides=target,
            fast_mode=False,
            compose_mode=True,
            structured_output="slide_deck",
        )
        if not (isinstance(revised, dict) and isinstance(revised.get("slides"), list) and revised.get("slides")):
            return base
        return self._normalize_structured_content(revised)

    def _build_single_slide_revision_messages(
        self,
        deck_title: str,
        slide_index: int,
        slide: Dict[str, Any],
        revision_prompt: str,
    ) -> List[Dict[str, str]]:
        payload = json.dumps(slide, ensure_ascii=False)
        system_msg = (
            self._llm_system_prefix()
            + "You are an expert presentation editor.\n\n"
            + "TASK: Revise exactly ONE slide according to the user's request.\n\n"
            + "STRICT RULES:\n"
            "- Revise only the provided slide. Do not create extra slides.\n"
            "- Apply the user's request literally and narrowly. If the user asks to change a few words, change only those words.\n"
            "- Preserve the slide's core topic unless the user explicitly asks to change it.\n"
            "- Keep useful bullets that the user did not ask to change.\n"
            "- Return one slide as JSON with title, bullets, notes, and layout.\n"
            "- Notes must remain a natural 70-120 word presenter script grounded in the revised title and bullets; never describe the slide as an object or invent facts.\n"
            "- Do not mention that this is a revision.\n\n"
            + self._output_language_instruction()
            + "Return ONLY JSON with this shape:\n"
            "{\"title\":\"...\",\"bullets\":[\"...\"],\"notes\":\"...\",\"layout\":\"text_only\"}\n"
        )
        user_msg = (
            f"Deck title: {deck_title}\n"
            f"Slide number: {slide_index + 1}\n\n"
            "Current slide JSON:\n"
            f"{payload}\n\n"
            "User revision request:\n"
            f"{revision_prompt}\n\n"
            "Return the revised slide JSON only."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def revise_selected_slides(
        self,
        structured: Dict[str, Any],
        revision_prompt: str,
        target_indices: List[int],
    ) -> Dict[str, Any]:
        """Revise only selected slides and keep every other slide unchanged."""
        base = self._normalize_structured_content(structured)
        slides = base.get("slides") or []
        prompt = str(revision_prompt or "").strip()
        valid_indices = sorted({int(i) for i in (target_indices or []) if 0 <= int(i) < len(slides)})
        if not prompt or not valid_indices:
            return base

        self._slide_lang_hint = self._detect_output_language_hint(
            "\n\n".join(
                [
                    str(base.get("title") or ""),
                    "\n".join(str(slides[i].get("title") or "") for i in valid_indices if isinstance(slides[i], dict)),
                    prompt,
                ]
            )
        )

        deck_title = str(base.get("title") or "Bài thuyết trình")
        for idx in valid_indices:
            current = dict(slides[idx]) if isinstance(slides[idx], dict) else {}
            msgs = self._build_single_slide_revision_messages(deck_title, idx, current, prompt)
            try:
                revised = await self._request_json_dict(
                    msgs,
                    target_slides=1,
                    fast_mode=False,
                    compose_mode=False,
                    structured_output=None,
                )
            except Exception as e:
                print(f"[revision] slide {idx + 1} revision failed: {e}")
                continue

            if not isinstance(revised, dict):
                continue
            normalized = self._normalize_structured_content({
                "title": deck_title,
                "slides": [revised],
            })
            new_slide = (normalized.get("slides") or [None])[0]
            if not isinstance(new_slide, dict):
                continue

            for visual_key in ("image_url", "table", "chart"):
                if current.get(visual_key) and not new_slide.get(visual_key):
                    new_slide[visual_key] = current.get(visual_key)
            slides[idx] = new_slide

        base["slides"] = slides
        return self._normalize_structured_content(base)

    def _build_revision_plan_messages(
        self,
        structured: Dict[str, Any],
        revision_prompt: str,
        context_slide_number: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        compact = {
            "title": structured.get("title") or "",
            "slides": [
                {
                    "number": idx + 1,
                    "title": str(slide.get("title") or ""),
                    "layout": str(slide.get("layout") or ""),
                    "has_image": bool(slide.get("image_url")),
                    "bullets": [str(x) for x in (slide.get("bullets") or [])[:3]],
                }
                for idx, slide in enumerate(structured.get("slides") or [])
                if isinstance(slide, dict)
            ],
        }
        payload = json.dumps(compact, ensure_ascii=False)
        system_msg = (
            self._llm_system_prefix()
            + "You are a revision planner for an AI slide editor.\n\n"
            + "TASK: Convert the user's natural-language edit request into a small JSON plan.\n\n"
            + "Rules:\n"
            "- Do not edit the deck content here; only plan operations.\n"
            "- If the user mentions specific slide numbers, put them in target_slide_numbers.\n"
            "- If the request is about images, visuals, illustrations, photos, or pictures, include regenerate_image.\n"
            "- If the request is about wording, bullets, titles, notes, tone, length, or content, include rewrite_text.\n"
            "- If the request asks for table/chart/layout/design, include change_layout.\n"
            "- If the request asks to add, remove, merge, split, or reorder slides, include restructure_deck.\n"
            "- If the target is unclear but says whole/all/toan bo/deck, use scope deck.\n"
            "- Infer scope semantically from the complete request; do not rely on a fixed keyword list.\n"
            "- A selected slide is weak UI context, not a forced target. Use it only when the request "
            "does not identify another target and is naturally a single-slide edit.\n"
            "- Requests such as adding more visuals throughout the presentation may target several "
            "appropriate slides even when a selected slide is provided.\n"
            "- Prefer scope slides when one or more target slides are intended; otherwise use deck.\n\n"
            + "Return ONLY JSON with this shape:\n"
            "{\"scope\":\"slides|deck\",\"target_slide_numbers\":[1],\"operations\":[{\"type\":\"rewrite_text|regenerate_image|change_layout|restructure_deck\",\"instruction\":\"...\"}],\"preserve_unmentioned\":true}\n"
        )
        user_msg = (
            f"Current deck summary JSON:\n{payload}\n\n"
            f"Selected slide context (optional, not a forced target): {context_slide_number or 'none'}\n\n"
            f"User edit request:\n{revision_prompt}\n\n"
            "Return the plan JSON only."
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def plan_slide_revision(
        self,
        structured: Dict[str, Any],
        revision_prompt: str,
        context_slide_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Plan a natural-language revision request before applying it."""
        base = self._normalize_structured_content(structured)
        prompt = str(revision_prompt or "").strip()
        slide_count = len(base.get("slides") or [])
        if not prompt:
            return {
                "scope": "deck",
                "target_slide_numbers": [],
                "operations": [],
                "preserve_unmentioned": True,
            }

        msgs = self._build_revision_plan_messages(
            base,
            prompt,
            context_slide_number=context_slide_number,
        )
        planner_succeeded = False
        try:
            plan = await self._request_json_dict(
                msgs,
                target_slides=max(1, min(slide_count or 1, 10)),
                fast_mode=True,
                compose_mode=False,
                structured_output=None,
            )
            planner_succeeded = isinstance(plan, dict) and bool(plan)
        except Exception as e:
            print(f"[revision_plan] planner failed: {e}")
            plan = {}
            if context_slide_number and 1 <= context_slide_number <= slide_count:
                plan = {
                    "scope": "slides",
                    "target_slide_numbers": [context_slide_number],
                    "operations": [{"type": "rewrite_text", "instruction": prompt}],
                    "preserve_unmentioned": True,
                }

        if not isinstance(plan, dict):
            plan = {}

        scope = str(plan.get("scope") or "").strip().lower()
        if scope not in {"slides", "deck"}:
            scope = "slides" if plan.get("target_slide_numbers") else "deck"

        raw_targets = plan.get("target_slide_numbers") or []
        if not isinstance(raw_targets, list):
            raw_targets = [raw_targets]
        target_numbers: List[int] = []
        for item in raw_targets:
            try:
                n = int(item)
            except Exception:
                continue
            if 1 <= n <= slide_count:
                target_numbers.append(n)

        raw_ops = plan.get("operations") or []
        if not isinstance(raw_ops, list):
            raw_ops = []
        valid_types = {"rewrite_text", "regenerate_image", "change_layout", "restructure_deck"}
        operations: List[Dict[str, str]] = []
        for op in raw_ops:
            if not isinstance(op, dict):
                continue
            op_type = str(op.get("type") or "").strip().lower()
            if op_type not in valid_types:
                continue
            instruction = str(op.get("instruction") or prompt).strip()
            operations.append({"type": op_type, "instruction": instruction or prompt})

        if not operations:
            operations = [{"type": "rewrite_text", "instruction": prompt}]

        return {
            "scope": scope,
            "target_slide_numbers": sorted(set(target_numbers)),
            "operations": operations,
            "preserve_unmentioned": bool(plan.get("preserve_unmentioned", True)),
            "planner_succeeded": planner_succeeded,
        }

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
            f"- Keep concise, ideally around {BULLET_WORD_RANGE} words, hard max {MAX_WORDS_PER_BULLET} words.\n"
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
        """Chỉ sửa các gạch đầu dòng vẫn trông có vẻ bị cụt sau bước tinh chỉnh (refine)."""
        if not isinstance(structured, dict):
            return structured
        structured = self._canonicalize_continued_titles(structured)
        slides = structured.get("slides") or []
        if not isinstance(slides, list) or not slides:
            return structured

        deck_title = str(structured.get("title") or "Bài thuyết trình")
        repaired = 0
        for slide in slides:
            if repaired >= max_repairs:
                break
            if not isinstance(slide, dict):
                continue
            slide_title = str(slide.get("title") or "Nội dung")
            bullets = slide.get("bullets") or []
            if not isinstance(bullets, list):
                continue

            out_bullets: List[str] = []
            for b in bullets:
                bt = str(b or "").strip()
                if not bt:
                    continue
                # Luôn luôn chạy sửa phần đuôi trước (nhẹ/nội bộ).
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
                        # Chấp nhận gạch đầu dòng đã sửa nếu nó giải quyết được lỗi cụt câu, nếu không thì giữ nguyên văn bản sửa dự phòng.
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
        """Đánh bóng (polish) tất cả các gạch đầu dòng trong một slide để đảm bảo tính hoàn chỉnh/rõ ràng."""
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
            f"- Keep concise: roughly {BULLET_WORD_RANGE} words, hard max {MAX_WORDS_PER_BULLET} words each bullet.\n"
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

    def _build_expand_no_image_messages(
        self,
        deck_title: str,
        slide_title: str,
        bullets: List[str],
    ) -> List[Dict[str, str]]:
        """Nhận slide không có ảnh và viết lại chữ chi tiết hơn để slide không bị trống."""
        bullets_payload = json.dumps(bullets, ensure_ascii=False)
        system_msg = (
            self._llm_system_prefix()
            + "You are an expert presentation copywriter.\n\n"
            + f"TASK: The slide titled '{slide_title}' will not contain any visual images. "
            + "Therefore, you must rewrite the bullet points to be longer, more informative, and detailed so that the slide does not look empty.\n\n"
            + "RULES:\n"
            "- Keep original facts. Do not invent completely fake concepts.\n"
            "- Make each bullet point a rich, complete sentence of 18-28 words.\n"
            "- If the input has less than 4 bullets, generate 1 additional highly relevant detailed bullet point to fill the space (total 4 bullets maximum).\n"
            "- Keep the same language as input.\n"
            "- Return ONLY JSON with schema: {\"bullets\": [\"...\", \"...\"]}\n"
        )
        user_msg = (
            f"Deck title: {deck_title}\n"
            f"Slide title: {slide_title}\n"
            f"Input bullets JSON: {bullets_payload}\n\n"
            "Expand all bullets following the rules."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def _expand_slide_bullets_for_no_image(
        self,
        structured: Dict[str, Any],
        missing_indices: List[int],
    ) -> Dict[str, Any]:
        """Bước tối ưu hóa visual: viết thêm/dài chữ cho các slide ban đầu có ý định sinh ảnh nhưng thất bại."""
        if not isinstance(structured, dict) or not missing_indices:
            return structured
        slides = structured.get("slides") or []
        if not isinstance(slides, list) or not slides:
            return structured

        deck_title = str(structured.get("title") or "Bài thuyết trình")
        
        tasks = []
        indices_map = []
        
        for idx in missing_indices:
            if idx < 0 or idx >= len(slides):
                continue
            slide = slides[idx]
            if not isinstance(slide, dict):
                continue
            slide_title = str(slide.get("title") or "Nội dung")
            bullets = slide.get("bullets") or []
            in_bullets = [str(b or "").strip() for b in bullets if str(b or "").strip()]
            if not in_bullets:
                continue
                
            msgs = self._build_expand_no_image_messages(deck_title, slide_title, in_bullets)
            tasks.append(self._request_json_dict(
                msgs,
                target_slides=1,
                fast_mode=False,
                compose_mode=False,
                structured_output="bullets",
            ))
            indices_map.append(idx)
            
        if not tasks:
            return structured
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                print(f"[slide_pipeline] Expand bullets failed for slide {indices_map[i]}: {res}")
                continue
            out = res.get("bullets") if isinstance(res, dict) else None
            if isinstance(out, list) and out:
                cleaned = [str(x or "").strip() for x in out if str(x or "").strip()]
                if cleaned:
                    slides[indices_map[i]]["bullets"] = cleaned[:5]
                    print(f"[slide_images_postprocess] Expanded bullets for slide {indices_map[i]} due to missing image")
                    
        return structured

    async def _polish_slide_bullets_quality(
        self,
        structured: Dict[str, Any],
        max_slides: int = 24,
    ) -> Dict[str, Any]:
        """Lượt xử lý ưu tiên chất lượng: viết lại các gạch đầu dòng theo từng slide để giảm thiểu lỗi cụt nghĩa (semantic truncation)."""
        if not isinstance(structured, dict):
            return structured
        slides = structured.get("slides") or []
        if not isinstance(slides, list) or not slides:
            return structured

        deck_title = str(structured.get("title") or "Bài thuyết trình")
        processed = 0
        for slide in slides:
            if processed >= max_slides:
                break
            if not isinstance(slide, dict):
                continue
            slide_title = str(slide.get("title") or "Nội dung")
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
                    # Giữ nguyên số lượng gạch đầu dòng nếu mô hình tạo ra thừa hoặc thiếu.
                    if len(polished) < len(in_bullets):
                        polished.extend(in_bullets[len(polished):])
                    polished = polished[: len(in_bullets)]
                    slide["bullets"] = polished[:MAX_BULLETS_PER_SLIDE]
            except Exception as e:
                print(f"Slide bullet polish failed ({slide_title!r}): {e}")

            processed += 1
        return structured

    def _bullet_needs_final_fix(self, text: str) -> bool:
        """Cổng chất lượng cuối cùng (an toàn): chỉ sửa các gạch đầu dòng có khả năng cao bị lỗi."""
        t = re.sub(r"\s+", " ", (text or "").strip())
        if not t:
            return False
        if self._is_truncated_bullet(t):
            return True
        if re.search(r"[,;:\-—/]\s*$", t):
            return True
        if not re.search(r"[.!?]$", t):
            return True
        # Quá ngắn và kết thúc đột ngột thường biểu thị thông tin kém hoặc đoản khúc bị lỗi.
        words = t.rstrip(".!?").split()
        if len(words) < 4 and len(t) >= 18:
            return True
        return False

    async def _run_final_quality_gate(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        """Cổng kiểm soát chất lượng lượt cuối: sửa các gạch đầu dòng mục tiêu, chỉ chấp nhận nếu có cải thiện."""
        if not isinstance(structured, dict):
            return structured
        slides = structured.get("slides") or []
        if not isinstance(slides, list) or not slides:
            return structured

        max_fixes = max(0, int(LLM_FINAL_QUALITY_GATE_MAX_FIXES))
        if max_fixes <= 0:
            return structured

        deck_title = str(structured.get("title") or "Bài thuyết trình")
        fixed = 0
        for slide in slides:
            if fixed >= max_fixes:
                break
            if not isinstance(slide, dict):
                continue
            slide_title = str(slide.get("title") or "Nội dung")
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
                        # Chỉ chấp nhận nếu câu ứng viên vượt qua cổng kiểm soát cuối cùng nghiêm ngặt hơn.
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
        pattern = re.compile(
            r"\s*\([^)]*(?:tiếp|tiep|continued|cont\.?)\s*\d*\)\s*$",
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
            f"- Each bullet must be a detailed, complete sentence of {BULLET_WORD_RANGE} words.\n"
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
        """Đảm bảo mỗi slide có ít nhất mật độ gạch đầu dòng đã cấu hình."""
        if not isinstance(structured, dict):
            return structured
        slides = structured.get("slides") or []
        if not isinstance(slides, list) or not slides:
            return structured

        lecture_mode = bool(
            getattr(self, "_lecture_mode", False)
            or str(structured.get("presentation_mode") or "").strip().lower() == "lecture"
        )
        default_min_b = max(2, int(LLM_FINAL_DENSITY_MIN_BULLETS))
        max_rw = max(0, int(LLM_FINAL_DENSITY_MAX_REWRITES))
        rewrites = 0
        deck_title = str(structured.get("title") or "Bài thuyết trình")

        # 1) Làm sạch hậu tố "(tiếp)" khỏi các tiêu đề trước.
        for s in slides:
            if isinstance(s, dict):
                s["title"] = self._strip_continued_suffix(str(s.get("title") or "Nội dung"))

        # 2) Mượn tạm gạch đầu dòng từ các slide lân cận trước khi gọi LLM.
        for i, s in enumerate(slides):
            if not isinstance(s, dict):
                continue
            role = str(s.get("pedagogical_role") or "").strip().lower()
            layout = str(s.get("layout") or "").strip().lower()
            min_b = 1 if layout in {"intro", "title", "thankyou", "thank_you"} else (
                max(default_min_b, 4) if lecture_mode and role not in {
                    "knowledge_check", "practice", "summary",
                } else default_min_b
            )
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

        # 3) Sử dụng LLM để tăng mật độ gạch đầu dòng chỉ cho các slide còn quá mỏng.
        for s in slides:
            if rewrites >= max_rw:
                break
            if not isinstance(s, dict):
                continue
            title = str(s.get("title") or "Nội dung")
            role = str(s.get("pedagogical_role") or "").strip().lower()
            layout = str(s.get("layout") or "").strip().lower()
            min_b = 1 if layout in {"intro", "title", "thankyou", "thank_you"} else (
                max(default_min_b, 4) if lecture_mode and role not in {
                    "knowledge_check", "practice", "summary",
                } else default_min_b
            )
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
                    # Chỉ chấp nhận nếu mật độ gạch đầu dòng được cải thiện và các câu đều tương đối sạch.
                    if len(fixed) >= min_b and sum(1 for x in fixed if self._bullet_needs_final_fix(x)) <= 1:
                        s["bullets"] = fixed[:MAX_BULLETS_PER_SLIDE]
                        rewrites += 1
            except Exception as e:
                print(f"Final density gate failed ({title!r}): {e}")

        return structured

    def _ensure_deck_boundaries(
        self,
        structured: Dict[str, Any],
        target_slides: int,
    ) -> Dict[str, Any]:
        """Add a cover and turn the final summary into a closing slide."""
        if not isinstance(structured, dict):
            return structured
        slides = structured.get("slides") or []
        if not isinstance(slides, list) or not slides:
            return structured

        lang = str(getattr(self, "_slide_lang_hint", "") or "").lower()
        vietnamese = lang == "vi"
        lecture_mode = bool(
            getattr(self, "_lecture_mode", False)
            or str(structured.get("presentation_mode") or "").strip().lower() == "lecture"
        )
        deck_title = str(structured.get("title") or "").strip()
        generic_titles = {
            "bai thuyet trinh",
            "bai trinh chieu",
            "presentation",
            "slide presentation",
            "lecture presentation",
        }
        if self._fold_language_text(deck_title) in generic_titles:
            structural_markers = (
                "muc tieu",
                "learning objective",
                "tong ket",
                "ket luan",
                "summary",
                "conclusion",
                "bai tap",
                "thuc hanh",
                "practice",
                "exercise",
                "activity",
                "quiz",
            )
            intro_prefix = re.compile(
                r"^\s*(?:giới\s+thiệu|gioi\s+thieu|tổng\s+quan|tong\s+quan|"
                r"introduction|overview)\s*(?:về|ve|to|of)?\s*[:\-–—]?\s*",
                re.IGNORECASE,
            )
            for candidate_slide in slides:
                if not isinstance(candidate_slide, dict):
                    continue
                candidate = str(candidate_slide.get("title") or "").strip()
                folded_candidate = self._fold_language_text(candidate)
                if (
                    not candidate
                    or folded_candidate in generic_titles
                    or any(marker in folded_candidate for marker in structural_markers)
                ):
                    continue
                candidate = intro_prefix.sub("", candidate).strip(" :-–—")
                if len(candidate.split()) >= 3:
                    deck_title = candidate
                    break
        if not deck_title or self._fold_language_text(deck_title) in generic_titles:
            deck_title = "Bài trình chiếu" if vietnamese else "Presentation"
        structured["title"] = deck_title

        if vietnamese:
            cover_fallback = (
                f"Khám phá {deck_title} qua các khái niệm, ví dụ và nội dung trọng tâm."
                if lecture_mode
                else f"Tổng quan về {deck_title} và những điểm đáng chú ý."
            )
        else:
            cover_fallback = (
                f"Explore the key concepts, examples, and practical ideas in {deck_title}."
                if lecture_mode
                else f"An overview of {deck_title} and the ideas that matter most."
            )
        if vietnamese:
            cover_notes = (
                f"Xin chào mọi người. Trong phần này, chúng ta sẽ cùng tìm hiểu {deck_title}. "
                + (
                    "Bài học sẽ đi từ những khái niệm nền tảng đến các ví dụ và cách vận dụng, "
                    "giúp người học nhận ra mối liên hệ giữa kiến thức và thực hành. "
                    "Trước khi bắt đầu, hãy thử liên hệ chủ đề này với những điều bạn đã biết; "
                    "sau đó chúng ta sẽ thống nhất các mục tiêu cần đạt."
                    if lecture_mode
                    else
                    "Phần trình bày tập trung vào bối cảnh, các luận điểm chính và ý nghĩa thực tiễn của chủ đề. "
                    "Trong quá trình theo dõi, hãy chú ý cách các ý liên kết với nhau và đâu là thông tin quan trọng nhất. "
                    "Trước hết, chúng ta bắt đầu từ bức tranh tổng quan."
                )
            )
        else:
            cover_notes = (
                f"Welcome. In this session, we will explore {deck_title}. "
                + (
                    "We will move from the foundational concepts to examples and practical application, "
                    "so that the relationship between knowledge and practice remains clear. "
                    "Before we begin, connect this topic with what you already know; "
                    "then we will establish the learning objectives for the session."
                    if lecture_mode
                    else
                    "The presentation focuses on the context, the central arguments, and the practical meaning of the topic. "
                    "As we move through it, notice how the ideas connect and which points carry the most significance. "
                    "Let us begin with the broader picture."
                )
            )
        cover = {
            "title": deck_title,
            "bullets": [cover_fallback],
            "notes": cover_notes,
            "layout": "intro",
            "pedagogical_role": "concept",
            "source_pages": [],
        }

        intro_index = next(
            (
                idx
                for idx, slide in enumerate(slides)
                if isinstance(slide, dict)
                and str(slide.get("layout") or "").strip().lower() in {"intro", "title"}
            ),
            None,
        )
        if intro_index is None:
            slides.insert(0, cover)
        else:
            intro_slide = slides.pop(intro_index)
            intro_slide["title"] = deck_title
            intro_slide["layout"] = "intro"
            intro_bullets = [
                str(item).strip()
                for item in (intro_slide.get("bullets") or [])
                if str(item).strip()
            ]
            folded_intro = self._fold_language_text(" ".join(intro_bullets))
            wrong_mode_copy = not lecture_mode and any(
                marker in folded_intro
                for marker in ("bai giang", "lecture overview", "lecture introduction")
            )
            if not intro_bullets or wrong_mode_copy:
                intro_slide["bullets"] = [cover_fallback]
            if not str(intro_slide.get("notes") or "").strip():
                intro_slide["notes"] = cover_notes
            slides.insert(0, intro_slide)

        # Section generation can occasionally exceed its allocation. Keep both
        # deck boundaries and remove overflow from the end of the content run.
        while len(slides) > target_slides and len(slides) > 2:
            slides.pop(-2)

        closing = slides[-1] if isinstance(slides[-1], dict) else {}
        closing_layout = str(closing.get("layout") or "").strip().lower()
        closing_role = str(closing.get("pedagogical_role") or "").strip().lower()
        closing_title_folded = self._fold_language_text(str(closing.get("title") or ""))
        is_existing_closing = (
            closing_layout in {"thankyou", "thank_you"}
            or closing_role == "summary"
            or any(
                marker in closing_title_folded
                for marker in ("tong ket", "ket luan", "summary", "conclusion", "q&a", "hoi dap")
            )
        )
        existing_bullets = [
            str(item).strip()
            for item in (closing.get("bullets") or [])
            if str(item).strip()
        ]
        content_slides = [
            slide
            for slide in slides[1:-1]
            if isinstance(slide, dict)
            and str(slide.get("pedagogical_role") or "").strip().lower()
            not in {"learning_objectives", "practice", "knowledge_check", "summary"}
        ]

        def semantic_tokens(value: Any) -> set[str]:
            folded = self._fold_language_text(str(value or ""))
            ignored = {
                "and", "the", "for", "with", "from", "this", "that",
                "va", "voi", "cho", "cua", "cac", "nhung", "trong", "mot",
                "summary", "conclusion", "tong", "ket", "hoi", "dap",
                "program", "programs", "result", "results", "value", "values",
                "content", "contents", "information", "key", "idea", "ideas",
            }
            return {
                token
                for token in re.sub(r"[^a-z0-9]+", " ", folded).split()
                if len(token) >= 3 and token not in ignored
            }

        body_tokens: set[str] = set()
        for slide in content_slides:
            body_tokens.update(semantic_tokens(slide.get("title")))
            body_tokens.update(semantic_tokens(" ".join(str(x) for x in (slide.get("bullets") or []))))
        closing_tokens = semantic_tokens(" ".join(existing_bullets))
        closing_overlap = closing_tokens & body_tokens
        body_title_token_sets = [
            semantic_tokens(slide.get("title"))
            for slide in content_slides
            if semantic_tokens(slide.get("title"))
        ]
        aligned_closing_bullets = sum(
            1
            for bullet in existing_bullets
            if any(
                semantic_tokens(bullet) & title_tokens
                for title_tokens in body_title_token_sets
            )
        )
        closing_is_aligned = bool(
            existing_bullets
            and (
                len(closing_overlap) >= 3
                and len(closing_overlap) / max(1, len(closing_tokens)) >= 0.35
                and aligned_closing_bullets >= min(2, len(existing_bullets))
            )
        )

        if is_existing_closing and closing_is_aligned:
            closing_bullets = existing_bullets[:4]
        else:
            closing_bullets = []
            for slide in content_slides:
                bullets = [
                    str(item).strip()
                    for item in (slide.get("bullets") or [])
                    if str(item).strip()
                ]
                if bullets:
                    closing_bullets.append(bullets[0])
                if len(closing_bullets) >= 3:
                    break
            if not closing_bullets:
                objectives = [
                    str(item).strip()
                    for item in (structured.get("learning_objectives") or [])
                    if str(item).strip()
                ]
                closing_bullets = objectives[:3]
        if not closing_bullets:
            closing_bullets = (
                [
                    f"Các nội dung trọng tâm về {deck_title} đã được hệ thống hóa.",
                    "Cảm ơn và mời đặt câu hỏi.",
                ]
                if vietnamese
                else [
                    f"The key ideas about {deck_title} have been consolidated.",
                    "Thank you. Questions are welcome.",
                ]
            )
        existing_closing_title = str(closing.get("title") or "").strip()
        folded_closing_title = self._fold_language_text(existing_closing_title)
        closing_title_is_wrong_mode = not lecture_mode and any(
            marker in folded_closing_title
            for marker in ("ket thuc bai giang", "end of lecture", "lecture summary")
        )
        nearby_body_has_conclusion = any(
            any(
                marker in self._fold_language_text(str(slide.get("title") or ""))
                for marker in ("ket luan", "conclusion", "closing thoughts")
            )
            for slide in slides[max(1, len(slides) - 3):-1]
            if isinstance(slide, dict)
        )
        if not is_existing_closing or not existing_closing_title or closing_title_is_wrong_mode:
            if vietnamese:
                existing_closing_title = (
                    "Tổng kết và Hỏi đáp"
                    if lecture_mode
                    else f"Kết luận: {deck_title}"
                )
            else:
                existing_closing_title = (
                    "Summary and Q&A"
                    if lecture_mode
                    else f"Closing thoughts: {deck_title}"
                )
        if nearby_body_has_conclusion and not lecture_mode:
            existing_closing_title = "Cảm ơn và Hỏi đáp" if vietnamese else "Thank You and Q&A"
            closing_bullets = (
                ["Cảm ơn mọi người đã theo dõi. Mời đặt câu hỏi và trao đổi."]
                if vietnamese
                else ["Thank you for your attention. Questions and discussion are welcome."]
            )
        closing["title"] = existing_closing_title
        closing["layout"] = "thankyou"
        closing["pedagogical_role"] = "summary"
        closing["bullets"] = closing_bullets
        closing["notes"] = (
            f"Khép lại bài trình bày bằng cách nhắc lại các ý chính về {deck_title}. "
            "Nhấn mạnh mối liên hệ giữa các luận điểm vừa được phân tích và giá trị thực tiễn mà người nghe có thể ghi nhớ. "
            "Không cần đọc lại từng gạch đầu dòng; hãy cô đọng thông điệp quan trọng nhất bằng lời của người trình bày. "
            "Cuối cùng, mời người nghe nêu câu hỏi, chia sẻ điểm còn chưa rõ và liên hệ nội dung với kinh nghiệm hoặc phần thực hành tiếp theo."
            if vietnamese
            else (
                f"Close the presentation by revisiting the key ideas about {deck_title}. "
                "Emphasize how the main arguments connect and what practical value the audience should retain. "
                "Rather than reading each bullet again, restate the central message naturally in your own words. "
                "Finally, invite questions, clarify any remaining uncertainty, and connect the discussion to experience or the next practical activity."
            )
        )
        slides[-1] = closing

        structured["slides"] = slides[:target_slides]

        # Drop fragmented ASCII diagrams that document extraction incorrectly
        # split into separate bullets.
        for slide in structured["slides"]:
            if not isinstance(slide, dict):
                continue
            bullets = [str(item).strip() for item in (slide.get("bullets") or []) if str(item).strip()]
            art_indices = [
                idx for idx, item in enumerate(bullets)
                if re.fullmatch(r"[+\-|_=:\s]{4,}", item)
            ]
            if len(art_indices) >= 2:
                start = art_indices[0]
                if start > 0 and bullets[start - 1].rstrip().endswith(":"):
                    start -= 1
                end = art_indices[-1]
                bullets = bullets[:start] + bullets[end + 1:]
            slide["bullets"] = bullets
        return structured

    async def _refine_deck_with_optional_second(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        """Tinh chỉnh (refine) lần 1, sau đó lặp thêm tối đa LLM_REFINE_MAX_EXTRA_PASSES lượt khi vẫn phát hiện gạch đầu dòng bị cụt."""
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
        """Tạo prompt để LLM xem xét tiêu đề của từng slide và sửa nếu nó quá chung chung hoặc không khớp với nội dung."""
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

    def _build_unified_post_process_messages(self, structured: Dict[str, Any]) -> List[Dict[str, str]]:
        payload = json.dumps(structured, ensure_ascii=False)
        system_msg = (
            self._llm_system_prefix()
            + "You are a premium presentation editor.\n\n"
            + "TASK: Conduct a comprehensive revision of the generated slide deck JSON to guarantee professional quality.\n\n"
            + "DECK BOUNDARIES: Keep the exact slide count. Rewrite slide 1 as a cover with layout='intro', "
            "the deck topic as title, and at most two concise subtitle bullets. Rewrite the final slide as a "
            "closing with layout='thankyou', one or two key takeaways plus an optional Q&A invitation, and at most four bullets. "
            "Do not append extra slides.\n\n"
            + "CRITICAL QUALITY RULES:\n"
            "1. NO TRUNCATION: Fix any bullet point that is cut off or incomplete. Vietnamese bullets MUST NOT end with a preposition/conjunction/function word followed by a period (e.g., 'của.', 'cho.', 'với.', 'để.', 'gồm.', 'và.', 'hoặc.'). Complete the sentence or rewrite it.\n"
            f"2. BULLET LENGTH & STRUCTURE: Each bullet must be a single complete sentence, containing roughly {BULLET_WORD_RANGE} words (hard max {MAX_WORDS_PER_BULLET} words). No bullet should be a single phrase/label or a huge paragraph.\n"
            "2b. VISUAL DENSITY: Keep ordinary slides at 3-6 visible bullets and near 500 characters. A slide intended "
            "for an image must remain below roughly 760 visible characters. Preserve central ideas on-slide and move "
            "secondary explanation to notes; never solve crowding by producing tiny text. When natural semantic groups "
            "exist, use 'Short label: complete explanation' bullets instead of a flat list.\n"
            "Practice and knowledge-check slides must show at most 6 primary prompts; place optional variants and "
            "answer guidance in speaker notes.\n"
            "3. SLIDE TITLES: Sửa các slide title chung chung hoặc là placeholder ('Nội dung', 'Slide 1', 'Tiếp theo') bằng một tiêu đề cụ thể, mô tả chính xác nội dung các bullet của slide đó. Độ dài tiêu đề slide từ 3-8 từ.\n"
            "4. NO DUPLICATIONS: Xóa bỏ các slide hoặc bullet bị lặp ý hoàn toàn. Nếu slide quá mỏng (< 2 bullets), hãy mượn hoặc ghép nó vào slide hợp lý trước đó.\n"
            "5. PRESERVE TECHNICAL DETAILS: Giữ nguyên các thuật ngữ chuyên ngành, tên hàm, số liệu kỹ thuật, tên thuật toán từ slide gốc.\n\n"
            + ANTI_TRUNCATION_TOKEN_RULE
            + self._output_language_instruction()
            + "Return ONLY valid JSON. Schema:\n"
            "{\"title\":\"...\",\"slides\":[{\"title\":\"...\",\"bullets\":[\"...\"],\"notes\":\"...\",\"layout\":\"intro|normal|thankyou\"}]}\n"
        )
        user_msg = (
            "Review and revise the following slide deck JSON to apply the quality rules:\n\n"
            f"{payload}\n\n"
            "Return JSON starting with { and ending with }."
            + self._user_lang_reminder()
        )
        return [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

    async def _unified_post_process(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        """Unified pass to refine, repair, and polish bullets/titles in a single LLM call."""
        if not isinstance(structured, dict) or not structured.get("slides"):
            return structured
        try:
            print("[slide_pipeline] unified post-process start")
            # Tự động dọn dẹp Continued Suffix trước để LLM có đầu vào sạch hơn
            structured = self._canonicalize_continued_titles(structured)
            msgs = self._build_unified_post_process_messages(structured)
            refined = await self._request_json_dict(
                msgs,
                target_slides=len(structured.get("slides") or []),
                fast_mode=False,
                compose_mode=True,
                structured_output="slide_deck",
            )
            expected_count = len(structured.get("slides") or [])
            has_slides = (
                isinstance(refined, dict)
                and isinstance(refined.get("slides"), list)
                and len(refined.get("slides")) == expected_count
            )
            if has_slides:
                print("[slide_pipeline] unified post-process success")
                # Sau khi LLM sửa, chạy canonicalize lần nữa để chuẩn hóa tiêu đề
                return self._canonicalize_continued_titles(self._normalize_structured_content(refined))
            else:
                print("[slide_pipeline] unified post-process empty result, using original")
                return structured
        except Exception as e:
            print(f"[slide_pipeline] unified post-process failed: {e}. Falling back to original.")
            return structured

    def _merged_body_from_raw(self, raw_content: str) -> Dict[str, str]:
        """Chuẩn hóa nội dung ngắn thành dạng merged summary (## + bullet) không cần qua LLM."""
        norm = self._normalize_for_llm(raw_content or "")
        doc_title = "Bài thuyết trình"
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
        """Luồng slide duy nhất sau khi có bản tóm tắt gộp (merged): mở rộng (expand) → nhóm (group) → tạo slide (generate) → tinh chỉnh (refine) → chuẩn hóa (normalize)."""
        print(
            f"Slide pipeline: expand → group → generate → refine (target ~{target_slides} slides)"
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
        content_target = max(5, target_slides - 1)
        structured = await self._generate_slides_for_sections(
            sections, target_slides=content_target
        )
        structured = self._ensure_deck_boundaries(structured, target_slides)
        print(
            f"[slide_pipeline] generate sections done slides={len((structured or {}).get('slides') or [])}"
        )
        try:
            print("[slide_pipeline] unified post-process starting")
            structured = await self._unified_post_process(structured)
            if LLM_FINAL_DENSITY_GATE:
                print("[slide_pipeline] final density gate start")
                structured = await self._run_final_density_gate(structured)
                print("[slide_pipeline] final density gate done")
        except Exception as e:
            print(f"[slide_pipeline] unified post-process failed: {e}; fallback refine start")
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
