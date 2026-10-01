from routes.api import _new_task_content_extractor


def test_each_task_gets_isolated_content_extractor_state():
    first = _new_task_content_extractor("task-a")
    second = _new_task_content_extractor("task-b")

    first._source_content = "private source A"
    first._presentation_mode = "lecture"

    assert first is not second
    assert second._source_content == ""
    assert getattr(second, "_presentation_mode", "") != "lecture"
    assert first._telemetry_task_id == "task-a"
    assert second._telemetry_task_id == "task-b"

