"""Chunking, summarization, and reduce-stage helpers."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List, Optional

from config import (
    LLM_CHUNK_FAST_TIMEOUT_SEC,
    LLM_CHUNK_PARALLEL,
    LLM_CHUNK_TIMEOUT_SEC,
    LLM_FAST_MODE,
    LLM_QUALITY_MODE,
    LLM_SUBCHUNK_TIMEOUT_SEC,
)
from services.content.errors import TaskCancelledError
from services.content.prompts import MAX_BULLETS_PER_SLIDE


class ChunkingMixin:
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
            f"- Target ~12–16 words per bullet, max {word_limit} words; prefer finishing the sentence over filling length.\n"
            "- Do not use double-quote characters inside title/bullets (breaks JSON).\n"
            "- One idea per bullet—do not merge unrelated ideas.\n"
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
        title = fallback.get("title") or "Nội dung chính"
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
            title = str(summary.get("title") or "Nội dung chính").strip()[:120]
            raw_bullets = summary.get("bullets", [])
            if isinstance(raw_bullets, str):
                raw_bullets = [raw_bullets]
            if not isinstance(raw_bullets, list):
                raise ValueError("Summary bullets missing")
            bullets = [str(b).strip() for b in raw_bullets if str(b).strip()][:max_bullets]
            if not bullets:
                raise ValueError("Summary bullets empty")
            # Model đôi khi trả quá ít bullet (đặc biệt 1-2 bullet) cho cả đoạn dài
            # → deck sau bị "một dòng một slide"
            if len(bullets) < 4 and len(chunk_content or "") > 900 and not fast_mode:
                try:
                    base_msgs = self._build_summary_messages(chunk_content, fast_mode=False)
                    retry_msgs = [
                        {
                            "role": "system",
                            "content": base_msgs[0]["content"]
                            + "\n\nMANDATORY: Long passage—return at least 4 distinct bullets; "
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
                            print(f"  (chunk summary retry → {len(bullets)} bullets)")
                except Exception as re:
                    print(f"  (chunk summary retry skipped: {re})")
            return {"title": title or "Nội dung chính", "bullets": bullets}
        except Exception as e:
            print(f"Summary fallback due to error: {e}")
            return self._fallback_summary(chunk_content, max_bullets=max_bullets)

    def _merge_chunk_summaries(self, summaries: List[Dict[str, Any]]) -> Dict[str, str]:
        """Reduce step input: merge chunk summaries into one compact markdown-like document."""
        lines: List[str] = []
        doc_title = "Bài thuyết trình"
        for idx, summary in enumerate(summaries, start=1):
            title = str(summary.get("title") or f"Phần {idx}").strip()
            if idx == 1 and title:
                doc_title = title[:120]
            lines.append(f"## {title or f'Phần {idx}'}")
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
                "title": str(slide.get("title") or "Nội dung"),
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
                    "title": f"{source['title']} (tiếp)",
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
            return {"title": "Bài thuyết trình", "slides": []}

        slides: List[Dict[str, Any]] = []
        doc_title = "Bài thuyết trình"

        for idx, summary in enumerate(summaries):
            raw_title = str(summary.get("title") or f"Phần {idx + 1}").strip()
            section_title = self._sanitize_title(raw_title)[:120] or f"Phần {idx + 1}"
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

            # Outline thường phân bổ nhiều slide hơn số bullet thực tế → mỗi slide 1 dòng.
            # Giới hạn: trung bình ~≥3 bullet/slide khi chia (ceil(n/3) slide tối đa).
            max_slides_for_bullets = max(1, (len(bullets) + 2) // 3)
            desired_slides = min(desired_slides, max_slides_for_bullets)

            for part_idx, part in enumerate(self._partition_bullets(bullets, desired_slides), start=1):
                slide_title = section_title if part_idx == 1 else f"{section_title} (tiếp)"
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

        # Khi chạy server mạnh, cho phép deck dày hơn và “thoải mái” số slide hơn.
        # Tránh tình trạng bị kẹp quá chặt quanh ~10 slide.
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
            {"section": str(summaries[i].get("title") or f"Phần {i+1}"), "slides": raw_alloc[i]}
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

        Input: merged_summary["content"] (đã là bản tóm tắt theo ##)
        Output: JSON thuần {"sections":[{"title": "...", "description": "..."}]}
        """
        normalized = self._normalize_for_llm(merged_content)
        preview = normalized[:7000] if len(normalized) > 7000 else normalized
        system_msg = self._llm_system_prefix() + (
            "You design content structure for a slide deck.\n\n"
            "RULES:\n"
            "- Return ONLY valid JSON—no text outside JSON.\n"
            + self._output_language_instruction()
            + f"- Produce EXACTLY between {min_sections} and {max_sections} sections (inclusive).\n"
            "- Each section is a DISTINCT topic (no duplicated ideas).\n"
            "- description: 1–2 sentences on why the section matters and what it covers.\n"
            "- No overlap: one idea must not appear in multiple sections.\n\n"
            "Schema:\n"
            "{\"sections\": [{\"title\": \"...\", \"description\": \"...\"}]}"
        )
        user_msg = (
            "Summary by major headings—build an outline:\n\n"
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
        # Clamp số section về [min,max] (nếu model trả lệch).
        if len(cleaned) > max_sections:
            cleaned = cleaned[:max_sections]
        if len(cleaned) < min_sections and cleaned:
            # Nếu ít hơn, duplicate description để đủ số section theo đúng schema.
            while len(cleaned) < min_sections:
                cleaned.append(dict(cleaned[-1]))
        return cleaned

    def _build_expansion_messages(
        self,
        merged_content: str,
        outline_sections: List[Dict[str, Any]],
        target_slides: int,
    ) -> List[Dict[str, str]]:
        """FINAL SPEC - Expansion step (làm content phong phú hơn, KHÔNG summarize)."""
        normalized = self._normalize_for_llm(merged_content)
        preview = normalized[:7000] if len(normalized) > 7000 else normalized
        # Khi user chọn nhiều slide: mở rộng sâu hơn + thêm ví dụ/phân rã.
        depth_rule = (
            "High target slide count: expand deeply—split ideas, add examples and explanations per part."
            if target_slides >= 12
            else "Expand enough so each point has context plus supporting examples."
        )
        outline_json = json.dumps(outline_sections, ensure_ascii=False)
        system_msg = self._llm_system_prefix() + (
            "You EXPAND material for slide generation.\n\n"
            "RULES:\n"
            "- DO NOT summarize. Do not compress.\n"
            "- Always expand: add explanations, examples, and supporting detail.\n"
            "- Each outline section must be clearly expanded—not keyword lists.\n\n"
            + self._output_language_instruction()
            + "Schema:\n"
            "{\"expanded_content\": \"...\"}\n\n"
            "expanded_content format:\n"
            "- Use headings: ## <section_title>\n"
            "- Under each heading, write 2–4 paragraphs (explanation + examples).\n"
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
            # Nếu outline fail, vẫn fallback bằng nội dung đã có để không chết pipeline.
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
        print("Planning outline sections (5–8)...")
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
        # Generate slides from expanded content (không compose_mode).
        final_result = await self._extract_compact_content(
            expanded_content,
            target_slides=target_slides,
            chunk_mode=False,
            fast_mode=LLM_FAST_MODE,
            compose_mode=False,
        )
        # FINAL SPEC: đảm bảo slide count đúng {N} kể cả khi post-process
        # (lọc/dedup/merge) làm trượt số slide.
        final_result = await self._force_slide_count_exact(final_result, target_slides)
        return final_result

    async def _summarize_chunk_with_retries(
        self,
        chunk: str,
        chunk_idx: int,
        total_chunks: int,
        should_stop: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> List[Dict[str, Any]]:
        """Map step: một chunk → một hoặc nhiều summary dict (subchunk khi timeout)."""
        print(f"Summarizing chunk {chunk_idx + 1}/{total_chunks} ({len(chunk)} chars)...")
        parts: List[Dict[str, Any]] = []
        try:
            summary_result = await asyncio.wait_for(
                self._summarize_chunk(chunk),
                timeout=LLM_CHUNK_TIMEOUT_SEC,
            )
            bullets_got = len(summary_result.get("bullets", []))
            print(f"  ✓ Chunk {chunk_idx + 1} summary done → {bullets_got} bullets")
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
                print(f"  ✓ Chunk {chunk_idx + 1} fast summary done → {bullets_got} bullets")
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
                            f"    ✓ Subchunk {sub_idx + 1}/{len(subchunks)} summary done"
                        )
                    except asyncio.TimeoutError:
                        print(
                            f"    ✗ Subchunk {sub_idx + 1}/{len(subchunks)} timeout, skipping"
                        )
                    except Exception as e:
                        print(
                            f"    ✗ Subchunk {sub_idx + 1}/{len(subchunks)} error: {e}"
                        )
        except TaskCancelledError:
            raise
        except Exception as e:
            print(f"  ✗ Chunk {chunk_idx + 1} error: {e}")
        return parts

    async def _extract_with_chunking(
        self,
        raw_content: str,
        should_stop: Optional[Callable[[], Awaitable[bool]]] = None,
        target_slides_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Chunking strategy: chia content theo Heading; summary map theo LLM_CHUNK_PARALLEL;
        merge rồi cùng một luồng `_expand_group_generate_refine_pipeline` như nội dung ngắn.
        """
        chunks = self._split_by_headings(raw_content)
        
        if len(chunks) == 1:
            if should_stop and await should_stop():
                raise TaskCancelledError("Task cancelled by user")
            # Một chunk: summary → merge → cùng pipeline slide chuẩn.
            summary_result = await self._summarize_chunk(chunks[0], fast_mode=LLM_FAST_MODE)
            merged_summary = self._merge_chunk_summaries([summary_result])
            slide_plan = self._estimate_reduce_slide_plan([summary_result], merged_summary["content"])
            target_slides = int(target_slides_override or slide_plan.get("target") or 10)
            final_result = await self._expand_group_generate_refine_pipeline(
                merged_summary, target_slides
            )
            final_result = await self._force_slide_count_exact(final_result, target_slides)
            if merged_summary.get("title") and final_result.get("title") == "Bài thuyết trình":
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
        final_result = await self._force_slide_count_exact(final_result, target_slides)
        if merged_summary.get("title") and final_result.get("title") == "Bài thuyết trình":
            final_result["title"] = merged_summary["title"]

        print(f"Done: {len(final_result.get('slides', []))} slides total")
        return final_result



