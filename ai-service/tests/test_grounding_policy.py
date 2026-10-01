from services.generation_context import GenerationContext, GenerationMode, bind_legacy_extractor_state
from services.grounding_policy import (
    GroundingMode,
    extract_numeric_anchors,
    policy_for_extractor,
    sparse_document_slide_cap,
    unsupported_numeric_anchors,
)


class Extractor:
    _telemetry_task_id = ""


def test_document_policy_uses_source_as_authority_and_preserves_numeric_forms():
    extractor = Extractor()
    bind_legacy_extractor_state(
        extractor,
        GenerationContext(
            mode=GenerationMode.DOCUMENT,
            source_text="Revenue was 12.5% in 2024.",
            user_instruction="Add exactly 3 questions.",
        ),
    )
    policy = policy_for_extractor(extractor, "Revenue was 12.5% in 2024 and cost ₫ 2,000.")

    assert policy.mode == GroundingMode.DOCUMENT
    assert policy.source_is_authoritative is True
    assert extract_numeric_anchors("12.5%, 2024, then 12.5%") == ("12.5%", "2024")
    assert policy.numeric_anchors == ("12.5%", "2024", "₫ 2,000", "3")
    assert "cannot override source facts" in policy.instruction_block()


def test_prompt_policy_allows_foundational_knowledge_without_claiming_document_evidence():
    extractor = Extractor()
    bind_legacy_extractor_state(
        extractor,
        GenerationContext(mode=GenerationMode.PROMPT, user_instruction="Explain AI"),
    )
    policy = policy_for_extractor(extractor, "Expanded background text with 10 examples")

    assert policy.mode == GroundingMode.PROMPT
    assert policy.numeric_anchors == ()
    assert "stable foundational knowledge" in policy.instruction_block()
    assert unsupported_numeric_anchors(["A claim of 99%"], policy) == ()


def test_document_policy_reports_only_numeric_claims_absent_from_source():
    extractor = Extractor()
    bind_legacy_extractor_state(extractor, GenerationContext(mode=GenerationMode.DOCUMENT))
    policy = policy_for_extractor(extractor, "Accuracy was 91% in 2023.")

    assert unsupported_numeric_anchors(
        ["Accuracy was 91% in 2023, not 97% in 2025."], policy
    ) == ("97%", "2025")


def test_sparse_document_slide_cap_shrinks_a_thin_source():
    source = (
        "PAGE 1\nTong quan du an va boi canh.\n\n"
        "PAGE 2\nPhuong phap trien khai theo ba giai doan.\n\n"
        "PAGE 99\nKet qua bat buoc o cuoi tai lieu: ty le hoan thanh dat 87.6% vao ngay 31/12/2025."
    )
    assert sparse_document_slide_cap(source, 8) == 5


def test_sparse_document_slide_cap_does_not_shrink_a_fact_dense_source():
    source = (
        "PAGE 1\nDoanh thu nam 2024 dat 12.5 ty dong.\n\n"
        "PAGE 2\nQuy I dat 2.1 ty; Quy II dat 3.0 ty; Quy III dat 3.4 ty; Quy IV dat 4.0 ty."
    )
    assert sparse_document_slide_cap(source, 7) == 7


def test_sparse_document_slide_cap_never_raises_the_requested_count():
    assert sparse_document_slide_cap("A single short fact sentence here.", 3) == 3
    assert sparse_document_slide_cap("", 8) == 8
