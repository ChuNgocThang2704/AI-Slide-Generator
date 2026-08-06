from io import BytesIO
import asyncio

import fitz
from PIL import Image

import services.source_visuals as source_visuals
from services.source_visuals import (
    extract_pdf_visual_candidates,
    match_source_visuals_to_slides,
    match_source_visuals_with_ai,
)


def _write_pdf_with_figure(path):
    image = Image.new("RGB", (400, 300), "white")
    for x in range(80, 320):
        for y in range(70, 230):
            image.putpixel((x, y), (110, 62, 35))
    buffer = BytesIO()
    image.save(buffer, format="PNG")

    document = fitz.open()
    page = document.new_page(width=600, height=800)
    page.insert_image(fitz.Rect(90, 90, 510, 405), stream=buffer.getvalue())
    page.insert_text(
        fitz.Point(90, 435),
        "Figure 1: Eucalyptus transverse-section specimen",
        fontsize=12,
    )
    document.save(path)
    document.close()


def test_extracts_embedded_pdf_figure_with_page_and_caption(tmp_path, monkeypatch):
    pdf_path = tmp_path / "research.pdf"
    _write_pdf_with_figure(pdf_path)
    monkeypatch.setattr(source_visuals, "IMAGE_DIR", tmp_path / "images")

    candidates = extract_pdf_visual_candidates(pdf_path, "source-test")

    assert candidates
    candidate = candidates[0]
    assert candidate["page"] == 1
    assert "Eucalyptus" in candidate["caption"]
    assert candidate["source"] == "pdf_embedded_image"
    assert candidate["width"] >= 256
    assert candidate["height"] >= 256


def test_matches_source_visual_by_page_and_caption():
    candidates = [
        {
            "path": "wood.jpg",
            "page": 4,
            "caption": "Figure 2: Eucalyptus transverse-section anatomy",
            "kind": "figure",
        },
        {
            "path": "curve.jpg",
            "page": 13,
            "caption": "Figure 4: DenseNet training and validation curves",
            "kind": "chart",
        },
    ]
    slides = [
        {
            "title": "Phương pháp thu thập dữ liệu",
            "bullets": ["Ảnh mặt cắt ngang gỗ được thu nhận bằng kính hiển vi."],
            "source_pages": [4],
            "layout": "text_image",
        },
        {
            "title": "Hiệu suất DenseNet-121",
            "bullets": ["Đường cong huấn luyện xác nhận khả năng hội tụ."],
            "source_pages": [13],
            "layout": "text_image",
        },
    ]

    matches = match_source_visuals_to_slides(candidates, slides, eligible_indices=[0, 1])

    assert matches[0]["path"] == "wood.jpg"
    assert matches[1]["path"] == "curve.jpg"


def test_does_not_match_without_source_page_provenance():
    matches = match_source_visuals_to_slides(
        [{"path": "figure.jpg", "page": 2, "caption": "Figure 1", "kind": "figure"}],
        [{"title": "Overview", "bullets": ["General context"], "layout": "text_image"}],
        eligible_indices=[0],
    )

    assert matches == {}


def test_ai_matching_supports_cross_language_captions():
    class FakeExtractor:
        async def _request_json_dict(self, messages, target_slides, fast_mode=False):
            return {
                "matches": [{
                    "slide_index": 0,
                    "candidate_index": 0,
                    "confidence": 0.92,
                }]
            }

    candidates = [{
        "path": "figure.jpg",
        "page": 14,
        "caption": "Training and validation accuracy curves for DenseNet",
        "kind": "chart",
    }]
    slides = [{
        "title": "Kết quả huấn luyện mô hình",
        "bullets": ["Độ chính xác hội tụ ổn định qua các epoch."],
        "source_pages": [14],
    }]
    matches = asyncio.run(match_source_visuals_with_ai(
        FakeExtractor(),
        candidates,
        slides,
        eligible_indices=[0],
        max_matches=1,
    ))
    assert matches[0]["path"] == "figure.jpg"
    assert matches[0]["match_source"] == "ai_multilingual"
