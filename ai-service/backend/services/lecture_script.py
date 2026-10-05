"""Lecture script ("kịch bản dựng") for an uploaded slide deck.

The user brings a finished deck (PPTX or PDF). For each slide the lecturer's spoken words are
written, in the form a video team records from: an opening on camera, one scene per slide, a
closing on camera. Nothing here touches slide generation: the deck is only read.
"""

from __future__ import annotations

import asyncio
import io
import json
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from services.content.json_utils import parse_json_response

MAX_SLIDES = 80
WORDS_PER_MINUTE = 140          # the pace of the reference scripts (about 1100 words for 8 minutes)
_BATCH_SLIDES = 5
_PARALLEL_BATCHES = 3
_SLIDE_TEXT_CHARS = 1400
_COVER_WORDS = 40               # a first slide with no more words than this is the title slide
_FIGURE_AREA = 0.15             # a picture this large (share of the slide) is a figure, not a logo or an icon
_BACKGROUND_AREA = 0.85         # ... and one this large is the slide's background, not something to talk about
_MAX_IMAGES_PER_SLIDE = 2       # the largest pictures of a slide are looked at
_MAX_FIGURE_SLIDES = 40         # slides of one deck whose figures are looked at
_FIGURE_SIDE = 768              # pictures are shrunk to this many pixels before the model sees them (cost)
_PARALLEL_FIGURES = 3

SCENE_INTRO = "Lời mở đầu"
SCENE_OUTRO = "Lời kết"
NOTE_PRESENTER = "Hình ảnh GV"     # not filled in by the AI: the editing notes column is left to the video team

_EMU_PICTURE = 13
_EMU_GROUP = 6


# ── reading the deck ───────────────────────────────────────────────────────────

def _clean(text: Any) -> str:
    return re.sub(r"[ \t ]+", " ", str(text or "")).strip()


def _shape_lines(shape) -> List[str]:
    lines: List[str] = []
    if getattr(shape, "shape_type", None) == _EMU_GROUP:
        for child in shape.shapes:
            lines.extend(_shape_lines(child))
        return lines
    if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            text = _clean("".join(run.text for run in paragraph.runs) or paragraph.text)
            if text:
                lines.append(text)
    if getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            cells = [_clean(cell.text) for cell in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
    return lines


def _figure_count(shape, slide_area: float) -> int:
    kind = getattr(shape, "shape_type", None)
    if kind == _EMU_GROUP:
        return sum(_figure_count(child, slide_area) for child in shape.shapes)
    area = float(getattr(shape, "width", 0) or 0) * float(getattr(shape, "height", 0) or 0)
    if kind == _EMU_PICTURE:
        return 1 if slide_area and area / slide_area >= _FIGURE_AREA else 0
    if getattr(shape, "has_chart", False) and shape.has_chart:
        return 1
    return 0


def _picture_blobs(shape, slide_area: float) -> List[tuple]:
    """[(share of the slide, image bytes)] of the figure-sized pictures in `shape` (groups included)."""
    kind = getattr(shape, "shape_type", None)
    if kind == _EMU_GROUP:
        found: List[tuple] = []
        for child in shape.shapes:
            found.extend(_picture_blobs(child, slide_area))
        return found
    if kind != _EMU_PICTURE or not slide_area:
        return []
    area = float(getattr(shape, "width", 0) or 0) * float(getattr(shape, "height", 0) or 0)
    share = area / slide_area
    if not _FIGURE_AREA <= share <= _BACKGROUND_AREA:
        return []
    try:
        return [(share, shape.image.blob)]
    except Exception:
        return []


def read_pptx(data: bytes) -> List[Dict[str, Any]]:
    from pptx import Presentation

    deck = Presentation(io.BytesIO(data))
    slide_area = float(deck.slide_width or 1) * float(deck.slide_height or 1)
    slides: List[Dict[str, Any]] = []
    for number, slide in enumerate(deck.slides, start=1):
        title = ""
        try:
            if slide.shapes.title is not None:
                title = _clean(slide.shapes.title.text_frame.text)
        except Exception:
            title = ""
        lines: List[str] = []
        figures = 0
        pictures: List[tuple] = []
        for shape in slide.shapes:
            lines.extend(_shape_lines(shape))
            figures += _figure_count(shape, slide_area)
            pictures.extend(_picture_blobs(shape, slide_area))
        if not title and lines:
            title = lines[0]
        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = _clean(slide.notes_slide.notes_text_frame.text)
        pictures.sort(key=lambda item: item[0], reverse=True)
        slides.append({
            "number": number, "title": title[:200], "text": "\n".join(lines)[:_SLIDE_TEXT_CHARS],
            "notes": notes[:600], "has_figure": figures > 0,
            # The pictures themselves are only carried until their figures have been described.
            "images": [blob for _, blob in pictures[:_MAX_IMAGES_PER_SLIDE]],
        })
    return slides


def read_pdf(data: bytes) -> List[Dict[str, Any]]:
    import pymupdf

    slides: List[Dict[str, Any]] = []
    with pymupdf.open(stream=data, filetype="pdf") as document:
        for number, page in enumerate(document, start=1):
            lines = [_clean(line) for line in page.get_text("text").splitlines()]
            lines = [line for line in lines if line]
            page_area = float(page.rect.width * page.rect.height) or 1.0
            has_figure = False
            pictures = []
            for image in page.get_images(full=True):
                try:
                    for rect in page.get_image_rects(image[0]):
                        share = rect.width * rect.height / page_area
                        if _FIGURE_AREA <= share <= _BACKGROUND_AREA:
                            has_figure = True
                            pictures.append((share, document.extract_image(image[0]).get("image")))
                except Exception:
                    continue
            pictures = sorted((item for item in pictures if item[1]), key=lambda item: item[0], reverse=True)
            slides.append({
                "number": number, "title": (lines[0] if lines else "")[:200],
                "text": "\n".join(lines)[:_SLIDE_TEXT_CHARS], "notes": "", "has_figure": has_figure,
                "images": [blob for _, blob in pictures[:_MAX_IMAGES_PER_SLIDE]],
            })
    return slides


def read_deck(data: bytes, filename: str) -> List[Dict[str, Any]]:
    """[{number, title, text, notes, has_figure}] for every slide of a .pptx or .pdf deck."""
    name = str(filename or "").lower()
    if name.endswith(".pptx"):
        slides = read_pptx(data)
    elif name.endswith(".pdf"):
        slides = read_pdf(data)
    else:
        raise ValueError("Chỉ hỗ trợ file .pptx hoặc .pdf")
    if not slides:
        raise ValueError("Không đọc được slide nào trong file")
    if len(slides) > MAX_SLIDES:
        raise ValueError(f"File có {len(slides)} slide, tối đa {MAX_SLIDES} slide cho một kịch bản")
    # A deck saved as pictures (a scanned or image-only PDF) has nothing to read: writing a script
    # for it would mean inventing the lecture.
    if sum(1 for slide in slides if readable(slide)) < max(1, len(slides) // 3):
        raise ValueError(
            "File này gần như không có chữ đọc được (slide được lưu dưới dạng ảnh). "
            "Hãy dùng file .pptx gốc hoặc PDF xuất trực tiếp từ PowerPoint."
        )
    return slides


def readable(slide: Dict[str, Any]) -> bool:
    """Whether the slide carries enough words (on it or in its notes) to speak about."""
    return len(f"{slide.get('text') or ''} {slide.get('notes') or ''}".split()) >= 4


def has_cover(slides: List[Dict[str, Any]]) -> bool:
    """Whether slide 1 is a title slide: the opening on camera stands in for it."""
    return bool(slides) and len(slides) > 1 and len(str(slides[0].get("text") or "").split()) <= _COVER_WORDS


def looks_vietnamese(slides: List[Dict[str, Any]]) -> bool:
    sample = " ".join(str(slide.get("text") or "") for slide in slides[:12])
    marks = len(re.findall(r"[ăâêôơưđáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", sample.lower()))
    return marks >= max(3, len(sample) // 200)


# ── looking at the pictures ────────────────────────────────────────────────────

def shrink_image(blob: bytes) -> Optional[str]:
    """A picture as a small JPEG data URL; the model's price grows with the pixels, not the file size."""
    try:
        import base64
        from PIL import Image

        with Image.open(io.BytesIO(blob)) as image:
            image.load()
            if image.mode in ("RGBA", "LA", "P"):
                converted = image.convert("RGBA")
                flat = Image.new("RGB", converted.size, (255, 255, 255))
                flat.paste(converted, mask=converted.split()[-1])
                image = flat
            else:
                image = image.convert("RGB")
            image.thumbnail((_FIGURE_SIDE, _FIGURE_SIDE))
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii")
    except Exception as error:
        print(f"[lecture_script] cannot read a picture: {error!r}")
        return None


_DECORATIVE = "TRANG TRI"


def _fold(text: str) -> str:
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", str(text or "").upper().replace("Đ", "D")) if unicodedata.category(ch) != "Mn")


async def describe_figures(extractor, slides: List[Dict[str, Any]], vietnamese: bool) -> int:
    """Fills slide["figure"] with what the model sees in the pictures of each slide, then drops the pictures.

    Decorations (a photo, a logo, a pattern) get no description: there is nothing to teach from them.
    A failed call leaves the slide as it was, written from its text alone."""
    cover = has_cover(slides)
    work = [
        slide for slide in slides
        if slide.get("images") and not (cover and slide is slides[0])
    ][:_MAX_FIGURE_SLIDES]
    gate = asyncio.Semaphore(_PARALLEL_FIGURES)
    model = getattr(extractor, "model_name", None) or None

    async def look(slide: Dict[str, Any]) -> bool:
        urls = [url for url in (shrink_image(blob) for blob in slide.get("images") or []) if url]
        if not urls or not hasattr(extractor, "_llm_completion_plain_text"):
            return False
        if vietnamese:
            ask = (
                f"Đây là hình trong một slide bài giảng có tiêu đề \"{slide.get('title') or ''}\".\n"
                f"Chữ trên slide: {str(slide.get('text') or '')[:500]}\n\n"
                "Mô tả hình để giảng viên giảng cho người nghe không nhìn thấy hình: đó là loại hình gì (sơ đồ, biểu đồ, bảng, ảnh chụp màn hình, ảnh minh hoạ), "
                "các thành phần chính, nhãn chữ đọc được, mũi tên hay quan hệ giữa chúng, và ý nghĩa của hình với bài. "
                "Viết 2-4 câu tiếng Việt, chỉ nói điều thực sự nhìn thấy, không bịa. "
                f"Nếu hình chỉ để trang trí (ảnh nền, logo, họa tiết, ảnh người không mang thông tin) thì trả lời đúng hai chữ: {_DECORATIVE}."
            )
        else:
            ask = (
                f"This is a picture from a lecture slide titled \"{slide.get('title') or ''}\".\n"
                f"Text on the slide: {str(slide.get('text') or '')[:500]}\n\n"
                "Describe it for a lecturer who will explain it to listeners who cannot see it: the kind of picture (diagram, chart, table, screenshot, illustration), "
                "its main parts, readable labels, arrows or relations between them, and what it means for the lesson. "
                "2-4 sentences, only what is really visible, nothing invented. "
                f"If it is only decoration (a background, logo, pattern, a person with no information) answer exactly: {_DECORATIVE}."
            )
        content: List[Dict[str, Any]] = [{"type": "text", "text": ask}]
        content.extend({"type": "image_url", "image_url": {"url": url}} for url in urls)
        async with gate:
            try:
                text = await extractor._llm_completion_plain_text(
                    [{"role": "user", "content": content}], max_tokens=420, temperature=0.2,
                    call_purpose="lecture_script_figure", model_override=model,
                )
            except Exception as error:
                print(f"[lecture_script] figure of slide {slide.get('number')} failed: {error!r}")
                return False
        text = " ".join(str(text or "").split())
        if len(text) < 20 or _fold(text).startswith(_DECORATIVE) or _fold(text)[:20].startswith("TRANG TRI"):
            return False
        slide["figure"] = text[:700]
        return True

    try:
        results = await asyncio.gather(*(look(slide) for slide in work))
    finally:
        for slide in slides:
            slide.pop("images", None)       # never travels further: not into the task result, not into a saved set
    described = sum(1 for ok in results if ok)
    if work:
        print(f"[lecture_script] figures: {described}/{len(work)} slides described")
    return described

# ── writing the script ─────────────────────────────────────────────────────────

_STYLE_VI = """Bạn viết LỜI THOẠI cho giảng viên đọc khi quay video bài giảng (kịch bản dựng), dựa trên slide có sẵn.

Văn phong bắt buộc:
- Đây là lời NÓI của giảng viên trước sinh viên: tự nhiên, ấm áp, mạch lạc. Mặc định giảng viên xưng "thầy", gọi người học là "các em"; xen kẽ "chúng ta". (Nếu yêu cầu thêm của người dùng nêu cách xưng hô khác thì theo đó.)
- Giảng giải nội dung slide chứ không đọc lại nguyên văn: nêu ý, giải thích vì sao, nối các ý với nhau, thêm ví dụ ngắn khi slide quá cô đọng. Không bịa số liệu, tên riêng, mốc thời gian không có trên slide.
- ĐỘ DÀI: mỗi slide 5-7 đoạn, mỗi đoạn 1-2 câu, mỗi câu không quá 28 từ; tổng cộng khoảng 105-130 từ, KHÔNG BAO GIỜ quá 150 từ (slide rất ít nội dung: 60-90 từ). Giảng giải đủ ý: nói rõ khái niệm, vì sao nó quan trọng, một ví dụ hoặc hình ảnh so sánh ngắn khi slide có nhiều thuật ngữ. Các đoạn cách nhau bằng MỘT DÒNG TRỐNG.
- Mở đầu mỗi slide bằng một câu dẫn tự nhiên, đa dạng, ví dụ: "Chúng ta bắt đầu với...", "Mời các em quan sát...", "Vậy ... là gì?", "Tiếp theo, thầy sẽ...", "Các em thấy đấy,...". Không mở đầu slide nào bằng "Slide này" và không lặp một kiểu mở đầu ở hai slide liền nhau. Câu "Mời các em quan sát..." chỉ dùng cho slide có has_figure=true. Trong các slide được giao, mỗi kiểu mở đầu dùng nhiều nhất một lần.
- Cứ khoảng hai, ba slide thì có một câu hỏi gợi mở cho người học ("Theo các em, ...?", "Vậy ... là gì?") rồi tự trả lời ngay sau đó.
- Slide liệt kê nhiều ý thì đếm thành lời: "thứ nhất..., thứ hai..., và thứ ba...", mỗi ý một đoạn.
- Lời chào đã có ở phần Lời mở đầu: không slide nào chào lại hay "chào mừng" lại người học.
- Kết mỗi slide bằng một câu chốt ý hoặc một câu dẫn sang slide kế tiếp (dựa vào tiêu đề slide kế tiếp được cung cấp).
- Thuật ngữ tiếng Anh giữ nguyên, lần đầu xuất hiện thì đặt trong ngoặc sau từ tiếng Việt, ví dụ "Mối đe dọa (Threat)".
- Công thức, ký hiệu phải viết thành lời để đọc được: "Tấn công bằng Mối đe dọa cộng với Lỗ hổng", "K1 bằng K2".
- Danh sách trên slide được nói thành câu: "thứ nhất là..., thứ hai..., và cuối cùng...".
- Chỉ văn xuôi thuần: không gạch đầu dòng, không markdown, không emoji, không ghi chú trong ngoặc vuông, không viết "(Slide 3)".
- Slide có hình/sơ đồ: nếu có "figure_description" (mô tả hình do AI đã xem) thì giảng giải đúng nội dung hình theo mô tả đó ("Ở sơ đồ này, ..."), nêu các thành phần và quan hệ chính để người nghe hiểu hình mà không cần nhìn; không thêm chi tiết ngoài mô tả. Không có mô tả mà slide ít chữ: mời người học quan sát hình theo tiêu đề, không tả chi tiết bạn không biết.

Ví dụ lời thoại đúng văn phong (chỉ để học giọng văn, không chép nội dung):
---
Chúng ta bắt đầu với phần 2.1: Khái quát về Mối đe dọa, Lỗ hổng và Tấn công.

Thầy muốn hỏi các em một câu: Theo các em, điều gì khiến một hệ thống máy tính không còn an toàn?

Đó chính là sự kết hợp giữa 3 yếu tố: Mối đe dọa (Threat), Điểm yếu (Weakness) và Lỗ hổng (Vulnerability).

Mối đe dọa là hành động gây hại, điểm yếu là lỗi tồn tại trong hệ thống, còn lỗ hổng là điểm yếu cho phép mối đe dọa gây tác hại thực sự.

Các em hãy nhớ rằng, mọi hệ thống đều luôn có điểm yếu, vấn đề là chúng ta quản lý chúng như thế nào.
---
Mời các em quan sát sơ đồ về quan hệ giữa Mối đe dọa và Lỗ hổng.

Các em thấy đấy, mối đe dọa sẽ khai thác lỗ hổng để dẫn đến một cuộc tấn công.

Có ba nguyên lý cốt lõi ở đây: thứ nhất là mối đe dọa thường nhắm vào các lỗ hổng đã biết.

Thứ hai, nếu tồn tại lỗ hổng thì khả năng bị tấn công là rất cao.

Và thứ ba, công thức kinh điển: Tấn công bằng Mối đe dọa cộng với Lỗ hổng.

Nếu chúng ta giảm thiểu được lỗ hổng, khả năng bị tấn công sẽ giảm xuống đáng kể.
---"""

_STYLE_EN = """You write the SPOKEN SCRIPT a lecturer reads when recording a lecture video, based on an existing slide deck.

Required style:
- It is the lecturer speaking to students: natural, warm, clear. Use "I" for the lecturer, "you" for the learners and "we" together (unless the user's extra request asks for something else).
- Explain the slide rather than read it out: state the point, say why it matters, connect the ideas, add a short example when the slide is terse. Never invent figures, names or dates that are not on the slide.
- LENGTH: 5-7 paragraphs per slide, 1-2 sentences each, no sentence over 28 words; about 105-130 words in total and NEVER more than 150 (60-90 for a sparse slide). Explain enough: the concept, why it matters, and a short example or comparison when the slide has many terms. Paragraphs are separated by ONE BLANK LINE.
- Open each slide with a natural, varied lead-in ("Let's start with...", "Take a look at...", "So what is...?"). Never open with "This slide" and never use the same opener on two slides in a row.
- The greeting belongs to the opening scene: no slide greets or welcomes the learners again.
- Close each slide with a takeaway or a bridge to the next slide (its title is given).
- Say formulas and symbols in words. Turn lists into sentences ("first..., second..., and finally...").
- Plain prose only: no bullets, no markdown, no emoji, no bracketed stage directions.
- For a slide with a figure: when "figure_description" is given (what the AI saw in the picture), explain the figure from it ("In this diagram, ..."), naming its parts and relations so a listener understands it without seeing it; add nothing beyond the description. Without a description, on a slide with little text: invite the learners to look at the figure according to the title and do not describe details you do not know."""


def _style(vietnamese: bool) -> str:
    return _STYLE_VI if vietnamese else _STYLE_EN


def _outline(slides: List[Dict[str, Any]]) -> str:
    return "\n".join(f"{slide['number']}. {slide.get('title') or '(không có tiêu đề)'}" for slide in slides)


def _user_request(prompt: str, vietnamese: bool) -> str:
    text = _clean(prompt)[:1500]
    if not text:
        return ""
    head = "Yêu cầu thêm của người dùng (ưu tiên cao hơn mặc định ở trên)" if vietnamese else "Extra request from the user (overrides the defaults above)"
    return f"\n\n{head}:\n{text}"


def _strip_fence(text: str) -> str:
    return str(text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()


def tidy_script(text: Any) -> str:
    """Spoken prose only: markdown, bullets and stage directions the model slipped in are removed,
    and paragraphs are separated by exactly one blank line."""
    raw = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"\*\*(.+?)\*\*", r"\1", raw)
    raw = re.sub(r"(?m)^\s*(?:[-•*–]\s+|#{1,6}\s+)", "", raw)
    raw = re.sub(r"\[[^\]\n]{0,60}\]", "", raw)
    paragraphs = [" ".join(part.split()) for part in re.split(r"\n\s*\n|\n", raw)]
    return "\n\n".join(part for part in paragraphs if part)


def word_count(text: Any) -> int:
    return len(str(text or "").split())


def estimated_minutes(rows: List[Dict[str, Any]]) -> int:
    words = sum(word_count(row.get("script")) for row in rows)
    return max(1, round(words / WORDS_PER_MINUTE)) if words else 0


async def _ask_json(extractor, messages, *, max_tokens: int, purpose: str) -> Optional[Dict[str, Any]]:
    raw = await extractor._llm_completion_plain_text(
        messages, max_tokens=max_tokens, temperature=0.6, json_mode=True, call_purpose=purpose,
    )
    parsed = parse_json_response(raw, clean_result_text=_strip_fence)
    return parsed if isinstance(parsed, dict) else None


async def _write_batch(
    extractor, deck_title: str, outline: str, batch: List[Dict[str, Any]], next_title: str,
    prompt: str, vietnamese: bool, previous: Optional[Dict[int, str]] = None,
) -> Dict[int, str]:
    payload = {
        "deck_title": deck_title,
        "slides": [
            {
                "slide": slide["number"], "title": slide.get("title") or "", "text_on_slide": slide.get("text") or "",
                "presenter_notes": slide.get("notes") or "", "has_figure": bool(slide.get("has_figure")),
                **({"figure_description": slide["figure"]} if slide.get("figure") else {}),
                **({"current_script": previous[slide["number"]]} if previous and previous.get(slide["number"]) else {}),
            }
            for slide in batch
        ],
        "title_of_the_slide_after_these": next_title,
    }
    task = (
        "Viết lời thoại cho từng slide trong \"slides\". "
        if vietnamese else "Write the script for every slide in \"slides\". "
    )
    if previous:
        task += (
            "Mỗi slide đã có \"current_script\": hãy viết lại theo yêu cầu thêm của người dùng, giữ những gì yêu cầu không đụng tới. "
            if vietnamese else
            "Each slide has a \"current_script\": rewrite it to follow the user's extra request and keep what the request does not touch. "
        )
    system = (
        _style(vietnamese) + _user_request(prompt, vietnamese)
        + ("\n\nDàn ý toàn bộ bài (để nối mạch, không viết lời cho slide ngoài danh sách được giao):\n" if vietnamese
           else "\n\nOutline of the whole deck (for continuity only; write nothing for slides you were not given):\n")
        + outline
        + "\n\n" + task
        + ("Trả về DUY NHẤT JSON: {\"items\":[{\"slide\":số,\"script\":\"lời thoại, các đoạn cách nhau bằng \\n\\n\"}]} "
           "với đúng một phần tử cho mỗi slide được giao, theo đúng thứ tự."
           if vietnamese else
           "Return ONLY JSON: {\"items\":[{\"slide\":number,\"script\":\"the script, paragraphs separated by \\n\\n\"}]} "
           "with exactly one item per slide given, in order.")
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    wanted = {slide["number"] for slide in batch}
    found: Dict[int, str] = {}
    for _ in range(2):
        try:
            parsed = await _ask_json(extractor, messages, max_tokens=700 + 520 * len(batch), purpose="lecture_script_slides")
        except Exception as error:
            print(f"[lecture_script] batch {sorted(wanted)} failed: {error!r}")
            parsed = None
        for item in (parsed or {}).get("items") or []:
            if not isinstance(item, dict):
                continue
            try:
                number = int(item.get("slide"))
            except (TypeError, ValueError):
                continue
            script = tidy_script(item.get("script"))
            if number in wanted and word_count(script) >= 12:
                found.setdefault(number, script)
        if wanted <= set(found):
            break
    return found


async def _write_frame(
    extractor, deck_title: str, outline: str, prompt: str, vietnamese: bool,
    previous: Optional[Dict[str, str]] = None, full_intro: bool = False, cover_text: str = "",
) -> Dict[str, str]:
    """The two on-camera scenes: the opening before slide 2 and the closing after the last slide.

    Only the first video of a course opens by welcoming the learners and introducing the lecturer and
    the course; every other video opens with a short greeting and what this part is about."""
    if vietnamese:
        if full_intro:
            intro_spec = (
                "- \"intro\" (Lời mở đầu, 70-110 từ, 4-6 đoạn ngắn cách nhau bằng dòng trống): chào mừng người học, "
                "giới thiệu giảng viên và học phần/môn học (CHỈ những gì có ghi trên slide bìa trong \"cover_slide_text\"), "
                "nói ngắn gọn bài này sẽ giúp họ hiểu điều gì, mời vào nội dung. Kiểu: \"Chào các em.\\n\\nChào mừng các em đến với môn học...\".\n"
            )
        else:
            intro_spec = (
                "- \"intro\" (Lời mở đầu, 30-55 từ, 2-3 đoạn ngắn cách nhau bằng dòng trống): chỉ chào ngắn rồi nói phần này học gì "
                "(theo tiêu đề và dàn ý), mời vào nội dung. TUYỆT ĐỐI không chào mừng dài dòng, không giới thiệu tên giảng viên, "
                "tên trường hay tên học phần (đã giới thiệu ở video đầu tiên). "
                "Kiểu: \"Chào các em.\\n\\nTrong video này, chúng ta sẽ tìm hiểu về...\\n\\nCác em hãy cùng thầy đi vào nội dung chi tiết nhé.\".\n"
            )
        task = (
            "Viết hai đoạn giảng viên nói trước ống kính (không có slide):\n"
            + intro_spec
            + "- \"outro\" (Lời kết, 30-55 từ, MỘT đoạn): tóm lại vừa học xong phần gì, hẹn nội dung tiếp theo, chào. "
            "Kiểu: \"Vậy là chúng ta đã hoàn thành phần ... Xin chào và hẹn gặp lại các em.\"\n"
            "Không bịa tên giảng viên, tên trường hay tên môn học nếu slide không ghi."
        )
        task += (
            "\n- \"title\": tên ngắn của bài giảng này (tối đa 14 từ) nêu đúng các nội dung chính trong dàn ý, "
            "ví dụ \"Mối đe dọa, Lỗ hổng và Phân loại tấn công\"; không ghi tên trường, tên giảng viên."
        )
        shape = "Trả về DUY NHẤT JSON: {\"title\":\"...\",\"intro\":\"...\",\"outro\":\"...\"}"
    else:
        if full_intro:
            intro_spec = (
                "- \"intro\" (70-110 words, 4-6 short paragraphs separated by a blank line): welcome the learners, introduce the lecturer "
                "and the course (ONLY what the title slide in \"cover_slide_text\" says), say briefly what they will understand after it, "
                "lead into the content.\n"
            )
        else:
            intro_spec = (
                "- \"intro\" (30-55 words, 2-3 short paragraphs separated by a blank line): a short greeting, then what this part covers "
                "(from the title and outline), then lead into the content. Do NOT give a long welcome and do NOT introduce the lecturer, "
                "school or course (the first video did that).\n"
            )
        task = (
            "Write the two scenes the lecturer speaks on camera (no slide):\n"
            + intro_spec
            + "- \"outro\" (30-55 words, ONE paragraph): sum up what was covered, point to what comes next, say goodbye.\n"
            "Do not invent a lecturer, school or course name that the slides do not give."
        )
        task += "\n- \"title\": a short name for this lecture (at most 14 words) built from the main topics of the outline."
        shape = "Return ONLY JSON: {\"title\":\"...\",\"intro\":\"...\",\"outro\":\"...\"}"
    payload: Dict[str, Any] = {"deck_title": deck_title, "outline": outline}
    if full_intro and cover_text:
        payload["cover_slide_text"] = cover_text[:600]
    if previous:
        payload["current"] = previous
        task += ("\nĐã có bản hiện tại trong \"current\": viết lại theo yêu cầu thêm của người dùng." if vietnamese
                 else "\nThe current version is in \"current\": rewrite it to follow the user's extra request.")
    system = _style(vietnamese) + _user_request(prompt, vietnamese) + "\n\n" + task + "\n" + shape
    messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    for _ in range(2):
        try:
            parsed = await _ask_json(extractor, messages, max_tokens=900, purpose="lecture_script_frame")
        except Exception as error:
            print(f"[lecture_script] intro/outro failed: {error!r}")
            parsed = None
        intro, outro = tidy_script((parsed or {}).get("intro")), tidy_script((parsed or {}).get("outro"))
        if word_count(intro) >= 10 and word_count(outro) >= 8:
            title = " ".join(str((parsed or {}).get("title") or "").split()).strip(" .\"'")
            return {"intro": intro, "outro": outro.replace("\n\n", " "), "title": title if 2 <= len(title) <= 160 else ""}
    return {}


def _fallback_frame(deck_title: str, vietnamese: bool) -> Dict[str, str]:
    topic = deck_title or ("bài học hôm nay" if vietnamese else "today's lecture")
    if vietnamese:
        return {
            "intro": f"Chào các em.\n\nHôm nay, thầy và các em sẽ cùng tìm hiểu nội dung: {topic}.\n\nCác em hãy cùng thầy đi vào nội dung chi tiết nhé.",
            "outro": f"Vậy là chúng ta đã hoàn thành phần {topic}. Xin chào và hẹn gặp lại các em.",
        }
    return {
        "intro": f"Hello everyone.\n\nToday we will work through: {topic}.\n\nLet's get started.",
        "outro": f"That brings us to the end of {topic}. Thank you, and see you next time.",
    }


def deck_title_of(slides: List[Dict[str, Any]], filename: str = "") -> str:
    first = slides[0] if slides else {}
    lines = [line for line in str(first.get("text") or "").splitlines() if line.strip()]
    if has_cover(slides) and lines:
        # A title slide often stacks school, course and chapter: the last two lines name the lecture.
        named = [line for line in lines if 3 <= len(line) <= 90 and not re.search(r"ths\.|ts\.|pgs\.|gv\b|@|khoa\s", line.lower())]
        if named:
            return " – ".join(named[-2:]) if len(named) > 2 else " – ".join(named)
    title = _clean(first.get("title"))
    if title:
        return title
    return re.sub(r"\.(pptx|pdf)$", "", str(filename or ""), flags=re.IGNORECASE)


def assemble_rows(slides: List[Dict[str, Any]], scripts: Dict[int, str], frame: Dict[str, str]) -> List[Dict[str, Any]]:
    """Rows in the order the video is cut: opening, one row per slide, closing."""
    rows: List[Dict[str, Any]] = [
        {"scene": SCENE_INTRO, "slide": 1 if has_cover(slides) else None, "script": frame.get("intro", ""), "note": ""}
    ]
    for slide in slides[1:] if has_cover(slides) else slides:
        number = slide["number"]
        rows.append({
            "scene": f"Slide {number}", "slide": number, "script": scripts.get(number, ""),
            "note": "",
        })
    rows.append({"scene": SCENE_OUTRO, "slide": None, "script": frame.get("outro", ""), "note": ""})
    return rows


Progress = Callable[[int], Awaitable[None]]


async def write_script(
    extractor, slides: List[Dict[str, Any]], *, prompt: str = "", filename: str = "",
    previous_rows: Optional[List[Dict[str, Any]]] = None, on_progress: Optional[Progress] = None,
    first_video: bool = False,
) -> Dict[str, Any]:
    """The whole script for `slides`. With `previous_rows`, an existing script is rewritten to
    follow `prompt` instead of being written from nothing."""
    vietnamese = looks_vietnamese(slides)
    figures = await describe_figures(extractor, slides, vietnamese)
    deck_title = deck_title_of(slides, filename)
    outline = _outline(slides)
    body = slides[1:] if has_cover(slides) else slides

    previous_scripts: Dict[int, str] = {}
    previous_frame: Dict[str, str] = {}
    for row in previous_rows or []:
        if not isinstance(row, dict) or not str(row.get("script") or "").strip():
            continue
        if row.get("scene") == SCENE_INTRO:
            previous_frame["intro"] = str(row["script"])
        elif row.get("scene") == SCENE_OUTRO:
            previous_frame["outro"] = str(row["script"])
        elif isinstance(row.get("slide"), int):
            previous_scripts[row["slide"]] = str(row["script"])

    # A slide with no words is left for the user to write: nothing is made up for it.
    body = [slide for slide in body if readable(slide) or previous_scripts.get(slide["number"])]
    batches = [body[start:start + _BATCH_SLIDES] for start in range(0, len(body), _BATCH_SLIDES)]
    done = 0
    gate = asyncio.Semaphore(_PARALLEL_BATCHES)

    async def run(index: int, batch: List[Dict[str, Any]]) -> Dict[int, str]:
        nonlocal done
        following = batches[index + 1][0].get("title", "") if index + 1 < len(batches) else ""
        async with gate:
            result = await _write_batch(
                extractor, deck_title, outline, batch, following, prompt, vietnamese, previous_scripts or None,
            )
        done += 1
        if on_progress:
            await on_progress(10 + int(80 * done / max(1, len(batches) + 1)))
        return result

    frame_task = asyncio.create_task(
        _write_frame(
            extractor, deck_title, outline, prompt, vietnamese, previous_frame or None,
            full_intro=first_video, cover_text=str(slides[0].get("text") or "") if has_cover(slides) else "",
        )
    )
    results = await asyncio.gather(*(run(index, batch) for index, batch in enumerate(batches)))
    scripts: Dict[int, str] = {}
    for result in results:
        scripts.update(result)
    frame = await frame_task or {}
    if previous_frame:
        frame = {**previous_frame, **frame}
    frame = {**_fallback_frame(deck_title, vietnamese), **{key: value for key, value in frame.items() if value}}
    # A slide the model skipped keeps what it had before; a slide never written stays empty for the user to fill.
    for number, text in previous_scripts.items():
        scripts.setdefault(number, text)

    rows = assemble_rows(slides, scripts, frame)
    missing = [row["scene"] for row in rows if not row["script"].strip()]
    if len(missing) > max(1, len(rows) // 2):
        raise RuntimeError("AI chưa viết được kịch bản cho file này. Hãy thử lại sau ít phút.")
    return {
        "title": frame.get("title") or deck_title,
        "language": "vi" if vietnamese else "en",
        "slide_count": len(slides),
        "figures_described": figures,
        "duration_minutes": estimated_minutes(rows),
        "word_count": sum(word_count(row["script"]) for row in rows),
        "rows": rows,
        "missing": missing,
    }


# ── English subtitles ──────────────────────────────────────────────────────────

_TRANSLATE_KIND = (
    "paragraphs of a lecturer's spoken lecture script that will be shown as English subtitles: write natural, clear "
    "spoken English, keep the meaning and the register of a teacher talking to students, keep technical terms; where "
    "the Vietnamese gives a term with its English original in parentheses, use that English term once without repeating it"
)
_TRANSLATE_BATCH_CHARS = 3000


async def _translate_batch(extractor, batch: List[str]) -> List[Optional[str]]:
    """English for every string of `batch`, in order; a batch the model gets wrong is split in two and
    asked again, down to one string, so one stubborn paragraph cannot spoil its neighbours."""
    from services.visual_translate import translate_strings

    for _ in range(2):
        result = await translate_strings(extractor, batch, "en", _TRANSLATE_KIND)
        if result and all(result):
            return list(result)
    if len(batch) == 1:
        return [None]
    middle = len(batch) // 2
    return await _translate_batch(extractor, batch[:middle]) + await _translate_batch(extractor, batch[middle:])


async def translate_scripts(extractor, scripts: List[str], on_progress: Optional[Progress] = None) -> Dict[str, Any]:
    """{"items": [{"i": row index, "en": "..."}], "failed": [row index]} for Vietnamese `scripts`.

    Each script is cut into its paragraphs (the lines of the video) and translated paragraph by
    paragraph, so the English keeps the same blank-line structure and lines up with the Vietnamese."""
    pieces: List[tuple] = []          # (row index, paragraph index, text)
    counts: Dict[int, int] = {}
    for row, script in enumerate(scripts):
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n|\n", str(script or "")) if part.strip()]
        counts[row] = len(paragraphs)
        pieces.extend((row, position, text) for position, text in enumerate(paragraphs))
    batches: List[List[tuple]] = []
    current: List[tuple] = []
    size = 0
    for piece in pieces:
        if current and size + len(piece[2]) > _TRANSLATE_BATCH_CHARS:
            batches.append(current)
            current, size = [], 0
        current.append(piece)
        size += len(piece[2])
    if current:
        batches.append(current)

    done = 0
    gate = asyncio.Semaphore(_PARALLEL_BATCHES)

    async def run(batch: List[tuple]) -> List[Optional[str]]:
        nonlocal done
        async with gate:
            out = await _translate_batch(extractor, [text for _, _, text in batch])
        done += 1
        if on_progress:
            await on_progress(5 + int(90 * done / max(1, len(batches))))
        return out

    results = await asyncio.gather(*(run(batch) for batch in batches))
    english: Dict[int, Dict[int, Optional[str]]] = {}
    for batch, texts in zip(batches, results):
        for (row, position, _), text in zip(batch, texts):
            english.setdefault(row, {})[position] = text
    items: List[Dict[str, Any]] = []
    failed: List[int] = []
    for row in range(len(scripts)):
        if not counts.get(row):
            continue
        parts = [english.get(row, {}).get(position) for position in range(counts[row])]
        if any(part is None for part in parts):
            failed.append(row)            # a row with a missing line is not half-translated: it is left to try again
            continue
        items.append({"i": row, "en": "\n\n".join(tidy_script(part) for part in parts if part)})
    return {"items": items, "failed": failed}
