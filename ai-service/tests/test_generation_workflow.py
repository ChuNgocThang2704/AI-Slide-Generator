import asyncio

import services.generation_workflow as workflow


class _Extractor:
    def __init__(self):
        self.force_calls = 0

    async def _force_slide_count_exact(self, deck, target):
        self.force_calls += 1
        return {**deck, "forced_to": target}


def test_locked_outline_skips_grounding(monkeypatch):
    calls = []

    async def grounding(*args, **kwargs):
        calls.append("ground")
        return args[1]

    async def finalize(_extractor, deck, **kwargs):
        calls.append("finalize")
        return {**deck, "_structure_locked": True, "_structure_signature": ["s1"]}

    monkeypatch.setattr(workflow, "improve_deck_source_grounding", grounding)
    monkeypatch.setattr(workflow, "finalize_deck_for_visuals", finalize)
    monkeypatch.setattr(workflow, "assert_deck_structure_locked", lambda deck: tuple(deck["_structure_signature"]))

    deck, signature = asyncio.run(workflow.ground_finalize_and_lock(
        _Extractor(), {"_outline_locked": True, "slides": [{}]}, raw_content="source",
        user_instruction="request", task_id="task", plan="pro", target_slides=1,
    ))

    assert calls == ["finalize"]
    assert signature == ("s1",)
    assert deck["_structure_locked"] is True


def test_legacy_deck_preserves_optional_count_repair(monkeypatch):
    calls = []

    async def grounding(_extractor, deck, *_args, **_kwargs):
        calls.append("ground")
        return deck

    async def finalize(_extractor, deck, **kwargs):
        calls.append("finalize")
        return {**deck, "_structure_locked": True, "_structure_signature": ["s1"]}

    monkeypatch.setattr(workflow, "improve_deck_source_grounding", grounding)
    monkeypatch.setattr(workflow, "finalize_deck_for_visuals", finalize)
    monkeypatch.setattr(workflow, "assert_deck_structure_locked", lambda deck: tuple(deck["_structure_signature"]))
    extractor = _Extractor()

    asyncio.run(workflow.ground_finalize_and_lock(
        extractor, {"slides": [{}]}, raw_content="source", user_instruction="request",
        task_id="task", plan="pro", target_slides=1,
        restore_exact_count_after_grounding=True,
    ))

    assert calls == ["ground", "finalize"]
    assert extractor.force_calls == 1

