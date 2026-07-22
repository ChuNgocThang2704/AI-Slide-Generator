"""Làm sạch, chuẩn hóa và cân bằng danh sách bullet của slide deck.

SlideNormalizerMixin cung cấp tất cả logic hậu xử lý cho JSON slide được tạo
bởi LLM: làm sạch các bullet, cân bằng deck, sửa các câu bị cắt cụt và
bắt buộc số lượng slide chính xác.
"""
from __future__ import annotations

import html
import json
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
        # Các từ nối luôn cần phần tiếp theo để tạo thành ý nghĩa hoàn chỉnh.
        "nhằm",  # "in order to" — luôn đi trước một cụm động từ
        "gồm",   # "includes" — luôn đi trước danh sách các mục
        "nhờ",   # "thanks to / through" — luôn đi trước phương tiện/nguyên nhân
    }
)

# Các từ Hán-Việt liên kết KHÔNG BAO GIỜ kết thúc câu một cách hợp lệ khi đứng một mình.
# Mỗi mục là âm tiết ĐẦU TIÊN của một từ ghép phổ biến mà bắt buộc phải có từ đi kèm
# (ví dụ: "trung" → trung thành / trung tâm / trung thực).
# Được phát hiện trong _repair_incomplete_tail và _is_truncated_bullet.
_VN_BOUND_PREFIXES = frozenset({
    "trung",   # trung thành, trung tâm, trung thực, trung bình, trung lập
    "bất",     # bất kỳ, bất ngờ, bất hợp (pháp)
    "vô",      # vô cùng, vô ích, vô lý, vô hiệu
    "siêu",    # siêu thị, siêu tốc, siêu âm
    "tiểu",    # tiểu thuyết, tiểu học, tiểu đường
    "đại",     # đại học, đại diện, đại dương (đứng cuối câu rất hiếm)
    "phi",     # phi lợi nhuận, phi tập trung
    "hợp",     # hợp pháp, hợp lệ, hợp đồng (đứng độc lập ở cuối câu rất hiếm trong slide)
    "tương",   # tương tác, tương lai, tương đương
    "thực",    # thực tế, thực hành, thực hiện (kết thúc độc lập trông lạ trong slide)
    "chính",   # chính sách, chính xác (chỉ khi rõ ràng là âm tiết đầu)
})

# Danh sách đầy đủ các hư từ (function words) tiếng Việt + tiếng Anh.
# Các từ này không mang ý nghĩa độc lập khi đứng ở CUỐI câu: giới từ,
# liên từ, từ hạn định, trợ từ. Dùng để phát hiện các đoạn cuối bị lơ lửng
# mà không cần liệt kê từng mẫu cụm từ cụ thể.
_VN_FUNCTION_WORDS = frozenset({
    # Giới từ tiếng Việt (luôn cần cụm danh từ/cụm động từ phía sau)
    "của", "cho", "với", "từ", "theo", "để", "nhằm", "gồm", "nhờ", "qua",
    "về", "đến", "thành", "trong", "ngoài", "bởi", "sau", "trước", "giữa",
    "đối", "tại", "vào", "ra", "lên", "xuống", "suốt", "trên", "dưới",
    "cạnh", "ngang", "dọc", "tới", "cùng",
    # Liên từ tiếng Việt (kết nối với phần đi sau)
    "và", "hoặc", "hay", "mà", "nhưng", "song", "vừa",
    "khi", "nếu", "tuy", "dù", "hễ", "miễn", "vì",
    # Từ hạn định / từ chỉ số lượng tiếng Việt (yêu cầu danh từ đi sau)
    "các", "những", "một", "mọi", "từng", "nhiều", "ít", "vài", "mấy",
    # Các từ tương đương trong tiếng Anh
    "the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "at",
    "by", "with", "from", "as", "but", "nor", "yet", "so", "when", "if",
    "including", "through", "via", "based", "such", "than", "rather",
    "which", "that", "this", "these", "those",
})

# Biện pháp dự phòng bổ sung: các từ nối lơ lửng gồm nhiều từ để tăng độ bao phủ.
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
        # Số thứ tự tiếng Việt — "Nội dung 1", "Phần 2", v.v. (có số đằng sau = placeholder)
        n[o\u1ed9][i\u1ecb]\s*dung\s*\d+    |  # nội dung 1, noi dung 2
        ph[a\u1ea7]n\s*\d+                   |  # phần 1, phan 2
        ch[\u01b0\u01a1u][o\u01a1]ng\s*\d+  |  # chương 1
        m[u\u1ee5]c\s*\d+                    |  # mục 1
        # Số thứ tự tiếng Anh — "Slide 1", "Section 2", v.v.
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
        """Chuẩn hóa đầu ra của mô hình thành văn bản slide thuần túy, không có định dạng markdown."""
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
        """Tạo tiêu đề slide cụ thể từ các bullet của chính chunk đó."""
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
                # Cắt chuỗi an toàn theo ranh giới từ (word-boundary slicing)
                c_str = candidate.strip()
                if len(c_str) <= 90:
                    return c_str
                trimmed = c_str[:90]
                last_space = trimmed.rfind(" ")
                return trimmed[:last_space].strip(".,;:!-“”‘’\"' ") if last_space > 0 else trimmed

        fb_str = fallback_clean.strip()
        if len(fb_str) <= 90:
            return fb_str
        trimmed_fb = fb_str[:90]
        last_space_fb = trimmed_fb.rfind(" ")
        return trimmed_fb[:last_space_fb].strip(".,;:!-“”‘’\"' ") if last_space_fb > 0 else trimmed_fb

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
        folded = unicodedata.normalize("NFKD", text).replace("đ", "d").replace("Đ", "D")
        folded = "".join(ch for ch in folded if not unicodedata.combining(ch)).lower()
        vn_ascii_hits = sum(
            1
            for pattern in (
                r"\bhe\s+thong\b",
                r"\bquan\s+ly\b",
                r"\bdu\s+lieu\b",
                r"\bnguoi\s+dung\b",
                r"\bvan\s+hanh\b",
                r"\btrinh\s+bay\b",
                r"\btoc\s+do\b",
                r"\bchi\s+phi\b",
                r"\bsinh\s+vien\b",
                r"\btruong\s+dai\s+hoc\b",
            )
            if re.search(pattern, folded)
        )
        if vn_ascii_hits >= 2:
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
            transitions = ("To begin,", "A second point is", "This also means", "Taken together,")
            body = [f"{transitions[idx]} {bullet}." for idx, bullet in enumerate(clean_bullets[:4])]
            body.append("These points provide the context needed for the next part of the presentation.")
            return " ".join(body).strip()
        transitions = ("Trước hết,", "Điểm tiếp theo là", "Điều này cũng cho thấy", "Nhìn tổng thể,")
        body = [f"{transitions[idx]} {bullet}." for idx, bullet in enumerate(clean_bullets[:4])]
        body.append("Các ý trên là cơ sở để chuyển sang nội dung tiếp theo của bài trình bày.")
        return " ".join(body).strip()

    @staticmethod
    def _speaker_notes_need_fallback(notes: str) -> bool:
        text = re.sub(r"\s+", " ", str(notes or "")).strip()
        if len(text.split()) < 35:
            return True
        return bool(
            re.search(
                r"\b(?:slide|trang)\s+(?:này|nay)\s+(?:giới\s+thiệu|gioi\s+thieu|trình\s+bày|trinh\s+bay|mô\s+tả|mo\s+ta|tóm\s+tắt|tom\s+tat|nhấn\s+mạnh|nhan\s+manh)\b"
                r"|\bthis\s+slide\s+(?:introduces|presents|describes|summarizes|highlights)\b",
                text,
                flags=re.IGNORECASE,
            )
        )

    def _normalize_structured_content(self, structured_content: Dict[str, Any]) -> Dict[str, Any]:
        """Chuẩn hóa cấu trúc nội dung về định dạng JSON slide chuẩn.

        Định dạng chuẩn:
        {
          "title": str,
          "slides": [{"title": str, "bullets": [str], "notes": str}]
        }

        Tương thích ngược: chấp nhận trường "content" cũ dưới dạng các bullet.
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
                title_clean = self._sanitize_title(raw_title) or f"Slide {idx + 1}"
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
                out_slide: Dict[str, Any] = {
                    "title": title_clean,
                    "bullets": bullets_clean[:MAX_BULLETS_PER_SLIDE],
                    "notes": notes,
                }
                for visual_key in ("table", "chart", "image_url"):
                    if slide.get(visual_key):
                        out_slide[visual_key] = slide.get(visual_key)
                explicit_slides.append(out_slide)
            return {
                "title": self._sanitize_title(str(title).strip()),
                "slides": explicit_slides,
                "_explicit_slide_mode": True,
            }

        def _clean_bullet(text: str, _max_words: int) -> str:
            """Loại bỏ các ký tự thừa, sửa các câu bị cụt, cắt cứng tại _max_words để giữ bullet súc tích."""
            t = (text or "").strip()
            _max_words = 0  # Let the LLM quality pass shorten content semantically.
            # Loại bỏ các ký tự markdown/tiêu đề vô tình xuất hiện trong bullet
            t = re.sub(r"^\s*#{1,6}\s*", "", t)
            t = re.sub(r"^\s*[-*•]\s*", "", t)
            t = re.sub(r"^\s*[→>]+\s*", "", t)
            # Loại bỏ số thứ tự ở đầu như "1.", "2.3", "1-"
            t = re.sub(r"^\s*\d+(\.\d+)*\s*[-:.)]\s*", "", t)
            # Loại bỏ các dấu ... hoặc … ở cuối (lỗi sao chép-dán của mô hình)
            t = re.sub(r'[…\.]{2,}\s*$', '', t).strip()
            t = t.rstrip(',(').strip()
            t = re.sub(r'\s+', ' ', t)
            # Giới hạn độ dài: tôn trọng ranh giới câu để tránh cắt giữa chừng.
            if _max_words and _max_words > 0:
                words = t.split()
                if len(words) > _max_words:
                    # Chiến lược A: ranh giới câu TRƯỚC giới hạn từ (lý tưởng).
                    candidate = " ".join(words[:_max_words])
                    cut = None
                    for sep in (".", "!", "?", ";"):
                        pos = candidate.rfind(sep)
                        if pos > len(candidate) // 2:
                            cut = candidate[: pos + 1].strip()
                            break

                    if cut is None:
                        # Chiến lược B: không có ranh giới câu trước giới hạn từ — cố gắng mở rộng thêm tối đa
                        # _max_words + 8 để tìm nơi câu hiện tại kết thúc một cách tự nhiên.
                        # Điều này tránh hoàn toàn việc cắt ngang giữa câu.
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
                            # Chiến lược C: hoàn toàn không có ranh giới câu — cắt tại ranh giới mệnh đề cuối cùng
                            # (dấu phẩy) để giữ lại ít nhất một mệnh đề hoàn chỉnh.
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
            if not str(slide_title or "").strip():
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
                # Chuẩn hóa để kiểm tra độ trùng lặp xấp xỉ (tránh việc bullet trùng với tiêu đề).
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
                # Loại bullet kiểu vài chữ / không đủ ngữ cảnh (hay gặp khi model lười).
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

            # Loại bỏ các bullet trùng lặp với tiêu đề slide (lỗi phổ biến).
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
                # Đồng thời loại bỏ các bullet trùng lặp xấp xỉ để tránh lặp lại các dòng.
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

            out_slide = {
                "title": self._sanitize_title(slide_title.strip()),
                "bullets": bullets_list,
                "notes": notes,
            }
            for visual_key in ("table", "chart", "image_url"):
                if slide.get(visual_key):
                    out_slide[visual_key] = slide.get(visual_key)
            slides_out.append(out_slide)

        slides_out = self._balance_deck(slides_out)
        # Loại bỏ trùng lặp bullet trên toàn bộ slide deck (giảm thiểu "lặp lại giữa các slide").
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
            # Không bao giờ làm hỏng yêu cầu chỉ vì các thuật toán loại trùng.
            pass
        for s in slides_out:
            if not isinstance(s, dict):
                continue
            slide_notes = str(s.get("speaker_notes") or s.get("notes") or "").strip()
            slide_notes = self._sanitize_inline_markup(slide_notes)
            s["notes"] = slide_notes
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
            final_seen_titles.add(key)
        normalized = {"title": self._sanitize_title(title.strip()), "slides": slides_out}
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
        """Hậu xử lý danh sách slide: loại trùng theo tiêu đề + độ tương đồng ngữ nghĩa, bỏ slide trống, cứu các slide thưa thớt."""
        if not slides:
            return slides

        # 1. Loại trùng theo tiêu đề khớp chính xác: giữ slide đầu tiên, gộp bullet nếu tìm thấy tiêu đề trùng lặp
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

        # 2. Bỏ các slide không có bullet nào
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
                # Lấy từ slide trước nếu slide trước có dư
                if i - 1 >= 0:
                    bs_prev = slides[i - 1].get("bullets") or []
                    if isinstance(bs_prev, list) and len(bs_prev) > min_required:
                        donated = bs_prev.pop()
                        slides[i]["bullets"].insert(0, donated)
                        changed = True
                        continue
                # Lấy từ slide sau nếu slide trước không đủ
                if i + 1 < len(slides):
                    bs_next = slides[i + 1].get("bullets") or []
                    if isinstance(bs_next, list) and len(bs_next) > min_required:
                        donated = bs_next.pop(0)
                        slides[i]["bullets"].append(donated)
                        changed = True

        # 4. Gộp các cặp slide liên tiếp chỉ có 1 bullet thành một slide
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
        """Loại bỏ các khối suy nghĩ (thinking blocks) và các khối markdown trước khi phân tích JSON."""
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = text.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
            if m:
                text = m.group(1).strip()
        return text

    def _has_balanced_delimiters(self, text: str) -> bool:
        """Kiểm tra sự cân bằng của các dấu ngoặc/dấu nháy để phát hiện các cụm từ bị mở một nửa."""
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

        # Cân bằng dấu nháy (bỏ qua dấu nháy đơn bên trong từ).
        clean = re.sub(r"(?<=\w)'(?=\w)", "", text)
        clean = re.sub(r'(?<=\w)"(?=\w)', "", clean)
        if clean.count('"') % 2 != 0:
            return False
        if clean.count("'") % 2 != 0:
            return False
        return True

    @staticmethod
    def _count_content_words(phrase: str) -> int:
        """Đếm các từ KHÔNG nằm trong tập hợp hư từ (mang ý nghĩa ngữ nghĩa thực sự)."""
        return sum(
            1 for w in phrase.split()
            if re.sub(r"[^\w]+", "", w).lower() not in _VN_FUNCTION_WORDS
        )

    def _repair_incomplete_tail(self, text: str) -> str:
        """Cắt bỏ các mệnh đề lơ lửng ở cuối bằng mật độ từ mang ý nghĩa + các mẫu cụ thể.

        Nguyên tắc chung: sau dấu , hoặc ; cuối cùng, phần đuôi còn lại phải chứa
        ≥ 3 từ mang ý nghĩa (không phải hư từ) để được coi là có nghĩa.
        Điều này phát hiện BẤT KỲ mẫu lơ lửng nào bất kể từ ngữ cụ thể được chọn.
        """
        t = re.sub(r"\s+", " ", (text or "").strip())
        if not t:
            return t

        # Loại bỏ các dấu phân cách lơ lửng trước tiên.
        t = re.sub(r"[,;:\-——/]\s*$", "", t).strip()

        # ── Kiểm tra từ mang ý nghĩa nói chung (không phụ thuộc ngôn ngữ) ────────
        # Nếu mệnh đề cuối cùng (sau dấu , hoặc ;) có < 3 từ mang ý nghĩa thì nó là lơ lửng.
        # Các ví dụ sẽ bị cắt bỏ:
        #   "... kỹ thuật, thiết bị di động và."    → phần đuôi có 2 từ mang ý nghĩa → bỏ
        #   "... tối ưu hóa thông qua các công cụ." → phần đuôi có >= 3 từ mang ý nghĩa → giữ
        m = re.search(r"([,;])\s*(.+)$", t)
        if m:
            tail_raw = m.group(2).strip().rstrip(".!?")
            content_count = self._count_content_words(tail_raw)
            tail_word_count = len(tail_raw.split())
            if content_count < 3 and tail_word_count <= 7:
                head = t[: m.start()].strip()
                if len(head.split()) >= 4:
                    t = head

        # ── Biện pháp dự phòng bổ sung: các từ nối lơ lửng gồm nhiều từ ────────
        bare = t.rstrip(".!?").rstrip()
        m2 = _DANGLING_TAIL_RE.search(bare)
        if m2:
            head = bare[: m2.start()].strip()
            if len(head.split()) >= 4:
                t = head

        # ── Từ Hán-Việt ghép bị cụt ─────────────────────────────────────────────
        # Ví dụ: "...xây dựng cộng đồng trung." → LLM viết "trung" nhưng ý là
        # "trung thành"; từ ghép không thể đứng một mình → bỏ nó đi.
        words = t.rstrip(".!?").split()
        if words:
            last = re.sub(r"[^\w]+", "", words[-1]).lower()
            if last in _VN_BOUND_PREFIXES and len(words) >= 4:
                t = " ".join(words[:-1]).strip()
                words = t.rstrip(".!?").split()  # cập nhật lại để kiểm tra tiếp

        # ── Kết thúc bằng một hư từ đơn độc ───────────────────────────────────────
        if words:
            last = re.sub(r"[^\w]+", "", words[-1]).lower()
            if last in _VN_FUNCTION_WORDS and len(words) >= 5:
                t = " ".join(words[:-1]).strip()

        t = t.strip()
        if t and not re.search(r"[.!?]$", t):
            t += "."
        return t

    def _is_truncated_bullet(self, text: str) -> bool:
        """Phát hiện câu bị cắt cụt dựa trên điểm số, phần lớn không phụ thuộc ngôn ngữ."""
        raw = (text or "").strip()
        if not raw:
            return False
        t = re.sub(r"\s+", " ", raw)
        score = 0

        # Tín hiệu mạnh.
        if re.search(r"(?:\.\.\.|…)\s*$", t):
            score += 3
        if re.search(r"[,;:\-——/]\s*$", t):
            score += 2
        if len(t) >= 32 and not re.search(r"[\.!?]$", t):
            score += 2
        if not self._has_balanced_delimiters(t):
            score += 2

        # Tổng quát: mệnh đề cuối cùng (sau dấu , hoặc ;) có quá ít từ mang ý nghĩa → lơ lửng.
        _mc = re.search(r"[,;]\s*(.+)$", t)
        if _mc:
            _tail = _mc.group(1).strip().rstrip(".!?")
            _cc = self._count_content_words(_tail)
            _tw = len(_tail.split())
            if _cc < 3 and _tw <= 7:
                score += 3

        # Các cụm từ nối lơ lửng cụ thể ở cuối.
        if _DANGLING_TAIL_RE.search(t.rstrip(".!?")):
            score += 3

        # Tiền tố Hán-Việt liên kết ở cuối câu (không bao giờ đứng độc lập).
        _w = t.rstrip(".!?").split()
        if _w:
            _last = re.sub(r"[^\w]+", "", _w[-1]).lower()
            if _last in _VN_BOUND_PREFIXES and len(_w) >= 4:
                score += 4
            elif _last in _VN_FUNCTION_WORDS and len(_w) >= 4:
                score += 3

        # Tín hiệu yếu: mệnh đề cuối sau dấu phân cách quá ngắn để tạo thành nghĩa.
        m = re.search(r"[,;:]\s*([^,;:]+)$", t)
        if m:
            tail = m.group(1).strip().rstrip(".!?")
            tail_words = tail.split()
            if len(t) >= 18 and (len(tail_words) <= 3 or len(tail) <= 14):
                score += 2

        # Các bullet rất ngắn có xu hướng là nhãn (label), nhưng vẫn giữ không gian cho các sự thật ngắn thực sự.
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
        """Bắt buộc số lượng slide của deck phải chính xác bằng `desired_slides`.

        - Nếu quá nhiều slide: cắt bỏ bớt.
        - Nếu quá ít slide: tách bullet từ slide có nhiều bullet nhất.
        """
        if not isinstance(structured_content, dict):
            return structured_content
        desired_slides = int(desired_slides)
        if desired_slides <= 0:
            return structured_content

        slides = structured_content.get("slides") or []
        if not isinstance(slides, list):
            return structured_content

        valid_slides = [
            slide
            for slide in slides
            if isinstance(slide, dict)
            and str(slide.get("title") or "").strip()
            and isinstance(slide.get("bullets"), list)
            and any(str(value or "").strip() for value in slide.get("bullets") or [])
        ]
        if len(valid_slides) == desired_slides and len(valid_slides) == len(slides):
            return structured_content

        if hasattr(self, "_request_json_dict"):
            current_deck = {
                "title": str(structured_content.get("title") or "Presentation"),
                "slides": valid_slides,
            }
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a senior presentation editor. Recompose the supplied deck into exactly "
                        f"{desired_slides} coherent slides. Preserve the original topic, language, facts, numbers, "
                        "requested sections, and narrative order. Merge overlapping slides when reducing the count; "
                        "create a genuinely distinct missing section from the deck context when increasing it. "
                        "Never truncate the tail, duplicate a slide, move an unrelated bullet, add generic filler, "
                        "or invent unsupported numbers. Preserve table/chart/image/layout fields when their slide is kept. "
                        "Every slide must have a complete title, non-empty bullets, and useful speaker notes. "
                        "Return strict JSON with title and slides only."
                    ),
                },
                {
                    "role": "user",
                    "content": "CURRENT DECK JSON:\n" + json.dumps(current_deck, ensure_ascii=False),
                },
            ]
            for attempt in range(2):
                try:
                    candidate = await self._request_json_dict(
                        messages,
                        target_slides=desired_slides,
                        fast_mode=False,
                        compose_mode=True,
                        structured_output="slide_deck",
                    )
                    candidate_slides = candidate.get("slides") if isinstance(candidate, dict) else None
                    if (
                        isinstance(candidate_slides, list)
                        and len(candidate_slides) == desired_slides
                        and all(
                            isinstance(slide, dict)
                            and str(slide.get("title") or "").strip()
                            and isinstance(slide.get("bullets"), list)
                            and any(str(value or "").strip() for value in slide.get("bullets") or [])
                            for slide in candidate_slides
                        )
                    ):
                        print(
                            f"[slide_normalizer] AI recomposed deck to {desired_slides} slides "
                            f"(attempt={attempt + 1})"
                        )
                        return candidate
                    messages.append({
                        "role": "user",
                        "content": (
                            f"The previous result did not contain exactly {desired_slides} complete slides. "
                            "Retry the full deck without duplicate or filler slides."
                        ),
                    })
                except Exception as error:
                    print(f"[slide_normalizer] AI slide-count compose failed: {error}")
                    break

        print(
            f"[slide_normalizer] keeping original deck: unable to safely reach "
            f"{desired_slides} slides from {len(slides)}"
        )
        return structured_content
