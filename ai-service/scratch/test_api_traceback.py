import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.append(str(backend_dir))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

try:
    response = client.post(
        "/api/generate-slide-full",
        data={
            "text": "Bối cảnh Việt Nam sau Hiệp định Giơ-ne-vơ (1954)",
            "plan": "pro",
            "slide_theme": "modern",
            "generate_images": "false"
        }
    )
    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
