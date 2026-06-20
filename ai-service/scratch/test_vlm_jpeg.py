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

from services.images.validation import _vlm_judge_image

async def test_vlm():
    # Download a small public JPEG image for testing
    img_url = "https://picsum.photos/200/300.jpg"
    print(f"Downloading test JPEG image from: {img_url}")
    
    async with httpx.AsyncClient() as client:
        r = await client.get(img_url, follow_redirects=True)
        r.raise_for_status()
        img_bytes = r.content
        print(f"Downloaded {len(img_bytes)} bytes. First 4 bytes: {img_bytes[:4]}")
        
        slide = {"title": "Test Slide", "bullets": ["A test bullet point about tech"]}
        semantic = {"content_type": "normal", "main_topic": "Test Topic"}
        
        print("\n--- Running VLM Judge (should fail if mime_type mismatch strictly checked) ---")
        try:
            res = await _vlm_judge_image(
                client,
                image_bytes=img_bytes,
                prompt="a test illustration of tech",
                slide=slide,
                semantic=semantic,
                min_relevance=0.5,
            )
            print("VLM Result:", res)
        except Exception as e:
            print("VLM Failed with exception:")
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_vlm())
