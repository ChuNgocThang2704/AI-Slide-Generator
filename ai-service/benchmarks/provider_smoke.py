"""One-token Gemini connectivity check without printing credentials or content."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    model = os.getenv("GEMINI_MODEL", "").strip()
    if not key or not model:
        print("provider_smoke: missing Gemini key or model")
        return 2
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = json.dumps({
        "contents": [{"parts": [{"text": "Reply OK."}]}],
        "generationConfig": {"maxOutputTokens": 8, "temperature": 0},
    }).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            result = json.load(response)
        count = len(result.get("candidates") or [])
        print(f"provider_smoke: model={model} status=200 candidates={count}")
        return 0 if count else 1
    except urllib.error.HTTPError as error:
        print(f"provider_smoke: model={model} http_status={error.code}")
        return 1
    except (OSError, ValueError) as error:
        print(f"provider_smoke: model={model} error_type={type(error).__name__}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
