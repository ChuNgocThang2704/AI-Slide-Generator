import asyncio
import os
import json
import sys
import redis.asyncio as aioredis

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = aioredis.from_url(redis_url, decode_responses=True)
    
    task_ids = [
        "3deb1b53-9d73-4e62-b392-2d92bc1f6f4b",
        "5dcd6e74-b9c2-4cdf-848b-e2287c57c9b9",
        "2ac12137-fba5-4b57-a7cd-5ad96e27f8e1",
        "1b9535eb-7db5-4c4f-8bc9-06de480a3341",
        "7a46f7af-dd1b-4a6e-9b14-5fd3f00d3a24",
        "9fb00d0f-75ac-47c4-887a-170efaee2fcf",
        "a7f30d54-143e-45fb-a9df-30803b1745a0",
        "c5080ba6-287a-44ba-a1c9-7e57e5c5e183"
    ]
    
    for tid in task_ids:
        print(f"\n==================== TASK {tid} ====================")
        task_val = await client.get(f"task:{tid}")
        status_val = await client.get(f"status:{tid}")
        
        if task_val:
            tdata = json.loads(task_val)
            print("Action:", tdata.get("action"))
            # Print first 200 chars of raw_content
            raw_c = tdata.get("raw_content") or ""
            print("Raw Content Preview:", repr(raw_c[:300]))
        else:
            print("No task data")
            
        if status_val:
            sdata = json.loads(status_val)
            print("Status:", sdata.get("status"))
            res = sdata.get("result") or {}
            print("Result Keys:", list(res.keys()))
            if "download_url" in res:
                print("Download URL:", res["download_url"])
        else:
            print("No status data")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
