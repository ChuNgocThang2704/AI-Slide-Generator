import sys
import os
import asyncio
import httpx
from pathlib import Path
from PIL import Image
import io

# Add backend to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent / 'backend'))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / 'backend' / '.env')

from services.stock_photos import _download_image

async def test_downloads():
    urls = [
        "https://upload.wikimedia.org/wikipedia/commons/a/a2/20_Vi%E1%BB%87t_-_Democratic_Republic_of_Vietnam_%281948%29_02.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/0/0a/5_H%C3%A0o_-_North_Vietnam_%281946%29_01.jpg",
        "https://images.pexels.com/photos/28536956/pexels-photo-28536956.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
        "https://images.pexels.com/photos/30144941/pexels-photo-30144941.jpeg?auto=compress&cs=tinysrgb&h=650&w=940"
    ]
    
    async with httpx.AsyncClient() as client:
        for idx, url in enumerate(urls):
            print(f"\n--- Downloading URL [{idx}]: {url[:100]}... ---")
            res = await _download_image(client, url)
            if res is None:
                print("Download failed or image too small.")
            else:
                print(f"Download succeeded! Extension: {res['extension']}, bytes: {len(res['bytes'])}")
                # Check dimensions
                with Image.open(io.BytesIO(res['bytes'])) as img:
                    print(f"Dimensions: {img.size}")

if __name__ == '__main__':
    asyncio.run(test_downloads())
