import sys
import httpx

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get("http://20.196.113.144:8000/api/status/ca5b93da-cb53-402a-90c9-0f9c78a67ade")
        data = resp.json()
        print("Status:", data.get("status"))
        result = data.get("result", {})
        if isinstance(result, dict):
            print("Root Title in JSON:", result.get("title"))
            slides = result.get("slides", [])
            print("Slides count:", len(slides))
            if slides:
                print("First slide title:", slides[0].get("title"))
        else:
            print("Result is not a dict:", type(result))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
