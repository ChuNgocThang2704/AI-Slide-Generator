import sys
import os
import asyncio
import httpx
import traceback
from pathlib import Path

# Add backend to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent / 'backend'))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / 'backend' / '.env')

from services.images.providers import _try_secondary_ai_image_fallback

async def test_imagen():
    async with httpx.AsyncClient() as client:
        print("Calling Imagen fallback...")
        try:
            res = await _try_secondary_ai_image_fallback(
                client,
                prompt="a beautiful landscape of Vietnam, soft lighting",
                negative_prompt="text, blurry",
                payload_template={"width": 1024, "height": 1024}
            )
            if res:
                print(f"Success! Generated {len(res)} bytes of image.")
            else:
                print("Failed to generate image (returned None). Check console/debug outputs above.")
        except Exception as e:
            print("Failed with exception:")
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_imagen())
