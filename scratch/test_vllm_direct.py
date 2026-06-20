import asyncio
import httpx
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.append(str(backend_dir))

from config import VLLM_API_BASE_URL, LLM_MODEL

async def main():
    print(f"vLLM URL: {VLLM_API_BASE_URL}")
    print(f"Model: {LLM_MODEL}")
    
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello! Reply with exactly 'Hello World'"}
        ],
        "temperature": 0.1,
        "max_tokens": 50
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{VLLM_API_BASE_URL}/v1/chat/completions", json=payload)
            print("STATUS CODE:", resp.status_code)
            print("RESPONSE:", resp.text)
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    asyncio.run(main())
