from services.llm_telemetry import monotonic_start, record_llm_call


class _Owner:
    _telemetry_task_id = "task-123"


def test_ledger_contains_metadata_but_no_content(capsys):
    owner = _Owner()
    event = record_llm_call(
        owner,
        purpose="planner",
        provider="vllm",
        model="test-model",
        started_at=monotonic_start(),
        status="success",
        max_tokens=1200,
        json_mode=True,
    )

    assert event["purpose"] == "planner"
    assert event["task_id"] == "task-123"
    assert owner._llm_call_ledger == [event]
    assert "prompt" not in event
    assert "response" not in event
    assert "[llm_telemetry]" in capsys.readouterr().out


def test_ledger_is_bounded():
    owner = _Owner()
    for _ in range(505):
        record_llm_call(
            owner,
            purpose="test",
            provider="gemini",
            model="test-model",
            started_at=monotonic_start(),
            status="success",
            max_tokens=1,
            json_mode=False,
        )

    assert len(owner._llm_call_ledger) == 500

