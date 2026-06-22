"""Slide deck bullet cleaning, normalization, and balancing.

SlideNormalizerMixin provides all post-processing logic for the slide JSON
produced by the LLM: cleaning bullets, balancing the deck, repairing
truncated sentences, and enforcing exact slide counts.
"""
from __future__ import annotations

import html
import re
import unicodedata
from typing import Any, Dict, List, Optional

from services.content.prompts import MAX_BULLETS_PER_SLIDE, MAX_WORDS_PER_BULLET

# Từ/cụm kết thường làm bullet bị cụt khi cắt theo số từ (Việt + Anh).
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
        "của",
        "cho",
        "như",
        "với",
        "từ",
        "theo",
        "mà",
        "để",
        "và",
        "hoặc",
        "trong",
        "ngoài",
        "bởi",
        "các",
        "một",
        "đặc",
        "biệt",
        # Connector-words that always need continuation to form a complete idea.
        "nhằm",  # "in order to" — always precedes a verb phrase
        "gồm",   # "includes" — always precedes its items
        "nhờ",   # "thanks to / through" — always precedes the means
    }
)

# Sino-Vietnamese bound morphemes that NEVER legitimately end a sentence alone.
# Each entry is the FIRST syllable of a common compound that must be followed
# by its complement (e.g. "trung" → trung thành / trung tâm / trung thực).
# Detected in _repair_incomplete_tail and _is_truncated_bullet.
_VN_BOUND_PREFIXES = frozenset({
    "trung",   # trung thành, trung tâm, trung thực, trung bình, trung lập
    "bất",     # bất kỳ, bất ngờ, bất hợp (pháp)
    "vô",      # vô cùng, vô ích, vô lý, vô hiệu
    "siêu",    # siêu thị, siêu tốc, siêu âm
    "tiểu",    # tiểu thuyết, tiểu học, tiểu đường
    "đại",     # đại học, đại diện, đại dương (as sentence-final: extremely rare)
    "phi",     # phi lợi nhuận, phi tập trung
    "hợp",     # hợp pháp, hợp lệ, hợp đồng (standalone: rare in slide context)
    "tương",   # tương tác, tương lai, tương đương
    "thực",    # thực tế, thực hành, thực hiện (standalone ending: odd in slides)
    "chính",   # chính sách, chính xác (only when clearly the first morpheme)
})

# Comprehensive Vietnamese + English function words.
# These words carry no standalone meaning at sentence END: prepositions,
# conjunctions, determiners, auxiliaries. Used to detect dangling tails
# without enumerating specific phrase patterns.
_VN_FUNCTION_WORDS = frozenset({
    # Vietnamese prepositions (always need NP/VP after them)
    "của", "cho", "với", "từ", "theo", "để", "nhằm", "gồm", "nhờ", "qua",
    "về", "đến", "thành", "trong", "ngoài", "bởi", "sau", "trước", "giữa",
    "đối", "tại", "vào", "ra", "lên", "xuống", "suốt", "trên", "dưới",
    "cạnh", "ngang", "dọc", "tới", "cùng",
    # Vietnamese conjunctions (connect to what follows)
    "và", "hoặc", "hay", "mà", "nhưng", "song", "vừa",
    "khi", "nếu", "tuy", "dù", "hễ", "miễn", "vì",
    # Vietnamese determiners / quantifiers (require following noun)
    "các", "những", "một", "mọi", "từng", "nhiều", "ít", "vài", "mấy",
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
    r"nhằm(?:\s+\S+)?"
    r"|bao\s+gồm(?:\s+\S+)?"
    r"|dựa\s+trên(?:\s+\S+)?"
    r"|dựa\s+vào(?:\s+\S+)?"
    r"|thông\s+qua(?:\s+\S+)?"
    r"|hướng\s+tới(?:\s+\S+)?"
    r"|nhờ\s+vào(?:\s+\S+)?"
    r"|kết\s+hợp\s+với(?:\s+\S+)?"
    r"|in\s+order\s+to(?:\s+\S+)?"
    r"|based\s+on(?:\s+\S+)?"
    r"|including(?:\s+\S+)?"
    r"|such\s+as(?:\s+\S+)?"
    r")"
    r"\s*[.,]?\s*$",
    re.IGNORECASE | re.UNICODE,
)


# Ký tự có dấu tiếng Việt (heuristic đoán input).
_VN_DIACRITIC_RE = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]"
)

# ---------------------------------------------------------------------------
# Tiêu đề slide vô nghĩa / placeholder thuần túy — bắt để thay thế.
# CHỈ bắt những tiêu đề THỰC SỰ là placeholder, không có nghĩa gì với nội dung.
# Tiêu đề như "Kết luận", "Giới thiệu", "Overview"... là HỢP LỆ nếu slide
# có nội dung tương ứng — KHÔNG đưa vào đây.
# ---------------------------------------------------------------------------
_GENERIC_TITLE_EXACT = frozenset({
    # Placeholder thuần tuý — không có ý nghĩa nội dung nào cả
    "nội dung", "noi dung",          # chỉ nghĩa là "content" — quá chung
    "tiêu đề", "tieu de",            # nghĩa là "title" — là placeholder
    "tiêu đề slide", "tieu de slide",
    "tiếp theo", "tiep theo",        # chỉ nghĩa "next" — không mô tả gì
    "slide",                         # một từ, không nghĩa
    "content",                       # một từ, không nghĩa
    "title",                         # một từ, không nghĩa
    "untitled",                      # rõ ràng là placeholder
    "next",                          # chỉ nghĩa "tiếp"
})

_GENERIC_TITLE_PREFIX_RE = re.compile(
    r"""^(?:
        # numbered Vietnamese — "Nội dung 1", "Phần 2", v.v. (có số đằng sau = placeholder)
        n[o\u1ed9][i\u1ecb]\s*dung\s*\d+    |  # nội dung 1, noi dung 2
        ph[a\u1ea7]n\s*\d+                   |  # phần 1, phan 2
        ch[\u01b0\u01a1u][o\u01a1]ng\s*\d+  |  # chương 1
        m[u\u1ee5]c\s*\d+                    |  # mục 1
        # numbered English — "Slide 1", "Section 2", v.v.
        slide\s*\d+                          |  # slide 1
        section\s*\d+                        |  # section 1
        part\s*\d+                           |  # part 1
        chapter\s*\d+                        |  # chapter 1
        page\s*\d+                           |  # page 1
        topic\s*\d+                             # topic 1
    )$""",
    re.IGNORECASE | re.VERBOSE | re.UNICODE,
)


def _is_generic_title(title: str) -> bool:
    """Trả về True nếu tiêu đề slide là placeholder vô nghĩa.

    Chỉ bắt các trường hợp THỰC SỰ vô nghĩa:
    - Trống / None
    - Placeholder rõ ràng: "Nội dung", "Tiêu đề", "Slide", "Next"...
    - Placeholder có số: "Nội dung 1", "Slide 3", "Phần 2"...

    KHÔNG bắt các tiêu đề cấu trúc hợp lệ như:
    "Kết luận", "Giới thiệu", "Tổng quan", "Overview", "Introduction"...
    vì chúng có thể hoàn toàn phù hợp với nội dung slide.
    """
    t = str(title or "").strip()
    if not t:
        return True
    tl = t.lower()
    if tl in _GENERIC_TITLE_EXACT:
        return True
    if _GENERIC_TITLE_PREFIX_RE.match(tl):
        return True
    return False



class SlideNormalizerMixin:

    def _sanitize_inline_markup(self, text: str) -> str:
        """Normalize model output to plain slide text, without markdown formatting."""
        if text is None:
            return ""
        t = unicodedata.normalize("NFKC", html.unescape(str(text))).strip()
        if not t:
            return ""
        t = t.translate(str.maketrans({
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2013": "-",
            "\u2014": "-",
            "\u2026": "...",
        }))
        t = re.sub(r"<[^>\n]{1,80}>", " ", t)
        t = re.sub(r"[•◦▪▫■□●○◆◇★☆✓✔✗✘➜→←↑↓↔]", " ", t)
        cleaned_chars: List[str] = []
        symbol_keep = set("$€£¥₫%‰+-=<>±×÷°")
        for ch in t:
            if ch == "\ufffd":
                continue
            cat = unicodedata.category(ch)
            if cat[0] == "C":
                cleaned_chars.append(" ")
                continue
            if cat[0] == "S" and ch not in symbol_keep:
                cleaned_chars.append(" ")
                continue
            cleaned_chars.append(ch)
        t = "".join(cleaned_chars)
        t = re.sub(r"^\s*(?:[-+*]|•)\s+", "", t)
        t = re.sub(r"^\s*\*+", "", t)
        t = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", t)
        t = re.sub(r"__([^_\n]+)__", r"\1", t)
        t = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", t)
        t = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"\1", t)
        t = re.sub(r"\*{2,}", "", t)
        t = re.sub(r"_{2,}", "", t)
        t = re.sub(r"\*+\s*:", ":", t)
        t = re.sub(r":\s*\*+\s*", ": ", t)
        t = re.sub(r"\s+\*+\s+", " ", t)
        t = re.sub(r"\s{2,}", " ", t)
        return t.strip()

    def _sanitize_title(self, title: str) -> str:
        """Dọn dẹp tiêu đề: loại bỏ markdown, quotes, và ký tự thừa."""
        if not title:
            return ""
        t = self._sanitize_inline_markup(str(title).strip())
        t = re.sub(r"^\s*#{1,6}\s*", "", t)
        t = re.sub(r"^\s*[-*•]\s*", "", t)
        t = re.sub(r"^\s*[→>]+\s*", "", t)
        t = re.sub(r"^\s*\d+(\.\d+)*\s*[-:.)]\s*", "", t)
        t = t.replace('"', '').replace("'", "").strip(".,;:!-“”‘’\"' ")
        return t

    def _derive_slide_title_from_bullets(
        self,
        bullets: List[Any],
        fallback: str = "Nội dung chính",
        *,
        max_words: int = 11,
    ) -> str:
        """Create a concrete slide title from the chunk's own bullets."""
        fallback_clean = self._sanitize_title(str(fallback or "Nội dung chính")) or "Nội dung chính"
        fallback_clean = re.sub(r"\s+-\s+Ph\S*\s+\d+\s*$", "", fallback_clean, flags=re.IGNORECASE).strip() or fallback_clean
        fallback_norm = re.sub(r"\W+", " ", fallback_clean.lower()).strip()

        for raw in bullets or []:
            text = self._sanitize_title(str(raw or ""))
            if not text:
                continue
            text = re.sub(r"^\s*(?:[-*•]|\d+[\).:-])\s*", "", text).strip()
            text = re.sub(
                r"^(?:điểm|ý|noi dung|nội dung|van de|vấn đề|luan diem|luận điểm)\s+\d+\s*[:.-]\s*",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip()
            if ":" in text and text.find(":") <= 48:
                candidate = text.split(":", 1)[0].strip()
            else:
                first_clause = re.split(r"[.;!?]", text, maxsplit=1)[0].strip()
                comma_clause = first_clause.split(",", 1)[0].strip()
                if len(comma_clause.split()) >= 4:
                    first_clause = comma_clause
                words = first_clause.split()
                candidate = " ".join(words[:max_words]).strip()
            candidate = self._sanitize_title(candidate)
            candidate_norm = re.sub(r"\W+", " ", candidate.lower()).strip()
            if len(candidate.split()) >= 3 and candidate_norm and candidate_norm != fallback_norm:
                return candidate[:90]

        return fallback_clean[:90]

    _VN_DIACRITIC_SAFE_RE = re.compile(
        "["
        "\u00e0\u00e1\u1ea3\u00e3\u1ea1"
        "\u0103\u1eb1\u1eaf\u1eb3\u1eb5\u1eb7"
        "\u00e2\u1ea7\u1ea5\u1ea9\u1eab\u1ead"
        "\u00e8\u00e9\u1ebb\u1ebd\u1eb9"
        "\u00ea\u1ec1\u1ebf\u1ec3\u1ec5\u1ec7"
        "\u00ec\u00ed\u1ec9\u0129\u1ecb"
        "\u00f2\u00f3\u1ecf\u00f5\u1ecd"
        "\u00f4\u1ed3\u1ed1\u1ed5\u1ed7\u1ed9"
        "\u01a1\u1edd\u1edb\u1edf\u1ee1\u1ee3"
        "\u00f9\u00fa\u1ee7\u0169\u1ee5"
        "\u01b0\u1eeb\u1ee9\u1eed\u1eef\u1ef1"
        "\u1ef3\u00fd\u1ef7\u1ef9\u1ef5"
        "\u0111\u0110"
        "]",
        re.IGNORECASE,
    )
    _EN_FUNCTION_SAFE_RE = re.compile(
        r"\b(the|and|or|of|for|with|to|from|in|on|at|by|as|is|are|was|were|be|this|that|which|will|can|should|would|could)\b",
        re.IGNORECASE,
    )

    def _detect_slide_language(self, title: str, bullets: List[str]) -> str:
        text = " ".join([str(title or "")] + [str(b or "") for b in (bullets or [])])
        if len(self._VN_DIACRITIC_SAFE_RE.findall(text)) >= 2:
            return "vi"
        if len(self._EN_FUNCTION_SAFE_RE.findall(text)) >= 3:
            return "en"
        if len(re.findall(r"[A-Za-z]{3,}", text)) >= 5:
            return "en"
        return "vi"

    def _build_default_speaker_notes(self, title: str, bullets: List[str]) -> str:
        clean_title = str(title or "").strip()
        clean_bullets = [str(b or "").strip().rstrip(".") for b in (bullets or []) if str(b or "").strip()]
        if not clean_bullets:
            return ""
        if self._detect_slide_language(clean_title, clean_bullets) == "en":
            opener = f"On this slide, I will present {clean_title}." if clean_title else "On this slide, I will present the main points."
            body_parts = []
            for idx, bullet in enumerate(clean_bullets[:4]):
                if idx == 0:
                    body_parts.append(f"The first point to note is that {bullet}.")
                elif idx == 1:
                    body_parts.append(f"Next, {bullet}.")
                elif idx == 2:
                    body_parts.append(f"In addition, {bullet}.")
                else:
                    body_parts.append(f"Finally, {bullet}.")
            return " ".join([opener] + body_parts).strip()
        opener = f"Ở slide này, em sẽ trình bày về {clean_title}." if clean_title else "Ở slide này, em sẽ trình bày nội dung chính."
        body_parts = []
        for idx, bullet in enumerate(clean_bullets[:4]):
            if idx == 0:
                body_parts.append(f"Điểm đầu tiên cần chú ý là {bullet}.")
            elif idx == 1:
                body_parts.append(f"Tiếp theo, {bullet}.")
            elif idx == 2:
                body_parts.append(f"Ngoài ra, {bullet}.")
            else:
                body_parts.append(f"Cuối cùng, {bullet}.")
        return " ".join([opener] + body_parts).strip()

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
            return {"title": "Bài thuyết trình", "slides": []}

        title = structured_content.get("title")
        if not isinstance(title, str) or not title.strip():
            title = "Bài thuyết trình"

        slides_in = structured_content.get("slides", [])
        if not isinstance(slides_in, list):
            slides_in = []

        if structured_content.get("_explicit_slide_mode"):
            explicit_slides: List[Dict[str, Any]] = []
            for idx, slide in enumerate(slides_in):
                if not isinstance(slide, dict):
                    continue
                raw_title = str(slide.get("title") or f"Slide {idx + 1}").strip()
                title_clean = self._sanitize_title(raw_title)[:120] or f"Slide {idx + 1}"
                raw_bullets = slide.get("bullets") or slide.get("content") or []
                if isinstance(raw_bullets, str):
                    bullet_items = [raw_bullets]
                elif isinstance(raw_bullets, list):
                    bullet_items = raw_bullets
                else:
                    bullet_items = []
                bullets_clean = [
                    self._sanitize_inline_markup(str(b).strip())
                    for b in bullet_items
                    if self._sanitize_inline_markup(str(b).strip())
                ]
                if not bullets_clean:
                    bullets_clean = [title_clean]
                notes = self._sanitize_inline_markup(
                    str(slide.get("script") or slide.get("speaker_notes") or slide.get("notes") or "").strip()
                )
                if not notes:
                    notes = self._build_default_speaker_notes(title_clean, bullets_clean)
                out_slide: Dict[str, Any] = {
                    "title": title_clean,
                    "bullets": bullets_clean[:MAX_BULLETS_PER_SLIDE],
                    "notes": notes,
                    "script": notes,
                }
                for visual_key in ("table", "chart", "image_url"):
                    if slide.get(visual_key):
                        out_slide[visual_key] = slide.get(visual_key)
                explicit_slides.append(out_slide)
            return {
                "title": self._sanitize_title(str(title).strip())[:120],
                "slides": explicit_slides,
                "_explicit_slide_mode": True,
            }

        def _clean_bullet(text: str, _max_words: int) -> str:
            """Strip artifacts, repair tails, hard-cut tại _max_words để giữ bullet súc tích."""
            t = (text or "").strip()
            # Remove accidental markdown/heading markers inside bullets
            t = re.sub(r"^\s*#{1,6}\s*", "", t)
            t = re.sub(r"^\s*[-*•]\s*", "", t)
            t = re.sub(r"^\s*[→>]+\s*", "", t)
            # Remove leading numbering like "1.", "2.3", "1-"
            t = re.sub(r"^\s*\d+(\.\d+)*\s*[-:.)]\s*", "", t)
            # Strip trailing ... or … (model's copy-paste artifact)
            t = re.sub(r'[…\.]{2,}\s*$', '', t).strip()
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
            if t and not re.search(r'[\.!?]$', t):
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
            if _is_generic_title(slide_title):
                slide_title = None
                if bullets_list:
                    first_b = bullets_list[0].strip()
                    if ":" in first_b and first_b.find(":") < 30:
                        slide_title = first_b.split(":", 1)[0].strip()
                    else:
                        words = first_b.split()
                        slide_title = " ".join(words[:5]).strip(".,;:!-“”‘’\"' ")
                if not slide_title or not slide_title.strip():
                    slide_title = "Nội dung"

            def _norm_compare(s: str) -> str:
                # Normalize for approximate equality checks (avoid accepting bullet duplicated title).
                t = (s or "").strip().lower()
                t = re.sub(r"\s+", " ", t)
                t = t.strip(" \t\n\r\"'“”“”‘’.,;:!?-—–()[]{}")
                return t

            # Enforce spec: đủ bullet dài để slide có ý; bỏ bullet cụt ngay (không đưa vào deck).
            cleaned_bullets: List[str] = []
            for b in bullets_list:
                if not b.strip():
                    continue
                cb = _clean_bullet(b.strip(), MAX_WORDS_PER_BULLET)
                cb = self._sanitize_inline_markup(cb)
                if not cb or self._is_truncated_bullet(cb):
                    continue
                cleaned_bullets.append(cb)
            cleaned_bullets = cleaned_bullets[:MAX_BULLETS_PER_SLIDE]

            def _bullet_ok(s: str) -> bool:
                """Loại bullet kiểu vài chữ / không đủ ngữ cảnh (hay gặp khi model lười)."""
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
            notes = self._sanitize_inline_markup(notes.strip())
            if not notes:
                notes = self._build_default_speaker_notes(slide_title, bullets_list)

            out_slide = {
                "title": self._sanitize_title(slide_title.strip())[:120],
                "bullets": bullets_list,
                "notes": notes,
                "script": notes,
            }
            for visual_key in ("table", "chart", "image_url"):
                if slide.get(visual_key):
                    out_slide[visual_key] = slide.get(visual_key)
            slides_out.append(out_slide)

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
            notes = self._sanitize_inline_markup(notes)
            if not notes:
                notes = self._build_default_speaker_notes(str(s.get("title") or ""), s.get("bullets") or [])
            s["notes"] = notes
            s["script"] = notes
        title_counts: Dict[str, int] = {}
        for s in slides_out:
            if not isinstance(s, dict):
                continue
            original_title = str(s.get("title") or "Nội dung").strip()
            base_title = re.sub(
                r"\s*\([^)]*(?:tiếp|tiep|continued|cont\.?|tiáº|tiÃ|tiÃ¡)[^)]*\)\s*$",
                "",
                original_title,
                flags=re.IGNORECASE,
            ).strip() or original_title
            title_counts[base_title] = title_counts.get(base_title, 0) + 1
            count = title_counts[base_title]
            s["title"] = base_title if count == 1 else f"{base_title} - Phần {count}"
        final_seen_titles: set[str] = set()
        for s in slides_out:
            if not isinstance(s, dict):
                continue
            current_title = str(s.get("title") or "").strip()
            key = re.sub(r"\W+", " ", current_title.lower()).strip()
            if " - Ph" in current_title or key in final_seen_titles or self._is_truncated_bullet(current_title):
                s["title"] = self._derive_slide_title_from_bullets(
                    s.get("bullets") or [],
                    fallback=current_title,
                    max_words=11,
                )
                key = re.sub(r"\W+", " ", str(s.get("title") or "").lower()).strip()
            final_seen_titles.add(key)
        normalized = {"title": self._sanitize_title(title.strip())[:120], "slides": slides_out}
        if structured_content.get("_explicit_slide_mode"):
            normalized["_explicit_slide_mode"] = True
        return normalized

    def _slide_content_tokens(self, slide: Dict[str, Any]) -> set[str]:
        """Tách các từ (tokens) từ tiêu đề và bullets của slide để đo độ trùng lặp."""
        if not isinstance(slide, dict):
            return set()
        words: List[str] = []
        title = slide.get("title") or ""
        if isinstance(title, str):
            words.extend(re.findall(r"\w+", title.lower()))
        bullets = slide.get("bullets") or []
        if isinstance(bullets, list):
            for bullet in bullets:
                if isinstance(bullet, str):
                    words.extend(re.findall(r"\w+", bullet.lower()))
        return set(words)

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

        # 1b. Dedup slides có nội dung quá trùng (token overlap > 65%) —
        #     áp dụng khi deck >= 6 slide, gộp bullet vào slide trước thay vì xoá hẳn.
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
                    # Gộp bullet mới vào slide đã có (bỏ trùng)
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

        # 3. Rescue thin slides: đảm bảo mỗi slide có ít nhất 3 bullets (đúng spec),
        #    bằng cách "cho mượn" bullet từ slide lân cận nếu chúng có dư > 3.
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
                # Take from previous if previous has dư
                if i - 1 >= 0:
                    bs_prev = slides[i - 1].get("bullets") or []
                    if isinstance(bs_prev, list) and len(bs_prev) > min_required:
                        donated = bs_prev.pop()
                        slides[i]["bullets"].insert(0, donated)
                        changed = True
                        continue
                # Take from next if previous không đủ
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

        # 5. Gộp slide chỉ còn 1 bullet vào slide trước nếu còn chỗ (tránh "một dòng một slide")
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

        # FINAL SPEC: sau khi merge, chạy lại pass đảm bảo mỗi slide có >= 3 bullets.
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
        ≥ 3 content words (non-function-words) to be considered meaningful.
        This catches ANY dangling pattern regardless of specific word choice.
        """
        t = re.sub(r"\s+", " ", (text or "").strip())
        if not t:
            return t

        # Remove hanging delimiters first.
        t = re.sub(r"[,;:\-——/]\s*$", "", t).strip()

        # ── General content-word check (language-agnostic) ─────────────────────
        # If the last clause (after , or ;) has < 3 content words it is dangling.
        # Examples that get trimmed:
        #   "... kỹ thuật, thiết bị di động và."    → tail has 2 content words → drop
        #   "... tối ưu hóa thông qua các công cụ." → tail has 3+ content words → keep
        m = re.search(r"([,;])\s*(.+)$", t)
        if m:
            tail_raw = m.group(2).strip().rstrip(".!?")
            content_count = self._count_content_words(tail_raw)
            tail_word_count = len(tail_raw.split())
            if content_count < 3 and tail_word_count <= 7:
                head = t[: m.start()].strip()
                if len(head.split()) >= 4:
                    t = head

        # ── Belt-and-suspenders: specific multi-word dangling connectors ────────
        bare = t.rstrip(".!?").rstrip()
        m2 = _DANGLING_TAIL_RE.search(bare)
        if m2:
            head = bare[: m2.start()].strip()
            if len(head.split()) >= 4:
                t = head

        # ── Sino-Vietnamese bound morpheme ending ──────────────────────────────
        # e.g. "...xây dựng cộng đồng trung." → LLM wrote "trung" but meant
        # "trung thành"; the morpheme cannot stand alone → drop it.
        words = t.rstrip(".!?").split()
        if words:
            last = re.sub(r"[^\w]+", "", words[-1]).lower()
            if last in _VN_BOUND_PREFIXES and len(words) >= 4:
                t = " ".join(words[:-1]).strip()
                words = t.rstrip(".!?").split()  # refresh for next check

        # ── Single function-word ending ─────────────────────────────────────────
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
        if re.search(r"(?:\.\.\.|…)\s*$", t):
            score += 3
        if re.search(r"[,;:\-——/]\s*$", t):
            score += 2
        if len(t) >= 32 and not re.search(r"[\.!?]$", t):
            score += 2
        if not self._has_balanced_delimiters(t):
            score += 2

        # General: last clause (after , or ;) has too few content words → dangling.
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


    async def _force_slide_count_exact(self, structured_content: Dict[str, Any], desired_slides: int) -> Dict[str, Any]:
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

        original_count = len(slides)

        def _split_one(slides_list: List[Dict[str, Any]]) -> bool:
            # Pick slide with max bullets (>1) to split.
            candidates = [
                (idx, len(s.get("bullets") or []))
                for idx, s in enumerate(slides_list)
                if isinstance(s, dict) and len(s.get("bullets") or []) > 1
            ]
            if not candidates:
                # Recovery: nếu tất cả slide đều chỉ còn 1 bullet, không muốn lặp slide,
                # ta thử tách 1 bullet dài thành 2 bullet để tạo thêm slide.
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
                # Need đủ dài để tách
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
                base_title = re.sub(
                    r"\s*\([^)]*(?:tiếp|tiep|continued|cont\.?|tiáº|tiÃ|tiÃ¡)[^)]*\)\s*$",
                    "",
                    str(slide.get("title") or "Nội dung"),
                    flags=re.IGNORECASE,
                ).strip() or str(slide.get("title") or "Nội dung")
                new_slide["title"] = f"{base_title} - Phần 2"
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
            base_title = re.sub(
                r"\s*\([^)]*(?:tiếp|tiep|continued|cont\.?|tiáº|tiÃ|tiÃ¡)[^)]*\)\s*$",
                "",
                str(slide.get("title") or "Nội dung"),
                flags=re.IGNORECASE,
            ).strip() or str(slide.get("title") or "Nội dung")
            new_slide["title"] = f"{base_title} - Phần 2"
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
                base_title = re.sub(
                    r"\s*\([^)]*(?:tiếp|tiep|continued|cont\.?|tiáº|tiÃ|tiÃ¡)[^)]*\)\s*$",
                    "",
                    str(last.get("title") or "Nội dung"),
                    flags=re.IGNORECASE,
                ).strip() or str(last.get("title") or "Nội dung")
                last["title"] = f"{base_title} - Phần 2"
                slides.append(last)
                break

        if len(slides) > desired_slides:
            slides = slides[:desired_slides]
        structured_content["slides"] = slides

        # HARD FIX: nếu slide có <2 bullets thì chuyển 1 bullet từ slide lân cận sang
        # (giữ nguyên slide count, chỉ "bơm chữ" để tránh 1 slide 1 dòng).
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

        # If slide count changed or any "(tiếp)" slides are present, run density and quality gates.
        has_tiep_slides = any("(tiếp)" in str(s.get("title") or "") or "(continued)" in str(s.get("title") or "").lower() for s in slides)
        if len(slides) != original_count or has_tiep_slides:
            try:
                from config import LLM_FINAL_DENSITY_GATE, LLM_FINAL_QUALITY_GATE
            except Exception:
                LLM_FINAL_DENSITY_GATE = True
                LLM_FINAL_QUALITY_GATE = True

            if LLM_FINAL_DENSITY_GATE and hasattr(self, "_run_final_density_gate"):
                print(f"[slide_normalizer] re-running density gate on forced deck (count={desired_slides})")
                structured_content = await self._run_final_density_gate(structured_content)

            if LLM_FINAL_QUALITY_GATE and hasattr(self, "_run_final_quality_gate"):
                print(f"[slide_normalizer] re-running quality gate on forced deck")
                structured_content = await self._run_final_quality_gate(structured_content)

        title_counts: Dict[str, int] = {}
        for slide in structured_content.get("slides") or []:
            if not isinstance(slide, dict):
                continue
            original_title = str(slide.get("title") or "Nội dung").strip()
            base_title = re.sub(
                r"\s*\([^)]*(?:tiếp|tiep|continued|cont\.?|tiáº|tiÃ|tiÃ¡)[^)]*\)\s*$",
                "",
                original_title,
                flags=re.IGNORECASE,
            ).strip() or original_title
            title_counts[base_title] = title_counts.get(base_title, 0) + 1
            count = title_counts[base_title]
            slide["title"] = base_title if count == 1 else f"{base_title} - Phần {count}"

        final_seen_titles: set[str] = set()
        for slide in structured_content.get("slides") or []:
            if not isinstance(slide, dict):
                continue
            current_title = str(slide.get("title") or "").strip()
            key = re.sub(r"\W+", " ", current_title.lower()).strip()
            if " - Ph" in current_title or key in final_seen_titles or self._is_truncated_bullet(current_title):
                slide["title"] = self._derive_slide_title_from_bullets(
                    slide.get("bullets") or [],
                    fallback=current_title,
                    max_words=11,
                )
                key = re.sub(r"\W+", " ", str(slide.get("title") or "").lower()).strip()
            final_seen_titles.add(key)

        return structured_content
