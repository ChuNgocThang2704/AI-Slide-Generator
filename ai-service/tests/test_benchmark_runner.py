from benchmarks.run_live_case import _submission_payload


def test_prompt_payload_is_form_encoded():
    payload, content_type = _submission_payload({
        "mode": "prompt", "target_slides": 8, "input": "Giới thiệu AI",
    })
    assert content_type == "application/x-www-form-urlencoded"
    assert b"slide_count=8" in payload
    assert b"generate_images=false" in payload


def test_document_payload_uploads_utf8_txt_as_file():
    payload, content_type = _submission_payload({
        "mode": "document", "target_slides": 7, "input": "Doanh thu 12,5 tỷ",
    })
    boundary = content_type.split("boundary=", 1)[1]
    assert content_type.startswith("multipart/form-data; boundary=")
    assert b'name="file"; filename="fixture.txt"' in payload
    assert b'name="text"' in payload
    assert "Doanh thu 12,5 tỷ".encode("utf-8") in payload
    assert f"--{boundary}--\r\n".encode() in payload
