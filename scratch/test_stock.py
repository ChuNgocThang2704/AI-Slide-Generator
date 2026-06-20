import sys
import os
import asyncio
import httpx
from pathlib import Path

# Add backend to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent / 'backend'))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / 'backend' / '.env')

from services.stock_photos import _search_wikimedia, _search_pexels
from config import PEXELS_API_KEY

async def test_search():
    queries = [
        'Economic Recovery and Development in North Vietnam (1954-1960) Vietnam 1954',
        'Economic Recovery and Development in North Vietnam (1954-1960)',
        'North Vietnam',
        'factory',
        'currency',
        'trade agreement'
    ]
    
    async with httpx.AsyncClient() as client:
        print("=== TESTING WIKIMEDIA SEARCH ===")
        for query in queries:
            results = await _search_wikimedia(client, query)
            print(f"Query: '{query}' -> Found {len(results)} results")
            for idx, r in enumerate(results[:2]):
                print(f"  [{idx}] URL: {r.get('image_url')}")
                
        print("\n=== TESTING PEXELS SEARCH ===")
        print(f"Pexels API Key configured: {bool(PEXELS_API_KEY)}")
        for query in queries:
            results = await _search_pexels(client, query, api_key=PEXELS_API_KEY)
            print(f"Query: '{query}' -> Found {len(results)} results")
            for idx, r in enumerate(results[:2]):
                print(f"  [{idx}] URL: {r.get('image_url')}")

if __name__ == '__main__':
    asyncio.run(test_search())
