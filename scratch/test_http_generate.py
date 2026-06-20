import httpx
import json

url = "http://localhost:8000/api/generate-slide-full"
data = {
    "text": "Bối cảnh Việt Nam sau Hiệp định Giơ-ne-vơ (1954)",
    "plan": "pro",
    "slide_theme": "modern",
    "generate_images": "false"
}

try:
    response = httpx.post(url, data=data, timeout=10.0)
    print("STATUS:", response.status_code)
    try:
        print("RESPONSE JSON:", response.json())
    except Exception:
        print("RESPONSE TEXT:", response.text[:1000])
except Exception as e:
    print("ERROR:", e)
