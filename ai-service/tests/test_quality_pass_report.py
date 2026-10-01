from benchmarks.summarize_quality_passes import parse_events, summarize


def test_quality_pass_log_parser_and_summary_ignore_unrelated_or_invalid_lines():
    events = parse_events([
        "server started",
        '[quality_pass] {"pass":"coherence","llm_calls":2,"no_effect":true,"changed_slide_count":0,"latency_ms":100}',
        'prefix [quality_pass] {"pass":"coherence","llm_calls":1,"no_effect":false,"changed_slide_count":2,"latency_ms":80}',
        "[quality_pass] invalid",
    ])
    report = summarize(events)

    assert report["total_events"] == 2
    assert report["passes"]["coherence"] == {
        "runs": 2,
        "executed_runs": 2,
        "skipped_runs": 0,
        "llm_calls": 3,
        "no_effect_runs": 1,
        "no_effect_rate": 0.5,
        "changed_slide_events": 2,
        "latency_ms": 180.0,
    }
