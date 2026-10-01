import asyncio

from services.quality_pass_telemetry import quality_pass_summary, run_measured_deck_pass


class Owner:
    _llm_call_ledger = []


def test_measured_pass_records_changed_slide_fields_without_content():
    owner = Owner()
    owner._llm_call_ledger = []
    deck = {"title": "Deck", "slides": [{"title": "A", "bullets": ["Old"], "notes": ""}]}

    async def change_bullets(current):
        owner._llm_call_ledger.append({"purpose": "fake"})
        return {"title": "Deck", "slides": [{"title": "A", "bullets": ["New"], "notes": ""}]}

    result = asyncio.run(run_measured_deck_pass(owner, "test_pass", deck, change_bullets))
    event = owner._quality_pass_ledger[0]

    assert result["slides"][0]["bullets"] == ["New"]
    assert event["changed_slide_indices"] == [0]
    assert event["changed_fields"] == ["bullets"]
    assert event["llm_calls"] == 1
    assert "Old" not in str(event) and "New" not in str(event)


def test_summary_counts_no_effect_passes():
    owner = Owner()
    owner._llm_call_ledger = []
    deck = {"slides": [{"title": "A", "bullets": ["Stable"]}]}

    async def unchanged(current):
        return current

    asyncio.run(run_measured_deck_pass(owner, "noop", deck, unchanged))
    summary = quality_pass_summary(owner)

    assert summary["passes"] == 1
    assert summary["no_effect_passes"] == 1
    assert summary["changed_slide_events"] == 0


def test_safe_skip_does_not_execute_operation_and_records_reason():
    owner = Owner()
    owner._llm_call_ledger = []
    deck = {"slides": [{"title": "A", "bullets": ["Stable"]}]}
    called = []

    async def must_not_run(current):
        called.append(True)
        return current

    result = asyncio.run(run_measured_deck_pass(
        owner,
        "coverage",
        deck,
        must_not_run,
        skip_reason="no_user_instruction_to_audit",
    ))

    assert result is deck
    assert called == []
    assert owner._quality_pass_ledger[0]["skipped"] is True
    assert owner._quality_pass_ledger[0]["skip_reason"] == "no_user_instruction_to_audit"
