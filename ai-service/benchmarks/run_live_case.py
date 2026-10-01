"""Run one versioned benchmark case against a running AI API (images disabled)."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def _json_request(url: str, data: bytes | None = None, *, content_type: str = "application/x-www-form-urlencoded") -> dict:
    headers = {"Content-Type": content_type} if data else {}
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _submission_payload(case: dict) -> tuple[bytes, str]:
    fields = {
        "slide_count": str(case["target_slides"]),
        "plan": "pro",
        "generate_images": "false",
    }
    if case.get("mode") == "prompt":
        fields["text"] = case["input"]
        return urllib.parse.urlencode(fields).encode("utf-8"), "application/x-www-form-urlencoded"
    if case.get("mode") != "document":
        raise ValueError("This runner supports prompt and document fixtures only")
    fields["text"] = case.get("instruction") or (
        "Tạo bài thuyết trình bao quát toàn bộ nội dung tài liệu và giữ nguyên các số liệu, ngày tháng trong nguồn."
        if case.get("language") == "vi"
        else "Create a presentation covering the entire source document and preserve its factual details."
    )
    boundary = f"lecgen-benchmark-{uuid.uuid4().hex}"
    parts = []
    for key, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    parts.extend([
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="fixture.txt"\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n'.encode("utf-8"),
        case["input"].encode("utf-8"),
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ])
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def run_case(case: dict, base_url: str, timeout: int, *, task_id: str = "") -> tuple[dict, dict]:
    started = time.monotonic()
    resumed = bool(task_id)
    if not task_id:
        payload, content_type = _submission_payload(case)
        submitted = _json_request(
            f"{base_url}/api/generate-slide-spec", payload, content_type=content_type
        )
        task_id = submitted.get("task_id")
    if not task_id:
        raise RuntimeError("Generation did not return a task_id")
    deadline = started + timeout
    while time.monotonic() < deadline:
        status = _json_request(f"{base_url}/api/status/{task_id}")
        state = status.get("status")
        if state in {"completed", "error", "cancelled"}:
            result = status.get("result") or {}
            deck = result.get("deck") or {}
            report = {
                "case_id": case["id"],
                "task_id": task_id,
                "status": state,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "resumed": resumed,
                "slide_count": len(deck.get("slides") or []),
                "error": result.get("error") if state != "completed" else None,
            }
            return deck, report
        time.sleep(3)
    return {}, {
        "case_id": case["id"], "task_id": task_id, "status": "timeout",
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "resumed": resumed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--output-dir", default=str(Path.home() / "lecgen-benchmark"))
    parser.add_argument("--task-id", default="", help="Resume an existing task without another AI call")
    args = parser.parse_args()
    cases = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
    case = next((item for item in cases if item["id"] == args.case_id), None)
    if case is None:
        parser.error(f"Unknown case: {args.case_id}")
    try:
        deck, report = run_case(
            case, args.base_url.rstrip("/"), args.timeout, task_id=args.task_id
        )
    except (OSError, ValueError, RuntimeError, urllib.error.HTTPError) as error:
        print(json.dumps({"case_id": args.case_id, "status": "request_error", "error_type": type(error).__name__}))
        return 1
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if deck:
        (output_dir / f"{args.case_id}.json").write_text(
            json.dumps(deck, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (output_dir / f"{args.case_id}.run.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
