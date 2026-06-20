import re

def reconstruct():
    path = r"e:\DemoDoan\backend\services\content\slide_normalizer.py"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # We want to replace everything from the start of `_normalize_structured_content`
    # up to the start of `_balance_deck`.
    
    start_idx = -1
    end_idx = -1
    for idx, line in enumerate(lines):
        if "def _normalize_structured_content(" in line:
            start_idx = idx
        if "def _balance_deck(" in line:
            end_idx = idx
            break
            
    if start_idx == -1 or end_idx == -1:
        print(f"Error finding boundaries: start_idx={start_idx}, end_idx={end_idx}")
        return
        
    print(f"Found boundaries: lines {start_idx + 1} to {end_idx + 1}")
    
    # We define the clean and updated implementation of `_normalize_structured_content`
    new_method = """    def _normalize_structured_content(self, structured_content: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Normalize to canonical slide JSON format.

        Canonical format:
        {
          "title": str,
          "slides": [{"title": str, "bullets": [str], "notes": str}]
        }

        Backward compat: accepts legacy "content" as bullets.
        \"\"\"
        if not isinstance(structured_content, dict):
            return {"title": "Bài thuyết trình", "slides": []}

        title = structured_content.get("title")
        if not isinstance(title, str) or not title.strip():
            title = "Bài thuyết trình"

        slides_in = structured_content.get("slides", [])
        if not isinstance(slides_in, list):
            slides_in = []

        def _clean_bullet(text: str, _max_words: int) -> str:
            \"\"\"Strip artifacts, repair tails, hard-cut tại _max_words để giữ bullet súc tích.\"\"\"
            t = (text or "").strip()
            # Remove accidental markdown/heading markers inside bullets
            t = re.sub(r"^\s*#{1,6}\s*", "", t)
            t = re.sub(r"^\s*[-*•]\s*", "", t)
            t = re.sub(r"^\s*[→>]+\s*", "", t)
            # Remove leading numbering like "1.", "2.3", "1-"
            t = re.sub(r"^\s*\d+(\.\d+)*\s*[-:.)]\s*", "", t)
            # Strip trailing ... or … (model's copy-paste artifact)
            t = re.sub(r'[…\\.]{2,}\\s*$', '', t).strip()
            t = t.rstrip(',(').strip()
            t = re.sub(r'\\s+', ' ', t)
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
                        # Strategy B: no boundary before limit — try to extend up to
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
                            # Strategy C: no sentence boundary at all — cut at last
                            # clause boundary (comma) to keep at least one full clause.
                            pos = candidate.rfind(",")
                            if pos > len(candidate) // 3:
                                cut = candidate[:pos].strip()
                            else:
                                cut = candidate.rstrip(",").strip()

                    t = cut
                    # Sau khi cắt, nếu kết quả vẫn bị phát hiện là cụt bởi
                    # _is_truncated_bullet, mở rộng thêm 1 từ mỗi lần cho đến khi
                    # bullet trông hoàn chỉnh hoặc chạm giới hạn an toàn (+6 từ).
                    # Cách này tổng quát: không cần liệt kê từng tiền tố cụ thể.
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
            if t and not re.search(r'[\\.!?]$', t):
                t += '.'
            return t

        slides_out: List[Dict[str, Any]] = []
        for slide in slides_in:
            if not isinstance(slide, dict):
                continue

            bullets = slide.get("bullets")
            if bullets is None:
                bullets = slide.get("content")  # legacy

            if isinstance(bullets, str):
                bullets_list = [bullets.strip()] if bullets.strip() else []
            elif isinstance(bullets, list):
                bullets_list = [str(b).strip() for b in bullets if str(b).strip()]
            else:
                bullets_list = []

            slide_title = slide.get("title")
            if not isinstance(slide_title, str) or not slide_title.strip() or slide_title.strip().lower() in ("nội dung", "noi dung"):
                if bullets_list:
                    first_b = bullets_list[0].strip()
                    if ":" in first_b and first_b.find(":") < 30:
                        slide_title = first_b.split(":", 1)[0].strip()
                    else:
                        words = first_b.split()
                        slide_title = " ".join(words[:5]).strip(".,;:!-“”‘’\\"' ")
                if not slide_title or not slide_title.strip():
                    slide_title = "Nội dung"

            def _norm_compare(s: str) -> str:
                # Normalize for approximate equality checks (avoid accepting bullet duplicated title).
                t = (s or "").strip().lower()
                t = re.sub(r"\\s+", " ", t)
                t = t.strip(" \\t\\n\\r\\"'“”“”‘’.,;:!?-—–()[]{}")
                return t

            # Enforce spec: đủ bullet dài để slide có ý; bỏ bullet cụt ngay (không đưa vào deck).
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
                \"\"\"Loại bullet kiểu vài chữ / không đủ ngữ cảnh (hay gặp khi model lười).\"\"\"
                s = (s or "").strip()
                w = len(s.split())
                c = len(s)
                # Ngưỡng strict: nếu bullet quá ngắn thì bỏ.
                # Fix theo yêu cầu: nếu c < 25 hoặc w < 4 => reject.
                # (Giảm nguy cơ "1 slide 1 dòng" do filter quá gắt.)
                if c < 25:
                    return False
                if w < 4:
                    return False
                return True

            strict_filtered = [b for b in cleaned_bullets if b and _bullet_ok(b)]

            # Recovery: tránh tình trạng slide rơi xuống 1 bullet sau khi lọc strict.
            # Mục tiêu là giữ mật độ chữ/ý ổn định; nếu strict không đủ 3 bullet,
            # hãy nới ngưỡng để giữ lại bullet có ít nhất độ dài “tối thiểu”.
            if len(strict_filtered) >= 3:
                bullets_list = strict_filtered
            else:
                def _bullet_loose_ok(s: str) -> bool:
                    s = (s or "").strip()
                    w = len(s.split())
                    c = len(s)
                    # Nới nhẹ thêm để tránh rơi vào trạng thái chỉ còn 1 bullet/slide.
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

            notes = slide.get("script") or slide.get("speaker_notes") or slide.get("notes")
            if not isinstance(notes, str):
                notes = str(notes)
            notes = notes.strip()
            if not notes:
                notes = self._build_default_speaker_notes(slide_title, bullets_list)

            slides_out.append({
                "title": self._sanitize_title(slide_title.strip())[:120],
                "bullets": bullets_list,
                "notes": notes,
                "script": notes,
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
        for s in slides_out:
            if not isinstance(s, dict):
                continue
            notes = str(s.get("script") or s.get("speaker_notes") or s.get("notes") or "").strip()
            if not notes:
                notes = self._build_default_speaker_notes(str(s.get("title") or ""), s.get("bullets") or [])
            s["notes"] = notes
            s["script"] = notes
        return {"title": self._sanitize_title(title.strip())[:120], "slides": slides_out}

"""
    
    # Splice new content
    patched_lines = lines[:start_idx] + [new_method] + lines[end_idx:]
    
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(patched_lines)
    print("Patch applied successfully!")

if __name__ == '__main__':
    reconstruct()
