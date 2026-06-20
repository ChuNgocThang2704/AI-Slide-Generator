import asyncio
import os
import json
import sys
import redis.asyncio as aioredis

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = aioredis.from_url(redis_url, decode_responses=True)
    
    status_keys = await client.keys("status:*")
    print("Found status keys:", status_keys)
    
    for key in status_keys:
        task_id = key.split(":")[-1]
        print(f"\n==================== TASK {task_id} ====================")
        
        task_val = await client.get(f"task:{task_id}")
        status_val = await client.get(f"status:{task_id}")
        
        if task_val:
            tdata = json.loads(task_val)
            print("Action:", tdata.get("action"))
            print("Slide Count:", tdata.get("slide_count"))
            print("Slide Theme:", tdata.get("slide_theme"))
            print("Generate Images:", tdata.get("generate_images"))
            raw = tdata.get("raw_content") or ""
            print("Raw Content Length:", len(raw))
            print("Raw Content Preview:", repr(raw[:300]))
        else:
            print("No task data found")
            
        if status_val:
            sdata = json.loads(status_val)
            print("Status:", sdata.get("status"))
            print("Progress:", sdata.get("progress"))
            res = sdata.get("result") or {}
            print("Result Keys:", list(res.keys()))
            if "download_url" in res:
                print("Download URL:", res["download_url"])
            if "error" in res:
                print("Error:", res["error"])
        else:
            print("No status data found")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
