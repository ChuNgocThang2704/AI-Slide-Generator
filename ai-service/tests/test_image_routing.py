from services.images.pipeline import (
    _allows_generated_factual_fallback,
    _requires_factual_visual_source,
)
from services.images.semantics import _classify_risk
from services.images.prompts import _simplify_prompt_for_retry
from services.slide_quality import _heuristic_visual, _is_dense_for_image


def _slide(title: str, *bullets: str) -> dict:
    return {"title": title, "bullets": list(bullets)}


def test_operational_medical_content_is_not_forced_to_scientific_diagram():
    slide = _slide(
        "Hồ sơ bệnh án điện tử",
        "Bệnh viện số hóa quy trình chẩn đoán và thanh toán.",
    )
    assert _classify_risk(slide, {}, "process") is None


def test_generic_infrastructure_investment_is_not_finance_sensitive():
    slide = _slide(
        "Đầu tư hạ tầng y tế",
        "Các địa phương ưu tiên mạng và thiết bị bệnh viện.",
    )
    assert _classify_risk(slide, {}, "normal") is None


def test_electronic_payment_is_not_religious():
    slide = _slide(
        "Thanh toán điện tử",
        "Người dùng thanh toán dịch vụ trực tuyến.",
    )
    assert _classify_risk(slide, {}, "normal") is None


def test_anatomy_still_requires_scientific_visual_handling():
    slide = _slide("Giải phẫu tim", "Mô tả cấu trúc mạch máu và các buồng tim.")
    assert _classify_risk(slide, {}, "normal") == "medical_diagram"


def test_generic_scene_prefers_generation():
    semantic = {
        "visual_source": "generated",
        "requires_exact_identity": False,
        "requires_exact_location": False,
        "requires_exact_event": False,
        "requires_scientific_accuracy": False,
    }
    assert not _requires_factual_visual_source(semantic, "process", None)
    assert _allows_generated_factual_fallback(semantic)


def test_exact_real_world_subject_prefers_verified_source():
    semantic = {
        "visual_source": "stock",
        "requires_exact_location": True,
    }
    assert _requires_factual_visual_source(semantic, "normal", None)
    assert not _allows_generated_factual_fallback(semantic)


def test_scientific_reference_must_not_fall_back_to_generation():
    semantic = {
        "visual_source": "scientific_reference",
        "requires_scientific_accuracy": True,
    }
    assert _requires_factual_visual_source(semantic, "medical_diagram", "medical_diagram")
    assert not _allows_generated_factual_fallback(semantic)


def test_semantic_retry_prompt_is_short_and_keeps_slide_subject():
    prompt = _simplify_prompt_for_retry(
        {"main_topic": "hệ thống tưới tiêu tự động"},
        {"title": "Hệ thống tưới tiêu tự động", "bullets": ["Cảm biến độ ẩm điều khiển tưới."]},
        "process",
    )
    assert "tưới" in prompt.lower()
    assert len(prompt.split()) <= 35


def test_dense_slide_does_not_receive_decorative_image():
    slide = _slide(
        "IELTS Speaking Part 2",
        *(f"Technique {index}: " + "Explain the speaking strategy with a concrete example. " * 2 for index in range(8)),
    )
    assert _is_dense_for_image(slide)
    assert _heuristic_visual(slide, want_images=True) == "none"


def test_readable_concept_slide_can_still_receive_image():
    slide = _slide(
        "Smart agriculture",
        "Sensors measure soil moisture in real time.",
        "AI recommends an appropriate irrigation schedule.",
        "Farmers monitor the field from a mobile application.",
    )
    assert not _is_dense_for_image(slide)
    assert _heuristic_visual(slide, want_images=True) == "image"
